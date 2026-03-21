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


class DocumentOverviewRead(BaseModel):
    id: str
    original_filename: str
    extension: str
    file_size: int
    document_type: str | None
    reporting_period: str | None
    project_id: str | None
    package_id: str | None
    created_at: datetime
    updated_at: datetime
    latest_ingestion_status: str | None
    latest_ingestion_summary: str | None
    latest_ingestion_error: str | None
    chunk_count: int


class TabularColumnRead(BaseModel):
    name: str
    dtype: str


class TabularDatasetProfileRead(BaseModel):
    dataset_name: str
    row_count: int
    column_count: int
    columns: list[TabularColumnRead]
    sample_rows: list[dict[str, object | None]]
    parquet_path: str


class TabularProfileRead(BaseModel):
    datasets: list[TabularDatasetProfileRead]
