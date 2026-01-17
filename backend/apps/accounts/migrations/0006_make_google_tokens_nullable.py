# Generated to remove unused google token fields
# These fields were never created in production, so we safely drop them IF they exist

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_phone_number'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'accounts_user'
                    AND column_name = 'google_access_token'
                ) THEN
                    ALTER TABLE accounts_user DROP COLUMN google_access_token;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'accounts_user'
                    AND column_name = 'google_refresh_token'
                ) THEN
                    ALTER TABLE accounts_user DROP COLUMN google_refresh_token;
                END IF;
            END $$;
            """,
            reverse_sql="""
            -- Cannot reverse - these fields are no longer used
            """,
        ),
    ]
