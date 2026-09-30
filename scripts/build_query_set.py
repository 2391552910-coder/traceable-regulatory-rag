# -*- coding: utf-8 -*-
"""
检索评测查询集构建工具。

背景：原 8 条演示查询引用 DOC001-004（已归档的演示文档）。本脚本基于扩充后的
真实知识库重建查询集：
  - 手工设计 40 条查询（每维度 10 条），覆盖四维度典型监管问题；
  - 相关条款采用"维度内多关键词命中"弱监督预标（弱标注，label_source=weak），
    输出 retrieval_queries.csv 可直接跑通实验 02；
  - 同时输出 retrieval_queries_for_annotation.csv（隐藏答案、含候选池），
    供两位标注者独立复核，复核后按 docs/标注规范.md 计算 Cohen's Kappa，
    达成一致后替换为正式 gold 集。

用法：python scripts/build_query_set.py
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.clause_splitter import split_document  # noqa: E402
from src.data.knowledge_loader import load_documents  # noqa: E402

# (query, [必须全部命中的关键词组])；任一关键词组全命中即视为相关
QUERIES = [
    # ---------------- D1 信息披露 ----------------
    ("D1", "上市公司年度报告的披露时限", [["年度报告", "四个月"], ["年度报告", "披露", "个月"]]),
    ("D1", "信息披露真实准确完整的法定义务", [["真实", "准确", "完整"], ["虚假记载", "误导性陈述"]]),
    ("D1", "重大事件的临时报告披露义务", [["重大事件", "临时报告"], ["立即", "披露", "重大"]]),
    ("D1", "招股说明书的签署与责任", [["招股说明书", "签字"], ["招股说明书", "真实", "准确"]]),
    ("D1", "定期报告内容与格式准则要求", [["定期报告", "格式准则"], ["年度报告", "内容", "格式"]]),
    ("D1", "上市公司收购中的权益披露", [["权益变动", "披露"], ["收购", "持股比例", "披露"], ["5%", "权益"]]),
    ("D1", "重大资产重组的信息披露程序", [["重大资产重组", "披露"], ["重组", "董事会决议", "公告"]]),
    ("D1", "股东减持股份的信息披露", [["减持", "披露"], ["减持计划", "公告"]]),
    ("D1", "证券发行注册文件的要求", [["注册申请文件", "真实"], ["发行", "信息披露", "注册"]]),
    ("D1", "公司债券发行的信息披露", [["公司债券", "信息披露"], ["债券", "募集说明书"]]),
    # ---------------- D2 董事会治理 ----------------
    ("D2", "独立董事的独立性要求", [["独立董事", "独立性"], ["独立董事", "利害关系"]]),
    ("D2", "独立董事在董事会中的比例要求", [["独立董事", "三分之一"], ["独立董事", "比例"]]),
    ("D2", "股东大会的召集程序", [["股东大会", "召集"], ["股东大会", "通知", "公告"]]),
    ("D2", "董事会的职权与议事规则", [["董事会", "职权"], ["董事会", "议事规则"]]),
    ("D2", "监事会的监督职责", [["监事会", "监督"], ["监事会", "检查", "财务"]]),
    ("D2", "上市公司章程必备条款", [["章程", "必备条款"], ["章程指引"]]),
    ("D2", "股权激励的授予对象", [["股权激励", "激励对象"], ["限制性股票", "授予"]]),
    ("D2", "董事的忠实勤勉义务", [["忠实义务", "勤勉"], ["董事", "勤勉尽责"]]),
    ("D2", "控股股东与实际控制人行为规范", [["控股股东", "行为规范"], ["实际控制人", "不得"]]),
    ("D2", "董事会审计委员会的设置", [["审计委员会", "董事会"], ["专门委员会", "审计"]]),
    # ---------------- D3 内部控制与合规 ----------------
    ("D3", "内部控制的目标与原则", [["内部控制", "目标"], ["内部控制", "原则"]]),
    ("D3", "内部控制的五要素", [["内部环境"], ["风险评估"], ["信息与沟通"], ["内部监督"]]),
    ("D3", "财务会计报告的真实完整责任", [["财务会计报告", "真实"], ["财务报告", "真实", "完整"]]),
    ("D3", "注册会计师的审计责任", [["注册会计师", "审计", "责任"], ["审计报告", "注册会计师"]]),
    ("D3", "资金占用与违规担保的禁止性规定", [["资金占用"], ["违规担保"], ["占用", "担保", "不得"]]),
    ("D3", "财务造假的行政处罚与责任", [["财务造假", "处罚"], ["虚增", "利润", "处罚"]]),
    ("D3", "反洗钱客户身份识别义务", [["反洗钱", "客户身份"], ["客户身份识别"]]),
    ("D3", "期货业务的合规经营要求", [["期货", "合规"], ["期货经纪", "不得"]]),
    ("D3", "证券公司内部控制要求", [["证券公司", "内部控制"], ["内部控制指引", "证券公司"]]),
    ("D3", "审计委员会对财务报告的监督", [["审计委员会", "财务报告"], ["审计委员会", "监督"]]),
    ("D3", "证券公司风险处置措施", [["风险处置"], ["风险处置条例"]]),
    # ---------------- D4 第三方声誉 ----------------
    ("D4", "证券市场禁入的适用情形", [["市场禁入", "情形"], ["禁入", "终身"]]),
    ("D4", "操纵证券市场行为的认定", [["操纵", "证券市场"], ["操纵市场", "处罚"]]),
    ("D4", "内幕交易的构成要件", [["内幕交易", "内幕信息"], ["内幕信息", "知情人"]]),
    ("D4", "证券期货市场诚信记录管理", [["诚信", "记录"], ["诚信档案"]]),
    ("D4", "行政处罚听证程序", [["听证", "处罚"], ["听证程序"]]),
    ("D4", "上市公司现场检查的程序", [["现场检查", "程序"], ["现场检查", "上市公司"]]),
    ("D4", "中介机构未勤勉尽责的责任", [["中介机构", "勤勉尽责"], ["未勤勉尽责", "处罚"]]),
    ("D4", "短线交易的规制", [["六个月", "卖出"], ["短线交易"]]),
    ("D4", "私募基金的监督管理", [["私募"], ["非公开募集"]]),
]


def relevant_for(chunk, kw_groups) -> bool:
    text = chunk.text
    for group in kw_groups:
        if all(k in text for k in group):
            return True
    return False


def main() -> None:
    docs = load_documents(ROOT / "data" / "knowledge_base")
    chunks = []
    for d in docs:
        chunks.extend(split_document(d, strategy="clause"))
    by_dim: dict[str, list] = defaultdict(list)
    for c in chunks:
        if c.dimension:
            by_dim[c.dimension].append(c)
    print(f"知识库块数 {len(chunks)}")

    gold_rows, anno_rows = [], []
    for i, (dim, query, kw_groups) in enumerate(QUERIES, 1):
        pool = by_dim.get(dim, [])
        rel = [c.chunk_id for c in pool if relevant_for(c, kw_groups)]
        # 候选池：相关 + 同维度随机补足 20 条，供人工标注
        qid = f"Q{i:02d}"
        gold_rows.append({
            "query_id": qid, "dimension": dim, "query": query,
            "relevant_chunk_ids": ";".join(rel[:12]),
            "label_source": "weak_auto", "n_relevant": len(rel),
        })
        pool_ids = [c.chunk_id for c in pool if c.chunk_id not in rel][:20 - min(len(rel), 20)]
        anno_rows.append({
            "query_id": qid, "dimension": dim, "query": query,
            "candidate_chunk_ids": ";".join(rel[:12] + pool_ids),
            "annotator": "", "relevant_chunk_ids": "",
        })

    out1 = ROOT / "data" / "annotation" / "retrieval_queries.csv"
    with out1.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query_id", "dimension", "query",
                                          "relevant_chunk_ids", "label_source", "n_relevant"])
        w.writeheader()
        w.writerows(gold_rows)

    out2 = ROOT / "data" / "annotation" / "retrieval_queries_for_annotation.csv"
    with out2.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query_id", "dimension", "query",
                                          "candidate_chunk_ids", "annotator", "relevant_chunk_ids"])
        w.writeheader()
        w.writerows(anno_rows)

    n_empty = sum(1 for r in gold_rows if r["n_relevant"] == 0)
    print(f"查询 {len(gold_rows)} 条 -> {out1.name}（空相关集 {n_empty} 条需人工补充）")
    print(f"标注工作表 -> {out2.name}")
    for r in gold_rows:
        print(f"  {r['query_id']} {r['dimension']} 相关{r['n_relevant']:>3}  {r['query']}")


if __name__ == "__main__":
    main()
