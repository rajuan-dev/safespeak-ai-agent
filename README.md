# SafeSpeak FastAPI Backend

SafeSpeak now runs as a unified FastAPI backend. This service owns the application
API surface for sessions, authentication, users, profiles, consent, privacy,
reports, evidence, conversation flow, AI orchestration, RAG, ScamShield, support,
admin, analytics, content, resources, platform settings, and audit logging.

The legacy Node.js backend should be treated as an archive/reference codebase
only after cutover validation is complete.

## Architecture

- `app/main.py` boots the complete FastAPI application and registers all product
  and admin routers.
- MongoDB remains the primary source of truth for transactional and audit data.
- Evidence uses authenticated encryption with AES-256-GCM and storage adapters
  for local disk or S3.
- RAG supports governed ingestion, chunking, embeddings, approval workflow,
  retrieval, and citation-aware AI grounding.
- Admin and frontend clients use the same `/api/v1` FastAPI surface.

## Local Setup

```powershell
cd safespeak-ai-agent
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
copy .env.example .env
```

Run the API:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health endpoints:

- `GET /health`
- `GET /api/v1/health`

## Environment

Use [`./.env.example`](./.env.example) as the authoritative template.

Required integration groups:

- MongoDB
- JWT and auth recovery
- Google OAuth
- OpenAI
- Pinecone
- AWS / S3
- evidence encryption and audit signing keys
- content/media storage
- report delivery
- ScamShield

Rules:

- Never commit live secrets.
- Never use fake production encryption keys.
- Rotate all production secrets before deployment.
- In production, missing evidence encryption or audit signing keys must fail
  startup.

## Verification

Run the validation suite before cutover:

```powershell
ruff check .
pytest
```

Recommended smoke tests:

- frontend login, refresh, content loading, AI chat, report creation, evidence upload
- admin login, dashboard, content management, knowledge/RAG flows, analytics

## Deployment

1. Provision MongoDB, object storage, Pinecone, and required API credentials.
2. Populate `.env` from `.env.example` with environment-specific values.
3. Run `ruff check .` and `pytest`.
4. Start FastAPI with your process manager or container runtime.
5. Point frontend and admin clients at the FastAPI `/api/v1` base URL.
6. Disable Node traffic only after smoke tests and production checks pass.

## Migration Status

FastAPI is the complete SafeSpeak backend implementation. Remaining go-live work
is operational hardening, regression validation, and traffic cutover.
