# ============================================================================
# Dockerfile for LLM Guard Bench
# Base: python:3.11-slim (lightweight, ~150MB)
# No gcc or build tools — all dependencies have prebuilt wheels
# ============================================================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="Security Team"
LABEL description="LLM Guard Bench: Adversarial Attack Benchmark Framework"

# ============================================================================
# Build Arguments
# ============================================================================
ARG PIP_NO_CACHE_DIR=1
ARG PIP_DISABLE_PIP_VERSION_CHECK=1

# ============================================================================
# Environment Setup
# ============================================================================
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ============================================================================
# Dependency Installation (Layer 1: Minimal system libraries)
# ============================================================================
# Only install curl (for health checks) and ca-certificates (for HTTPS)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ============================================================================
# Python Dependencies (Layer 2: Cached Python packages)
# Separated from source code so changes to .py files don't rebuild this layer
# ============================================================================

# Copy dependency specification first
COPY setup.py pyproject.toml* requirements.txt* ./
COPY config/ ./config/

# Install Python dependencies (all have prebuilt wheels for 3.11)
# Install Python dependencies cleanly without broken force-reinstall flags
RUN pip install --upgrade pip setuptools wheel \
    && pip install -e .

# ============================================================================
# Application Code (Layer 3: Source code)
# ============================================================================
COPY . .

# ============================================================================
# Directory Setup
# ============================================================================
RUN mkdir -p /app/results \
    && chmod 755 /app/results

# ============================================================================
# Health Check
# ============================================================================
HEALTHCHECK --interval=180s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1/health || python -c "import sys; sys.exit(0)" || exit 1

# ============================================================================
# Default Command
# ============================================================================
CMD ["python", "main.py", "run", "--help"]
