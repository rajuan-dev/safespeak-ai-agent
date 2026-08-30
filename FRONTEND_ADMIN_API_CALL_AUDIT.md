# Frontend/Admin API Call Audit

Date: 2026-07-23

## Scope

Static audit of:

- `safespeak-frontend`
- `safespeak-admin`

Reviewed environment files present in each app:

- `safespeak-frontend/.env`
- `safespeak-frontend/.env.example`
- `safespeak-admin/.env`
- `safespeak-admin/.env.example`

No additional `.env.local`, `.env.development`, or `.env.production` files were present in either app at audit time.

## Environment Cutover Result

Frontend backend API target: `FastAPI only`

Admin backend API target: `FastAPI only`

Updated active API base values:

- Frontend: `http://127.0.0.1:8000/api/v1`
- Admin: `http://127.0.0.1:8000/api/v1`

Source-level hardcoded fallbacks also updated to FastAPI:

- `safespeak-frontend/next.config.mjs`
- `safespeak-frontend/src/lib/api.ts`
- `safespeak-admin/src/lib/api.ts`

## Frontend API Calls Audited

Confirmed frontend library usage is FastAPI-compatible and environment-based for the active backend target.

| Area | Frontend call(s) | FastAPI status |
| --- | --- | --- |
| Auth | `/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/verify-reset-otp`, `/auth/reset-password`, `/auth/refresh`, `/auth/me`, `/auth/logout`, `/api/auth/google` | Present |
| AI | `/ai/extract-incident-fields`, `/ai/triage-report`, `/ai/clarifying-questions`, `/ai/generate-summary`, `/ai/translate`, `/ai/redact-pii`, `/ai/transcribe-audio`, `/ai/synthesize-speech` | Present |
| RAG | `/rag/search`, `/rag/answer`, `/rag/timeline-assistant` | Present |
| Notifications | `/notifications`, `/notifications/read`, `/notifications/read-all` | Present |
| Content pages | `/content-pages/{key}` | Present |
| Media assets | `/media-assets`, `/media-assets/{id}` | Present |
| Scope | `/scope/bootstrap`, `/scope/cultural-profiles` | Present |

## Admin API Calls Audited

Confirmed admin library usage is FastAPI-compatible and environment-based for the active backend target.

| Area | Admin call(s) | FastAPI status |
| --- | --- | --- |
| Admin auth | `/auth/admin/login`, `/auth/refresh`, `/auth/me`, `/auth/change-password`, `/auth/forgot-password`, `/auth/verify-reset-otp`, `/auth/reset-password` | Present |
| Dashboard/users | `/admin/dashboard`, `/admin/users`, `/admin/users/{id}` | Present |
| Notifications | `/admin/notifications`, `/admin/notifications/read`, `/admin/notifications/read-all` | Present |
| Content pages | `/admin/content-pages/{key}`, `/admin/content-pages/{key}/publish` | Present |
| Content resources | `/admin/content-resources`, `/admin/content-resources/{id}` | Present |
| Media assets | `/admin/media-assets`, `/admin/media-assets/{id}` | Present |
| Microeducation | `/admin/microeducation`, `/admin/microeducation/generate`, `/admin/microeducation/categories`, `/admin/microeducation/categories/{id}`, `/admin/microeducation/{id}` | Present |
| Knowledge sources | `/rag/knowledge-sources`, `/rag/knowledge-sources/readiness`, `/rag/admin/pinecone/health`, `/rag/knowledge-sources/{id}`, `/rag/knowledge-sources/{id}/chunks`, `/rag/knowledge-sources/{id}/artifacts`, `/rag/knowledge-sources/{id}/status`, `/rag/knowledge-sources/{id}/approve`, `/rag/knowledge-sources/{id}/reject`, `/rag/knowledge-sources/{id}/ingest`, `/rag/knowledge-sources/{id}/document`, `/rag/knowledge-sources/{id}/refresh`, `/rag/knowledge-sources/{id}/reindex` | Present |
| Platform settings | `/admin/platform-settings`, `/admin/platform-settings/draft`, `/admin/platform-settings/publish` | Present |
| Taxonomies/deliveries/privacy/support | `/admin/taxonomies*`, `/admin/report-deliveries`, `/admin/privacy-requests*`, `/admin/support-services*`, `/admin/support-services/warm-referrals*` | Present |
| Analytics | `/admin/analytics/overview`, `/admin/analytics/heatmap`, `/admin/analytics/trends`, `/admin/analytics/categories`, `/admin/analytics/languages`, `/admin/analytics/export` | Present |
| Audit logs | `/admin/audit-logs` | Present |

## Node URL Reference Search

Search performed across both app trees for:

- `safespeak-backend`
- `localhost:5000`
- `localhost:4000`
- `localhost:8001`
- `NODE_BACKEND`
- `BACKEND_URL`

Result:

- `safespeak-admin`: no active source matches
- `safespeak-frontend`: one remaining source match in `REPORT_INCIDENT_PROGRESS.md`

Remaining match classification:

- `safespeak-frontend/REPORT_INCIDENT_PROGRESS.md`
  - archived documentation note only
  - not runtime code
  - not env configuration

Observed generated artifact matches from earlier validation:

- `safespeak-frontend/.next-dev*/routes-manifest.json`

These are build artifacts, not active source-of-truth configuration, and should not be treated as a live Node backend dependency.

## Result

- Frontend backend API target: `FastAPI only`
- Admin backend API target: `FastAPI only`
- Node backend URL references in active env/source: `none`
- Remaining Node wording exists only in archived notes or generated build artifacts
