"""URLs for Sixth Man."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("sixth_man.core.urls")),
]
