import json

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import create_order, get_order_detail, get_care_plan_download, search_orders
from .exceptions import BaseAppException, ValidationError
from .intake import get_adapter
from .serializers import (
    serialize_order_created,
    serialize_order_detail,
    serialize_search_results,
)


class ExceptionHandlerMixin:
    """
    给原生 Django View 加上统一异常捕获。
    在 dispatch 层统一 catch BaseAppException，返回结构化 JSON 错误响应。
    """

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except BaseAppException as exc:
            body = {
                'type': exc.type,
                'code': exc.code,
                'message': exc.message,
            }
            if exc.detail is not None:
                body['detail'] = exc.detail
            return JsonResponse(body, status=exc.http_status)


@method_decorator(csrf_exempt, name='dispatch')
class OrderCreateView(ExceptionHandlerMixin, View):
    """POST /api/orders/ - Create order and start async care plan generation"""

    def post(self, request):
        source = request.headers.get('X-Order-Source', 'clinic_b')
        adapter = get_adapter(source, request.body, request.content_type)
        internal_order = adapter.process()          # parse → transform → validate
        order = create_order(internal_order)        # 直接传 InternalOrder
        return JsonResponse(serialize_order_created(order), status=201)


@method_decorator(csrf_exempt, name='dispatch')
class OrderDetailView(ExceptionHandlerMixin, View):
    """GET /api/orders/<order_id>/ - Get order status and care plan"""

    def get(self, request, order_id):
        order = get_order_detail(order_id)
        return JsonResponse(serialize_order_detail(order))


@method_decorator(csrf_exempt, name='dispatch')
class OrderDownloadView(ExceptionHandlerMixin, View):
    """GET /api/orders/<order_id>/download - Download care plan as text file"""

    def get(self, request, order_id):
        order = get_care_plan_download(order_id)
        content = order.care_plan.content
        filename = f"careplan_{order.patient.mrn}_{order.medication_name}_{order.created_at.strftime('%Y%m%d')}.txt"
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class OrderSearchView(ExceptionHandlerMixin, View):
    """POST /api/orders/search/ - Search orders"""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            raise ValidationError(
                message='Request body must be valid JSON.',
                code='INVALID_JSON',
            )
        query = (body.get('query') or '').strip()
        orders = search_orders(query)
        return JsonResponse(serialize_search_results(orders))
