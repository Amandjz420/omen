"""Production settings (Railway + Postgres + S3)."""

from .base import *  # noqa: F401,F403
from .base import RAILWAY_HOSTS, env_bool, env_list

DEBUG = env_bool("DEBUG", False)
# Configured hosts + Railway hosts (".railway.app" covers the public domain and
# the "healthcheck.railway.app" probe; RAILWAY_PUBLIC_DOMAIN is appended in base).
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "") + RAILWAY_HOSTS

# Behind Railway's proxy (TLS terminated upstream).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
# Railway's health-check probes the container directly over HTTP (no edge proxy,
# so no X-Forwarded-Proto). Without this exemption SECURE_SSL_REDIRECT would
# 301-redirect /healthz to HTTPS and the probe would fail. Real traffic still
# gets redirected. The pattern is matched against the path without leading "/".
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# The Lovable frontend: the app URL and its custom domain. Override via the
# FRONTEND_ORIGIN env var (comma list) to add/replace origins without a deploy.
DEFAULT_FRONTEND_ORIGINS = "https://omtas.lovable.app,https://omen.devmate.in"
CORS_ALLOWED_ORIGINS = env_list("FRONTEND_ORIGIN", DEFAULT_FRONTEND_ORIGINS)
# Also allow Lovable preview subdomains on both preview domains
# (https://<id>.lovable.app and https://<id>.lovableproject.com).
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.lovable\.app$",
    r"^https://.*\.lovableproject\.com$",
]

# CSRF trusts the same frontend origins plus any configured Railway domain.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", DEFAULT_FRONTEND_ORIGINS)

# Never enable passwordless login in production unless explicitly set.
DEV_LOGIN = env_bool("DEV_LOGIN", False)
