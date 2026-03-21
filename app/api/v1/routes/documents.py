from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chunk import DocumentChunkRead
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.services.chunk_service import ChunkService
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService

router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    package_id: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    reporting_period: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    document_service = DocumentService(db)
    ingestion_service = IngestionService(db)

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required.")

    document = document_service.create_document(
        file=file,
        project_id=project_id,
        package_id=package_id,
        document_type=document_type,
        reporting_period=reporting_period,
    )
    job = ingestion_service.create_job(document)
    background_tasks.add_task(ingestion_service.run_job, job.id)

    return DocumentUploadResponse(
        message="Document accepted for ingestion.",
        document=DocumentRead.model_validate(document),
        ingestion_job_id=job.id,
        ingestion_status=job.status,
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentRead:
    document_service = DocumentService(db)
    document = document_service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentRead.model_validate(document)


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
def list_document_chunks(document_id: str, db: Session = Depends(get_db)) -> list[DocumentChunkRead]:
    document_service = DocumentService(db)
    document = document_service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    chunks = ChunkService(db).list_document_chunks(document_id)
    return [DocumentChunkRead.model_validate(chunk) for chunk in chunks]
