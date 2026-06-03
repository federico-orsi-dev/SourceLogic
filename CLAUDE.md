# SourceLogic SaaS — Project Brain

## Context

Python SaaS application — sistema RAG (Retrieval-Augmented Generation) multi-tenant per esplorazione di codebase locali.
Indicizza file sorgenti in ChromaDB e serve risposte contestualizzate via chat streaming.
Isolamento tenant a livello storage (SQLAlchemy + filtri metadati ChromaDB).
Auth multi-modalità: dev (X-Tenant-ID), api_key (SHA-256 hashing), JWT Bearer token.

## Tech Stack

| Layer | Tecnologia | Versione |
|---|---|---|
| Language | Python | 3.12+ |
| Web Framework | **FastAPI** | >=0.100 |
| Validation | **Pydantic v2** | via FastAPI + pydantic-settings |
| ORM | **SQLAlchemy** async | >=2.0.0 |
| DB Driver | aiosqlite | — |
| LLM Orchestration | LangChain + LangChain-OpenAI | >=0.3.0 |
| LLM Provider | OpenAI (gpt-4o, gpt-4-turbo, gpt-3.5-turbo) | — |
| Vector Store | **ChromaDB** (locale, persistente) | >=1.5.5 |
| Embeddings | HuggingFace sentence-transformers | all-MiniLM-L6-v2 |
| Rate Limiting | **Slowapi** | >=0.1.9 |
| Auth | python-jose[cryptography] | >=3.3.0 |
| Package Manager | **uv** | — |
| Frontend | React 18 + Vite 5 + TypeScript 5.6 | — |
| Styling | TailwindCSS 3.4 + Framer Motion 11 | — |
| HTTP Client | Axios 1.7.9 (services) / fetch nativo (streaming) | — |
| Frontend Tests | Vitest 4 + React Testing Library 16 | — |

## Repository Map

```
SourceLogic/
├── CLAUDE.md
├── .gitignore
├── README.md
├── ROADMAP.md
├── SECURITY.md
│
├── .github/
│   └── workflows/
│       └── ci.yml               # CI: ruff → mypy → bandit → alembic check → pytest (threshold ≥70%)
│
├── backend/
│   ├── pyproject.toml           # dipendenze + config ruff/mypy/pytest/coverage
│   ├── uv.lock                  # lockfile deterministico
│   ├── .env                     # secrets (gitignored ✅)
│   ├── .env.example
│   ├── Dockerfile
│   │
│   ├── alembic/                 # migrazioni DB (autogenerate da schema)
│   │
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, rate limiter, RequestID middleware,
│   │   │                        #   lifespan: configure_logging + reset INDEXING workspaces
│   │   ├── api/
│   │   │   ├── dependencies.py  # get_current_tenant() — dispatcher: jwt → api_key → dev
│   │   │   └── v1/
│   │   │       ├── workspaces.py  # CRUD workspace + ingest + session list
│   │   │       ├── sessions.py    # history + delete session + chat streaming SSE
│   │   │       └── admin.py       # API key lifecycle: create/list/revoke (X-Admin-Secret)
│   │   │
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings: OPENAI_API_KEY, DATABASE_URL,
│   │   │   │                    #   CHROMA_PATH, AUTH_MODE, JWT_SECRET, ADMIN_SECRET,
│   │   │   │                    #   CHAT_RATE_LIMIT, LOG_LEVEL, WORKSPACE_ALLOWED_BASE
│   │   │   ├── database.py      # async engine, AsyncSessionLocal, configure_sqlite()
│   │   │   ├── embeddings.py    # singleton HuggingFaceEmbeddings (lru_cache)
│   │   │   ├── limiter.py       # Slowapi rate limiter — bucket per API key (SHA-256 prefix)
│   │   │   ├── logging_config.py # JSON structured logging (Datadog/Loki compatible)
│   │   │   ├── middleware.py    # RequestIDMiddleware — propaga X-Request-ID
│   │   │   └── vectorstore.py   # singleton ChromaDB (lru_cache)
│   │   │
│   │   ├── models/
│   │   │   └── models.py        # Workspace, Session, Message, TenantAPIKey (SQLAlchemy ORM)
│   │   │                        # UniqueConstraint(tenant_id, root_path) ✅
│   │   │                        # index su tenant_id, workspace_id, session_id ✅
│   │   │
│   │   ├── schemas/
│   │   │   ├── payloads.py      # ChatStreamPayload, ChatStreamFilters,
│   │   │   │                    #   DeleteResponse, SessionDeleteResponse, ...
│   │   │   ├── workspace.py
│   │   │   ├── session.py
│   │   │   └── message.py
│   │   │
│   │   └── services/
│   │       ├── code_parser.py   # CodeParser + SourceCodeSplitter (usato da ingest_service)
│   │       ├── chat_service.py  # ChatService — RAG + LangChain streaming
│   │       ├── db_service.py    # DatabaseService — CRUD operations
│   │       └── ingest_service.py # ChromaDB ingestion pipeline (asyncio.to_thread)
│   │
│   └── tests/                   # 78 test · coverage 77% · SQLite in-memory
│       ├── conftest.py          # AsyncClient + in-memory SQLite fixtures, tenant override
│       ├── test_admin.py        # Admin endpoints: create/list/revoke API key
│       ├── test_auth.py         # Auth modes: dev, api_key, JWT
│       ├── test_auth_e2e.py     # E2E auth flow
│       ├── test_chat_service.py # ChatService integration
│       ├── test_chat_service_unit.py # ChatService unit (mock LLM + vectorstore)
│       ├── test_chat_stream.py  # SSE streaming endpoint
│       ├── test_code_parser.py  # CodeParser + SourceCodeSplitter
│       ├── test_db_service.py   # DatabaseService CRUD
│       ├── test_health.py       # /health endpoint
│       ├── test_ingest_service_unit.py # IngestionService unit
│       ├── test_models.py       # SQLAlchemy ORM constraints
│       ├── test_schemas.py      # Pydantic validation
│       ├── test_sessions.py     # Session endpoints
│       └── test_workspaces.py   # Workspace endpoints
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts           # Vite + Vitest config
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx              # coordinatore hooks + JSX top-level
│       ├── main.tsx             # React root con ErrorBoundary
│       ├── setupTests.ts        # @testing-library/jest-dom
│       ├── components/
│       │   ├── Sidebar.tsx      # workspace list + session list con inline-confirm delete
│       │   ├── ChatArea.tsx     # messaggi + streaming indicator
│       │   ├── ChatFooter.tsx   # input + model selector + send/stop button
│       │   ├── ChatHeader.tsx   # tenant selector + filtri estensione/cartella
│       │   ├── WorkspaceModal.tsx
│       │   ├── ChatMessage.tsx  # markdown + syntax highlight
│       │   └── ErrorBoundary.tsx
│       ├── hooks/
│       │   ├── useStreaming.ts  # SSE consumer con AbortController ✅
│       │   ├── useChat.ts
│       │   ├── useWorkspaces.ts
│       │   ├── useSessions.ts
│       │   ├── useToast.ts
│       │   └── useTenant.ts
│       ├── services/
│       │   ├── apiClient.ts
│       │   ├── SessionService.ts
│       │   └── WorkspaceService.ts
│       └── types/
│           └── chat.ts          # ChatModel, ChatMessageModel, MODEL_OPTIONS
│
├── docs/
│   └── decisions/
│       └── ADR-001-chromadb-vector-store.md
│
└── docker-compose.yml
```

