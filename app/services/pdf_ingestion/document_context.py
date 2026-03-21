import re
from dataclasses import asdict, dataclass

from docling_core.types.doc.document import DoclingDocument


@dataclass
class DocumentContext:
    document_id: str
    source_doc: str
    document_type: str
    reporting_period: str | None
    title: str | None
    project: str | None
    prepared_for: str | None
    reporting_date: str | None
    page_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class DocumentContextExtractor:
    """Extract lightweight document-level context from Docling output and upload metadata."""

    def extract(
        self,
        *,
        document: DoclingDocument,
        document_id: str,
        source_doc: str,
        document_type: str,
        reporting_period: str | None,
    ) -> DocumentContext:
        markdown = document.export_to_markdown()
        title = self._extract_title(markdown)
        project = self._extract_section_value(markdown, section_heading="Project")
        prepared_for = self._extract_label_value(markdown, "Prepared for")
        reporting_date = self._extract_label_value(markdown, "Reporting date")

        return DocumentContext(
            document_id=document_id,
            source_doc=source_doc,
            document_type=document_type,
            reporting_period=reporting_period,
            title=title,
            project=project,
            prepared_for=prepared_for,
            reporting_date=reporting_date,
            page_count=len(document.pages),
        )

    def _extract_title(self, markdown: str) -> str | None:
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return None

    def _extract_section_value(self, markdown: str, *, section_heading: str) -> str | None:
        lines = markdown.splitlines()
        target = f"## {section_heading}".lower()
        for index, line in enumerate(lines):
            if line.strip().lower() != target:
                continue
            for candidate in lines[index + 1 :]:
                stripped = candidate.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    return None
                return stripped
        return None

    def _extract_label_value(self, markdown: str, label: str) -> str | None:
        lines = markdown.splitlines()
        label_pattern = re.compile(rf"^{re.escape(label)}\s*:?\s*$", re.IGNORECASE)
        inline_pattern = re.compile(rf"^{re.escape(label)}\s*:\s*(.+)$", re.IGNORECASE)

        for index, line in enumerate(lines):
            stripped = line.strip()
            inline_match = inline_pattern.match(stripped)
            if inline_match:
                return inline_match.group(1).strip()

            if label_pattern.match(stripped):
                for candidate in lines[index + 1 :]:
                    value = candidate.strip()
                    if not value:
                        continue
                    if value.startswith("#"):
                        return None
                    return value
        return None
