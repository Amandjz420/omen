"""Production settings (Railway + Postgres + S3)."""

from .base import *  # noqa: F401,F403
from .base import env_bool, env_list

DEBUG = env_bool("DEBUG", False)
# Railway sends health-check probes with Host "healthcheck.railway.app", so it
# must always be allowed or Django rejects them with 400 DisallowedHost (even
# though the app started fine). Configured hosts are added on top.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "") + ["healthcheck.railway.app"]

# Behind Railway's proxy (TLS terminated upstream).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Trust the Railway public domain for CSRF (e.g. https://omen.up.railway.app).
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# Never enable passwordless login in production unless explicitly set.
DEV_LOGIN = env_bool("DEV_LOGIN", False)
