from django.urls import path

from .views import (
    OrderDetailView,
    OrderListView,
    OrderPrepareView,
    OrderVerifyPaymentView,
    PaystackWebhookView,
)

urlpatterns = [
    path("", OrderListView.as_view(), name="order-list"),
    path("prepare/", OrderPrepareView.as_view(), name="order-prepare"),
    path("verify-payment/", OrderVerifyPaymentView.as_view(), name="order-verify-payment"),
    path("paystack/webhook/", PaystackWebhookView.as_view(), name="paystack-webhook"),
    path("<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
]
