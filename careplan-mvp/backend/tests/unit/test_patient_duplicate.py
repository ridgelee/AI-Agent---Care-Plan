"""
Unit tests for check_patient_duplicate().

覆盖所有 5 条路径：
1. MRN 存在 + 姓名 DOB 全匹配 → 复用，无警告
2. MRN 存在 + 姓名不匹配 → 复用 + MRN_INFO_MISMATCH 警告
3. MRN 存在 + DOB 不匹配 → 复用 + MRN_INFO_MISMATCH 警告
4. MRN 存在 + 姓名和 DOB 都不匹配 → 复用 + 警告里列出两项差异
5. MRN 不存在 + 姓名 DOB 匹配已有患者 → 返回 None + POSSIBLE_DUPLICATE_PATIENT 警告
6. MRN 不存在 + 无任何匹配 → 返回 None，无警告（全新患者）
7. DOB 为字符串时能正确解析
"""
import pytest
from datetime import date
from careplan.services import check_patient_duplicate
from tests.conftest import PatientFactory


@pytest.mark.django_db
class TestPatientDuplicate:

    # ---------------------------------------------------------------
    # Case 1: MRN 匹配 + 全部信息一致 → 复用，无警告
    # ---------------------------------------------------------------
    def test_exact_match_reuses_patient(self):
        existing = PatientFactory(mrn='111111', first_name='John', last_name='Doe', dob=date(1990, 1, 15))

        patient, warnings = check_patient_duplicate({
            'mrn': '111111',
            'first_name': 'John',
            'last_name': 'Doe',
            'dob': date(1990, 1, 15),
        })

        assert patient.id == existing.id
        assert warnings == []

    # ---------------------------------------------------------------
    # Case 2: MRN 匹配 + 姓名不同 → 复用 + 警告
    # ---------------------------------------------------------------
    def test_mrn_match_name_mismatch_warns(self):
        PatientFactory(mrn='111111', first_name='John', last_name='Doe', dob=date(1990, 1, 15))

        patient, warnings = check_patient_duplicate({
            'mrn': '111111',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'dob': date(1990, 1, 15),
        })

        assert patient is not None  # 仍然复用
        assert len(warnings) == 1
        assert warnings[0]['code'] == 'MRN_INFO_MISMATCH'
        assert '姓名' in warnings[0]['message']

    # ---------------------------------------------------------------
    # Case 3: MRN 匹配 + DOB 不同 → 复用 + 警告
    # ---------------------------------------------------------------
    def test_mrn_match_dob_mismatch_warns(self):
        PatientFactory(mrn='111111', first_name='John', last_name='Doe', dob=date(1990, 1, 15))

        patient, warnings = check_patient_duplicate({
            'mrn': '111111',
            'first_name': 'John',
            'last_name': 'Doe',
            'dob': date(2000, 6, 1),
        })

        assert patient is not None
        assert len(warnings) == 1
        assert warnings[0]['code'] == 'MRN_INFO_MISMATCH'
        assert 'DOB' in warnings[0]['message']

    # ---------------------------------------------------------------
    # Case 4: MRN 匹配 + 姓名和 DOB 都不同 → 警告里列出两项差异
    # ---------------------------------------------------------------
    def test_mrn_match_both_mismatch_warns(self):
        PatientFactory(mrn='111111', first_name='John', last_name='Doe', dob=date(1990, 1, 15))

        patient, warnings = check_patient_duplicate({
            'mrn': '111111',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'dob': date(2000, 6, 1),
        })

        assert patient is not None
        assert len(warnings) == 1
        assert '姓名' in warnings[0]['message']
        assert 'DOB' in warnings[0]['message']

    # ---------------------------------------------------------------
    # Case 5: MRN 不存在 + 姓名 DOB 已有 → None + 警告
    # ---------------------------------------------------------------
    def test_new_mrn_with_name_dob_duplicate_warns(self):
        PatientFactory(mrn='111111', first_name='John', last_name='Doe', dob=date(1990, 1, 15))

        patient, warnings = check_patient_duplicate({
            'mrn': '222222',
            'first_name': 'John',
            'last_name': 'Doe',
            'dob': date(1990, 1, 15),
        })

        assert patient is None  # 没有复用，需要新建
        assert len(warnings) == 1
        assert warnings[0]['code'] == 'POSSIBLE_DUPLICATE_PATIENT'
        assert '111111' in warnings[0]['message']  # 提到已有的 MRN

    # ---------------------------------------------------------------
    # Case 6: 全新患者 → None，无警告
    # ---------------------------------------------------------------
    def test_completely_new_patient_no_warnings(self):
        patient, warnings = check_patient_duplicate({
            'mrn': '333333',
            'first_name': 'Brand',
            'last_name': 'New',
            'dob': date(2001, 12, 25),
        })

        assert patient is None
        assert warnings == []

    # ---------------------------------------------------------------
    # Case 7: DOB 传字符串也能正常工作
    # ---------------------------------------------------------------
    def test_dob_as_string_works(self):
        existing = PatientFactory(mrn='111111', first_name='John', last_name='Doe', dob=date(1990, 1, 15))

        patient, warnings = check_patient_duplicate({
            'mrn': '111111',
            'first_name': 'John',
            'last_name': 'Doe',
            'dob': '1990-01-15',  # 字符串
        })

        assert patient.id == existing.id
        assert warnings == []
