from django.http import JsonResponse
from django.urls import path, include


def health_check(request):
    return JsonResponse({
        "status": "ok",
        "version": "1.0",
        "endpoints": {
            "orders": "/api/orders/",
            "search": "/api/orders/search/",
            "metrics": "/metrics",
        }
    })


urlpatterns = [
    path('', health_check, name='health-check'),
    path('', include('django_prometheus.urls')),
    path('api/', include('careplan.urls')),
]
