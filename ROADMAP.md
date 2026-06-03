# SourceLogic SaaS: Strategic Roadmap

## Completed

- [x] **Multi-tenant isolation** — tenant_id scoped to all workspaces, sessions, and vector chunks
- [x] **API key authentication** — SHA-256 hashing, timing-safe comparison, revocation support
- [x] **JWT Bearer token auth** — HS256 implementation with `tenant_id` claim (`AUTH_MODE=jwt`)
- [x] **Admin endpoints** — API key lifecycle management (create / list / revoke)
- [x] **Rate limiting** — per-key bucketing via Slowapi (configurable `CHAT_RATE_LIMIT`)
- [x] **Structured logging** — JSON output compatible with Datadog / Loki
- [x] **RequestID middleware** — propagates `X-Request-ID` through request lifecycle
- [x] **Incremental indexing** — MD5 manifest skips unchanged files on re-ingest
- [x] **Source citations** — every AI answer links to file path, name, and line number
- [x] **SSE streaming** — token-by-token delivery with AbortController on the frontend

## Phase 1: Advanced Retrieval

- [ ] **Hybrid Search (Vector + BM25)**: Combine semantic search with keyword search for better accuracy on exact identifiers and method names.
- [ ] **Reranking Layer**: Integrate a Cross-Encoder (e.g., Cohere or BGE) to re-score the top-k chunks for higher precision.
- [ ] **Contextual Retrieval**: Contextual chunking to preserve file-level context during embeddings.

## Phase 2: Identity & Access

- [ ] **OAuth2 / OIDC provider integration**: Plug Auth0, Okta, or Clerk into the existing JWT auth layer (swap `JWT_SECRET` for a provider public key).
- [ ] **Role-Based Access Control (RBAC)**: Admin, Editor, Viewer roles at the workspace level for shared organizations.
- [ ] **Frontend API key UI**: Allow tenants to manage their own API keys from the chat interface.

## Phase 3: Observability

- [ ] **LLM tracing**: Integrate LangSmith or Langfuse to monitor costs, latency, and retrieval quality per query.
- [ ] **Feedback loop**: Thumbs-up / down UI to collect signal for future fine-tuning.

## Phase 4: Performance & Portability

- [ ] **Ollama integration**: Allow 100% local LLMs (Llama 3, Mistral) for maximum data privacy.
- [ ] **PostgreSQL support**: `DATABASE_URL` swap already works — add connection pooling and asyncpg benchmarks.
- [ ] **Client-side vector search**: Experiment with Wasm-based stores (Voy) for edge deployments.
