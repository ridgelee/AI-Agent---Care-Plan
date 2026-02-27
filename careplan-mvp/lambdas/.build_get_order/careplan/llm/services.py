"""
具体 LLM 实现。

新增 LLM 供应商：在此文件添加一个类，然后在 factory.py 注册即可。

已注册供应商：
  anthropic — ClaudeService   (claude-sonnet-4-20250514)
  openai    — OpenAIService   (gpt-4o)
"""

import os

from .base import BaseLLMService
from .types import LLMResponse


# ── ClaudeService ──────────────────────────────────────────────────────────
#
# 使用 Anthropic SDK。
# 环境变量：ANTHROPIC_API_KEY
# 模型：claude-sonnet-4-20250514（可通过 ANTHROPIC_MODEL 覆盖）

class ClaudeService(BaseLLMService):

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")

        model = os.getenv("ANTHROPIC_MODEL", self.DEFAULT_MODEL)
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return LLMResponse(
            content=response.content[0].text,
            model=model,
        )


# ── OpenAIService ──────────────────────────────────────────────────────────
#
# 使用 OpenAI SDK。
# 环境变量：OPENAI_API_KEY
# 模型：gpt-4o（可通过 OPENAI_MODEL 覆盖）

class OpenAIService(BaseLLMService):

    DEFAULT_MODEL = "gpt-4o"

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        import openai

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")

        model = os.getenv("OPENAI_MODEL", self.DEFAULT_MODEL)
        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
        )
