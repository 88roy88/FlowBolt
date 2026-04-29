ARG BACKEND_BASE_IMAGE
FROM ${BACKEND_BASE_IMAGE}

# UV configuration build args
ARG UV_NATIVE_TLS=true
ARG UV_INDEX_URL
ARG UV_INDEX_NAME=default
ARG UV_INDEX_DEFAULT=true
ARG UV_INSECURE_HOST1
ARG UV_INSECURE_HOST2

USER root
WORKDIR /app

# Copy all project files
COPY --chown=appuser:appuser . .

# Generate uv.toml from build args (overwriting any existing one from the context)
RUN echo "native-tls = ${UV_NATIVE_TLS}" > uv.toml && \
    echo "allow-insecure-host = [\"${UV_INSECURE_HOST1}\", \"${UV_INSECURE_HOST2}\"]" >> uv.toml && \
    echo "[[index]]" >> uv.toml && \
    echo "name = \"${UV_INDEX_NAME}\"" >> uv.toml && \
    echo "url = \"${UV_INDEX_URL}\"" >> uv.toml && \
    echo "default = ${UV_INDEX_DEFAULT}" >> uv.toml

# Run uv sync using the generated uv.toml
RUN uv sync --no-dev --frozen

USER appuser

EXPOSE 8000
