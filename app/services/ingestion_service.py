import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.chunk_service import ChunkService
from app.models.document import Document
from app.models.ingestion_job import IngestionJob, IngestionStatus
from app.services.csv_ingestion.csv_loader import CsvLoader
from app.services.embedding_service import EmbeddingService
from app.services.pdf_ingestion.docling_pipeline import DoclingPipeline

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_job(self, document: Document) -> IngestionJob:
        file_type = document.extension.removeprefix(".")
        job = IngestionJob(document_id=document.id, file_type=file_type, status=IngestionStatus.pending)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: str) -> IngestionJob | None:
        return self.db.get(IngestionJob, job_id)

    def run_job(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(IngestionJob, job_id)
            if job is None:
                logger.warning("Ingestion job %s not found.", job_id)
                return

            document = db.get(Document, job.document_id)
            if document is None:
                raise ValueError("Document not found for ingestion job.")

            job.status = IngestionStatus.processing
            job.started_at = datetime.now(UTC)
            db.commit()

            if document.extension == ".pdf":
                pdf_result = DoclingPipeline().ingest(
                    document.storage_path,
                    document.id,
                    source_doc=document.original_filename,
                    document_type=document.document_type or "project_description",
                    reporting_period=document.reporting_period,
                )
                ChunkService(db).replace_document_chunks(
                    document_id=document.id,
                    chunk_records=pdf_result.chunk_records,
                )
                embedding_result = EmbeddingService(db).embed_document_chunks(document.id)
                summary = pdf_result.summary
                if embedding_result["enabled"]:
                    summary = (
                        f"{summary} Embedded {embedding_result['embedded_chunks']} chunk(s) "
                        f"with {embedding_result['model']}."
                    )
                else:
                    summary = f"{summary} Embedding skipped: {embedding_result['reason']}"
            elif document.extension in {".csv", ".xlsx"}:
                summary = CsvLoader().ingest(
                    document.storage_path,
                    document.id,
                    source_name=document.original_filename,
                )
            else:
                raise ValueError(f"Unsupported extension during ingestion: {document.extension}")

            job.status = IngestionStatus.completed
            job.summary = summary
            job.completed_at = datetime.now(UTC)
            job.error_message = None
            db.commit()
        except Exception as exc:
            logger.exception("Failed ingestion job %s", job_id)
            job = db.get(IngestionJob, job_id)
            if job is not None:
                job.status = IngestionStatus.failed
                job.error_message = str(exc)
                job.completed_at = datetime.now(UTC)
                db.commit()
        finally:
            db.close()
