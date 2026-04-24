# SourceLogic SaaS — Project Brain

## Context

Python SaaS application — sistema RAG (Retrieval-Augmented Generation) multi-tenant per esplorazione di codebase locali.
Indicizza file sorgenti in ChromaDB e serve risposte contestualizzate via chat streaming.
Isolamento tenant a livello storage (SQLAlchemy + filtri metadati ChromaDB). Auth attualmente mockato.

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
| Vector Store | **ChromaDB** (locale, persistente) | non pinned |
| Embeddings | HuggingFace sentence-transformers | all-MiniLM-L6-v2 |
| Package Manager | **uv** | — |
| Frontend | React 18 + Vite 5 + TypeScript 5.6 | — |
| Styling | TailwindCSS 3.4 + Framer Motion 11 | — |
| HTTP Client | Axios 1.7.9 (services) / fetch nativo (streaming) | — |
| Frontend Tests | Vitest 4 + React Testing Library 16 | — |

## Repository Map

```
SourceLogic SaaS/
├── CLAUDE.md
├── .gitignore
├── README.md
│
├── .github/
│   └── workflows/
│       └── ci.yml               # CI: ruff → mypy → bandit → pytest (threshold ≥70%)
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
│   │   ├── main.py              # FastAPI app, CORS, router include, lifespan startup
│   │   ├── api/
│   │   │   ├── dependencies.py  # get_current_tenant() — auth MOCK (intenzionale)
│   │   │   └── v1/
│   │   │       ├── workspaces.py  # CRUD workspace + ingest + session list
│   │   │       └── sessions.py    # history + delete session + chat streaming SSE
│   │   │
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings: OPENAI_API_KEY, DATABASE_URL,
│   │   │   │                    #   CHROMA_PATH, WORKSPACE_ALLOWED_BASE (path guard)
│   │   │   ├── database.py      # async engine, AsyncSessionLocal, init_db()
│   │   │   └── embeddings.py    # singleton HuggingFaceEmbeddings (lru_cache)
│   │   │
│   │   ├── models/
│   │   │   └── models.py        # Workspace, Session, Message (SQLAlchemy ORM)
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
│   └── tests/                   # 114 test · coverage ≥77% · SQLite in-memory
│       ├── conftest.py
│       ├── test_chat_service.py
│       ├── test_db_service.py
│       ├── test_health.py
│       ├── test_models.py
│       ├── test_schemas.py
│       ├── test_sessions.py
│       └── test_workspaces.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts           # Vite + Vitest config
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx              # ~80 righe — coordinatore hooks + JSX top-level
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
└── docker-compose.yml
```

## Build & Run

> Tutti i comandi backend vanno eseguiti da `SourceLogic SaaS/backend/`.

```bash
# ── BACKEND ─────────────────────────────────────────────
cd "SourceLogic SaaS/backend"
uv sync --frozen --all-groups

# Prima esecuzione: applicare le migrazioni DB
uv run alembic upgrade head

# Avviare backend (porta 8000)
uv run uvicorn app.main:app --reload --port 8000

# ── FRONTEND ────────────────────────────────────────────
cd "SourceLogic SaaS/frontend"
npm install          # prima volta
npm run dev          # porta 5173

# ── CI COMPLETO ─────────────────────────────────────────
# Backend (da backend/)
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run bandit -r app -ll
uv run pytest -q --cov --cov-report=term-missing --cov-fail-under=70

# Frontend (da frontend/)
npm run test:run     # Vitest
npx tsc --noEmit
```

## Standards

### Python
- Type hints rigorosi ovunque — MyPy `strict=true`, nessun `Any` non giustificato
- `async/await` su ogni endpoint e query DB — zero operazioni bloccanti
- Pydantic su tutti i boundary: input HTTP, config env, output HTTP
- Ruff: 100-char lines, double quotes, lf endings
- ChromaDB sync → sempre `asyncio.to_thread()`

### Testing
- Backend: pytest + pytest-asyncio (`asyncio_mode = "auto"`) · SQLite in-memory
- Frontend: Vitest + React Testing Library · jsdom
- Target: ≥70% coverage backend · fetch mockato con `vi.stubGlobal` nei test SSE
- No mock del DB in integration test — SQLite in-memory reale

### Sicurezza
- Secrets in `backend/.env` (gitignored ✅)
- No raw SQL — solo SQLAlchemy ORM
- Path traversal guard: `WORKSPACE_ALLOWED_BASE` in config (opt-in per deployment)

## Confirmed Non-Issues

- `.env` è in `.gitignore` — chiavi API **non** committate ✅
- Auth mock via `X-Tenant-ID` è intenzionale — non implementare JWT senza richiesta esplicita
- `DatabaseService` (`db_service.py`) è usato da `_run_ingestion_task` in workspaces.py — non è dead code
