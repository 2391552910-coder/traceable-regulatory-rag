# -*- coding: utf-8 -*-
"""
知识库扩充采集脚本：从国家法律法规数据库（flk.npc.gov.cn）采集监管法规全文。

流程（全部基于该站公开接口，无需登录）：
  1. POST /law-search/search/list          按标题关键词检索，取"有效"(sxx=3)条目
  2. GET  /law-search/search/flfgDetails   取元数据与 OSS 文件路径（优先 docx）
  3. GET  /law-search/amazonFile/ofdGenerateLink  换取带签名的下载 URL
  4. 签名 URL 的 Host 为内网域名，按 AWS SigV4 规则 Host 头参与签名，
     因此保持 Host 头不变、将 TCP 连接指向外网 IP 即可下载（stdlib socket 实现，
     不依赖 curl）。
  5. 解析 docx（zip+xml）提取条文文本；无 docx 时回退 PDF（pdfplumber 双栏重排）。
  6. 按仓库知识库格式写出 data/knowledge_base/DOCxxx_<slug>.txt 及
     collection_manifest.json（采集清单，便于复核与增量更新）。

用法：
  python scripts/collect_regulations.py --dry-run            # 只检索不落盘，看候选清单
  python scripts/collect_regulations.py --limit-per-kw 3     # 小批量验证
  python scripts/collect_regulations.py                      # 全量采集（默认每关键词 20 篇）
"""
from __future__ import annotations

import argparse
import io
import json
import re
import socket
import sys
import time
import zipfile
from pathlib import Path
from urllib import request as urlreq
from urllib.parse import urlsplit

BASE = "https://flk.npc.gov.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": BASE + "/",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}
ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "knowledge_base"
MANIFEST = KB_DIR / "collection_manifest.json"

# ---------------------------------------------------------------------------
# 检索词清单：按四维度组织。searchRange=1 表示按标题检索。
# ---------------------------------------------------------------------------
SEARCH_PLAN = [
    # D1 信息披露质量
    ("D1", "信息披露", 20),
    ("D1", "上市公司证券发行", 10),
    ("D1", "首次公开发行", 15),
    ("D1", "公开发行", 15),
    ("D1", "公司债券", 15),
    ("D1", "上市公司收购", 10),
    ("D1", "重大资产重组", 10),
    ("D1", "上市公司回购", 8),
    ("D1", "非上市公众公司", 10),
    # D2 董事会治理有效性
    ("D2", "公司法", 10),
    ("D2", "上市公司治理", 8),
    ("D2", "独立董事", 8),
    ("D2", "股东大会", 8),
    ("D2", "上市公司章程", 8),
    ("D2", "股权激励", 8),
    ("D2", "证券公司治理", 6),
    ("D2", "证券投资基金", 12),
    # D3 内部控制与合规性
    ("D3", "内部控制", 10),
    ("D3", "审计", 15),
    ("D3", "会计", 12),
    ("D3", "企业内部控制", 8),
    ("D3", "期货", 12),
    ("D3", "反洗钱", 6),
    ("D3", "证券公司监督管理", 6),
    # D4 第三方声誉
    ("D4", "诚信", 10),
    ("D4", "市场禁入", 8),
    ("D4", "行政处罚", 10),
    ("D4", "证券期货", 12),
    ("D4", "投资者保护", 8),
    ("D4", "证券公司风险", 6),
]

# 相关性白名单：标题须含金融监管核心词之一
INCLUDE_PAT = re.compile(
    r"(证券|股票|股份|股权|上市|公司|企业|债券|基金|期货|投资|融资|私募|保荐|承销|"
    r"收购|重组|披露|公示|审计|会计|财务|内部控制|内控|合规|诚信|信用|行政处罚|"
    r"市场禁入|洗钱|治理|董事|监事|股东|章程|资本|资产评估|反垄断|公平竞争|破产|"
    r"非法集资|金融监管|存款保险|金融稳定)"
)
# 明显无关的标题（误命中）过滤
EXCLUDE_PAT = re.compile(
    r"(地方|省|市|自治区|县|条例实施办法$|水文|环境|农业|教育|卫生|民政|公安|海关|税务征收|土地|矿产|森林|草原|渔业|气象|地震|档案|保密|统计法|计量|标准化|烟草|药品|医疗器械|食品安全|化妆品|疫苗|军|退役|工会|妇女|未成年|老年|残疾|华侨|归侨|台湾|香港|澳门|民族|宗教|体育|旅游|文物|图书馆|博物馆|电影|广播电视|出版|著作权|专利|商标|种子|畜牧|动物|植物|防洪|水土|防汛|抗旱|消防|安全生产|矿山|建筑|房地产|物业|城市|市容|道路|公路|铁路|民航|港口|航运|船舶|航行|邮政|电信|无线电|电力|煤炭|石油|天然气|节能|可再生|测绘|规划|住房|公积金|劳动|就业|工伤|养老|医疗|生育|失业|社会保险|低保|救助|慈善|红十字|献血|传染病|精神卫生|母婴|人口|计划生|殡葬|婚姻|收养|继承|户籍|出入境|护照|签证|国籍|国旗|国徽|国歌|首都|行政区划|边界|领海|海岛|专属经济区|国防|兵役|民兵|预备役|人民防空|装备|武器|保密|间谍|反恐怖|禁毒|戒严|集会|游行|示威|信访|行政复议|行政诉讼|国家赔偿|立法|监督法|代表法|议事规则|组织法|选举法|村民|居民委员会|人民调解|仲裁法|公证|律师|监狱|社区矫正|戒毒|检察|法院|法官|检察官|警|监狱|引渡|刑事|民事|诉讼|程序|证据|执行|海商|海事|票据|保险法|信托|商业|外贸|海关|关税|进出口|外汇|银行|人民银|银保监|存款|贷款|支付|清算|票据|信用证|银行卡|反假币|人民币|国库|预算|国债|税收|印花|增值|消费|企业所得|个人所得|车船|车辆|房产|契税|资源|污染|大气|土壤|噪声|固废|放射性|野生动|自然保护|湿地|黄河|长江|珠江|淮河|黑土地|船舶|烈士|青藏高原|生态|乳品|棉花|粮食|农产品|畜禽|生猪|饲料|兽药|农药|林业|荒漠|防沙|治沙|清洁生产|循环经济|政府信息公开|监察工作|涉税信息|计算机信息|信息网络|信息系统|视频图像|关键信息基础设施|外资保险|废旧金属|治安|中小企业促进|外国企业常驻|科学知识|科学技术|技术合同|广告|价格违法|促进法$)"
)

