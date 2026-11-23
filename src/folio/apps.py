"""Django application configuration for Folio."""

from django.apps import AppConfig


class FolioConfig(AppConfig):
    """Register Folio templates and static assets with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "folio"
    verbose_name = "Folio SK Design System"
