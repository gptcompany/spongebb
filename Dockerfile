# SpongeBB - Production Dockerfile
# Multi-stage build with uv for fast dependency installation
#
# Build: docker build -t spongebb .
# Run: docker run -p 8002:8000 --env-file .env spongebb

# =============================================================================
# Stage 1: Production Builder
# =============================================================================
FROM python:3.14-slim AS builder-prod

WORKDIR /app

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy dependency files first (cache layer optimization)
COPY pyproject.toml uv.lock README.md ./

# Create venv and install dependencies (production only)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source code
COPY src/ ./src/

# Install the project itself
RUN uv sync --frozen --no-dev


# =============================================================================
# Stage 2: Test Builder (includes dev dependencies like pytest)
# =============================================================================
FROM python:3.14-slim AS builder-test

WORKDIR /app

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy dependency files first (cache layer optimization)
COPY pyproject.toml uv.lock README.md ./

# Create venv and install dependencies (including dev deps)
RUN uv sync --frozen --dev --no-install-project

# Copy application source code
COPY src/ ./src/

# Install the project itself with dev dependencies
RUN uv sync --frozen --dev


# =============================================================================
# Stage 3: Runtime (production)
# =============================================================================
FROM python:3.14-slim AS runtime

WORKDIR /app

# Install curl for healthcheck and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from production builder
COPY --from=builder-prod /app/.venv /app/.venv

# Copy application source
COPY --from=builder-prod /app/src /app/src

# Fix permissions for OpenBB build lock (it needs to write on first import)
RUN chown -R appuser:appuser /app/.venv/lib/python3.11/site-packages/openbb* || true

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn (use string import for proper reload support)
CMD ["python", "-m", "uvicorn", "liquidity.api:app", "--host", "0.0.0.0", "--port", "8000"]


# =============================================================================
# Stage 4: Runtime (tests)
# =============================================================================
FROM python:3.14-slim AS test-runtime

WORKDIR /app

# Install curl for consistency and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from test builder (includes pytest + dev tools)
COPY --from=builder-test /app/.venv /app/.venv

# Copy application source
COPY --from=builder-test /app/src /app/src

# Fix permissions for OpenBB build lock (it needs to write on first import)
RUN chown -R appuser:appuser /app/.venv/lib/python3.11/site-packages/openbb* || true

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Default command for test image (can be overridden by compose)
CMD ["python", "-m", "pytest", "tests/unit", "-q"]
