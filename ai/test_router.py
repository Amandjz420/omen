"""Tests for the LLM router."""

from __future__ import annotations

import pytest
from django.test import override_settings

from ai import router
from ai.costs import estimate_cost
from ai.models import LLMCall
from ai.router import Provider, TaskType


def test_parse_json_strips_code_fences():
    assert router.parse_json("```json\n{\"a\": 1}\n```") == {"a": 1}


def test_parse_json_extracts_embedded_object():
    assert router.parse_json("Here you go: {\"x\": 2} thanks") == {"x": 2}


def test_parse_json_raises_when_no_json():
    with pytest.raises(ValueError):
        router.parse_json("no json here")


def test_resolve_applies_env_overrides(monkeypatch):
    monkeypatch.setenv("AI_MODEL_FORM_AUTOFILL", "some/other-model")
    monkeypatch.setenv("AI_PROVIDER_FORM_AUTOFILL", "perplexity")
    cfg = router.resolve(TaskType.FORM_AUTOFILL)
    assert cfg["model"] == "some/other-model"
    assert cfg["provider"] == Provider.PERPLEXITY


def test_estimate_cost_known_and_unknown_model():
    known = estimate_cost("deepseek-ai/DeepSeek-V3.2", 1_000_000, 1_000_000)
    assert float(known) > 0
    # Unknown model falls back to DEFAULT pricing (non-zero).
    assert float(estimate_cost("mystery/model", 1_000_000, 0)) > 0


@override_settings(AI_MOCK=True)
@pytest.mark.django_db
def test_mock_complete_records_llm_call():
    result = router.complete(
        TaskType.NARRATIVE, [{"role": "user", "content": "hi"}]
    )
    assert result.text
    assert result.provider == "deepinfra"
    assert LLMCall.objects.filter(task="narrative").exists()


@override_settings(AI_MOCK=True)
@pytest.mark.django_db
def test_mock_doc_extract_returns_parseable_json():
    result = router.complete(
        TaskType.DOC_EXTRACT, [{"role": "user", "content": "extract"}]
    )
    data = result.as_json()
    assert "owner" in data


@override_settings(AI_MOCK=True)
@pytest.mark.django_db
def test_mock_search_returns_citations():
    res = router.search("rate near MG Road")
    assert "answer" in res
    assert isinstance(res["citations"], list)


def test_with_retry_eventually_succeeds(monkeypatch):
    monkeypatch.setattr(router.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    assert router._with_retry(flaky, label="t") == "ok"
    assert calls["n"] == 2
