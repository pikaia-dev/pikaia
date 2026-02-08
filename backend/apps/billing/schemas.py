"""
Billing API schemas - request/response types for billing endpoints.
"""

from ninja import Schema


class CheckoutSessionRequest(Schema):
    """Request to create a Stripe Checkout session."""

    success_url: str
    cancel_url: str
    quantity: int | None = None  # If None, uses current member count


class CheckoutSessionResponse(Schema):
    """Response with Checkout session URL."""

    checkout_url: str


class PortalSessionRequest(Schema):
    """Request to create a Stripe Customer Portal session."""

    return_url: str


class PortalSessionResponse(Schema):
    """Response with Customer Portal URL."""

    portal_url: str


class SubscriptionResponse(Schema):
    """Current subscription status."""

    status: str  # 'active', 'past_due', 'canceled', 'none'
    quantity: int
    current_period_end: str | None
    cancel_at_period_end: bool
    stripe_customer_id: str | None
    trial_ends_at: str | None  # ISO timestamp
    is_trial_active: bool


class SubscriptionIntentRequest(Schema):
    """Request to create a subscription with payment intent."""

    quantity: int | None = None  # If None, uses current member count


class SubscriptionIntentResponse(Schema):
    """Response with client secret for Elements payment form."""

    client_secret: str
    subscription_id: str


class ConfirmSubscriptionRequest(Schema):
    """Request to confirm/sync subscription after payment."""

    subscription_id: str


class ConfirmSubscriptionResponse(Schema):
    """Response after confirming subscription."""

    is_active: bool


class InvoiceResponse(Schema):
    """Invoice data from Stripe."""

    id: str
    number: str | None
    status: str  # 'draft', 'open', 'paid', 'uncollectible', 'void'
    amount_due: int  # Amount in cents
    amount_paid: int  # Amount in cents
    currency: str  # e.g., 'usd'
    created: str  # ISO timestamp
    hosted_invoice_url: str | None  # URL to view invoice online
    invoice_pdf: str | None  # URL to download PDF
    period_start: str | None  # ISO timestamp
    period_end: str | None  # ISO timestamp


class InvoiceListResponse(Schema):
    """List of invoices with pagination info."""

    invoices: list[InvoiceResponse]
    has_more: bool
