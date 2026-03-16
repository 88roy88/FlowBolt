FROM python:3.12-slim

# Install system dependencies + nsjail build deps
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
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Build and install nsjail
RUN git clone --depth 1 https://github.com/google/nsjail.git /tmp/nsjail \
    && cd /tmp/nsjail \
    && make -j$(nproc) \
    && mv /tmp/nsjail/nsjail /usr/bin/nsjail \
    && rm -rf /tmp/nsjail

# Install Node.js 20 + pnpm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g pnpm \
    && rm -rf /var/lib/apt/lists/*

# Create workspace base directory
RUN mkdir -p /var/lib/ai-builder/workspaces

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
