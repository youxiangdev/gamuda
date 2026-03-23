FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface

ARG TORCH_VERSION=2.10.0
ARG TORCHVISION_VERSION=0.25.0

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

# Export the locked dependencies minus PyTorch, then install CPU-only torch
# explicitly so Linux builds do not pull the CUDA package set.
RUN uv export --format requirements.txt --frozen --no-header --no-annotate --no-hashes \
        --no-emit-project --prune torch --prune torchvision > requirements.lock.txt \
    && uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python --no-cache -r requirements.lock.txt \
    && uv pip install --python /app/.venv/bin/python --no-cache --torch-backend cpu \
        torch==${TORCH_VERSION} torchvision==${TORCHVISION_VERSION} \
    && uv pip install --python /app/.venv/bin/python --no-cache --no-deps . \
    && rm -rf /root/.cache /app/.cache requirements.lock.txt

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
