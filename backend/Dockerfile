# Build stage for nsjail
FROM python:3.12-slim AS nsjail-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    bison \
    flex \
    gcc \
    g++ \
    git \
    libprotobuf-dev \
    libnl-route-3-dev \
    libtool \
    make \
    pkg-config \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

# Pin nsjail to specific version for reproducibility
RUN git clone --depth 1 --branch 3.4 https://github.com/google/nsjail.git /tmp/nsjail \
    && cd /tmp/nsjail \
    && make -j$(nproc) \
    && mv /tmp/nsjail/nsjail /usr/bin/nsjail

# Final stage
FROM python:3.12-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libprotobuf32t64 \
    libnl-route-3-200 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy nsjail binary from builder stage
COPY --from=nsjail-builder /usr/bin/nsjail /usr/bin/nsjail

# Install Node.js 20 + pnpm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g pnpm \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create non-root user
RUN useradd -m -u 1000 appuser \
    && mkdir -p /var/lib/ai-builder/workspaces \
    && chown -R appuser:appuser /var/lib/ai-builder

# Create data directory for runtime database
RUN mkdir -p /app/data && chown appuser:appuser /app/data

WORKDIR /app

# Install Python dependencies as root (for system-wide installation)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Copy application code and set ownership
COPY --chown=appuser:appuser . .

# Ensure /app directory and all contents are owned by appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Use namespaced sandbox mode in container (nsjail isolation)
ENV AIB_SANDBOX_MODE=namespaced

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uv", "run", "start"]
