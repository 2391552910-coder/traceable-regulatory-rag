"""
评价生成器：按模式组装提示词 → 调用大模型 → 解析结果 → 抽取引用

引用抽取双通道：
1. 模型自报 JSON citations 字段（ours 模式）；
2. 评价正文正则扫描 【依据：《X》第Y条】（三模式通用，用于交叉核验）。
"""
import re

from src.generation.llm_client import LLMClient, parse_json
from src.generation.prompts import PROMPT_BY_MODE

CITATION_PATTERN = re.compile(r"【依据：\s*《(.+?)》\s*(第[一二三四五六七八九十百千零0-9]+条(?:之[一二三四五六七八九十0-9]+)?)?】")


class Evaluator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def evaluate(self, mode: str, stock_name: str, stock_code: str, year: int,
                 dimension_name: str, facts: str, regulations: str = "") -> dict:
        template = PROMPT_BY_MODE[mode]
        prompt = template.format(
            stock_name=stock_name, stock_code=stock_code, year=year,
            dimension_name=dimension_name, facts=facts, regulations=regulations,
        )
        raw = self.llm.chat(prompt)
        result = parse_json(raw)
        result["raw"] = raw
        result["mode"] = mode
        result["inline_citations"] = self.extract_inline_citations(
            result.get("evaluation", ""))
        return result

    @staticmethod
    def extract_inline_citations(text: str) -> list[dict]:
        """从评价正文扫描 【依据：《X》第Y条】 引用"""
        return [{"title": m.group(1), "clause": m.group(2)}
                for m in CITATION_PATTERN.finditer(text)]
