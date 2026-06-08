"""AI task functions.

Each function is a plain callable that operates on a :class:`Valuation` and
persists its output. They are invoked synchronously here but always run through
the :class:`ai.models.AIJob` queue in production (see ``ai.jobs``). Keeping them
provider-agnostic — they only talk to :mod:`ai.router` — means model choices
change in one place.
"""

from __future__ import annotations

import logging

from django.conf import settings

from valuations import storage
from valuations.models import (
    Answer,
    Confidence,
    MarketRateLookup,
    MediaAsset,
    MediaKind,
)

from . import router
from .router import TaskType

logger = logging.getLogger("omen.ai")


# ---------------------------------------------------------------------------
# 1. Transcription
# ---------------------------------------------------------------------------
def transcribe_valuation_audio(valuation) -> dict:
    """Run ASR on each audio asset, translate to English, store on the asset.

    Keeps the original-language text alongside the English translation.
    """
    results = []
    for asset in valuation.media_assets.filter(kind=MediaKind.AUDIO):
        audio_bytes = storage.get_bytes(asset.s3_key)
        asr = router.transcribe(audio_bytes, valuation=valuation)
        english = asr["text"]
        if asr.get("language") and not asr["language"].startswith("en"):
            translated = router.complete(
                TaskType.TRANSLATE,
                [
                    {"role": "system", "content": "Translate the user's text to English."},
                    {"role": "user", "content": asr["text"]},
                ],
                json_schema={"english": "string"},
                valuation=valuation,
            )
            try:
                english = translated.as_json().get("english", asr["text"])
            except ValueError:
                english = translated.text
        asset.transcript = {
            "text": asr["text"],
            "language": asr.get("language"),
            "english": english,
        }
        asset.save(update_fields=["transcript", "updated_at"])
        results.append({"asset_id": str(asset.id), "language": asr.get("language")})
    return {"transcribed": results}


# ---------------------------------------------------------------------------
# 2. Document extraction
# ---------------------------------------------------------------------------
DOC_SCHEMA = {
    "owner": "string",
    "survey_no": "string",
    "extent": "string",
    "boundaries": {"north": "string", "south": "string", "east": "string", "west": "string"},
    "tax_paid": "boolean",
    "approval_validity": "string (YYYY-MM-DD or null)",
    "rto_or_insurance": "string",
}


def extract_documents(valuation) -> dict:
    """Vision OCR + field extraction over document assets."""
    results = []
    for asset in valuation.media_assets.filter(kind=MediaKind.DOCUMENT):
        url = storage.presign_get(asset.s3_key)
        result = router.complete(
            TaskType.DOC_EXTRACT,
            [
                {
                    "role": "system",
                    "content": "You extract structured fields from Indian property "
                    "documents. Return null for fields you cannot read.",
                },
                {"role": "user", "content": "Extract the fields from this document."},
            ],
            images=[url],
            json_schema=DOC_SCHEMA,
            valuation=valuation,
        )
        try:
            extraction = result.as_json()
        except ValueError:
            extraction = {"_raw": result.text}
        asset.extraction = extraction
        asset.save(update_fields=["extraction", "updated_at"])
        results.append({"asset_id": str(asset.id), "fields": extraction})
    return {"extracted": results}


# ---------------------------------------------------------------------------
# 3. Photo analysis
# ---------------------------------------------------------------------------
PHOTO_SCHEMA = {
    "construction_type": "string",
    "floors": "integer",
    "condition": "string",
    "defects": ["string"],
    "surroundings": "string",
}


