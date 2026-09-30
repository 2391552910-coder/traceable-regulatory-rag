import re
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


def _normalize_title(t: str) -> str:
    """法规标题归一化：去令号/公告前缀、书名号、修订/试行/节选标记"""
    t = re.sub(r"【第[^】]*】", "", t)
    t = re.sub(r"（[^）]*(?:修订|试行|节选|年版?)[^）]*）", "", t)
    t = re.sub(r"\(\d{4}[^)]*\)", "", t)
    t = re.sub(r"关于修改[《〈＜].{0,30}决定》?的?", "", t)
    return re.sub(r"[《》〈＜\s]", "", t).strip()


def _title_match(a: str, b: str) -> bool:
    """法规标题宽松匹配（归一化后双向子串，容忍令号/修订标记差异）"""
    na, nb = _normalize_title(a), _normalize_title(b)
    if not na or not nb:
        return False
    return na in nb or nb in na


def citation_stats(aligned: list[dict]) -> dict:
    """引用忠实度统计"""
    total = len(aligned)
    supported = sum(1 for a in aligned if a["supported"])
    return {
        "n_citations": total,
        "n_supported": supported,
        "citation_accuracy": supported / total if total else None,
    }
