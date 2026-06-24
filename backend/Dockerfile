ARG DOCKER_REGISTRY_PREFIX=
FROM ${DOCKER_REGISTRY_PREFIX}python:3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest
COPY --from=${UV_IMAGE} /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY contracts ./contracts
COPY fixtures ./fixtures

RUN uv sync --frozen --no-dev \
    && uv run playwright install chromium --with-deps

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["buque-api"]
