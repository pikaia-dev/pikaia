"""Admin configuration for devices app."""

from django.contrib import admin

from apps.devices.models import Device, DeviceLinkToken


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """Admin for Device model."""

    list_display = ["name", "user", "platform", "device_uuid", "is_revoked", "created_at"]
    list_filter = ["platform", "revoked_at"]
    search_fields = ["name", "device_uuid", "user__email"]
    readonly_fields = ["device_uuid", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self, request):
        """Include revoked devices in admin."""
        return Device.all_objects.all()

    @admin.display(boolean=True, description="Revoked")
    def is_revoked(self, obj: Device) -> bool:
        """Show revoked status as boolean."""
        return obj.is_revoked


@admin.register(DeviceLinkToken)
class DeviceLinkTokenAdmin(admin.ModelAdmin):
    """Admin for DeviceLinkToken model."""

    list_display = ["id", "user", "organization", "status", "created_at", "expires_at"]
    list_filter = ["organization"]
    search_fields = ["user__email", "organization__name"]
    readonly_fields = ["id", "token_hash", "created_at"]
    ordering = ["-created_at"]

    @admin.display(description="Status")
    def status(self, obj: DeviceLinkToken) -> str:
        """Show token status."""
        if obj.is_used:
            return "Used"
        if obj.is_expired:
            return "Expired"
        return "Valid"
