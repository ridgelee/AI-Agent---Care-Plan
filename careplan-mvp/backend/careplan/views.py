from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import create_order, get_order_detail, get_care_plan_download, search_orders
from .exceptions import BaseAppException
from .serializers import (
    parse_order_request,
    serialize_order_created,
    serialize_order_detail,
    serialize_search_results,
)


class ExceptionHandlerMixin:
    """
    给原生 Django View 加上统一异常捕获。

    DRF 的 EXCEPTION_HANDLER 只对 DRF 的 APIView 生效。
    当前项目用的是 django.views.View，所以需要这个 mixin
    在 dispatch 层统一 catch BaseAppException。
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
        data = parse_order_request(request)
        order = create_order(data)    # BlockError / WarningError → mixin 兜底
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
        data = parse_order_request(request)
        query = data.get('query', '').strip()
        orders = search_orders(query)
        return JsonResponse(serialize_search_results(orders))
