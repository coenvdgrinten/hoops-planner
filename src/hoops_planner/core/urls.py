"""URL patterns for the core API."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from hoops_planner.core import auth_views
from hoops_planner.core.views import (
    AvailabilityViewSet,
    GameViewSet,
    PlayerViewSet,
    SeasonViewSet,
    SettingsViewSet,
    TaskAssignmentViewSet,
    TaskViewSet,
    TeamViewSet,
    game_ics,
    seed,
)

router = DefaultRouter()
router.register(r"seasons", SeasonViewSet)
router.register(r"teams", TeamViewSet)
router.register(r"players", PlayerViewSet)
router.register(r"games", GameViewSet, basename="games")
router.register(r"tasks", TaskViewSet)
router.register(r"assignments", TaskAssignmentViewSet)
router.register(r"settings", SettingsViewSet, basename="settings")
router.register(r"availability", AvailabilityViewSet, basename="availability")

urlpatterns = [
    path("auth/login/", auth_views.login, name="login"),
    path("auth/logout/", auth_views.logout, name="logout"),
    path("auth/register/", auth_views.register, name="register"),
    path("auth/me/", auth_views.me, name="me"),
    path(
        "auth/password_reset_request/",
        auth_views.password_reset_request,
        name="password_reset_request",
    ),
    path(
        "auth/password_reset_confirm/",
        auth_views.password_reset_confirm,
        name="password_reset_confirm",
    ),
    path(
        "auth/verify_email_request/",
        auth_views.verify_email_request,
        name="verify_email_request",
    ),
    path(
        "auth/verify_email_confirm/",
        auth_views.verify_email_confirm,
        name="verify_email_confirm",
    ),
    path("auth/pending_users/", auth_views.pending_users, name="pending_users"),
    path("auth/approve_user/", auth_views.approve_user, name="approve_user"),
    path("auth/reject_user/", auth_views.reject_user, name="reject_user"),
    path("game_ics/", game_ics, name="game_ics"),
    # Development-only: seed demo data (admin + DEBUG). Used by the e2e fixture.
    path("seed/", seed, name="seed"),
] + router.urls
