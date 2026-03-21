import re
from functools import lru_cache

from docling_core.transforms.chunker import HybridChunker
from docling_core.transforms.chunker.base import BaseChunk
from transformers import AutoTokenizer

from app.services.pdf_ingestion.document_context import DocumentContext

ENTITY_PATTERNS = [
    re.compile(r"\bMS-\d+\b"),
    re.compile(r"\bVO-\d+\b"),
    re.compile(r"\bNCR-\d+\b"),
    re.compile(r"\bR-\d+\b"),
]


@lru_cache(maxsize=1)
def get_hybrid_chunker() -> HybridChunker:
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    return HybridChunker(tokenizer=tokenizer, max_tokens=300)


class ChunkRecordBuilder:
    def build(self, *, document, document_context: DocumentContext) -> list[dict[str, object]]:
        chunker = get_hybrid_chunker()
        chunk_records: list[dict[str, object]] = []

        for index, chunk in enumerate(chunker.chunk(document), start=1):
            chunk_records.append(
                self._build_chunk_record(
                    chunk=chunk,
                    chunk_index=index,
                    document_context=document_context,
                    contextualized_text=chunker.contextualize(chunk),
                )
            )

        return chunk_records

    def _build_chunk_record(
        self,
        *,
        chunk: BaseChunk,
        chunk_index: int,
        document_context: DocumentContext,
        contextualized_text: str,
    ) -> dict[str, object]:
        headings = [heading for heading in chunk.meta.headings or [] if heading]
        page_numbers = self._extract_page_numbers(chunk)
        chunk_kind = self._infer_chunk_kind(chunk)
        raw_text = chunk.text.strip()

        return {
            "chunk_id": f"{document_context.document_id}_chunk_{chunk_index:04d}",
            "document_id": document_context.document_id,
            "chunk_index": chunk_index,
            "source_doc": document_context.source_doc,
            "document_type": document_context.document_type,
            "reporting_period": document_context.reporting_period,
            "title": document_context.title,
            "project": document_context.project,
            "heading_path": headings,
            "chunk_kind": chunk_kind,
            "page_span": page_numbers,
            "raw_text": raw_text,
            "contextualized_text": self._prepend_document_context(
                contextualized_text=contextualized_text.strip(),
                document_context=document_context,
                headings=headings,
                page_numbers=page_numbers,
                chunk_kind=chunk_kind,
            ),
            "contains_entities": self._extract_entities(raw_text),
        }

    def _prepend_document_context(
        self,
        *,
        contextualized_text: str,
        document_context: DocumentContext,
        headings: list[str],
        page_numbers: list[int],
        chunk_kind: str,
    ) -> str:
        prefix_lines = [
            f"Document: {document_context.source_doc}",
            f"Document type: {document_context.document_type}",
        ]
        if document_context.reporting_period:
            prefix_lines.append(f"Reporting period: {document_context.reporting_period}")
        if document_context.reporting_date:
            prefix_lines.append(f"Reporting date: {document_context.reporting_date}")
        if document_context.project:
            prefix_lines.append(f"Project: {document_context.project}")
        if document_context.title:
            prefix_lines.append(f"Title: {document_context.title}")
        if headings:
            prefix_lines.append(f"Section: {' > '.join(headings)}")
        if page_numbers:
            prefix_lines.append(f"Page span: {', '.join(str(page) for page in page_numbers)}")
        prefix_lines.append(f"Chunk type: {chunk_kind}")

        return "\n".join(prefix_lines) + "\n\n" + contextualized_text

    def _extract_page_numbers(self, chunk: BaseChunk) -> list[int]:
        pages = {
            prov.page_no
            for item in chunk.meta.doc_items
            for prov in item.prov
            if prov.page_no is not None
        }
        return sorted(pages)

    def _infer_chunk_kind(self, chunk: BaseChunk) -> str:
        labels = {self._normalize_label(item.label) for item in chunk.meta.doc_items}
        if labels == {"table"}:
            return "table"
        if labels and all("list" in label for label in labels):
            return "list"
        if len(labels) == 1:
            return next(iter(labels))
        return "mixed"

    def _normalize_label(self, label: object) -> str:
        if hasattr(label, "value"):
            return str(label.value).lower()
        return str(label).split(".")[-1].lower()

    def _extract_entities(self, text: str) -> list[str]:
        entities: set[str] = set()
        for pattern in ENTITY_PATTERNS:
            entities.update(pattern.findall(text))
        return sorted(entities)
