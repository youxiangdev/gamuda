from pathlib import Path
from datetime import date, datetime
import json
import re

from fastapi import HTTPException, UploadFile, status
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.ingestion_job import IngestionJob
from app.services.storage_service import StorageService

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx"}
ALLOWED_DOCUMENT_TYPES = {"project_description", "progress_update"}
REPORTING_PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DEFAULT_PROJECT_ID = "east-metro"
DEFAULT_PACKAGE_ID = "v3"


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
            project_id=(project_id.strip() if project_id else DEFAULT_PROJECT_ID),
            package_id=(package_id.strip() if package_id else DEFAULT_PACKAGE_ID),
            document_type=document_type,
            reporting_period=reporting_period,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_document(self, document_id: str) -> Document | None:
        return self.db.get(Document, document_id)

    def list_documents(self) -> list[Document]:
        stmt = select(Document).order_by(Document.created_at.desc())
        return list(self.db.scalars(stmt))

    def get_tabular_profile(self, document_id: str) -> dict[str, object]:
        document = self.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        artifact_dir = self.storage_service.ensure_artifact_dir(document_id)
        profile_path = artifact_dir / "tabular_profile.json"
        if not profile_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tabular profile not found for this document.",
            )

        return json.loads(profile_path.read_text(encoding="utf-8"))

    def get_document_file_path(self, document_id: str) -> tuple[Document, Path]:
        document = self.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        file_path = Path(document.storage_path)
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found.")

        return document, file_path

    def get_document_file_view(self, document_id: str) -> dict[str, object]:
        document = self.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        if document.extension == ".pdf":
            self.get_document_file_path(document_id)
            return {
                "viewer_type": "pdf",
                "file_url": f"/api/v1/documents/{document_id}/file",
                "sheets": [],
            }

        if document.extension in {".csv", ".xlsx"}:
            return {
                "viewer_type": "tabular",
                "sheets": self._get_tabular_view_sheets(document),
            }

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct file viewing is not supported for this file type.",
        )

    def _get_tabular_view_sheets(self, document: Document) -> list[dict[str, object]]:
        artifact_dir = self.storage_service.ensure_artifact_dir(document.id)
        profile_path = artifact_dir / "tabular_profile.json"

        if profile_path.exists():
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            datasets = profile.get("datasets") or []
            sheets = []
            for dataset in datasets:
                parquet_path = Path(str(dataset.get("parquet_path") or ""))
                if not parquet_path.is_absolute():
                    parquet_path = artifact_dir / parquet_path.name
                if not parquet_path.exists():
                    continue

                dataframe = pd.read_parquet(parquet_path)
                sheets.append(
                    self._dataframe_to_sheet(
                        str(dataset.get("dataset_name") or parquet_path.stem),
                        dataframe,
                    )
                )

            if sheets:
                return sheets

        _, file_path = self.get_document_file_path(document.id)

        if document.extension == ".csv":
            dataframe = pd.read_csv(file_path, dtype=object, keep_default_na=True)
            return [self._dataframe_to_sheet("CSV", dataframe)]

        workbook = pd.read_excel(file_path, sheet_name=None, dtype=object)
        return [
            self._dataframe_to_sheet(sheet_name, dataframe)
            for sheet_name, dataframe in workbook.items()
        ]

    def list_document_overviews(self) -> list[dict[str, object]]:
        documents = self.list_documents()
        overviews: list[dict[str, object]] = []

        for document in documents:
            latest_job = self.db.scalar(
                select(IngestionJob)
                .where(IngestionJob.document_id == document.id)
                .order_by(IngestionJob.created_at.desc())
                .limit(1)
            )
            chunk_count = self.db.scalar(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)
            ) or 0

            overviews.append(
                {
                    "id": document.id,
                    "original_filename": document.original_filename,
                    "extension": document.extension,
                    "file_size": document.file_size,
                    "document_type": document.document_type,
                    "reporting_period": document.reporting_period,
                    "project_id": document.project_id or DEFAULT_PROJECT_ID,
                    "package_id": document.package_id or DEFAULT_PACKAGE_ID,
                    "created_at": document.created_at,
                    "updated_at": document.updated_at,
                    "latest_ingestion_status": latest_job.status if latest_job else None,
                    "latest_ingestion_summary": latest_job.summary if latest_job else None,
                    "latest_ingestion_error": latest_job.error_message if latest_job else None,
                    "chunk_count": int(chunk_count),
                }
            )

        return overviews

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

    def _dataframe_to_sheet(self, sheet_name: str, dataframe: pd.DataFrame) -> dict[str, object]:
        normalized = dataframe.copy()
        normalized.columns = [str(column) for column in normalized.columns]
        normalized = normalized.where(pd.notna(normalized), None)

        rows = [
            {
                column: self._normalize_cell_value(value)
                for column, value in row.items()
            }
            for row in normalized.to_dict(orient="records")
        ]

        return {
            "sheet_name": sheet_name,
            "columns": list(normalized.columns),
            "row_count": len(rows),
            "rows": rows,
        }

    def _normalize_cell_value(self, value: object) -> object | None:
        if value is None:
            return None

        if hasattr(value, "item") and not isinstance(value, (str, bytes)):
            try:
                value = value.item()
            except (ValueError, TypeError):
                pass

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        if isinstance(value, (str, int, float, bool)):
            return value

        return str(value)
