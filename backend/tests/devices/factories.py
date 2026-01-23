"""
Factories for devices app models.

Used in tests to create test data.
"""

import uuid
from datetime import timedelta
from typing import Any

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.devices.models import Device, DeviceLinkToken


class DeviceFactory(DjangoModelFactory[Device]):
    """Factory for Device model."""

    class Meta:
        model = Device

    user: Any = factory.SubFactory("tests.accounts.factories.UserFactory")
    device_uuid = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name: Any = factory.Faker("word")
    platform = "ios"
    os_version = "17.2"
    app_version = "1.0.0"
    revoked_at = None


class DeviceLinkTokenFactory(DjangoModelFactory[DeviceLinkToken]):
    """Factory for DeviceLinkToken model."""

    class Meta:
        model = DeviceLinkToken

    user: Any = factory.SubFactory("tests.accounts.factories.UserFactory")
    member: Any = factory.SubFactory("tests.accounts.factories.MemberFactory")
    organization: Any = factory.SubFactory("tests.accounts.factories.OrganizationFactory")
    token_hash = factory.LazyFunction(lambda: uuid.uuid4().hex + uuid.uuid4().hex)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=5))
    used_at = None
