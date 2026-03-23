from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.ai import AgentState, ChatRunStatus, build_initial_state, get_chat_graph
from app.ai.state import make_event
from app.db.session import SessionLocal
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread


class ChatMessageStatus(StrEnum):
    pending = "pending"
    streaming = "streaming"
    completed = "completed"
    failed = "failed"


@dataclass(slots=True)
class LiveRunTransport:
    run_id: str
    thread_id: str
    user_message_id: str
    assistant_message_id: str
    question: str
    state: AgentState
    graph_config: dict[str, Any]
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)


class ChatService:
    def __init__(self) -> None:
        self._runs: dict[str, LiveRunTransport] = {}

    async def create_run(self, question: str, thread_id: str | None = None) -> dict[str, object]:
        normalized_question = question.strip()
        now = datetime.now(UTC)

        with SessionLocal() as db:
            thread = self._get_or_create_thread(db, thread_id, normalized_question, now)
            user_message = ChatMessage(
                thread_id=thread.id,
                role="user",
                status=ChatMessageStatus.completed,
                content=normalized_question,
            )
            assistant_message = ChatMessage(
                thread_id=thread.id,
                role="assistant",
                status=ChatMessageStatus.pending,
                content="",
            )
            db.add_all([user_message, assistant_message])
            db.flush()
            thread.updated_at = now
            db.commit()

            messages = self._load_thread_messages(db, thread.id)

        state = build_initial_state(messages=messages)
        transport = LiveRunTransport(
            run_id=state["id"],
            thread_id=thread.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            question=normalized_question,
            state=state,
            graph_config={
                "configurable": {"thread_id": thread.id},
                "metadata": {
                    "thread_id": thread.id,
                    "run_id": state["id"],
                    "user_message_id": user_message.id,
                    "assistant_message_id": assistant_message.id,
                },
                "tags": ["chat", "langgraph"],
            },
        )
        self._runs[state["id"]] = transport
        asyncio.create_task(self._process_run(state["id"]))
        return {
            "id": state["id"],
            "thread_id": transport.thread_id,
            "user_message_id": transport.user_message_id,
            "assistant_message_id": transport.assistant_message_id,
            "question": transport.question,
            "status": state["status"],
            "created_at": state["created_at"],
        }

    def get_run(self, run_id: str) -> AgentState | None:
        transport = self._runs.get(run_id)
        return transport.state if transport is not None else None

    def list_threads(self) -> list[dict[str, object]]:
        with SessionLocal() as db:
            stmt = (
                select(
                    ChatThread.id,
                    ChatThread.title,
                    ChatThread.created_at,
                    ChatThread.updated_at,
                    func.count(ChatMessage.id).label("message_count"),
                )
                .outerjoin(ChatMessage, ChatMessage.thread_id == ChatThread.id)
                .group_by(ChatThread.id)
                .order_by(ChatThread.updated_at.desc())
            )
            rows = db.execute(stmt).all()

        return [
            {
                "id": row.id,
                "title": row.title,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "message_count": int(row.message_count or 0),
            }
            for row in rows
        ]

    def get_thread(self, thread_id: str) -> dict[str, object] | None:
        with SessionLocal() as db:
            stmt = (
                select(ChatThread)
                .options(selectinload(ChatThread.messages))
                .where(ChatThread.id == thread_id)
            )
            thread = db.scalar(stmt)
            if thread is None:
                return None

            messages = sorted(thread.messages, key=lambda message: message.created_at)
            return {
                "id": thread.id,
                "title": thread.title,
                "created_at": thread.created_at,
                "updated_at": thread.updated_at,
                "messages": messages,
            }

    async def stream_events(self, run_id: str):
        transport = self._runs.get(run_id)
        if transport is None:
            raise KeyError(run_id)

        cursor = 0
        while True:
            events = transport.state["events"]
            while cursor < len(events):
                event = events[cursor]
                cursor += 1
                yield self._format_sse(event_id=cursor, event=event)
                if event["event"] in {"completed", "error"}:
                    return

            async with transport.condition:
                await transport.condition.wait()

    async def _process_run(self, run_id: str) -> None:
        transport = self._runs[run_id]
        try:
            graph = get_chat_graph()
            self._mark_run_started(
                assistant_message_id=transport.assistant_message_id,
                thread_id=transport.thread_id,
            )
            async for snapshot in graph.astream(
                transport.state,
                config=transport.graph_config,
                stream_mode="values",
            ):
                transport.state = snapshot
                async with transport.condition:
                    transport.condition.notify_all()

            final_answer = transport.state.get("final_answer") or ""
            self._mark_run_completed(
                assistant_message_id=transport.assistant_message_id,
                thread_id=transport.thread_id,
                final_answer=final_answer,
            )
        except Exception as exc:  # pragma: no cover - runtime safety for SSE loop
            error_event = make_event(
                "error",
                status=ChatRunStatus.failed,
                detail=str(exc),
            )
            transport.state = {
                **transport.state,
                "status": ChatRunStatus.failed,
                "final_answer": str(exc),
                "events": [*transport.state["events"], error_event],
            }
            self._mark_run_failed(
                assistant_message_id=transport.assistant_message_id,
                thread_id=transport.thread_id,
                detail=str(exc),
            )
            async with transport.condition:
                transport.condition.notify_all()

    def _get_or_create_thread(
        self,
        db,
        thread_id: str | None,
        question: str,
        now: datetime,
    ) -> ChatThread:
        if thread_id:
            thread = db.get(ChatThread, thread_id)
            if thread is None:
                raise ValueError("Chat thread not found.")
            return thread

        thread = ChatThread(title=self._build_thread_title(question))
        thread.updated_at = now
        db.add(thread)
        db.flush()
        return thread

    def _load_thread_messages(self, db, thread_id: str) -> list[BaseMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = list(db.scalars(stmt))
        history: list[BaseMessage] = []
        for message in messages:
            content = message.content.strip()
            if not content:
                continue
            if message.role == "assistant":
                history.append(AIMessage(content=content))
            else:
                history.append(HumanMessage(content=content))
        return history

    def _mark_run_started(self, assistant_message_id: str, thread_id: str) -> None:
        now = datetime.now(UTC)
        with SessionLocal() as db:
            assistant_message = db.get(ChatMessage, assistant_message_id)
            thread = db.get(ChatThread, thread_id)
            if assistant_message is None or thread is None:
                return
            assistant_message.status = ChatMessageStatus.streaming
            thread.updated_at = now
            db.commit()

    def _mark_run_completed(self, assistant_message_id: str, thread_id: str, final_answer: str) -> None:
        now = datetime.now(UTC)
        with SessionLocal() as db:
            assistant_message = db.get(ChatMessage, assistant_message_id)
            thread = db.get(ChatThread, thread_id)
            if assistant_message is None or thread is None:
                return
            assistant_message.status = ChatMessageStatus.completed
            assistant_message.content = final_answer
            thread.updated_at = now
            db.commit()

    def _mark_run_failed(self, assistant_message_id: str, thread_id: str, detail: str) -> None:
        now = datetime.now(UTC)
        with SessionLocal() as db:
            assistant_message = db.get(ChatMessage, assistant_message_id)
            thread = db.get(ChatThread, thread_id)
            if assistant_message is None or thread is None:
                return
            assistant_message.status = ChatMessageStatus.failed
            assistant_message.content = detail
            thread.updated_at = now
            db.commit()

    def _build_thread_title(self, question: str) -> str:
        collapsed = " ".join(question.split())
        return collapsed[:77] + "..." if len(collapsed) > 80 else collapsed

    def _format_sse(self, *, event_id: int, event: dict[str, object]) -> str:
        payload = json.dumps({"event_id": event_id, **event}, default=str)
        return f"id: {event_id}\nevent: {event['event']}\ndata: {payload}\n\n"


chat_service = ChatService()
