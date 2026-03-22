from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRunCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None


class ChatRunCreated(BaseModel):
    run_id: str
    thread_id: str
    user_message_id: str
    assistant_message_id: str
    question: str
    status: str
    created_at: datetime


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    role: str
    status: str
    content: str
    created_at: datetime
    updated_at: datetime


class ChatThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ChatThreadDetailRead(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageRead]
