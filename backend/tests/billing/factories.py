"""
Factories for billing app models.

Used in tests to create test data.
"""

from datetime import datetime, timedelta, timezone

import factory
from factory.django import DjangoModelFactory

from apps.billing.models import Subscription
from apps.organizations.models import Organization
from tests.accounts.factories import OrganizationFactory


class SubscriptionFactory(DjangoModelFactory):
    """Factory for Subscription model."""

    class Meta:
        model = Subscription

    organization = factory.SubFactory(OrganizationFactory)
    stripe_subscription_id = factory.Sequence(lambda n: f"sub_test_{n}")
    stripe_price_id = factory.Sequence(lambda n: f"price_test_{n}")
    status = Subscription.Status.ACTIVE
    quantity = 1
    current_period_start = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    current_period_end = factory.LazyFunction(
        lambda: datetime.now(tz=timezone.utc) + timedelta(days=30)
    )
    cancel_at_period_end = False
