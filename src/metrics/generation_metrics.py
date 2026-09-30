"""
生成质量指标

1. citation_accuracy：引用忠实度（对齐后 supported 比例）
2. LLM-as-judge：faithfulness / coverage / professionalism 三维 1-5 分
3. hallucination_rate：正文引用中不在检索结果内的比例（幻觉代理指标）
"""
from src.generation.llm_client import LLMClient, parse_json
from src.generation.prompts import JUDGE_PROMPT


def judge_scores(llm: LLMClient, text: str, regulations: str, facts: str) -> dict:
    prompt = JUDGE_PROMPT.format(text=text, regulations=regulations, facts=facts)
    raw = llm.chat(prompt)
    result = parse_json(raw)
    return {
        "faithfulness": float(result.get("faithfulness", 0)),
        "coverage": float(result.get("coverage", 0)),
        "professionalism": float(result.get("professionalism", 0)),
        "comment": result.get("comment", ""),
    }


def summarize_generation(records: list[dict]) -> dict:
    """按模式汇总生成评测结果"""
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[r["mode"]].append(r)

    summary = {}
    for mode, rows in groups.items():
        def avg(key):
            vals = [r[key] for r in rows if r.get(key) is not None]
            return sum(vals) / len(vals) if vals else None
        summary[mode] = {
            "n": len(rows),
            "score": avg("score"),
            "citation_accuracy": avg("citation_accuracy"),
            "n_citations": avg("n_citations"),
            "faithfulness": avg("faithfulness"),
            "coverage": avg("coverage"),
            "professionalism": avg("professionalism"),
        }
    return summary
