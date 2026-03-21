from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    stored_filename: str
    content_type: str
    extension: str
    storage_path: str
    file_size: int
    project_id: str | None
    package_id: str | None
    document_type: str | None
    reporting_period: str | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentRead
    ingestion_job_id: str
    ingestion_status: str
