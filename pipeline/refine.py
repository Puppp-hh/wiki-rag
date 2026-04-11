"""答案优化层：让 LLM 重写初始回答，去噪音、补结构、修错误。"""
from __future__ import annotations

from core.llm import LLMError, ask
from core.utils import log

_REFINE_PROMPT = """你是一个专业的技术知识整理专家。

请对以下回答进行优化：

要求：

1. 严格围绕用户问题
   - 删除所有无关内容
   - 不扩展问题之外内容

2. 提高准确性
   - 修正错误内容
   - 删除模型编造的信息

3. 结构优化
   输出结构：
   - 简洁定义
   - 核心原理
   - 示例（如适用）
   - 一句话总结

4. 删除噪音
   - 删除路径（如 /xxx/xxx）
   - 删除 --- 分隔符
   - 删除重复内容
   - 删除无意义文本

5. 表达要求
   - 简洁清晰
   - 技术风格
   - 不要解释你做了什么

6. 如果信息不足：
   - 直接说明"根据已有内容无法完整回答"
   - 不要编造

输入：
问题：{question}

原始回答：
{answer}

输出：
优化后的最终答案"""


def refine_answer(question: str, answer: str) -> str:
    """对初始回答做一次 LLM 重写。失败时由调用方决定回退策略。"""
    log.info("二次优化回答 (refine)...")
    prompt = _REFINE_PROMPT.format(question=question, answer=answer)
    try:
        return ask(prompt)
    except LLMError:
        # 让上层决定是否回退到原始回答
        raise
