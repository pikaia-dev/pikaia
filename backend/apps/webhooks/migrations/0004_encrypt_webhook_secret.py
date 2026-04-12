from django.db import migrations

import apps.core.fields
import apps.webhooks.models


class Migration(migrations.Migration):
    dependencies = [
        ("webhooks", "0003_remove_webhookdelivery_redundant_index"),
    ]

    operations = [
        migrations.AlterField(
            model_name="webhookendpoint",
            name="secret",
            field=apps.core.fields.EncryptedTextField(
                default=apps.webhooks.models.generate_webhook_secret,
                help_text="Secret used to sign webhook payloads (HMAC-SHA256). Encrypted at rest.",
            ),
        ),
    ]
