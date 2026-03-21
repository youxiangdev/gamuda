from pathlib import Path
import re

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.storage_service import StorageService

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx"}
ALLOWED_DOCUMENT_TYPES = {"project_description", "progress_update"}
REPORTING_PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage_service = StorageService()

    def create_document(
        self,
        file: UploadFile,
        project_id: str | None,
        package_id: str | None,
        document_type: str | None,
        reporting_period: str | None,
    ) -> Document:
        extension = Path(file.filename or "").suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Allowed types: PDF, CSV, XLSX.",
            )

        document_type = self._validate_document_type(document_type)
        reporting_period = self._validate_reporting_period(document_type, reporting_period)

        stored_file = self.storage_service.save_upload(file)
        document = Document(
            original_filename=stored_file.original_filename,
            stored_filename=stored_file.stored_filename,
            content_type=stored_file.content_type,
            extension=stored_file.extension,
            storage_path=stored_file.storage_path,
            file_size=stored_file.file_size,
            project_id=project_id,
            package_id=package_id,
            document_type=document_type,
            reporting_period=reporting_period,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_document(self, document_id: str) -> Document | None:
        return self.db.get(Document, document_id)

    def _validate_document_type(self, document_type: str | None) -> str:
        if document_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="document_type is required. Allowed values: project_description, progress_update.",
            )

        normalized = document_type.strip().lower()
        if normalized not in ALLOWED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid document_type. Allowed values: project_description, progress_update.",
            )
        return normalized

    def _validate_reporting_period(self, document_type: str, reporting_period: str | None) -> str | None:
        if document_type == "progress_update":
            if reporting_period is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="reporting_period is required for progress_update documents and must use YYYY-MM format.",
                )

            normalized = reporting_period.strip()
            if not REPORTING_PERIOD_PATTERN.match(normalized):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid reporting_period. Expected format: YYYY-MM.",
                )
            return normalized

        return None
