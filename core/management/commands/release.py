"""Production release step: collectstatic, migrate, and (optionally) seed.

Wired into Railway's pre-deploy command (and the Procfile ``release`` line) so a
fresh database is migrated and seeded automatically on every deploy — no manual
one-off commands needed.

Resilient by design: ``collectstatic`` always runs (no DB needed), but migrate
and seed are skipped when the database is unreachable. This matters because the
command may run during the **build phase**, where Railway's private network
(``postgres.railway.internal``) isn't resolvable yet — there it skips DB work and
the build still succeeds; the migrate/seed happen at pre-deploy/runtime when the
DB is reachable.

Seeding is on by default and idempotent; disable it with ``SEED_ON_RELEASE=0``
once you have real data you don't want demo rows mixed into.
"""

from __future__ import annotations

import os

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections


def _truthy(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _db_reachable() -> bool:
    """True if the default database accepts a connection right now."""
    try:
        connections["default"].ensure_connection()
        return True
    except Exception:  # noqa: BLE001 - any connection error means "not reachable"
        return False


class Command(BaseCommand):
    help = "collectstatic, then migrate + (optionally) seed_demo when the DB is reachable."

    def handle(self, *args, **opts):
        # Static files have no DB dependency — always (re)collect them. This is
        # what bakes them into the build image.
        self.stdout.write("release: collecting static files…")
        call_command("collectstatic", interactive=False, verbosity=0)

        if not _db_reachable():
            self.stdout.write(
                self.style.WARNING(
                    "release: database not reachable (likely the build phase) — "
                    "skipping migrate/seed; they run at pre-deploy/runtime."
                )
            )
            self.stdout.write(self.style.SUCCESS("release: done (static only)."))
            return

        self.stdout.write("release: applying migrations…")
        call_command("migrate", interactive=False, verbosity=1)

        if _truthy(os.environ.get("SEED_ON_RELEASE"), default=True):
            self.stdout.write("release: seeding demo data (SEED_ON_RELEASE)…")
            call_command("seed_demo")
        else:
            self.stdout.write("release: SEED_ON_RELEASE=0 — skipping seed.")

        self.stdout.write(self.style.SUCCESS("release: done."))
