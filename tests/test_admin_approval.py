"""Tests for admin approval and email verification endpoints."""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from hoops_planner.core.models import EmailVerificationToken


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        username="admin", password="adminpass", email="admin@example.com"
    )


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    token = Token.objects.create(user=admin_user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def pending_user():
    """Create a user who verified email but is inactive."""
    user = User.objects.create_user(
        username="pendinguser",
        password="pass123",
        email="pending@example.com",
        is_active=False,
    )
    # No verification tokens = email already verified
    return user


@pytest.mark.django_db
class TestPendingUsers:
    def test_list_pending_users(self, admin_client, pending_user):
        response = admin_client.get("/api/auth/pending_users/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["username"] == "pendinguser"

    def test_list_pending_users_empty(self, admin_client):
        response = admin_client.get("/api/auth/pending_users/")
        assert response.status_code == 200
        assert response.json() == []

    def test_pending_excludes_unverified(self, admin_client):
        user = User.objects.create_user(
            username="unverified",
            password="pass123",
            email="unverified@example.com",
            is_active=False,
        )
        # Has a pending token = not yet verified
        EmailVerificationToken.objects.create(
            user=user,
            token="some_token",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        response = admin_client.get("/api/auth/pending_users/")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_pending_excludes_active_users(self, admin_client, pending_user):
        # Activate the user
        pending_user.is_active = True
        pending_user.save()
        response = admin_client.get("/api/auth/pending_users/")
        assert response.status_code == 200
        assert len(response.json()) == 0


@pytest.mark.django_db
class TestApproveUser:
    def test_approve_success(self, admin_client, pending_user):
        response = admin_client.post(
            "/api/auth/approve_user/",
            {"user_id": pending_user.pk},
            format="json",
        )
        assert response.status_code == 200
        pending_user.refresh_from_db()
        assert pending_user.is_active
        # Token should be created
        assert Token.objects.filter(user=pending_user).exists()

    def test_approve_missing_user_id(self, admin_client):
        response = admin_client.post(
            "/api/auth/approve_user/",
            {},
            format="json",
        )
        assert response.status_code == 400

    def test_approve_nonexistent_user(self, admin_client):
        response = admin_client.post(
            "/api/auth/approve_user/",
            {"user_id": 99999},
            format="json",
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestRejectUser:
    def test_reject_success(self, admin_client, pending_user):
        username = pending_user.username
        response = admin_client.delete(
            "/api/auth/reject_user/",
            {"user_id": pending_user.pk},
            format="json",
        )
        assert response.status_code == 200
        assert not User.objects.filter(username=username).exists()

    def test_reject_missing_user_id(self, admin_client):
        response = admin_client.delete(
            "/api/auth/reject_user/",
            {},
            format="json",
        )
        assert response.status_code == 400

    def test_reject_nonexistent_user(self, admin_client):
        response = admin_client.delete(
            "/api/auth/reject_user/",
            {"user_id": 99999},
            format="json",
        )
        assert response.status_code == 404

    def test_reject_active_user_fails(self, admin_client, admin_user):
        response = admin_client.delete(
            "/api/auth/reject_user/",
            {"user_id": admin_user.pk},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestVerifyEmailConfirm:
    def test_verify_valid_token(self):
        user = User.objects.create_user(
            username="verifyuser",
            password="pass123",
            email="verify@example.com",
            is_active=False,
        )
        token = EmailVerificationToken.objects.create(
            user=user,
            token="valid_token_123",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        client = APIClient()
        response = client.post(
            "/api/auth/verify_email_confirm/",
            {"token": "valid_token_123"},
            format="json",
        )
        assert response.status_code == 200
        # Token should be deleted after verification
        assert not EmailVerificationToken.objects.filter(
            user=user
        ).exists()

    def test_verify_invalid_token(self):
        client = APIClient()
        response = client.post(
            "/api/auth/verify_email_confirm/",
            {"token": "nonexistent_token"},
            format="json",
        )
        assert response.status_code == 400

    def test_verify_expired_token(self):
        user = User.objects.create_user(
            username="expireduser",
            password="pass123",
            email="expired@example.com",
            is_active=False,
        )
        EmailVerificationToken.objects.create(
            user=user,
            token="expired_token",
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        client = APIClient()
        response = client.post(
            "/api/auth/verify_email_confirm/",
            {"token": "expired_token"},
            format="json",
        )
        assert response.status_code == 400

    def test_verify_missing_token(self):
        client = APIClient()
        response = client.post(
            "/api/auth/verify_email_confirm/",
            {},
            format="json",
        )
        assert response.status_code == 400
