"""
Factories for webhooks app models.

Used in tests to create test data.
"""

import factory
from factory.django import DjangoModelFactory

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint

from ..accounts.factories import OrganizationFactory, UserFactory


class WebhookEndpointFactory(DjangoModelFactory):
    """Factory for WebhookEndpoint model."""

    class Meta:
        model = WebhookEndpoint

    organization = factory.SubFactory(OrganizationFactory)
    created_by = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Webhook Endpoint {n}")
    description = "Test webhook endpoint"
    url = factory.Sequence(lambda n: f"https://example.com/webhook/{n}")
    events = ["member.created", "member.deleted"]
    active = True


class WebhookDeliveryFactory(DjangoModelFactory):
    """Factory for WebhookDelivery model."""

    class Meta:
        model = WebhookDelivery

    endpoint = factory.SubFactory(WebhookEndpointFactory)
    event_id = factory.Sequence(lambda n: f"evt_test_{n}")
    event_type = "member.created"
    url_snapshot = factory.LazyAttribute(lambda obj: obj.endpoint.url)
    status = WebhookDelivery.Status.PENDING
