import json
import urllib.parse
import urllib.request

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException


class PaymentGatewayError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Paystack could not process the payment request."
    default_code = "payment_gateway_error"


class PaymentConfigurationError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Online payments are not configured."
    default_code = "payment_configuration_error"


def _paystack_request(path, payload=None):
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaymentConfigurationError()

    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.paystack.co/{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        },
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PaymentGatewayError() from exc

    if not isinstance(result, dict) or not result.get("status"):
        raise PaymentGatewayError()
    data = result.get("data")
    if not isinstance(data, dict):
        raise PaymentGatewayError()
    return data


def initialize_paystack_transaction(
    *,
    email,
    amount_minor,
    reference,
    metadata,
    payment_method,
):
    if not settings.PAYSTACK_CALLBACK_URL:
        raise PaymentConfigurationError(
            "PAYSTACK_CALLBACK_URL must be configured before accepting payments."
        )
    data = _paystack_request(
        "transaction/initialize",
        {
            "email": email,
            "amount": amount_minor,
            "currency": "GHS",
            "reference": reference,
            "callback_url": settings.PAYSTACK_CALLBACK_URL,
            "metadata": metadata,
            "channels": ["card"] if payment_method == "card" else ["mobile_money"],
        },
    )
    authorization_url = data.get("authorization_url")
    if not authorization_url:
        raise PaymentGatewayError()
    return authorization_url


def verify_paystack_transaction(reference):
    encoded_reference = urllib.parse.quote(reference, safe="")
    return _paystack_request(f"transaction/verify/{encoded_reference}")
