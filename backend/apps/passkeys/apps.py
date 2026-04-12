"""Passkeys app configuration."""

from django.apps import AppConfig


class PasskeysConfig(AppConfig):
    """Configuration for passkeys app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.passkeys"
