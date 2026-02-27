"""
统一异常处理器。

挂到 DRF 的 EXCEPTION_HANDLER setting 上。
所有响应（无论成功还是失败）前端都能用同一套逻辑判断：
  response.type === 'error' / 'validation_error' / 'block' / 'warning'  → 出问题了
  没有 type 字段  → 成功

统一错误响应格式：
{
    "type":    "validation_error" | "block" | "warning",
    "code":    "INVALID_NPI",
    "message": "NPI 必须是10位数字",
    "detail":  { ... }  // 可选
}
"""

from rest_framework.views import exception_handler as drf_default_handler
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.http import JsonResponse

from .exceptions import BaseAppException


def unified_exception_handler(exc, context):
    """
    DRF exception handler entry point.

    优先级：
    1. BaseAppException 及其子类 → 统一格式
    2. DRF 自带的 ValidationError（serializer.is_valid raise 的）→ 转成统一格式
    3. 其他异常 → 交给 DRF 默认处理
    """

    # --- 1. 我们自己的异常体系 ---
    if isinstance(exc, BaseAppException):
        body = {
            'type': exc.type,
            'code': exc.code,
            'message': exc.message,
        }
        if exc.detail is not None:
            body['detail'] = exc.detail
        return JsonResponse(body, status=exc.http_status)

    # --- 2. DRF 自带的 ValidationError ---
    if isinstance(exc, DRFValidationError):
        body = {
            'type': 'validation_error',
            'code': 'VALIDATION_ERROR',
            'message': 'Request validation failed',
            'detail': exc.detail,
        }
        return JsonResponse(body, status=400)

    # --- 3. 其他的交给 DRF 默认处理 ---
    return drf_default_handler(exc, context)
