from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.ai.agent import LangChainAgent
from app.ai.data_tools import build_data_tools
from app.ai.document_tools import build_document_tools
from app.ai.pricing import calculate_call_cost
from app.ai.prompt import (
    CLARIFY_SYSTEM_PROMPT,
    DATA_AGENT_SYSTEM_PROMPT,
    DIRECT_RESPONSE_SYSTEM_PROMPT,
    DOCUMENT_AGENT_SYSTEM_PROMPT,
    REPORTER_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    build_reporter_context_messages,
    with_system_message,
)
from app.ai.state import (
    AgentMetric,
    AgentState,
    ChatRoute,
    ChatRunStatus,
    DataFindingsPayload,
    DocumentFindingsPayload,
    FindingsPayload,
    RouterDecision,
    make_event,
)
from app.core.config import get_settings
from app.db.session import SessionLocal

MAX_SPECIALIST_TOOL_ROUNDS = 5
MAX_SPECIALIST_RETRY_ATTEMPTS = 3


def _chunk_answer(text: str) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        if len(current) >= 10:
            chunks.append(" ".join(current) + " ")
            current = []
    if current:
        chunks.append(" ".join(current) + " ")
    return chunks


def _build_agents() -> dict[str, LangChainAgent]:
    settings = get_settings()
    return {
        "router": LangChainAgent(
            name="router",
            provider=settings.router_provider,
            model_name=settings.router_model,
            prompt=ROUTER_SYSTEM_PROMPT,
            tags=["chat", "router"],
            settings=settings,
        ),
        "document": LangChainAgent(
            name="document_agent",
            provider=settings.document_agent_provider,
            model_name=settings.document_agent_model,
            prompt=DOCUMENT_AGENT_SYSTEM_PROMPT,
            tags=["chat", "document"],
            settings=settings,
        ),
        "data": LangChainAgent(
            name="data_agent",
            provider=settings.data_agent_provider,
            model_name=settings.data_agent_model,
            prompt=DATA_AGENT_SYSTEM_PROMPT,
            tags=["chat", "data"],
            settings=settings,
        ),
        "direct_response": LangChainAgent(
            name="direct_response_agent",
            provider=settings.reporter_provider,
            model_name=settings.reporter_model,
            prompt=DIRECT_RESPONSE_SYSTEM_PROMPT,
            tags=["chat", "direct-response"],
            settings=settings,
        ),
        "clarify": LangChainAgent(
            name="clarify_agent",
            provider=settings.reporter_provider,
            model_name=settings.reporter_model,
            prompt=CLARIFY_SYSTEM_PROMPT,
            tags=["chat", "clarify"],
            settings=settings,
        ),
        "reporter": LangChainAgent(
            name="reporter",
            provider=settings.reporter_provider,
            model_name=settings.reporter_model,
            prompt=REPORTER_SYSTEM_PROMPT,
            tags=["chat", "reporter"],
            settings=settings,
        ),
    }


