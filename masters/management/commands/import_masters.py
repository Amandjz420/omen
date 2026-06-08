"""Placeholder importer for legacy master data (CSV/JSON).

The legacy system exports large master tables we will wire in later:
Clients (~1,288), Orderers (~1,973), Questions (~1,791), Bank headings (~400).

This command is a SCAFFOLD only — it validates inputs and dispatches to a
per-entity handler, but the actual mapping/upsert logic is intentionally left as
``TODO`` until we have the exported schema. Do not rely on it for real imports
yet.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

SUPPORTED_ENTITIES = ("clients", "orderers", "questions", "headings")


class Command(BaseCommand):
    help = "SCAFFOLD: import legacy master data (clients/orderers/questions/headings)."

    def add_arguments(self, parser):
        parser.add_argument("entity", choices=SUPPORTED_ENTITIES)
        parser.add_argument("path", help="Path to a .csv or .json export file.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Parse and report counts only."
        )

    def handle(self, *args, **opts):
        entity = opts["entity"]
        path = Path(opts["path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        rows = self._load(path)
        self.stdout.write(f"Loaded {len(rows)} row(s) for '{entity}' from {path.name}.")

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — no rows written."))
            return

        # TODO: implement per-entity field mapping + upsert once the legacy
        # export schema is finalized. Dispatch table kept ready below.
        handlers = {
            "clients": self._import_clients,
            "orderers": self._import_orderers,
            "questions": self._import_questions,
            "headings": self._import_headings,
        }
        handlers[entity](rows)

    @staticmethod
    def _load(path: Path) -> list[dict]:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text())
        with path.open(newline="") as fh:
            return list(csv.DictReader(fh))

    def _not_implemented(self, entity: str) -> None:
        self.stdout.write(
            self.style.WARNING(
                f"Importer for '{entity}' is scaffolded but not implemented yet. "
                "Provide a sample export and we'll wire the field mapping."
            )
        )

    def _import_clients(self, rows):  # noqa: D401 - scaffold
        self._not_implemented("clients")

    def _import_orderers(self, rows):
        self._not_implemented("orderers")

    def _import_questions(self, rows):
        self._not_implemented("questions")

    def _import_headings(self, rows):
        self._not_implemented("headings")
