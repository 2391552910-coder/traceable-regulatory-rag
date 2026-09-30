"""
评价生成提示词——三组对照

- no_rag：无检索依据（基线1），模型仅凭自身知识生成评价；
- naive_rag：注入检索结果但无引用约束（基线2）；
- ours：注入检索结果 + 强制引用标注 + 禁引用未提供条文（本方法）。
"""

NO_RAG_PROMPT = """你是证券监管领域资深评价专家。请对上市公司{stock_name}（{stock_code}）{year}年度报告的
「{dimension_name}」维度出具自律评价意见。

【抽取到的事实材料】
{facts}

【要求】指出该维度自律表现的优势与不足（各至少 1 条），给出 0-100 的维度得分。
输出 JSON：{{"evaluation": "评价正文", "strengths": [], "weaknesses": [], "score": 0}}
"""

NAIVE_RAG_PROMPT = """你是证券监管领域资深评价专家。请基于事实材料与检索到的法规内容，对上市公司
{stock_name}（{stock_code}）{year}年度报告的「{dimension_name}」维度出具自律评价意见。

【抽取到的事实材料】
{facts}

【检索到的法规内容】
{regulations}

【要求】指出该维度自律表现的优势与不足（各至少 1 条），给出 0-100 的维度得分。
输出 JSON：{{"evaluation": "评价正文", "strengths": [], "weaknesses": [], "score": 0}}
"""

OURS_PROMPT = """你是证券监管领域资深评价专家。请基于给定的事实材料与监管法规依据，对上市公司
{stock_name}（{stock_code}）{year}年度报告的「{dimension_name}」维度出具自律评价意见。

【抽取到的事实材料】
{facts}

【监管法规依据（编号检索结果）】
{regulations}

【硬性约束】
1. 引用法规时必须标注来源，格式：【依据：《法规名》第X条】；
2. 严禁引用上述编号结果之外的法规条文；
3. 指出该维度自律表现的优势与不足（各至少 1 条）；
4. 给出 0-100 的维度得分并说明评分理由。

输出 JSON：{{"evaluation": "评价正文", "strengths": [], "weaknesses": [],
"score": 0, "citations": [{{"title": "法规名", "clause": "第X条", "used_for": "支持的论点"}}]}}
"""

PROMPT_BY_MODE = {
    "no_rag": NO_RAG_PROMPT,
    "naive_rag": NAIVE_RAG_PROMPT,
    "ours": OURS_PROMPT,
}

# LLM-as-judge 评分提示词（生成质量自动评测）
JUDGE_PROMPT = """你是论文评审专家，请对下面一段「上市公司自律评价」文本按 1-5 分打分：
- faithfulness（依据忠实度）：评价结论是否都有法规/事实依据支撑，无凭空结论；
- coverage（事实覆盖度）：是否覆盖给定事实材料的关键信息；
- professionalism（专业性与规范性）：表述是否专业审慎，引用格式是否规范。

【评价文本】
{text}

【检索到的法规（供核对引用是否属实）】
{regulations}

【事实材料】
{facts}

输出 JSON：{{"faithfulness": 1-5, "coverage": 1-5, "professionalism": 1-5, "comment": "简要评语"}}
"""
