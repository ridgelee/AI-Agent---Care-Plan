"""
测试 intake adapter 系统：
- ClinicBAdapter (JSON)
- HospitalAAdapter (XML)
- RiversideAdapter (JSON, 不同命名风格)
- 工厂函数 get_adapter
- validate() 校验失败路径
- services.create_order() 直接接受 InternalOrder
"""

import json
import pytest

from careplan.exceptions import ValidationError
from careplan.intake import get_adapter
from careplan.intake.adapters import ClinicBAdapter, HospitalAAdapter, RiversideAdapter
from careplan.intake.types import InternalOrder


# ── 测试数据 ──────────────────────────────────────────────────────────────

CLINIC_B_PAYLOAD = {
    "pt": {"mrn": "123456", "fname": "John", "lname": "Doe", "dob": "1980-01-15"},
    "provider": {"npi_num": "1234567890", "name": "Dr. Smith"},
    "dx": {"primary": "G70.00", "secondary": ["E11.9"]},
    "rx": {"med_name": "Pyridostigmine"},
    "med_hx": ["Neostigmine 2020-2022"],
    "clinical_notes": "Patient presents with ptosis.",
    "confirm": False,
}

HOSPITAL_A_XML = """<Order>
  <Patient>
    <PatientMRN>654321</PatientMRN>
    <PatientFirstName>Jane</PatientFirstName>
    <PatientLastName>Smith</PatientLastName>
    <DateOfBirth>1975-06-20</DateOfBirth>
  </Patient>
  <Physician NPI="0987654321" Name="Dr. Lee" />
  <Diagnosis Primary="M05.79">
    <Secondary>M79.3</Secondary>
  </Diagnosis>
  <Medication Name="Methotrexate" />
  <MedHistory>
    <Item>Hydroxychloroquine 2019-2021</Item>
  </MedHistory>
  <ClinicalNotes>Joint pain bilateral wrists.</ClinicalNotes>
</Order>"""

RIVERSIDE_PAYLOAD = {
    "referral": {"ref_id": "REF-2024-0891"},
    "subject": {"id_number": "789012", "given_name": "Carlos", "family_name": "Mendez", "birth_date": "19720408"},
    "ordering_physician": {"license_id": "3141592653", "full_name": "Dr. Priya Nair"},
    "treatment": {
        "drug": "Rituximab",
        "icd_primary": "C83.39",
        "icd_secondary": ["Z79.899"],
        "prior_drugs": [{"drug": "CHOP", "year": "2022"}],
    },
    "chart_summary": "Patient presents with DLBCL stage III.",
    "force_submit": False,
}


# ── ClinicBAdapter ────────────────────────────────────────────────────────

class TestClinicBAdapter:
    def _make(self, payload=None):
        body = json.dumps(payload or CLINIC_B_PAYLOAD)
        return ClinicBAdapter(raw_body=body, content_type="application/json")

    def test_process_returns_internal_order(self):
        order = self._make().process()
        assert isinstance(order, InternalOrder)

    def test_patient_fields(self):
        order = self._make().process()
        assert order.patient.mrn == "123456"
        assert order.patient.first_name == "John"
        assert order.patient.last_name == "Doe"
        assert order.patient.dob == "1980-01-15"

    def test_provider_fields(self):
        order = self._make().process()
        assert order.provider.npi == "1234567890"
        assert order.provider.name == "Dr. Smith"

    def test_medication_fields(self):
        order = self._make().process()
        assert order.medication.name == "Pyridostigmine"
        assert order.medication.primary_diagnosis == "G70.00"
        assert order.medication.additional_diagnoses == ["E11.9"]
        assert order.medication.medication_history == ["Neostigmine 2020-2022"]

    def test_raw_payload_preserved(self):
        order = self._make().process()
        assert order.raw_payload["pt"]["fname"] == "John"

    def test_source_tag(self):
        assert self._make().process().source == "clinic_b"

    def test_confirm_false_by_default(self):
        assert self._make().process().confirm is False

    def test_alternate_field_names(self):
        payload = dict(CLINIC_B_PAYLOAD)
        payload["pt"] = {"mrn": "123456", "first_name": "Alice", "last_name": "Wong", "dob": "1990-03-10"}
        payload["provider"] = {"npi": "1234567890", "name": "Dr. Kim"}
        order = self._make(payload).process()
        assert order.patient.first_name == "Alice"
        assert order.provider.npi == "1234567890"


# ── HospitalAAdapter ──────────────────────────────────────────────────────

