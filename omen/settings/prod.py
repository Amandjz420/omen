"""Production settings (Railway + Postgres + S3)."""

from .base import *  # noqa: F401,F403
from .base import env, env_bool, env_list

DEBUG = env_bool("DEBUG", False)
# Allow any *.railway.app host (covers the public domain + the
# "healthcheck.railway.app" probe) plus Railway's injected public domain and any
# explicitly configured hosts. A leading dot matches all subdomains.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "") + [".railway.app"]
_railway_domain = env("RAILWAY_PUBLIC_DOMAIN")
if _railway_domain:
    ALLOWED_HOSTS.append(_railway_domain)

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
# Also allow Lovable preview subdomains (https://<id>.lovable.app).
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://[a-z0-9-]+\.lovable\.app$"]

# CSRF trusts the same frontend origins plus any configured Railway domain.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", DEFAULT_FRONTEND_ORIGINS)

# Never enable passwordless login in production unless explicitly set.
DEV_LOGIN = env_bool("DEV_LOGIN", False)
