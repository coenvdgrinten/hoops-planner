"""Custom permission classes."""

from rest_framework import permissions


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """Allow authenticated users full access. Allow read-only for unauthenticated."""

    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated


class IsAuthenticated(permissions.BasePermission):
    """Require authentication for any request."""

    def has_permission(self, request, view) -> bool:
        return request.user and request.user.is_authenticated
