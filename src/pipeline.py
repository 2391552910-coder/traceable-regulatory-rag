"""
端到端流水线：知识库构建 → 检索 → 评价生成 → 证据对齐 → 评测汇总
"""
from src.config import load_config
from src.data.clause_splitter import split_document
from src.data.knowledge_loader import load_documents
from src.generation.llm_client import LLMClient
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.router import DimensionRoutedRetriever


def build_knowledge_index(cfg: dict, chunking: str | None = None):
    """加载语料并按指定策略切分，构建混合检索器"""
    kb_cfg = cfg["knowledge_base"]
    strategy = chunking or kb_cfg["chunking"]
    docs = load_documents(kb_cfg["path"])
    chunks = []
    for doc in docs:
        chunks.extend(split_document(doc, strategy=strategy,
                                     window_size=kb_cfg["window_size"],
                                     window_overlap=kb_cfg["window_overlap"]))
    ret_cfg = cfg["retrieval"]
    retriever = HybridRetriever(
        chunks, vector_weight=ret_cfg["vector_weight"],
        backend=ret_cfg["embedding_backend"],
        model_name=ret_cfg["embedding_model"],
        device=ret_cfg["embedding_device"],
    )
    return chunks, retriever


def make_llm(cfg: dict, mock: bool | None = None) -> LLMClient:
    llm_cfg = cfg["llm"]
    return LLMClient(base_url=llm_cfg["base_url"], api_key=llm_cfg["api_key"],
                     model=llm_cfg["model"], temperature=llm_cfg["temperature"],
                     mock=mock if mock is not None else llm_cfg["mock"])


def make_router(retriever: HybridRetriever) -> DimensionRoutedRetriever:
    return DimensionRoutedRetriever(retriever)
