"""
Management command to set up Stripe products and prices.

Run once per environment to create the required Stripe price.
Usage: python manage.py setup_stripe
"""

from django.core.management.base import BaseCommand, CommandError

from apps.billing.stripe_client import get_stripe
from config.settings.base import settings


class Command(BaseCommand):
    help = "Set up Stripe product and price for per-seat billing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--price",
            type=int,
            default=1000,
            help="Monthly price per seat in cents (default: 1000 = $10.00)",
        )
        parser.add_argument(
            "--currency",
            type=str,
            default="usd",
            help="Currency code (default: usd)",
        )
        parser.add_argument(
            "--product-name",
            type=str,
            default="Pro Plan",
            help="Product name in Stripe (default: Pro Plan)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Create new product/price even if one exists",
        )

    def handle(self, *args, **options):
        if not settings.STRIPE_SECRET_KEY:
            raise CommandError(
                "STRIPE_SECRET_KEY not set. Add it to your .env file first."
            )

        stripe = get_stripe()
        product_name = options["product_name"]
        price_cents = options["price"]
        currency = options["currency"]

        self.stdout.write(f"Setting up Stripe for: {product_name}")
        self.stdout.write(f"Price: {price_cents} {currency.upper()} cents/seat/month")

        # Check for existing product
        existing_product = None
        existing_price = None

        if not options["force"]:
            # Search for existing product by metadata
            products = stripe.Product.search(
                query="metadata['app']:'tango' AND active:'true'"
            )
            if products.data:
                existing_product = products.data[0]
                self.stdout.write(
                    self.style.WARNING(
                        f"Found existing product: {existing_product.id}"
                    )
                )

                # Find active price for this product
                prices = stripe.Price.list(
                    product=existing_product.id,
                    active=True,
                    type="recurring",
                )
                if prices.data:
                    existing_price = prices.data[0]
                    self.stdout.write(
                        self.style.WARNING(
                            f"Found existing price: {existing_price.id}"
                        )
                    )

        if existing_price and not options["force"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Stripe already configured!\n"
                    f"Add this to your .env:\n\n"
                    f"STRIPE_PRICE_ID={existing_price.id}\n"
                )
            )
            return

        # Create product
        if not existing_product or options["force"]:
            product = stripe.Product.create(
                name=product_name,
                description="Per-seat monthly subscription",
                metadata={
                    "app": "tango",
                    "tier": "pro",
                },
            )
            self.stdout.write(f"Created product: {product.id}")
        else:
            product = existing_product

        # Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=price_cents,
            currency=currency,
            recurring={
                "interval": "month",
                "usage_type": "licensed",
            },
            billing_scheme="per_unit",
            metadata={
                "app": "tango",
                "tier": "pro",
            },
        )
        self.stdout.write(f"Created price: {price.id}")

        # Output instructions
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Stripe setup complete!\n"
                f"Add this to your .env:\n\n"
                f"STRIPE_PRICE_ID={price.id}\n"
            )
        )

        # Remind about webhook
        self.stdout.write(
            self.style.NOTICE(
                "\n📌 Don't forget to set up your webhook endpoint:\n"
                "   Stripe Dashboard → Developers → Webhooks\n"
                "   URL: https://your-domain.com/webhooks/stripe/\n"
                "   Events: checkout.session.completed, customer.subscription.*, invoice.*\n"
            )
        )