## Build & Run

> Tutti i comandi backend vanno eseguiti da `backend/`.

```bash
# ── BACKEND ─────────────────────────────────────────────
cd backend
uv sync --frozen --all-groups

# Prima esecuzione: applicare le migrazioni DB
uv run alembic upgrade head

# Avviare backend (porta 8000)
uv run uvicorn app.main:app --reload --port 8000

# ── FRONTEND ────────────────────────────────────────────
cd frontend
npm install          # prima volta
npm run dev          # porta 5173

# ── CI COMPLETO ─────────────────────────────────────────
# Backend (da backend/)
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run bandit -r app -ll
uv run alembic upgrade head && uv run alembic check
uv run pytest -q --cov --cov-report=term-missing --cov-fail-under=70

# Frontend (da frontend/)
npm run lint
npm run type-check
npm run test:run
npm run build
```

## Environment Variables

| Variabile | Default | Descrizione |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Chiave OpenAI per gpt-4o / gpt-4-turbo / gpt-3.5-turbo |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/codechat.db` | SQLAlchemy async URL |
| `CHROMA_PATH` | `./data/chroma_db` | Directory persistenza vettori ChromaDB |
| `AUTH_MODE` | `dev` | Modalità auth: `dev` / `api_key` / `jwt` |
| `ADMIN_SECRET` | — | Segreto per endpoint admin (richiesto se AUTH_MODE=api_key) |
| `JWT_SECRET` | — | Segreto per verifica Bearer token (richiesto se AUTH_MODE=jwt) |
| `CHAT_RATE_LIMIT` | `20/minute` | Rate limit per chiave API (formato Slowapi) |
| `LOG_LEVEL` | `INFO` | Livello logging JSON |
| `WORKSPACE_ALLOWED_BASE` | — | Path guard: restringe root_path ai sotto-percorsi di questo valore |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Lista origini CORS permesse |

## Standards

### Python
- Type hints rigorosi ovunque — MyPy `strict=true`, nessun `Any` non giustificato
- `async/await` su ogni endpoint e query DB — zero operazioni bloccanti
- Pydantic su tutti i boundary: input HTTP, config env, output HTTP
- Ruff: 100-char lines, double quotes, lf endings
- ChromaDB sync → sempre `asyncio.to_thread()`

### Auth
- Tre modalità controllate da `AUTH_MODE`: `dev` → `api_key` → `jwt`
- `dev`: trust `X-Tenant-ID` header (default `tenant-a`) — solo sviluppo locale
- `api_key`: valida `X-API-Key` contro hash SHA-256 in DB, timing-safe con `compare_digest`
- `jwt`: decodifica Bearer token HS256 con `python-jose`, estrae `tenant_id` dal payload

### Testing
- Backend: pytest + pytest-asyncio (`asyncio_mode = "auto"`) · SQLite in-memory
- Frontend: Vitest + React Testing Library · jsdom
- Target: ≥70% coverage backend (attuale: 77%) · fetch mockato con `vi.stubGlobal` nei test SSE
- No mock del DB in integration test — SQLite in-memory reale
- Patch `app.services.chat_service.settings` (non `os.environ`) per mock OPENAI_API_KEY

### Sicurezza
- Secrets in `backend/.env` (gitignored ✅)
- No raw SQL — solo SQLAlchemy ORM
- Path traversal guard: `WORKSPACE_ALLOWED_BASE` in config (opt-in per deployment)
- Rate limiting per API key con Slowapi (bucket SHA-256, previene IP-sharing abuse)
- Admin endpoints protetti con `compare_digest` (timing-safe)

## Confirmed Non-Issues

- `.env` è in `.gitignore` — chiavi API **non** committate ✅
- JWT è implementato e funzionante — settare `AUTH_MODE=jwt` e `JWT_SECRET` per abilitarlo
- `DatabaseService` (`db_service.py`) è usato da `_run_ingestion_task` in workspaces.py — non è dead code
- `TenantAPIKey` in models.py è usato da admin endpoints e auth `api_key` mode — non è dead code
