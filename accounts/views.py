import logging
import smtplib

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core import signing
from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.utils.http import urlencode
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import generics, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from orders.models import Order

from .serializers import (
    AccountEmailSerializer,
    AccountLoginSerializer,
    AccountRegistrationSerializer,
    AccountVerificationSerializer,
)


User = get_user_model()
logger = logging.getLogger(__name__)
VERIFICATION_SALT = "accounts.verify_email"
VERIFICATION_MAX_AGE = 60 * 60 * 24


class VerificationEmailDeliveryError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "We could not send your verification email. Please try again."
    default_code = "verification_email_failed"


def send_verification_email(user):
    token = signing.TimestampSigner(salt=VERIFICATION_SALT).sign(str(user.pk))
    url = f"{settings.ACCOUNT_VERIFICATION_URL}?{urlencode({'token': token})}"
    message = EmailMessage(
        subject="Verify your Deb Lucky account",
        body=(
            f"Hello {user.first_name},\n\n"
            "Verify your email address to activate your Deb Lucky account and "
            "access your order history:\n\n"
            f"{url}\n\n"
            "This link expires in 24 hours. If you did not create this account, "
            "you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    try:
        message.send(fail_silently=False)
    except (OSError, smtplib.SMTPException) as exc:
        logger.exception("Could not send account verification email for %s", user.pk)
        raise VerificationEmailDeliveryError() from exc


def account_data(user):
    orders = (
        Order.objects.filter(customer_email__iexact=user.email)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    return {
        "authenticated": True,
        "name": user.first_name,
        "email": user.email,
        "orders": [
            {
                "order_number": order.order_number,
                "status": order.status,
                "total_amount": str(order.total_amount),
                "created_at": order.created_at,
                "items": [
                    {
                        "product_name": item.product.name,
                        "quantity": item.quantity,
                        "unit_price": str(item.unit_price),
                    }
                    for item in order.items.all()
                ],
            }
            for order in orders
        ],
    }


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request, *args, **kwargs):
        return Response({"csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class AccountRegistrationView(generics.GenericAPIView):
    serializer_class = AccountRegistrationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "account_auth"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data["email"],
                    email=data["email"],
                    first_name=data["name"],
                    password=data["password"],
                    is_active=False,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"email": "An account with this email already exists."}
            ) from exc

        send_verification_email(user)
        return Response(
            {
                "detail": "Check your email for a verification link to activate your account.",
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
class AccountResendVerificationView(generics.GenericAPIView):
    serializer_class = AccountEmailSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "account_auth"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"],
            is_active=False,
        ).first()
        if user:
            send_verification_email(user)
        return Response(
            {"detail": "If an unverified account exists, a verification email has been sent."}
        )


@method_decorator(csrf_protect, name="dispatch")
class AccountVerifyEmailView(generics.GenericAPIView):
    serializer_class = AccountVerificationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "account_auth"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_id = signing.TimestampSigner(salt=VERIFICATION_SALT).unsign(
                serializer.validated_data["token"],
                max_age=VERIFICATION_MAX_AGE,
            )
            user = User.objects.get(pk=user_id)
        except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist) as exc:
            raise ValidationError(
                {"token": "This verification link is invalid or has expired."}
            ) from exc

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        login(request, user)
        return Response(account_data(user))


@method_decorator(csrf_protect, name="dispatch")
class AccountLoginView(generics.GenericAPIView):
    serializer_class = AccountLoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "account_auth"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = authenticate(
            request,
            username=data["email"].strip().lower(),
            password=data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Email or password is incorrect."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response(account_data(user))


class AccountLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountProfileView(APIView):
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method in {"GET", "HEAD", "OPTIONS"}:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({"authenticated": False})
        return Response(account_data(request.user))

    def patch(self, request, *args, **kwargs):
        name = request.data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError({"name": "Enter your name."})
        if len(name.strip()) > 150:
            raise ValidationError({"name": "Ensure this field has no more than 150 characters."})
        request.user.first_name = name.strip()
        request.user.save(update_fields=["first_name"])
        return Response(account_data(request.user))
