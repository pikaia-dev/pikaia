"""
Base Django settings.

Shared configuration for all environments.
"""

from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Environment-based configuration using pydantic-settings."""

    SECRET_KEY: str = "django-insecure-change-me-in-production"
    DEBUG: bool = False
    ALLOWED_HOSTS: str = ""  # Comma-separated list, e.g. "localhost,127.0.0.1"

    # Database - supports both DATABASE_URL (local) and individual DB_* vars (ECS)
    DATABASE_URL: PostgresDsn | None = None
    DB_HOST: str = ""
    DB_PORT: str = "5432"
    DB_NAME: str = ""
    DB_USER: str = ""
    DB_PASSWORD: str = ""

    # Stytch
    STYTCH_PROJECT_ID: str = ""
    STYTCH_SECRET: str = ""
    STYTCH_WEBHOOK_SECRET: str = ""  # Svix webhook signing secret

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID: str = ""  # Price ID for per-seat subscription

    # Resend
    RESEND_API_KEY: str = ""

    # CORS (production only - local uses CORS_ALLOW_ALL_ORIGINS)
    CORS_ALLOWED_ORIGINS: str = ""  # Comma-separated URLs, e.g. "https://app.example.com"

    # Events
    EVENT_BACKEND: str = "local"  # "local" or "eventbridge"
    EVENT_BUS_NAME: str = ""  # AWS EventBridge bus name (required for eventbridge backend)

    # S3 Media Storage (production or LocalStack for local dev)
    # For LocalStack, set AWS_ENDPOINT_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY env vars
    # boto3 reads these automatically - no need to configure in Django settings
    USE_S3_STORAGE: bool = False
    AWS_STORAGE_BUCKET_NAME: str = ""
    AWS_S3_REGION_NAME: str = "us-east-1"
    AWS_S3_CUSTOM_DOMAIN: str = ""  # CloudFront domain for media CDN
    IMAGE_TRANSFORM_URL: str = ""  # URL for dynamic image transformation

    # WebAuthn / Passkeys
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "Pikaia"
    WEBAUTHN_ORIGIN: str = "http://localhost:5173"

    # Stytch Trusted Auth Token (for passkey -> Stytch session)
    STYTCH_TRUSTED_AUTH_PROFILE_ID: str = ""  # From Stytch dashboard
    STYTCH_TRUSTED_AUTH_AUDIENCE: str = "stytch"  # Must match dashboard config
    STYTCH_TRUSTED_AUTH_ISSUER: str = "passkey-auth"  # Must match dashboard config
    PASSKEY_JWT_PRIVATE_KEY: str = ""  # RSA private key (PEM format)

    # Mobile provisioning
    MOBILE_PROVISION_API_KEY: str = ""  # API key for mobile app user provisioning

    # Device linking
    DEVICE_SESSION_EXPIRY_MINUTES: int = 525600  # 1 year default
    DEVICE_LINK_URL_SCHEME: str = "pikaia://device/link"  # Deep link URL for QR code

    # Free trial
    FREE_TRIAL_DAYS: int = 14

    # Application branding (used for Stripe metadata, etc.)
    APP_SLUG: str = "pikaia"

    # Proxy SSL detection header name (depends on architecture)
    # - "CloudFront-Forwarded-Proto" when API routes through CloudFront
    # - "X-Forwarded-Proto" when API goes directly to ALB
    PROXY_SSL_HEADER: str = "CloudFront-Forwarded-Proto"

    # AWS SMS (End User Messaging)
    AWS_SMS_REGION: str = "us-east-1"  # AWS region for SMS service
    AWS_SMS_ORIGINATION_IDENTITY: str = ""  # Phone number or sender ID
    AWS_SMS_OTP_LENGTH: int = 4  # Length of OTP codes
    AWS_SMS_OTP_EXPIRY_MINUTES: int = 30  # OTP expiration time

    # Sentry
    SENTRY_DSN: str = ""

    # Feature gating
    SUBSCRIPTION_GATING_ENABLED: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()


def parse_comma_list(value: str) -> list[str]:
    """Parse a comma-separated string into a list of stripped, non-empty values."""
    return [item.strip() for item in value.split(",") if item.strip()]


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = settings.SECRET_KEY

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = settings.DEBUG

ALLOWED_HOSTS = parse_comma_list(settings.ALLOWED_HOSTS)

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third-party
    "corsheaders",
    "storages",
    # Local apps
    "apps.core",
    "apps.events",
    "apps.accounts",
    "apps.organizations",
    "apps.billing",
    "apps.media",
    "apps.passkeys",
    "apps.webhooks",
    "apps.sms",
    "apps.devices",
    "apps.sync",
]

MIDDLEWARE = [
    "apps.core.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.core.middleware.CorrelationIdMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.StytchAuthMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# CORS configuration
CORS_ALLOW_CREDENTIALS = True


# Cookie security and cross-domain settings
# Required for frontend/backend cross-origin session sharing
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = parse_comma_list(settings.WEBAUTHN_ORIGIN)


# Database configuration
def _get_database_config() -> dict:
    """Build Django DATABASES config.

    For ECS: Uses individual DB_* environment variables directly (no URL encoding needed).
    For local: Uses DATABASE_URL or default localhost.
    """
    if settings.DB_HOST:
        # ECS: Use individual env vars directly - no URL parsing needed
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": settings.DB_NAME,
            "USER": settings.DB_USER,
            "PASSWORD": settings.DB_PASSWORD,
            "HOST": settings.DB_HOST,
            "PORT": settings.DB_PORT,
        }
    elif settings.DATABASE_URL:
        # Local dev: Parse DATABASE_URL via pydantic
        dsn = settings.DATABASE_URL
        host_info = dsn.hosts()[0] if dsn.hosts() else {}  # type: ignore[typeddict-item]
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": dsn.path.lstrip("/") if dsn.path else "",
            "USER": host_info.get("username") or "",
            "PASSWORD": host_info.get("password") or "",
            "HOST": host_info.get("host") or "localhost",
            "PORT": str(host_info.get("port") or 5432),
        }
    else:
        # Default for local dev without DATABASE_URL
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": settings.DB_NAME or "app",
            "USER": "postgres",
            "PASSWORD": "postgres",  # nosec B105
            "HOST": "localhost",
            "PORT": "5432",
        }


DATABASES = {"default": _get_database_config()}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Cache - use database cache for passkey challenges
# This ensures challenges persist across multiple ECS tasks/containers
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}


# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files (user uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Storage backend - from environment variable
USE_S3_STORAGE = settings.USE_S3_STORAGE

# S3 storage settings (used when USE_S3_STORAGE=True)
AWS_STORAGE_BUCKET_NAME = settings.AWS_STORAGE_BUCKET_NAME
AWS_S3_REGION_NAME = settings.AWS_S3_REGION_NAME
AWS_S3_CUSTOM_DOMAIN = settings.AWS_S3_CUSTOM_DOMAIN or None
IMAGE_TRANSFORM_URL = settings.IMAGE_TRANSFORM_URL or None

# Media upload limits
MEDIA_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MEDIA_ALLOWED_IMAGE_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/svg+xml",
    "image/avif",
]

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# Stytch B2B authentication
STYTCH_PROJECT_ID = settings.STYTCH_PROJECT_ID
STYTCH_SECRET = settings.STYTCH_SECRET
STYTCH_WEBHOOK_SECRET = settings.STYTCH_WEBHOOK_SECRET

# Event-driven architecture
EVENT_BACKEND = settings.EVENT_BACKEND
EVENT_BUS_NAME = settings.EVENT_BUS_NAME

# WebAuthn / Passkeys
WEBAUTHN_RP_ID = settings.WEBAUTHN_RP_ID
WEBAUTHN_RP_NAME = settings.WEBAUTHN_RP_NAME
WEBAUTHN_ORIGIN = settings.WEBAUTHN_ORIGIN

# Stytch Trusted Auth Token (for passkey -> Stytch session)
STYTCH_TRUSTED_AUTH_PROFILE_ID = settings.STYTCH_TRUSTED_AUTH_PROFILE_ID
STYTCH_TRUSTED_AUTH_AUDIENCE = settings.STYTCH_TRUSTED_AUTH_AUDIENCE
STYTCH_TRUSTED_AUTH_ISSUER = settings.STYTCH_TRUSTED_AUTH_ISSUER
PASSKEY_JWT_PRIVATE_KEY = settings.PASSKEY_JWT_PRIVATE_KEY
JWT_SIGNING_KEY_ID = "passkey-auth-key-1"  # Key ID for JWT headers

# Mobile provisioning
MOBILE_PROVISION_API_KEY = settings.MOBILE_PROVISION_API_KEY

# AWS SMS (End User Messaging)
AWS_SMS_REGION = settings.AWS_SMS_REGION
AWS_SMS_ORIGINATION_IDENTITY = settings.AWS_SMS_ORIGINATION_IDENTITY
AWS_SMS_OTP_LENGTH = settings.AWS_SMS_OTP_LENGTH
AWS_SMS_OTP_EXPIRY_MINUTES = settings.AWS_SMS_OTP_EXPIRY_MINUTES

# Auth endpoint rate limits
AUTH_RATE_LIMIT_MAGIC_LINK_SEND_PER_EMAIL = 5  # Per email per 15 min
AUTH_RATE_LIMIT_MAGIC_LINK_SEND_PER_IP = 20  # Per IP per 15 min
AUTH_RATE_LIMIT_MAGIC_LINK_SEND_WINDOW = 900  # 15 minutes
AUTH_RATE_LIMIT_TOKEN_AUTH_PER_IP = 10  # Per IP per minute
AUTH_RATE_LIMIT_TOKEN_AUTH_WINDOW = 60  # 1 minute
AUTH_RATE_LIMIT_ORG_CREATE_PER_IP = 3  # Per IP per hour
AUTH_RATE_LIMIT_ORG_CREATE_WINDOW = 3600  # 1 hour
AUTH_RATE_LIMIT_MOBILE_PROVISION_PER_IP = 5  # Per IP per minute
AUTH_RATE_LIMIT_MOBILE_PROVISION_WINDOW = 60  # 1 minute
AUTH_RATE_LIMIT_PASSKEY_AUTH_PER_IP = 10  # Per IP per minute
AUTH_RATE_LIMIT_PASSKEY_AUTH_WINDOW = 60  # 1 minute

# Device linking
DEVICE_LINK_TOKEN_EXPIRY_SECONDS = 300  # 5 minutes
DEVICE_MAX_LINK_ATTEMPTS_PER_HOUR = 5  # Rate limit for initiating links (per user)
DEVICE_LINK_COMPLETE_MAX_ATTEMPTS_PER_HOUR = 20  # Rate limit for completing links (per IP)
DEVICE_SESSION_EXPIRY_MINUTES = settings.DEVICE_SESSION_EXPIRY_MINUTES
DEVICE_LINK_URL_SCHEME = settings.DEVICE_LINK_URL_SCHEME

# Free trial
FREE_TRIAL_DAYS = settings.FREE_TRIAL_DAYS

# Application branding
APP_SLUG = settings.APP_SLUG

# Sync engine
SYNC_PUSH_MAX_BATCH_SIZE = 100  # Max operations per push request
SYNC_PULL_DEFAULT_LIMIT = 100  # Default changes per pull request
SYNC_PULL_MAX_LIMIT = 500  # Max changes per pull request
SYNC_TOMBSTONE_RETENTION_DAYS = 90  # Days to keep soft-deleted records
SYNC_CLOCK_SKEW_TOLERANCE_MS = 100  # Overlap window for cursor queries

# Feature gating
SUBSCRIPTION_GATING_ENABLED = settings.SUBSCRIPTION_GATING_ENABLED
