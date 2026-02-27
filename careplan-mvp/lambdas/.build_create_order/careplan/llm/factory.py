"""
工厂函数：根据 settings.LLM_PROVIDER 返回对应的 LLMService 实例。

新增 LLM 供应商只需：
  1. 在 services.py 新建 XxxService(BaseLLMService) 类
  2. 在此处 _REGISTRY 加一行
  不需要修改 tasks.py 或任何业务代码。
"""

from django.conf import settings

from .base import BaseLLMService

_REGISTRY: dict[str, type[BaseLLMService]] = {}


def _build_registry() -> dict[str, type[BaseLLMService]]:
    # 延迟导入，避免在 Django 启动前触发 SDK import
    from .services import ClaudeService, OpenAIService

    return {
        "anthropic": ClaudeService,
        "openai":    OpenAIService,
    }


def get_llm_service() -> BaseLLMService:
    """
    从 settings.LLM_PROVIDER 读取供应商，返回对应的 LLMService 实例。

    settings.LLM_PROVIDER 由环境变量 LLM_PROVIDER 控制（默认 "anthropic"）。
    换 LLM 只需改环境变量，代码零改动。

    Raises:
        ValueError: LLM_PROVIDER 未知
    """
    provider = getattr(settings, "LLM_PROVIDER", "anthropic")
    registry = _build_registry()
    service_cls = registry.get(provider)

    if service_cls is None:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider!r}. "
            f"Known providers: {list(registry.keys())}"
        )

    return service_cls()
