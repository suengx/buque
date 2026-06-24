# ARG 须在首个 FROM 之前声明，供各阶段 FROM 使用
ARG DOCKER_REGISTRY_PREFIX=

FROM ghcr.io/astral-sh/uv:latest AS uv

FROM ${DOCKER_REGISTRY_PREFIX}python:3.12-slim-bookworm

ARG DEBIAN_APT_MIRROR=
ARG UV_INDEX_URL=
ARG PLAYWRIGHT_DOWNLOAD_HOST=

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_INDEX_URL=${UV_INDEX_URL} \
    PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST}

RUN set -eux; \
    if [ -n "$DEBIAN_APT_MIRROR" ]; then \
      for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        if [ -f "$f" ]; then \
          sed -i "s|deb.debian.org|${DEBIAN_APT_MIRROR}|g" "$f"; \
          sed -i "s|security.debian.org|${DEBIAN_APT_MIRROR}|g" "$f"; \
        fi; \
      done; \
    fi; \
    apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
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
