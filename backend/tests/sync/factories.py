"""
Factories for sync app models.

Used in tests to create test data.
"""

from typing import Any

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.sync.models import SyncOperation
from tests.accounts.factories import MemberFactory, OrganizationFactory


class SyncOperationFactory(DjangoModelFactory[SyncOperation]):
    """Factory for SyncOperation model."""

    class Meta:
        model = SyncOperation

    idempotency_key: Any = factory.Sequence(lambda n: f"op_{n:06d}")
    organization: Any = factory.SubFactory(OrganizationFactory)
    actor: Any = factory.SubFactory(MemberFactory)
    device_id = factory.Sequence(lambda n: f"device_{n}")

    entity_type = "test_contact"
    entity_id: Any = factory.Sequence(lambda n: f"tc_{n:024d}")
    intent = SyncOperation.Intent.CREATE

    payload: Any = factory.LazyFunction(lambda: {"name": "Test"})
    client_timestamp: Any = factory.LazyFunction(timezone.now)

    status = SyncOperation.Status.PENDING
    drift_ms = 50
    client_retry_count = 0
