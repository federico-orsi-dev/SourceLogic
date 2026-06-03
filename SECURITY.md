# Security Policy

## Implemented Controls

The following security controls are implemented in the current codebase:

| Control | Implementation | Location |
|---|---|---|
| **Secret management** | All secrets loaded from environment variables, never committed | `backend/.env` (gitignored), `core/config.py` |
| **Authentication** | Three modes: `dev`, `api_key` (SHA-256 + timing-safe compare), `jwt` (HS256 Bearer) | `app/api/dependencies.py` |
| **API key hashing** | Raw keys are never stored — only SHA-256 hashes in the database | `app/api/v1/admin.py` |
| **Timing-safe comparison** | `hmac.compare_digest` used for API key and admin secret validation | `app/api/dependencies.py`, `app/api/v1/admin.py` |
| **Rate limiting** | Per-API-key request bucketing via Slowapi (default 20 req/min, configurable) | `app/core/limiter.py` |
| **Path traversal guard** | `WORKSPACE_ALLOWED_BASE` restricts which directories can be indexed | `app/core/config.py`, `app/api/v1/workspaces.py` |
| **No raw SQL** | All database access via SQLAlchemy ORM — no string interpolation | `app/services/db_service.py`, all endpoints |
| **CORS policy** | Explicit origin allowlist via `CORS_ORIGINS` env var | `app/main.py` |
| **Request ID tracing** | `X-Request-ID` propagated through the request lifecycle for audit trails | `app/core/middleware.py` |
| **Structured logging** | JSON logs with no secret interpolation, compatible with SIEM tools | `app/core/logging_config.py` |
| **Non-root container** | Docker image runs as unprivileged `app` user | `backend/Dockerfile` |
| **Static analysis** | Bandit (`-r app -l`) runs on every CI push | `.github/workflows/ci.yml` |

## Known Limitations

- **SQLite concurrency**: the default SQLite backend is not safe for high-concurrency write workloads. Use `DATABASE_URL=postgresql+asyncpg://...` for production multi-user deployments.
- **JWT algorithm**: HS256 uses a shared secret. For production with an external identity provider (Auth0, Okta), switch to RS256 with the provider's public key.
- **ChromaDB**: the local file-backed vector store has no access control beyond process isolation. In a multi-server deployment, migrate to a managed vector store with auth.
- **`WORKSPACE_ALLOWED_BASE` is opt-in**: by default, any absolute path is accepted. Set this variable in any deployment where users should not be able to index arbitrary server paths.

## Vulnerability Reporting

Please open a GitHub Issue with the tag `[SECURITY]`:

- A clear title: `[SECURITY] <brief summary>`
- Affected file(s) and line numbers
- Reproduction steps and expected impact
- Suggested mitigation if available

For sensitive disclosures, contact the maintainer directly before opening a public issue.

## Dependency Scanning

Dependencies are pinned via `uv.lock`. To audit for known CVEs:

```bash
cd backend
pip-audit --requirement <(uv export --no-dev)
```

Frontend dependencies:

```bash
cd frontend
npm audit
```
