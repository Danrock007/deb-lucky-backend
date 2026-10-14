from decimal import Decimal
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from catalog.models import Category, Product
from .models import Order, OrderItem


# ============================================================
# ORDER MODEL TESTS
# ============================================================

class OrderModelTest(TestCase):

    def setUp(self):
        self.order = Order.objects.create(
            order_number="TEST-ORDER-001",
            customer_email="customer@example.com",
            total_amount=Decimal("250.00"),
        )

    def test_order_creation(self):
        self.assertEqual(self.order.order_number, "TEST-ORDER-001")
        self.assertEqual(
            self.order.customer_email,
            "customer@example.com",
        )
        self.assertEqual(
            self.order.total_amount,
            Decimal("250.00"),
        )

    def test_order_default_status_is_pending(self):
        self.assertEqual(self.order.status, "pending")

    def test_order_string_representation(self):
        self.assertEqual(str(self.order), "TEST-ORDER-001")


# ============================================================
# ORDER ITEM MODEL TESTS
# ============================================================

class OrderItemModelTest(TestCase):

    def setUp(self):
        self.category = Category.objects.create(
            name="Rings",
            description="Fashion rings",
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Gold Fashion Ring",
            description="A gold-coloured fashion ring",
            price=Decimal("250.00"),
            stock_quantity=10,
        )

        self.order = Order.objects.create(
            order_number="TEST-ORDER-002",
            customer_email="customer@example.com",
            total_amount=Decimal("500.00"),
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            unit_price=Decimal("250.00"),
        )

    def test_order_item_creation(self):
        self.assertEqual(self.order_item.order, self.order)
        self.assertEqual(self.order_item.product, self.product)
        self.assertEqual(self.order_item.quantity, 2)
        self.assertEqual(
            self.order_item.unit_price,
            Decimal("250.00"),
        )

    def test_order_item_string_representation(self):
        self.assertEqual(
            str(self.order_item),
            "Gold Fashion Ring x 2",
        )

    def test_order_can_have_multiple_items(self):
        second_product = Product.objects.create(
            category=self.category,
            name="Silver Fashion Ring",
            description="A silver-coloured fashion ring",
            price=Decimal("150.00"),
            stock_quantity=5,
        )

        OrderItem.objects.create(
            order=self.order,
            product=second_product,
            quantity=1,
            unit_price=Decimal("150.00"),
        )

        self.assertEqual(self.order.items.count(), 2)


# ============================================================
# ORDERS API TESTS
# ============================================================

