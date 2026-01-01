"""
Tests for Stytch webhook handlers.

Tests event handling for member and organization updates.
"""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory

from apps.accounts.webhooks import (
    handle_member_deleted,
    handle_member_updated,
    handle_organization_updated,
    stytch_webhook,
)

from .factories import MemberFactory, OrganizationFactory


@pytest.fixture
def request_factory() -> RequestFactory:
    """Django request factory for unit testing views."""
    return RequestFactory()


@pytest.mark.django_db
class TestHandleMemberUpdated:
    """Tests for handle_member_updated handler."""

    def test_updates_member_role_to_admin(self) -> None:
        """Should update member role when Stytch role changes."""
        member = MemberFactory(role="member")

        data = {
            "member": {
                "member_id": member.stytch_member_id,
                "roles": [{"role_id": "stytch_admin"}],
            }
        }

        handle_member_updated(data)

        member.refresh_from_db()
        assert member.role == "admin"

    def test_updates_member_role_to_member(self) -> None:
        """Should downgrade role when admin role removed."""
        member = MemberFactory(role="admin")

        data = {
            "member": {
                "member_id": member.stytch_member_id,
                "roles": [{"role_id": "stytch_member"}],  # Not admin
            }
        }

        handle_member_updated(data)

        member.refresh_from_db()
        assert member.role == "member"

    def test_soft_deletes_when_status_deleted(self) -> None:
        """Should soft delete member when status is 'deleted'."""
        member = MemberFactory()
        assert member.deleted_at is None

        data = {
            "member": {
                "member_id": member.stytch_member_id,
                "status": "deleted",
                "roles": [],
            }
        }

        handle_member_updated(data)

        member.refresh_from_db()
        assert member.deleted_at is not None

    def test_ignores_unknown_member(self) -> None:
        """Should not raise for unknown member_id."""
        data = {
            "member": {
                "member_id": "member-unknown-123",
                "roles": [{"role_id": "stytch_admin"}],
            }
        }

        # Should not raise
        handle_member_updated(data)

    def test_ignores_missing_member_id(self) -> None:
        """Should handle missing member_id gracefully."""
        data = {"member": {}}

        # Should not raise
        handle_member_updated(data)


@pytest.mark.django_db
class TestHandleMemberDeleted:
    """Tests for handle_member_deleted handler."""

    def test_soft_deletes_member(self) -> None:
        """Should soft delete the member."""
        member = MemberFactory()
        assert member.deleted_at is None

        data = {"id": member.stytch_member_id}

        handle_member_deleted(data)

        member.refresh_from_db()
        assert member.deleted_at is not None

    def test_uses_member_object_id(self) -> None:
        """Should support member.member_id format."""
        member = MemberFactory()

        data = {"member": {"member_id": member.stytch_member_id}}

        handle_member_deleted(data)

        member.refresh_from_db()
        assert member.deleted_at is not None

    def test_ignores_already_deleted(self) -> None:
        """Should not error if member already deleted."""
        member = MemberFactory()
        member.soft_delete()
        original_deleted_at = member.deleted_at

        data = {"id": member.stytch_member_id}

        handle_member_deleted(data)

        member.refresh_from_db()
        assert member.deleted_at == original_deleted_at

    def test_ignores_unknown_member(self) -> None:
        """Should not raise for unknown member_id."""
        data = {"id": "member-unknown-123"}

        # Should not raise
        handle_member_deleted(data)


@pytest.mark.django_db
class TestHandleOrganizationUpdated:
    """Tests for handle_organization_updated handler."""

    def test_updates_organization_name(self) -> None:
        """Should update org name when changed in Stytch."""
        org = OrganizationFactory(name="Old Name")

        data = {
            "organization": {
                "organization_id": org.stytch_org_id,
                "organization_name": "New Name",
                "organization_slug": org.slug,
            }
        }

        handle_organization_updated(data)

        org.refresh_from_db()
        assert org.name == "New Name"

    def test_updates_organization_slug(self) -> None:
        """Should update org slug when changed in Stytch."""
        org = OrganizationFactory(slug="old-slug")

        data = {
            "organization": {
                "organization_id": org.stytch_org_id,
                "organization_name": org.name,
                "organization_slug": "new-slug",
            }
        }

        handle_organization_updated(data)

        org.refresh_from_db()
        assert org.slug == "new-slug"

    def test_updates_logo_url(self) -> None:
        """Should update logo URL when changed."""
        org = OrganizationFactory(logo_url="")

        data = {
            "organization": {
                "organization_id": org.stytch_org_id,
                "organization_name": org.name,
                "organization_slug": org.slug,
                "organization_logo_url": "https://example.com/logo.png",
            }
        }

        handle_organization_updated(data)

        org.refresh_from_db()
        assert org.logo_url == "https://example.com/logo.png"

    def test_ignores_unknown_organization(self) -> None:
        """Should not raise for unknown organization_id."""
        data = {
            "organization": {
                "organization_id": "organization-unknown-123",
                "organization_name": "Test",
            }
        }

        # Should not raise
        handle_organization_updated(data)


