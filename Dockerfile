FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/app/.cache/huggingface

ARG JINA_EMBEDDING_MODEL=jina-embeddings-v5-text-small

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY app ./app
COPY README.md architecture.md decision.md ./

RUN uv sync --frozen

# Preload the default tokenizer used by Docling chunking so first PDF ingestion
# does not need to download Hugging Face assets at runtime.
RUN uv run python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('jinaai/${JINA_EMBEDDING_MODEL}')"

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
