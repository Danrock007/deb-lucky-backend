import hashlib
import hmac
import json
import logging
import smtplib
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils.crypto import constant_time_compare
from rest_framework import generics, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from .models import Order, OrderItem
from .payments import (
    PaymentConfigurationError,
    initialize_paystack_transaction,
    verify_paystack_transaction,
)
from .serializers import (
    OrderPrepareSerializer,
    OrderSerializer,
    PaymentReferenceSerializer,
)

logger = logging.getLogger(__name__)


def send_order_confirmation(order_id):
    order = Order.objects.prefetch_related("items__product").get(pk=order_id)
    item_lines = [
        f"{item.product.name} x {item.quantity} — GHS {item.unit_price * item.quantity:.2f}"
        for item in order.items.all()
    ]
    message = "\n".join(
        [
            f"Thank you for your order {order.order_number}.",
            "",
            *item_lines,
            "",
            f"Total paid: GHS {order.total_amount:.2f}",
        ]
    )
    try:
        send_mail(
            subject=f"Order confirmation {order.order_number}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer_email],
            fail_silently=False,
        )
    except (OSError, smtplib.SMTPException):
        logger.exception(
            "Could not send order confirmation for order %s",
            order.order_number,
        )


class OrderListView(generics.ListAPIView):
    """
    Return a list of orders to authenticated staff users.
    """

    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Order.objects.prefetch_related(
            "items__product"
        ).order_by("-created_at")


class OrderDetailView(generics.RetrieveAPIView):
    """
    Return details of a single order to authenticated staff users.
    """

    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Order.objects.prefetch_related(
            "items__product"
        )


class OrderPrepareView(generics.GenericAPIView):
    serializer_class = OrderPrepareSerializer
    permission_classes = [AllowAny]
    throttle_scope = "payment"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not settings.PAYSTACK_SECRET_KEY or not settings.PAYSTACK_CALLBACK_URL:
            raise PaymentConfigurationError(
                "PAYSTACK_SECRET_KEY and PAYSTACK_CALLBACK_URL must be configured before accepting payments."
            )

        quantities = {item["product"]: item["quantity"] for item in data["items"]}
        products = list(
            Product.objects.filter(id__in=quantities, is_active=True)
            .select_related("category")
            .order_by("id")
        )
        if len(products) != len(quantities):
            raise ValidationError({"items": "One or more products are no longer available."})

        subtotal = sum(
            (product.price * quantities[product.id] for product in products),
            Decimal("0.00"),
        )
        discount_percent = {"WELCOME10": 10, "SAVE20": 20}.get(
            data.get("promo_code", ""),
            0,
        )
        discount = (subtotal * discount_percent / 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        total_amount = (subtotal - discount).quantize(Decimal("0.01"))
        if total_amount <= 0:
            raise ValidationError({"items": "The order total must be greater than zero."})

        for product in products:
            if product.stock_quantity < quantities[product.id]:
                raise ValidationError(
                    {"items": f"Not enough stock for {product.name}."}
                )

        order_number = f"DLJ-{uuid.uuid4().hex[:12].upper()}"
        payment_reference = f"DLJ-{uuid.uuid4().hex.upper()}"
        with transaction.atomic():
            order = Order.objects.create(
                order_number=order_number,
                customer_name=data["customer_name"],
                customer_email=data["customer_email"],
                shipping_address=data["shipping_address"],
                shipping_city=data["shipping_city"],
                shipping_postal_code=data["shipping_postal_code"],
                shipping_country=data["shipping_country"],
                payment_reference=payment_reference,
                total_amount=total_amount,
                status="pending",
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        product=product,
                        quantity=quantities[product.id],
                        unit_price=product.price,
                    )
                    for product in products
                ]
            )

        authorization_url = initialize_paystack_transaction(
            email=order.customer_email,
            amount_minor=int(total_amount * 100),
            reference=payment_reference,
            metadata={"order_number": order.order_number},
            payment_method=data["payment_method"],
        )

        return Response(
            {
                "order_number": order.order_number,
                "reference": payment_reference,
                "amount": str(total_amount),
                "authorization_url": authorization_url,
            },
            status=status.HTTP_201_CREATED,
        )


class OrderVerifyPaymentView(generics.GenericAPIView):
    serializer_class = PaymentReferenceSerializer
    permission_classes = [AllowAny]
    throttle_scope = "payment"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(complete_order_payment(serializer.validated_data["reference"]))


def complete_order_payment(reference):
    order = Order.objects.filter(payment_reference=reference).first()
    if order is None:
        raise ValidationError({"reference": "No order exists for this payment."})
    if order.status == "paid":
        return {
            "order_number": order.order_number,
            "status": order.status,
            "customer_email": order.customer_email,
        }
    if order.status != "pending":
        raise ValidationError({"reference": "This order is not awaiting payment."})

    payment = verify_paystack_transaction(reference)
    customer = payment.get("customer")
    customer_email = customer.get("email") if isinstance(customer, dict) else None
    if (
        payment.get("status") != "success"
        or payment.get("currency") != "GHS"
        or payment.get("amount") != int(order.total_amount * 100)
        or not isinstance(customer_email, str)
        or customer_email.lower() != order.customer_email.lower()
    ):
        raise ValidationError({"reference": "Paystack could not verify this payment."})

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == "paid":
            return {
                "order_number": order.order_number,
                "status": order.status,
                "customer_email": order.customer_email,
            }
        if order.status != "pending":
            raise ValidationError({"reference": "This order is not awaiting payment."})

        order_items = list(order.items.all())
        product_ids = sorted(item.product_id for item in order_items)
        locked_products = {
            product.id: product
            for product in Product.objects.select_for_update()
            .filter(id__in=product_ids)
            .order_by("id")
        }
        for item in order_items:
            product = locked_products.get(item.product_id)
            if (
                product is None
                or not product.is_active
                or product.stock_quantity < item.quantity
            ):
                raise ValidationError(
                    {"items": "A product in this order is no longer available in the requested quantity."}
                )

        for product in locked_products.values():
            quantity = sum(
                item.quantity
                for item in order_items
                if item.product_id == product.id
            )
            product.stock_quantity -= quantity
            product.save(update_fields=["stock_quantity"])

        order.status = "paid"
        order.save(update_fields=["status", "updated_at"])
        transaction.on_commit(lambda: send_order_confirmation(order.pk))

    return {
        "order_number": order.order_number,
        "status": order.status,
        "customer_email": order.customer_email,
    }


class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request, *args, **kwargs):
        signature = request.headers.get("x-paystack-signature", "")
        if not settings.PAYSTACK_SECRET_KEY or not signature:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        expected_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
            request.body,
            hashlib.sha512,
        ).hexdigest()
        if not constant_time_compare(signature, expected_signature):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            event = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(event, dict):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if event.get("event") != "charge.success":
            return Response(status=status.HTTP_200_OK)

        event_data = event.get("data")
        reference = event_data.get("reference") if isinstance(event_data, dict) else None
        if not isinstance(reference, str) or not reference:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            complete_order_payment(reference)
        except APIException as exc:
            return Response(
                {"detail": exc.detail},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(status=status.HTTP_200_OK)
