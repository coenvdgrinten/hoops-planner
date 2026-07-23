"""URLs for Hoops Planner."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("hoops_planner.core.urls")),
]
