"""
Django settings for the Peakform project.

Configuration is driven by environment variables so the same codebase
runs locally (SQLite, debug on) and in production (Postgres/Supabase,
debug off) without code changes. See .env.example for the full list of
supported variables.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-dev-only-do-not-use-in-production",
)

DEBUG = env_bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "nutrition",
    "workouts",
    "motivation",
    "community",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "peakform.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "peakform.wsgi.application"


# Database
# Uses DATABASE_URL when set (e.g. a Supabase Postgres connection string in
# production); falls back to local SQLite for development with no setup.

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


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


# Static files (CSS, JavaScript, images)

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# User-uploaded media (profile photos, community post images).
# Local disk by default (fine for local dev, and as a fallback), which
# works but isn't durable on most PaaS hosts (wiped on redeploy). Set the
# SUPABASE_S3_* variables in production to store uploads in Supabase
# Storage instead, via its S3-compatible API.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

SUPABASE_S3_ACCESS_KEY_ID = os.environ.get("SUPABASE_S3_ACCESS_KEY_ID", "")
SUPABASE_S3_SECRET_ACCESS_KEY = os.environ.get("SUPABASE_S3_SECRET_ACCESS_KEY", "")
SUPABASE_S3_ENDPOINT_URL = os.environ.get("SUPABASE_S3_ENDPOINT_URL", "")
SUPABASE_S3_REGION = os.environ.get("SUPABASE_S3_REGION", "")
SUPABASE_S3_BUCKET = os.environ.get("SUPABASE_S3_BUCKET", "community-images")

if SUPABASE_S3_ACCESS_KEY_ID and SUPABASE_S3_SECRET_ACCESS_KEY and SUPABASE_S3_ENDPOINT_URL:
    # The bucket is public, so reads should go through Supabase's own public
    # object URL (unauthenticated, CDN-friendly) rather than a signed S3
    # URL - `custom_domain` makes django-storages build URLs that way while
    # uploads/deletes still go over the (always authenticated) S3 API.
    _supabase_storage_host = urlparse(SUPABASE_S3_ENDPOINT_URL).hostname or ""
    _supabase_project_ref = _supabase_storage_host.split(".")[0]

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": SUPABASE_S3_ACCESS_KEY_ID,
            "secret_key": SUPABASE_S3_SECRET_ACCESS_KEY,
            "bucket_name": SUPABASE_S3_BUCKET,
            "endpoint_url": SUPABASE_S3_ENDPOINT_URL,
            "region_name": SUPABASE_S3_REGION or "auto",
            "addressing_style": "path",
            "default_acl": None,
            "file_overwrite": False,
            "custom_domain": f"{_supabase_project_ref}.supabase.co/storage/v1/object/public/{SUPABASE_S3_BUCKET}",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "nutrition:dashboard"
LOGOUT_REDIRECT_URL = "core:landing"


# Third-party API keys (never hardcode; read from the environment only).
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_DAILY_LIMIT = int(os.environ.get("GEMINI_DAILY_LIMIT", "20"))


# Security hardening for production (no-ops locally when DEBUG is True).
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # The CSRF cookie is only ever read server-side (via the {% csrf_token %}
    # hidden input) - nothing in this app's JS reads it - so there's no
    # reason client-side script should be able to either.
    CSRF_COOKIE_HTTPONLY = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # By default Django only reports unhandled errors via email (which
    # requires ADMINS/email backend configuration we don't have). Send
    # warnings and above to the console instead, so they land in the
    # hosting platform's log stream (e.g. Railway/Render logs).
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {"class": "logging.StreamHandler"},
        },
        "root": {"handlers": ["console"], "level": "INFO"},
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
                "propagate": False,
            },
        },
    }
