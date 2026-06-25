"""URL patterns for the core API."""

from rest_framework.routers import DefaultRouter

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

urlpatterns = router.urls
