# ============================================================
# Automatron Golden Image — Ubuntu 24.04 + All Runtimes
# ============================================================
# This is the base image for ALL project containers.
# Pre-installed: Python 3.12, Node.js 22, Cline CLI, Git, etc.
# ============================================================

FROM ubuntu:24.04

LABEL maintainer="Automatron" \
      description="Golden base image for Automatron project containers"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# ── System packages ────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    curl \
    wget \
    git \
    jq \
    unzip \
    ca-certificates \
    gnupg \
    # Build tools
    build-essential \
    # Python
    python3.12 \
    python3.12-venv \
    python3-pip \
    # Misc
    sudo \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 22 LTS ─────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── pnpm ────────────────────────────────────────────────────
RUN npm install -g pnpm

# ── Cline CLI ───────────────────────────────────────────────
RUN npm install -g cline

# ── Create non-privileged user ──────────────────────────────
RUN useradd -m -s /bin/bash -u 1000 developer \
    && mkdir -p /workspace \
    && chown -R developer:developer /workspace

# ── Copy scaffold scripts ──────────────────────────────────
COPY orchestrator/scripts/ /opt/automatron/scripts/
RUN chmod +x /opt/automatron/scripts/*.sh

# ── Set working directory ───────────────────────────────────
WORKDIR /workspace

# ── Switch to non-privileged user ───────────────────────────
USER developer

# ── Default command (keep alive) ────────────────────────────
CMD ["sleep", "infinity"]
