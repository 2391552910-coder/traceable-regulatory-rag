# 面向监管评价的可追溯检索增强生成（Traceable Regulatory RAG）

小论文《面向上市公司主体自律评价的可追溯检索增强生成方法》配套代码与实验。

针对大模型生成监管评价时的**幻觉风险与法规依据缺失**问题，本仓库实现"检索—引用—溯源"闭环的
RAG 框架，并提供检索评测、生成评测、消融实验与统计检验的完整可复现流水线。

## 方法贡献

1. **条款级切分**：监管法规按"第X条"边界切分（对照：512 字滑窗），每个检索单元为完整法条，
   引用可精确定位到条款号——证据溯源的前提；
2. **维度路由混合检索**：按主体自律四维度（信息披露质量 / 董事会治理有效性 / 内部控制与合规性 /
   第三方声誉）构造领域化查询模板并在维度子库中检索，BM25 + BGE-M3 双路归一化加权融合；
3. **证据对齐与引用忠实度评测**：模型自报引用 ↔ 检索命中比对，量化引用忠实度与幻觉率，
   配合双人标注（Cohen's Kappa）保证评测可靠性。

## 目录结构

```
src/
├── data/          条款级切分（本方法）+ 滑窗切分（消融）、知识库加载、评测集加载
├── retrieval/     BM25 / BGE-M3 稠密 / 双路融合 / 维度路由检索器
├── generation/    三版对照提示词（no_rag / naive_rag / ours）、LLM 客户端、引用抽取
├── alignment/     证据对齐：引用 ↔ 检索命中比对，引用忠实度统计
├── metrics/       Recall@k/MRR/nDCG、LLM-judge、Wilcoxon、Cohen's Kappa
└── pipeline.py    端到端流水线
experiments/       01 知识库构建统计  02 检索评测  03 生成评测  04 消融  05 显著性检验  06 出图
data/              示例法规语料（4 篇演示条目）+ 检索评测集 + 公司事实样本
docs/              实验设计与流程.md（论文实验部分底稿）、标注规范.md
tests/             冒烟测试（离线可跑）
```

## 快速开始

```bash
pip install -r requirements.txt

# 1. 离线冒烟测试（不下载模型、不调 API）
python tests/test_smoke.py

# 2. 检索评测（TF-IDF 后端免模型下载；正式实验用默认 BGE-M3）
python experiments/02_retrieval_evaluation.py --backend tfidf

# 3. 生成评测（离线 mock 模式联调）
python experiments/03_generation_evaluation.py --mock --backend tfidf

# 4. 消融 / 5. 显著性检验 / 6. 出图
python experiments/04_ablation_study.py --backend tfidf
python experiments/05_statistical_tests.py
python experiments/06_make_figures.py
```

正式实验：

```bash
export LLM_API_KEY=sk-xxx        # DeepSeek API Key
# configs/default.yaml 中 mock: false，embedding_backend: bge
python experiments/03_generation_evaluation.py --repeats 3
```

## 实验总览

| 实验 | 脚本 | 研究问题 | 输出 |
| --- | --- | --- | --- |
| 检索对比 | 02 | RQ1 | `results/retrieval_eval.csv`（BM25 / Dense / Hybrid / +Routing 四配置） |
| 生成对比 | 03 | RQ2/RQ4 | `results/generation_records.csv`（引用忠实度 + judge 三维分） |
| 消融 | 04 | RQ3 | `results/ablation.csv`（切分×路由×融合权重） |
| 显著性 | 05 | RQ2 | Wilcoxon p 值 + 效应量 |
| 出图 | 06 | — | `results/fig*.png` |

## 说明

- `data/knowledge_base/` 内 4 篇法规为**演示条目**（真实条文节选），正式实验请替换为
  ≥200 篇完整语料（格式见文件头注释）；
- 引用格式约定：【依据：《法规名》第X条】，由 `generation/evaluator.py` 正则抽取；
- 与"基于大模型的上市公司主体自律评价系统"仓库配套：系统产出评价与证据，本仓库负责方法与实验验证。
