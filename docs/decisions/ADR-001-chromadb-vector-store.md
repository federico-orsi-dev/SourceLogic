# ADR-001: Selection of ChromaDB as Vector Store for Local RAG

- Status: Accepted
- Date: 2026-03-25
- Deciders: Federico Orsi

## Context

Chat-Project (CodeChat) aims to provide a local-first retrieval-augmented generation (RAG) assistant for codebase exploration. This require storing and querying embeddings for thousands of code chunks efficiently without relying on expensive, cloud-hosted vector databases which could expose private code.

## Decision

We have selected **ChromaDB** as the primary vector storage and retrieval engine. It will be used in a persistent, file-system-backed mode for the local developer environment.

## Rationale

1. **Local-First Native**: ChromaDB is designed to run locally (in-process or via Docker) with zero third-party cloud data leakage.
2. **Persistence**: Its ability to persist to a specific file-system path allows for incremental indexing of large repositories without re-processing on every restart.
3. **Simplicity**: No complex cluster management (like Milvus or elasticsearch) is required, reducing the overhead for the local developer.
4. **LangChain-Ready**: Mature integration with the LangChain ecosystem, which is used in the backend's service layer.

## Consequences

### Positive:
- **Fast Local Retrieval**: Near-zero network latency for similarity searches.
- **Portability**: The entire vector index can be stored alongside the workspace's metadata.
- **Privacy Compliance**: Ideal for projects requiring strict control over where source code data resides.

### Negative:
- **Manual Migration**: Scaling to a distributed production environment would require transitioning to a handled service (managed Chroma or Pinecone).
- **Disk I/O**: Performance is bound by local disk speed, especially during large-scale ingestion.
- **Concurrency**: Local SQLite-backed storage has limitations for high-concurrency write operations.

### Trade-offs:
We prioritized **Data Privacy** and **Ease of Deployment** over cloud-scale horizontal scalability. For a developer-centric repository explorer, ChromaDB is the optimal localized choice.
