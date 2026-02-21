"""
LLM 层的标准响应结构。

所有 LLMService 实现的 complete() 都返回这个对象。
业务层（tasks.py）只认识这个格式，不知道背后用的是哪家 LLM。
"""

from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str       # 生成的文本内容
    model: str         # 实际使用的模型名，写入 CarePlan.llm_model
