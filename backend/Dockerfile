# ── Stage 1: dependency installation ─────────────────────────────────────────
FROM python:3.12-slim AS deps

# Create non-root user early so uv can install to the right place
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# Install uv from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy only lockfiles first — maximises layer cache
COPY pyproject.toml uv.lock ./

# Install production deps only, into an isolated .venv
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# Bring the pre-built virtualenv from deps stage
COPY --from=deps /app/.venv /app/.venv

# Copy application source (the package the uvicorn command references)
# Build context is ./backend — copy its contents into ./backend/ so that
# the "backend.app.*" import path resolves correctly inside the container.
COPY . ./backend/

# Persistent storage directories (mounted via volume in production)
RUN mkdir -p data && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
