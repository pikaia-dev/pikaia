"""
Admin configuration for SMS app.
"""

from django.contrib import admin

from apps.sms.models import OTPVerification


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    """Admin for OTP verifications."""

    list_display = [
        "id",
        "phone_number_masked",
        "purpose",
        "is_verified",
        "attempts",
        "is_expired_display",
        "created_at",
    ]
    list_filter = ["purpose", "is_verified", "created_at"]
    search_fields = ["phone_number", "user__email"]
    readonly_fields = [
        "code_hash",
        "created_at",
        "verified_at",
        "aws_message_id",
    ]
    raw_id_fields = ["user"]

    def phone_number_masked(self, obj: OTPVerification) -> str:
        """Show only last 4 digits of phone for privacy."""
        return f"***{obj.phone_number[-4:]}"

    phone_number_masked.short_description = "Phone"  # type: ignore[attr-defined]

    def is_expired_display(self, obj: OTPVerification) -> bool:
        """Display expired status."""
        return obj.is_expired

    is_expired_display.short_description = "Expired"  # type: ignore[attr-defined]
    is_expired_display.boolean = True  # type: ignore[attr-defined]
