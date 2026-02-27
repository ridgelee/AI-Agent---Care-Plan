"""
BaseIntakeAdapter — 所有数据源 Adapter 的抽象基类。

每个新数据源只需：
1. 继承 BaseIntakeAdapter
2. 实现 parse() 和 transform()
3. 在 factory.py 的 _REGISTRY 注册一行

业务代码无需任何改动。
"""

import re
from abc import ABC, abstractmethod
from typing import Any

from ..exceptions import ValidationError
from .types import InternalOrder

# ── 共用校验正则（Adapter 可直接复用） ─────────────────────────────────────
NPI_RE = re.compile(r"^\d{10}$")
MRN_RE = re.compile(r"^\d{6}$")
ICD10_RE = re.compile(r"^[A-Za-z]\d{2}(\.\d{1,4})?$")


class BaseIntakeAdapter(ABC):
    """
    三步流水线：parse → transform → validate

    子类必须实现 parse() 和 transform()；
    validate() 提供通用 ICD-10 / NPI / MRN 校验，子类可 super() 后追加检查。
    """

    # 子类声明自己对应的 source 标识符（与 factory 注册键一致）
    source: str = ""

    def __init__(self, raw_body: bytes | str, content_type: str = ""):
        self._raw_body = raw_body
        self._content_type = content_type

    # ── 必须实现 ───────────────────────────────────────────────────────────

    @abstractmethod
    def parse(self) -> Any:
        """
        解析原始数据（bytes / str）→ 中间结构（通常是 dict 或 ElementTree）。
        应将解析结果赋值给 self._parsed 以便 transform() 使用。
        """

    @abstractmethod
    def transform(self) -> InternalOrder:
        """
        将 self._parsed 转换为 InternalOrder。
        必须把原始数据存入 InternalOrder.raw_payload。
        """

    # ── 提供默认实现，子类可 override ──────────────────────────────────────

    def validate(self, order: InternalOrder) -> None:
        """
        校验 InternalOrder 中的通用字段。
        抛出 ValidationError（与现有异常体系兼容）。
        """
        errors = []

        if not NPI_RE.match(order.provider.npi):
            errors.append({"field": "provider.npi", "message": "NPI must be exactly 10 digits."})

        if not MRN_RE.match(order.patient.mrn):
            errors.append({"field": "patient.mrn", "message": "MRN must be exactly 6 digits."})

        if order.medication.primary_diagnosis:
            if not ICD10_RE.match(order.medication.primary_diagnosis):
                errors.append({
                    "field": "medication.primary_diagnosis",
                    "message": "Primary diagnosis must be valid ICD-10 format (e.g. G70.00, E11.9).",
                })

        for i, code in enumerate(order.medication.additional_diagnoses):
            if code and not ICD10_RE.match(code):
                errors.append({
                    "field": f"medication.additional_diagnoses[{i}]",
                    "message": f"Invalid ICD-10 code: {code!r}.",
                })

        if errors:
            raise ValidationError(
                message="Request validation failed.",
                code="VALIDATION_ERROR",
                detail={"errors": errors},
            )

    # ── 对外统一入口 ───────────────────────────────────────────────────────

    def process(self) -> InternalOrder:
        """parse → transform → validate，返回校验通过的 InternalOrder。"""
        self.parse()
        order = self.transform()
        self.validate(order)
        return order
