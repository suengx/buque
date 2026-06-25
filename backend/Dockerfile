# buque-backend-dockerfile-v5
# ARG 须在首个 FROM 之前声明
ARG DOCKER_REGISTRY_PREFIX=

FROM ${DOCKER_REGISTRY_PREFIX}python:3.12-slim-bookworm

ARG DEBIAN_APT_MIRROR=
ARG UV_INDEX_URL=
ARG PLAYWRIGHT_DOWNLOAD_HOST=
ARG PLAYWRIGHT_DOWNLOAD_BASE_URL=

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_INDEX_URL=${UV_INDEX_URL} \
    PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST} \
    PLAYWRIGHT_DOWNLOAD_BASE_URL=${PLAYWRIGHT_DOWNLOAD_BASE_URL} \
    PLAYWRIGHT_BROWSERS_PATH=/app/.playwright-browsers \
    HOME=/home/buque

COPY docker/setup-apt-mirror.sh /tmp/setup-apt-mirror.sh

RUN DEBIAN_APT_MIRROR="$DEBIAN_APT_MIRROR" sh /tmp/setup-apt-mirror.sh \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gosu \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -n "$UV_INDEX_URL" ]; then \
         pip install --no-cache-dir uv -i "$UV_INDEX_URL"; \
       else \
         pip install --no-cache-dir uv; \
       fi

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY contracts ./contracts
COPY fixtures ./fixtures
COPY docker/entrypoint.sh ./docker/entrypoint.sh

# 拆分两层 + BuildKit 缓存：SSH 断开后重试不必重新下载全部 wheel
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    set -eux; \
    if [ -n "$UV_INDEX_URL" ]; then \
      echo ">>> uv sync --index-url $UV_INDEX_URL"; \
      uv sync --frozen --no-dev --index-url "$UV_INDEX_URL"; \
    else \
      echo ">>> uv sync (default PyPI, 国内 ECS 建议设 UV_INDEX_URL)"; \
      uv sync --frozen --no-dev; \
    fi

# Playwright 浏览器必须写入镜像层；cache mount 不会进入最终镜像
RUN set -eux; \
    echo ">>> playwright install (PLAYWRIGHT_DOWNLOAD_BASE_URL=${PLAYWRIGHT_DOWNLOAD_BASE_URL:-default})"; \
    uv run playwright install chromium --with-deps

RUN groupadd --system --gid 1001 buque \
    && useradd --system --uid 1001 --gid buque --home-dir /home/buque --create-home buque \
    && chmod +x /app/docker/entrypoint.sh \
    && chown -R buque:buque /app /home/buque

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["buque-api"]
