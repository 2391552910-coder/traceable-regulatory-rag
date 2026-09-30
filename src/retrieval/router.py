"""
维度路由检索器（本方法贡献）

针对"上市公司主体自律评价"场景，检索不是通用问答：
1. 按评价维度 D1-D4 构造领域化查询模板（而非直接用原始问题）；
2. 优先在标注了对应维度的法规子库中检索，子库为空时回退全库；
3. 输出供提示词注入的编号法规清单。
"""
from src.data.clause_splitter import Chunk
from src.retrieval.hybrid import HybridRetriever

DIMENSIONS = {
    "D1": "信息披露质量",
    "D2": "董事会治理有效性",
    "D3": "内部控制与合规性",
    "D4": "第三方声誉",
}

# 维度路由查询模板：将评价维度扩展为带监管语义的检索语句
QUERY_TEMPLATES = {
    "D1": "信息披露 及时性 完整性 披露义务 违规 {keywords}",
    "D2": "董事会 独立董事 治理 履职 专门委员会 {keywords}",
    "D3": "内部控制 关联交易 处罚 整改 合规 {keywords}",
    "D4": "审计意见 社会责任 ESG 声誉 舆情 {keywords}",
}


class DimensionRoutedRetriever:
    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever

    def route_pool(self, dimension: str) -> list[Chunk] | None:
        """返回该维度的优先子库；无标注数据时返回 None（全库）"""
        pool = [c for c in self.retriever.chunks
                if c.dimension == dimension or c.dimension is None]
        return pool if pool else None

    def build_query(self, dimension: str, keywords: str) -> str:
        template = QUERY_TEMPLATES.get(dimension, "{keywords}")
        return template.format(keywords=keywords)

    def search(self, dimension: str, keywords: str, top_k: int = 5,
               routed: bool = True) -> list[tuple[Chunk, float]]:
        query = self.build_query(dimension, keywords)
        pool = self.route_pool(dimension) if routed else None
        return self.retriever.search(query, top_k=top_k, pool=pool)

    @staticmethod
    def format_for_prompt(hits: list[tuple[Chunk, float]]) -> str:
        """检索结果格式化为提示词注入的编号法规清单"""
        lines = []
        for i, (chunk, score) in enumerate(hits, 1):
            ref = chunk.doc_title + (f" {chunk.clause_no}" if chunk.clause_no else "")
            lines.append(f"[{i}] 《{ref}》（{chunk.source}）\n{chunk.text[:400]}")
        return "\n\n".join(lines) if lines else "无相关法规依据。"
