from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from catalog.models import Category, Product
from orders.models import Order, OrderItem


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CustomerAccountApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.csrf_client = APIClient(enforce_csrf_checks=True)
        self.registration_url = "/api/accounts/register/"
        self.login_url = "/api/accounts/login/"
        self.profile_url = "/api/accounts/me/"
        self.registration_data = {
            "name": "Test Customer",
            "email": "Customer@example.com",
            "password": "Violet-River-Quartz-91!",
        }

    def test_registration_creates_account_and_starts_session(self):
        response = self.client.post(
            self.registration_url,
            self.registration_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("verification link", response.data["detail"])
        self.assertEqual(response.data["email"], "customer@example.com")
        user = get_user_model().objects.get(email="customer@example.com")
        self.assertTrue(user.check_password(self.registration_data["password"]))
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        profile = self.client.get(self.profile_url)
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertFalse(profile.data["authenticated"])

        verification_url = next(
            line for line in mail.outbox[0].body.splitlines()
            if line.startswith("http")
        )
        token = parse_qs(urlparse(verification_url).query)["token"][0]
        verified = self.client.post(
            "/api/accounts/verify-email/",
            {"token": token},
            format="json",
        )
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.assertTrue(get_user_model().objects.get(pk=user.pk).is_active)
        self.assertEqual(self.client.get(self.profile_url).status_code, status.HTTP_200_OK)
        repeated_verification = self.client.post(
            "/api/accounts/verify-email/",
            {"token": token},
            format="json",
        )
        self.assertEqual(repeated_verification.status_code, status.HTTP_200_OK)

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        get_user_model().objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="Existing-Password1!",
        )

        response = self.client.post(
            self.registration_url,
            self.registration_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            self.registration_url,
            {**self.registration_data, "password": "password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            get_user_model().objects.filter(email="customer@example.com").exists()
        )

    def test_login_and_logout_manage_customer_session(self):
        get_user_model().objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            first_name="Test Customer",
            password=self.registration_data["password"],
            is_active=True,
        )

        response = self.client.post(
            self.login_url,
            {
                "email": "CUSTOMER@example.com",
                "password": self.registration_data["password"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(self.profile_url).status_code, status.HTTP_200_OK)

        logout_response = self.client.post("/api/accounts/logout/")

        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.client.get(self.profile_url).data["authenticated"])

    def test_login_uses_generic_error_for_invalid_credentials(self):
        response = self.client.post(
            self.login_url,
            {"email": "customer@example.com", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            str(response.data["detail"]),
            "Email or password is incorrect.",
        )

    def test_profile_updates_name_and_returns_only_matching_email_orders(self):
        user = get_user_model().objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password=self.registration_data["password"],
            is_active=True,
        )
        self.client.force_authenticate(user=user)
        category = Category.objects.create(name="Rings")
        product = Product.objects.create(
            category=category,
            name="Gold Ring",
            price=Decimal("25.00"),
            stock_quantity=1,
        )
        order = Order.objects.create(
            order_number="DLJ-CUSTOMER-1",
            customer_name="Test Customer",
            customer_email="CUSTOMER@example.com",
            total_amount=Decimal("25.00"),
            status="paid",
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            unit_price=Decimal("25.00"),
        )
        Order.objects.create(
            order_number="DLJ-OTHER-1",
            customer_email="other@example.com",
            total_amount=Decimal("99.00"),
        )

        response = self.client.patch(
            self.profile_url,
            {"name": "Updated Customer"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Customer")
        self.assertEqual(len(response.data["orders"]), 1)
        self.assertEqual(response.data["orders"][0]["order_number"], "DLJ-CUSTOMER-1")
        self.assertEqual(
            response.data["orders"][0]["items"][0]["product_name"],
            "Gold Ring",
        )

    def test_resend_verification_does_not_disclose_account_existence(self):
        response = self.client.post(
            "/api/accounts/resend-verification/",
            {"email": "unknown@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        get_user_model().objects.create_user(
            username="pending@example.com",
            email="pending@example.com",
            password="Existing-Password1!",
            is_active=False,
        )
        response = self.client.post(
            "/api/accounts/resend-verification/",
            {"email": "PENDING@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_expired_or_invalid_verification_token_is_rejected(self):
        response = self.client.post(
            "/api/accounts/verify-email/",
            {"token": "not-a-valid-token"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authenticated_state_changing_requests_require_csrf(self):
        response = self.csrf_client.post(
            self.registration_url,
            self.registration_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        csrf_response = self.csrf_client.get("/api/accounts/csrf/")
        self.assertEqual(csrf_response.status_code, status.HTTP_200_OK)
        self.csrf_client.credentials(
            HTTP_X_CSRFTOKEN=csrf_response.data["csrf_token"]
        )
        registered = self.csrf_client.post(
            self.registration_url,
            self.registration_data,
            format="json",
        )
        self.assertEqual(registered.status_code, status.HTTP_201_CREATED)

        verification_url = next(
            line for line in mail.outbox[-1].body.splitlines()
            if line.startswith("http")
        )
        token = parse_qs(urlparse(verification_url).query)["token"][0]
        verified = self.csrf_client.post(
            "/api/accounts/verify-email/",
            {"token": token},
            format="json",
        )
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.csrf_client.get("/api/accounts/csrf/")
        self.csrf_client.credentials()
        no_csrf_logout = self.csrf_client.post("/api/accounts/logout/")
        self.assertEqual(no_csrf_logout.status_code, status.HTTP_403_FORBIDDEN)
