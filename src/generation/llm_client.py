"""
大模型客户端（OpenAI 兼容接口）

- 真实模式：调用 DeepSeek / Qwen 等 OpenAI 兼容 API；
- mock 模式：离线模板响应，供冒烟测试与流水线联调（不消耗 API）。
"""
import json
import os
import re


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.2, mock: bool = False):
        self.model = model
        self.temperature = temperature
        self.mock = mock
        if not mock:
            from openai import OpenAI
            if not api_key:
                raise ValueError("真实模式需要设置环境变量 LLM_API_KEY")
            self._client = OpenAI(base_url=base_url, api_key=api_key)

    # ---------- 调用 ----------
    def chat(self, prompt: str, system: str | None = None) -> str:
        if self.mock:
            return self._mock_response(prompt)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages, temperature=self.temperature)
        return resp.choices[0].message.content

    # ---------- 离线模板响应 ----------
    def _mock_response(self, prompt: str) -> str:
        if "judge" in prompt[:200] or "评审专家" in prompt[:200]:
            return json.dumps({"faithfulness": 4, "coverage": 4,
                               "professionalism": 4, "comment": "mock judge"},
                              ensure_ascii=False)
        # 从提示词中提取第一条法规编号，生成带引用的模板评价
        # 注：法规标题可能含《》（如"【第215号令】《XX办法》"），故匹配至 "》（来源）" 边界
        m = re.search(r"\[1\] 《(.+)》 ?（", prompt)
        title = m.group(1) if m else "上市公司信息披露管理办法"
        if " 第" in title:
            # 提示词行内带条款号：拆出真实条款号
            title_part, clause_part = title.split(" 第", 1)
            clause = "第" + clause_part
        else:
            # 无条款号信息：clause 置 None（对齐时按法规名匹配），不编造条款
            title_part, clause = title, None
        citation = {"title": title_part, "clause": clause, "used_for": "mock 引用"}
        clause_txt = citation["clause"] or ""
        return json.dumps({
            "evaluation": f"（mock）依据《{citation['title']}》{clause_txt}，"
                          f"该公司相关自律表现总体合规。【依据：《{citation['title']}》{clause_txt}】",
            "strengths": ["mock 优势"], "weaknesses": ["mock 不足"],
            "score": 80, "citations": [citation],
        }, ensure_ascii=False)


def parse_json(text: str) -> dict:
    """稳健解析模型输出的 JSON"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)