class TestHospitalAAdapter:
    def _make(self, xml=None):
        return HospitalAAdapter(raw_body=xml or HOSPITAL_A_XML, content_type="application/xml")

    def test_process_returns_internal_order(self):
        assert isinstance(self._make().process(), InternalOrder)

    def test_patient_fields(self):
        order = self._make().process()
        assert order.patient.mrn == "654321"
        assert order.patient.first_name == "Jane"
        assert order.patient.last_name == "Smith"
        assert order.patient.dob == "1975-06-20"

    def test_provider_fields(self):
        order = self._make().process()
        assert order.provider.npi == "0987654321"
        assert order.provider.name == "Dr. Lee"

    def test_medication_fields(self):
        order = self._make().process()
        assert order.medication.name == "Methotrexate"
        assert order.medication.primary_diagnosis == "M05.79"
        assert order.medication.additional_diagnoses == ["M79.3"]
        assert order.medication.medication_history == ["Hydroxychloroquine 2019-2021"]

    def test_raw_payload_is_xml_string(self):
        assert "<PatientMRN>" in self._make().process().raw_payload

    def test_source_tag(self):
        assert self._make().process().source == "hospital_a"


# ── RiversideAdapter ──────────────────────────────────────────────────────

class TestRiversideAdapter:
    def _make(self, payload=None):
        body = json.dumps(payload or RIVERSIDE_PAYLOAD)
        return RiversideAdapter(raw_body=body, content_type="application/json")

    def test_process_returns_internal_order(self):
        assert isinstance(self._make().process(), InternalOrder)

    def test_patient_fields(self):
        order = self._make().process()
        assert order.patient.mrn == "789012"
        assert order.patient.first_name == "Carlos"
        assert order.patient.last_name == "Mendez"
        assert order.patient.dob == "1972-04-08"   # YYYYMMDD → ISO 8601

    def test_provider_fields(self):
        order = self._make().process()
        assert order.provider.npi == "3141592653"
        assert order.provider.name == "Dr. Priya Nair"

    def test_medication_fields(self):
        order = self._make().process()
        assert order.medication.name == "Rituximab"
        assert order.medication.primary_diagnosis == "C83.39"
        assert order.medication.additional_diagnoses == ["Z79.899"]
        assert order.medication.medication_history == [{"drug": "CHOP", "year": "2022"}]

    def test_force_submit_maps_to_confirm(self):
        assert self._make().process().confirm is False

    def test_source_tag(self):
        assert self._make().process().source == "riverside"

    def test_raw_payload_preserved(self):
        order = self._make().process()
        assert order.raw_payload["referral"]["ref_id"] == "REF-2024-0891"


# ── 工厂函数 ──────────────────────────────────────────────────────────────

class TestGetAdapter:
    def test_clinic_b(self):
        assert isinstance(get_adapter("clinic_b", json.dumps(CLINIC_B_PAYLOAD)), ClinicBAdapter)

    def test_hospital_a(self):
        assert isinstance(get_adapter("hospital_a", HOSPITAL_A_XML), HospitalAAdapter)

    def test_riverside(self):
        assert isinstance(get_adapter("riverside", json.dumps(RIVERSIDE_PAYLOAD)), RiversideAdapter)

    def test_unknown_source_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            get_adapter("unknown_clinic", b"{}")
        assert exc_info.value.code == "UNKNOWN_SOURCE"

    def test_full_pipeline_via_factory(self):
        order = get_adapter("clinic_b", json.dumps(CLINIC_B_PAYLOAD)).process()
        assert order.patient.mrn == "123456"


# ── validate() 校验失败路径 ───────────────────────────────────────────────

class TestValidation:
    def _make_bad(self, overrides: dict):
        payload = json.loads(json.dumps(CLINIC_B_PAYLOAD))
        payload.update(overrides)
        adapter = ClinicBAdapter(raw_body=json.dumps(payload))
        adapter.parse()
        return adapter.transform()

    def test_bad_npi_raises(self):
        order = self._make_bad({"provider": {"npi_num": "123", "name": "Dr. X"}})
        with pytest.raises(ValidationError) as exc_info:
            ClinicBAdapter(raw_body="{}").validate(order)
        fields = [e["field"] for e in exc_info.value.detail["errors"]]
        assert "provider.npi" in fields

    def test_bad_mrn_raises(self):
        order = self._make_bad({"pt": {"mrn": "99", "fname": "X", "lname": "Y", "dob": "2000-01-01"}})
        with pytest.raises(ValidationError) as exc_info:
            ClinicBAdapter(raw_body="{}").validate(order)
        fields = [e["field"] for e in exc_info.value.detail["errors"]]
        assert "patient.mrn" in fields

    def test_bad_icd10_raises(self):
        order = self._make_bad({"dx": {"primary": "NOTVALID", "secondary": []}})
        with pytest.raises(ValidationError) as exc_info:
            ClinicBAdapter(raw_body="{}").validate(order)
        fields = [e["field"] for e in exc_info.value.detail["errors"]]
        assert "medication.primary_diagnosis" in fields
