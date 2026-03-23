from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_usage(usage_metadata: Any, response_metadata: Any) -> dict[str, int | None]:
    usage = usage_metadata or {}
    response = response_metadata or {}
    token_usage = response.get("token_usage", {}) if isinstance(response, dict) else {}

    input_tokens = _as_int(
        usage.get("input_tokens")
        or token_usage.get("prompt_tokens")
        or token_usage.get("input_tokens")
    )
    output_tokens = _as_int(
        usage.get("output_tokens")
        or token_usage.get("completion_tokens")
        or token_usage.get("output_tokens")
        or response.get("output_tokens")
    )
    total_tokens = _as_int(
        usage.get("total_tokens")
        or token_usage.get("total_tokens")
    )
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


@lru_cache
def load_pricing_catalog(pricing_file: str) -> dict[str, Any]:
    with Path(pricing_file).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def calculate_call_cost(
    *,
    provider: str,
    model: str,
    usage_metadata: Any,
    response_metadata: Any,
    pricing_file: Path,
) -> dict[str, Any]:
    usage = normalize_usage(usage_metadata, response_metadata)
    catalog = load_pricing_catalog(str(pricing_file))
    provider_models = catalog.get("providers", {}).get(provider, {})
    pricing = provider_models.get(model)

    if pricing is None:
        return {
            **usage,
            "input_cost_usd": None,
            "output_cost_usd": None,
            "total_cost_usd": None,
            "pricing_source": None,
        }

    input_tokens = usage["input_tokens"] or 0
    output_tokens = usage["output_tokens"] or 0
    input_per_million = float(pricing["input_per_million_tokens_usd"])
    output_per_million = float(pricing["output_per_million_tokens_usd"])

    input_cost = round((input_tokens / 1_000_000) * input_per_million, 8)
    output_cost = round((output_tokens / 1_000_000) * output_per_million, 8)
    total_cost = round(input_cost + output_cost, 8)

    return {
        **usage,
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": total_cost,
        "pricing_source": pricing.get("source"),
    }