@pytest.mark.django_db
class TestStytchWebhook:
    """Tests for the stytch_webhook view."""

    @patch("apps.accounts.webhooks.settings")
    def test_returns_500_when_secret_not_configured(
        self, mock_settings, request_factory: RequestFactory
    ) -> None:
        """Should return 500 if webhook secret is not set."""
        mock_settings.STYTCH_WEBHOOK_SECRET = ""

        request = request_factory.post(
            "/webhooks/stytch/",
            data=b"{}",
            content_type="application/json",
        )

        response = stytch_webhook(request)

        assert response.status_code == 500

    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_returns_400_on_invalid_signature(
        self, mock_settings, mock_webhook_class, request_factory: RequestFactory
    ) -> None:
        """Should return 400 if signature verification fails."""
        from svix.webhooks import WebhookVerificationError

        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()
        mock_webhook.verify.side_effect = WebhookVerificationError("Invalid signature")
        mock_webhook_class.return_value = mock_webhook

        request = request_factory.post(
            "/webhooks/stytch/",
            data=b"{}",
            content_type="application/json",
        )

        response = stytch_webhook(request)

        assert response.status_code == 400

    @patch("apps.accounts.webhooks.handle_member_updated")
    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_dispatches_member_update_event(
        self,
        mock_settings,
        mock_webhook_class,
        mock_handler,
        request_factory: RequestFactory,
    ) -> None:
        """Should dispatch member update events to handler."""
        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()

        event_data = {
            "event_type": "direct.member.update",
            "action": "UPDATE",
            "object_type": "member",
            "member": {"member_id": "member-123"},
        }
        mock_webhook.verify.return_value = event_data
        mock_webhook_class.return_value = mock_webhook

        request = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
        )

        response = stytch_webhook(request)

        assert response.status_code == 200
        mock_handler.assert_called_once_with(event_data)

    @patch("apps.accounts.webhooks.handle_member_deleted")
    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_dispatches_member_delete_event(
        self,
        mock_settings,
        mock_webhook_class,
        mock_handler,
        request_factory: RequestFactory,
    ) -> None:
        """Should dispatch member delete events to handler."""
        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()

        event_data = {
            "event_type": "dashboard.member.delete",
            "action": "DELETE",
            "object_type": "member",
            "id": "member-123",
        }
        mock_webhook.verify.return_value = event_data
        mock_webhook_class.return_value = mock_webhook

        request = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
        )

        response = stytch_webhook(request)

        assert response.status_code == 200
        mock_handler.assert_called_once_with(event_data)

    @patch("apps.accounts.webhooks.handle_organization_updated")
    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_dispatches_organization_update_event(
        self,
        mock_settings,
        mock_webhook_class,
        mock_handler,
        request_factory: RequestFactory,
    ) -> None:
        """Should dispatch organization update events to handler."""
        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()

        event_data = {
            "event_type": "dashboard.organization.update",
            "action": "UPDATE",
            "object_type": "organization",
            "organization": {"organization_id": "org-123"},
        }
        mock_webhook.verify.return_value = event_data
        mock_webhook_class.return_value = mock_webhook

        request = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
        )

        response = stytch_webhook(request)

        assert response.status_code == 200
        mock_handler.assert_called_once_with(event_data)

    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_returns_200_for_unhandled_events(
        self, mock_settings, mock_webhook_class, request_factory: RequestFactory
    ) -> None:
        """Should return 200 for unhandled event types."""
        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()

        event_data = {
            "event_type": "direct.sso_connection.create",
            "action": "CREATE",
            "object_type": "sso_connection",
        }
        mock_webhook.verify.return_value = event_data
        mock_webhook_class.return_value = mock_webhook

        request = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
        )

        response = stytch_webhook(request)

        assert response.status_code == 200
