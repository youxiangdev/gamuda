from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


@dataclass
class StoredFile:
    original_filename: str
    stored_filename: str
    storage_path: str
    content_type: str
    extension: str
    file_size: int


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, file: UploadFile) -> StoredFile:
        original_filename = file.filename or "upload"
        extension = Path(original_filename).suffix.lower()
        stored_filename = f"{uuid4()}{extension}"
        destination = self.settings.storage_dir / stored_filename

        file.file.seek(0)
        content = file.file.read()
        destination.write_bytes(content)

        return StoredFile(
            original_filename=original_filename,
            stored_filename=stored_filename,
            storage_path=str(destination),
            content_type=file.content_type or "application/octet-stream",
            extension=extension,
            file_size=len(content),
        )

    def ensure_artifact_dir(self, document_id: str) -> Path:
        destination = self.settings.artifacts_dir / document_id
        destination.mkdir(parents=True, exist_ok=True)
        return destination