def _question_from_messages(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = str(message.content).strip()
            if content:
                return content
    return ""


def _base_messages(state: AgentState, system_prompt: str) -> list[BaseMessage]:
    return with_system_message(system_prompt, state["messages"])


def _common_payload(state: AgentState, system_prompt: str) -> dict[str, object]:
    return {
        "messages": _base_messages(state, system_prompt),
    }


def _to_finding_dicts(payload: FindingsPayload) -> list[dict[str, object]]:
    return [finding.model_dump() for finding in payload.findings]


def _cost_summary(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    total_cost = round(sum(metric.get("total_cost_usd") or 0 for metric in metrics), 8)
    total_tokens = sum(metric.get("total_tokens") or 0 for metric in metrics)
    return {
        "total_cost_usd": total_cost,
        "total_tokens": total_tokens,
        "agent_calls": metrics,
    }


def _metrics_from_react_messages(
    *,
    agent_name: str,
    provider: str,
    model_name: str,
    messages: list[BaseMessage],
) -> list[dict[str, Any]]:
    settings = get_settings()
    metrics: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        usage_metadata = getattr(message, "usage_metadata", None)
        response_metadata = getattr(message, "response_metadata", None)
        if usage_metadata is None and response_metadata is None:
            continue
        pricing = calculate_call_cost(
            provider=provider,
            model=model_name,
            usage_metadata=usage_metadata,
            response_metadata=response_metadata,
            pricing_file=settings.llm_pricing_file,
        )
        metrics.append(
            AgentMetric(
                agent=agent_name,
                provider=provider,
                model=model_name,
                latency_ms=0.0,
                input_tokens=pricing["input_tokens"],
                output_tokens=pricing["output_tokens"],
                total_tokens=pricing["total_tokens"],
                input_cost_usd=pricing["input_cost_usd"],
                output_cost_usd=pricing["output_cost_usd"],
                total_cost_usd=pricing["total_cost_usd"],
                pricing_source=pricing["pricing_source"],
            ).model_dump()
        )
    return metrics


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    return str(content)


def _extract_json_object(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return cleaned[start : end + 1]
    return cleaned


def _parse_findings_payload(
    messages: list[BaseMessage],
    schema: type[DocumentFindingsPayload] | type[DataFindingsPayload],
) -> DocumentFindingsPayload | DataFindingsPayload:
    fallback = schema.model_validate({"findings": [], "insufficient_evidence": True})
    ai_messages = [message for message in messages if isinstance(message, AIMessage)]
    if not ai_messages:
        return fallback
    content = _content_to_text(ai_messages[-1].content)
    if not content.strip():
        return fallback
    candidate = _extract_json_object(content)
    try:
        return schema.model_validate_json(candidate)
    except Exception:
        try:
            return schema.model_validate(json.loads(candidate))
        except Exception:
            return fallback


def _is_retryable_specialist_error(exc: Exception) -> bool:
    text = str(exc)
    markers = (
        "output_parse_failed",
        "tool_use_failed",
        "attempted to call tool 'json'",
        "Parsing failed. The model generated output that could not be parsed.",
    )
    return any(marker in text for marker in markers)


def _build_specialist_retry_message(*, error_text: str, allowed_tools: list[str]) -> HumanMessage:
    tool_names = ", ".join(allowed_tools)
    return HumanMessage(
        content=(
            "Your previous response was invalid for the provider API.\n"
            f"Provider error: {error_text}\n\n"
            "Retry and follow these rules exactly:\n"
            f"- If you need another retrieval step, call only one of these tools: {tool_names}\n"
            "- If you already have enough evidence, return only the final JSON findings object.\n"
            "- Do not call any made-up tool such as `json`.\n"
            "- Do not include chain-of-thought, analysis, or explanatory prose outside the final JSON."
        )
    )


async def _invoke_tool_call(tool_call: dict[str, Any], tools_by_name: dict[str, Any]) -> ToolMessage:
    tool_name = str(tool_call.get("name") or "").strip()
    tool_call_id = str(tool_call.get("id") or "").strip()
    tool = tools_by_name.get(tool_name)
    if tool is None:
        content = f"Error: Unknown tool '{tool_name}'."
    else:
        try:
            result = await tool.ainvoke(tool_call.get("args") or {})
            content = result if isinstance(result, str) else json.dumps(result, default=str, ensure_ascii=True)
        except Exception as exc:
            content = f"Error: {exc}"
    return ToolMessage(content=content, tool_call_id=tool_call_id, name=tool_name)


async def _run_bounded_specialist_agent(
    *,
    agent: LangChainAgent,
    state: AgentState,
    system_prompt: str,
    tools: list[Any],
    schema: type[DocumentFindingsPayload] | type[DataFindingsPayload],
    config: RunnableConfig | None,
) -> tuple[list[BaseMessage], bool]:
    transcript = _base_messages(state, system_prompt)
    react_messages: list[BaseMessage] = []
    tool_rounds = 0
    tools_by_name = {tool.name: tool for tool in tools}
    tool_enabled_model = agent.model.bind_tools(tools)
    retry_attempts = 0

    while True:
        try:
            response, _ = await agent.ainvoke_message(
                transcript,
                run_id=state["id"],
                config=config,
                model_override=tool_enabled_model,
            )
            retry_attempts = 0
        except Exception as exc:
            if _is_retryable_specialist_error(exc) and retry_attempts < MAX_SPECIALIST_RETRY_ATTEMPTS:
                retry_attempts += 1
                transcript.append(
                    _build_specialist_retry_message(
                        error_text=str(exc),
                        allowed_tools=sorted(tools_by_name),
                    )
                )
                continue

            if _is_retryable_specialist_error(exc) and any(isinstance(message, ToolMessage) for message in transcript):
                transcript.append(
                    HumanMessage(
                        content=(
                            "Provider retries were exhausted. Based only on the evidence already retrieved in this "
                            "conversation, return the final JSON findings now. Do not call any more tools."
                        )
                    )
                )
                break

            raise

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            transcript.append(response)
            react_messages.append(response)
            return react_messages, False

        if tool_rounds >= MAX_SPECIALIST_TOOL_ROUNDS:
            # Do not carry an unresolved assistant tool-call message into the
            # forced finalization step; providers reject that transcript shape.
            react_messages.append(response)
            break

        transcript.append(response)
        react_messages.append(response)
        tool_rounds += 1
        for tool_call in tool_calls:
            tool_message = await _invoke_tool_call(tool_call, tools_by_name)
            transcript.append(tool_message)
            react_messages.append(tool_message)

    transcript.append(
        HumanMessage(
            content=(
                "Tool-call budget exhausted. Based only on the evidence already retrieved in this conversation, "
                "return the final JSON findings now. Do not call any more tools."
            )
        )
    )
    try:
        raw_message, _ = await agent.ainvoke_message(
            transcript,
            run_id=state["id"],
            config=config,
        )
        react_messages.append(raw_message)
        final_payload = _parse_findings_payload(react_messages, schema)
        react_messages[-1] = AIMessage(content=json.dumps(final_payload.model_dump(), ensure_ascii=True))
    except Exception:
        react_messages.append(
            AIMessage(content=json.dumps({"findings": [], "insufficient_evidence": True}, ensure_ascii=True))
        )

    parsed = _parse_findings_payload(react_messages, schema)
    if parsed.insufficient_evidence and not parsed.findings:
        react_messages[-1] = AIMessage(
            content=json.dumps({"findings": [], "insufficient_evidence": True}, ensure_ascii=True)
        )

    return react_messages, True


@lru_cache
def get_chat_graph():
    agents = _build_agents()

    async def router_node(state: AgentState, config: RunnableConfig | None = None) -> dict[str, object]:
        decision, _, metric = await agents["router"].ainvoke_structured(
            _common_payload(state, ROUTER_SYSTEM_PROMPT),
            RouterDecision,
            run_id=state["id"],
            config=config,
        )
        return {
            "status": ChatRunStatus.running,
            "route": decision.route,
            "needs_clarification": decision.needs_clarification or decision.route == ChatRoute.clarify,
            "agent_metrics": [metric.model_dump()],
            "events": [
                make_event(
                    "run_started",
                    run_id=state["id"],
                    question=_question_from_messages(state["messages"]),
                    status=ChatRunStatus.running,
                    created_at=state["created_at"],
                    mode="langgraph",
                ),
                make_event(
                    "route_selected",
                    route=decision.route,
                    mode="langgraph",
                ),
            ],
        }

    async def document_node(state: AgentState, config: RunnableConfig | None = None) -> dict[str, object]:
        with SessionLocal() as db:
            runtime, tools = build_document_tools(db)
            react_messages, tool_budget_exhausted = await _run_bounded_specialist_agent(
                agent=agents["document"],
                state=state,
                system_prompt=DOCUMENT_AGENT_SYSTEM_PROMPT,
                tools=tools,
                schema=DocumentFindingsPayload,
                config=config,
            )
            raw_findings = _parse_findings_payload(react_messages, DocumentFindingsPayload)
            findings = runtime.validate_findings_payload(raw_findings)
            metrics = _metrics_from_react_messages(
                agent_name=agents["document"].name,
                provider=agents["document"].provider,
                model_name=agents["document"].model_name,
                messages=react_messages,
            )

        document_payload = {
            "findings": _to_finding_dicts(findings),
            "insufficient_evidence": findings.insufficient_evidence,
        }
        return {
            "document_findings": document_payload,
            "agent_metrics": metrics,
            "events": [
                make_event("document_agent_started", agent="document_retriever"),
                *(
                    [
                        make_event(
                            "document_agent_budget_exhausted",
                            detail=f"Tool-call budget reached ({MAX_SPECIALIST_TOOL_ROUNDS} rounds).",
                        )
                    ]
                    if tool_budget_exhausted
                    else []
                ),
                make_event("document_findings", findings=document_payload["findings"]),
            ],
        }

    async def data_node(state: AgentState, config: RunnableConfig | None = None) -> dict[str, object]:
        with SessionLocal() as db:
            runtime, tools = build_data_tools(db)
            react_messages, tool_budget_exhausted = await _run_bounded_specialist_agent(
                agent=agents["data"],
                state=state,
                system_prompt=DATA_AGENT_SYSTEM_PROMPT,
                tools=tools,
                schema=DataFindingsPayload,
                config=config,
            )
            raw_findings = _parse_findings_payload(react_messages, DataFindingsPayload)
            findings = runtime.validate_findings_payload(raw_findings)
            metrics = _metrics_from_react_messages(
                agent_name=agents["data"].name,
                provider=agents["data"].provider,
                model_name=agents["data"].model_name,
                messages=react_messages,
            )

        data_payload = {
            "findings": _to_finding_dicts(findings),
            "insufficient_evidence": findings.insufficient_evidence,
        }
        return {
            "data_findings": data_payload,
            "agent_metrics": metrics,
            "events": [
                make_event("data_agent_started", agent="data_analyst"),
                *(
                    [
                        make_event(
                            "data_agent_budget_exhausted",
                            detail=f"Tool-call budget reached ({MAX_SPECIALIST_TOOL_ROUNDS} rounds).",
                        )
                    ]
                    if tool_budget_exhausted
                    else []
                ),
                make_event("data_findings", findings=data_payload["findings"]),
            ],
        }

    async def direct_response_node(state: AgentState, config: RunnableConfig | None = None) -> dict[str, object]:
        answer, _, metric = await agents["direct_response"].ainvoke_text(
            _common_payload(state, DIRECT_RESPONSE_SYSTEM_PROMPT),
            run_id=state["id"],
            config=config,
        )
        return {
            "final_answer": answer,
            "messages": [AIMessage(content=answer)],
            "agent_metrics": [metric.model_dump()],
            "events": [
                make_event("direct_response_started", agent="direct_response_agent"),
                *[make_event("answer_chunk", delta=chunk) for chunk in _chunk_answer(answer)],
            ],
        }

    async def clarify_node(state: AgentState, config: RunnableConfig | None = None) -> dict[str, object]:
        answer, _, metric = await agents["clarify"].ainvoke_text(
            _common_payload(state, CLARIFY_SYSTEM_PROMPT),
            run_id=state["id"],
            config=config,
        )
        return {
            "needs_clarification": True,
            "final_answer": answer,
            "messages": [AIMessage(content=answer)],
            "agent_metrics": [metric.model_dump()],
            "events": [
                make_event("clarify_started", agent="clarify_agent"),
                *[make_event("answer_chunk", delta=chunk) for chunk in _chunk_answer(answer)],
            ],
        }

    async def reporter_node(state: AgentState, config: RunnableConfig | None = None) -> dict[str, object]:
        answer, _, metric = await agents["reporter"].ainvoke_text(
            {
                "messages": with_system_message(
                    REPORTER_SYSTEM_PROMPT,
                    state["messages"],
                    extras=build_reporter_context_messages(
                        route=str(state.get("route") or ChatRoute.hybrid),
                        document_findings=state["document_findings"],
                        data_findings=state["data_findings"],
                    ),
                ),
            },
            run_id=state["id"],
            config=config,
        )
        return {
            "final_answer": answer,
            "messages": [AIMessage(content=answer)],
            "agent_metrics": [metric.model_dump()],
            "events": [
                make_event("reporter_started", agent="reporter"),
                *[make_event("answer_chunk", delta=chunk) for chunk in _chunk_answer(answer)],
            ],
        }

    async def finalize_node(state: AgentState, _: RunnableConfig | None = None) -> dict[str, object]:
        summary = _cost_summary(state["agent_metrics"])
        return {
            "status": ChatRunStatus.completed,
            "total_cost_usd": summary["total_cost_usd"],
            "events": [
                make_event(
                    "completed",
                    status=ChatRunStatus.completed,
                    route=state.get("route"),
                    needs_clarification=state["needs_clarification"],
                    final_answer=state.get("final_answer") or "",
                    cost_summary=summary,
                )
            ],
        }

    def route_from_router(state: AgentState):
        route = state.get("route")
        if route == ChatRoute.direct_response:
            return "direct_response_agent"
        if route == ChatRoute.clarify:
            return "clarify_agent"
        if route == ChatRoute.document:
            return "document_agent"
        if route == ChatRoute.data:
            return "data_agent"
        return ["document_agent", "data_agent"]

    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("direct_response_agent", direct_response_node)
    graph.add_node("clarify_agent", clarify_node)
    graph.add_node("document_agent", document_node)
    graph.add_node("data_agent", data_node)
    graph.add_node("reporter", reporter_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", route_from_router)
    graph.add_edge("direct_response_agent", "finalize")
    graph.add_edge("clarify_agent", "finalize")
    graph.add_edge("document_agent", "reporter")
    graph.add_edge("data_agent", "reporter")
    graph.add_edge("reporter", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()
