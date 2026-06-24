#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "缺少 .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${ROOT}/backups"
mkdir -p "$OUT_DIR"
OUT_FILE="${OUT_DIR}/buque_${STAMP}.sql.gz"

docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-buque}" "${POSTGRES_DB:-buque}" | gzip > "$OUT_FILE"

echo "已备份: $OUT_FILE"
