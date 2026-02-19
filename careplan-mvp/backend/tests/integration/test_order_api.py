"""
Integration tests — 真实 HTTP 请求打到 Django View，验证完整流程。

用 Django test Client，走完：
  HTTP Request → urls.py → View → Service → ORM → DB → Response

每个测试验证：status_code + response body 的统一格式。
Celery task 被 mock 掉，不实际调 LLM。
"""
import json
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from django.utils import timezone

from tests.conftest import PatientFactory, ProviderFactory, OrderFactory, CarePlanFactory
from careplan.models import Patient, Provider, Order


# -------------------------------------------------------------------
# Helper
# -------------------------------------------------------------------

def post_order(api_client, payload, **kwargs):
    """快捷方式：POST /api/orders/，返回 (status_code, body_dict)。"""
    response = api_client.post(
        '/api/orders/',
        data=json.dumps(payload),
        content_type='application/json',
        **kwargs,
    )
    return response.status_code, json.loads(response.content)


# ===================================================================
# Happy path
# ===================================================================

@pytest.mark.django_db
class TestCreateOrderHappyPath:

    @patch('careplan.tasks.generate_care_plan')
    def test_create_order_success(self, mock_task, api_client, sample_order_payload):
        status, body = post_order(api_client, sample_order_payload)

        assert status == 201
        assert 'order_id' in body
        assert body['status'] == 'pending'
        # 不应有 type 字段（type 只在错误时出现）
        assert 'type' not in body

        # DB 里确实创建了
        assert Patient.objects.filter(mrn='999001').exists()
        assert Provider.objects.filter(npi='9999900001').exists()
        assert Order.objects.count() == 1

    @patch('careplan.tasks.generate_care_plan')
    def test_celery_task_dispatched(self, mock_task, api_client, sample_order_payload):
        post_order(api_client, sample_order_payload)
        mock_task.delay.assert_called_once()


# ===================================================================
# Provider errors
# ===================================================================

@pytest.mark.django_db
class TestProviderErrors:

    @patch('careplan.tasks.generate_care_plan')
    def test_npi_conflict_returns_409_block(self, mock_task, api_client, sample_order_payload):
        ProviderFactory(npi='9999900001', name='Dr. Existing')
        # payload 里的 NPI 相同但名字不同
        sample_order_payload['provider']['name'] = 'Dr. Different'

        status, body = post_order(api_client, sample_order_payload)

        assert status == 409
        assert body['type'] == 'block'
        assert body['code'] == 'NPI_CONFLICT'
        assert 'Dr. Existing' in body['message']
        # 不应创建订单
        assert Order.objects.count() == 0


# ===================================================================
# Patient warnings
# ===================================================================

@pytest.mark.django_db
class TestPatientWarnings:

    @patch('careplan.tasks.generate_care_plan')
    def test_mrn_info_mismatch_returns_409_warning(self, mock_task, api_client, sample_order_payload):
        PatientFactory(mrn='999001', first_name='Bob', last_name='Lee', dob=date(1985, 3, 20))
        # payload 里的 MRN 相同但名字不同

        status, body = post_order(api_client, sample_order_payload)

        assert status == 409
        assert body['type'] == 'warning'
        assert body['code'] == 'CONFIRMATION_REQUIRED'
        assert any(
            w['code'] == 'MRN_INFO_MISMATCH'
            for w in body['detail']['warnings']
        )
        # 不应创建订单
        assert Order.objects.count() == 0

    @patch('careplan.tasks.generate_care_plan')
    def test_warning_with_confirm_creates_order(self, mock_task, api_client, sample_order_payload):
        PatientFactory(mrn='999001', first_name='Bob', last_name='Lee', dob=date(1985, 3, 20))

        sample_order_payload['confirm'] = True
        status, body = post_order(api_client, sample_order_payload)

        assert status == 201
        assert Order.objects.count() == 1

    @patch('careplan.tasks.generate_care_plan')
    def test_possible_duplicate_patient_warns(self, mock_task, api_client, sample_order_payload):
        # 同名同DOB 但不同 MRN
        PatientFactory(mrn='888888', first_name='Alice', last_name='Wang', dob=date(1985, 3, 20))

        status, body = post_order(api_client, sample_order_payload)

        assert status == 409
        assert body['type'] == 'warning'
        assert any(
            w['code'] == 'POSSIBLE_DUPLICATE_PATIENT'
            for w in body['detail']['warnings']
        )


# ===================================================================
# Order duplicate errors
# ===================================================================

