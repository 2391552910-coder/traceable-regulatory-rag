"""
实验 04：消融实验（对应论文 RQ3）

消融变量：
  1. 切分策略：clause（条款级）vs window（512 滑窗）
  2. 维度路由：routed vs 全库检索
  3. 融合权重：vector_weight ∈ {0.3, 0.5, 0.7, 0.9}
在检索评测集上跑 Recall@5 / MRR，验证各组件贡献。
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


def run_eval(retriever, router, queries, top_k: int, routed: bool) -> dict:
    rows = []
    for q in queries:
        hits = router.search(q.dimension, q.query, top_k, routed=routed)
        ranked = [c.chunk_id for c, _ in hits]
        rows.append({
            "recall@5": recall_at_k(ranked, q.relevant, top_k),
            "mrr": reciprocal_rank(ranked, q.relevant),
            "ndcg@5": ndcg_at_k(ranked, q.relevant, top_k),
        })
    return aggregate(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=None)
    args = parser.parse_args()

    cfg = load_config()
    if args.backend:
        cfg["retrieval"]["embedding_backend"] = args.backend
    top_k = cfg["retrieval"]["top_k"]
    queries = load_retrieval_queries(ROOT / "data" / "annotation" / "retrieval_queries.csv")

    rows = []
    # 消融 1 & 2：切分 × 路由
    for chunking in ("clause", "window"):
        _, retriever = build_knowledge_index(cfg, chunking=chunking)
        router = make_router(retriever)
        for routed in (True, False):
            summary = run_eval(retriever, router, queries, top_k, routed)
            rows.append({"ablation": "chunking×routing", "chunking": chunking,
                         "routing": routed, "vector_weight": cfg["retrieval"]["vector_weight"],
                         **summary})
            print(f"chunking={chunking:6s} routing={routed!s:5s} "
                  f"Recall@5={summary['recall@5']:.3f} MRR={summary['mrr']:.3f}")

    # 消融 3：融合权重
    _, retriever = build_knowledge_index(cfg, chunking="clause")
    router = make_router(retriever)
    for w in (0.3, 0.5, 0.7, 0.9):
        retriever.vector_weight = w
        summary = run_eval(retriever, router, queries, top_k, routed=True)
        rows.append({"ablation": "vector_weight", "chunking": "clause",
                     "routing": True, "vector_weight": w, **summary})
        print(f"vector_weight={w:.1f} Recall@5={summary['recall@5']:.3f} MRR={summary['mrr']:.3f}")

    out = ROOT / "results" / "ablation.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n结果已保存：{out}")


if __name__ == "__main__":
    main()
