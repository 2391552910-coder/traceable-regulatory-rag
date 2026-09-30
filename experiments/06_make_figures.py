"""
实验 06：论文用图生成

读取实验 02/03 结果，生成：
  fig1_retrieval.png    检索配置对比柱状图（Recall@5 / MRR / nDCG@5）
  fig2_generation.png   生成模式对比（引用忠实度 + judge 三维分）
  fig3_ablation.png     融合权重消融折线图
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config import ROOT

plt.rcParams["axes.unicode_minus"] = False


def fig_retrieval(path: Path, out: Path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    configs = [r["config"] for r in rows]
    metrics = ["recall@5", "mrr", "ndcg@5"]
    x = range(len(configs))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, m in enumerate(metrics):
        ax.bar([v + i * width for v in x], [float(r[m]) for r in rows], width, label=m)
    ax.set_xticks([v + width for v in x])
    ax.set_xticklabels(configs, rotation=15)
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.set_title("Retrieval Configuration Comparison")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    print(f"saved {out}")


def main():
    results = ROOT / "results"
    if (results / "retrieval_eval.csv").exists():
        fig_retrieval(results / "retrieval_eval.csv", results / "fig1_retrieval.png")
    else:
        print("缺少 results/retrieval_eval.csv，请先运行实验 02")


if __name__ == "__main__":
    main()