OSS_INTERNAL_HOST = "flkoss.obs-bj2-internal.cucloud.cn"
OSS_EXTERNAL_HOST = "flkoss.obs-bj2.cucloud.cn"


def http_json(url: str, payload: dict | None = None, timeout: int = 40) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urlreq.Request(url, data=data, headers=HEADERS, method="POST" if data else "GET")
    with urlreq.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_external_ip() -> str:
    return socket.gethostbyname(OSS_EXTERNAL_HOST)


def download_signed_url(url: str, connect_ip: str, timeout: int = 60) -> bytes:
    """下载签名 URL：Host 头保持内网域名（参与签名），TCP 连接指向外网 IP。"""
    u = urlsplit(url)
    path = u.path + ("?" + u.query if u.query else "")
    host = u.hostname
    port = u.port or 80
    req_lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}",
        "User-Agent: Mozilla/5.0",
        "Connection: close",
        "",
        "",
    ]
    raw_req = "\r\n".join(req_lines).encode("utf-8")
    with socket.create_connection((connect_ip, port), timeout=timeout) as sock:
        sock.sendall(raw_req)
        chunks, buf = [], b""
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)
        raw = b"".join(chunks)
    header, _, body = raw.partition(b"\r\n\r\n")
    status = int(header.split(b" ", 2)[1])
    if status != 200:
        raise RuntimeError(f"OSS download failed: HTTP {status}: {header[:200]!r}")
    # 处理 chunked 传输编码
    if b"chunked" in header.lower():
        body = _dechunk(body)
    return body


def _dechunk(data: bytes) -> bytes:
    out, i = io.BytesIO(), 0
    while True:
        j = data.find(b"\r\n", i)
        if j < 0:
            break
        size = int(data[i:j].split(b";")[0], 16)
        if size == 0:
            break
        out.write(data[j + 2: j + 2 + size])
        i = j + 2 + size + 2
    return out.getvalue()


def search(keyword: str, max_n: int) -> list[dict]:
    payload = {
        "searchRange": 1, "sxrq": [], "gbrq": [], "searchType": 2, "sxx": [],
        "gbrqYear": [], "flfgCodeId": [], "zdjgCodeId": [],
        "searchContent": keyword, "page": 1, "size": min(max_n * 2, 50),
    }
    res = http_json(f"{BASE}/law-search/search/list", payload)
    rows = res.get("rows") or []
    out = []
    for r in rows:
        if r.get("sxx") != 3:  # 仅保留"有效"
            continue
        title = re.sub(r"<[^>]+>", "", r.get("title") or "")
        if not INCLUDE_PAT.search(title) or EXCLUDE_PAT.search(title):
            continue
        out.append({**r, "title": title})
        if len(out) >= max_n:
            break
    return out


def get_detail(bbbs: str) -> dict:
    return http_json(f"{BASE}/law-search/search/flfgDetails?bbbs={bbbs}").get("data") or {}


def get_signed_url(file_path: str) -> str:
    res = http_json(f"{BASE}/law-search/amazonFile/ofdGenerateLink?filePath={file_path}")
    return res["file"]["download_url"]


def extract_docx(data: bytes) -> str:
    """stdlib 解析 docx 段落文本。"""
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        xml_data = zf.read("word/document.xml")
    root = ET.fromstring(xml_data)
    paras = []
    for p in root.iter(ns + "p"):
        text = "".join(t.text or "" for t in p.iter(ns + "t")).strip()
        if text:
            paras.append(text)
    return "\n\n".join(paras)