def analyze_photos(valuation) -> dict:
    """Vision over photo assets → construction/condition/surroundings."""
    results = []
    for asset in valuation.media_assets.filter(kind=MediaKind.PHOTO):
        url = storage.presign_get(asset.s3_key)
        result = router.complete(
            TaskType.IMAGE_ANALYZE,
            [
                {
                    "role": "system",
                    "content": "You are a civil engineer assessing a building from a "
                    "photo. Describe construction type, visible condition and surroundings.",
                },
                {"role": "user", "content": "Analyze this building photo."},
            ],
            images=[url],
            json_schema=PHOTO_SCHEMA,
            valuation=valuation,
        )
        try:
            analysis = result.as_json()
        except ValueError:
            analysis = {"_raw": result.text}
        asset.extraction = analysis
        asset.save(update_fields=["extraction", "updated_at"])
        results.append({"asset_id": str(asset.id), "analysis": analysis})
    return {"analyzed": results}


# ---------------------------------------------------------------------------
# 4. Autofill — the key step
# ---------------------------------------------------------------------------
# answer_types whose values are numeric/judgmental and must never be auto-confirmed.
_JUDGMENT_TYPES = {"formula_based_calculation", "sum_of_attribute"}


def _gather_inputs(valuation) -> dict:
    """Collect transcripts + extractions + photo analyses + GPS into one blob."""
    transcripts, documents, photos = [], [], []
    for asset in valuation.media_assets.all():
        if asset.transcript:
            transcripts.append({"asset_id": str(asset.id), **asset.transcript})
        if asset.extraction and asset.kind == MediaKind.DOCUMENT:
            documents.append({"asset_id": str(asset.id), "fields": asset.extraction})
        if asset.extraction and asset.kind == MediaKind.PHOTO:
            photos.append({"asset_id": str(asset.id), "analysis": asset.extraction})
    return {
        "transcripts": transcripts,
        "documents": documents,
        "photos": photos,
        "gps": {"lat": str(valuation.latitude), "lng": str(valuation.longitude)},
        "address": valuation.address,
        "locality": valuation.locality,
    }


def _mock_autofill(question_payload: list[dict], inputs: dict) -> dict:
    """Deterministic offline suggestions, one per question (all ``amber``).

    Used only when ``AI_MOCK`` is on and the (mock) router returned no answers, so
    the demo populates with realistic-shaped values + evidence the valuer reviews.
    """
    # Point evidence at the first available source asset, if any.
    first_asset = None
    snippet = ""
    if inputs.get("transcripts"):
        first_asset = inputs["transcripts"][0].get("asset_id")
        snippet = (inputs["transcripts"][0].get("english") or "")[:80]
    elif inputs.get("documents"):
        first_asset = inputs["documents"][0].get("asset_id")
        snippet = "extracted from document"
    evidence = [{"asset_id": first_asset, "snippet": snippet}] if first_asset else []

    answers = {}
    for q in question_payload:
        atype = q["answer_type"]
        options = q.get("options") or {}
        choices = options.get("choices") if isinstance(options, dict) else None
        if atype in _JUDGMENT_TYPES:
            value = None  # never suggest a numeric/derived figure
        elif atype == "radio":
            value = choices[0]["value"] if choices else "[AI draft] option 1"
        elif atype == "checkbox":
            value = [choices[0]["value"]] if choices else ["[AI draft] option 1"]
        elif atype == "tabular":
            value = [{"north": "road", "south": "plot", "east": "plot", "west": "road"}]
        else:  # text
            value = "[AI draft] to be confirmed by valuer"
        answers[q["question_id"]] = {
            "question_id": q["question_id"],
            "value": value,
            "confidence": Confidence.AMBER,
            "evidence": evidence,
        }
    return answers


