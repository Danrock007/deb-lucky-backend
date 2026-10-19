from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


User = get_user_model()


class AccountRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(
        min_length=8,
        max_length=128,
        trim_whitespace=False,
        write_only=True,
    )

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate(self, attrs):
        user = User(
            username=attrs["email"],
            email=attrs["email"],
            first_name=attrs["name"],
        )
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class AccountLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(
        max_length=128,
        trim_whitespace=False,
        write_only=True,
    )


class AccountEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150, trim_whitespace=True)

    def validate_email(self, value):
        return value.strip().lower()


class AccountVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512, trim_whitespace=True)
