# Global Liquidity Monitor - Production Dockerfile
# Multi-stage build with uv for fast dependency installation
#
# Build: docker build -t liquidity-monitor .
# Run: docker run -p 8000:8000 --env-file .env liquidity-monitor

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy dependency files first (cache layer optimization)
COPY pyproject.toml uv.lock README.md ./

# Create venv and install dependencies (production only, no dev deps)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source code
COPY src/ ./src/

# Install the project itself
RUN uv sync --frozen --no-dev


# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install curl for healthcheck and create non-root user
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY --from=builder /app/src /app/src

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