def autofill_answers(valuation) -> dict:
    """Map all gathered inputs onto the case's Question set and upsert Answers.

    For each question the model returns ``{question_id, value, confidence,
    evidence[]}``. Numeric/judgment questions are forced to ``amber`` so a final
    valuation figure is never auto-confirmed — the valuer must review.
    """
    from masters.selectors import questions_for

    wo = valuation.work_order
    questions = list(
        questions_for(
            service_type_id=wo.service_type_id,
            sub_type_id=wo.sub_type_id,
            bank_id=wo.bank_id,
        )
    )
    if not questions:
        return {"filled": 0, "detail": "No questions configured for this case."}

    question_payload = [
        {
            "question_id": str(q.id),
            "text": q.text,
            "answer_type": q.answer_type,
            "options": q.options,
            "mandatory": q.is_mandatory,
        }
        for q in questions
    ]
    inputs = _gather_inputs(valuation)

    bank_name = wo.bank.name
    sub_type = wo.sub_type.name if wo.sub_type_id else ""
    result = router.complete(
        TaskType.FORM_AUTOFILL,
        [
            {
                "role": "system",
                "content": (
                    f"You are an autofill agent for a {bank_name} property-valuation "
                    f"report ({wo.service_type.name} / {sub_type}) in India. Fill the "
                    "bank's CIF question set from the field evidence (voice transcript, "
                    "document extraction, photo analysis, GPS). For each question "
                    "produce a value consistent with its answer_type and options "
                    "(radio/checkbox values must come from options; tabular returns "
                    "rows). Cite evidence by asset_id with a short supporting snippet. "
                    "Confidence: 'green' only when directly supported by evidence, "
                    "'amber' when inferred or judgmental, 'red' when unsupported. "
                    "NEVER assert a rate, area or final valuation figure as confident — "
                    "those are always 'amber' for the human valuer to confirm."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"QUESTIONS:\n{question_payload}\n\nEVIDENCE:\n{inputs}\n\n"
                    "Return JSON: {\"answers\": [{question_id, value, confidence, "
                    "evidence: [{asset_id, snippet}]}]}"
                ),
            },
        ],
        json_schema={
            "answers": [
                {
                    "question_id": "string",
                    "value": "any",
                    "confidence": "green|amber|red",
                    "evidence": [{"asset_id": "string", "snippet": "string"}],
                }
            ]
        },
        valuation=valuation,
    )

    try:
        parsed = result.as_json()
        ai_answers = {a["question_id"]: a for a in parsed.get("answers", [])}
    except (ValueError, KeyError, TypeError):
        ai_answers = {}

    # Offline demo: the mock router can't see the question set, so synthesize
    # deterministic per-question suggestions (always amber — AI-suggested, for the
    # valuer to confirm) so the whole capture→autofill→review flow is visible
    # without provider keys. No effect once real keys are configured.
    if settings.AI_MOCK and not ai_answers:
        ai_answers = _mock_autofill(question_payload, inputs)

    filled = 0
    for q in questions:
        ai = ai_answers.get(str(q.id))
        if ai is None:
            # Ensure a row exists so the valuer sees the gap (red).
            Answer.objects.get_or_create(
                valuation=valuation,
                question=q,
                defaults={"confidence": Confidence.RED, "ai_filled": False},
            )
            continue

        confidence = ai.get("confidence", Confidence.AMBER)
        if q.answer_type in _JUDGMENT_TYPES and confidence == Confidence.GREEN:
            confidence = Confidence.AMBER  # never auto-confirm numeric/judgment
        if confidence not in Confidence.values:
            confidence = Confidence.AMBER

        Answer.objects.update_or_create(
            valuation=valuation,
            question=q,
            defaults={
                "value": ai.get("value"),
                "confidence": confidence,
                "evidence": ai.get("evidence", []),
                "ai_filled": True,
                "confirmed": False,
            },
        )
        filled += 1

    return {"filled": filled, "questions": len(questions)}


# ---------------------------------------------------------------------------
# 5. Market rate
# ---------------------------------------------------------------------------
def market_rate(valuation) -> dict:
    """Perplexity live search for the prevailing rate; store a lookup. Suggest only."""
    wo = valuation.work_order
    property_type = wo.service_type.name
    locality = valuation.locality or valuation.address or "the area"
    query = (
        f"What is the prevailing market rate per sq ft for {property_type} property "
        f"near {locality}? Give a typical range in INR."
    )
    res = router.search(query, deep=False, valuation=valuation)

    # Best-effort range parse from the answer text.
    import re

    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]{3,}", res["answer"])]
    result_range = None
    if len(nums) >= 2:
        result_range = {"min": min(nums), "max": max(nums), "unit": "sq_ft", "currency": "INR"}
    elif nums:
        result_range = {"min": nums[0], "max": nums[0], "unit": "sq_ft", "currency": "INR"}

    lookup = MarketRateLookup.objects.create(
        valuation=valuation,
        query=query,
        result_range=result_range,
        citations=res.get("citations", []),
        raw_response=res.get("raw"),
    )
    return {
        "lookup_id": str(lookup.id),
        "range": result_range,
        "citations": res.get("citations", []),
    }


