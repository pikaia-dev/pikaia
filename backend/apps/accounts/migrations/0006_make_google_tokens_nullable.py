# Generated manually to fix NOT NULL constraint on google tokens

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_phone_number'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE accounts_user 
            ALTER COLUMN google_access_token DROP NOT NULL,
            ALTER COLUMN google_refresh_token DROP NOT NULL;
            """,
            reverse_sql="""
            -- Cannot reverse - would require values for all rows
            """,
        ),
    ]
