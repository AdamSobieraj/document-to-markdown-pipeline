# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim
# Install local CA certificates
COPY root-ca.pem /usr/local/share/ca-certificates/localca.crt
RUN update-ca-certificates

# Set environment variables so Python libraries use the updated CA bundle
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV CERTINFO=/etc/ssl/certs/ca-certificates.crt
ENV AWS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Install the project into `/app`
WORKDIR /app

# Create a non-root user 'app' with fixed UID/GID 1000 to match cache mount ownership
RUN groupadd -g 1000 app && useradd -m -s /bin/sh -u 1000 -g 1000 app

# Prepare writable directories for the application user.
RUN mkdir -p /home/app/.cache/uv && chown -R app:app /app /home/app

USER app

#set uv preference to use system python
ENV UV_PYTHON_PREFERENCE=only-system
ENV UV_SYSTEM_PYTHON=true

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Enable UV native TLS
ENV UV_NATIVE_TLS=true
# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Generate proper TOML lockfile first
RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=README.md,target=README.md \
    uv lock

# Install the project's dependencies using the lockfile
RUN --mount=type=cache,target=/home/app/.cache/uv,uid=1000,gid=1000 \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Remove .venv before copying source code to avoid conflicts
RUN rm -rf /app/.venv

# Then, copy the rest of the project source code and install it
COPY --chown=app:app . /app

# Reinstall everything including the project
RUN --mount=type=cache,target=/home/app/.cache/uv,uid=1000,gid=1000 \
    uv sync --frozen --no-dev --no-editable

# Remove unnecessary files from the virtual environment before copying
RUN find /app/.venv -type d -name '__pycache__' -prune -exec rm -rf {} + || true && \
    find /app/.venv -type f -name '*.pyc' -delete || true && \
    find /app/.venv -type f -name '*.pyo' -delete || true && \
    echo "Cleaned up .venv"




# set path to the virtual environment
ENV PATH="/app/.venv/bin:$PATH"
# keep the project root importable without hard-coding a Python minor version
ENV PYTHONPATH="/app"
# set tiktoken cache directory
ENV TIKTOKEN_CACHE_DIR=/app/buissnes_agent
# Disable Python output buffering for proper stdio communication
ENV PYTHONUNBUFFERED=1