# ---------------------------------------------------------------------------
# 6. Draft comments
# ---------------------------------------------------------------------------
def draft_comments(valuation) -> dict:
    """NARRATIVE: professional valuer remarks in English from confirmed answers."""
    confirmed = [
        {"q": a.question.text, "value": a.value}
        for a in valuation.answers.select_related("question").filter(confirmed=True)
    ]
    result = router.complete(
        TaskType.NARRATIVE,
        [
            {
                "role": "system",
                "content": "Write concise, professional property-valuer remarks in "
                "English suitable for a bank report. No markdown.",
            },
            {"role": "user", "content": f"Confirmed findings:\n{confirmed}"},
        ],
        valuation=valuation,
    )
    return {"comments": result.text}


# ---------------------------------------------------------------------------
# 7. Risk checks
# ---------------------------------------------------------------------------
def run_risk_checks(valuation, stage: str | None = None) -> dict:
    """Stage-aware verification risk flags.

    Combines deterministic checks (missing mandatory fields, coordinates) with an
    LLM pass. Returns ``{"flags": [{severity, message, related_answer}]}``.
    """
    flags: list[dict] = []

    # Deterministic: missing mandatory answers.
    for ans in valuation.answers.select_related("question").all():
        if ans.question.is_mandatory and (ans.value in (None, "", [], {})):
            flags.append({
                "severity": "high",
                "message": f"Mandatory field unanswered: {ans.question.text[:80]}",
                "related_answer": str(ans.id),
            })

    # Deterministic: coordinates present?
    if valuation.latitude is None or valuation.longitude is None:
        flags.append({
            "severity": "medium",
            "message": "GPS coordinates missing for the site.",
            "related_answer": None,
        })

    # LLM pass for subtler, document-vs-site risks.
    answers = [
        {"q": a.question.text, "value": a.value, "confidence": a.confidence}
        for a in valuation.answers.select_related("question").all()
    ]
    result = router.complete(
        TaskType.RISK_CHECK,
        [
            {
                "role": "system",
                "content": "You flag verification risks for a bank valuation "
                f"(stage: {stage or 'general'}). Examples: expired approval, "
                "boundary deviation doc-vs-site, coordinates outside stated locality.",
            },
            {"role": "user", "content": f"Answers:\n{answers}\nReturn {{\"flags\":[...]}}"},
        ],
        json_schema={"flags": [{"severity": "string", "message": "string", "related_answer": "string|null"}]},
        valuation=valuation,
    )
    try:
        flags.extend(result.as_json().get("flags", []))
    except (ValueError, AttributeError):
        pass

    return {"flags": flags, "stage": stage}


# ---------------------------------------------------------------------------
# 8. Report generation
# ---------------------------------------------------------------------------
def generate_report(valuation) -> dict:
    """Assemble answers into the bank's headings and render a PDF to S3."""
    from reports.generator import render_valuation_pdf

    key, url = render_valuation_pdf(valuation)
    return {"report_key": key, "url": url}


# Registry used by the worker / enqueue layer.
TASK_FUNCTIONS = {
    "transcribe": transcribe_valuation_audio,
    "extract-documents": extract_documents,
    "analyze-photos": analyze_photos,
    "autofill": autofill_answers,
    "market-rate": market_rate,
    "draft-comments": draft_comments,
    "generate-report": generate_report,
}
