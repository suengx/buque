#!/usr/bin/env bash
# 【紧急兜底】ECS 长时间 Docker 构建（SSH 断开不影响）。
# 主路径请用：./deploy/release-ip.sh（零月费：ECS 构建或 GHCR pull）
# 用法: ./deploy/build-ip-background.sh [all|migrate]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TARGET="${1:-all}"
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
  if [[ -n "${DOCKER_REGISTRY_PREFIX:-}" ]]; then
    echo ">>> 预拉基础镜像"
    docker pull "${DOCKER_REGISTRY_PREFIX}python:3.12-slim-bookworm"
    docker pull "${DOCKER_REGISTRY_PREFIX}node:22-bookworm-slim"
  fi
  if [[ "$TARGET" == "all" ]]; then
    docker compose -f docker-compose.ip.yml build --progress=plain
  else
    docker compose -f docker-compose.ip.yml build --progress=plain migrate
  fi
  echo "=== $(date '+%F %T') 构建完成 ==="
) >>"$LOG_FILE" 2>&1 &

echo $! >"$PID_FILE"
echo "后台构建已启动 PID=$(cat "$PID_FILE")"
echo "日志: tail -f $LOG_FILE"
echo "构建完成后执行:"
echo "  ./deploy/migrate-ip.sh --skip-build"
echo "  ./deploy/up-ip.sh --skip-build"