class OrderAPITest(APITestCase):

    def setUp(self):
        self.client = APIClient()

        # Create a staff user for protected API requests.
        self.staff_user = get_user_model().objects.create_user(
            username="orderstaff",
            password="TestPassword123!",
            is_staff=True,
        )

        self.list_url = "/api/orders/"

        # Create an order for API detail tests.
        self.order = Order.objects.create(
            order_number="API-ORDER-001",
            customer_email="customer@example.com",
            total_amount=Decimal("250.00"),
        )

    def test_unauthenticated_user_cannot_list_orders(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_user_can_list_orders(self):
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_unauthenticated_user_cannot_view_order_detail(self):
        detail_url = f"/api/orders/{self.order.id}/"

        response = self.client.get(detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_user_can_view_order_detail(self):
        self.client.force_authenticate(user=self.staff_user)

        detail_url = f"/api/orders/{self.order.id}/"
        response = self.client.get(detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["order_number"],
            "API-ORDER-001",
        )

    def test_staff_user_receives_404_for_nonexistent_order(self):
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get("/api/orders/999999/")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )


@override_settings(
    PAYSTACK_SECRET_KEY="sk_test_fake-secret",
    PAYSTACK_CALLBACK_URL="https://shop.example.com/checkout",
)
class OrderPaymentFlowTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Rings")
        self.product = Product.objects.create(
            category=self.category,
            name="Test Ring",
            price=Decimal("250.00"),
            stock_quantity=5,
        )
        self.prepare_url = "/api/orders/prepare/"
        self.payload = {
            "customer_name": "Test Customer",
            "customer_email": "customer@example.com",
            "shipping_address": "12 Main Street",
            "shipping_city": "Accra",
            "shipping_postal_code": "00233",
            "shipping_country": "Ghana",
            "payment_method": "card",
            "items": [{"product": self.product.id, "quantity": 1}],
        }

    @patch(
        "orders.views.initialize_paystack_transaction",
        return_value="https://checkout.paystack.com/example",
    )
    def test_prepare_uses_server_price_and_creates_pending_order(self, initialize):
        response = self.client.post(self.prepare_url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], "250.00")
        self.assertEqual(self.product.stock_quantity, 5)
        order = Order.objects.get(order_number=response.data["order_number"])
        self.assertEqual(order.status, "pending")
        initialize.assert_called_once()
        self.assertEqual(initialize.call_args.kwargs["amount_minor"], 25000)

    @patch(
        "orders.views.initialize_paystack_transaction",
        return_value="https://checkout.paystack.com/example",
    )
    @patch("orders.views.verify_paystack_transaction")
    def test_payment_is_verified_before_order_is_paid_and_stock_changes(
        self,
        verify,
        _initialize,
    ):
        prepared = self.client.post(self.prepare_url, self.payload, format="json")
        reference = prepared.data["reference"]
        verify.return_value = {
            "status": "success",
            "currency": "GHS",
            "amount": 25000,
            "customer": {"email": "customer@example.com"},
        }

        response = self.client.post(
            "/api/orders/verify-payment/",
            {"reference": reference},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order = Order.objects.get(payment_reference=reference)
        self.assertEqual(order.status, "paid")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 4)

        repeated = self.client.post(
            "/api/orders/verify-payment/",
            {"reference": reference},
            format="json",
        )
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 4)
        verify.assert_called_once_with(reference)

    @patch(
        "orders.views.initialize_paystack_transaction",
        return_value="https://checkout.paystack.com/example",
    )
    @patch("orders.views.verify_paystack_transaction")
    def test_payment_with_wrong_amount_does_not_mark_order_paid(
        self,
        verify,
        _initialize,
    ):
        prepared = self.client.post(self.prepare_url, self.payload, format="json")
        reference = prepared.data["reference"]
        verify.return_value = {
            "status": "success",
            "currency": "GHS",
            "amount": 1,
            "customer": {"email": "customer@example.com"},
        }

        response = self.client.post(
            "/api/orders/verify-payment/",
            {"reference": reference},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.get(payment_reference=reference).status, "pending")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    @patch(
        "orders.views.initialize_paystack_transaction",
        return_value="https://checkout.paystack.com/example",
    )
    def test_promo_discount_is_recalculated_on_backend(self, initialize):
        payload = {
            **self.payload,
            "promo_code": "WELCOME10",
            "amount": "1.00",
        }

        response = self.client.post(self.prepare_url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], "225.00")
        self.assertEqual(initialize.call_args.kwargs["amount_minor"], 22500)

    @patch(
        "orders.views.initialize_paystack_transaction",
        return_value="https://checkout.paystack.com/example",
    )
    @patch("orders.views.verify_paystack_transaction")
    def test_signed_webhook_verifies_payment_and_updates_order(
        self,
        verify,
        _initialize,
    ):
        prepared = self.client.post(self.prepare_url, self.payload, format="json")
        reference = prepared.data["reference"]
        verify.return_value = {
            "status": "success",
            "currency": "GHS",
            "amount": 25000,
            "customer": {"email": "customer@example.com"},
        }
        body = json.dumps(
            {"event": "charge.success", "data": {"reference": reference}}
        ).encode("utf-8")
        signature = hmac.new(
            b"sk_test_fake-secret",
            body,
            hashlib.sha512,
        ).hexdigest()

        response = self.client.generic(
            "POST",
            "/api/orders/paystack/webhook/",
            body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Order.objects.get(payment_reference=reference).status,
            "paid",
        )

    @patch("orders.views.initialize_paystack_transaction")
    def test_prepare_requires_payment_configuration(self, initialize):
        with override_settings(PAYSTACK_SECRET_KEY="", PAYSTACK_CALLBACK_URL=""):
            response = self.client.post(
                self.prepare_url,
                self.payload,
                format="json",
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertEqual(Order.objects.count(), 0)
        initialize.assert_not_called()
