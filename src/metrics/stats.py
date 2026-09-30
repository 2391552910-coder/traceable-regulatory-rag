"""
统计检验

1. Wilcoxon 符号秩检验：两组实验（如 ours vs naive_rag）在同一批样本上的
   配对比较（样本量小、不满足正态假设时的非参数检验）；
2. Cohen's Kappa：双人标注一致性（检索评测集标注可靠性，Kappa>0.6 可接受）。
"""
import numpy as np
from scipy import stats as scipy_stats


def wilcoxon(a: list[float], b: list[float]) -> dict:
    """配对 Wilcoxon 符号秩检验，返回统计量、p 值与效应量"""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) != len(b):
        raise ValueError("两组样本长度必须一致（配对检验）")
    if len(a) < 2 or np.all(a == b):
        return {"statistic": None, "p_value": None, "n": len(a),
                "note": "样本不足或两组完全一致"}
    stat, p = scipy_stats.wilcoxon(a, b)
    # 效应量 r = Z / sqrt(N)
    n = len(a)
    z = scipy_stats.norm.ppf(1 - p / 2)
    effect = z / np.sqrt(n)
    return {"statistic": float(stat), "p_value": float(p),
            "effect_size": float(effect), "n": n}


def cohens_kappa(annotator1: list, annotator2: list) -> float:
    """双人标注一致性"""
    from sklearn.metrics import cohen_kappa_score
    return float(cohen_kappa_score(annotator1, annotator2))
