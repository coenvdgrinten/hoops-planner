"""Tests for authentication endpoints."""

import pytest
from django.contrib.auth.models import User  # noqa: F401
from rest_framework.test import APIClient


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
        assert "token" in data
        assert data["user"]["username"] == "newuser"
        assert User.objects.filter(username="newuser").exists()

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
