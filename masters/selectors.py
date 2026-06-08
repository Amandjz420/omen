"""Query helpers for selecting the applicable Question set for a case."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import Question


def questions_for(
    *, service_type_id, sub_type_id=None, bank_id=None
) -> QuerySet[Question]:
    """Return the ordered Question set that applies to a case.

    Rules:
    * Must match ``service_type``.
    * Sub-type matches the given sub-type *or* questions with no sub-type
      (applies to all sub-types of the service).
    * Bank scope matches the given bank *or* questions with no bank scope
      (bank-agnostic questions apply to everyone).

    Ordered by ``detail_category.sequence`` then ``sequence``.
    """
    qs = Question.objects.filter(service_type_id=service_type_id)

    if sub_type_id:
        qs = qs.filter(Q(sub_type_id=sub_type_id) | Q(sub_type__isnull=True))
    else:
        qs = qs.filter(sub_type__isnull=True)

    if bank_id:
        qs = qs.filter(Q(bank_id=bank_id) | Q(bank__isnull=True))
    else:
        qs = qs.filter(bank__isnull=True)

    return qs.select_related("detail_category").order_by(
        "detail_category__sequence", "sequence", "created_at"
    )
