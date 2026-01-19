"""
Tests for Stytch webhook handlers.

Tests event handling for member and organization updates.
"""

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from django.test import RequestFactory

from apps.accounts.webhooks import (
    handle_member_created,
    handle_member_deleted,
    handle_member_updated,
    handle_organization_deleted,
    handle_organization_updated,
    stytch_webhook,
)

from .factories import MemberFactory, OrganizationFactory, UserFactory


@pytest.mark.django_db
class TestHandleMemberCreated:
    """Tests for handle_member_created handler."""

    def test_creates_member_when_not_exists(self) -> None:
        """Should create member and user from webhook data."""
        from apps.accounts.models import Member, User

        org = OrganizationFactory.create()

        data = {
            "member": {
                "member_id": "member-new-123",
                "organization_id": org.stytch_org_id,
                "email_address": "newuser@example.com",
                "name": "New User",
                "roles": [],
            }
        }

        handle_member_created(data)

        # Verify user was created
        user = User.objects.get(email="newuser@example.com")
        assert user.name == "New User"

        # Verify member was created
        member = Member.objects.get(stytch_member_id="member-new-123")
        assert member.user == user
        assert member.organization == org
        assert member.role == "member"

    def test_creates_admin_member_from_roles(self) -> None:
        """Should set admin role when stytch_admin role present."""
        from apps.accounts.models import Member

        org = OrganizationFactory.create()

        data = {
            "member": {
                "member_id": "member-admin-123",
                "organization_id": org.stytch_org_id,
                "email_address": "admin@example.com",
                "name": "Admin User",
                "roles": [{"role_id": "stytch_admin"}],
            }
        }

        handle_member_created(data)

        member = Member.objects.get(stytch_member_id="member-admin-123")
        assert member.role == "admin"

    def test_skips_existing_member(self) -> None:
        """Should not create duplicate if member already exists."""
        member = MemberFactory.create()

        data = {
            "member": {
                "member_id": member.stytch_member_id,
                "organization_id": member.organization.stytch_org_id,
                "email_address": member.user.email,
                "name": "Different Name",
                "roles": [],
            }
        }

        handle_member_created(data)

        # Member should not be duplicated or modified
        member.refresh_from_db()
        assert member.user.name != "Different Name"

    def test_skips_unknown_organization(self) -> None:
        """Should not create member if organization doesn't exist."""
        from apps.accounts.models import Member

        data = {
            "member": {
                "member_id": "member-orphan-123",
                "organization_id": "organization-unknown-999",
                "email_address": "orphan@example.com",
                "name": "Orphan User",
                "roles": [],
            }
        }

        handle_member_created(data)

        # Member should not be created
        assert not Member.objects.filter(stytch_member_id="member-orphan-123").exists()

    def test_handles_missing_fields(self) -> None:
        """Should gracefully handle missing required fields."""
        data = {"member": {"member_id": "member-123"}}

        # Should not raise
        handle_member_created(data)

    def test_links_to_existing_user(self) -> None:
        """Should link to existing user if email matches."""
        from apps.accounts.models import Member

        org = OrganizationFactory.create()
        existing_user = UserFactory.create(email="existing@example.com", name="Existing Name")

        data = {
            "member": {
                "member_id": "member-existing-user-123",
                "organization_id": org.stytch_org_id,
                "email_address": "existing@example.com",
                "name": "New Name",  # Different name
                "roles": [],
            }
        }

        handle_member_created(data)

        member = Member.objects.get(stytch_member_id="member-existing-user-123")
        assert member.user == existing_user