@pytest.mark.django_db
class TestOrderDuplicateErrors:

    @patch('careplan.tasks.generate_care_plan')
    def test_same_day_duplicate_returns_409_block(self, mock_task, api_client, sample_order_payload):
        # 先创建一个今天的订单
        patient = PatientFactory(mrn='999001', first_name='Alice', last_name='Wang', dob=date(1985, 3, 20))
        provider = ProviderFactory(npi='9999900001', name='Dr. Test')
        OrderFactory(patient=patient, provider=provider, medication_name='Humira')

        status, body = post_order(api_client, sample_order_payload)

        assert status == 409
        assert body['type'] == 'block'
        assert body['code'] == 'DUPLICATE_ORDER_SAME_DAY'

    @patch('careplan.tasks.generate_care_plan')
    def test_history_duplicate_warns(self, mock_task, api_client, sample_order_payload):
        patient = PatientFactory(mrn='999001', first_name='Alice', last_name='Wang', dob=date(1985, 3, 20))
        provider = ProviderFactory(npi='9999900001', name='Dr. Test')
        order = OrderFactory(patient=patient, provider=provider, medication_name='Humira')
        # 把订单改到昨天
        Order.objects.filter(id=order.id).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        status, body = post_order(api_client, sample_order_payload)

        assert status == 409
        assert body['type'] == 'warning'
        assert any(
            w['code'] == 'DUPLICATE_ORDER_HISTORY'
            for w in body['detail']['warnings']
        )

    @patch('careplan.tasks.generate_care_plan')
    def test_history_duplicate_with_confirm_succeeds(self, mock_task, api_client, sample_order_payload):
        patient = PatientFactory(mrn='999001', first_name='Alice', last_name='Wang', dob=date(1985, 3, 20))
        provider = ProviderFactory(npi='9999900001', name='Dr. Test')
        order = OrderFactory(patient=patient, provider=provider, medication_name='Humira')
        Order.objects.filter(id=order.id).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        sample_order_payload['confirm'] = True
        status, body = post_order(api_client, sample_order_payload)

        assert status == 201
        assert Order.objects.count() == 2  # 原来 1 + 新建 1


# ===================================================================
# Order detail & download errors
# ===================================================================

@pytest.mark.django_db
class TestOrderDetailErrors:

    def test_nonexistent_order_returns_404(self, api_client):
        response = api_client.get('/api/orders/00000000-0000-0000-0000-000000000000/')
        body = json.loads(response.content)

        assert response.status_code == 404
        assert body['type'] == 'block'
        assert body['code'] == 'ORDER_NOT_FOUND'

    def test_existing_order_returns_200(self, api_client):
        order = OrderFactory()
        response = api_client.get(f'/api/orders/{order.id}/')
        body = json.loads(response.content)

        assert response.status_code == 200
        assert body['order_id'] == str(order.id)
        assert 'type' not in body


@pytest.mark.django_db
class TestOrderDownloadErrors:

    def test_download_not_completed_returns_400(self, api_client):
        order = OrderFactory(status='pending')
        response = api_client.get(f'/api/orders/{order.id}/download')
        body = json.loads(response.content)

        assert response.status_code == 400
        assert body['type'] == 'validation_error'
        assert body['code'] == 'CAREPLAN_NOT_READY'

    def test_download_completed_returns_file(self, api_client):
        order = OrderFactory(status='completed')
        CarePlanFactory(order=order, content='Plan content here')

        response = api_client.get(f'/api/orders/{order.id}/download')

        assert response.status_code == 200
        assert response['Content-Type'] == 'text/plain'
        assert b'Plan content here' in response.content


# ===================================================================
# Unified response format contract
# ===================================================================

@pytest.mark.django_db
class TestUnifiedResponseFormat:
    """
    验证前端的核心约定：
    - 成功响应：没有 type 字段
    - 错误响应：一定有 type / code / message 字段
    """

    @patch('careplan.tasks.generate_care_plan')
    def test_success_has_no_type(self, mock_task, api_client, sample_order_payload):
        _, body = post_order(api_client, sample_order_payload)
        assert 'type' not in body

    @patch('careplan.tasks.generate_care_plan')
    def test_block_has_required_fields(self, mock_task, api_client, sample_order_payload):
        ProviderFactory(npi='9999900001', name='Dr. Other')
        _, body = post_order(api_client, sample_order_payload)
        assert 'type' in body
        assert 'code' in body
        assert 'message' in body

    def test_404_has_required_fields(self, api_client):
        response = api_client.get('/api/orders/00000000-0000-0000-0000-000000000000/')
        body = json.loads(response.content)
        assert 'type' in body
        assert 'code' in body
        assert 'message' in body
