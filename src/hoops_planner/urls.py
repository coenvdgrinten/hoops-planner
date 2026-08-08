"""URLs for Hoops Planner."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularRedocView,
    SpectacularSwaggerView,
    SpectacularSwaggerAPIView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("hoops_planner.core.urls")),
    path("api/schema/", SpectacularSwaggerAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
