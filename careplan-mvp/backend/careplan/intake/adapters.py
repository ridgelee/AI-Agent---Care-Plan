"""
具体 Adapter 实现。

新增数据源：在此文件添加一个类，然后在 factory.py 注册即可。

已注册数据源：
  clinic_b    — ClinicBAdapter      (JSON, pt/dx/rx 命名风格)
  hospital_a  — HospitalAAdapter    (XML, PascalCase 命名风格)
  riverside   — RiversideAdapter    (JSON, subject/ordering_physician 命名风格)
  summit      — SummitAdapter       (JSON, 完全平铺 + SCREAMING_SNAKE_CASE)
"""

import json
import xml.etree.ElementTree as ET
from typing import Any

from .base import BaseIntakeAdapter
from .types import InternalOrder, MedicationData, PatientData, ProviderData


# ── ClinicBAdapter ─────────────────────────────────────────────────────────
#
# 外部格式示例（JSON）:
# {
#   "pt":       { "mrn": "123456", "fname": "John", "lname": "Doe", "dob": "1980-01-15" },
#   "provider": { "npi_num": "1234567890", "name": "Dr. Smith" },
#   "dx":       { "primary": "G70.00", "secondary": ["E11.9"] },
#   "rx":       { "med_name": "Pyridostigmine" },
#   "med_hx":   ["Neostigmine 2020-2022"],
#   "clinical_notes": "Patient presents with ptosis...",
#   "confirm":  false
# }

class ClinicBAdapter(BaseIntakeAdapter):
    source = "clinic_b"

    def parse(self) -> Any:
        raw = json.loads(self._raw_body) if isinstance(self._raw_body, (bytes, str)) else self._raw_body
        self._parsed = raw
        return raw

    def transform(self) -> InternalOrder:
        raw = self._parsed
        pt       = raw.get("pt") or {}
        provider = raw.get("provider") or {}
        dx       = raw.get("dx") or {}
        rx       = raw.get("rx") or {}

        secondary = dx.get("secondary") or []
        if isinstance(secondary, str):
            secondary = [secondary] if secondary else []

        return InternalOrder(
            source=self.source,
            raw_payload=raw,                          # 保留原始数据
            confirm=bool(raw.get("confirm", False)),
            patient=PatientData(
                mrn=str(pt.get("mrn") or "").strip(),
                first_name=(pt.get("fname") or pt.get("first_name") or "").strip() or "Unknown",
                last_name=(pt.get("lname") or pt.get("last_name") or "").strip() or "Unknown",
                dob=(pt.get("dob") or "").strip(),
            ),
            provider=ProviderData(
                npi=str(provider.get("npi_num") or provider.get("npi") or "").strip(),
                name=(provider.get("name") or "").strip() or "Unknown",
            ),
            medication=MedicationData(
                name=(rx.get("med_name") or rx.get("name") or "").strip(),
                primary_diagnosis=(dx.get("primary") or "").strip(),
                additional_diagnoses=[c.strip() for c in secondary if (c or "").strip()],
                medication_history=list(raw.get("med_hx") or raw.get("medication_history") or []),
            ),
            patient_records=(raw.get("clinical_notes") or raw.get("patient_records") or "").strip(),
        )


# ── HospitalAAdapter ───────────────────────────────────────────────────────
#
# 外部格式示例（XML）:
# <Order>
#   <Patient>
#     <PatientMRN>123456</PatientMRN>
#     <PatientFirstName>Jane</PatientFirstName>
#     <PatientLastName>Smith</PatientLastName>
#     <DateOfBirth>1975-06-20</DateOfBirth>
#   </Patient>
#   <Physician NPI="0987654321" Name="Dr. Lee" />
#   <Diagnosis Primary="M05.79">
#     <Secondary>M79.3</Secondary>
#   </Diagnosis>
#   <Medication Name="Methotrexate" />
#   <MedHistory>
#     <Item>Hydroxychloroquine 2019-2021</Item>
#   </MedHistory>
#   <ClinicalNotes>Joint pain bilateral...</ClinicalNotes>
# </Order>

