"""
实验 03：生成质量评测（对应论文 RQ2）

三组对照：no_rag / naive_rag / ours（引用约束 + 证据对齐）
流程：检索 → 评价生成 → 引用抽取 → 证据对齐 → 引用忠实度 + LLM-judge 评分
输出：results/generation_records.csv（明细）+ 按模式汇总表
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.alignment.citation_alignment import align_citations, citation_stats
from src.config import load_config, ROOT
from src.data.eval_dataset import load_company_samples
from src.generation.evaluator import Evaluator
from src.metrics.generation_metrics import judge_scores, summarize_generation
from src.pipeline import build_knowledge_index, make_llm, make_router
from src.retrieval.router import DIMENSIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="离线模板模式（冒烟测试）")
    parser.add_argument("--backend", default=None)
    parser.add_argument("--repeats", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config()
    if args.backend:
        cfg["retrieval"]["embedding_backend"] = args.backend
    repeats = args.repeats or cfg["generation"]["generation_repeats"]

    chunks, retriever = build_knowledge_index(cfg)
    router = make_router(retriever)
    llm = make_llm(cfg, mock=args.mock or None)
    evaluator = Evaluator(llm)
    samples = load_company_samples(ROOT / "data" / "companies")

    records = []
    for sample in samples:
        for dim, facts in sample["dimensions"].items():
            dim_name = DIMENSIONS.get(dim, dim)
            # 检索（维度路由）
            hits = router.search(dim, facts[:200], cfg["retrieval"]["top_k"], routed=True)
            regulations = router.format_for_prompt(hits)

            for mode in cfg["generation"]["modes"]:
                for _ in range(repeats):
                    regs = regulations if mode != "no_rag" else ""
                    result = evaluator.evaluate(
                        mode, sample["stock_name"], sample["stock_code"],
                        sample["year"], dim_name, facts, regs)
                    # 证据对齐：模型自报引用 + 正文扫描引用合并
                    citations = result.get("citations", []) + result.get("inline_citations", [])
                    aligned = align_citations(citations, hits)
                    stats = citation_stats(aligned)
                    # LLM-judge
                    judge = judge_scores(llm, result.get("evaluation", ""), regulations, facts)
                    records.append({
                        "sample": sample["stock_code"], "dimension": dim, "mode": mode,
                        "score": result.get("score"),
                        "evaluation": result.get("evaluation", ""),
                        "n_citations": stats["n_citations"],
                        "citation_accuracy": stats["citation_accuracy"],
                        "aligned": json.dumps(aligned, ensure_ascii=False),
                        **{k: v for k, v in judge.items() if k != "comment"},
                    })
                    print(f"[{sample['stock_code']} {dim} {mode}] "
                          f"引用={stats['n_citations']} 忠实度={stats['citation_accuracy']}")

    out = ROOT / "results" / "generation_records.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    summary = summarize_generation(records)
    print(f"\n{'模式':<12}{'引用数':>8}{'引用忠实度':>12}{'faithfulness':>14}{'coverage':>10}{'prof':>8}")
    for mode, s in summary.items():
        def fmt(v):
            return f"{v:.3f}" if isinstance(v, float) else "-"
        print(f"{mode:<12}{fmt(s['n_citations']):>8}{fmt(s['citation_accuracy']):>12}"
              f"{fmt(s['faithfulness']):>14}{fmt(s['coverage']):>10}{fmt(s['professionalism']):>8}")
    print(f"\n明细已保存：{out}")


if __name__ == "__main__":
    main()
