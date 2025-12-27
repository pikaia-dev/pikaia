"""Billing app configuration."""

from django.apps import AppConfig


class BillingConfig(AppConfig):
    """Configuration for billing app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.billing"
