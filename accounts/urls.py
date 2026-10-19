from django.urls import path

from .views import (
    AccountLoginView,
    AccountLogoutView,
    AccountProfileView,
    AccountRegistrationView,
    AccountResendVerificationView,
    AccountVerifyEmailView,
    CsrfTokenView,
)

urlpatterns = [
    path("csrf/", CsrfTokenView.as_view(), name="account-csrf"),
    path("register/", AccountRegistrationView.as_view(), name="account-register"),
    path("verify-email/", AccountVerifyEmailView.as_view(), name="account-verify-email"),
    path(
        "resend-verification/",
        AccountResendVerificationView.as_view(),
        name="account-resend-verification",
    ),
    path("login/", AccountLoginView.as_view(), name="account-login"),
    path("logout/", AccountLogoutView.as_view(), name="account-logout"),
    path("me/", AccountProfileView.as_view(), name="account-profile"),
]
