#!/usr/bin/env bash
# ECS 零成本发布：后台 docker build（无需镜像仓库月费）
#
# 适用：不用 TCR/GHCR，只在 ECS 上构建一次并启动。
# 与 pull 路径相比慢（约 15–30 分钟首次），但无额外费用。
#
# === 一次性 .env 配置 ===
#   SITE_URL=http://<ECS_IP>:8080
#   UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
#   勿设 PLAYWRIGHT_DOWNLOAD_HOST=npmmirror（会构建失败）
#   勿设 BUQUE_IMAGE_REGISTRY（留空即走本脚本）
#
# === 日常发版 ===
#   cd /opt/buque && ./deploy/release-ip.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE_FILE="docker-compose.ip.yml"
LOG_DIR="$ROOT/logs"

if [[ ! -f .env ]]; then
  echo "请先复制并填写: cp .env.example .env"
  exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
  echo "请勿 sudo 运行。"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${SITE_URL:-}" ]]; then
  echo "请在 .env 设置 SITE_URL"
  exit 1
fi

# 本地 compose 镜像名（不推仓库，仅本机 tag）
export BUQUE_IMAGE_REGISTRY="${BUQUE_IMAGE_REGISTRY:-buque}"
export BUQUE_IMAGE_TAG="${BUQUE_IMAGE_TAG:-local}"
export PLAYWRIGHT_DOWNLOAD_HOST=
export PLAYWRIGHT_DOWNLOAD_BASE_URL=
export DOCKER_BUILDKIT=1

echo ">>> 拉取代码"
git pull origin main

echo ">>> 后台构建（SSH 可断开，日志: logs/docker-build-*.log）"
if [[ -f "$LOG_DIR/docker-build.pid" ]] && kill -0 "$(cat "$LOG_DIR/docker-build.pid")" 2>/dev/null; then
  echo "已有构建在运行 PID=$(cat "$LOG_DIR/docker-build.pid")"
else
  ./deploy/build-ip-background.sh all
fi

PID="$(cat "$LOG_DIR/docker-build.pid")"
LOG_FILE="$(ls -t "$LOG_DIR"/docker-build-*.log 2>/dev/null | head -1)"
echo "跟踪: tail -f $LOG_FILE"

while kill -0 "$PID" 2>/dev/null; do
  echo "$(date '+%H:%M:%S') 构建中…（末行）"
  tail -1 "$LOG_FILE" 2>/dev/null || true
  sleep 60
done

if ! grep -q "构建完成" "$LOG_FILE" 2>/dev/null; then
  echo "构建可能失败，日志末尾："
  tail -30 "$LOG_FILE"
  exit 1
fi

echo ">>> 构建完成"

echo ">>> 数据库迁移"
./deploy/migrate-ip.sh --skip-build

echo ">>> 启动服务"
./deploy/up-ip.sh --skip-build

docker compose -f "$COMPOSE_FILE" ps
echo "发布完成。访问: ${SITE_URL}"
