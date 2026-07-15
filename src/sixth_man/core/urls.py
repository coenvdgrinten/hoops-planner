"""URL patterns for the core API."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from sixth_man.core import auth_views
from sixth_man.core.views import (
    AvailabilityViewSet,
    GameViewSet,
    PlayerViewSet,
    SeasonViewSet,
    SettingsViewSet,
    TaskAssignmentViewSet,
    TaskViewSet,
    TeamViewSet,
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
    path("auth/register/", auth_views.register, name="register"),
    path("auth/me/", auth_views.me, name="me"),
] + router.urls
