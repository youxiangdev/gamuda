# Gamuda Take Home Backend

FastAPI backend skeleton for document upload and ingestion.

## Current Scope

- Upload `PDF`, `CSV`, and `XLSX` documents
- Persist uploaded files locally
- Create and track ingestion jobs
- Run basic background ingestion for:
  - `CSV` and `XLSX` into normalized analysis artifacts
  - `PDF` via Docling structured parsing

## Tech Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL + `pgvector`
- `uv` for dependency management and app execution
- Pandas + Parquet for tabular analysis artifacts

## Requirements

- `uv`
- Python `3.12+`
- Docker

## Quick Start

### 1. Start the backend dependencies

```bash
docker compose up -d db
```

This starts:

- `db`: PostgreSQL + `pgvector` on `localhost:5432`

Configuration is centralized in `.env`.
Docker Compose reads `.env` directly, and local backend/frontend development uses the same shared values where relevant.

Default local database:

- host: `localhost`
- port: `5432`
- database: `gamuda`
- user: `postgres`
- password: `postgres`

### 2. Run the FastAPI backend

```bash
uv sync --python 3.12
uv run uvicorn app.main:app --reload
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- API base URL: `http://127.0.0.1:8000`
- Local `uv run` may download the configured Hugging Face tokenizer on first PDF ingestion if it is not already cached.

### 3. Run the React frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server:

- `http://127.0.0.1:5173`

## Available Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/documents/upload` | Upload a file and trigger ingestion |
| `GET` | `/api/v1/documents/{document_id}` | Fetch uploaded document metadata |
| `GET` | `/api/v1/ingestions/{job_id}` | Fetch ingestion job status |

## Upload Assumptions

| Field | Rule |
| --- | --- |
| `document_type` | Required. Allowed values: `project_description`, `progress_update` |
| `reporting_period` | Required only for `progress_update` documents |
| `reporting_period` format | `YYYY-MM` |

### Interpretation

- `project_description`: baseline or reference documents without a required reporting period
- `progress_update`: time-bound reporting documents that must carry a reporting period

## Upload Example

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/documents/upload" \
  -F "file=@data/synthetic-data/financial_summary_mar_2026.csv" \
  -F "document_type=progress_update" \
  -F "reporting_period=2026-03" \
  -F "project_id=east-metro" \
  -F "package_id=v3"
```

## Project Structure

```text
app/
  api/
  core/
  db/
  models/
  schemas/
  services/
data/
decision.md
architecture.md
pyproject.toml
```

## Notes

- Uploaded files are stored under `storage/uploads/`
- The backend is API-only and allows local React development via CORS
- The React frontend lives in `frontend/` and calls FastAPI directly
- PDF chunking uses Docling `HybridChunker` with the Hugging Face tokenizer for the configured Jina embedding model
- PDF chunk embeddings are stored directly on `document_chunks.embedding` using Jina AI when `JINA_API_KEY` is configured
- The Docker image preloads the default Jina tokenizer during build so the first PDF ingestion does not need a runtime download
- PDF ingestion writes Docling artifacts to `storage/artifacts/<document_id>/`
- PDF artifacts include `document.md`, `document.json`, `document_context.json`, and `chunks.json`
- CSV/XLSX ingestion writes normalized parquet datasets and `tabular_profile.json` to `storage/artifacts/<document_id>/`
- CSV files that require malformed-row repair also write `csv_repair_report.json` with repair counts and affected row numbers
# gamuda
