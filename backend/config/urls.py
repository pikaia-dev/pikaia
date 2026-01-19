"""
URL configuration for the backend.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from apps.accounts.webhooks import stytch_webhook
from apps.billing.webhooks import stripe_webhook

from .api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    # Webhooks - outside Django Ninja for raw request handling
    path("webhooks/stripe/", stripe_webhook, name="stripe-webhook"),
    path("webhooks/stytch/", stytch_webhook, name="stytch-webhook"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
