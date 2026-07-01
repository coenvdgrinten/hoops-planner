"""URL patterns for the core API."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from sixth_man.core import auth_views
from sixth_man.core.views import (
    GameViewSet,
    PlayerViewSet,
    SeasonViewSet,
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

urlpatterns = [
    path("auth/login/", auth_views.login, name="login"),
    path("auth/register/", auth_views.register, name="register"),
    path("auth/me/", auth_views.me, name="me"),
] + router.urls
