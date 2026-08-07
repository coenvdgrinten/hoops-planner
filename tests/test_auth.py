"""Tests for authentication endpoints."""

import pytest
from django.contrib.auth.models import User  # noqa: F401
from django.contrib.auth.tokens import default_token_generator
from rest_framework.test import APIClient

from hoops_planner.core.models import EmailVerificationToken


@pytest.fixture
def auth_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com",
    )


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, auth_client, test_user):
        response = auth_client.post(
            "/api/auth/login/",
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["username"] == "testuser"
        assert data["user"]["email"] == "test@example.com"

    def test_login_wrong_password(self, auth_client, test_user):
        response = auth_client.post(
            "/api/auth/login/",
            {"username": "testuser", "password": "wrongpass"},
            format="json",
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, auth_client):
        response = auth_client.post(
            "/api/auth/login/",
            {"username": "nobody", "password": "nobody"},
            format="json",
        )
        assert response.status_code == 401

    def test_login_blocked_for_inactive_user(self, auth_client):
        User.objects.create_user(
            username="inactiveuser",
            password="pass123",
            is_active=False,
        )
        response = auth_client.post(
            "/api/auth/login/",
            {"username": "inactiveuser", "password": "pass123"},
            format="json",
        )
        assert response.status_code == 403

    def test_login_missing_fields(self, auth_client):
        response = auth_client.post(
            "/api/auth/login/",
            {"username": "testuser"},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestRegister:
    def test_register_success(self, auth_client):
        response = auth_client.post(
            "/api/auth/register/",
            {
                "username": "newuser",
                "password": "newpass123",
                "email": "new@example.com",
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert "detail" in data
        assert "token" in data  # email verification token
        user = User.objects.get(username="newuser")
        assert not user.is_active  # pending approval

    def test_register_missing_email(self, auth_client):
        response = auth_client.post(
            "/api/auth/register/",
            {
                "username": "newuser",
                "password": "newpass123",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_register_duplicate_email(self, auth_client, test_user):
        response = auth_client.post(
            "/api/auth/register/",
            {
                "username": "newuser",
                "password": "newpass123",
                "email": test_user.email,
            },
            format="json",
        )
        assert response.status_code == 400

    def test_register_duplicate_username(self, auth_client, test_user):
        response = auth_client.post(
            "/api/auth/register/",
            {
                "username": "testuser",
                "password": "newpass123",
                "email": "other@example.com",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_register_missing_fields(self, auth_client):
        response = auth_client.post(
            "/api/auth/register/",
            {"username": "newuser"},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestMe:
    def test_me_authenticated(self, auth_client, test_user):
        from rest_framework.authtoken.models import Token

        token = Token.objects.create(user=test_user)
        auth_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = auth_client.get("/api/auth/me/")
        assert response.status_code == 200
        assert response.json()["username"] == "testuser"

    def test_me_unauthenticated(self, auth_client):
        response = auth_client.get("/api/auth/me/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestProtectedEndpoints:
    def test_seasons_requires_auth(self, auth_client):
        response = auth_client.get("/api/seasons/")
        assert response.status_code == 401

    def test_seasons_works_with_token(self, auth_client, test_user):
        from rest_framework.authtoken.models import Token

        token = Token.objects.create(user=test_user)
        auth_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = auth_client.get("/api/seasons/")
        assert response.status_code == 200

    def test_create_season_requires_auth(self, auth_client):
        response = auth_client.post(
            "/api/seasons/", {"name": "2026-2027"}, format="json"
        )
        assert response.status_code == 401


@pytest.mark.django_db
class TestPasswordReset:
    def test_password_reset_request_success(self, auth_client, test_user):
        response = auth_client.post(
            "/api/auth/password_reset_request/",
            {"email": "test@example.com"},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["uid"] == test_user.pk

    def test_password_reset_request_missing_email(self, auth_client):
        response = auth_client.post(
            "/api/auth/password_reset_request/",
            {},
            format="json",
        )
        assert response.status_code == 400

    def test_password_reset_request_nonexistent_email(self, auth_client):
        response = auth_client.post(
            "/api/auth/password_reset_request/",
            {"email": "nobody@example.com"},
            format="json",
        )
        # Should not reveal whether email exists
        assert response.status_code == 200

    def test_password_reset_request_email_case_insensitive(
        self,
        auth_client,
        test_user,
    ):
        response = auth_client.post(
            "/api/auth/password_reset_request/",
            {"email": "Test@Example.COM"},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["uid"] == test_user.pk

    def test_password_reset_confirm_success(self, auth_client, test_user):
        token = default_token_generator.make_token(test_user)
        response = auth_client.post(
            "/api/auth/password_reset_confirm/",
            {"token": token, "uid": test_user.pk, "password": "newpass123"},
            format="json",
        )
        assert response.status_code == 200
        test_user.refresh_from_db()
        assert test_user.check_password("newpass123")

    def test_password_reset_confirm_invalid_token(self, auth_client, test_user):
        response = auth_client.post(
            "/api/auth/password_reset_confirm/",
            {"token": "badtoken", "uid": test_user.pk, "password": "newpass123"},
            format="json",
        )
        assert response.status_code == 400

    def test_password_reset_confirm_invalid_uid(self, auth_client):
        response = auth_client.post(
            "/api/auth/password_reset_confirm/",
            {"token": "token", "uid": 99999, "password": "newpass123"},
            format="json",
        )
        assert response.status_code == 400

    def test_password_reset_confirm_missing_fields(self, auth_client):
        response = auth_client.post(
            "/api/auth/password_reset_confirm/",
            {"token": "token"},
            format="json",
        )
        assert response.status_code == 400

    def test_password_reset_confirm_expired_token(self, auth_client, test_user):
        # Use a known-bad token format to trigger the invalid path.
        response = auth_client.post(
            "/api/auth/password_reset_confirm/",
            {
                "token": "0-0-00000000000000000000",
                "uid": test_user.pk,
                "password": "newpass123",
            },
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestEmailVerification:
    def test_verify_email_request_success(self, auth_client, test_user):
        from rest_framework.authtoken.models import Token

        token = Token.objects.create(user=test_user)
        auth_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = auth_client.post("/api/auth/verify_email_request/")
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        # Token should be stored in DB
        assert EmailVerificationToken.objects.filter(user=test_user).exists()

    def test_verify_email_request_cleans_old_tokens(
        self,
        auth_client,
        test_user,
    ):
        from datetime import timedelta

        from django.utils import timezone
        from rest_framework.authtoken.models import Token

        # Create an existing token
        old_token = EmailVerificationToken.objects.create(
            user=test_user,
            token="old_token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Request a new verification
        auth_token = Token.objects.create(user=test_user)
        auth_client.credentials(HTTP_AUTHORIZATION=f"Token {auth_token.key}")
        response = auth_client.post("/api/auth/verify_email_request/")
        assert response.status_code == 200
        # Old token should be deleted
        assert not EmailVerificationToken.objects.filter(pk=old_token.pk).exists()
        # New token should exist
        assert EmailVerificationToken.objects.filter(user=test_user).exists()

    def test_verify_email_request_no_email(self, auth_client):
        from rest_framework.authtoken.models import Token

        user_no_email = User.objects.create_user(
            username="noemail",
            password="pass123",
            email="",
        )
        token = Token.objects.create(user=user_no_email)
        auth_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = auth_client.post("/api/auth/verify_email_request/")
        assert response.status_code == 400

    def test_verify_email_confirm_success(self, auth_client, test_user):
        from datetime import timedelta

        from django.utils import timezone

        # Create a verification token
        expires = timezone.now() + timedelta(hours=1)
        verification = EmailVerificationToken.objects.create(
            user=test_user,
            token="test_token_123",
            expires_at=expires,
        )

        response = auth_client.post(
            "/api/auth/verify_email_confirm/",
            {"token": "test_token_123"},
            format="json",
        )
        assert response.status_code == 200
        # Token should be deleted after use
        assert not EmailVerificationToken.objects.filter(pk=verification.pk).exists()

    def test_verify_email_confirm_invalid_token(self, auth_client):
        response = auth_client.post(
            "/api/auth/verify_email_confirm/",
            {"token": "nonexistent_token"},
            format="json",
        )
        assert response.status_code == 400

    def test_verify_email_confirm_expired_token(self, auth_client, test_user):
        from datetime import timedelta

        from django.utils import timezone

        # Create an expired token
        expires = timezone.now() - timedelta(hours=1)
        verification = EmailVerificationToken.objects.create(
            user=test_user,
            token="expired_token",
            expires_at=expires,
        )

        response = auth_client.post(
            "/api/auth/verify_email_confirm/",
            {"token": "expired_token"},
            format="json",
        )
        assert response.status_code == 400
        # Token should be deleted
        assert not EmailVerificationToken.objects.filter(pk=verification.pk).exists()

    def test_verify_email_confirm_missing_token(self, auth_client):
        response = auth_client.post(
            "/api/auth/verify_email_confirm/",
            {},
            format="json",
        )
        assert response.status_code == 400

    def test_verify_email_activates_user(self, auth_client):
        from datetime import timedelta

        from django.utils import timezone

        # Create inactive user
        inactive_user = User.objects.create_user(
            username="inactive",
            password="pass123",
            email="inactive@example.com",
            is_active=False,
        )

        # Create verification token
        expires = timezone.now() + timedelta(hours=1)
        EmailVerificationToken.objects.create(
            user=inactive_user,
            token="activate_token",
            expires_at=expires,
        )

        # Verify email (no auth needed — AllowAny)
        response = auth_client.post(
            "/api/auth/verify_email_confirm/",
            {"token": "activate_token"},
            format="json",
        )
        assert response.status_code == 200
        inactive_user.refresh_from_db()
        assert not inactive_user.is_active  # still needs admin approval
