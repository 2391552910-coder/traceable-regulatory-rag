# -*- coding: utf-8 -*-
"""
证监会行政处罚决定书专项采集脚本。

数据来源：https://www.csrc.gov.cn/guestweb4/s 全站搜索（pageNum 分页，0 起）
        + 行政处罚栏目（c101928）正式决定书页面。

要点：
  - 决定书标题千篇一律（"中国证券监督管理委员会行政处罚决定书"），
    从 meta description / 正文提取当事人信息生成可读标题；
  - 维度标签依据正文违法事实关键词启发式判定（D1 信披 / D2 治理 / D3 内控财务 / D4 市场行为）。

用法：
  python scripts/collect_penalties.py --pages 12          # 翻 12 页（约 120 篇）
  python scripts/collect_penalties.py --pages 2 --sleep 0.5
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib import parse, request as urlreq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_csrc import (  # noqa: E402
    CONTENT_RE, DATA_RE, TITLE_ATTR_RE, extract_attachment_text, extract_content, fetch,
)

BASE = "https://www.csrc.gov.cn"
ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "knowledge_base"
MANIFEST = KB_DIR / "collection_manifest_penalty.json"

DIMENSION_RULES = [
    ("D1", re.compile(r"(信息披露|定期报告|年度报告|半年度报告|季度报告|虚假记载|误导性陈述|"
                      r"重大遗漏|未按期披露|未及时披露|披露义务|临时报告|关联交易.*未披露|"
                      r"未按规定披露|未如实披露)")),
    ("D3", re.compile(r"(内部控制|财务造假|虚增|虚减|虚构|审计报告|会计师|资金占用|违规担保|"
                      r"财务顾问|资产评估|伪造.*账|账外|两套账)")),
    ("D4", re.compile(r"(操纵市场|操纵证券|内幕交易|短线交易|泄露内幕|利用未公开信息|"
                      r"市场禁入|老鼠仓|蛊惑交易|抢帽子|编造.*虚假信息|传播虚假)")),
    ("D2", re.compile(r"(股东大会|董事会|监事会|独立董事|公司治理|勤勉尽责|忠实义务)")),
]

META_DESC_RE = re.compile(r'<meta\s+name="description"\s+content=\'([^\']+)\'')
NOISE_TITLE = "中国证券监督管理委员会行政处罚决定书"


def search_page(page_num: int) -> list[dict]:
    body = parse.urlencode({
        "searchWord": NOISE_TITLE, "uc": "1", "siteCode": "bm56000001",
        "column": "全部", "pageNum": page_num,
    }).encode("utf-8")
    html = fetch(f"{BASE}/guestweb4/s", data=body)
    out, seen = [], set()
    for url, attrs, inner in CONTENT_RE.findall(html):
        url = "https:" + url if url.startswith("//") else url
        if "/c101928/" not in url or url in seen:
            continue
        seen.add(url)
        out.append({"url": url})
    return out


def classify_dimension(text: str) -> str:
    scores = {}
    for dim, pat in DIMENSION_RULES:
        scores[dim] = len(pat.findall(text))
    best = max(scores, key=lambda k: (scores[k], "D4D3D1D2".find(k)))
    return best if scores[best] > 0 else "D3"


def make_title(page_html: str, text: str, url: str) -> str:
    """生成可读标题：决定书〔年份〕编号 + 当事人。"""
    m = META_DESC_RE.search(page_html)
    party = ""
    if m:
        seg = m.group(1)
        pm = re.search(r"当事人[:：]\s*([^,，。;；]{4,40})", seg)
        if pm:
            party = pm.group(1)
    if not party:
        pm = re.search(r"当事人[:：]\s*([^,，。;；\n]{4,40})", text)
        if pm:
            party = pm.group(1)
    num = ""
    nm = re.search(r"〔\s*(\d{4})\s*〕\s*(\d+)", text)
    if nm:
        num = f"〔{nm.group(1)}〕{nm.group(2)}号"
    cid = url.rstrip("/").split("/")[-2]
    title = f"中国证监会行政处罚决定书{num}"
    if party:
        # 清洗当事人名：去掉“（以下简称…）”及其后内容
        party = re.split(r"[（(]\s*以下简称|，|,\s*", party)[0]
        party = party.strip(" ，,。:：（）()“”\"'")
        if 2 < len(party) <= 30:
            title += f"（{party}）"
    return title or f"中国证监会行政处罚决定书_{cid}"


def slugify(title: str, max_len: int = 26) -> str:
    return re.sub(r"[《》（）()、，。：:；;\s〔〕【】]", "", title)[:max_len]


def next_doc_id(existing: list[str]) -> int:
    nums = [int(m.group(1)) for f in existing if (m := re.match(r"DOC(\d+)", f))]
    return max(nums, default=0) + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=12)
    ap.add_argument("--sleep", type=float, default=0.6)
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
    links, seen = [], set(existing_urls)
    for pn in range(args.pages):
        try:
            rows = search_page(pn)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 第{pn}页搜索失败: {e}", file=sys.stderr)
            continue
        for r in rows:
            if r["url"] not in seen:
                seen.add(r["url"])
                links.append(r)
        print(f"[page {pn}] 本页 {len(rows)} 条，累计 {len(links)}")
        time.sleep(args.sleep)

    doc_num = next_doc_id([p.name for p in KB_DIR.glob("DOC*.txt")])
    manifest: list[dict] = []
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            manifest = []
    ok, fail = 0, 0
    for i, c in enumerate(links, 1):
        try:
            html = fetch(c["url"])
            text = extract_content(html)
            if len(text) < 300:
                text = extract_attachment_text(html, c["url"])
            if len(text) < 300:
                raise RuntimeError(f"正文过短({len(text)}字)")
            title = make_title(html, text, c["url"])
            dim = classify_dimension(text)
            doc_id = f"DOC{doc_num:03d}"
            doc_num += 1
            fp = KB_DIR / f"{doc_id}_{slugify(title)}.txt"
            fp.write_text(
                f"@DOC_ID: {doc_id}\n@TITLE: {title}\n@TYPE: penalty\n"
                f"@SOURCE: 中国证监会\n@DATE: \n@DIMENSION: {dim}\n---\n{text}\n",
                encoding="utf-8",
            )
            manifest.append({"doc_id": doc_id, "title": title, "dimension": dim,
                             "type": "penalty", "source": "中国证监会", "url": c["url"],
                             "chars": len(text), "file": fp.name})
            ok += 1
            print(f"[{i}/{len(links)}] OK {doc_id} {dim} {title[:44]} ({len(text)}字)")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(links)}] FAIL {c['url'][-30:]}: {e}", file=sys.stderr)
        time.sleep(args.sleep)
        if i % 15 == 0:
            MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：成功 {ok}，失败 {fail}，清单 -> {MANIFEST}")


if __name__ == "__main__":
    main()
