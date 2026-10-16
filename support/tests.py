from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase


@override_settings(
    CONTACT_EMAIL="store@example.com",
    DEFAULT_FROM_EMAIL="orders@example.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ContactViewTests(APITestCase):
    url = "/api/contact/"
    payload = {
        "name": "Customer",
        "email": "customer@example.com",
        "message": "I have a question about an order.",
    }

    def test_valid_message_is_sent_to_store_inbox(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["store@example.com"])
        self.assertEqual(mail.outbox[0].reply_to, ["customer@example.com"])
        self.assertEqual(mail.outbox[0].subject, "Store contact form submission")
        self.assertIn("Name: Customer", mail.outbox[0].body)
        self.assertIn(self.payload["message"], mail.outbox[0].body)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(
            self.url,
            {**self.payload, "email": "not-an-email"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(CONTACT_EMAIL="")
    def test_missing_inbox_configuration_is_reported(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertEqual(len(mail.outbox), 0)

    @patch("support.views.EmailMessage.send", side_effect=OSError("SMTP unavailable"))
    def test_delivery_failure_does_not_report_success(self, _send):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )
        self.assertEqual(
            response.data["detail"],
            "We could not send your message. Please try again later.",
        )
