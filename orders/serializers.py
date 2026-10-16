from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "unit_price",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "customer_name",
            "customer_email",
            "shipping_address",
            "shipping_city",
            "shipping_postal_code",
            "shipping_country",
            "payment_reference",
            "total_amount",
            "status",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "total_amount",
            "status",
            "items",
            "created_at",
            "updated_at",
        ]


class OrderItemInputSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class OrderPrepareSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=200, trim_whitespace=True)
    customer_email = serializers.EmailField()
    shipping_address = serializers.CharField(max_length=255, trim_whitespace=True)
    shipping_city = serializers.CharField(max_length=100, trim_whitespace=True)
    shipping_postal_code = serializers.CharField(max_length=50, trim_whitespace=True)
    shipping_country = serializers.CharField(max_length=100, trim_whitespace=True)
    promo_code = serializers.ChoiceField(
        choices=["", "WELCOME10", "SAVE20"],
        required=False,
        allow_blank=True,
    )
    payment_method = serializers.ChoiceField(
        choices=["card", "mobile_money"],
        default="card",
    )
    items = OrderItemInputSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        product_ids = [item["product"] for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Each product may appear only once.")
        return items


class PaymentReferenceSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=120, trim_whitespace=True)
