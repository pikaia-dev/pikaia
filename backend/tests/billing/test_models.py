"""
Tests for billing models.
"""

import pytest

from apps.billing.models import Subscription

from .factories import SubscriptionFactory


@pytest.mark.django_db
class TestSubscriptionModel:
    """Tests for Subscription model."""

    def test_str_representation(self) -> None:
        """Should return org name and status."""
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE)
        assert sub.organization.name in str(sub)
        assert "active" in str(sub)

    def test_is_active_when_active(self) -> None:
        """Should return True when status is active."""
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE)
        assert sub.is_active is True

    def test_is_active_when_trialing(self) -> None:
        """Should return True when status is trialing."""
        sub = SubscriptionFactory(status=Subscription.Status.TRIALING)
        assert sub.is_active is True

    def test_is_active_when_past_due(self) -> None:
        """Should return False when status is past_due."""
        sub = SubscriptionFactory(status=Subscription.Status.PAST_DUE)
        assert sub.is_active is False

    def test_is_active_when_canceled(self) -> None:
        """Should return False when status is canceled."""
        sub = SubscriptionFactory(status=Subscription.Status.CANCELED)
        assert sub.is_active is False

    def test_is_active_when_incomplete(self) -> None:
        """Should return False when status is incomplete."""
        sub = SubscriptionFactory(status=Subscription.Status.INCOMPLETE)
        assert sub.is_active is False

    def test_is_active_when_unpaid(self) -> None:
        """Should return False when status is unpaid."""
        sub = SubscriptionFactory(status=Subscription.Status.UNPAID)
        assert sub.is_active is False

    def test_is_active_when_paused(self) -> None:
        """Should return False when status is paused."""
        sub = SubscriptionFactory(status=Subscription.Status.PAUSED)
        assert sub.is_active is False


@pytest.mark.django_db
class TestSubscriptionConstraints:
    """Tests for database constraints on Subscription model."""

    def test_stripe_subscription_id_is_unique(self) -> None:
        """Should enforce unique constraint on stripe_subscription_id."""
        sub1 = SubscriptionFactory(stripe_subscription_id="sub_same_id")

        with pytest.raises(Exception):  # IntegrityError wrapped
            SubscriptionFactory(
                stripe_subscription_id="sub_same_id",
            )

    def test_one_subscription_per_org(self) -> None:
        """Should enforce OneToOne relationship with organization."""
        sub = SubscriptionFactory()

        with pytest.raises(Exception):  # IntegrityError wrapped
            SubscriptionFactory(
                organization=sub.organization,
                stripe_subscription_id="sub_different_id",
            )

    def test_quantity_must_be_positive(self) -> None:
        """Quantity should be a positive integer (enforced by PositiveIntegerField)."""
        with pytest.raises(Exception):
            sub = SubscriptionFactory(quantity=-1)
            sub.full_clean()


@pytest.mark.django_db
class TestSubscriptionTimestamps:
    """Tests for timestamp behavior on Subscription model."""

    def test_created_at_set_on_create(self) -> None:
        """Should set created_at automatically."""
        sub = SubscriptionFactory()
        assert sub.created_at is not None

    def test_updated_at_changes_on_save(self) -> None:
        """Should update updated_at on each save."""
        sub = SubscriptionFactory()
        original_updated = sub.updated_at

        sub.status = Subscription.Status.PAST_DUE
        sub.save()

        assert sub.updated_at > original_updated
