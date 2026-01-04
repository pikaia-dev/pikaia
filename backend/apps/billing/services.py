"""
Billing services - Stripe integration logic.

All Stripe API calls are isolated here for testability.
External calls must NOT be inside database transactions.
"""

import logging
from datetime import datetime, timedelta, timezone


from apps.billing.models import Subscription
from apps.billing.stripe_client import get_stripe
from apps.events.services import publish_event
from apps.organizations.models import Organization
from config.settings.base import settings

logger = logging.getLogger(__name__)


def get_or_create_stripe_customer(org: Organization) -> str:
    """
    Get or create a Stripe Customer for the organization.

    Returns the Stripe customer ID.
    """
    if org.stripe_customer_id:
        return org.stripe_customer_id

    stripe = get_stripe()

    # Determine email for Stripe customer
    if org.use_billing_email and org.billing_email:
        email = org.billing_email
    else:
        # Fall back to first admin's email
        from apps.accounts.models import Member

        admin = Member.objects.filter(organization=org, role="admin").select_related("user").first()
        email = admin.user.email if admin else None

    # Build customer data
    customer_data: dict = {
        "name": org.billing_name or org.name,
        "metadata": {
            "organization_id": str(org.id),
            "stytch_org_id": org.stytch_org_id,
        },
    }

    if email:
        customer_data["email"] = email

    # Add address if available
    if org.billing_country:
        customer_data["address"] = {
            "line1": org.billing_address_line1,
            "line2": org.billing_address_line2,
            "city": org.billing_city,
            "state": org.billing_state,
            "postal_code": org.billing_postal_code,
            "country": org.billing_country,
        }

    # Add VAT ID if available (EU tax exempt handling)
    # Note: tax_id_data must be added separately after customer creation

    customer = stripe.Customer.create(**customer_data)

    # Update org with Stripe customer ID
    org.stripe_customer_id = customer.id
    org.save(update_fields=["stripe_customer_id", "updated_at"])

    # Add VAT ID if present
    if org.vat_id:
        try:
            # Determine tax ID type based on country
            tax_id_type = _get_tax_id_type(org.billing_country, org.vat_id)
            if tax_id_type:
                stripe.Customer.create_tax_id(
                    customer.id,
                    type=tax_id_type,
                    value=org.vat_id,
                )
        except stripe.StripeError as e:
            logger.warning("Failed to add VAT ID to Stripe customer: %s", e)

    logger.info("Created Stripe customer %s for org %s", customer.id, org.id)
    return customer.id


def sync_billing_to_stripe(org: Organization) -> None:
    """
    Sync billing info (address, VAT, email) to Stripe.

    Call this after billing info is updated locally.
    """
    if not org.stripe_customer_id:
        return

    stripe = get_stripe()

    # Determine email
    if org.use_billing_email and org.billing_email:
        email = org.billing_email
    else:
        from apps.accounts.models import Member

        admin = Member.objects.filter(organization=org, role="admin").select_related("user").first()
        email = admin.user.email if admin else None

    # Build update data
    update_data: dict = {
        "name": org.billing_name or org.name,
    }

    if email:
        update_data["email"] = email

    if org.billing_country:
        update_data["address"] = {
            "line1": org.billing_address_line1,
            "line2": org.billing_address_line2,
            "city": org.billing_city,
            "state": org.billing_state,
            "postal_code": org.billing_postal_code,
            "country": org.billing_country,
        }

    try:
        stripe.Customer.modify(org.stripe_customer_id, **update_data)
        logger.info("Synced billing info to Stripe for org %s", org.id)
    except stripe.StripeError as e:
        logger.error("Failed to sync billing to Stripe: %s", e)
        raise


