"""Sync app configuration."""

from django.apps import AppConfig


class SyncConfig(AppConfig):
    """Django app configuration for sync engine."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sync"
    verbose_name = "Sync Engine"
