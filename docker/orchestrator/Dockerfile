# ============================================================
# Automatron Orchestrator — FastAPI + LangGraph
# ============================================================

FROM python:3.12-slim

LABEL maintainer="Automatron"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy project files
COPY orchestrator/pyproject.toml orchestrator/README.md* ./
COPY orchestrator/orchestrator/ ./orchestrator/
COPY orchestrator/prompts/ ./prompts/
COPY orchestrator/scripts/ ./scripts/

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Create data directory
RUN mkdir -p /app/data

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "orchestrator.main:combined_app", "--host", "0.0.0.0", "--port", "8000"]
