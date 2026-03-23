from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool
from sqlalchemy import Text, cast, or_, select
from sqlalchemy.orm import Session

from app.ai.state import DocumentFindingsPayload, FindingsPayload
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EmbeddingService


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    source: str
    citation: str
    snippet: str
    page_span: list[int]
    heading_path: list[str]
    chunk_kind: str
    retrieval_score: float
    search_type: str


@dataclass(slots=True)
class DocumentToolRuntime:
    db: Session
    embedding_service: EmbeddingService
    seen_evidence: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    seen_chunks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def search_documents(self, query: str, top_k: int) -> str:
        results = self._semantic_search(query=query, top_k=top_k)
        self._remember(results)
        return json.dumps({"results": [result for result in results]}, ensure_ascii=True)

    def keyword_search_documents(self, keywords: Sequence[str], top_k: int) -> str:
        results = self._keyword_search(keywords=keywords, top_k=top_k)
        self._remember(results)
        return json.dumps({"results": [result for result in results]}, ensure_ascii=True)

    def validate_findings_payload(self, payload: DocumentFindingsPayload) -> FindingsPayload:
        validated_findings: list[dict[str, Any]] = []
        for finding in payload.findings[:3]:
            claim = str(finding.claim).strip()
            if not claim:
                continue

            validated_evidence: list[dict[str, str]] = []
            for item in finding.evidence:
                chunk_id = str(item.chunk_id).strip()
                allowed = self.seen_chunks.get(chunk_id)
                if allowed is None:
                    continue
                validated_evidence.append(
                    {
                        "source": str(allowed.get("source") or ""),
                        "citation": str(allowed.get("citation") or ""),
                        "snippet": str(allowed.get("snippet") or ""),
                    }
                )

            if validated_evidence:
                validated_findings.append({"claim": claim, "evidence": validated_evidence})

        return FindingsPayload(
            findings=validated_findings,
            insufficient_evidence=bool(payload.insufficient_evidence or not validated_findings),
        )

    def build_tools(self) -> list[BaseTool]:
        runtime = self

        @tool
        def search_documents(
            query: Annotated[str, "Natural-language query for semantic document retrieval."],
            top_k: Annotated[int, "Maximum number of chunks to return. Use 1 to 10."] = 8,
        ) -> str:
            """Semantic search over ingested PDF document chunks."""
            return runtime.search_documents(query=query, top_k=top_k)

        @tool
        def keyword_search_documents(
            keywords: Annotated[
                list[str],
                "Short keywords or phrases for exact lookup. Use at most 5 items.",
            ],
            top_k: Annotated[int, "Maximum number of chunks to return. Use 1 to 10."] = 8,
        ) -> str:
            """Keyword search over ingested PDF document chunks using phrases, dates, IDs, acronyms, or section terms."""
            return runtime.keyword_search_documents(keywords=keywords, top_k=top_k)

        return [
            search_documents,
            keyword_search_documents,
        ]

    def _semantic_search(self, *, query: str, top_k: int) -> list[dict[str, Any]]:
        if not self.embedding_service.enabled:
            return []

        try:
            embeddings = self.embedding_service._embed_texts([query], task="retrieval.query")
        except Exception:
            return []

        if not embeddings:
            return []

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(DocumentChunk.embedding.cosine_distance(embeddings[0]), DocumentChunk.chunk_index.asc())
            .limit(top_k)
        )
        chunks = list(self.db.scalars(stmt))
        return [
            self._serialize_chunk(chunk, search_type="semantic", retrieval_score=float(top_k - index))
            for index, chunk in enumerate(chunks, start=1)
        ]

    def _keyword_search(self, *, keywords: Sequence[str], top_k: int) -> list[dict[str, Any]]:
        cleaned_keywords = [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
        if not cleaned_keywords:
            return []

        conditions = []
        for keyword in cleaned_keywords[:5]:
            pattern = f"%{keyword}%"
            conditions.extend(
                [
                    DocumentChunk.raw_text.ilike(pattern),
                    DocumentChunk.contextualized_text.ilike(pattern),
                    DocumentChunk.source_doc.ilike(pattern),
                    DocumentChunk.title.ilike(pattern),
                    cast(DocumentChunk.heading_path, Text).ilike(pattern),
                ]
            )

        stmt = (
            select(DocumentChunk)
            .where(or_(*conditions))
            .order_by(DocumentChunk.updated_at.desc(), DocumentChunk.chunk_index.asc())
            .limit(top_k * 4)
        )
        chunks = list(self.db.scalars(stmt))

        scored: list[tuple[float, DocumentChunk]] = []
        for chunk in chunks:
            searchable = " ".join(
                [
                    chunk.raw_text or "",
                    chunk.contextualized_text or "",
                    chunk.source_doc or "",
                    chunk.title or "",
                    " ".join(chunk.heading_path or []),
                ]
            ).lower()
            score = 0.0
            for keyword in cleaned_keywords:
                if keyword.lower() in searchable:
                    score += 1.0
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            self._serialize_chunk(chunk, search_type="keyword", retrieval_score=score)
            for score, chunk in scored[:top_k]
        ]

    def _serialize_chunk(self, chunk: DocumentChunk, *, search_type: str, retrieval_score: float) -> dict[str, Any]:
        citation = self._format_citation(chunk)
        return {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source": chunk.source_doc,
            "citation": citation,
            "snippet": self._build_snippet(chunk.raw_text, chunk_kind=chunk.chunk_kind),
            "page_span": list(chunk.page_span or []),
            "heading_path": list(chunk.heading_path or []),
            "chunk_kind": chunk.chunk_kind,
            "retrieval_score": round(retrieval_score, 6),
            "search_type": search_type,
        }

    def _remember(self, results: Sequence[dict[str, Any]]) -> None:
        for result in results:
            source = str(result.get("source") or "").strip()
            citation = str(result.get("citation") or "").strip()
            chunk_id = str(result.get("chunk_id") or "").strip()
            if not source or not citation:
                continue
            self.seen_evidence[(source, citation)] = dict(result)
            if chunk_id:
                self.seen_chunks[chunk_id] = dict(result)

    def _format_citation(self, chunk: DocumentChunk) -> str:
        parts = [f"document={chunk.source_doc}", f"chunk={chunk.chunk_id}"]
        if chunk.page_span:
            parts.append(f"pages={','.join(str(page) for page in chunk.page_span)}")
        if chunk.heading_path:
            parts.append(f"section={' > '.join(chunk.heading_path)}")
        return " | ".join(parts)

    def _build_snippet(self, text: str, *, chunk_kind: str, limit: int = 220) -> str:
        cleaned = " ".join((text or "").split())
        if chunk_kind == "table":
            # Preserve full table rows when practical so the agent can compare values
            # instead of falling back to weaker narrative chunks.
            return cleaned[:1200].strip()
        return cleaned[:limit].strip()


def build_document_tools(db: Session) -> tuple[DocumentToolRuntime, list[BaseTool]]:
    runtime = DocumentToolRuntime(db=db, embedding_service=EmbeddingService(db))
    return runtime, runtime.build_tools()
