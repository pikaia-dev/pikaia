"""Django admin for sync engine debugging."""

from django.contrib import admin

from apps.sync.models import SyncOperation


@admin.register(SyncOperation)
class SyncOperationAdmin(admin.ModelAdmin):
    """Admin for viewing sync operations."""

    list_display = [
        "idempotency_key",
        "entity_type",
        "entity_id",
        "intent",
        "status",
        "device_id",
        "server_timestamp",
        "drift_ms",
    ]
    list_filter = [
        "status",
        "intent",
        "entity_type",
        "server_timestamp",
    ]
    search_fields = [
        "idempotency_key",
        "entity_id",
        "device_id",
    ]
    readonly_fields = [
        "idempotency_key",
        "organization",
        "actor",
        "device_id",
        "entity_type",
        "entity_id",
        "intent",
        "payload",
        "client_timestamp",
        "server_timestamp",
        "status",
        "resolution_details",
        "drift_ms",
        "conflict_fields",
        "client_retry_count",
    ]
    ordering = ["-server_timestamp"]
    date_hierarchy = "server_timestamp"

    def has_add_permission(self, request):
        """Sync operations are created by the API, not admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Sync operations are immutable."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Sync operations should not be deleted."""
        return False
