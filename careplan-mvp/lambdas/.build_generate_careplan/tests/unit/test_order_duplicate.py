"""
Unit tests for check_order_duplicate().

覆盖所有路径：
1. 无历史订单 → 空 warnings
2. 同患者 + 同药 + 同天 → raise BlockError(DUPLICATE_ORDER_SAME_DAY)
3. 同患者 + 同药 + 不同天 + confirm=False → 警告
4. 同患者 + 同药 + 不同天 + confirm=True → 跳过，空 warnings
5. 同患者 + 不同药 → 不触发
"""
import pytest
from datetime import date, timedelta
from django.utils import timezone
from careplan.services import check_order_duplicate
from careplan.exceptions import BlockError
from tests.conftest import PatientFactory, ProviderFactory, OrderFactory


@pytest.mark.django_db
class TestOrderDuplicate:

    def test_no_existing_orders_no_warnings(self):
        patient = PatientFactory()
        warnings = check_order_duplicate(patient, 'Humira')
        assert warnings == []

    def test_same_day_same_medication_blocks(self):
        patient = PatientFactory()
        provider = ProviderFactory()
        OrderFactory(patient=patient, provider=provider, medication_name='Humira')

        with pytest.raises(BlockError) as exc_info:
            check_order_duplicate(patient, 'Humira')

        assert exc_info.value.code == 'DUPLICATE_ORDER_SAME_DAY'
        assert exc_info.value.http_status == 409

    def test_different_day_warns_without_confirm(self):
        patient = PatientFactory()
        provider = ProviderFactory()
        # 创建一个昨天的订单
        order = OrderFactory(patient=patient, provider=provider, medication_name='Humira')
        # 手动把 created_at 改到昨天
        from careplan.models import Order
        Order.objects.filter(id=order.id).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        warnings = check_order_duplicate(patient, 'Humira', confirm=False)

        assert len(warnings) == 1
        assert warnings[0]['code'] == 'DUPLICATE_ORDER_HISTORY'

    def test_different_day_skips_with_confirm(self):
        patient = PatientFactory()
        provider = ProviderFactory()
        order = OrderFactory(patient=patient, provider=provider, medication_name='Humira')
        from careplan.models import Order
        Order.objects.filter(id=order.id).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        warnings = check_order_duplicate(patient, 'Humira', confirm=True)

        assert warnings == []

    def test_different_medication_no_conflict(self):
        patient = PatientFactory()
        provider = ProviderFactory()
        OrderFactory(patient=patient, provider=provider, medication_name='Humira')

        # 同一天，但不同药
        warnings = check_order_duplicate(patient, 'Enbrel')
        assert warnings == []
