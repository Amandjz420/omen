"""Tiny cost table for estimating LLM spend per call.

Prices are USD per 1M tokens (input/output). These are rough, change often, and
are intentionally kept in ONE place so finance estimates are easy to update.
Models not listed fall back to ``DEFAULT``.
"""

from __future__ import annotations

from decimal import Decimal

# model -> (usd_per_1m_input, usd_per_1m_output)
COST_PER_1M: dict[str, tuple[float, float]] = {
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": (0.08, 0.30),
    "meta-llama/Llama-4-Maverick-17B-128E-Instruct": (0.20, 0.60),
    "mistralai/Mistral-Small-24B-Instruct-2501": (0.05, 0.10),
    "deepseek-ai/DeepSeek-V3.2": (0.27, 0.40),
    "Qwen/Qwen3-235B-A22B-Thinking-2507": (0.13, 0.60),
    "Qwen/Qwen3-VL-30B-A3B-Instruct": (0.10, 0.30),
    "openai/whisper-large-v3": (0.0, 0.0),  # priced per audio-minute upstream
    "BAAI/bge-m3": (0.01, 0.0),
    "sonar": (1.0, 1.0),
    "sonar-pro": (3.0, 15.0),
}

DEFAULT: tuple[float, float] = (0.20, 0.60)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    """Estimate USD cost for a call given token counts."""
    in_rate, out_rate = COST_PER_1M.get(model, DEFAULT)
    cost = (prompt_tokens / 1_000_000) * in_rate + (
        completion_tokens / 1_000_000
    ) * out_rate
    return Decimal(str(round(cost, 6)))