def create_checkout_session(
    org: Organization,
    quantity: int,
    success_url: str,
    cancel_url: str,
) -> str:
    """
    Create a Stripe Checkout Session for a new subscription.

    Returns the checkout session URL.
    """
    stripe = get_stripe()

    # Ensure customer exists
    customer_id = get_or_create_stripe_customer(org)

    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[
            {
                "price": settings.STRIPE_PRICE_ID,
                "quantity": quantity,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        subscription_data={
            "metadata": {
                "organization_id": str(org.id),
            },
        },
        # Collect billing address if not already set
        billing_address_collection="auto" if not org.billing_country else "auto",
        # Allow updating quantity later
        allow_promotion_codes=True,
        # Automatic tax collection (if configured in Stripe)
        automatic_tax={"enabled": True},
    )

    logger.info("Created checkout session %s for org %s", session.id, org.id)
    return session.url


def create_subscription_intent(
    org: Organization,
    quantity: int,
) -> tuple[str, str]:
    """
    Create a subscription with incomplete status for Elements payment.

    Returns (client_secret, subscription_id) for the PaymentElement.
    """
    stripe = get_stripe()

    # Ensure customer exists
    customer_id = get_or_create_stripe_customer(org)

    # Create subscription with payment_behavior=default_incomplete
    # This creates the subscription but doesn't charge until payment confirmed
    # Note: Stripe API 2025+ uses confirmation_secret instead of payment_intent
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[
            {
                "price": settings.STRIPE_PRICE_ID,
                "quantity": quantity,
            }
        ],
        payment_behavior="default_incomplete",
        payment_settings={"save_default_payment_method": "on_subscription"},
        expand=["latest_invoice.confirmation_secret"],
        metadata={
            "organization_id": str(org.id),
        },
    )

    # Get client secret from confirmation_secret (Stripe API 2025+)
    client_secret = subscription.latest_invoice.confirmation_secret.client_secret

    logger.info(
        "Created subscription intent %s for org %s",
        subscription.id,
        org.id,
    )

    return client_secret, subscription.id


def sync_subscription_from_stripe(subscription_id: str) -> bool:
    """
    Sync subscription status from Stripe.

    Fetches the subscription directly from Stripe and updates local database.
    Useful for development without webhooks (no Stripe CLI needed).

    Returns True if subscription is now active.
    """
    stripe = get_stripe()

    try:
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
    except stripe.StripeError as e:
        logger.error("Failed to retrieve subscription %s: %s", subscription_id, e)
        raise

    # Use the existing handler to sync the subscription
    # This handles all the parsing and database updates
    handle_subscription_created(stripe_sub)

    # Return whether subscription is now active
    return stripe_sub.status in ("active", "trialing")


def sync_subscription_quantity(org: Organization) -> None:
    """
    Sync subscription quantity to match active member count.

    Call this after members are added/removed.
    Uses proration for fair billing.
    """
    try:
        subscription = org.subscription
    except Subscription.DoesNotExist:
        # No subscription yet - nothing to sync
        return

    if not subscription.is_active:
        return

    # Count active members
    from apps.accounts.models import Member

    member_count = Member.objects.filter(organization=org).count()

    if member_count == subscription.quantity:
        return  # Already in sync

    if member_count < 1:
        member_count = 1  # Minimum 1 seat

    stripe = get_stripe()

    try:
        # Get subscription items
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        item_id = stripe_sub["items"]["data"][0]["id"]

        # Update quantity with proration
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{"id": item_id, "quantity": member_count}],
            proration_behavior="create_prorations",
        )

        # Update local record
        subscription.quantity = member_count
        subscription.save(update_fields=["quantity", "updated_at"])

        logger.info(
            "Synced subscription quantity to %d for org %s",
            member_count,
            org.id,
        )
    except stripe.StripeError as e:
        logger.error("Failed to sync subscription quantity: %s", e)
        raise


def create_customer_portal_session(org: Organization, return_url: str) -> str:
    """
    Create a Stripe Customer Portal session.

    Returns the portal URL.
    """
    if not org.stripe_customer_id:
        raise ValueError("Organization has no Stripe customer")

    stripe = get_stripe()

    session = stripe.billing_portal.Session.create(
        customer=org.stripe_customer_id,
        return_url=return_url,
    )

    return session.url


