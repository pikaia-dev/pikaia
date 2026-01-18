"""
Stripe client configuration.

Provides a configured Stripe client for billing operations.
"""

from types import ModuleType

import stripe

from config.settings.base import settings

# API version required for billing_mode: flexible and confirmation_secret
STRIPE_API_VERSION = "2025-06-30.basil"

# Network configuration
# Stripe SDK has 80s default timeout which is reasonable for payment APIs.
# Retries are safe due to automatic idempotency key generation.
STRIPE_MAX_NETWORK_RETRIES = 2


def configure_stripe() -> None:
    """Configure Stripe API with settings."""
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = STRIPE_API_VERSION
    stripe.max_network_retries = STRIPE_MAX_NETWORK_RETRIES


def get_stripe() -> ModuleType:
    """
    Get configured Stripe module.

    Ensures Stripe is configured before use.
    """
    configure_stripe()
    return stripe
