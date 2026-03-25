# 🚀 SourceLogic SaaS: Strategic Vision & Roadmap

This project is currently a high-performance, multi-tenant Local RAG system. The following roadmap outlines the strategic evolution towards an Enterprise-grade AI platform.

## Phase 1: Advanced Retrieval (RAG Upgrades)
- [ ] **Hybrid Search (Vector + BM25)**: Combine semantic search with traditional keyword search for better accuracy on specific technical terms.
- [ ] **Reranking Layer**: Integrate a Cross-Encoder (e.g., Cohere or BGE) to re-score the top-k chunks for higher precision.
- [ ] **Contextual Retrieval**: Implement "late interaction" or contextual chunking to preserve file-level context during embeddings.

## Phase 2: Security & Identity
- [ ] **Real Authentication**: Replace `X-Tenant-ID` mocks with a robust JWT/OAuth2 flow using **Clerk** or **Auth0**.
- [ ] **Role-Based Access Control (RBAC)**: Define custom permissions (Admin, Editor, Viewer) at the workspace level for shared organizations.

## Phase 3: Observability
- [ ] **Tracing & Monitoring**: Integrate **LangSmith** or **Langfuse** to monitor LLM costs, latency, and retrieval quality.
- [ ] **Feedback Loop**: Add a "Thumbs Up/Down" UI to collect training data for future fine-tuning.

## Phase 4: Extreme Performance
- [ ] **Ollama Integration**: Allow users to run 100% local LLMs (Llama 3, Mistral) for maximum privacy.
- [ ] **Client-Side Vector Search**: Experiment with **Voy** or **Wasm-based Vector Stores** to move search logic to the browser.