def extract_pdf(data: bytes) -> str:
    """pdfplumber 双栏重排提取（公报版式）。"""
    import pdfplumber

    pages_text = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            mid = page.width / 2
            left = page.crop((0, 0, mid, page.height)).extract_text() or ""
            right = page.crop((mid, 0, page.width, page.height)).extract_text() or ""
            pages_text.append(left + "\n" + right)
    return "\n\n".join(pages_text)


def clean_text(text: str) -> str:
    """清理页眉页脚与多余空白。"""
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if re.fullmatch(r"[—\-–=\d\s·]{2,}", ln):
            continue
        if re.fullmatch(r"第?\s*\d+\s*页?(共\s*\d+\s*页)?", ln):
            continue
        lines.append(ln)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(title: str, max_len: int = 24) -> str:
    s = re.sub(r"[《》（）()、，。：:；;\s]", "", title)
    return s[:max_len]


def next_doc_id(existing: list[str]) -> int:
    nums = [int(m.group(1)) for f in existing if (m := re.match(r"DOC(\d+)", f))]
    return max(nums, default=0) + 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只检索候选清单，不下载")
    ap.add_argument("--limit-per-kw", type=int, default=0, help="覆盖每个关键词的采集上限（调试用）")
    ap.add_argument("--sleep", type=float, default=0.6, help="请求间隔秒数")
    args = ap.parse_args()

    KB_DIR.mkdir(parents=True, exist_ok=True)
    plan = [(d, kw, (args.limit_per_kw or n)) for d, kw, n in SEARCH_PLAN]

    # 1) 检索汇总，按标题去重（保留最新公布日期）
    candidates: dict[str, dict] = {}
    for dim, kw, max_n in plan:
        try:
            rows = search(kw, max_n)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 搜索失败 {kw}: {e}", file=sys.stderr)
            continue
        for r in rows:
            key = r["title"]
            if key not in candidates or (r.get("gbrq") or "") > (candidates[key].get("gbrq") or ""):
                candidates[key] = {**r, "dimension": dim, "keyword": kw}
        print(f"[search] {dim} {kw}: {len(rows)} 条（累计候选 {len(candidates)}）")
        time.sleep(args.sleep)

    cand_list = sorted(candidates.values(), key=lambda r: (r["dimension"], r["title"]))
    print(f"\n候选法规 {len(cand_list)} 部（去重、仅有效、已排除明显无关领域）")
    if args.dry_run:
        for c in cand_list:
            print(f"  {c['dimension']}  {c['title']}  {c.get('flxz')}  {c.get('gbrq')}")
        return

    # 2) 下载 + 解析 + 写盘
    ext_ip = resolve_external_ip()
    print(f"OSS 外网 IP: {ext_ip}")
    doc_num = next_doc_id([p.name for p in KB_DIR.glob("DOC*.txt")])
    manifest, ok, fail = [], 0, 0
    for i, c in enumerate(cand_list, 1):
        title, bbbs, dim = c["title"], c["bbbs"], c["dimension"]
        try:
            detail = get_detail(bbbs)
            time.sleep(args.sleep)
            oss = detail.get("ossFile") or {}
            text, fmt = "", ""
            if oss.get("ossWordPath"):
                blob = download_signed_url(get_signed_url(oss["ossWordPath"]), ext_ip)
                text, fmt = extract_docx(blob), "docx"
            elif oss.get("ossPdfPath"):
                blob = download_signed_url(get_signed_url(oss["ossPdfPath"]), ext_ip)
                text, fmt = extract_pdf(blob), "pdf"
            else:
                raise RuntimeError("无可下载文件")
            text = clean_text(text)
            if len(text) < 200:
                raise RuntimeError(f"正文过短({len(text)}字)")

            doc_id = f"DOC{doc_num:03d}"
            doc_num += 1
            fp = KB_DIR / f"{doc_id}_{slugify(title)}.txt"
            date = (detail.get("gbrq") or c.get("gbrq") or "")[:10]
            src = detail.get("zdjgName") or c.get("zdjgName") or ""
            fp.write_text(
                f"@DOC_ID: {doc_id}\n@TITLE: {title}\n@TYPE: regulation\n"
                f"@SOURCE: {src}\n@DATE: {date}\n@DIMENSION: {dim}\n---\n{text}\n",
                encoding="utf-8",
            )
            manifest.append({
                "doc_id": doc_id, "title": title, "dimension": dim, "type": "regulation",
                "category": detail.get("flxz") or c.get("flxz"), "source": src, "date": date,
                "bbbs": bbbs, "format": fmt, "chars": len(text), "keyword": c["keyword"],
                "file": fp.name,
            })
            ok += 1
            print(f"[{i}/{len(cand_list)}] OK {doc_id} {title} ({len(text)}字, {fmt})")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(cand_list)}] FAIL {title}: {e}", file=sys.stderr)
        time.sleep(args.sleep)
        # 每 20 篇落一次 manifest，防中断丢失
        if i % 20 == 0:
            MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：成功 {ok}，失败 {fail}，清单 -> {MANIFEST}")


if __name__ == "__main__":
    main()
