#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE_FILE="docker-compose.ip.yml"

if [[ ! -f .env ]]; then
  echo "请先复制并填写: cp .env.example .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${SITE_URL:-}" ]]; then
  echo "IP 部署请在 .env 设置 SITE_URL，例如: SITE_URL=http://43.1.1.1"
  echo "若 80 端口映射为 8080，则: SITE_URL=http://43.1.1.1:8080"
  exit 1
fi

docker compose -f "$COMPOSE_FILE" up -d --build
echo "部署完成。访问: ${SITE_URL}"
