"""
Rename OTPVerification.code to code_hash and update max_length for SHA-256 storage.

Security fix: OTP codes are now hashed before database storage.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sms", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="otpverification",
            old_name="code",
            new_name="code_hash",
        ),
        migrations.AlterField(
            model_name="otpverification",
            name="code_hash",
            field=models.CharField(
                help_text="SHA-256 hash of the OTP code",
                max_length=64,
            ),
        ),
    ]
