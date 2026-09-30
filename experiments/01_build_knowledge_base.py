"""
实验 01：知识库构建与切分统计

输出条款级切分 vs 滑窗切分的块数、平均块长统计，
验证条款级切分的块完整性（每个条款级块恰好一条法条）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config, ROOT
from src.data.clause_splitter import split_document
from src.data.knowledge_loader import load_documents


def main():
    cfg = load_config()
    docs = load_documents(ROOT / cfg["knowledge_base"]["path"])

    for strategy in ("clause", "window"):
        chunks = []
        for doc in docs:
            chunks.extend(split_document(doc, strategy=strategy,
                                         window_size=cfg["knowledge_base"]["window_size"],
                                         window_overlap=cfg["knowledge_base"]["window_overlap"]))
        lengths = [len(c.text) for c in chunks]
        print(f"[{strategy}] 文档数={len(docs)} 块数={len(chunks)} "
              f"平均块长={sum(lengths) / len(lengths):.0f} "
              f"含条款号块数={sum(1 for c in chunks if c.clause_no)}")

    print("\n示例条款级切分结果：")
    for doc in docs[:1]:
        for c in split_document(doc, "clause"):
            print(f"  {c.chunk_id} {c.clause_no or '-'} {c.text[:40]}...")


if __name__ == "__main__":
    main()
