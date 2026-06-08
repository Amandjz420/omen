"""Load the real legacy seed data idempotently.

Reads ``seed/masters_seed.json`` and ``seed/questions_seed.csv`` (the
representative subset of the legacy OMEN Assessors data — see
``docs/legacy_system_reference.md``) and creates the master config + the 904-row
Question Bank. Safe to re-run: everything goes through ``get_or_create`` keyed on
natural identity.

Data hygiene handled here:
* Detail categories are normalized (trim, collapse spaces, remove spaces around
  ``/``, uppercase) and de-duplicated, then ordered by their JSON sequence with
  any CSV-only categories (e.g. the bank-as-detail-category rows) appended.
* ``bank_scope`` (non-empty) links a question to a Bank — meaning it only applies
  when the case's bank matches.
* ClientTypes and AnswerTypes already exist as code enums (``ClientKind`` /
  ``AnswerType``); they are *validated* against the JSON rather than stored as
  rows.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from masters.models import (
    AnswerType,
    Bank,
    BillingHead,
    ClientDesignation,
    ClientDivision,
    ClientKind,
    DetailCategory,
    Question,
    ServiceSubType,
    ServiceType,
)

SEED_DIR = Path(settings.BASE_DIR) / "seed"

# CSV/JSON answer-type label (lowercased) -> AnswerType enum value.
ANSWER_TYPE_MAP = {
    "text": AnswerType.TEXT,
    "radio": AnswerType.RADIO,
    "checkbox": AnswerType.CHECKBOX,
    "tabular": AnswerType.TABULAR,
    "sum of attribute": AnswerType.SUM_OF_ATTRIBUTE,
    "formula based calculation": AnswerType.FORMULA,
}

# The legacy "service type" that owns the asset-valuation sub-types.
PRIMARY_SERVICE_TYPE = "Valuation of asset"


def normalize_detail_category(raw: str) -> str:
    """Normalize a detail-category label: trim, collapse spaces, tidy ``/``, upper."""
    s = raw.strip()
    s = re.sub(r"\s*/\s*", "/", s)   # "BANK / PARTY" -> "BANK/PARTY"
    s = re.sub(r"\s+", " ", s)        # collapse internal whitespace
    return s.upper()


class Command(BaseCommand):
    help = "Idempotently seed master data + the 904-row Question Bank from seed/."

    @transaction.atomic
    def handle(self, *args, **opts):
        masters = self._load_json("masters_seed.json")
        rows = self._load_csv("questions_seed.csv")

        counts = {
            "service_types": 0,
            "service_sub_types": 0,
            "banks": 0,
            "client_divisions": 0,
            "client_designations": 0,
            "billing_heads": 0,
            "detail_categories": 0,
            "questions": 0,
        }

        # --- Validate the enum-backed masters (ClientType, AnswerType) --------
        self._validate_against_enum(
            masters.get("client_types", []),
            {label for _, label in ClientKind.choices},
            "client_types",
            "ClientKind",
        )
        self._validate_against_enum(
            masters.get("answer_types", []),
            {k.title() for k in ANSWER_TYPE_MAP},  # display-ish keys
            "answer_types",
            "AnswerType",
            mapper=lambda v: v.strip().lower() in ANSWER_TYPE_MAP,
        )

        # --- Service types (from JSON) ---------------------------------------
        for name in masters.get("service_types", []):
            _, created = ServiceType.objects.get_or_create(
                code=slugify(name)[:40], defaults={"name": name}
            )
            counts["service_types"] += created

        # --- Banks -----------------------------------------------------------
        for name in masters.get("banks", []):
            _, created = Bank.objects.get_or_create(
                name=name, defaults={"kind": ClientKind.BANK}
            )
            counts["banks"] += created

        # --- Client divisions (global list) + designations -------------------
        for name in masters.get("client_divisions", []):
            _, created = ClientDivision.objects.get_or_create(name=name, bank=None)
            counts["client_divisions"] += created
        for name in masters.get("client_designations", []):
            _, created = ClientDesignation.objects.get_or_create(name=name)
            counts["client_designations"] += created

        # --- Billing heads ---------------------------------------------------
        for name in masters.get("billing_heads", []):
            _, created = BillingHead.objects.get_or_create(name=name)
            counts["billing_heads"] += created

        # --- Service sub types (from JSON, under the primary service type) ---
        primary_st, _ = ServiceType.objects.get_or_create(
            code=slugify(PRIMARY_SERVICE_TYPE)[:40],
            defaults={"name": PRIMARY_SERVICE_TYPE},
        )
        for name in masters.get("service_sub_types", []):
            _, created = ServiceSubType.objects.get_or_create(
                service_type=primary_st,
                name=name,
                defaults={"code": slugify(name)[:40] or "sub"},
            )
            counts["service_sub_types"] += created

        # --- Detail categories: normalize, de-dup, order ---------------------
        dc_map = self._seed_detail_categories(masters, rows, counts)

        # --- Questions (904 rows) --------------------------------------------
        st_cache: dict[str, ServiceType] = {}
        sub_cache: dict[tuple[str, str], ServiceSubType] = {}
        bank_cache: dict[str, Bank] = {}

        for row in rows:
            st_name = row["service_type"].strip()
            sub_name = row["service_sub_type"].strip()
            dc_name = normalize_detail_category(row["detail_category"])
            atype = ANSWER_TYPE_MAP[row["answer_type"].strip().lower()]
            scope = row.get("bank_scope", "").strip()
            try:
                seq = int(row["sequence"]) if row["sequence"].strip() else 0
            except (ValueError, AttributeError):
                seq = 0
            text = row["question_text"].strip()

            st = st_cache.get(st_name)
            if st is None:
                st, c = ServiceType.objects.get_or_create(
                    code=slugify(st_name)[:40], defaults={"name": st_name}
                )
                counts["service_types"] += c
                st_cache[st_name] = st

            sub = None
            if sub_name:
                key = (st.pk, sub_name)
                sub = sub_cache.get(key)
                if sub is None:
                    sub, c = ServiceSubType.objects.get_or_create(
                        service_type=st,
                        name=sub_name,
                        defaults={"code": slugify(sub_name)[:40] or "sub"},
                    )
                    counts["service_sub_types"] += c
                    sub_cache[key] = sub

            bank = None
            if scope:
                bank = bank_cache.get(scope)
                if bank is None:
                    bank, c = Bank.objects.get_or_create(
                        name=scope, defaults={"kind": ClientKind.BANK}
                    )
                    counts["banks"] += c
                    bank_cache[scope] = bank

            _, created = Question.objects.get_or_create(
                service_type=st,
                sub_type=sub,
                detail_category=dc_map[dc_name],
                bank=bank,
                sequence=seq,
                text=text,
                defaults={"answer_type": atype},
            )
            counts["questions"] += created

        self._print_summary(counts, total_rows=len(rows))

    # ------------------------------------------------------------------ utils
    def _load_json(self, name: str) -> dict:
        path = SEED_DIR / name
        if not path.exists():
            raise CommandError(f"Seed file not found: {path}")
        return json.loads(path.read_text())

    def _load_csv(self, name: str) -> list[dict]:
        path = SEED_DIR / name
        if not path.exists():
            raise CommandError(f"Seed file not found: {path}")
        with path.open(newline="") as fh:
            return list(csv.DictReader(fh))

    def _validate_against_enum(self, values, allowed, label, enum_name, mapper=None):
        """Ensure every JSON value is representable by the code enum."""
        for v in values:
            ok = mapper(v) if mapper else (v in allowed)
            if not ok:
                raise CommandError(
                    f"'{v}' in masters_seed.json[{label}] is not covered by the "
                    f"{enum_name} enum. Add it to the enum (and migrate) first."
                )
        self.stdout.write(
            f"  validated {len(values)} {label} against {enum_name} (no rows created)"
        )

    def _seed_detail_categories(self, masters, rows, counts) -> dict[str, DetailCategory]:
        """Create normalized, de-duplicated detail categories in display order."""
        ordered: list[str] = []
        seen: set[str] = set()
        # JSON order first (defines the canonical sequence)...
        for raw in masters.get("detail_categories", []):
            n = normalize_detail_category(raw)
            if n not in seen:
                seen.add(n)
                ordered.append(n)
        # ...then any CSV-only categories (e.g. bank-as-detail-category rows).
        for row in rows:
            n = normalize_detail_category(row["detail_category"])
            if n not in seen:
                seen.add(n)
                ordered.append(n)

        used_codes = set(DetailCategory.objects.values_list("code", flat=True))
        dc_map: dict[str, DetailCategory] = {}
        for seq, name in enumerate(ordered, start=1):
            existing = DetailCategory.objects.filter(name=name).first()
            if existing:
                dc_map[name] = existing
                continue
            code = self._unique_code(slugify(name)[:36] or "cat", used_codes)
            dc_map[name] = DetailCategory.objects.create(
                name=name, code=code, sequence=seq
            )
            counts["detail_categories"] += 1
        return dc_map

    @staticmethod
    def _unique_code(base: str, used: set[str]) -> str:
        code = base
        i = 2
        while code in used:
            code = f"{base}-{i}"[:40]
            i += 1
        used.add(code)
        return code

    def _print_summary(self, counts: dict, total_rows: int):
        self.stdout.write(self.style.SUCCESS("Legacy seed complete (created this run):"))
        for key, val in counts.items():
            self.stdout.write(f"  {key:22s}: {val}")
        self.stdout.write(
            f"  (CSV rows processed: {total_rows}; re-runs create 0 new rows)"
        )
