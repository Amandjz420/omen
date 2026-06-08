"""Seed a small, curated demo on top of the real legacy data.

Runs ``seed_from_legacy`` first (idempotent) so the full Question Bank exists,
then adds one admin + one valuer + one verifier, two sample banks, a couple of
orderers, and one complete **L & B valuation for State Bank of India** — enough
to click through capture → autofill → review → verify, with a real rendered
question set.

Idempotent: re-running reuses existing rows by natural keys.
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, User
from leads.models import WorkOrder, WorkOrderStatus
from masters.models import Bank, Orderer, ServiceSubType, ServiceType
from masters.selectors import questions_for
from valuations.models import Valuation, ValuationStatus

# The demo case targets a real legacy combination.
DEMO_SERVICE_TYPE = "Valuation of asset"
DEMO_SUB_TYPE = "L & B"
DEMO_BANK = "State Bank of India"
SECOND_BANK = "Canara Bank"


class Command(BaseCommand):
    help = "Seed a curated end-to-end demo (users + an L&B/SBI valuation) on top of legacy data."

    @transaction.atomic
    def handle(self, *args, **opts):
        # 1. Ensure the real masters + Question Bank are loaded.
        self.stdout.write("Loading legacy masters + Question Bank (seed_from_legacy)…")
        call_command("seed_from_legacy")

        # 2. Users (one per role).
        admin = self._user("admin", Role.ADMIN, "admin12345", staff=True, superuser=True)
        valuer = self._user("valuer", Role.VALUER, "valuer12345")
        self._user("verifier", Role.VERIFIER, "verifier12345")

        # 3. Two sample banks (already created by the legacy seed) + orderers.
        try:
            sbi = Bank.objects.get(name=DEMO_BANK)
            canara = Bank.objects.get(name=SECOND_BANK)
        except Bank.DoesNotExist as exc:  # pragma: no cover - legacy seed guarantees these
            raise CommandError(
                f"Expected bank missing after seed_from_legacy: {exc}"
            ) from exc

        orderer_sbi, _ = Orderer.objects.get_or_create(
            bank=sbi, name="R. Sharma", defaults={"email": "rsharma@sbi.example"}
        )
        Orderer.objects.get_or_create(
            bank=canara, name="P. Nair", defaults={"email": "pnair@canara.example"}
        )

        # 4. The L & B / SBI work order + valuation.
        service_type = ServiceType.objects.get(name=DEMO_SERVICE_TYPE)
        sub_type = ServiceSubType.objects.get(
            service_type=service_type, name=DEMO_SUB_TYPE
        )

        wo, _ = WorkOrder.objects.get_or_create(
            reference="WO-DEMO-001",
            defaults={
                "bank": sbi,
                "orderer": orderer_sbi,
                "service_type": service_type,
                "sub_type": sub_type,
                "property_address": "12 MG Road, Bengaluru, Karnataka",
                "status": WorkOrderStatus.ASSIGNED,
            },
        )
        valuation, _ = Valuation.objects.get_or_create(
            work_order=wo,
            defaults={
                "assigned_valuer": valuer,
                "status": ValuationStatus.IN_PROGRESS,
                "address": "12 MG Road, Bengaluru, Karnataka",
                "locality": "MG Road, Bengaluru",
                "latitude": "12.975600",
                "longitude": "77.605600",
            },
        )

        # 5. Mark a curated set of mandatory questions so the submit-guard is
        #    meaningful (legacy rows carry no mandatory flag). Matched by keyword.
        case_questions = questions_for(
            service_type_id=service_type.id,
            sub_type_id=sub_type.id,
            bank_id=sbi.id,
        )
        q_count = case_questions.count()
        mandatory_keywords = (
            "name of the reported owner",
            "purpose of valuation",
            "address of the property",
            "type of building",
            "year of construction",
        )
        mandatory = 0
        for q in case_questions:
            if any(kw in q.text.lower() for kw in mandatory_keywords) and not q.is_mandatory:
                q.is_mandatory = True
                q.save(update_fields=["is_mandatory"])
                mandatory += 1

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded."))
        self.stdout.write("  admin / admin12345 (role=admin)")
        self.stdout.write("  valuer / valuer12345 (role=valuer)")
        self.stdout.write("  verifier / verifier12345 (role=verifier)")
        self.stdout.write(f"  Work order : {wo.reference} — {DEMO_SUB_TYPE} / {DEMO_BANK}")
        self.stdout.write(f"  Valuation  : {valuation.id}")
        self.stdout.write(
            f"  Renders {q_count} questions for this case ({mandatory} mandatory)."
        )
        self.stdout.write(
            '  Dev login (no password): POST /api/auth/login {"username": "valuer"}'
        )

    @staticmethod
    def _user(username, role, password, *, staff=False, superuser=False) -> User:
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"role": role, "is_staff": staff, "is_superuser": superuser},
        )
        user.role = role
        user.is_staff = staff or superuser
        user.is_superuser = superuser
        user.set_password(password)
        user.save()
        return user
