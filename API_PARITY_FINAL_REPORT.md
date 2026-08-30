# API Parity Final Report

Date: 2026-07-23

## Scope

Final static parity audit between:

- `safespeak-backend`
- `safespeak-ai-agent`

Focused on the routes actively consumed by:

- `safespeak-frontend`
- `safespeak-admin`

This report does not claim live runtime smoke success. MongoDB-backed runtime validation remains dependent on a healthy local MongoDB instance.

## Executive Summary

Static API parity for the currently consumed frontend/admin surface is in place.

FastAPI now serves as the only configured backend target for both client applications at the environment and source-config level.

Backend-side parity hardening completed in this pass:

- removed stale Node default from `app/config/settings.py`
- aligned backend base URL defaults to `http://127.0.0.1:8000/api/v1`
- added `DATABASE_NAME` compatibility support alongside `MONGODB_DATABASE`
- updated `safespeak-ai-agent/.env`
- updated `safespeak-ai-agent/.env.example`

## AI-Agent Environment Parity

### Updated

- `app/config/settings.py`
  - `BACKEND_API_BASE_URL` default changed from Node-era `localhost:5000` to FastAPI `127.0.0.1:8000`
  - `AI_AGENT_BASE_URL` default aligned to `127.0.0.1:8000`
  - `MONGODB_DATABASE` now accepts `DATABASE_NAME` as a compatibility alias

- `.env`
  - added `DATABASE_NAME=`
  - updated `BACKEND_API_BASE_URL=http://127.0.0.1:8000/api/v1`

- `.env.example`
  - added `DATABASE_NAME=`
  - updated `BACKEND_API_BASE_URL=http://127.0.0.1:8000/api/v1`

### Current database variable behavior

Effective precedence:

1. `MONGODB_DATABASE`
2. `DATABASE_NAME`
3. default database embedded in `MONGODB_URI`

This removes the previous configuration mismatch where runtime notes referenced `DATABASE_NAME` but the settings layer only accepted `MONGODB_DATABASE`.

## Frontend/Admin Consumed Route Parity

| Route area | Node status | FastAPI status | Mismatch |
| --- | --- | --- | --- |
| Auth and refresh flows | Present | Present | None in static audit |
| Session-compatible frontend auth usage | Present | Present | None in static audit |
| AI orchestration routes used by frontend | Present | Present | None in static audit |
| RAG answer/search/timeline assistant | Present | Present | None in static audit |
| Notifications | Present | Present | None in static audit |
| Public content pages | Present | Present | None in static audit |
| Public media assets | Present | Present | None in static audit |
| Scope bootstrap/cultural profiles | Present | Present | None in static audit |
| Admin dashboard/users | Present | Present | None in static audit |
| Admin notifications | Present | Present | None in static audit |
| Admin content pages | Present | Present | None in static audit |
| Admin content resources | Present | Present | None in static audit |
| Admin media assets | Present | Present | None in static audit |
| Admin microeducation | Present | Present | None in static audit |
| Admin knowledge-source management | Present | Present | None in static audit |
| Admin platform settings | Present | Present | None in static audit |
| Admin taxonomies/report deliveries/privacy/support | Present | Present | None in static audit |
| Admin analytics | Present | Present | None in static audit |
| Admin audit logs | Present | Present | None in static audit |

## Notes

- `safespeak-admin` source did not show active client calls to `/admin/advocates/*` during this audit pass.
- The Node backend still contains additional routes outside the currently consumed frontend/admin surface. This report is intentionally scoped to cutover-critical parity rather than every historical route signature.

## Runtime Constraint

Static parity is not the current blocker.

The current cutover blocker remains runtime infrastructure:

- local MongoDB service availability
- successful FastAPI startup with database/index initialization
- honest frontend/admin smoke validation against a healthy FastAPI runtime

## Final Static Assessment

- Frontend/admin API target configuration: `FastAPI only`
- Active frontend/admin consumed route parity: `satisfied in static audit`
- Remaining cutover blocker category: `runtime infrastructure, not source routing`