class HospitalAAdapter(BaseIntakeAdapter):
    source = "hospital_a"

    def parse(self) -> Any:
        body = self._raw_body if isinstance(self._raw_body, str) else self._raw_body.decode("utf-8")
        self._parsed = ET.fromstring(body)
        self._raw_str = body           # 保留原始 XML 字符串
        return self._parsed

    def _text(self, tag: str, default: str = "") -> str:
        el = self._parsed.find(tag)
        return (el.text or "").strip() if el is not None else default

    def transform(self) -> InternalOrder:
        root = self._parsed

        physician = root.find("Physician")
        diagnosis = root.find("Diagnosis")
        medication = root.find("Medication")

        secondary = [
            (el.text or "").strip()
            for el in (diagnosis.findall("Secondary") if diagnosis is not None else [])
            if (el.text or "").strip()
        ]
        med_history = [
            (el.text or "").strip()
            for el in root.findall("MedHistory/Item")
            if (el.text or "").strip()
        ]

        return InternalOrder(
            source=self.source,
            raw_payload=self._raw_str,                # 保留原始 XML
            confirm=False,
            patient=PatientData(
                mrn=self._text("Patient/PatientMRN"),
                first_name=self._text("Patient/PatientFirstName") or "Unknown",
                last_name=self._text("Patient/PatientLastName") or "Unknown",
                dob=self._text("Patient/DateOfBirth"),
            ),
            provider=ProviderData(
                npi=(physician.get("NPI") or "").strip() if physician is not None else "",
                name=(physician.get("Name") or "").strip() if physician is not None else "Unknown",
            ),
            medication=MedicationData(
                name=(medication.get("Name") or "").strip() if medication is not None else "",
                primary_diagnosis=(diagnosis.get("Primary") or "").strip() if diagnosis is not None else "",
                additional_diagnoses=secondary,
                medication_history=med_history,
            ),
            patient_records=self._text("ClinicalNotes"),
        )


# ── RiversideAdapter ───────────────────────────────────────────────────────
#
# Riverside Medical Center 的 JSON 格式，命名风格完全不同：
#
# {
#   "referral": {
#     "ref_id": "REF-2024-0891",
#     "submitted_by": "intake-system@riverside.org"
#   },
#   "subject": {
#     "id_number":   "789012",
#     "given_name":  "Carlos",
#     "family_name": "Mendez",
#     "birth_date":  "19720408"          ← YYYYMMDD，无连字符
#   },
#   "ordering_physician": {
#     "license_id":  "3141592653",
#     "full_name":   "Dr. Priya Nair"
#   },
#   "treatment": {
#     "drug":           "Rituximab",
#     "icd_primary":    "C83.39",
#     "icd_secondary":  ["Z79.899"],
#     "prior_drugs":    [{"drug": "CHOP", "year": "2022"}]   ← 对象数组，不是字符串
#   },
#   "chart_summary": "Patient presents with DLBCL stage III...",
#   "force_submit":  false               ← 对应 confirm
# }
#
# 与现有格式的主要差异：
#   1. birth_date 格式是 "YYYYMMDD" → 需要转成 "YYYY-MM-DD"
#   2. prior_drugs 是对象数组 → 保留原对象，不强行变成字符串
#   3. 二次确认字段叫 force_submit，不叫 confirm
#   4. NPI 字段叫 license_id

class RiversideAdapter(BaseIntakeAdapter):
    source = "riverside"

    def parse(self) -> Any:
        raw = json.loads(self._raw_body) if isinstance(self._raw_body, (bytes, str)) else self._raw_body
        self._parsed = raw
        return raw

    @staticmethod
    def _normalize_dob(raw_dob: str) -> str:
        """
        Riverside 的生日格式是 "YYYYMMDD"（无连字符）。
        统一转成 ISO 8601 "YYYY-MM-DD"。
        其他格式原样返回（容错）。
        """
        dob = (raw_dob or "").strip()
        if len(dob) == 8 and dob.isdigit():
            return f"{dob[:4]}-{dob[4:6]}-{dob[6:]}"
        return dob  # 已经是正确格式，或无法识别时原样返回

    def transform(self) -> InternalOrder:
        raw       = self._parsed
        subject   = raw.get("subject") or {}
        physician = raw.get("ordering_physician") or {}
        treatment = raw.get("treatment") or {}

        # icd_secondary 可能是字符串或列表，统一处理
        icd_secondary = treatment.get("icd_secondary") or []
        if isinstance(icd_secondary, str):
            icd_secondary = [icd_secondary] if icd_secondary.strip() else []

        # prior_drugs 是对象数组 [{"drug": "CHOP", "year": "2022"}]
        # 保留原始结构，业务层可自行处理
        prior_drugs = treatment.get("prior_drugs") or []

        return InternalOrder(
            source=self.source,
            raw_payload=raw,                          # 保留完整原始数据
            confirm=bool(raw.get("force_submit", False)),   # Riverside 叫 force_submit
            patient=PatientData(
                mrn=str(subject.get("id_number") or "").strip(),
                first_name=(subject.get("given_name") or "").strip() or "Unknown",
                last_name=(subject.get("family_name") or "").strip() or "Unknown",
                dob=self._normalize_dob(subject.get("birth_date") or ""),
            ),
            provider=ProviderData(
                npi=str(physician.get("license_id") or "").strip(),
                name=(physician.get("full_name") or "").strip() or "Unknown",
            ),
            medication=MedicationData(
                name=(treatment.get("drug") or "").strip(),
                primary_diagnosis=(treatment.get("icd_primary") or "").strip(),
                additional_diagnoses=[c.strip() for c in icd_secondary if (c or "").strip()],
                medication_history=prior_drugs,       # 保留对象结构
            ),
            patient_records=(raw.get("chart_summary") or "").strip(),
        )


