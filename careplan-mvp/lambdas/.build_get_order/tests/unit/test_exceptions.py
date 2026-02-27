"""
Unit tests for exception classes and ExceptionHandlerMixin.

不需要数据库，纯 Python 测试：
1. BaseAppException 默认值
2. 各子类的默认 type / code / http_status
3. 构造时覆盖 code / http_status
4. detail 可选
5. ExceptionHandlerMixin 把异常转成正确的 JsonResponse
"""
import json
import pytest
from django.test import RequestFactory
from django.http import JsonResponse
from django.views import View

from careplan.exceptions import (
    BaseAppException,
    ValidationError,
    BlockError,
    WarningError,
)
from careplan.views import ExceptionHandlerMixin


# -------------------------------------------------------------------
# Exception classes
# -------------------------------------------------------------------

class TestBaseAppException:

    def test_defaults(self):
        exc = BaseAppException('something broke')
        assert exc.message == 'something broke'
        assert exc.type == 'error'
        assert exc.code == 'UNKNOWN_ERROR'
        assert exc.http_status == 500
        assert exc.detail is None

    def test_override_code_and_status(self):
        exc = BaseAppException('bad', code='CUSTOM_CODE', http_status=418)
        assert exc.code == 'CUSTOM_CODE'
        assert exc.http_status == 418

    def test_detail_preserved(self):
        exc = BaseAppException('bad', detail={'key': 'value'})
        assert exc.detail == {'key': 'value'}


class TestValidationError:

    def test_defaults(self):
        exc = ValidationError('bad input')
        assert exc.type == 'validation_error'
        assert exc.code == 'VALIDATION_ERROR'
        assert exc.http_status == 400

    def test_custom_code(self):
        exc = ValidationError('npi invalid', code='INVALID_NPI')
        assert exc.code == 'INVALID_NPI'
        assert exc.http_status == 400  # status 没变


class TestBlockError:

    def test_defaults(self):
        exc = BlockError('blocked')
        assert exc.type == 'block'
        assert exc.code == 'BUSINESS_BLOCK'
        assert exc.http_status == 409

    def test_override_http_status(self):
        exc = BlockError('not found', code='ORDER_NOT_FOUND', http_status=404)
        assert exc.http_status == 404


class TestWarningError:

    def test_defaults(self):
        exc = WarningError('needs confirm')
        assert exc.type == 'warning'
        assert exc.code == 'CONFIRMATION_REQUIRED'
        assert exc.http_status == 409

    def test_with_warnings_detail(self):
        exc = WarningError(
            'needs confirm',
            detail={'warnings': [{'code': 'X', 'message': 'y'}]},
        )
        assert exc.detail['warnings'][0]['code'] == 'X'


# -------------------------------------------------------------------
# ExceptionHandlerMixin
# -------------------------------------------------------------------

class _RaisingView(ExceptionHandlerMixin, View):
    """测试用 View，根据 query param 抛不同异常。"""

    exc_to_raise = None

    def get(self, request):
        if self.exc_to_raise:
            raise self.exc_to_raise
        return JsonResponse({'ok': True})


class TestExceptionHandlerMixin:

    def _make_request(self):
        return RequestFactory().get('/')

    def test_no_exception_passes_through(self):
        _RaisingView.exc_to_raise = None
        response = _RaisingView.as_view()(self._make_request())
        assert response.status_code == 200

    def test_block_error_returns_409(self):
        _RaisingView.exc_to_raise = BlockError(
            'blocked', code='NPI_CONFLICT', detail={'npi': '123'}
        )
        response = _RaisingView.as_view()(self._make_request())

        assert response.status_code == 409
        body = json.loads(response.content)
        assert body['type'] == 'block'
        assert body['code'] == 'NPI_CONFLICT'
        assert body['detail']['npi'] == '123'

    def test_validation_error_returns_400(self):
        _RaisingView.exc_to_raise = ValidationError('bad input')
        response = _RaisingView.as_view()(self._make_request())

        assert response.status_code == 400
        body = json.loads(response.content)
        assert body['type'] == 'validation_error'

    def test_warning_error_returns_409(self):
        _RaisingView.exc_to_raise = WarningError(
            'confirm pls',
            detail={'warnings': [{'code': 'W1', 'message': 'warn'}]},
        )
        response = _RaisingView.as_view()(self._make_request())

        assert response.status_code == 409
        body = json.loads(response.content)
        assert body['type'] == 'warning'
        assert body['detail']['warnings'][0]['code'] == 'W1'

    def test_no_detail_field_when_none(self):
        _RaisingView.exc_to_raise = BlockError('blocked')
        response = _RaisingView.as_view()(self._make_request())

        body = json.loads(response.content)
        assert 'detail' not in body

    def test_non_app_exception_not_caught(self):
        """非 BaseAppException 的异常不被 mixin 捕获，应正常冒泡。"""
        _RaisingView.exc_to_raise = RuntimeError('unexpected')
        with pytest.raises(RuntimeError):
            _RaisingView.as_view()(self._make_request())
