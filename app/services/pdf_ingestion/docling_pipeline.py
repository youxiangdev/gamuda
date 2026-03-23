import json
from dataclasses import dataclass
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.pipeline_options import TableFormerMode
from docling.document_converter import DocumentConverter
from docling.document_converter import PdfFormatOption

from app.core.config import get_settings
from app.services.pdf_ingestion.chunk_builder import ChunkRecordBuilder
from app.services.pdf_ingestion.document_context import DocumentContextExtractor
from app.services.storage_service import StorageService


@dataclass
class PdfIngestionResult:
    summary: str
    document_context: dict[str, object]
    chunk_records: list[dict[str, object]]


class DoclingPipeline:
    """Structured PDF ingestion backed by Docling."""

    def __init__(self) -> None:
        settings = get_settings()
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.force_backend_text = True
        pipeline_options.do_table_structure = settings.pdf_do_table_structure
        pipeline_options.document_timeout = settings.pdf_document_timeout_seconds
        pipeline_options.accelerator_options.num_threads = settings.pdf_num_threads
        pipeline_options.layout_batch_size = settings.pdf_layout_batch_size
        pipeline_options.table_batch_size = settings.pdf_table_batch_size
        pipeline_options.table_structure_options.mode = TableFormerMode(settings.pdf_table_mode)

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        self.chunk_builder = ChunkRecordBuilder()
        self.context_extractor = DocumentContextExtractor()
        self.storage_service = StorageService()

    def ingest(
        self,
        file_path: str,
        document_id: str,
        *,
        source_doc: str,
        document_type: str,
        reporting_period: str | None,
    ) -> PdfIngestionResult:
        path = Path(file_path)
        result = self.converter.convert(source=str(path))
        artifact_dir = self.storage_service.ensure_artifact_dir(document_id)
        document = result.document
        markdown = document.export_to_markdown()
        document_dict = document.export_to_dict()
        document_context = self.context_extractor.extract(
            document=document,
            document_id=document_id,
            source_doc=source_doc,
            document_type=document_type,
            reporting_period=reporting_period,
        )
        chunk_records = self.chunk_builder.build(
            document=document,
            document_context=document_context,
        )

        markdown_path = artifact_dir / "document.md"
        json_path = artifact_dir / "document.json"
        context_path = artifact_dir / "document_context.json"
        chunks_path = artifact_dir / "chunks.json"

        markdown_path.write_text(markdown, encoding="utf-8")
        json_path.write_text(json.dumps(document_dict, indent=2), encoding="utf-8")
        context_path.write_text(json.dumps(document_context.to_dict(), indent=2), encoding="utf-8")
        chunks_path.write_text(json.dumps(chunk_records, indent=2), encoding="utf-8")

        page_count = len(document.pages)
        return PdfIngestionResult(
            summary=(
                f"PDF parsed with Docling into {page_count} page(s) and {len(chunk_records)} chunk(s). "
                f"Artifacts saved to {artifact_dir}."
            ),
            document_context=document_context.to_dict(),
            chunk_records=chunk_records,
        )
