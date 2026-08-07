"""Authentication views for login and registration."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from hoops_planner.core.models import EmailVerificationToken


def send_html_email(subject, to, context):
    """Send a styled HTML email with plain text fallback."""
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")

    # Plain text fallback
    text_content = (
        f"{context['title']}\n\n"
        f"{context['message']}\n\n"
        f"{context['button_url']}\n\n"
        f"{context['footer']}"
    )

    # HTML template
    html_content = f"""\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{context["title"]}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%); padding: 40px 40px 30px; text-align: center;">
                            <a href="https://github.com/coenvdgrinten/hoops-planner" style="text-decoration: none; display: inline-block;">
                                <div style="font-size: 48px; margin-bottom: 8px;">🏀</div>
                                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">Hoops Planner</h1>
                            </a>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 16px; color: #1a1a1a; font-size: 22px; font-weight: 600;">{context["title"]}</h2>
                            <p style="margin: 0 0 24px; color: #555555; font-size: 16px; line-height: 1.5;">{context["message"]}</p>
                            <table cellpadding="0" cellspacing="0" style="margin: 32px auto;">
                                <tr>
                                    <td style="border-radius: 8px; background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);">
                                        <a href="{context["button_url"]}" style="display: inline-block; padding: 14px 32px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600;">{context["button_text"]}</a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 24px 0 0; color: #888888; font-size: 14px; line-height: 1.5;">{context["footer"]}</p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; background-color: #f9f9f9; text-align: center; border-top: 1px solid #eeeeee;">
                            <p style="margin: 0; color: #999999; font-size: 12px;">&copy; {timezone.now().year} Hoops Planner</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)


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
            {
                "detail": "Account is pending approval. Please wait for an admin to approve your account."
            },
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

    send_html_email(
        subject="Verify Your Email — Hoops Planner",
        to=[email],
        context={
            "title": "Verify Your Email",
            "message": "Thanks for signing up! Click the button below to verify your email address.",
            "button_text": "Verify Email",
            "button_url": f"{settings.SITE_URL}/verify-email/{token_value}",
            "footer": "After verification, an admin will review and approve your account.",
        },
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
    send_html_email(
        subject="Reset Your Password — Hoops Planner",
        to=[email],
        context={
            "title": "Reset Your Password",
            "message": "Click the button below to reset your password.",
            "button_text": "Reset Password",
            "button_url": f"{settings.SITE_URL}/password-reset/{token}/{user.pk}",
            "footer": "If you didn't request this, you can safely ignore this email.",
        },
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
@permission_classes([IsAuthenticated])
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

    send_html_email(
        subject="Verify Your Email — Hoops Planner",
        to=[email],
        context={
            "title": "Verify Your Email",
            "message": "Click the button below to verify your email address.",
            "button_text": "Verify Email",
            "button_url": f"{settings.SITE_URL}/verify-email/{token_value}",
            "footer": "If you didn't request this, you can safely ignore this email.",
        },
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
    return Response(
        {"detail": "Email verified successfully. An admin will review your account."}
    )


@api_view(["GET"])
def pending_users(request):
    """List users awaiting admin approval (inactive + verified email)."""
    # Get inactive users who have verified their email (no pending tokens)
    pending = (
        User.objects.filter(
            is_active=False,
        )
        .exclude(
            pk__in=EmailVerificationToken.objects.values_list("user_id", flat=True)
        )
        .order_by("-date_joined")
    )

    return Response(
        [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "date_joined": u.date_joined,
            }
            for u in pending
        ]
    )


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
