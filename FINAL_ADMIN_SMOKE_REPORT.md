# Final Admin Smoke Report

Date: July 23, 2026

## Scope

- Target app: `safespeak-admin`
- Admin origin used for smoke: `http://localhost:5174`
- Backend target: FastAPI only at `http://127.0.0.1:8000/api/v1`

## Runtime Preconditions

- MongoDB service: `RUNNING`
- FastAPI startup: `PASS`
- Admin app reachable on `localhost:5174`

## Validation Result

- Status: `FAIL`

## Passed Checks

- Admin login page loaded
- Admin password reset flow worked against FastAPI
- Admin login worked against FastAPI
- Admin dashboard metrics endpoint worked
- Admin users list endpoint worked
- Admin user update endpoint worked
- Admin content page endpoint worked
- Admin media-assets endpoint worked
- Admin knowledge-source listing endpoint worked
- Admin analytics overview endpoint worked
- Admin support-services admin endpoint worked
- Scope blueprint endpoint worked
- Admin dashboard route loaded with a real FastAPI-issued session in browser storage

## Failed Checks

- Advocate admin endpoint failed
  - Request: `GET /api/v1/admin/advocates`
  - Response: `404 Not Found`

## Notes

- The admin app itself is correctly targeting FastAPI only and can authenticate against it.
- This pass verified both browser-level dashboard access and direct FastAPI-backed admin data routes.
- The `advocates` admin route remains missing from FastAPI on this runtime, which is a real parity gap and a cutover blocker for the requested admin surface.
- The users listing response still exposes internal fields such as `passwordHash` and `refreshTokenHash` in the admin payload. That did not block route execution, but it is a security concern worth addressing separately.

## Conclusion

Admin runtime smoke is no longer blocked by MongoDB or backend startup.

Admin cutover still cannot be approved because `GET /api/v1/admin/advocates` is missing at runtime, leaving the advocate-management surface incomplete.
