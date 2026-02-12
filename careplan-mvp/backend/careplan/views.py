from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import create_order, get_order_detail, get_care_plan_download, search_orders
from .serializers import (
    parse_order_request,
    serialize_order_created,
    serialize_order_detail,
    serialize_order_not_found,
    serialize_search_results,
)


@method_decorator(csrf_exempt, name='dispatch')
class OrderCreateView(View):
    """POST /api/orders/ - Create order and start async care plan generation"""

    def post(self, request):
        print(f"\n[DEBUG][views.py][OrderCreateView.post] ========== 请求进入 ==========")
        print(f"[DEBUG][views.py][OrderCreateView.post] Step 1: 调用 serializers.parse_order_request()")
        data = parse_order_request(request)
        print(f"[DEBUG][views.py][OrderCreateView.post] Step 2: 调用 services.create_order()")
        order = create_order(data)
        print(f"[DEBUG][views.py][OrderCreateView.post] Step 3: 调用 serializers.serialize_order_created()")
        response_data = serialize_order_created(order)
        print(f"[DEBUG][views.py][OrderCreateView.post] Step 4: 返回 JsonResponse, status=201")
        print(f"[DEBUG][views.py][OrderCreateView.post] ========== 请求结束 ==========\n")
        return JsonResponse(response_data, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class OrderDetailView(View):
    """GET /api/orders/<order_id>/ - Get order status and care plan"""

    def get(self, request, order_id):
        order = get_order_detail(order_id)
        if order is None:
            return JsonResponse(serialize_order_not_found(order_id), status=404)
        return JsonResponse(serialize_order_detail(order))


@method_decorator(csrf_exempt, name='dispatch')
class OrderDownloadView(View):
    """GET /api/orders/<order_id>/download - Download care plan as text file"""

    def get(self, request, order_id):
        order, error_msg, status_code = get_care_plan_download(order_id)
        if order is None:
            return JsonResponse({'error': error_msg}, status=status_code)

        content = order.care_plan.content
        filename = f"careplan_{order.patient.mrn}_{order.medication_name}_{order.created_at.strftime('%Y%m%d')}.txt"

        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class OrderSearchView(View):
    """POST /api/orders/search/ - Search orders"""

    def post(self, request):
        data = parse_order_request(request)
        query = data.get('query', '').strip()
        orders = search_orders(query)
        return JsonResponse(serialize_search_results(orders))
