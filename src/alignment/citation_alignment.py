"""
证据对齐（本方法贡献）：模型引用 ↔ 检索命中 比对

- 对齐：模型自报/正文扫描出的每条引用，与检索命中的条款清单比对，
  判断该引用是否有检索依据支撑；
- 输出引用忠实度指标所需的对齐结果明细。
"""
from src.data.clause_splitter import Chunk


def align_citations(citations: list[dict],
                    retrieved: list[tuple[Chunk, float]]) -> list[dict]:
    """
    对齐每条引用：
    - supported: 检索结果中存在同法规同条款（条款号缺失时按法规名匹配）
    - unsupported: 引用了检索结果之外的法规（幻觉信号）
    """
    retrieved_refs = [(c.doc_title, c.clause_no) for c, _ in retrieved]
    aligned = []
    for cit in citations:
        title, clause = cit.get("title", ""), cit.get("clause")
        supported = any(
            _title_match(title, r_title) and (clause is None or clause == r_clause)
            for r_title, r_clause in retrieved_refs
        )
        aligned.append({**cit, "supported": supported})
    return aligned


def _title_match(a: str, b: str) -> bool:
    """法规标题宽松匹配（容忍"（节选）""（2021修订）"等后缀差异）"""
    a = a.replace("（节选）", "").strip()
    b = b.replace("（节选）", "").strip()
    return a in b or b in a


def citation_stats(aligned: list[dict]) -> dict:
    """引用忠实度统计"""
    total = len(aligned)
    supported = sum(1 for a in aligned if a["supported"])
    return {
        "n_citations": total,
        "n_supported": supported,
        "citation_accuracy": supported / total if total else None,
    }
