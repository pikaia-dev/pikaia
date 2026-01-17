"""
Billing API endpoints.

Handles Stripe checkout, subscription management, and customer portal.
"""

from datetime import UTC, datetime

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.billing.models import Subscription
from apps.billing.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    ConfirmSubscriptionRequest,
    ConfirmSubscriptionResponse,
    InvoiceListResponse,
    InvoiceResponse,
    PortalSessionRequest,
    PortalSessionResponse,
    SubscriptionIntentRequest,
    SubscriptionIntentResponse,
    SubscriptionResponse,
)
from apps.billing.services import (
    create_checkout_session,
    create_customer_portal_session,
    create_subscription_intent,
    sync_subscription_from_stripe,
)
from apps.billing.stripe_client import get_stripe
from apps.core.logging import get_logger
from apps.core.schemas import ErrorResponse
from apps.core.security import BearerAuth, require_admin

logger = get_logger(__name__)

router = Router(tags=["billing"])
bearer_auth = BearerAuth()


@router.post(
    "/checkout",
    response={200: CheckoutSessionResponse, 401: ErrorResponse, 403: ErrorResponse},
    auth=bearer_auth,
    operation_id="createCheckoutSession",
    summary="Create Stripe Checkout session",
)
@require_admin
def create_checkout(
    request: HttpRequest, payload: CheckoutSessionRequest
) -> CheckoutSessionResponse:
    """
    Create a Stripe Checkout session for subscribing.

    Admin only. Returns URL to redirect user to Stripe Checkout.
    """
    org = request.auth_organization

    # Check if already subscribed
    try:
        existing = org.subscription
        if existing.is_active:
            raise HttpError(400, "Already subscribed. Use the customer portal to manage.")
    except Subscription.DoesNotExist:
        pass  # No subscription yet - proceed with creation

    # Determine quantity
    if payload.quantity:
        quantity = payload.quantity
    else:
        # Use current member count
        from apps.accounts.models import Member

        quantity = Member.objects.filter(organization=org).count()
        if quantity < 1:
            quantity = 1

    try:
        checkout_url = create_checkout_session(
            org=org,
            quantity=quantity,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
    except Exception:
        logger.exception("checkout_session_creation_failed")
        raise HttpError(500, "Failed to create checkout session")

    return CheckoutSessionResponse(checkout_url=checkout_url)


@router.post(
    "/portal",
    response={200: PortalSessionResponse, 401: ErrorResponse, 403: ErrorResponse},
    auth=bearer_auth,
    operation_id="createPortalSession",
    summary="Create Stripe Customer Portal session",
)
@require_admin
def create_portal(request: HttpRequest, payload: PortalSessionRequest) -> PortalSessionResponse:
    """
    Create a Stripe Customer Portal session.

    Admin only. Returns URL to redirect user to manage their subscription.
    """
    org = request.auth_organization

    if not org.stripe_customer_id:
        raise HttpError(400, "No billing account set up")

    try:
        portal_url = create_customer_portal_session(
            org=org,
            return_url=payload.return_url,
        )
    except Exception:
        logger.exception("portal_session_creation_failed")
        raise HttpError(500, "Failed to create portal session")

    return PortalSessionResponse(portal_url=portal_url)


@router.get(
    "/subscription",
    response={200: SubscriptionResponse, 401: ErrorResponse},
    auth=bearer_auth,
    operation_id="getSubscription",
    summary="Get current subscription status",
)
def get_subscription(request: HttpRequest) -> SubscriptionResponse:
    """
    Get current subscription status.

    Returns subscription details or 'none' status if not subscribed.
    """
    if not hasattr(request, "auth_organization") or request.auth_organization is None:
        raise HttpError(401, "Not authenticated")

    org = request.auth_organization

    try:
        subscription = org.subscription
        return SubscriptionResponse(
            status=subscription.status,
            quantity=subscription.quantity,
            current_period_end=subscription.current_period_end.isoformat(),
            cancel_at_period_end=subscription.cancel_at_period_end,
            stripe_customer_id=org.stripe_customer_id,
        )
    except Subscription.DoesNotExist:
        # No subscription
        from apps.accounts.models import Member

        member_count = Member.objects.filter(organization=org).count()
        return SubscriptionResponse(
            status="none",
            quantity=member_count or 1,
            current_period_end=None,
            cancel_at_period_end=False,
            stripe_customer_id=org.stripe_customer_id,
        )


@router.post(
    "/subscription-intent",
    response={
        200: SubscriptionIntentResponse,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="createSubscriptionIntent",
    summary="Create subscription intent for Elements payment",
)
@require_admin
def create_subscription_intent_endpoint(
    request: HttpRequest, payload: SubscriptionIntentRequest
) -> SubscriptionIntentResponse:
    """
    Create a subscription with an incomplete payment intent.

    Admin only. Returns client_secret for PaymentElement.
    Use this for embedded Stripe Elements payment flow.
    """
    org = request.auth_organization

    # Check if already subscribed
    try:
        existing = org.subscription
        if existing.is_active:
            raise HttpError(400, "Already subscribed. Use the customer portal to manage.")
    except Subscription.DoesNotExist:
        pass  # No subscription yet - proceed with creation

    # Determine quantity
    if payload.quantity:
        quantity = payload.quantity
    else:
        from apps.accounts.models import Member

        quantity = Member.objects.filter(organization=org).count()
        if quantity < 1:
            quantity = 1

    try:
        client_secret, subscription_id = create_subscription_intent(
            org=org,
            quantity=quantity,
        )
    except Exception:
        logger.exception("subscription_intent_creation_failed")
        raise HttpError(500, "Failed to create subscription intent")

    return SubscriptionIntentResponse(
        client_secret=client_secret,
        subscription_id=subscription_id,
    )


@router.post(
    "/confirm-subscription",
    response={
        200: ConfirmSubscriptionResponse,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
    },
    auth=bearer_auth,
    operation_id="confirmSubscription",
    summary="Confirm subscription after payment",
)
@require_admin
def confirm_subscription_endpoint(
    request: HttpRequest, payload: ConfirmSubscriptionRequest
) -> ConfirmSubscriptionResponse:
    """
    Sync subscription status from Stripe after payment.

    Call this after confirmPayment succeeds to update local database.
    Useful for development without Stripe CLI webhooks.
    """

    try:
        is_active = sync_subscription_from_stripe(payload.subscription_id)
    except Exception:
        logger.exception("subscription_confirmation_failed")
        raise HttpError(500, "Failed to confirm subscription")

    return ConfirmSubscriptionResponse(is_active=is_active)


@router.get(
    "/invoices",
    response={200: InvoiceListResponse, 401: ErrorResponse, 403: ErrorResponse},
    auth=bearer_auth,
    operation_id="listInvoices",
    summary="List organization invoices",
)
@require_admin
def list_invoices(
    request: HttpRequest,
    limit: int = 12,
    starting_after: str | None = None,
) -> InvoiceListResponse:
    """
    List invoices from Stripe for the current organization.

    Admin only. Returns invoices sorted by date (newest first).
    Use starting_after with an invoice ID for pagination.
    """
    if not hasattr(request, "auth_organization") or request.auth_organization is None:
        raise HttpError(401, "Not authenticated")

    org = request.auth_organization

    if not org.stripe_customer_id:
        return InvoiceListResponse(invoices=[], has_more=False)

    try:
        stripe = get_stripe()

        # Build params for Stripe API
        params: dict = {
            "customer": org.stripe_customer_id,
            "limit": min(limit, 100),  # Stripe max is 100
        }
        if starting_after:
            params["starting_after"] = starting_after

        # Fetch invoices from Stripe
        invoice_list = stripe.Invoice.list(**params)

        invoices = []
        for inv in invoice_list.data:
            # Convert Unix timestamps to ISO format
            created = datetime.fromtimestamp(inv.created, tz=UTC).isoformat()
            period_start = (
                datetime.fromtimestamp(inv.period_start, tz=UTC).isoformat()
                if inv.period_start
                else None
            )
            period_end = (
                datetime.fromtimestamp(inv.period_end, tz=UTC).isoformat()
                if inv.period_end
                else None
            )

            invoices.append(
                InvoiceResponse(
                    id=inv.id,
                    number=inv.number,
                    status=inv.status or "unknown",
                    amount_due=inv.amount_due,
                    amount_paid=inv.amount_paid,
                    currency=inv.currency,
                    created=created,
                    hosted_invoice_url=inv.hosted_invoice_url,
                    invoice_pdf=inv.invoice_pdf,
                    period_start=period_start,
                    period_end=period_end,
                )
            )

        return InvoiceListResponse(
            invoices=invoices,
            has_more=invoice_list.has_more,
        )

    except Exception:
        logger.exception("invoice_list_failed")
        raise HttpError(500, "Failed to retrieve invoices")