def handle_subscription_created(stripe_subscription: dict) -> None:
    """
    Handle checkout.session.completed webhook.

    Creates local Subscription record.
    """
    org_id = stripe_subscription.get("metadata", {}).get("organization_id")
    if not org_id:
        logger.warning("Subscription has no organization_id in metadata")
        return

    try:
        org = Organization.objects.get(id=int(org_id))
    except Organization.DoesNotExist:
        logger.error("Organization %s not found for subscription", org_id)
        return

    # Parse dates - Stripe 2025 API may nest these differently
    # Try new location first, fall back to old
    current_period = stripe_subscription.get("current_period", {})
    period_start_ts = current_period.get("start") or stripe_subscription.get("current_period_start")
    period_end_ts = current_period.get("end") or stripe_subscription.get("current_period_end")

    # Default to now if not available (shouldn't happen but be safe)
    if period_start_ts:
        period_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc)
    else:
        period_start = datetime.now(tz=timezone.utc)

    if period_end_ts:
        period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)
    else:
        # Default to 30 days from now
        period_end = datetime.now(tz=timezone.utc) + timedelta(days=30)

    # Get price ID from first item
    items = stripe_subscription.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else ""
    quantity = items[0]["quantity"] if items else 1

    # Create or update subscription
    subscription, created = Subscription.objects.update_or_create(
        stripe_subscription_id=stripe_subscription["id"],
        defaults={
            "organization": org,
            "stripe_price_id": price_id,
            "status": stripe_subscription["status"],
            "quantity": quantity,
            "current_period_start": period_start,
            "current_period_end": period_end,
            "cancel_at_period_end": stripe_subscription.get("cancel_at_period_end", False),
        },
    )

    # Emit subscription.activated event (system actor - webhook triggered)
    if created or stripe_subscription["status"] in ("active", "trialing"):
        publish_event(
            event_type="subscription.activated",
            aggregate=subscription,
            data={
                "stripe_subscription_id": stripe_subscription["id"],
                "status": stripe_subscription["status"],
                "quantity": quantity,
                "price_id": price_id,
            },
            actor=None,  # System/webhook event
            organization_id=str(org.id),
        )

    logger.info("Created/updated subscription for org %s", org.id)


def handle_subscription_updated(stripe_subscription: dict) -> None:
    """
    Handle customer.subscription.updated webhook.

    Updates local Subscription record.
    """
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription["id"])
    except Subscription.DoesNotExist:
        # Might be a new subscription - try to create
        handle_subscription_created(stripe_subscription)
        return

    # Parse dates - Stripe 2025 API may nest these differently
    current_period = stripe_subscription.get("current_period", {})
    period_start_ts = current_period.get("start") or stripe_subscription.get("current_period_start")
    period_end_ts = current_period.get("end") or stripe_subscription.get("current_period_end")

    if period_start_ts:
        period_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc)
    else:
        period_start = subscription.current_period_start  # Keep existing

    if period_end_ts:
        period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)
    else:
        period_end = subscription.current_period_end  # Keep existing

    # Get quantity from first item
    items = stripe_subscription.get("items", {}).get("data", [])
    quantity = items[0]["quantity"] if items else subscription.quantity

    old_status = subscription.status
    old_quantity = subscription.quantity

    subscription.status = stripe_subscription["status"]
    subscription.quantity = quantity
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end
    subscription.cancel_at_period_end = stripe_subscription.get("cancel_at_period_end", False)
    subscription.save()

    # Emit subscription.updated event if there are meaningful changes
    if old_status != subscription.status or old_quantity != subscription.quantity:
        publish_event(
            event_type="subscription.updated",
            aggregate=subscription,
            data={
                "old_status": old_status,
                "new_status": subscription.status,
                "old_quantity": old_quantity,
                "new_quantity": subscription.quantity,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            },
            actor=None,  # System/webhook event
            organization_id=str(subscription.organization_id),
        )

    logger.info("Updated subscription %s", subscription.stripe_subscription_id)


def handle_subscription_deleted(stripe_subscription: dict) -> None:
    """
    Handle customer.subscription.deleted webhook.

    Marks subscription as canceled.
    """
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription["id"])
    except Subscription.DoesNotExist:
        return

    subscription.status = Subscription.Status.CANCELED
    subscription.save(update_fields=["status", "updated_at"])

    # Emit subscription.canceled event
    publish_event(
        event_type="subscription.canceled",
        aggregate=subscription,
        data={
            "stripe_subscription_id": stripe_subscription["id"],
        },
        actor=None,  # System/webhook event
        organization_id=str(subscription.organization_id),
    )

    logger.info("Marked subscription %s as canceled", subscription.stripe_subscription_id)


def _get_tax_id_type(country_code: str, vat_id: str) -> str | None:
    """
    Determine Stripe tax ID type based on country.

    See: https://stripe.com/docs/api/customers/create#create_customer-tax_id_data
    """
    # EU VAT numbers
    eu_countries = {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
    }

    if country_code in eu_countries:
        return "eu_vat"

    # Add more tax ID types as needed
    tax_id_types = {
        "GB": "gb_vat",
        "CH": "ch_vat",
        "NO": "no_vat",
        "AU": "au_abn",
        "NZ": "nz_gst",
        "CA": "ca_bn",
        "US": "us_ein",
    }

    return tax_id_types.get(country_code)
