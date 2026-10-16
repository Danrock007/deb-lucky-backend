import logging
import smtplib

from django.conf import settings
from django.core.mail import EmailMessage
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ContactMessageSerializer

logger = logging.getLogger(__name__)


class ContactDeliveryError(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "We could not send your message. Please try again later."
    default_code = "contact_delivery_failed"


class ContactConfigurationError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Contact form delivery is not configured."
    default_code = "contact_not_configured"


class ContactView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "contact"

    def post(self, request, *args, **kwargs):
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not settings.CONTACT_EMAIL:
            raise ContactConfigurationError()

        data = serializer.validated_data
        email = EmailMessage(
            subject="Store contact form submission",
            body=(
                f"Name: {data['name']}\n"
                f"Email: {data['email']}\n\n"
                f"{data['message']}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.CONTACT_EMAIL],
            reply_to=[data["email"]],
        )
        try:
            email.send(fail_silently=False)
        except (OSError, smtplib.SMTPException) as exc:
            logger.exception("Could not deliver storefront contact message")
            raise ContactDeliveryError() from exc

        return Response(
            {"detail": "Your message has been sent."},
            status=status.HTTP_200_OK,
        )
