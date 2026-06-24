#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "请先复制并填写: cp .env.example .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${DOMAIN:-}" ]]; then
  echo "生产部署请在 .env 中设置 DOMAIN（无需改 DATABASE_URL / CORS / VITE_*）"
  exit 1
fi

docker compose -f docker-compose.prod.yml up -d --build
echo "部署完成。访问: https://${DOMAIN:-$(grep ^DOMAIN= .env | cut -d= -f2)}"
