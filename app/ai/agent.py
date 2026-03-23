from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq

from app.ai.pricing import calculate_call_cost
from app.ai.state import AgentMetric
from app.core.config import Settings, get_settings

logger = logging.getLogger("app.ai.agent")

try:  # pragma: no cover - optional provider dependency
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:  # pragma: no cover - optional provider dependency
    ChatGoogleGenerativeAI = None


class LangChainAgent:
    def __init__(
        self,
        *,
        name: str,
        provider: str,
        model_name: str,
        prompt: str,
        tags: list[str] | None = None,
        temperature: float = 0,
        settings: Settings | None = None,
    ) -> None:
        self.name = name
        self.provider = provider
        self.model_name = model_name
        self.prompt = prompt
        self.tags = tags or []
        self.temperature = temperature
        self.settings = settings or get_settings()
        self.model = build_chat_model(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            settings=self.settings,
        )

    async def ainvoke_text(
        self,
        payload: dict[str, Any],
        *,
        run_id: str,
        config: RunnableConfig | None = None,
    ) -> tuple[str, AIMessage, AgentMetric]:
        messages = self._build_messages(payload)
        start = perf_counter()
        response = await self.model.ainvoke(
            messages,
            config=self._build_config(config=config, run_id=run_id),
        )
        latency_ms = round((perf_counter() - start) * 1000, 2)
        metric = self._log_call(
            run_id=run_id,
            latency_ms=latency_ms,
            input_messages=messages,
            output_preview=response.content,
            raw_message=response,
            config=config,
        )
        return str(response.content), response, metric

    async def ainvoke_structured(
        self,
        payload: dict[str, Any],
        schema: type[Any],
        *,
        run_id: str,
        config: RunnableConfig | None = None,
    ) -> tuple[Any, AIMessage, AgentMetric]:
        messages = self._build_messages(payload)
        start = perf_counter()
        structured_model = self.model.with_structured_output(schema, include_raw=True)
        result = await structured_model.ainvoke(
            messages,
            config=self._build_config(config=config, run_id=run_id),
        )
        latency_ms = round((perf_counter() - start) * 1000, 2)
        parsing_error = result.get("parsing_error")
        if parsing_error:
            raise parsing_error

        raw_message = result["raw"]
        parsed = result["parsed"]
        output_preview = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
        metric = self._log_call(
            run_id=run_id,
            latency_ms=latency_ms,
            input_messages=messages,
            output_preview=output_preview,
            raw_message=raw_message,
            config=config,
        )
        return parsed, raw_message, metric

    async def ainvoke_message(
        self,
        messages: Sequence[BaseMessage],
        *,
        run_id: str,
        config: RunnableConfig | None = None,
        model_override: Any | None = None,
    ) -> tuple[AIMessage, AgentMetric]:
        working_messages = list(messages)
        start = perf_counter()
        model = model_override or self.model
        response = await model.ainvoke(
            working_messages,
            config=self._build_config(config=config, run_id=run_id),
        )
        latency_ms = round((perf_counter() - start) * 1000, 2)
        metric = self._log_call(
            run_id=run_id,
            latency_ms=latency_ms,
            input_messages=working_messages,
            output_preview=response.content,
            raw_message=response,
            config=config,
        )
        return response, metric

    def _build_config(self, *, config: RunnableConfig | None, run_id: str) -> RunnableConfig:
        merged = dict(config or {})
        tags = [*merged.get("tags", []), *self.tags]
        metadata = dict(merged.get("metadata", {}))
        metadata.update(
            {
                "run_id": run_id,
                "agent": self.name,
                "provider": self.provider,
                "model": self.model_name,
            }
        )
        merged["run_name"] = self.name
        merged["tags"] = tags
        merged["metadata"] = metadata
        return merged

    def _build_messages(self, payload: dict[str, Any]) -> list[BaseMessage]:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not all(isinstance(message, BaseMessage) for message in messages):
            raise ValueError(f"{self.name} expected payload['messages'] to be a list of LangChain messages.")
        return messages

    def _log_call(
        self,
        *,
        run_id: str,
        latency_ms: float,
        input_messages: list[BaseMessage],
        output_preview: Any,
        raw_message: AIMessage,
        config: RunnableConfig | None,
    ) -> AgentMetric:
        thread_id = self._resolve_thread_id(config)
        usage_metadata = getattr(raw_message, "usage_metadata", None)
        response_metadata = getattr(raw_message, "response_metadata", None)
        pricing = calculate_call_cost(
            provider=self.provider,
            model=self.model_name,
            usage_metadata=usage_metadata,
            response_metadata=response_metadata,
            pricing_file=self.settings.llm_pricing_file,
        )
        metric = AgentMetric(
            agent=self.name,
            provider=self.provider,
            model=self.model_name,
            latency_ms=latency_ms,
            input_tokens=pricing["input_tokens"],
            output_tokens=pricing["output_tokens"],
            total_tokens=pricing["total_tokens"],
            input_cost_usd=pricing["input_cost_usd"],
            output_cost_usd=pricing["output_cost_usd"],
            total_cost_usd=pricing["total_cost_usd"],
            pricing_source=pricing["pricing_source"],
        )
        payload = {
            "agent": self.name,
            "provider": self.provider,
            "thread_id": thread_id,
            "run_id": run_id,
            "model": self.model_name,
            "latency_ms": latency_ms,
            "usage_metadata": usage_metadata,
            "response_metadata": response_metadata,
            "input_preview": self._truncate(self._preview_messages(input_messages)),
            "output_preview": self._truncate(output_preview),
            "tool_calls": getattr(raw_message, "tool_calls", None),
            "cost": metric.model_dump(),
        }
        if self.settings.agent_log_include_content:
            payload["input_messages"] = [
                {
                    "type": message.type,
                    "content": message.content,
                }
                for message in input_messages
            ]
            payload["output_full"] = output_preview

        encoded = json.dumps(payload, default=str, ensure_ascii=True)
        logger.info(encoded)
        self._write_log_file(encoded)
        return metric

    def _resolve_thread_id(self, config: RunnableConfig | None) -> str | None:
        if config is None:
            return None
        configurable = config.get("configurable", {})
        if isinstance(configurable, dict):
            thread_id = configurable.get("thread_id")
            if thread_id is not None:
                return str(thread_id)
        metadata = config.get("metadata", {})
        if isinstance(metadata, dict):
            thread_id = metadata.get("thread_id")
            if thread_id is not None:
                return str(thread_id)
        return None

    def _write_log_file(self, encoded: str) -> None:
        path = self.settings.agent_log_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.write("\n")

    def _preview_messages(self, messages: list[BaseMessage]) -> str:
        return "\n".join(f"{message.type.upper()}: {message.content}" for message in messages)

    def _truncate(self, value: Any, limit: int = 1200) -> str:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, default=str, ensure_ascii=True)
        return text if len(text) <= limit else f"{text[:limit]}..."

def build_chat_model(
    *,
    provider: str,
    model_name: str,
    temperature: float,
    settings: Settings | None = None,
):
    settings = settings or get_settings()
    normalized = provider.strip().lower()
    groq_api_key = _secret_value(settings.groq_api_key)
    google_api_key = _secret_value(settings.gemini_api_key)

    if normalized == "groq":
        if groq_api_key is None:
            raise RuntimeError("GROQ_API_KEY is required when using the Groq provider.")
        return ChatGroq(
            model=model_name,
            api_key=groq_api_key,
            temperature=temperature,
        )

    if normalized == "gemini":
        if ChatGoogleGenerativeAI is None:
            raise RuntimeError("langchain-google-genai must be installed to use the Gemini provider.")
        if google_api_key is None:
            raise RuntimeError("GEMINI_API_KEY is required when using the Gemini provider.")
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=google_api_key,
            temperature=temperature,
        )

    raise ValueError(f"Unsupported chat provider: {provider}")


def _secret_value(secret: Any) -> str | None:
    if secret is None:
        return None
    value = secret.get_secret_value()
    return value if value.strip() else None
