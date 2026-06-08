"""Master / configuration data that powers the whole platform.

These tables define *what* a valuation captures: the service taxonomy, the
financial institutions, the Question Bank, and how questions map onto each
bank's report headings.
"""

from __future__ import annotations

from django.db import models

from core.models import BaseModel


class ServiceType(BaseModel):
    """Top-level service category (e.g. Land, Land & Building, Automobile)."""

    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class ServiceSubType(BaseModel):
    """Sub-category under a :class:`ServiceType` (e.g. "L & B", "Flat & Shop")."""

    service_type = models.ForeignKey(
        ServiceType, on_delete=models.CASCADE, related_name="sub_types"
    )
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40)
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        unique_together = ("service_type", "code")

    def __str__(self) -> str:
        return f"{self.service_type.name} / {self.name}"


class ClientKind(models.TextChoices):
    BANK = "bank", "Financial Institution"
    CORPORATE = "corporate", "Corporate"
    INDIVIDUAL = "individual", "Individual"


class Bank(BaseModel):
    """A client institution.

    Named ``Bank`` to match the domain vocabulary, but ``kind`` distinguishes
    financial institutions, corporates and individuals.
    """

    name = models.CharField(max_length=200)
    kind = models.CharField(
        max_length=20, choices=ClientKind.choices, default=ClientKind.BANK
    )
    code = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Bank / Client"

    def __str__(self) -> str:
        return self.name


class ClientDivision(BaseModel):
    """A division within a bank/client (e.g. ADB, MSME, Retail/PB).

    In the legacy system these are a *global* configuration list, not per-bank,
    so ``bank`` is optional. It may be set when a division is specific to one
    institution.
    """

    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name="divisions",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)

    def __str__(self) -> str:
        if self.bank_id:
            return f"{self.bank.name} – {self.name}"
        return self.name


class ClientDesignation(BaseModel):
    """A designation an orderer can hold (e.g. Branch Manager)."""

    name = models.CharField(max_length=120, unique=True)

    def __str__(self) -> str:
        return self.name


class BillingHead(BaseModel):
    """A billing line-item head (e.g. Professional charges, Photo charges).

    Master data for the invoicing workflow, which connects to the legacy billing
    system later. Seeded from ``masters_seed.json``.
    """

    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Orderer(BaseModel):
    """A bank officer who places work orders."""

    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name="orderers")
    division = models.ForeignKey(
        ClientDivision, on_delete=models.SET_NULL, null=True, blank=True
    )
    designation = models.ForeignKey(
        ClientDesignation, on_delete=models.SET_NULL, null=True, blank=True
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self) -> str:
        return f"{self.name} @ {self.bank.name}"


class DetailCategory(BaseModel):
    """A report part / section grouping (Part A, B, C, D …)."""

    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40, unique=True)
    sequence = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ("sequence", "name")
        verbose_name_plural = "Detail categories"

    def __str__(self) -> str:
        return self.name


class AnswerType(models.TextChoices):
    """How a question is answered / rendered."""

    TEXT = "text", "Text"
    RADIO = "radio", "Radio (single choice)"
    CHECKBOX = "checkbox", "Checkbox (multi choice)"
    TABULAR = "tabular", "Tabular"
    SUM_OF_ATTRIBUTE = "sum_of_attribute", "Sum of attribute"
    FORMULA = "formula_based_calculation", "Formula-based calculation"


class Question(BaseModel):
    """A Question Bank entry.

    The set of questions that apply to a given case is selected by
    ``service_type`` + ``sub_type`` (+ optional ``bank`` scope), then ordered by
    ``detail_category.sequence`` and ``sequence``.
    """

    text = models.TextField()
    service_type = models.ForeignKey(
        ServiceType, on_delete=models.CASCADE, related_name="questions"
    )
    sub_type = models.ForeignKey(
        ServiceSubType,
        on_delete=models.CASCADE,
        related_name="questions",
        null=True,
        blank=True,
    )
    detail_category = models.ForeignKey(
        DetailCategory, on_delete=models.PROTECT, related_name="questions"
    )
    answer_type = models.CharField(
        max_length=40, choices=AnswerType.choices, default=AnswerType.TEXT
    )
    # For radio/checkbox: list of {value,label}. For tabular: column defs.
    # For formula/sum: expression / attribute references.
    options = models.JSONField(default=dict, blank=True)
    sequence = models.PositiveIntegerField(default=0)
    is_mandatory = models.BooleanField(default=False)
    # Optional bank scope: when set, the question only applies to that bank.
    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name="questions",
        null=True,
        blank=True,
    )

    class Meta(BaseModel.Meta):
        ordering = ("detail_category__sequence", "sequence", "created_at")

    def __str__(self) -> str:
        return f"[{self.service_type.code}] {self.text[:60]}"


class BankReportHeading(BaseModel):
    """A heading in a bank's report format."""

    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name="headings")
    title = models.CharField(max_length=200)
    sequence = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ("bank", "sequence")

    def __str__(self) -> str:
        return f"{self.bank.name}: {self.title}"


class ReportSetup(BaseModel):
    """Maps a :class:`Question` to a :class:`BankReportHeading`.

    Scoped by Bank + ServiceType + SubType; drives report assembly.
    """

    bank = models.ForeignKey(
        Bank, on_delete=models.CASCADE, related_name="report_setups"
    )
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    sub_type = models.ForeignKey(
        ServiceSubType, on_delete=models.CASCADE, null=True, blank=True
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    heading = models.ForeignKey(BankReportHeading, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ("heading__sequence", "sequence")
        unique_together = ("bank", "service_type", "sub_type", "question")

    def __str__(self) -> str:
        return f"{self.bank.name}: {self.question_id} → {self.heading.title}"
