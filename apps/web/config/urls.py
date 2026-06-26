from django.contrib import admin
from django.urls import include, path

from core.views import discover_placeholder, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("", include("accounts.urls")),
    # Temporary placeholder; replaced by recipes.urls include in Task 4.
    path("", discover_placeholder, name="discover"),
]
