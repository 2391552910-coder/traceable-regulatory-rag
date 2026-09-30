"""
检索质量指标：Recall@k / MRR / nDCG@k
"""
import math


def recall_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = len(set(ranked_ids[:k]) & relevant)
    return hits / len(relevant)


def reciprocal_rank(ranked_ids: list[str], relevant: set[str]) -> float:
    for i, cid in enumerate(ranked_ids):
        if cid in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    """二元相关性的 nDCG@k"""
    dcg = sum(1.0 / math.log2(i + 2) for i, cid in enumerate(ranked_ids[:k])
              if cid in relevant)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0.0


def aggregate(rows: list[dict]) -> dict:
    """对多条查询的指标取均值"""
    if not rows:
        return {}
    keys = [k for k in rows[0] if isinstance(rows[0][k], (int, float))]
    return {k: sum(r[k] for r in rows) / len(rows) for k in keys}
