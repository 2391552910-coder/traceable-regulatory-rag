"""
文本切分策略（实验消融对照的核心变量）

本方法：clause 条款级切分——按法规"第X条"边界切分，保证每条检索单元是
完整法条，引用时可精确定位到条款号（证据溯源的前提）。
消融对照：window 固定长度滑窗切分——RAG 常用基线做法。
"""
import re
from dataclasses import dataclass, field

CLAUSE_PATTERN = re.compile(
    r"(第[一二三四五六七八九十百千零0-9]+条(?:之[一二三四五六七八九十0-9]+)?)"
)


@dataclass
class Chunk:
    """检索单元"""
    chunk_id: str          # 全局唯一 ID，如 DOC001-C03（评测集标注引用它）
    doc_id: str
    doc_title: str
    doc_type: str          # regulation / penalty / announcement
    source: str
    clause_no: str | None  # 条款号（条款级切分时可定位；滑窗时为 None）
    text: str
    dimension: str | None = None  # 维度路由标签 D1-D4
    meta: dict = field(default_factory=dict)


def split_by_clause(doc_id: str, doc_title: str, doc_type: str, source: str,
                    text: str, dimension: str | None = None) -> list[Chunk]:
    """
    条款级切分（本方法）：
    按"第X条"边界切分，条款号写入 chunk.clause_no，引用可追溯。
    条款前的总则/附则等非条款文本并入相邻块。
    """
    parts = CLAUSE_PATTERN.split(text)
    chunks: list[Chunk] = []
    buffer = ""

    def flush(clause_no: str | None, body: str):
        body = body.strip()
        if not body:
            return
        idx = len(chunks) + 1
        chunks.append(Chunk(
            chunk_id=f"{doc_id}-C{idx:03d}",
            doc_id=doc_id, doc_title=doc_title, doc_type=doc_type, source=source,
            clause_no=clause_no,
            text=(f"{clause_no}{body}" if clause_no else body)[:2000],
            dimension=dimension,
        ))

    i = 0
    while i < len(parts):
        part = parts[i]
        if CLAUSE_PATTERN.fullmatch(part):
            flush(None, buffer)  # 上一条款与之间的自由文本
            buffer = ""
            body = parts[i + 1] if i + 1 < len(parts) else ""
            flush(part, body)
            i += 2
        else:
            buffer += part
            i += 1
    flush(None, buffer)
    return chunks


def split_by_window(doc_id: str, doc_title: str, doc_type: str, source: str,
                    text: str, size: int = 512, overlap: int = 64,
                    dimension: str | None = None) -> list[Chunk]:
    """固定长度滑窗切分（消融对照）"""
    chunks: list[Chunk] = []
    step = max(size - overlap, 1)
    for start in range(0, len(text), step):
        piece = text[start:start + size].strip()
        if not piece:
            continue
        chunks.append(Chunk(
            chunk_id=f"{doc_id}-W{len(chunks) + 1:03d}",
            doc_id=doc_id, doc_title=doc_title, doc_type=doc_type, source=source,
            clause_no=None, text=piece, dimension=dimension,
        ))
    return chunks


def split_document(doc: dict, strategy: str = "clause", **kw) -> list[Chunk]:
    """统一入口：doc 为 knowledge_loader 读取的文档字典"""
    if strategy == "clause":
        return split_by_clause(doc["doc_id"], doc["title"], doc["doc_type"],
                               doc["source"], doc["text"], doc.get("dimension"))
    if strategy == "window":
        return split_by_window(doc["doc_id"], doc["title"], doc["doc_type"],
                               doc["source"], doc["text"],
                               size=kw.get("window_size", 512),
                               overlap=kw.get("window_overlap", 64),
                               dimension=doc.get("dimension"))
    raise ValueError(f"未知切分策略: {strategy}")
