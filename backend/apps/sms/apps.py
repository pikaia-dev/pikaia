"""
SMS app configuration.
"""

from django.apps import AppConfig


class SmsConfig(AppConfig):
    """Configuration for SMS app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sms"
    verbose_name = "SMS & OTP"
