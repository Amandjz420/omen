"""Local development settings."""

from .base import *  # noqa: F401,F403
from .base import RAILWAY_HOSTS, env_bool, env_list

DEBUG = env_bool("DEBUG", True)
# Include Railway hosts too, so a service accidentally started with dev settings
# on Railway still answers the health probe.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0") + RAILWAY_HOSTS

# Convenience for early frontend testing.
DEV_LOGIN = env_bool("DEV_LOGIN", True)

# Allow any localhost origin during development.
CORS_ALLOW_ALL_ORIGINS = True
