"""
Tests for device models.

Tests Device and DeviceLinkToken model properties, methods, and managers.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.devices.models import Device
from tests.accounts.factories import UserFactory
from tests.devices.factories import DeviceFactory, DeviceLinkTokenFactory


@pytest.mark.django_db
class TestDeviceModel:
    """Tests for Device model."""

    def test_is_revoked_false_for_active_device(self) -> None:
        """Should return False when device has no revoked_at."""
        device = DeviceFactory.create(revoked_at=None)

        assert device.is_revoked is False

    def test_is_revoked_true_for_revoked_device(self) -> None:
        """Should return True when device has revoked_at set."""
        device = DeviceFactory.create()
        device.revoked_at = timezone.now()
        device.save()

        assert device.is_revoked is True

    def test_revoke_sets_revoked_at(self) -> None:
        """Should set revoked_at timestamp when called."""
        device = DeviceFactory.create()
        assert device.revoked_at is None

        device.revoke()

        device.refresh_from_db()
        assert device.revoked_at is not None
        assert device.is_revoked is True

    def test_str_representation_active_device(self) -> None:
        """Should return name and email for active device."""
        device = DeviceFactory.create(name="My iPhone")

        result = str(device)

        assert "My iPhone" in result
        assert device.user.email in result
        assert "(revoked)" not in result

    def test_str_representation_revoked_device(self) -> None:
        """Should include (revoked) for revoked device."""
        device = DeviceFactory.create(name="Old Phone")
        device.revoke()

        result = str(device)

        assert "Old Phone" in result
        assert "(revoked)" in result


@pytest.mark.django_db
class TestDeviceManager:
    """Tests for Device managers."""

    def test_default_manager_excludes_revoked(self) -> None:
        """Default manager should exclude revoked devices."""
        user = UserFactory.create()
        _active = DeviceFactory.create(user=user, name="Active")
        revoked = DeviceFactory.create(user=user, name="Revoked")
        revoked.revoke()

        # Default manager should only return active device
        devices = Device.objects.all()

        assert devices.count() == 1
        first_device = devices.first()
        assert first_device is not None
        assert first_device.name == "Active"

    def test_all_objects_manager_includes_revoked(self) -> None:
        """all_objects manager should include all devices."""
        user = UserFactory.create()
        _active = DeviceFactory.create(user=user, name="Active")
        revoked = DeviceFactory.create(user=user, name="Revoked")
        revoked.revoke()

        # all_objects should return both
        devices = Device.all_objects.all()

        assert devices.count() == 2
        names = [d.name for d in devices]
        assert "Active" in names
        assert "Revoked" in names

    def test_filter_by_user_on_default_manager(self) -> None:
        """Default manager filter should exclude revoked."""
        user = UserFactory.create()
        _active = DeviceFactory.create(user=user, name="Active")
        revoked = DeviceFactory.create(user=user, name="Revoked")
        revoked.revoke()

        devices = Device.objects.filter(user=user)

        assert devices.count() == 1
        first_device = devices.first()
        assert first_device is not None
        assert first_device.name == "Active"

    def test_get_by_id_excludes_revoked(self) -> None:
        """Default manager get() should not find revoked devices."""
        device = DeviceFactory.create()
        device_id = device.id
        device.revoke()

        with pytest.raises(Device.DoesNotExist):
            Device.objects.get(id=device_id)

    def test_all_objects_get_finds_revoked(self) -> None:
        """all_objects get() should find revoked devices."""
        device = DeviceFactory.create()
        device_id = device.id
        device.revoke()

        found = Device.all_objects.get(id=device_id)

        assert found.id == device_id
        assert found.is_revoked is True


@pytest.mark.django_db
class TestDeviceLinkTokenModel:
    """Tests for DeviceLinkToken model."""

    def test_is_used_false_when_used_at_is_none(self) -> None:
        """Should return False when token has not been used."""
        token = DeviceLinkTokenFactory.create(used_at=None)

        assert token.is_used is False

    def test_is_used_true_when_used_at_is_set(self) -> None:
        """Should return True when token has been used."""
        token = DeviceLinkTokenFactory.create(used_at=timezone.now())

        assert token.is_used is True

    def test_is_expired_false_when_not_expired(self) -> None:
        """Should return False when token has not expired."""
        token = DeviceLinkTokenFactory.create(expires_at=timezone.now() + timedelta(minutes=5))

        assert token.is_expired is False

    def test_is_expired_true_when_expired(self) -> None:
        """Should return True when token has expired."""
        token = DeviceLinkTokenFactory.create(expires_at=timezone.now() - timedelta(minutes=1))

        assert token.is_expired is True

    def test_is_valid_true_for_fresh_token(self) -> None:
        """Should return True for unused, unexpired token."""
        token = DeviceLinkTokenFactory.create(
            used_at=None,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        assert token.is_valid is True

    def test_is_valid_false_when_used(self) -> None:
        """Should return False for used token."""
        token = DeviceLinkTokenFactory.create(
            used_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        assert token.is_valid is False

    def test_is_valid_false_when_expired(self) -> None:
        """Should return False for expired token."""
        token = DeviceLinkTokenFactory.create(
            used_at=None,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        assert token.is_valid is False

    def test_mark_used_sets_used_at(self) -> None:
        """Should set used_at timestamp when called."""
        token = DeviceLinkTokenFactory.create(used_at=None)
        assert token.used_at is None

        token.mark_used()

        token.refresh_from_db()
        assert token.used_at is not None
        assert token.is_used is True

    def test_str_representation_valid_token(self) -> None:
        """Should include 'valid' for valid token."""
        token = DeviceLinkTokenFactory.create(
            used_at=None,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        result = str(token)

        assert "valid" in result
        assert str(token.id) in result

    def test_str_representation_used_token(self) -> None:
        """Should include 'used' for used token."""
        token = DeviceLinkTokenFactory.create(
            used_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        result = str(token)

        assert "used" in result

    def test_str_representation_expired_token(self) -> None:
        """Should include 'expired' for expired token."""
        token = DeviceLinkTokenFactory.create(
            used_at=None,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        result = str(token)

        assert "expired" in result

    def test_uuid_primary_key(self) -> None:
        """Token ID should be a UUID."""
        token = DeviceLinkTokenFactory.create()

        # ID should be a UUID (string representation has dashes)
        assert "-" in str(token.id)
        assert len(str(token.id)) == 36
