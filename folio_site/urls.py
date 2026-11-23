"""URL configuration for the Folio reference gallery."""

from django.urls import include, path

urlpatterns = [
    path("", include("folio.urls")),
]