@pytest.mark.django_db
class TestHandleMemberUpdated:
    """Tests for handle_member_updated handler."""

    def test_updates_member_role_to_admin(self) -> None:
        """Should update member role when Stytch role changes."""
        member = MemberFactory.create(role="member")

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
        member = MemberFactory.create(role="admin")

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
        member = MemberFactory.create()
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
        member = MemberFactory.create()
        assert member.deleted_at is None

        data = {"id": member.stytch_member_id}

        handle_member_deleted(data)

        member.refresh_from_db()
        assert member.deleted_at is not None

    def test_uses_member_object_id(self) -> None:
        """Should support member.member_id format."""
        member = MemberFactory.create()

        data = {"member": {"member_id": member.stytch_member_id}}

        handle_member_deleted(data)

        member.refresh_from_db()
        assert member.deleted_at is not None

    def test_ignores_already_deleted(self) -> None:
        """Should not error if member already deleted."""
        member = MemberFactory.create()
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
        org = OrganizationFactory.create(name="Old Name")

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
        org = OrganizationFactory.create(slug="old-slug")

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
        org = OrganizationFactory.create(logo_url="")

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
class TestHandleOrganizationDeleted:
    """Tests for handle_organization_deleted handler."""

    def test_soft_deletes_organization(self) -> None:
        """Should soft delete the organization."""
        from apps.organizations.models import Organization

        org = OrganizationFactory.create()
        assert org.deleted_at is None

        data = {"id": org.stytch_org_id}

        handle_organization_deleted(data)

        # Use all_objects to get soft-deleted org
        org = Organization.all_objects.get(id=org.id)
        assert org.deleted_at is not None

    def test_soft_deletes_all_members(self) -> None:
        """Should soft delete all members when org is deleted."""
        from apps.accounts.models import Member
        from apps.organizations.models import Organization

        org = OrganizationFactory.create()
        member1 = MemberFactory.create(organization=org)
        member2 = MemberFactory.create(organization=org)

        data = {"id": org.stytch_org_id}

        handle_organization_deleted(data)

        # Members should be soft deleted
        member1 = Member.all_objects.get(id=member1.id)
        member2 = Member.all_objects.get(id=member2.id)
        assert member1.deleted_at is not None
        assert member2.deleted_at is not None

        # Org should be soft deleted
        org = Organization.all_objects.get(id=org.id)
        assert org.deleted_at is not None

    def test_uses_organization_object_id(self) -> None:
        """Should support organization.organization_id format."""
        from apps.organizations.models import Organization

        org = OrganizationFactory.create()

        data = {"organization": {"organization_id": org.stytch_org_id}}

        handle_organization_deleted(data)

        org = Organization.all_objects.get(id=org.id)
        assert org.deleted_at is not None

    def test_ignores_already_deleted(self) -> None:
        """Should not error if org already deleted."""
        from apps.organizations.models import Organization

        org = OrganizationFactory.create()
        org.soft_delete()
        original_deleted_at = org.deleted_at

        data = {"id": org.stytch_org_id}

        handle_organization_deleted(data)

        org = Organization.all_objects.get(id=org.id)
        assert org.deleted_at == original_deleted_at

    def test_ignores_unknown_organization(self) -> None:
        """Should not raise for unknown organization_id."""
        data = {"id": "organization-unknown-123"}

        # Should not raise
        handle_organization_deleted(data)


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

    @patch("apps.accounts.webhooks.handle_member_created")
    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_dispatches_member_create_event(
        self,
        mock_settings,
        mock_webhook_class,
        mock_handler,
        request_factory: RequestFactory,
    ) -> None:
        """Should dispatch member create events to handler."""
        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()

        event_data = {
            "event_type": "direct.member.create",
            "action": "CREATE",
            "object_type": "member",
            "member": {"member_id": "member-123"},
        }
        mock_webhook.verify.return_value = event_data
        mock_webhook_class.return_value = mock_webhook

        request = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
            HTTP_SVIX_ID="msg_member_create_123",
        )

        response = stytch_webhook(request)

        assert response.status_code == 200
        mock_handler.assert_called_once_with(event_data)

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
            HTTP_SVIX_ID="msg_member_update_123",
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
            HTTP_SVIX_ID="msg_member_delete_123",
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
            HTTP_SVIX_ID="msg_org_update_123",
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
            HTTP_SVIX_ID="msg_unhandled_123",
        )

        response = stytch_webhook(request)

        assert response.status_code == 200

    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_missing_svix_id_returns_400(
        self,
        mock_settings: MagicMock,
        mock_webhook_class: MagicMock,
        request_factory: RequestFactory,
    ) -> None:
        """Should return 400 when svix-id header is missing."""
        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()
        mock_webhook.verify.return_value = {
            "event_type": "test",
            "action": "TEST",
            "object_type": "test",
        }
        mock_webhook_class.return_value = mock_webhook

        request = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps({}).encode(),
            content_type="application/json",
            # No HTTP_SVIX_ID header
        )

        response = stytch_webhook(request)

        assert response.status_code == 400


