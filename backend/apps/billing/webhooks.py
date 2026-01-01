"""
Stripe webhook handler.

Handles incoming webhooks from Stripe for subscription events.
This is a separate view (not Django Ninja) for raw request handling
needed to verify Stripe signatures.
"""

import json
import logging

import stripe
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.billing.services import (
    handle_subscription_created,
    handle_subscription_deleted,
    handle_subscription_updated,
)
from apps.billing.stripe_client import get_stripe
from config.settings.base import settings

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    """
    Handle Stripe webhook events.

    Verifies signature and dispatches to appropriate handler.
    """
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        logger.warning("Missing Stripe-Signature header")
        return HttpResponse(status=400)

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return HttpResponse(status=500)

    # Verify signature
    get_stripe()  # Ensure Stripe is configured
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError as e:
        logger.warning("Invalid payload: %s", e)
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError as e:
        logger.warning("Invalid signature: %s", e)
        return HttpResponse(status=400)

    # Log event for debugging
    logger.info("Received Stripe event: %s", event["type"])

    # Dispatch to handlers
    try:
        match event["type"]:
            case "checkout.session.completed":
                # Get the subscription from the session
                session = event["data"]["object"]
                if session.get("subscription"):
                    # Fetch full subscription details
                    subscription = stripe.Subscription.retrieve(session["subscription"])
                    handle_subscription_created(subscription)

            case "customer.subscription.created":
                handle_subscription_created(event["data"]["object"])

            case "customer.subscription.updated":
                handle_subscription_updated(event["data"]["object"])

            case "customer.subscription.deleted":
                handle_subscription_deleted(event["data"]["object"])

            case "invoice.paid":
                # Log successful payment
                invoice = event["data"]["object"]
                logger.info(
                    "Invoice paid: %s for customer %s",
                    invoice["id"],
                    invoice["customer"],
                )

            case "invoice.payment_failed":
                # Log failed payment - could trigger email notification
                invoice = event["data"]["object"]
                logger.warning(
                    "Invoice payment failed: %s for customer %s",
                    invoice["id"],
                    invoice["customer"],
                )

            case _:
                logger.debug("Unhandled event type: %s", event["type"])

    except Exception as e:
        logger.exception("Error handling webhook: %s", e)
        # Return 200 to acknowledge receipt even on errors
        # Stripe will retry, and we don't want infinite retries

    return HttpResponse(status=200)
