# Final Frontend Smoke Report

Date: July 23, 2026

## Scope

- Target app: `safespeak-frontend`
- Frontend origin used for smoke: `http://localhost:3000`
- Backend target: FastAPI only at `http://127.0.0.1:8000/api/v1`

## Runtime Preconditions

- MongoDB service: `RUNNING`
- MongoDB port `127.0.0.1:27017`: reachable
- FastAPI startup: `PASS`
- Health endpoints:
  - `GET /health`: `200`
  - `GET /api/v1/health`: `200`

## Validation Result

- Status: `FAIL`

## Passed Checks

- Frontend shell loaded at `http://localhost:3000`
- Signup worked against FastAPI
- Login worked against FastAPI
- Refresh token flow worked against FastAPI
- Logout worked against FastAPI
- Dashboard route loaded with a real FastAPI-issued session in browser storage
- Notifications API worked
- Content page retrieval worked
- Scope bootstrap retrieval worked
- Anonymous session creation worked
- Conversation session creation worked

## Failed Checks

- Support services flow failed without a valid anonymous-session header in the smoke request
  - API response: `401 User or anonymous session is required`
- Report creation failed even after a consent update was attempted for an authenticated user
  - API response: `403 cloud_sync consent is required before report data can be stored on SafeSpeak servers`
- RAG answer failed even after a consent update was attempted for an authenticated user
  - API response: `403 process_with_ai consent is required for AI processing`
- Conversation message send failed on the first pass due request-shape mismatch
  - API response: `400 Validation failed`
  - Required field: `content`
- Evidence upload flow was not completed because report creation did not succeed, so no valid `reportId` was available

## Notes

- The frontend application itself is correctly targeting FastAPI only and renders successfully.
- The remaining failures are now feature-level runtime issues, not MongoDB or general startup failures.
- The authenticated consent update is being accepted by `/consents/update`, but downstream report and RAG flows still reject the user as if the required consent is absent. That is a real cutover blocker.
- The anonymous-session follow-up request used the wrong field from the anonymous-session creation response during one pass. That specific request error is a smoke-script issue, not a confirmed product defect.

## Conclusion

Frontend runtime smoke is no longer blocked by MongoDB or FastAPI startup.

However, FastAPI-only frontend cutover cannot be approved yet because key user flows still fail:

- report creation
- RAG answer
- full evidence-upload path

These are production-relevant feature blockers.
