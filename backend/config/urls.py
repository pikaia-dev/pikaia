"""
URL configuration for Tango backend.
"""

from django.contrib import admin
from django.urls import path

from apps.billing.webhooks import stripe_webhook

from .api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    # Stripe webhook - outside Django Ninja for raw request handling
    path("webhooks/stripe/", stripe_webhook, name="stripe-webhook"),
]
