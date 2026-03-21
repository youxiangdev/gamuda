from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    chunk_id: str
    chunk_index: int
    source_doc: str
    document_type: str
    reporting_period: str | None
    title: str | None
    project: str | None
    heading_path: list[str]
    chunk_kind: str
    page_span: list[int]
    raw_text: str
    contextualized_text: str
    contains_entities: list[str]
    embedding_model: str | None
    embedding_task: str | None
    embedded_at: datetime | None
    created_at: datetime
    updated_at: datetime