@pytest.mark.django_db
class TestStytchWebhookIdempotency:
    """Tests for Stytch webhook idempotency."""

    @patch("apps.accounts.webhooks.handle_member_created")
    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_handler_exception_rolls_back_idempotency_marker(
        self,
        mock_settings: MagicMock,
        mock_webhook_class: MagicMock,
        mock_handler: MagicMock,
        request_factory: "RequestFactory",
    ) -> None:
        """Should rollback ProcessedWebhook when handler fails, allowing retry."""
        from apps.core.models import ProcessedWebhook

        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()
        event_id = "msg_rollback_test"
        event_data = {
            "event_type": "direct.member.create",
            "action": "CREATE",
            "object_type": "member",
            "member": {"member_id": "member-123"},
        }
        mock_webhook.verify.return_value = event_data
        mock_webhook_class.return_value = mock_webhook

        # First request - handler raises exception
        mock_handler.side_effect = Exception("Database error")
        request1 = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
            HTTP_SVIX_ID=event_id,
        )
        response1 = stytch_webhook(request1)
        assert response1.status_code == 500

        # Critical: ProcessedWebhook should NOT be persisted due to rollback
        assert not ProcessedWebhook.objects.filter(source="stytch", event_id=event_id).exists()

        # Retry request - handler succeeds this time
        mock_handler.side_effect = None
        mock_handler.reset_mock()
        request2 = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
            HTTP_SVIX_ID=event_id,
        )
        response2 = stytch_webhook(request2)
        assert response2.status_code == 200

        # Handler should be called on retry
        assert mock_handler.call_count == 1
        # Now the marker should exist
        assert ProcessedWebhook.objects.filter(source="stytch", event_id=event_id).exists()

    @patch("apps.accounts.webhooks.handle_member_created")
    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_duplicate_event_not_processed(
        self,
        mock_settings: MagicMock,
        mock_webhook_class: MagicMock,
        mock_handler: MagicMock,
        request_factory: RequestFactory,
    ) -> None:
        """Should skip processing for duplicate event IDs."""
        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()
        event_data = {
            "event_type": "direct.member.create",
            "action": "CREATE",
            "object_type": "member",
            "member": {"member_id": "member-123"},
        }
        mock_webhook.verify.return_value = event_data
        mock_webhook_class.return_value = mock_webhook

        # First request - should process
        request1 = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
            HTTP_SVIX_ID="msg_duplicate_test",
        )
        response1 = stytch_webhook(request1)
        assert response1.status_code == 200
        assert mock_handler.call_count == 1

        # Second request with same svix-id - should skip
        request2 = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
            HTTP_SVIX_ID="msg_duplicate_test",
        )
        response2 = stytch_webhook(request2)
        assert response2.status_code == 200
        # Handler should NOT be called again
        assert mock_handler.call_count == 1

    @patch("apps.accounts.webhooks.handle_member_created")
    @patch("apps.accounts.webhooks.Webhook")
    @patch("apps.accounts.webhooks.settings")
    def test_different_events_processed_separately(
        self,
        mock_settings: MagicMock,
        mock_webhook_class: MagicMock,
        mock_handler: MagicMock,
        request_factory: RequestFactory,
    ) -> None:
        """Should process events with different IDs."""
        mock_settings.STYTCH_WEBHOOK_SECRET = "whsec_test"
        mock_webhook = MagicMock()
        event_data = {
            "event_type": "direct.member.create",
            "action": "CREATE",
            "object_type": "member",
            "member": {"member_id": "member-123"},
        }
        mock_webhook.verify.return_value = event_data
        mock_webhook_class.return_value = mock_webhook

        # First event
        request1 = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
            HTTP_SVIX_ID="msg_first",
        )
        response1 = stytch_webhook(request1)
        assert response1.status_code == 200

        # Second event with different ID
        request2 = request_factory.post(
            "/webhooks/stytch/",
            data=json.dumps(event_data).encode(),
            content_type="application/json",
            HTTP_SVIX_ID="msg_second",
        )
        response2 = stytch_webhook(request2)
        assert response2.status_code == 200

        # Both should be processed
        assert mock_handler.call_count == 2
