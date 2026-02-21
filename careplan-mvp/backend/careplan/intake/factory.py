"""
工厂函数：根据来源字符串返回对应 Adapter 类。

新增数据源只需：
  1. 在 adapters.py 新建 Adapter 类
  2. 在此处 _REGISTRY 加一行
  不需要修改任何业务代码。
"""

from ..exceptions import ValidationError
from .base import BaseIntakeAdapter

# ── 注册表 ──────────────────────────────────────────────────────────────────
# key: source 字符串（通常来自 HTTP Header X-Order-Source 或 URL 参数）
# value: Adapter 类（未实例化）
def _build_registry() -> dict[str, type[BaseIntakeAdapter]]:
    # 延迟导入，避免循环依赖
    from .adapters import ClinicBAdapter, HospitalAAdapter, RiversideAdapter, SummitAdapter

    return {
        "clinic_b":   ClinicBAdapter,
        "hospital_a": HospitalAAdapter,
        "riverside":  RiversideAdapter,
        "summit":     SummitAdapter,      # ← 新增这一行
    }


def get_adapter(source: str, raw_body: bytes | str, content_type: str = "") -> BaseIntakeAdapter:
    """
    根据 source 返回已实例化的 Adapter。

    Args:
        source:       数据来源标识，例如 "clinic_b"、"hospital_a"
        raw_body:     原始请求体（bytes 或 str）
        content_type: HTTP Content-Type，Adapter 内部可按需使用

    Raises:
        ValidationError: 未知的 source
    """
    registry = _build_registry()
    adapter_cls = registry.get(source)

    if adapter_cls is None:
        raise ValidationError(
            message=f"Unknown order source: {source!r}.",
            code="UNKNOWN_SOURCE",
            detail={"known_sources": list(registry.keys())},
        )

    return adapter_cls(raw_body=raw_body, content_type=content_type)
