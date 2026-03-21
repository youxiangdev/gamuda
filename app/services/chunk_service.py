from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


class ChunkService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_document_chunks(self, *, document_id: str, chunk_records: list[dict[str, object]]) -> None:
        self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

        for record in chunk_records:
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_id=str(record["chunk_id"]),
                chunk_index=int(record["chunk_index"]),
                source_doc=str(record["source_doc"]),
                document_type=str(record["document_type"]),
                reporting_period=record.get("reporting_period"),
                title=record.get("title"),
                project=record.get("project"),
                heading_path=list(record.get("heading_path", [])),
                chunk_kind=str(record["chunk_kind"]),
                page_span=list(record.get("page_span", [])),
                raw_text=str(record["raw_text"]),
                contextualized_text=str(record["contextualized_text"]),
                contains_entities=list(record.get("contains_entities", [])),
            )
            self.db.add(chunk)

        self.db.commit()

    def list_document_chunks(self, document_id: str) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(self.db.scalars(stmt))

    def list_chunks_for_embedding(self, document_id: str) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(self.db.scalars(stmt))

    def update_chunk_embeddings(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        *,
        embedding_model: str,
        embedding_task: str,
    ) -> None:
        embedded_at = datetime.now(UTC)
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            chunk.embedding = embedding
            chunk.embedding_model = embedding_model
            chunk.embedding_task = embedding_task
            chunk.embedded_at = embedded_at

        self.db.commit()
