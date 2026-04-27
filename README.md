# SourceLogic

> **AI-powered codebase explorer** — ask questions about any local repository and get cited, context-aware answers streamed in real time.

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C)
![Tests](https://img.shields.io/badge/tests-127%20passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-76.60%25-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

SourceLogic indexes a local codebase into a vector store, then lets you ask natural-language questions about it. Each answer streams token-by-token via **Server-Sent Events** and includes **source citations** — file path, file name, and line number — so you always know where the information came from.

### Key features

| Feature | Detail |
|---|---|
| Multi-tenant isolation | Every request is scoped to a tenant ID; workspaces, sessions, and vector chunks are strictly separated |
| Incremental indexing | An MD5-hash manifest ensures only changed files are re-embedded on subsequent ingests |
| Source citations | Every AI answer links back to the exact chunk and line in the source code |
| Real-time streaming | Tokens arrive progressively via SSE — no waiting for the full response |
| Semantic search | ChromaDB + `all-MiniLM-L6-v2` (local, zero-cost) with per-workspace metadata filtering |
| Chat memory | Conversation history is persisted to SQLite and injected into every LLM prompt |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     React / Vite UI                     │
│       WorkspacePanel │ SessionPanel │ ChatView (SSE)    │
└────────────────────────┬────────────────────────────────┘
                         │  HTTP / SSE
┌────────────────────────▼────────────────────────────────┐
│                FastAPI  (async, /api/v1)                 │
│                                                         │
│   /workspaces      /sessions      /chat/{id}/stream     │
│                                                         │
│  ┌──────────────┐  ┌─────────────────┐  ┌───────────┐  │
│  │IngestionSvc  │  │   ChatService   │  │  DBSvc    │  │
│  │ CodeParser   │  │   LangChain     │  │  SQLAlch. │  │
│  │ SrcSplitter  │  │   ChatOpenAI    │  │  2.0 async│  │
│  └──────┬───────┘  └────────┬────────┘  └─────┬─────┘  │
└─────────┼───────────────────┼─────────────────┼─────────┘
          │                   │                 │
   ┌──────▼──────┐   ┌────────▼──────┐  ┌──────▼──────┐
   │  ChromaDB   │   │    OpenAI     │  │   SQLite    │
   │  (vectors)  │   │    gpt-4o     │  │ (aiosqlite) │
   └─────────────┘   └───────────────┘  └─────────────┘
```

**Chat request flow**

1. `POST /chat/{session_id}/stream` — validates tenant and session ownership
2. User message is persisted to SQLite
3. `ChatService` retrieves the top-5 semantically similar chunks from ChromaDB
4. Citations are emitted as the first SSE event (`event: citations`)
5. The LLM response streams token-by-token (`event: token`)
6. On completion, the full assistant message is persisted via an independent DB session

---

## Tech stack

| Layer | Technology |
|---|---|
| **Backend runtime** | Python ≥ 3.12 (tested on 3.13), FastAPI, uvicorn |
| **AI / LLM** | LangChain 0.3, `langchain-openai`, `langchain-community` |
| **Embeddings** | `all-MiniLM-L6-v2` via `langchain-huggingface` — local CPU, no extra cost |
| **Vector store** | ChromaDB (file-backed, no external service required) |
| **Database** | SQLAlchemy 2.0 async + aiosqlite (SQLite default; Postgres-ready) |
| **Frontend** | React 18, Vite 5, TypeScript 5, Tailwind CSS, Framer Motion |
| **Code quality** | Ruff (lint + format), mypy strict, pytest + pytest-asyncio, pytest-cov ≥70% |
| **Package manager** | uv (backend), npm (frontend) |

---

## Getting started

### Prerequisites

- Python ≥ 3.12 (3.13 recommended)
- Node.js ≥ 18
- [`uv`](https://docs.astral.sh/uv/) — `pip install uv`
- An OpenAI API key

### 1 — Clone & configure

```bash
git clone https://github.com/<your-handle>/sourcelogic.git
cd sourcelogic/backend
cp .env.example .env
# Set OPENAI_API_KEY in .env
```

### 2 — Backend

```bash
cd backend
uv sync                    # creates .venv and installs all dependencies
uv run alembic upgrade head            # initialize/migrate the database
uv run uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000` · Interactive docs: `http://localhost:8000/docs`

### 3 — Frontend

```bash
cd frontend
npm install
npm run dev                # http://localhost:5173
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI key used for gpt-4o / gpt-4-turbo / gpt-3.5-turbo |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/codechat.db` | SQLAlchemy async URL — swap to `postgresql+asyncpg://...` for Postgres |
| `CHROMA_PATH` | `./data/chroma_db` | Directory where ChromaDB persists the vector index |

Copy `backend/.env.example` to `backend/.env` and fill in the values.

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/workspaces` | List workspaces for the current tenant |
| `POST` | `/workspaces` | Create workspace (`name`, `root_path`) |
| `GET` | `/workspaces/{id}/status` | Indexing status (`IDLE` / `INDEXING` / `FAILED`) |
| `POST` | `/workspaces/{id}/ingest` | Trigger background ingestion — returns `task_id` |
| `GET` | `/workspaces/ingest/{task_id}` | Poll ingestion task status |
| `DELETE` | `/workspaces/{id}` | Delete workspace and all associated vectors |
| `POST` | `/workspaces/{id}/sessions` | Create a chat session |
| `GET` | `/workspaces/{id}/sessions` | List all sessions for a workspace |
| `DELETE` | `/sessions/{id}` | Delete a chat session |
| `GET` | `/sessions/{id}/history` | Full message history for a session (supports `limit` & `offset` params) |
| `POST` | `/chat/{session_id}/stream` | Stream AI answer via SSE |
| `POST` | `/admin/tenants/{tenant_id}/keys` | Create API key for tenant (requires `X-Admin-Secret`) |
| `GET` | `/admin/tenants/{tenant_id}/keys` | List active keys for tenant (requires `X-Admin-Secret`) |
| `DELETE` | `/admin/tenants/{tenant_id}/keys/{key_id}` | Revoke API key (requires `X-Admin-Secret`) |

Full OpenAPI spec at `/docs` when the server is running.

### Authentication

Three authentication modes are supported, controlled by the `AUTH_MODE` environment variable:

| Mode | Header | Status | Use case |
|---|---|---|---|
| `dev` (default) | `X-Tenant-ID: <tenant>` | ✅ Production-ready | Local single-user development |
| `api_key` | `X-API-Key: <raw-key>` | ✅ Production-ready | Multi-tenant production deployments |
| `jwt` | `Authorization: Bearer <token>` | ⏳ Stub ready (Week 4) | OAuth2 / OIDC provider integration |

#### Development mode (AUTH_MODE=dev)

Trusts the `X-Tenant-ID` header directly (defaults to `tenant-a`). Zero configuration required.

```bash
curl http://localhost:8000/workspaces \
  -H "X-Tenant-ID: my-org"
```

#### API key mode (AUTH_MODE=api_key) — ✅ Production-ready

Validates `X-API-Key` header against SHA-256 hashed keys in the database. Keys are provisioned via admin endpoints:

```bash
# Generate a key for a tenant (requires ADMIN_SECRET env var to be set)
curl -X POST http://localhost:8000/admin/tenants/my-tenant/keys?label=ci \
  -H "X-Admin-Secret: $ADMIN_SECRET"
# → returns { "key": "raw-key-shown-once", "tenant_id": "my-tenant", ... }

# List active keys for a tenant
curl http://localhost:8000/admin/tenants/my-tenant/keys \
  -H "X-Admin-Secret: $ADMIN_SECRET"

# Revoke a key
curl -X DELETE http://localhost:8000/admin/tenants/my-tenant/keys/{key_id} \
  -H "X-Admin-Secret: $ADMIN_SECRET"
```

**Key features:**
- SHA-256 hashing with timing-safe comparison (prevents timing attacks)
- Per-key rate limiting (default 20 req/min, configurable via `CHAT_RATE_LIMIT`)
- Revocation support (`is_active` flag in database)
- Admin endpoints for key lifecycle management

#### JWT mode (AUTH_MODE=jwt) — Week 4 preparation

JWT support is implemented as a middleware stub in `app/api/dependencies.py:37-58`. To enable JWT authentication in Week 4:

1. Choose an identity provider (Auth0, Okta, Cognito, etc.)
2. Set `JWT_SECRET` env var to your provider's public key (or shared secret)
3. Uncomment the JWT variant in `app/api/dependencies.py`
4. Install `python-jose`: `uv add python-jose`
5. Clients send: `Authorization: Bearer <jwt-token>`

The JWT payload must include a `tenant_id` field for tenant isolation.

```bash
# Example: after configuring JWT provider
curl http://localhost:8000/workspaces \
  -H "Authorization: Bearer eyJhbGc..."
```

See `backend/tests/test_auth.py:270-287` for documented JWT behavior specifications.

---

## Running tests

```bash
cd backend
OPENAI_API_KEY=ci-test-key \
DATABASE_URL="sqlite+aiosqlite:///./data/ci.db" \
uv run pytest -q --cov --cov-report=term-missing
```

The backend suite uses an in-memory SQLite database with `StaticPool` — **no external services required**. 127 tests covering:
- All CRUD endpoints (workspaces, sessions, messages)
- Authentication flows (dev mode, api_key mode, admin endpoints)
- Rate limiting per API key
- Pydantic input validation (max length, required fields)
- Database cascade deletes and constraints
- SSE streaming behavior and error handling
- ChatService and IngestionService with mock dependencies
- Coverage: 76.60% (threshold: 70%)

```bash
# Frontend tests (Vitest + React Testing Library)
cd frontend
npm run test:run    # 10 tests — hooks and components, no external services
npx tsc --noEmit    # type check
```

10 frontend tests cover custom hooks (`useToast`, `useStreaming`) and key components (`WorkspaceModal`, `ChatArea`, `ChatFooter`).

---

## Project structure

```
sourcelogic/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies.py  # Auth: dev/api_key/jwt modes + admin check
│   │   │   └── v1/              # FastAPI routers (workspaces, sessions, admin)
│   │   ├── core/
│   │   │   ├── config.py        # Settings: OPENAI_API_KEY, AUTH_MODE, JWT_SECRET
│   │   │   ├── database.py      # SQLAlchemy async engine, init_db()
│   │   │   ├── embeddings.py    # HuggingFaceEmbeddings singleton (lru_cache)
│   │   │   ├── limiter.py       # Slowapi rate limiter (per-key bucketing)
│   │   │   ├── logging_config.py # JSON logging for Datadog/Loki
│   │   │   ├── middleware.py    # RequestID middleware
│   │   │   └── vectorstore.py   # ChromaDB singleton
│   │   ├── models/              # SQLAlchemy ORM (Workspace, Session, Message, TenantAPIKey)
│   │   ├── schemas/             # Pydantic request/response models
│   │   └── services/            # Business logic (code_parser, chat_service, db_service, ingest_service)
│   ├── tests/                   # pytest suite (127 tests, 76.60% coverage, ≥70% required)
│   │   ├── conftest.py          # AsyncClient + in-memory SQLite fixtures
│   │   ├── test_auth.py         # Auth modes, admin endpoints, JWT stub docs
│   │   ├── test_*.py            # Endpoint, service, and schema tests
│   │   └── test_*_unit.py       # Unit tests with mock dependencies
│   ├── alembic/                 # DB migrations (async SQLAlchemy)
│   └── pyproject.toml           # uv / ruff / mypy strict / pytest config
├── frontend/
│   └── src/
│       ├── components/          # Sidebar, ChatArea, ChatFooter, ChatHeader,
│       │                        #   WorkspaceModal, ChatMessage, ErrorBoundary
│       ├── hooks/               # useStreaming, useChat, useWorkspaces,
│       │                        #   useSessions, useToast, useTenant
│       ├── services/            # WorkspaceService, SessionService, apiClient
│       └── types/               # chat.ts — ChatModel, ChatMessageModel
├── .github/workflows/ci.yml     # CI: ruff · mypy · bandit · pytest (coverage ≥70%)
└── docker-compose.yml           # Local dev: backend + frontend
```

---

## Design decisions

**Why local embeddings instead of OpenAI embeddings?**
`all-MiniLM-L6-v2` runs on CPU at zero marginal cost and is fast enough for typical codebases (up to ~50k files). Switching to `text-embedding-3-small` requires changing one line in `app/core/embeddings.py`.

**Why SQLite instead of PostgreSQL?**
Zero-dependency local setup. The SQLAlchemy async layer is identical for both; switching to Postgres requires only changing `DATABASE_URL`.

**Why SSE instead of WebSockets?**
SSE is stateless, proxy-friendly, and sufficient for unidirectional token streaming. No extra infrastructure.

**Why a file-hash manifest instead of re-ingesting every time?**
Re-embedding large repos takes minutes. The manifest records each file's MD5 hash; only modified or new files are re-processed on subsequent ingests.

**Why an embeddings singleton?**
`HuggingFaceEmbeddings` loads a ~90 MB model on first call. Without a singleton, every request that instantiated `ChatService` or `IngestionService` would pay that cold-start cost. The singleton (`app/core/embeddings.py`) loads the model once per process.

---

## Production deployment

### Pre-deployment checklist

| Item | Status | Notes |
|---|---|---|
| Authentication | ✅ Ready | `AUTH_MODE=api_key` with `ADMIN_SECRET` set |
| Rate limiting | ✅ Ready | Per-key rate limiting via Slowapi |
| Database migrations | ✅ Ready | Alembic setup for schema versioning |
| Structured logging | ✅ Ready | JSON logging compatible with Datadog/Loki |
| Security headers | ✅ Ready | Nginx config includes CSP, X-Frame-Options, etc. |
| TLS/HTTPS | ⏳ Required | Must be configured at load balancer / Nginx level |
| CORS origins | ✅ Ready | Set `CORS_ORIGINS` env var (defaults to localhost) |
| Path traversal guard | ✅ Ready | Set `WORKSPACE_ALLOWED_BASE` to restrict workspace indexing |
| OpenAI API key | ✅ Ready | Provision via env var (never commit to git) |
| ChromaDB persistence | ✅ Ready | File-backed vector store (production-safe) |
| SQLite → PostgreSQL | ✅ Optional | Swap `DATABASE_URL` — no code changes required |

### Environment variables for production

```bash
# Required
export OPENAI_API_KEY="sk-..."
export AUTH_MODE="api_key"
export ADMIN_SECRET="$(openssl rand -hex 32)"

# Optional but recommended
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/sourcelogic"
export WORKSPACE_ALLOWED_BASE="/home/user/projects"
export CORS_ORIGINS='["https://yourdomain.com","https://app.yourdomain.com"]'
export LOG_LEVEL="INFO"
export CHAT_RATE_LIMIT="50/minute"
export JWT_SECRET=""  # Leave empty unless using JWT auth in Week 4
```

### Docker deployment

```bash
cd sourcelogic
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Week 4 roadmap (Final Polish)

| Task | Status | Notes |
|---|---|---|
| JWT OAuth2 integration | ⏳ Ready to start | Stub code in `dependencies.py:37-58`; awaiting provider selection |
| Frontend API key UI | ⏳ Ready to start | Modal for tenants to manage their API keys |
| E2E auth tests | ⏳ Ready to start | Playwright tests for complete auth flow |
| Performance optimization | ⏳ Ready to start | Connection pooling, socket reuse optimizations |
| Security audit | ⏳ Ready to start | Review rate limiting, CORS, path traversal guards |

---

## Known limitations

- **Path traversal**: by default any absolute path is accepted (safe for local single-user use). Set `WORKSPACE_ALLOWED_BASE` in `.env` to restrict paths in multi-user or production deployments.
- **Large codebase indexing**: embeddings for >100k files may exceed memory. Consider breaking into multiple workspaces or using a cloud embedding provider.

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built by [Federico Orsi](https://www.linkedin.com/in/federico-orsi/) as a portfolio project demonstrating production-quality RAG architecture with FastAPI, LangChain, and React.*
