"""
Unit tests for serializer functions.

覆盖 serialize_order_detail 的所有 status 分支 + serialize_search_results。
"""
import pytest
from careplan.serializers import serialize_order_detail, serialize_search_results
from tests.conftest import OrderFactory, CarePlanFactory


@pytest.mark.django_db
class TestSerializeOrderDetail:

    def test_pending_status(self):
        order = OrderFactory(status='pending')
        result = serialize_order_detail(order)

        assert result['status'] == 'pending'
        assert result['message'] == 'Order is queued for processing'
        assert 'care_plan' not in result

    def test_processing_status(self):
        order = OrderFactory(status='processing')
        result = serialize_order_detail(order)

        assert result['status'] == 'processing'
        assert 'please wait' in result['message']

    def test_completed_status(self):
        order = OrderFactory(status='completed')
        CarePlanFactory(order=order, content='Test plan')

        result = serialize_order_detail(order)

        assert result['status'] == 'completed'
        assert 'care_plan' in result
        assert result['care_plan']['content'] == 'Test plan'
        assert f'/api/orders/{order.id}/download' in result['care_plan']['download_url']

    def test_failed_status(self):
        order = OrderFactory(status='failed', error_message='LLM timeout')
        result = serialize_order_detail(order)

        assert result['status'] == 'failed'
        assert result['error']['message'] == 'LLM timeout'
        assert result['error']['retry_allowed'] is True

    def test_patient_info_included(self):
        order = OrderFactory()
        result = serialize_order_detail(order)

        assert 'patient' in result
        assert 'mrn' in result['patient']
        assert 'name' in result['patient']


@pytest.mark.django_db
class TestSerializeSearchResults:

    def test_empty_results(self):
        result = serialize_search_results([])
        assert result['count'] == 0
        assert result['orders'] == []

    def test_with_results(self):
        orders = [OrderFactory(), OrderFactory()]
        result = serialize_search_results(orders)

        assert result['count'] == 2
        assert 'order_id' in result['orders'][0]
        assert 'patient_name' in result['orders'][0]
        assert 'medication' in result['orders'][0]
