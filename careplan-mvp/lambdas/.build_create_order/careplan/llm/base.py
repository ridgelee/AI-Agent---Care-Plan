"""
BaseLLMService — 所有 LLM 实现的抽象基类。

每个新 LLM 只需：
1. 继承 BaseLLMService
2. 实现 complete()
3. 在 factory.py 的 _REGISTRY 注册一行

tasks.py 完全不知道背后用哪家 LLM。
"""

from abc import ABC, abstractmethod

from .types import LLMResponse


class BaseLLMService(ABC):

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """
        调用 LLM，返回标准 LLMResponse。

        Args:
            system_prompt: 系统级角色设定（"You are an expert pharmacist..."）
            user_prompt:   用户级输入（Care Plan 所需的患者信息 prompt）

        Returns:
            LLMResponse(content=生成文本, model=模型名)

        Raises:
            Exception: API 调用失败时抛出，由 tasks.py 的重试机制处理
        """
