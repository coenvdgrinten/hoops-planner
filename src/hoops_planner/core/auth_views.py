"""Authentication views for login and registration."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from hoops_planner.core.models import EmailVerificationToken


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """Authenticate with email/username and password, return token."""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    if not username or not password:
        return Response(
            {"detail": "Username/email and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Allow login with either username or email
    if "@" in username:
        user = User.objects.filter(email=username).first()
    else:
        user = User.objects.filter(username=username).first()
    if user is None or not user.check_password(password):
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)
    return Response(
        {
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
            },
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """Create a new user and return their token."""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")
    email = request.data.get("email", "").strip()

    if not username or not password:
        return Response(
            {"detail": "Username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {"detail": "A user with that username already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_user(username=username, password=password, email=email)
    token = Token.objects.create(user=user)

    return Response(
        {
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def me(request):
    """Return the current authenticated user."""
    return Response(
        {
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "is_staff": request.user.is_staff,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    """Send a password reset email to the given email address."""
    email = request.data.get("email", "").strip().lower()

    if not email:
        return Response(
            {"detail": "Email is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.filter(email=email).first()
    if user is None:
        # Don't reveal whether the email exists
        return Response({"detail": "If the email exists, a reset link has been sent."})

    token = default_token_generator.make_token(user)
    send_mail(
        subject="Hoops Planner — Password Reset",
        message=(
            f"Click the link below to reset your password:\n\n"
            f"{settings.SITE_URL}/password-reset/{token}/{user.pk}\n\n"
            "If you didn't request this, ignore this email."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
        recipient_list=[email],
        fail_silently=True,
    )
    # Also return the token so the frontend can use it directly in dev
    return Response(
        {
            "detail": "If the email exists, a reset link has been sent.",
            "token": token,
            "uid": user.pk,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """Reset password given a valid token and user id."""
    token = str(request.data.get("token", "")).strip()
    uid = str(request.data.get("uid", "")).strip()
    password = request.data.get("password", "")

    if not token or not uid or not password:
        return Response(
            {"detail": "Token, uid, and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError):
        return Response(
            {"detail": "Invalid reset link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not default_token_generator.check_token(user, token):
        return Response(
            {"detail": "Invalid or expired reset link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(password)
    user.save(update_fields=["password", "last_login"])

    return Response({"detail": "Password has been reset. You can now log in."})


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email_request(request):
    """Send an email verification link to the current user."""
    user = request.user
    email = user.email

    if not email:
        return Response(
            {"detail": "No email address on this account."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Delete any existing unexpired tokens
    EmailVerificationToken.objects.filter(user=user).delete()

    token_value = secrets.token_urlsafe(32)
    expires = timezone.now() + timedelta(hours=24)
    EmailVerificationToken.objects.create(
        user=user,
        token=token_value,
        expires_at=expires,
    )

    send_mail(
        subject="Hoops Planner — Verify Your Email",
        message=(
            f"Click the link below to verify your email address:\n\n"
            f"{settings.SITE_URL}/verify-email/{token_value}\n\n"
            "If you didn't request this, ignore this email."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
        recipient_list=[email],
        fail_silently=True,
    )

    # Return token for dev/frontend use
    return Response({"detail": "Verification email sent.", "token": token_value})


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email_confirm(request):
    """Verify email address given a valid token."""
    token_value = request.data.get("token", "").strip()

    if not token_value:
        return Response(
            {"detail": "Token is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        verification = EmailVerificationToken.objects.get(token=token_value)
    except EmailVerificationToken.DoesNotExist:
        return Response(
            {"detail": "Invalid or expired verification link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not verification.is_valid():
        verification.delete()
        return Response(
            {"detail": "Invalid or expired verification link."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Mark user as active if they weren't already
    if not verification.user.is_active:
        verification.user.is_active = True
        verification.user.save(update_fields=["is_active"])

    verification.delete()
    return Response({"detail": "Email verified successfully."})
