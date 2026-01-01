"""
Base Django settings for Tango SaaS Starter.

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
    DATABASE_URL: PostgresDsn = "postgresql://postgres:postgres@localhost:5432/tango"

    # Stytch
    STYTCH_PROJECT_ID: str = ""
    STYTCH_SECRET: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID: str = ""  # Price ID for per-seat subscription

    # Resend
    RESEND_API_KEY: str = ""

    # CORS (production only - local uses CORS_ALLOW_ALL_ORIGINS)
    CORS_ALLOWED_ORIGINS: str = ""  # Comma-separated URLs, e.g. "https://app.example.com"

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
    # Third-party
    "corsheaders",
    "storages",
    # Local apps
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.billing",
    "apps.media",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.StytchAuthMiddleware",
    "apps.core.middleware.TenantContextMiddleware",
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

# Database - parsed from DATABASE_URL
def _parse_postgres_dsn(dsn: PostgresDsn) -> dict:
    """Convert pydantic PostgresDsn to Django DATABASES format."""
    # pydantic v2: hosts() returns list of dicts with username, password, host, port
    host_info = dsn.hosts()[0] if dsn.hosts() else {}
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": dsn.path.lstrip("/") if dsn.path else "",
        "USER": host_info.get("username") or "",
        "PASSWORD": host_info.get("password") or "",
        "HOST": host_info.get("host") or "localhost",
        "PORT": str(host_info.get("port") or 5432),
    }


DATABASES = {"default": _parse_postgres_dsn(settings.DATABASE_URL)}

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

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"

# Media files (user uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Storage backend - defaults to local filesystem
USE_S3_STORAGE = False

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
