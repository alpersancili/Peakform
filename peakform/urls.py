"""URL configuration for the Peakform project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import favicon

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", favicon, name="favicon"),
    path("accounts/", include("accounts.urls")),
    path("nutrition/", include("nutrition.urls")),
    path("workouts/", include("workouts.urls")),
    path("badges/", include("motivation.urls")),
    path("community/", include("community.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