# ── SummitAdapter ──────────────────────────────────────────────────────────
#
# Summit Health System 的 JSON 格式：完全平铺，无嵌套，SCREAMING_SNAKE_CASE
#
# {
#   "PATIENT_ID":       "334455",           ← 没有嵌套 patient 对象
#   "PT_FIRST":         "Maria",
#   "PT_LAST":          "Rodriguez",
#   "PT_BIRTHDATE":     "03/15/1968",       ← MM/DD/YYYY 格式
#   "PRESCRIBER_NPI":   "5678901234",
#   "PRESCRIBER_NAME":  "Dr. James Wu",
#   "DRUG_NAME":        "Adalimumab",
#   "DX_CODE_1":        "M06.09",           ← 副诊断是独立字段，不是数组
#   "DX_CODE_2":        "M79.3",
#   "DX_CODE_3":        "",
#   "PRIOR_MED_1":      "Methotrexate",     ← 用药历史也是独立字段
#   "PRIOR_MED_2":      "Leflunomide",
#   "CLINICAL_SUMMARY": "RA patient...",
#   "RESUBMIT":         false               ← 对应 confirm
# }
#
# 与其他格式的主要差异：
#   1. 完全没有嵌套，所有字段都在顶层
#   2. PT_BIRTHDATE 格式是 "MM/DD/YYYY" → 需要转成 "YYYY-MM-DD"
#   3. 副诊断是 DX_CODE_1/2/3 独立字段 → 需要收集成数组，过滤空值
#   4. 用药历史是 PRIOR_MED_1/2 独立字段 → 需要收集成数组，过滤空值
#   5. 二次确认字段叫 RESUBMIT

class SummitAdapter(BaseIntakeAdapter):
    source = "summit"

    def parse(self) -> Any:
        raw = json.loads(self._raw_body) if isinstance(self._raw_body, (bytes, str)) else self._raw_body
        self._parsed = raw
        return raw

    @staticmethod
    def _normalize_dob(raw_dob: str) -> str:
        """
        Summit 的生日格式是 "MM/DD/YYYY"。
        统一转成 ISO 8601 "YYYY-MM-DD"。
        其他格式原样返回（容错）。
        """
        dob = (raw_dob or "").strip()
        parts = dob.split("/")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            mm, dd, yyyy = parts
            return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
        return dob

    @staticmethod
    def _collect_numbered_fields(raw: dict, prefix: str) -> list[str]:
        """
        把 DX_CODE_1, DX_CODE_2, DX_CODE_3 ... 这类编号字段收集成数组。
        自动过滤空字符串，遇到第一个不存在的序号就停止。
        """
        result = []
        i = 1
        while True:
            val = (raw.get(f"{prefix}{i}") or "").strip()
            if f"{prefix}{i}" not in raw:
                break
            if val:
                result.append(val)
            i += 1
        return result

    def transform(self) -> InternalOrder:
        raw = self._parsed

        # 副诊断：DX_CODE_2, DX_CODE_3, ... （DX_CODE_1 是主诊断）
        additional_dx = self._collect_numbered_fields(raw, "DX_CODE_")[1:]

        # 用药历史：PRIOR_MED_1, PRIOR_MED_2, ...
        prior_meds = self._collect_numbered_fields(raw, "PRIOR_MED_")

        return InternalOrder(
            source=self.source,
            raw_payload=raw,
            confirm=bool(raw.get("RESUBMIT", False)),
            patient=PatientData(
                mrn=(raw.get("PATIENT_ID") or "").strip(),
                first_name=(raw.get("PT_FIRST") or "").strip() or "Unknown",
                last_name=(raw.get("PT_LAST") or "").strip() or "Unknown",
                dob=self._normalize_dob(raw.get("PT_BIRTHDATE") or ""),
            ),
            provider=ProviderData(
                npi=(raw.get("PRESCRIBER_NPI") or "").strip(),
                name=(raw.get("PRESCRIBER_NAME") or "").strip() or "Unknown",
            ),
            medication=MedicationData(
                name=(raw.get("DRUG_NAME") or "").strip(),
                primary_diagnosis=(raw.get("DX_CODE_1") or "").strip(),
                additional_diagnoses=additional_dx,
                medication_history=prior_meds,
            ),
            patient_records=(raw.get("CLINICAL_SUMMARY") or "").strip(),
        )
