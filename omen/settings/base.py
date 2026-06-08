"""Base settings shared by every environment.

Environment-specific modules (``dev``/``prod``) import everything from here and
then override what they need. All secrets and deployment knobs are read from
environment variables; see ``.env.example`` and ``CLAUDE.md`` for the full list.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths & .env
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load a local .env if present (no-op in production where real env vars win).
load_dotenv(BASE_DIR / ".env")


def env(key: str, default: str | None = None) -> str | None:
    """Read an environment variable with an optional default."""
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    """Read a boolean-ish environment variable (``1/true/yes/on``)."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable into a list."""
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", "django-insecure-change-me-in-production")
DEBUG = env_bool("DEBUG", False)

# Railway hosts: the public domain + the "healthcheck.railway.app" probe. A
# leading dot matches all subdomains, so ".railway.app" covers both. Always safe
# to allow and included in every environment (dev + prod) so a service started
# with any settings module never 400s a Railway probe.
RAILWAY_HOSTS = [".railway.app"]
if env("RAILWAY_PUBLIC_DOMAIN"):
    RAILWAY_HOSTS.append(env("RAILWAY_PUBLIC_DOMAIN"))

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1") + RAILWAY_HOSTS

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    # Local apps
    "core",
    "accounts",
    "masters",
    "leads",
    "valuations",
    "ai",
    "reports",
    "verification",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "omen.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "reports" / "templates"],
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

WSGI_APPLICATION = "omen.wsgi.application"
ASGI_APPLICATION = "omen.asgi.application"

# ---------------------------------------------------------------------------
# Database (Postgres via DATABASE_URL; SQLite fallback for local dev)
# ---------------------------------------------------------------------------
DATABASE_URL = (env("DATABASE_URL") or "").strip()
# Only treat it as a real DB URL when it has a scheme (e.g. ``postgres://…``).
# This guards against an *unresolved* Railway reference placeholder such as
# "${{Postgres.DATABASE_URL}}" during the build phase (service references only
# resolve at deploy/runtime) — which would otherwise crash dj_database_url. In
# that case we fall back to SQLite so settings import cleanly; the real Postgres
# URL is present at deploy time.
if "://" in DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Auth / passwords
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# I18N / TZ
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF + JWT + OpenAPI
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "OMEN AI Valuation API",
    "DESCRIPTION": "AI-assisted property-valuation platform for bank valuers in India.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# CORS (only the Lovable frontend origin)
# ---------------------------------------------------------------------------
FRONTEND_ORIGIN = env("FRONTEND_ORIGIN", "http://localhost:8080")
CORS_ALLOWED_ORIGINS = env_list("FRONTEND_ORIGIN", FRONTEND_ORIGIN)
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Auth flags
# ---------------------------------------------------------------------------
# DEV_LOGIN=1 lets the frontend obtain a token for the seeded valuer without a
# password (early testing only). OTP/email auth slot in later behind the same
# /api/auth endpoints.
DEV_LOGIN = env_bool("DEV_LOGIN", False)

# ---------------------------------------------------------------------------
# AWS S3 (private bucket, presigned PUT/GET)
# ---------------------------------------------------------------------------
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "ap-south-1")
AWS_S3_PRESIGN_EXPIRY = int(env("AWS_S3_PRESIGN_EXPIRY", "3600"))
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = True

# Absolute base URL for this API (e.g. https://omen.up.railway.app). Used to
# build signed media/report URLs in contexts without a request (the AI worker).
# Falls back to Railway's injected RAILWAY_PUBLIC_DOMAIN so it needs no manual
# config on Railway; when blank, request-derived hosts are used where available.
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "")
if not PUBLIC_BASE_URL and env("RAILWAY_PUBLIC_DOMAIN"):
    PUBLIC_BASE_URL = f"https://{env('RAILWAY_PUBLIC_DOMAIN')}"

# ``True`` when real S3 credentials are configured. When False the media layer
# falls back to a local presign stub so the upload flow is testable offline.
USE_S3 = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME)
if USE_S3:
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}

# ---------------------------------------------------------------------------
# AI router configuration
# ---------------------------------------------------------------------------
DEEPINFRA_API_KEY = env("DEEPINFRA_API_KEY")
DEEPINFRA_BASE_URL = env("DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai")
PERPLEXITY_API_KEY = env("PERPLEXITY_API_KEY")
PERPLEXITY_BASE_URL = env("PERPLEXITY_BASE_URL", "https://api.perplexity.ai")

LLM_TIMEOUT_SECONDS = int(env("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES = int(env("LLM_MAX_RETRIES", "3"))

# AI_MOCK=1 forces the router to return deterministic stub output instead of
# calling any provider. Auto-enabled when no provider keys are present so the
# whole pipeline runs offline.
AI_MOCK = env_bool("AI_MOCK", default=not (DEEPINFRA_API_KEY or PERPLEXITY_API_KEY))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "omen.ai": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # WeasyPrint's font subsetting is extremely chatty at DEBUG/INFO.
        "fontTools": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "weasyprint": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
