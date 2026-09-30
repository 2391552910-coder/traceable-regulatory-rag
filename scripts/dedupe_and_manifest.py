# -*- coding: utf-8 -*-
"""
知识库后处理：
  1. 规章类（regulation）多版本去重——同一名称保留内容最长（通常为最新全文）的一版，
     其余移入 data/knowledge_base_archive/；
  2. 处罚/通报类不去重（标题虽同，案件不同）；
  3. 从文件头重建统一清单 data/knowledge_base/manifest.json；
  4. 输出维度 / 类型 / 字数统计。

用法：python scripts/dedupe_and_manifest.py
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "data" / "knowledge_base"
ARCH = ROOT / "data" / "knowledge_base_archive"

HEAD_RE = {
    "doc_id": re.compile(r"@DOC_ID: (\S+)"),
    "title": re.compile(r"@TITLE: (.+)"),
    "type": re.compile(r"@TYPE: (\w+)"),
    "source": re.compile(r"@SOURCE: (.+)"),
    "date": re.compile(r"@DATE: (\S*)"),
    "dimension": re.compile(r"@DIMENSION: (\w+)"),
}


def parse_file(fp: Path) -> dict:
    head = fp.read_text(encoding="utf-8")[:800]
    meta = {k: (m.group(1).strip() if (m := p.search(head)) else "") for k, p in HEAD_RE.items()}
    body = fp.read_text(encoding="utf-8").split("---", 1)[-1]
    meta["chars"] = len(body)
    meta["file"] = fp.name
    return meta


def norm_title(t: str) -> str:
    t = re.sub(r"【第[^】]*】", "", t)
    t = re.sub(r"（\d{4}[^）]*）|\(\d{4}[^)]*\)", "", t)  # 去年号修订标记
    t = re.sub(r"关于修改[《〈＜].{0,30}决定》?的?", "", t)
    t = re.sub(r"证监会发布(修订后的|《)", "", t)
    t = re.sub(r"^中国证监会?", "", t)
    t = re.sub(r"[《》〈＜（）()\s·—\-]", "", t)
    return t


def main() -> None:
    ARCH.mkdir(exist_ok=True)
    docs = [parse_file(fp) for fp in sorted(KB.glob("DOC*.txt"))]
    print(f"入库文档 {len(docs)} 篇")

    # ---- 规章多版本去重 ----
    groups: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        if d["type"] == "regulation":
            groups[norm_title(d["title"])].append(d)
    moved = 0
    for key, members in groups.items():
        if len(members) <= 1 or not key:
            continue
        members.sort(key=lambda d: (d["chars"], d["date"]), reverse=True)
        keep = members[0]
        for d in members[1:]:
            shutil.move(str(KB / d["file"]), str(ARCH / d["file"]))
            moved += 1
        if len(members) > 1:
            print(f"  去重: {keep['title'][:36]} 保留({keep['chars']}字), 归档 {len(members)-1} 版")
    print(f"归档旧版 {moved} 篇")

    # ---- 重建 manifest ----
    docs = [parse_file(fp) for fp in sorted(KB.glob("DOC*.txt"))]
    (KB / "manifest.json").write_text(
        json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 统计 ----
    dims = Counter(d["dimension"] for d in docs)
    types = Counter(d["type"] for d in docs)
    total_chars = sum(d["chars"] for d in docs)
    print(f"\n最终 {len(docs)} 篇 | 类型 {dict(types)} | 维度 {dict(dims)}")
    print(f"总字数 {total_chars/1e4:.1f} 万 | 平均 {total_chars//max(len(docs),1)} 字/篇")


if __name__ == "__main__":
    main()
