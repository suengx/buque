#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "请先复制并填写: cp .env.example .env"
  exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
  echo "请勿 sudo 运行。"
  echo "若报 permission denied，执行: sudo usermod -aG docker \"\$USER\" 后重新 SSH 登录。"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

SKIP_BUILD=false
if [[ "${1:-}" == "--skip-build" ]]; then
  SKIP_BUILD=true
fi

echo "UV_INDEX_URL=${UV_INDEX_URL:-（空 — 将直连 PyPI，很慢）}"
head -1 backend/Dockerfile

if [[ -z "${UV_INDEX_URL:-}" ]]; then
  echo "警告: 未设置 UV_INDEX_URL"
fi

export DOCKER_BUILDKIT=1
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/migrate-$(date +%Y%m%d_%H%M%S).log"

if [[ "$SKIP_BUILD" == false ]]; then
  echo "阶段 1/2: 构建镜像（日志同时写入 $LOG_FILE）"
  echo "提示: 可改用 ./deploy/build-ip-background.sh 后台构建，完成后本脚本加 --skip-build"
  docker compose -f docker-compose.ip.yml build --progress=plain migrate 2>&1 | tee "$LOG_FILE"
else
  echo "跳过构建（--skip-build）"
fi

echo "阶段 2/2: 数据库迁移"
docker compose -f docker-compose.ip.yml run --rm migrate 2>&1 | tee -a "$LOG_FILE"
echo "数据库迁移与种子数据完成。"
