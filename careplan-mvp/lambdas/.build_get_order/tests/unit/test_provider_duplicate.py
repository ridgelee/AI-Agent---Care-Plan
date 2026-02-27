"""
Unit tests for check_provider_duplicate().

覆盖所有 3 条路径：
1. NPI 不存在 → 返回 None
2. NPI 存在 + 名字相同 → 返回现有 provider
3. NPI 存在 + 名字不同 → raise BlockError(NPI_CONFLICT)
"""
import pytest
from careplan.services import check_provider_duplicate
from careplan.exceptions import BlockError
from tests.conftest import ProviderFactory


@pytest.mark.django_db
class TestProviderDuplicate:

    def test_new_npi_returns_none(self):
        result = check_provider_duplicate({'npi': '0000000000', 'name': 'Dr. New'})
        assert result is None

    def test_same_npi_same_name_reuses(self):
        existing = ProviderFactory(npi='1111111111', name='Dr. Smith')

        result = check_provider_duplicate({'npi': '1111111111', 'name': 'Dr. Smith'})

        assert result.id == existing.id

    def test_same_npi_different_name_blocks(self):
        ProviderFactory(npi='1111111111', name='Dr. Smith')

        with pytest.raises(BlockError) as exc_info:
            check_provider_duplicate({'npi': '1111111111', 'name': 'Dr. Johnson'})

        assert exc_info.value.code == 'NPI_CONFLICT'
        assert exc_info.value.http_status == 409
        assert 'Dr. Smith' in exc_info.value.message
        assert 'Dr. Johnson' in exc_info.value.message
        assert exc_info.value.detail['npi'] == '1111111111'
