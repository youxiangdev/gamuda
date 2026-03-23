FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

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

# Resolve a fresh CPU-only dependency set for the active Linux platform so
# amd64 builds do not pull the CUDA package set from the existing lockfile.
RUN uv pip compile pyproject.toml --python-version 3.12 --torch-backend cpu \
        --no-header --no-annotate --no-strip-markers --emit-index-url \
        -o requirements.lock.txt \
    && uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python --no-cache --torch-backend cpu -r requirements.lock.txt \
    && uv pip install --python /app/.venv/bin/python --no-cache --no-deps . \
    && rm -rf /root/.cache /app/.cache requirements.lock.txt

EXPOSE 8000

CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
