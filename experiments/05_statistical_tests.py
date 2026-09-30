"""
实验 05：统计显著性检验

读取 03 生成的 generation_records.csv，对 ours 与两个基线的
judge 分数做 Wilcoxon 配对检验（同一样本×维度配对）。
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ROOT
from src.metrics.stats import wilcoxon


def load_pairs(path: Path, metric: str, mode_a: str, mode_b: str):
    """按 (sample, dimension) 配对两组模式的指标值"""
    records = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["sample"], row["dimension"])
            records.setdefault(key, {})[row["mode"]] = float(row[metric]) if row[metric] else None
    a, b = [], []
    for key, modes in records.items():
        va, vb = modes.get(mode_a), modes.get(mode_b)
        if va is not None and vb is not None:
            a.append(va)
            b.append(vb)
    return a, b


def main():
    records_path = ROOT / "results" / "generation_records.csv"
    if not records_path.exists():
        print("请先运行 experiments/03_generation_evaluation.py")
        return

    for metric in ("faithfulness", "coverage", "professionalism"):
        for baseline in ("no_rag", "naive_rag"):
            a, b = load_pairs(records_path, metric, "ours", baseline)
            result = wilcoxon(a, b)
            if result["p_value"] is None:
                print(f"[{metric}] ours vs {baseline}: {result['note']}")
                continue
            sig = "***" if result["p_value"] < 0.001 else "**" if result["p_value"] < 0.01 else "*" if result["p_value"] < 0.05 else "n.s."
            print(f"[{metric}] ours vs {baseline:<9s} "
                  f"p={result['p_value']:.4f} {sig} "
                  f"effect_size={result['effect_size']:.3f} n={result['n']}")


if __name__ == "__main__":
    main()
