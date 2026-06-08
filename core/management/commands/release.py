"""Production release step: migrate, collectstatic, and (optionally) seed.

Wired into Railway's pre-deploy command (and the Procfile ``release`` line) so a
fresh database is migrated and seeded automatically on every deploy — no manual
one-off commands needed.

Seeding is on by default and idempotent; disable it by setting
``SEED_ON_RELEASE=0`` once you have real data you don't want demo rows mixed into.
"""

from __future__ import annotations

import os

from django.core.management import call_command
from django.core.management.base import BaseCommand


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "Run migrations, collectstatic, and (optionally) seed_demo for a deploy."

    def handle(self, *args, **opts):
        self.stdout.write("release: applying migrations…")
        call_command("migrate", interactive=False, verbosity=1)

        self.stdout.write("release: collecting static files…")
        call_command("collectstatic", interactive=False, verbosity=0)

        if _truthy(os.environ.get("SEED_ON_RELEASE"), default=True):
            self.stdout.write("release: seeding demo data (SEED_ON_RELEASE)…")
            call_command("seed_demo")
        else:
            self.stdout.write("release: SEED_ON_RELEASE=0 — skipping seed.")

        self.stdout.write(self.style.SUCCESS("release: done."))
