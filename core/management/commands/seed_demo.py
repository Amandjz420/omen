"""Seed a minimal end-to-end demo dataset.

Creates one admin + one valuer + one verifier, a couple of banks/orderers, a few
service sub-types, a small Question Bank (Land + L&B), one work order and one
valuation — enough to click through the whole flow.

Idempotent: re-running updates/reuses existing rows by natural keys.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Role, User
from leads.models import WorkOrder, WorkOrderStatus
from masters.models import (
    AnswerType,
    Bank,
    BankReportHeading,
    ClientKind,
    DetailCategory,
    Orderer,
    Question,
    ReportSetup,
    ServiceSubType,
    ServiceType,
)
from valuations.models import Valuation, ValuationStatus


class Command(BaseCommand):
    help = "Seed a minimal demo dataset for end-to-end testing."

    @transaction.atomic
    def handle(self, *args, **opts):
        # --- Users --------------------------------------------------------
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"role": Role.ADMIN, "is_staff": True, "is_superuser": True},
        )
        admin.set_password("admin12345")
        admin.role = Role.ADMIN
        admin.is_staff = admin.is_superuser = True
        admin.save()

        valuer, _ = User.objects.get_or_create(
            username="valuer", defaults={"role": Role.VALUER}
        )
        valuer.set_password("valuer12345")
        valuer.save()

        verifier, _ = User.objects.get_or_create(
            username="verifier", defaults={"role": Role.VERIFIER}
        )
        verifier.set_password("verifier12345")
        verifier.save()

        # --- Service taxonomy --------------------------------------------
        land, _ = ServiceType.objects.get_or_create(
            code="land", defaults={"name": "Land"}
        )
        lnb, _ = ServiceType.objects.get_or_create(
            code="lnb", defaults={"name": "Land & Building"}
        )
        sub_land, _ = ServiceSubType.objects.get_or_create(
            service_type=land, code="land", defaults={"name": "Land"}
        )
        sub_lnb, _ = ServiceSubType.objects.get_or_create(
            service_type=lnb, code="lnb", defaults={"name": "L & B"}
        )

        # --- Banks / orderers --------------------------------------------
        sbi, _ = Bank.objects.get_or_create(
            name="State Bank of India", defaults={"kind": ClientKind.BANK, "code": "SBI"}
        )
        hdfc, _ = Bank.objects.get_or_create(
            name="HDFC Bank", defaults={"kind": ClientKind.BANK, "code": "HDFC"}
        )
        orderer, _ = Orderer.objects.get_or_create(
            bank=sbi, name="R. Sharma", defaults={"email": "rsharma@sbi.example"}
        )

        # --- Detail categories (report parts) ----------------------------
        part_a, _ = DetailCategory.objects.get_or_create(
            code="part-a", defaults={"name": "Part A — General", "sequence": 1}
        )
        part_b, _ = DetailCategory.objects.get_or_create(
            code="part-b", defaults={"name": "Part B — Technical", "sequence": 2}
        )

        # --- Question Bank (Land + L&B sample) ---------------------------
        questions = [
            (land, sub_land, part_a, "Name of the owner", AnswerType.TEXT, {}, 1, True),
            (land, sub_land, part_a, "Survey / Plot number", AnswerType.TEXT, {}, 2, True),
            (
                land, sub_land, part_a, "Type of land",
                AnswerType.RADIO,
                {"choices": [{"value": "residential", "label": "Residential"},
                             {"value": "commercial", "label": "Commercial"},
                             {"value": "agricultural", "label": "Agricultural"}]},
                3, True,
            ),
            (land, sub_land, part_b, "Extent / area (sq ft)", AnswerType.TEXT, {}, 4, True),
            (
                land, sub_land, part_b, "Adopted rate per sq ft (INR)",
                AnswerType.FORMULA, {"expression": "market_rate"}, 5, False,
            ),
            (lnb, sub_lnb, part_a, "Name of the owner", AnswerType.TEXT, {}, 1, True),
            (
                lnb, sub_lnb, part_b, "Type of construction",
                AnswerType.RADIO,
                {"choices": [{"value": "rcc", "label": "RCC"},
                             {"value": "load_bearing", "label": "Load bearing"}]},
                2, True,
            ),
            (lnb, sub_lnb, part_b, "Number of floors", AnswerType.TEXT, {}, 3, True),
            (
                lnb, sub_lnb, part_b, "Total valuation (INR)",
                AnswerType.FORMULA, {"expression": "land_value + building_value"}, 4, False,
            ),
        ]
        created_qs = []
        for st, sub, cat, text, atype, opts, seq, mand in questions:
            q, _ = Question.objects.get_or_create(
                service_type=st,
                sub_type=sub,
                text=text,
                defaults={
                    "detail_category": cat,
                    "answer_type": atype,
                    "options": opts,
                    "sequence": seq,
                    "is_mandatory": mand,
                },
            )
            created_qs.append(q)

        # --- Bank report headings + setup (SBI / L&B) --------------------
        h_general, _ = BankReportHeading.objects.get_or_create(
            bank=sbi, title="1. General Details", defaults={"sequence": 1}
        )
        h_tech, _ = BankReportHeading.objects.get_or_create(
            bank=sbi, title="2. Technical Details", defaults={"sequence": 2}
        )
        for q in created_qs:
            if q.service_type == lnb:
                heading = h_general if q.detail_category == part_a else h_tech
                ReportSetup.objects.get_or_create(
                    bank=sbi,
                    service_type=lnb,
                    sub_type=sub_lnb,
                    question=q,
                    defaults={"heading": heading, "sequence": q.sequence},
                )

        # --- Work order + valuation (SBI / L&B) --------------------------
        wo, _ = WorkOrder.objects.get_or_create(
            reference="WO-DEMO-001",
            defaults={
                "bank": sbi,
                "orderer": orderer,
                "service_type": lnb,
                "sub_type": sub_lnb,
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

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        self.stdout.write(f"  admin / admin12345 (role=admin)")
        self.stdout.write(f"  valuer / valuer12345 (role=valuer)")
        self.stdout.write(f"  verifier / verifier12345 (role=verifier)")
        self.stdout.write(f"  Work order: {wo.reference}")
        self.stdout.write(f"  Valuation id: {valuation.id}")
        self.stdout.write(
            "  Dev login (no password): POST /api/auth/login {\"username\": \"valuer\"}"
        )
