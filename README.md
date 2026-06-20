# SafeSpeak AI Agent

Separate FastAPI service for SafeSpeak legal RAG, PDF extraction, knowledge-source
administration, and LangGraph AI workflows.

## Architecture

- FastAPI and Pydantic v2 provide validated, OpenAPI-documented endpoints.
- PyMuPDF extracts page text, spans, bounding boxes, font signals, and tables.
- Optional Tesseract OCR handles image-only pages and records confidence warnings.
- MongoDB remains the source of truth and reuses the backend collections:
  `ragknowledgesources`, `ragchunks`, `users`, and `anonymoussessions`.
- Full structured extraction JSON, Markdown, and raw text are stored in
  `ragextracteddocuments`.
- Pinecone stores semantic vectors. MongoDB supplies keyword and exact-section search.
- Reciprocal Rank Fusion combines exact, keyword, and semantic retrieval.
- Deterministic and OpenAI relevance reranking prioritize exact legal provisions.
- Repealed provisions are excluded unless the user explicitly asks a historical question.
- Provision status, commencement/version dates, definitions, tables, and cross-references
  are persisted with each chunk.
- A sentence-level citation gate rejects unsupported sections, numbers, claims, or
  incomplete Act/section/page/version/source provenance.
- LangGraph orchestrates grounded legal answers and timeline assistant turns.
- The Node backend remains responsible for login, anonymous sessions, consent, and
  all non-AI product modules.

## Local setup

Python 3.12 or 3.13 is recommended.

```powershell
cd safespeak-ai-agent
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

The repository `.env` is copied from `safespeak-backend/.env`, so it uses the same
MongoDB, JWT, OpenAI, and Pinecone credentials. Review these agent-specific values:

```dotenv
PORT=8000
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
KNOWLEDGE_STORAGE_PATH=./storage/knowledge-sources
LEGAL_REQUIRE_PRODUCTION_GOLDEN=true
```

Install the pinned official English Tesseract language data for PyMuPDF integrated OCR:

```powershell
python scripts/install_tessdata.py
```

Run the service:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/docs` for Swagger UI and
`http://localhost:8000/api/v1/health` for health information.

## Run the full project

Use three terminals:

```powershell
cd safespeak-backend
npm run dev
```

```powershell
cd safespeak-ai-agent
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8000 --reload
```

```powershell
cd safespeak-frontend
npm run dev
```

Run the admin dashboard separately when needed:

```powershell
cd safespeak-admin
npm run dev
```

The frontend and admin retain their normal backend URL and use a dedicated AI URL:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:5000/api/v1
NEXT_PUBLIC_AI_AGENT_API_BASE_URL=http://localhost:8000/api/v1
VITE_API_BASE_URL=http://localhost:5000/api/v1
VITE_AI_AGENT_API_BASE_URL=http://localhost:8000/api/v1
```

Restart Next.js and Vite after changing environment files.

## Main endpoints

- `POST /api/v1/extract`
- `POST /api/v1/rag/search`
- `POST /api/v1/rag/answer`
- `POST /api/v1/rag/timeline-assistant`
- `GET|POST|PATCH|DELETE /api/v1/rag/knowledge-sources`
- `POST /api/v1/rag/knowledge-sources/{id}/document`
- `POST /api/v1/rag/knowledge-sources/{id}/ingest`
- `POST /api/v1/rag/knowledge-sources/{id}/reindex`
- `GET /api/v1/rag/knowledge-sources/{id}/artifacts`
- `POST /api/v1/ai/triage-report`
- `POST /api/v1/ai/extract-incident-fields`
- `POST /api/v1/ai/clarifying-questions`
- `POST /api/v1/ai/generate-summary`
- `POST /api/v1/ai/translate`
- `POST /api/v1/ai/redact-pii`

Admin endpoints accept the existing SafeSpeak bearer token. Public AI/RAG endpoints
accept either that bearer token or the existing `X-SafeSpeak-Session` token.

## OCR

OCR is optional because Tesseract is an operating-system dependency:

```powershell
pip install -e ".[ocr]"
```

Run `python scripts/install_tessdata.py` and set `RAG_ENABLE_OCR=true`. PyMuPDF then
uses its integrated Tesseract engine without requiring a system-wide executable.
Low-quality pages remain marked for mandatory human review. A system Tesseract
installation remains available as a secondary fallback through `TESSERACT_CMD`.

## Legal golden gate

The synthetic corpus checks the harness only:

```powershell
python scripts/generate_synthetic_golden.py
python -m app.evaluation.golden legal-golden/synthetic-manifest.json
```

Production requires at least eight pinned and legally reviewed Australian legislation
PDFs. Copy `legal-golden/production-manifest.example.json`, add the reviewed PDFs and
5 or more expected citation questions per document, then run:

```powershell
python -m app.evaluation.golden legal-golden/production-manifest.json `
  --require-production `
  --output legal-golden/reports/latest.json
```

When `ENVIRONMENT=production`, SafeSpeak fails closed if that report is missing or
failed, or if configured OCR is unavailable. Automated extraction cannot replace
legal review of the golden answers and consolidation dates.

## Verification

```powershell
ruff check app tests scripts
pytest
```

Before production deployment, create the configured Pinecone index with dimensions
matching `OPENAI_EMBEDDING_MODEL`, mount durable document and golden-report volumes,
place the API behind TLS, restrict CORS, rotate development credentials, and obtain
legal sign-off on every reviewed golden fixture.
