"""
InternalOrder dataclass — 业务逻辑唯一认识的标准格式。

所有 Adapter 的 transform() 必须返回这个结构。
业务层（services.py）只消费这个结构，永远不碰外部原始数据。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatientData:
    mrn: str
    first_name: str
    last_name: str
    dob: str  # ISO 8601: "YYYY-MM-DD"


@dataclass
class ProviderData:
    npi: str
    name: str


@dataclass
class MedicationData:
    name: str
    primary_diagnosis: str                    # ICD-10
    additional_diagnoses: list[str] = field(default_factory=list)
    medication_history: list[Any] = field(default_factory=list)


@dataclass
class InternalOrder:
    """
    标准内部订单格式。

    raw_payload  保存原始数据（dict / str），用于排查问题，不参与业务逻辑。
    source       标识数据来源（"clinic_b" / "hospital_a" / ...）。
    confirm      用户是否已确认（WarningError 二次提交时为 True）。
    """

    patient: PatientData
    provider: ProviderData
    medication: MedicationData
    patient_records: str = ""
    confirm: bool = False
    source: str = ""
    raw_payload: Any = field(default=None, repr=False)
