from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_email",
        "total_amount",
        "status",
        "created_at",
    )

    list_filter = ("status", "created_at")
    search_fields = ("order_number", "customer_email")
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "unit_price")
    search_fields = ("order__order_number", "product__name")