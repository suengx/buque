#!/usr/bin/env bash
# 长时间 Docker 构建：后台运行，SSH 断开不影响。用法: ./deploy/build-ip-background.sh [migrate|all]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TARGET="${1:-migrate}"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/docker-build-$(date +%Y%m%d_%H%M%S).log"
PID_FILE="$LOG_DIR/docker-build.pid"

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "已有构建在运行 PID=$(cat "$PID_FILE")"
  echo "跟踪: tail -f $(ls -t "$LOG_DIR"/docker-build-*.log | head -1)"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "缺少 .env"
  exit 1
fi

(
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  export DOCKER_BUILDKIT=1
  echo "=== $(date '+%F %T') 开始构建 target=$TARGET ==="
  echo "UV_INDEX_URL=${UV_INDEX_URL:-（空！）}"
  echo "DEBIAN_APT_MIRROR=${DEBIAN_APT_MIRROR:-（空）}"
  if [[ "$TARGET" == "all" ]]; then
    docker compose -f docker-compose.ip.yml build
  else
    docker compose -f docker-compose.ip.yml build migrate
  fi
  echo "=== $(date '+%F %T') 构建完成 ==="
) >>"$LOG_FILE" 2>&1 &

echo $! >"$PID_FILE"
echo "后台构建已启动 PID=$(cat "$PID_FILE")"
echo "日志: tail -f $LOG_FILE"
echo "构建完成后执行: ./deploy/migrate-ip.sh --skip-build"
