"""Expire existing OTP records that contain plaintext codes in code_hash.

After migration 0002 renamed `code` to `code_hash`, any pre-existing records
still hold plaintext codes rather than SHA-256 hashes. Since OTP codes expire
after 10 minutes, stale records are safe to mark as expired.
"""

from django.db import migrations
from django.utils import timezone


def expire_plaintext_records(apps, schema_editor):
    """Mark all non-expired OTP records as expired.

    Any record created before the hash migration contains a plaintext code
    in the code_hash column. Marking them expired prevents accidental
    verification against unhashed values.
    """
    OTPVerification = apps.get_model("sms", "OTPVerification")
    OTPVerification.objects.filter(expires_at__gte=timezone.now()).update(expires_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("sms", "0002_rename_code_to_code_hash"),
    ]

    operations = [
        migrations.RunPython(
            expire_plaintext_records,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
