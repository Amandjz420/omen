"""The LLM Router — the single entry point for every AI call in OMEN.

Why a router: provider catalogs and model slugs change monthly, so the mapping
from *task* to *provider/model/params* lives in exactly one place
(:data:`TASK_MODEL_MAP`), overridable via env vars (and a DB table later). Every
call is wrapped with timeout + retry, structured logging, and an
:class:`ai.models.LLMCall` audit row so we can see spend per task and per case.

Two providers sit behind one interface:

* **DeepInfra** — the OpenAI-compatible API (chat, vision, audio, embeddings),
  accessed with the ``openai`` SDK pointed at DeepInfra's base URL.
* **Perplexity** — Sonar models for live web search, via ``httpx``.

Set ``AI_MOCK=1`` (auto-enabled when no provider keys are configured) to return
deterministic stub output so the whole pipeline runs offline.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from django.conf import settings

from .costs import estimate_cost

logger = logging.getLogger("omen.ai")


class TaskType(str, Enum):
    """The kinds of AI work the platform performs."""

    ASR = "asr"  # speech-to-text (multilingual)
    TRANSLATE = "translate"  # to English, keep original
    CLASSIFY = "classify"  # cheap classification
    DOC_EXTRACT = "doc_extract"  # vision OCR + field extraction
    IMAGE_ANALYZE = "image_analyze"  # vision: construction/condition/surroundings
    FORM_AUTOFILL = "form_autofill"  # reasoning: inputs -> Question Bank answers
    NARRATIVE = "narrative"  # draft valuer comments / report prose
    RISK_CHECK = "risk_check"  # reasoning: flag verification risks
    MARKET_RATE_SEARCH = "market_rate_search"  # Perplexity live web search
    EMBED = "embed"  # embeddings for retrieval


class Provider(str, Enum):
    DEEPINFRA = "deepinfra"
    PERPLEXITY = "perplexity"


# ---------------------------------------------------------------------------
# Task -> {provider, model, params, fallback}. Edit models HERE only.
# Confirm exact slugs against deepinfra.com/models — the catalog changes often.
# ---------------------------------------------------------------------------
TASK_MODEL_MAP: dict[TaskType, dict[str, Any]] = {
    TaskType.ASR: {
        "provider": Provider.DEEPINFRA,
        "model": "openai/whisper-large-v3",
        "params": {},
    },
    TaskType.TRANSLATE: {
        "provider": Provider.DEEPINFRA,
        "model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "fallback": "mistralai/Mistral-Small-24B-Instruct-2501",
        "params": {"temperature": 0.0},
    },
    TaskType.CLASSIFY: {
        "provider": Provider.DEEPINFRA,
        "model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "fallback": "mistralai/Mistral-Small-24B-Instruct-2501",
        "params": {"temperature": 0.0},
    },
    TaskType.DOC_EXTRACT: {
        "provider": Provider.DEEPINFRA,
        "model": "Qwen/Qwen3-VL-30B-A3B-Instruct",
        "params": {"temperature": 0.0},
    },
    TaskType.IMAGE_ANALYZE: {
        "provider": Provider.DEEPINFRA,
        "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct",
        "params": {"temperature": 0.2},
    },
    TaskType.FORM_AUTOFILL: {
        "provider": Provider.DEEPINFRA,
        "model": "deepseek-ai/DeepSeek-V3.2",
        "fallback": "Qwen/Qwen3-235B-A22B-Thinking-2507",
        "params": {"temperature": 0.1},
    },
    TaskType.NARRATIVE: {
        "provider": Provider.DEEPINFRA,
        "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct",
        "params": {"temperature": 0.4},
    },
    TaskType.RISK_CHECK: {
        "provider": Provider.DEEPINFRA,
        "model": "deepseek-ai/DeepSeek-V3.2",
        "params": {"temperature": 0.0},
    },
    TaskType.MARKET_RATE_SEARCH: {
        "provider": Provider.PERPLEXITY,
        "model": "sonar",
        "deep_model": "sonar-pro",
        "params": {},
    },
    TaskType.EMBED: {
        "provider": Provider.DEEPINFRA,
        "model": "BAAI/bge-m3",
        "params": {},
    },
}


def resolve(task: TaskType) -> dict[str, Any]:
    """Resolve the config for a task, applying env-var overrides.

    ``AI_PROVIDER_<TASK>`` and ``AI_MODEL_<TASK>`` (uppercased task name)
    override the defaults without touching code.
    """
    cfg = dict(TASK_MODEL_MAP[task])
    import os

    provider_override = os.environ.get(f"AI_PROVIDER_{task.name}")
    model_override = os.environ.get(f"AI_MODEL_{task.name}")
    if provider_override:
        cfg["provider"] = Provider(provider_override)
    if model_override:
        cfg["model"] = model_override
    return cfg


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json(text: str) -> Any:
    """Parse model output as JSON, tolerating code fences and surrounding prose.

    Raises ``ValueError`` if no JSON object/array can be extracted.
    """
    cleaned = _FENCE_RE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} or [...] span.
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError(f"Could not parse JSON from model output: {text[:200]!r}")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: Any = None

    def as_json(self) -> Any:
        return parse_json(self.text)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
def _record_call(
    *, task, provider, model, prompt_tokens, completion_tokens, latency_ms,
    valuation=None, success=True, error="",
) -> None:
    """Write an :class:`ai.models.LLMCall` row (best-effort; never raises)."""
    try:
        from .models import LLMCall

        LLMCall.objects.create(
            valuation=valuation,
            task=str(task),
            provider=str(provider),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            est_cost=estimate_cost(model, prompt_tokens, completion_tokens),
            success=success,
            error=error[:2000],
        )
    except Exception:  # pragma: no cover - auditing must not break calls
        logger.exception("Failed to record LLMCall")


def _with_retry(fn, *, label: str):
    """Run ``fn`` with timeout-aware retry + exponential backoff."""
    attempts = max(1, settings.LLM_MAX_RETRIES)
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - providers raise varied types
            last_exc = exc
            wait = 2**attempt
            logger.warning(
                "LLM call '%s' failed (attempt %d/%d): %s; retrying in %ss",
                label, attempt + 1, attempts, exc, wait,
            )
            if attempt + 1 < attempts:
                time.sleep(wait)
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Provider clients (lazily constructed)
# ---------------------------------------------------------------------------
def _deepinfra_client():
    from openai import OpenAI

    return OpenAI(
        api_key=settings.DEEPINFRA_API_KEY,
        base_url=settings.DEEPINFRA_BASE_URL,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def _build_messages(messages: list[dict], images: list[str] | None) -> list[dict]:
    """Attach images (URLs or base64 data URLs) to the final user message."""
    if not images:
        return messages
    msgs = [dict(m) for m in messages]
    # Find last user message; append image parts.
    for m in reversed(msgs):
        if m.get("role") == "user":
            content = m.get("content", "")
            parts: list[dict] = []
            if isinstance(content, str) and content:
                parts.append({"type": "text", "text": content})
            elif isinstance(content, list):
                parts.extend(content)
            for img in images:
                url = img if img.startswith(("http://", "https://", "data:")) else f"data:image/jpeg;base64,{img}"
                parts.append({"type": "image_url", "image_url": {"url": url}})
            m["content"] = parts
            break
    return msgs


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def complete(
    task: TaskType,
    messages: list[dict],
    *,
    images: list[str] | None = None,
    json_schema: dict | None = None,
    valuation=None,
    **overrides,
) -> LLMResult:
    """Run a chat/vision completion for ``task``.

    ``messages`` is OpenAI-style. ``images`` (URLs or base64) are attached to the
    last user turn for vision models. ``json_schema`` requests JSON-only output.
    ``overrides`` (e.g. ``temperature``, ``model``) win over the task defaults.
    """
    cfg = resolve(task)
    model = overrides.pop("model", cfg["model"])
    params = {**cfg.get("params", {}), **overrides}

    if json_schema is not None:
        instruction = (
            "Respond with ONLY valid JSON matching this schema, no prose, no code "
            f"fences:\n{json.dumps(json_schema)}"
        )
        messages = messages + [{"role": "system", "content": instruction}]

    if settings.AI_MOCK:
        return _mock_complete(task, messages, model, json_schema, valuation)

    msgs = _build_messages(messages, images)
    start = time.perf_counter()

    def _call():
        client = _deepinfra_client()
        return client.chat.completions.create(model=model, messages=msgs, **params)

    try:
        resp = _with_retry(_call, label=f"complete:{task.value}")
    except Exception as exc:
        latency = int((time.perf_counter() - start) * 1000)
        _record_call(
            task=task.value, provider=cfg["provider"].value, model=model,
            prompt_tokens=0, completion_tokens=0, latency_ms=latency,
            valuation=valuation, success=False, error=str(exc),
        )
        raise

    latency = int((time.perf_counter() - start) * 1000)
    usage = getattr(resp, "usage", None)
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    _record_call(
        task=task.value, provider=cfg["provider"].value, model=model,
        prompt_tokens=pt, completion_tokens=ct, latency_ms=latency, valuation=valuation,
    )
    return LLMResult(
        text=resp.choices[0].message.content or "",
        model=model,
        provider=cfg["provider"].value,
        prompt_tokens=pt,
        completion_tokens=ct,
        raw=resp,
    )


def transcribe(audio_bytes: bytes, *, language: str | None = None, valuation=None) -> dict:
    """Speech-to-text via DeepInfra Whisper. Returns ``{text, language}``."""
    cfg = resolve(TaskType.ASR)
    model = cfg["model"]

    if settings.AI_MOCK:
        _record_call(
            task=TaskType.ASR.value, provider=cfg["provider"].value, model=model,
            prompt_tokens=0, completion_tokens=0, latency_ms=1, valuation=valuation,
        )
        return {
            "text": "[mock transcript] The property is a two-storey RCC building in "
            "good condition near the main road.",
            "language": language or "hi",
        }

    import io

    start = time.perf_counter()

    def _call():
        client = _deepinfra_client()
        buf = io.BytesIO(audio_bytes)
        buf.name = "audio.wav"
        kwargs = {"model": model, "file": buf}
        if language:
            kwargs["language"] = language
        return client.audio.transcriptions.create(**kwargs)

    resp = _with_retry(_call, label="transcribe")
    latency = int((time.perf_counter() - start) * 1000)
    _record_call(
        task=TaskType.ASR.value, provider=cfg["provider"].value, model=model,
        prompt_tokens=0, completion_tokens=0, latency_ms=latency, valuation=valuation,
    )
    return {
        "text": getattr(resp, "text", ""),
        "language": getattr(resp, "language", language) or language,
    }


def embed(texts: list[str], *, valuation=None) -> list[list[float]]:
    """Return embedding vectors for ``texts`` via DeepInfra."""
    cfg = resolve(TaskType.EMBED)
    model = cfg["model"]

    if settings.AI_MOCK:
        # Deterministic tiny vectors keyed by text length (offline-friendly).
        return [[float(len(t) % 7), 0.1, 0.2] for t in texts]

    start = time.perf_counter()

    def _call():
        client = _deepinfra_client()
        return client.embeddings.create(model=model, input=texts)

    resp = _with_retry(_call, label="embed")
    latency = int((time.perf_counter() - start) * 1000)
    _record_call(
        task=TaskType.EMBED.value, provider=cfg["provider"].value, model=model,
        prompt_tokens=0, completion_tokens=0, latency_ms=latency, valuation=valuation,
    )
    return [d.embedding for d in resp.data]


def search(query: str, *, deep: bool = False, valuation=None) -> dict:
    """Live web search via Perplexity Sonar. Returns ``{answer, citations}``."""
    cfg = resolve(TaskType.MARKET_RATE_SEARCH)
    model = cfg.get("deep_model", cfg["model"]) if deep else cfg["model"]

    if settings.AI_MOCK:
        _record_call(
            task=TaskType.MARKET_RATE_SEARCH.value, provider=cfg["provider"].value,
            model=model, prompt_tokens=0, completion_tokens=0, latency_ms=1,
            valuation=valuation,
        )
        return {
            "answer": "Prevailing market rate is approximately INR 4,500–6,000 per "
            "sq ft for residential property in this locality.",
            "citations": [
                "https://example.com/market-report-1",
                "https://example.com/market-report-2",
            ],
            "raw": {"mock": True},
        }

    start = time.perf_counter()

    def _call():
        with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            r = client.post(
                f"{settings.PERPLEXITY_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": query}],
                },
            )
            r.raise_for_status()
            return r.json()

    data = _with_retry(_call, label="search")
    latency = int((time.perf_counter() - start) * 1000)
    usage = data.get("usage", {})
    _record_call(
        task=TaskType.MARKET_RATE_SEARCH.value, provider=cfg["provider"].value,
        model=model, prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0), latency_ms=latency,
        valuation=valuation,
    )
    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    citations = data.get("citations") or data.get("search_results") or []
    return {"answer": answer, "citations": citations, "raw": data}


# ---------------------------------------------------------------------------
# Mock completion
# ---------------------------------------------------------------------------
def _mock_complete(task, messages, model, json_schema, valuation) -> LLMResult:
    """Deterministic stub output, shaped per task so downstream code works."""
    cfg = resolve(task)
    _record_call(
        task=task.value, provider=cfg["provider"].value, model=model,
        prompt_tokens=10, completion_tokens=20, latency_ms=1, valuation=valuation,
    )

    if task == TaskType.TRANSLATE:
        text = json.dumps({"english": "[mock] Translated text in English."})
    elif task == TaskType.DOC_EXTRACT:
        text = json.dumps({
            "owner": "[mock] Ramesh Kumar",
            "survey_no": "123/4",
            "extent": "2400 sq ft",
            "boundaries": {"north": "Road", "south": "Plot 12"},
            "tax_paid": True,
            "approval_validity": "2027-12-31",
        })
    elif task == TaskType.IMAGE_ANALYZE:
        text = json.dumps({
            "construction_type": "RCC framed",
            "floors": 2,
            "condition": "good",
            "defects": [],
            "surroundings": "residential, near main road",
        })
    elif task == TaskType.FORM_AUTOFILL:
        # Generic shape consumed by services.autofill_answers.
        text = json.dumps({"answers": []})
    elif task == TaskType.RISK_CHECK:
        text = json.dumps({"flags": []})
    elif task == TaskType.NARRATIVE:
        text = (
            "[mock] The property is a well-maintained RCC building in a "
            "predominantly residential locality with good access and amenities."
        )
    elif task == TaskType.CLASSIFY:
        text = json.dumps({"label": "mock", "confidence": 0.9})
    else:
        text = "[mock output]"

    return LLMResult(
        text=text, model=model, provider=cfg["provider"].value,
        prompt_tokens=10, completion_tokens=20, raw={"mock": True},
    )
