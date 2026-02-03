from django.urls import path
from .views import OrderCreateView, OrderDetailView, OrderDownloadView, OrderSearchView

urlpatterns = [
    path('orders/', OrderCreateView.as_view(), name='order-create'),
    path('orders/search/', OrderSearchView.as_view(), name='order-search'),
    path('orders/<uuid:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<uuid:order_id>/download', OrderDownloadView.as_view(), name='order-download'),
]
