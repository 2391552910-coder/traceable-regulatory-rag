# -*- coding: utf-8 -*-
"""
证监会官网（csrc.gov.cn）采集脚本：部门规章 / 规范性文件 / 行政处罚决定书。

流程：
  1. POST https://www.csrc.gov.cn/guestweb4/s   全站搜索（开普云站群接口）
  2. 解析结果页中的 content.shtml 链接与标题
  3. 抓取正文页，提取 <div class="content-body"> 内文本
  4. 按仓库知识库格式写出 data/knowledge_base/DOCxxx_<slug>.txt

用法：
  python scripts/collect_csrc.py --dry-run
  python scripts/collect_csrc.py --limit-per-kw 3   # 小批量验证
  python scripts/collect_csrc.py                    # 全量
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
from pathlib import Path
from urllib import parse, request as urlreq

BASE = "https://www.csrc.gov.cn"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "knowledge_base"
MANIFEST = KB_DIR / "collection_manifest_csrc.json"

# (dimension, keyword, doc_type, max_docs, title_filter)
# title_filter: 结果标题必须含此子串（防泛搜噪音）；为空则用 keyword 本身
SEARCH_PLAN = [
    # ---- 规章与规范性文件（regulation） ----
    ("D1", "上市公司信息披露管理办法", "regulation", 3, "信息披露管理办法"),
    ("D1", "上市公司定期报告格式准则", "regulation", 8, "报告"),
    ("D1", "公开发行证券的公司信息披露内容与格式准则", "regulation", 20, "信息披露"),
    ("D1", "上市公司重大资产重组管理办法", "regulation", 4, "重大资产重组"),
    ("D1", "上市公司收购管理办法", "regulation", 4, "收购管理办法"),
    ("D1", "上市公司股东减持股份管理暂行办法", "regulation", 4, "减持"),
    ("D1", "上市公司证券发行注册管理办法", "regulation", 5, "发行"),
    ("D1", "优先股试点管理办法", "regulation", 2, "优先股"),
    ("D1", "存托凭证发行与交易管理办法", "regulation", 2, "存托凭证"),
    ("D1", "上市公司股份回购规则", "regulation", 3, "回购"),
    ("D2", "上市公司治理准则", "regulation", 3, "治理准则"),
    ("D2", "上市公司独立董事管理办法", "regulation", 3, "独立董事"),
    ("D2", "上市公司股东大会规则", "regulation", 3, "股东大会"),
    ("D2", "上市公司章程指引", "regulation", 4, "章程指引"),
    ("D2", "上市公司股权激励管理办法", "regulation", 3, "股权激励"),
    ("D2", "上市公司董事和高级管理人员所持本公司股份", "regulation", 3, "董事"),
    ("D2", "上市公司监事会工作指引", "regulation", 2, "监事"),
    ("D3", "企业内部控制基本规范", "regulation", 2, "内部控制"),
    ("D3", "企业内部控制配套指引", "regulation", 3, "内部控制"),
    ("D3", "上市公司内部控制指引", "regulation", 4, "内部控制"),
    ("D3", "证券公司内部控制指引", "regulation", 3, "内部控制"),
    ("D3", "会计师事务所从事证券服务业务", "regulation", 4, "会计"),
    ("D3", "上市公司监管指引", "regulation", 12, "监管指引"),
    ("D4", "证券期货市场诚信监督管理办法", "regulation", 3, "诚信"),
    ("D4", "证券市场禁入规定", "regulation", 3, "禁入"),
    ("D4", "中国证监会行政处罚听证规则", "regulation", 2, "处罚"),
    ("D4", "上市公司现场检查规则", "regulation", 2, "检查"),
    # ---- 行政处罚决定书（penalty） ----
    ("D1", "行政处罚决定书 信息披露违法", "penalty", 25, "行政处罚"),
    ("D1", "行政处罚决定书 虚假记载", "penalty", 15, "行政处罚"),
    ("D3", "行政处罚决定书 内部控制", "penalty", 10, "行政处罚"),
    ("D3", "行政处罚决定书 财务造假", "penalty", 15, "行政处罚"),
    ("D4", "行政处罚决定书 市场禁入", "penalty", 10, "行政处罚"),
    ("D4", "行政处罚决定书 操纵市场", "penalty", 10, "行政处罚"),
    ("D4", "行政处罚决定书 内幕交易", "penalty", 10, "行政处罚"),
    # ---- 近年重大案件处罚通报（announcement） ----
    ("D1", "信息披露违法违规案 作出行政处罚", "announcement", 15, "行政处罚"),
    ("D3", "财务造假 行政处罚", "announcement", 12, "行政处罚"),
    ("D4", "操纵市场案 行政处罚", "announcement", 12, "行政处罚"),
    ("D4", "内幕交易案 行政处罚", "announcement", 12, "行政处罚"),
    ("D4", "作出行政处罚及市场禁入", "announcement", 12, "行政处罚"),
]

# 结果项两种形态：
#  1) <a href="//www.../content.shtml " ... data="栏目" ... title="完整标题">高亮文本</a>
#  2) <a href="http://www.../content.shtml" ... data="规章">标题文本</a>
CONTENT_RE = re.compile(
    r'href="((?:https?:)?//www\.csrc\.gov\.cn/csrc/[^"]*?/content\.shtml)\s*"'
    r'([^>]*)>(.*?)</a>',
    re.S,
)
DATA_RE = re.compile(r'data="([^"]{2,12})"')
TITLE_ATTR_RE = re.compile(r'title="([^"]{4,160})"')
# 非正式规章类结果排除
NEWS_PAT = re.compile(r"(征求意见|公开征求|新闻|发布会|答记者问|批复|复函|工作动态|简介)")


def fetch(url: str, data: bytes | None = None, timeout: int = 40) -> str:
    req = urlreq.Request(url, data=data, headers=HEADERS)
    with urlreq.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def search(keyword: str, max_n: int, want_penalty: bool = False) -> list[dict]:
    body = parse.urlencode({
        "searchWord": keyword, "uc": "1", "siteCode": "bm56000001", "column": "全部",
    }).encode("utf-8")
    html = fetch(f"{BASE}/guestweb4/s", data=body)
    seen, out = set(), []
    for url, attrs, inner in CONTENT_RE.findall(html):
        url = "https:" + url if url.startswith("//") else url
        if url in seen:
            continue
        m = TITLE_ATTR_RE.search(attrs)
        title = html_mod.unescape(m.group(1) if m else re.sub(r"<[^>]+>", "", inner)).strip()
        if not title or NEWS_PAT.search(title):
            continue
        channel = (DATA_RE.search(attrs) or [None, ""])[1] if DATA_RE.search(attrs) else ""
        if not want_penalty and channel in {"证监会要闻", "新闻"}:
            continue
        seen.add(url)
        out.append({"url": url, "title": title, "channel": channel})
        if len(out) >= max_n:
            break
    return out


CONTAINER_PATTERNS = [
    r'<div[^>]*class="detail-news"[^>]*>(.*?)(?=<div[^>]*class="(?:xxgk-down-box|share|fx|page)[^"]*"|<div[^>]*class="foot|<footer|$)',
    r'<div[^>]*class="content-body"[^>]*>(.*?)(?=<div class="clear">|<div[^>]*class="(?:share|fx|page)[^"]*"|<div[^>]*class="foot|$)',
    r'<div[^>]*class="detail_content"[^>]*>(.*?)(?=<div[^>]*class="(?:share|fx|page|clear)[^"]*"|<div[^>]*class="foot|$)',
    r'<div[^>]*class="TRS_Editor"[^>]*>(.*?)(?=<div[^>]*class="(?:share|fx|page|clear)[^"]*"|<div[^>]*class="foot|$)',
    r'<div[^>]*id="zoom"[^>]*>(.*?)(?=<div[^>]*class="(?:share|fx|page|clear)[^"]*"|<div[^>]*class="foot|$)',
]


def extract_content(html: str) -> str:
    body = ""
    for pat in CONTAINER_PATTERNS:
        m = re.search(pat, html, re.S)
        if m:
            body = m.group(1)
            break
    if not body:
        k = html.find("第一条")
        if k >= 0:
            body = html[k:]
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"<br\s*/?>", "\n", body)
    body = re.sub(r"</(p|div|tr|li|h\d)>", "\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    text = html_mod.unescape(body)
    text = re.sub(r"[\u2002\u2003\u3000]", " ", text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    cut = len(lines)
    for idx, l in enumerate(lines):
        if re.match(r"^(分享|打印|关闭|相关链接|上一篇|下一篇|网站地图|版权所有)", l):
            cut = idx
            break
    return "\n".join(lines[:cut])


ATTACH_RE = re.compile(r'href="([^"]+files/[^"]+?\.(?:pdf|docx?|wps))"', re.I)
ATTACH_BAD = re.compile(r"(立法说明|起草说明|修订说明|说明|解读|意见稿|反馈|中英文|英文)")


def _fetch_bytes(url: str, timeout: int = 60) -> bytes:
    req = urlreq.Request(url, headers=HEADERS)
    with urlreq.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def extract_attachment_text(page_html: str, page_url: str) -> str:
    """令/公告类页面正文在 PDF/DOCX 附件中：取第一个正文类附件解析。"""
    for href in ATTACH_RE.findall(page_html):
        label = href.split("/")[-1]
        if ATTACH_BAD.search(label):
            continue
        url = parse.urljoin(page_url, href)
        parts = parse.urlsplit(url)
        url = parse.urlunsplit((parts.scheme, parts.netloc, parse.quote(parts.path),
                                parts.query, parts.fragment))
        blob = _fetch_bytes(url)
        low = label.lower()
        if blob[:4] == b"%PDF":
            return _extract_pdf_bytes(blob)
        if blob[:2] == b"PK":  # docx/wps(实为zip)
            return _extract_docx_bytes(blob)
        if low.endswith((".doc", ".wps")):
            return ""  # 老 OLE 格式跳过
    return ""


def _extract_pdf_bytes(blob: bytes) -> str:
    import io

    import pdfplumber

    texts = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
    return "\n\n".join(t for t in texts if t)


def _extract_docx_bytes(blob: bytes) -> str:
    import io
    import zipfile
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        xml_data = zf.read("word/document.xml")
    root = ET.fromstring(xml_data)
    paras = []
    for p in root.iter(ns + "p"):
        t = "".join(x.text or "" for x in p.iter(ns + "t")).strip()
        if t:
            paras.append(t)
    return "\n\n".join(paras)


def extract_date(html: str) -> str:
    m = re.search(r'(\d{4}[-年]\d{1,2}[-月]\d{1,2})', html)
    if not m:
        return ""
    s = m.group(1).replace("年", "-").replace("月", "-").replace("日", "")
    parts = s.split("-")
    return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2][:2]):02d}" if len(parts) >= 3 else s


def slugify(title: str, max_len: int = 24) -> str:
    return re.sub(r"[《》（）()、，。：:；;\s]", "", title)[:max_len]


def next_doc_id(existing: list[str]) -> int:
    nums = [int(m.group(1)) for f in existing if (m := re.match(r"DOC(\d+)", f))]
    return max(nums, default=0) + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit-per-kw", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.8)
    args = ap.parse_args()

    KB_DIR.mkdir(parents=True, exist_ok=True)

    existing_urls: set[str] = set()
    for mf in KB_DIR.glob("collection_manifest*.json"):
        try:
            for it in json.loads(mf.read_text(encoding="utf-8")):
                if it.get("url"):
                    existing_urls.add(it["url"])
        except Exception:
            pass
    if existing_urls:
        print(f"增量模式：已采集 {len(existing_urls)} 个 URL，将跳过")

    candidates: dict[str, dict] = {}
    for dim, kw, dtype, max_n, tfilter in SEARCH_PLAN:
        max_n = args.limit_per_kw or max_n
        try:
            rows = search(kw, max_n * 3, want_penalty=(dtype in ("penalty", "announcement")))
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 搜索失败 {kw}: {e}", file=sys.stderr)
            continue
        kept = 0
        for r in rows:
            if tfilter not in r["title"] or r["url"] in candidates or r["url"] in existing_urls:
                continue
            candidates[r["url"]] = {**r, "dimension": dim, "type": dtype, "keyword": kw}
            kept += 1
            if kept >= max_n:
                break
        print(f"[search] {dim} {kw}: 命中 {len(rows)}，保留 {kept}（累计 {len(candidates)}）")
        time.sleep(args.sleep)

    cand_list = sorted(candidates.values(), key=lambda r: (r["type"], r["dimension"], r["title"]))
    print(f"\n候选文档 {len(cand_list)} 篇")
    if args.dry_run:
        for c in cand_list:
            print(f"  {c['dimension']} {c['type']:<10} {c['title'][:60]}")
        return

    doc_num = next_doc_id([p.name for p in KB_DIR.glob("DOC*.txt")])
    manifest: list[dict] = []
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            manifest = []
    ok, fail = 0, 0
    for i, c in enumerate(cand_list, 1):
        try:
            html = fetch(c["url"])
            text = extract_content(html)
            if len(text) < 200:
                # 回退：令/公告类页面正文在 PDF 附件中
                text = extract_attachment_text(html, c["url"])
            if len(text) < 200:
                raise RuntimeError(f"正文过短({len(text)}字)")
            doc_id = f"DOC{doc_num:03d}"
            doc_num += 1
            fp = KB_DIR / f"{doc_id}_{slugify(c['title'])}.txt"
            date = extract_date(html)
            fp.write_text(
                f"@DOC_ID: {doc_id}\n@TITLE: {c['title']}\n@TYPE: {c['type']}\n"
                f"@SOURCE: 中国证监会\n@DATE: {date}\n@DIMENSION: {c['dimension']}\n---\n{text}\n",
                encoding="utf-8",
            )
            manifest.append({"doc_id": doc_id, "title": c["title"], "dimension": c["dimension"],
                             "type": c["type"], "source": "中国证监会", "date": date,
                             "url": c["url"], "chars": len(text), "keyword": c["keyword"],
                             "file": fp.name})
            ok += 1
            print(f"[{i}/{len(cand_list)}] OK {doc_id} {c['title'][:50]} ({len(text)}字)")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(cand_list)}] FAIL {c['title'][:40]}: {e}", file=sys.stderr)
        time.sleep(args.sleep)
        if i % 20 == 0:
            MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：成功 {ok}，失败 {fail}，清单 -> {MANIFEST}")


if __name__ == "__main__":
    main()
