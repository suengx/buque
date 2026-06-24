#!/usr/bin/env bash
# 清理僵死的 Docker 构建（计划第二步）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "停止卡住的 compose build..."
pkill -f 'docker compose.*docker-compose.ip.yml build' 2>/dev/null || true

PID_FILE="$ROOT/logs/docker-build.pid"
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "终止后台构建 shell PID=$pid"
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  echo "已删除 $PID_FILE"
fi

echo "清理 buildkit 缓存锁..."
docker buildx prune -f 2>/dev/null || true

echo "完成。可重新构建: ./deploy/build-ip-background.sh"
