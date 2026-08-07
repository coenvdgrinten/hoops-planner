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

    if not user.is_active:
        return Response(
            {"detail": "Account is pending approval. Please wait for an admin to approve your account."},
            status=status.HTTP_403_FORBIDDEN,
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
    """Create a new user pending email verification and admin approval."""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")
    email = request.data.get("email", "").strip()

    if not username or not password or not email:
        return Response(
            {"detail": "Username, password, and email are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {"detail": "A user with that username already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email=email).exists():
        return Response(
            {"detail": "A user with that email already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Create user as inactive — needs email verification + admin approval
    user = User.objects.create_user(
        username=username, password=password, email=email, is_active=False
    )

    # Send verification email
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
            "After verification, an admin will review and approve your account."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
        recipient_list=[email],
        fail_silently=True,
    )

    return Response(
        {
            "detail": "Account created. Please check your email to verify your address. An admin will then review your account.",
            "token": token_value,
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

    # Email verified — user still needs admin approval
    verification.delete()
    return Response({"detail": "Email verified successfully. An admin will review your account."})


@api_view(["GET"])
def pending_users(request):
    """List users awaiting admin approval (inactive + verified email)."""
    # Get inactive users who have verified their email (no pending tokens)
    pending = User.objects.filter(
        is_active=False,
    ).exclude(
        pk__in=EmailVerificationToken.objects.values_list("user_id", flat=True)
    ).order_by("-date_joined")

    return Response([
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "date_joined": u.date_joined,
        }
        for u in pending
    ])


@api_view(["POST"])
def approve_user(request):
    """Approve a pending user (admin only)."""
    user_id = request.data.get("user_id")
    if not user_id:
        return Response(
            {"detail": "user_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response(
            {"detail": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user.is_active = True
    user.save(update_fields=["is_active"])

    # Create auth token so they can log in
    Token.objects.get_or_create(user=user)

    return Response({"detail": f"User {user.username} has been approved."})


@api_view(["DELETE"])
def reject_user(request):
    """Reject and delete a pending user (admin only)."""
    user_id = request.data.get("user_id")
    if not user_id:
        return Response(
            {"detail": "user_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response(
            {"detail": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if user.is_active:
        return Response(
            {"detail": "User is already active."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    username = user.username
    user.delete()

    return Response({"detail": f"User {username} has been rejected."})
