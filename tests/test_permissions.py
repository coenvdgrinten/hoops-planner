"""Tests for custom permission classes."""

import pytest
from rest_framework.test import APIRequestFactory

from hoops_planner.core.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)


@pytest.fixture
def factory():
    return APIRequestFactory()


@pytest.fixture
def dummy_view():
    """Dummy view class for permission testing."""

    class DummyView:
        pass

    return DummyView()


@pytest.mark.django_db
class TestIsAuthenticatedOrReadOnly:
    def test_get_allowed_without_auth(self, factory, dummy_view):
        request = factory.get("/api/test/")
        perm = IsAuthenticatedOrReadOnly()
        assert perm.has_permission(request, dummy_view) is True

    def test_post_denied_without_auth(self, factory, dummy_view):
        from django.contrib.auth.models import AnonymousUser

        request = factory.post("/api/test/")
        request.user = AnonymousUser()
        perm = IsAuthenticatedOrReadOnly()
        assert perm.has_permission(request, dummy_view) is False

    def test_put_denied_without_auth(self, factory, dummy_view):
        from django.contrib.auth.models import AnonymousUser

        request = factory.put("/api/test/")
        request.user = AnonymousUser()
        perm = IsAuthenticatedOrReadOnly()
        assert perm.has_permission(request, dummy_view) is False

    def test_delete_denied_without_auth(self, factory, dummy_view):
        from django.contrib.auth.models import AnonymousUser

        request = factory.delete("/api/test/")
        request.user = AnonymousUser()
        perm = IsAuthenticatedOrReadOnly()
        assert perm.has_permission(request, dummy_view) is False

    def test_get_allowed_with_auth(self, factory, dummy_view):
        from django.contrib.auth.models import User

        user = User.objects.create_user(
            username="testuser", password="pass123"
        )
        request = factory.get("/api/test/")
        request.user = user
        perm = IsAuthenticatedOrReadOnly()
        assert perm.has_permission(request, dummy_view) is True

    def test_post_allowed_with_auth(self, factory, dummy_view):
        from django.contrib.auth.models import User

        user = User.objects.create_user(
            username="testuser", password="pass123"
        )
        request = factory.post("/api/test/")
        request.user = user
        perm = IsAuthenticatedOrReadOnly()
        assert perm.has_permission(request, dummy_view) is True


@pytest.mark.django_db
class TestIsAuthenticated:
    def test_denied_without_auth(self, factory, dummy_view):
        from django.contrib.auth.models import AnonymousUser

        request = factory.get("/api/test/")
        request.user = AnonymousUser()
        perm = IsAuthenticated()
        assert perm.has_permission(request, dummy_view) is False

    def test_allowed_with_auth(self, factory, dummy_view):
        from django.contrib.auth.models import User

        user = User.objects.create_user(
            username="testuser", password="pass123"
        )
        request = factory.get("/api/test/")
        request.user = user
        perm = IsAuthenticated()
        assert perm.has_permission(request, dummy_view) is True
