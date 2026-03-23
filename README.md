# Gamuda Take Home

This project is a document ingestion and chat app. It lets you upload project files such as `PDF`, `CSV`, and `XLSX`, process them through a FastAPI backend, store data in PostgreSQL with `pgvector`, and access the app from a React frontend.

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy
- Database: PostgreSQL + `pgvector`
- Document processing: Docling, Pandas, PyArrow
- Frontend: React + Vite
- Local container setup: Docker Compose

## Environment Variables and API Keys

Copy the example env files before starting:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

API keys from the root `.env.example`:

- `GROQ_API_KEY`: required for the default AI setup because the app providers are configured to use `groq`
- `JINA_API_KEY`: required if you want embedding generation for PDF chunks and vector-based retrieval
- `GEMINI_API_KEY`: only needed if you switch any provider to `gemini`
- `GOOGLE_API_KEY`: optional, only needed for Google-based integrations if you enable them
- `LANGSMITH_API_KEY`: optional, only needed when `LANGSMITH_TRACING=true`

Frontend env:

- `frontend/.env` only needs `VITE_API_BASE_URL`, which should point to the backend, for example `http://localhost:8000`

## Start with Docker

To run the backend API and PostgreSQL in Docker:

```bash
docker compose up --build
```

This starts:

- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

If you only want the database container:

```bash
docker compose up -d db
```

## Start the Frontend

Run the frontend separately:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at:

- `http://localhost:5173`
