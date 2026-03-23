from __future__ import annotations

import operator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class ChatRoute(StrEnum):
    direct_response = "direct_response"
    clarify = "clarify"
    document = "document"
    data = "data"
    hybrid = "hybrid"


class ChatRunStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class EvidenceItem(BaseModel):
    source: str
    citation: str
    snippet: str


class DocumentEvidenceRef(BaseModel):
    chunk_id: str


class Finding(BaseModel):
    claim: str
    evidence: list[EvidenceItem] = Field(default_factory=list)


class DocumentFinding(BaseModel):
    claim: str
    evidence: list[DocumentEvidenceRef] = Field(default_factory=list)


class FindingsPayload(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    insufficient_evidence: bool = False


class DocumentFindingsPayload(BaseModel):
    findings: list[DocumentFinding] = Field(default_factory=list)
    insufficient_evidence: bool = False


class DataEvidenceRef(BaseModel):
    query_id: str


class DataFinding(BaseModel):
    claim: str
    evidence: list[DataEvidenceRef] = Field(default_factory=list)


class DataFindingsPayload(BaseModel):
    findings: list[DataFinding] = Field(default_factory=list)
    insufficient_evidence: bool = False


class RouterDecision(BaseModel):
    route: ChatRoute
    needs_clarification: bool = False


class AgentMetric(BaseModel):
    agent: str
    provider: str
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    input_cost_usd: float | None = None
    output_cost_usd: float | None = None
    total_cost_usd: float | None = None
    pricing_source: str | None = None


class GraphEvent(TypedDict, total=False):
    event: str
    timestamp: str
    status: str
    route: str
    mode: str
    run_id: str
    question: str
    created_at: str
    agent: str
    findings: list[dict[str, Any]]
    delta: str
    needs_clarification: bool
    final_answer: str
    detail: str
    cost_summary: dict[str, Any]


class AgentState(MessagesState):
    id: str
    status: str
    created_at: str
    route: str | None
    needs_clarification: bool
    document_findings: dict[str, Any]
    data_findings: dict[str, Any]
    final_answer: str | None
    total_cost_usd: float | None
    events: Annotated[list[GraphEvent], operator.add]
    agent_metrics: Annotated[list[dict[str, Any]], operator.add]


def build_initial_state(*, messages: list[BaseMessage]) -> AgentState:
    return {
        "id": str(uuid4()),
        "messages": messages,
        "status": ChatRunStatus.queued,
        "created_at": datetime.now(UTC).isoformat(),
        "route": None,
        "needs_clarification": False,
        "document_findings": {"findings": [], "insufficient_evidence": False},
        "data_findings": {"findings": [], "insufficient_evidence": False},
        "final_answer": None,
        "total_cost_usd": None,
        "events": [],
        "agent_metrics": [],
    }


def make_event(event: str, **payload: Any) -> GraphEvent:
    return {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        **payload,
    }
