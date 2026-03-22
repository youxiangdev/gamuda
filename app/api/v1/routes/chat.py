from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRunCreate, ChatRunCreated, ChatThreadDetailRead, ChatThreadRead
from app.services.chat_service import chat_service

router = APIRouter()


@router.post("/runs", response_model=ChatRunCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_chat_run(payload: ChatRunCreate) -> ChatRunCreated:
    try:
        run = await chat_service.create_run(payload.question, thread_id=payload.thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ChatRunCreated(
        run_id=run.id,
        thread_id=run.thread_id,
        user_message_id=run.user_message_id,
        assistant_message_id=run.assistant_message_id,
        question=run.question,
        status=run.status,
        created_at=run.created_at,
    )


@router.get("/runs/{run_id}/events")
async def stream_chat_run_events(run_id: str, request: Request) -> StreamingResponse:
    run = chat_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat run not found.")

    async def event_stream():
        async for event in chat_service.stream_events(run_id):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/threads", response_model=list[ChatThreadRead])
def list_chat_threads() -> list[ChatThreadRead]:
    return [ChatThreadRead.model_validate(thread) for thread in chat_service.list_threads()]


@router.get("/threads/{thread_id}", response_model=ChatThreadDetailRead)
def get_chat_thread(thread_id: str) -> ChatThreadDetailRead:
    thread = chat_service.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread not found.")
    return ChatThreadDetailRead.model_validate(thread)
