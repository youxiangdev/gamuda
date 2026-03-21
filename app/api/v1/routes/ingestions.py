from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ingestion import IngestionJobRead
from app.services.ingestion_service import IngestionService

router = APIRouter()


@router.get("/{job_id}", response_model=IngestionJobRead)
def get_ingestion_job(job_id: str, db: Session = Depends(get_db)) -> IngestionJobRead:
    ingestion_service = IngestionService(db)
    job = ingestion_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion job not found.")
    return IngestionJobRead.model_validate(job)
