"""Local development settings."""

from .base import *  # noqa: F401,F403
from .base import env_bool, env_list

DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")

# Convenience for early frontend testing.
DEV_LOGIN = env_bool("DEV_LOGIN", True)

# Allow any localhost origin during development.
CORS_ALLOW_ALL_ORIGINS = True
