"""
实验 02：检索质量评测（对应论文 RQ1）

对比检索配置：
  A. BM25-only          稀疏检索基线
  B. Dense-only         稠密向量基线（BGE-M3）
  C. Hybrid             双路融合
  D. Hybrid + 维度路由   本方法（维度路由子库检索）

指标：Recall@5 / MRR / nDCG@5，输出 CSV + 终端汇总表。
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, ROOT
from src.data.eval_dataset import load_retrieval_queries
from src.metrics.retrieval_metrics import aggregate, ndcg_at_k, recall_at_k, reciprocal_rank
from src.pipeline import build_knowledge_index, make_router


def evaluate_config(name: str, queries, search_fn, top_k: int = 5) -> dict:
    rows = []
    for q in queries:
        hits = search_fn(q)
        ranked_ids = [c.chunk_id for c, _ in hits]
        rows.append({
            "query_id": q.query_id,
            "recall@5": recall_at_k(ranked_ids, q.relevant, top_k),
            "mrr": reciprocal_rank(ranked_ids, q.relevant),
            "ndcg@5": ndcg_at_k(ranked_ids, q.relevant, top_k),
        })
    summary = aggregate(rows)
    summary["config"] = name
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=None, help="嵌入后端 bge/tfidf")
    parser.add_argument("--output", default=str(ROOT / "results" / "retrieval_eval.csv"))
    args = parser.parse_args()

    cfg = load_config()
    if args.backend:
        cfg["retrieval"]["embedding_backend"] = args.backend
    top_k = cfg["retrieval"]["top_k"]

    chunks, retriever = build_knowledge_index(cfg)
    router = make_router(retriever)
    queries = load_retrieval_queries(ROOT / "data" / "annotation" / "retrieval_queries.csv")
    print(f"知识库块数={len(chunks)}，评测查询数={len(queries)}")

    results = [
        evaluate_config("BM25-only", queries,
                        lambda q: retriever.bm25.search(q.query, top_k)),
        evaluate_config("Dense-only", queries,
                        lambda q: retriever.dense.search(q.query, top_k)),
        evaluate_config("Hybrid", queries,
                        lambda q: retriever.search(q.query, top_k)),
        evaluate_config("Hybrid+Routing (Ours)", queries,
                        lambda q: router.search(q.dimension, q.query, top_k, routed=True)),
    ]

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["config", "recall@5", "mrr", "ndcg@5"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'配置':<28}{'Recall@5':>10}{'MRR':>10}{'nDCG@5':>10}")
    for r in results:
        print(f"{r['config']:<28}{r['recall@5']:>10.3f}{r['mrr']:>10.3f}{r['ndcg@5']:>10.3f}")
    print(f"\n结果已保存：{args.output}")


if __name__ == "__main__":
    main()
