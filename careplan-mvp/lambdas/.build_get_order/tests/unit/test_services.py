"""
Unit tests for service layer functions not covered by duplicate detection tests.

覆盖：get_order_detail, get_care_plan_download, search_orders。
"""
import pytest
import uuid

from careplan.services import get_order_detail, get_care_plan_download, search_orders
from careplan.exceptions import BlockError, ValidationError
from tests.conftest import OrderFactory, CarePlanFactory


@pytest.mark.django_db
class TestGetOrderDetail:

    def test_existing_order(self):
        order = OrderFactory()
        result = get_order_detail(order.id)
        assert result.id == order.id

    def test_nonexistent_order_raises(self):
        fake_id = uuid.uuid4()
        with pytest.raises(BlockError) as exc_info:
            get_order_detail(fake_id)

        assert exc_info.value.code == 'ORDER_NOT_FOUND'
        assert exc_info.value.http_status == 404


@pytest.mark.django_db
class TestGetCarePlanDownload:

    def test_completed_order_returns_order(self):
        order = OrderFactory(status='completed')
        CarePlanFactory(order=order)

        result = get_care_plan_download(order.id)
        assert result.id == order.id

    def test_pending_order_raises_validation_error(self):
        order = OrderFactory(status='pending')

        with pytest.raises(ValidationError) as exc_info:
            get_care_plan_download(order.id)

        assert exc_info.value.code == 'CAREPLAN_NOT_READY'
        assert exc_info.value.http_status == 400

    def test_nonexistent_order_raises_block(self):
        fake_id = uuid.uuid4()
        with pytest.raises(BlockError) as exc_info:
            get_care_plan_download(fake_id)

        assert exc_info.value.code == 'ORDER_NOT_FOUND'


@pytest.mark.django_db
class TestSearchOrders:

    def test_search_by_medication(self):
        OrderFactory(medication_name='Humira')
        OrderFactory(medication_name='Enbrel')

        results = search_orders('Humira')
        assert len(results) == 1

    def test_search_by_patient_mrn(self):
        from tests.conftest import PatientFactory
        patient = PatientFactory(mrn='999999')
        OrderFactory(patient=patient)

        results = search_orders('999999')
        assert len(results) == 1

    def test_search_by_patient_name(self):
        from tests.conftest import PatientFactory
        patient = PatientFactory(first_name='UniqueNameXYZ')
        OrderFactory(patient=patient)

        results = search_orders('UniqueNameXYZ')
        assert len(results) == 1

    def test_search_no_match(self):
        OrderFactory()
        results = search_orders('nonexistent_term_xyz')
        assert len(results) == 0

    def test_search_limit_20(self):
        for _ in range(25):
            OrderFactory()
        results = search_orders('')
        # id__icontains='' matches everything, but limited to 20
        assert len(results) == 20
