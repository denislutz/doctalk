# =============================================================================
# DocTalk API - FastAPI Backend Dockerfile
# Multi-stage build for smaller production image
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Base image with Python dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.0

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure Poetry (no virtualenv in container)
RUN poetry config virtualenvs.create false

# Install production dependencies only
RUN poetry install --no-interaction --no-ansi --only main --no-root

# -----------------------------------------------------------------------------
# Stage 2: Development image with all dependencies
# -----------------------------------------------------------------------------
FROM base AS development

# Install dev dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY app/ ./app/
COPY tests/ ./tests/
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs

# Expose port
EXPOSE 8000

# Development command with auto-reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# -----------------------------------------------------------------------------
# Stage 3: Production image (minimal)
# -----------------------------------------------------------------------------
FROM base AS production

# Copy only the application code
COPY app/ ./app/

# Create necessary directories with proper permissions
RUN mkdir -p /app/uploads /app/logs && \
    chmod 755 /app/uploads /app/logs

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
