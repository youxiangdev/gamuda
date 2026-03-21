from collections.abc import Sequence

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.chunk_service import ChunkService


class EmbeddingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.chunk_service = ChunkService(db)

    @property
    def enabled(self) -> bool:
        api_key = self.settings.jina_api_key
        if api_key is None:
            return False
        return bool(api_key.get_secret_value().strip())

    def embed_document_chunks(self, document_id: str) -> dict[str, object]:
        if not self.enabled:
            return {
                "enabled": False,
                "embedded_chunks": 0,
                "model": self.settings.jina_embedding_model,
                "task": "retrieval.passage",
                "reason": "JINA_API_KEY is not configured.",
            }

        chunks = self.chunk_service.list_chunks_for_embedding(document_id)
        if not chunks:
            return {
                "enabled": True,
                "embedded_chunks": 0,
                "model": self.settings.jina_embedding_model,
                "task": "retrieval.passage",
                "reason": "No chunks available for embedding.",
            }

        inputs = [chunk.contextualized_text for chunk in chunks]
        embeddings = self._embed_texts(inputs, task="retrieval.passage")
        self.chunk_service.update_chunk_embeddings(
            chunks,
            embeddings,
            embedding_model=self.settings.jina_embedding_model,
            embedding_task="retrieval.passage",
        )
        return {
            "enabled": True,
            "embedded_chunks": len(chunks),
            "model": self.settings.jina_embedding_model,
            "task": "retrieval.passage",
        }

    def _embed_texts(self, texts: Sequence[str], *, task: str) -> list[list[float]]:
        api_key = self.settings.jina_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise RuntimeError("JINA_API_KEY is not configured.")

        embeddings: list[list[float]] = []
        batch_size = self.settings.jina_embedding_batch_size

        with httpx.Client(timeout=self.settings.jina_embedding_timeout_seconds) as client:
            for start in range(0, len(texts), batch_size):
                batch = list(texts[start : start + batch_size])
                response = client.post(
                    self.settings.jina_embedding_base_url,
                    headers={
                        "Authorization": f"Bearer {api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.jina_embedding_model,
                        "task": task,
                        "normalized": True,
                        "input": batch,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                data = sorted(payload.get("data", []), key=lambda item: item["index"])
                if len(data) != len(batch):
                    raise RuntimeError("Embedding API returned an unexpected number of vectors.")

                for item in data:
                    embedding = item.get("embedding")
                    if not isinstance(embedding, list):
                        raise RuntimeError("Embedding API returned a malformed embedding payload.")
                    if len(embedding) != self.settings.jina_embedding_dimensions:
                        raise RuntimeError(
                            "Embedding vector dimension mismatch. "
                            f"Expected {self.settings.jina_embedding_dimensions}, got {len(embedding)}."
                        )
                    embeddings.append([float(value) for value in embedding])

        return embeddings
