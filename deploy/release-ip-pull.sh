#!/usr/bin/env bash
# ECS 发布：从 GHCR 拉镜像（免费，无 TCR 月费）
#
# === 一次性准备 ===
# 1. GitHub 仓库 Settings → Secrets → Actions，添加 SITE_URL（如 http://42.192.42.169:8080）
#    GOOGLE_CLIENT_ID 可选
# 2. push main 后等 Actions「Release」workflow 成功
# 3. 创建 GitHub PAT（read:packages），ECS 登录：
#      echo <PAT> | docker login ghcr.io -u <GitHub用户名> --password-stdin
# 4. ECS .env：
#      BUQUE_IMAGE_REGISTRY=ghcr.io/<github用户名小写>
#      BUQUE_IMAGE_TAG=main
#    若仓库属组织，REGISTRY 为 ghcr.io/<组织名小写>
#
# === 日常发版 ===
#   ./deploy/release-ip-pull.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE_FILE="docker-compose.ip.yml"

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

if [[ -z "${BUQUE_IMAGE_REGISTRY:-}" ]]; then
  echo "请在 .env 设置 BUQUE_IMAGE_REGISTRY（如 ghcr.io/yourname）"
  exit 1
fi

if [[ -z "${SITE_URL:-}" ]]; then
  echo "请在 .env 设置 SITE_URL"
  exit 1
fi

TAG="${BUQUE_IMAGE_TAG:-main}"
BACKEND_IMAGE="${BUQUE_IMAGE_REGISTRY}/buque-backend:${TAG}"
WEB_IMAGE="${BUQUE_IMAGE_REGISTRY}/buque-web:${TAG}"

echo ">>> 拉取代码"
git pull origin main

echo ">>> 拉取镜像"
echo "    backend: ${BACKEND_IMAGE}"
echo "    web:     ${WEB_IMAGE}"
docker compose -f "$COMPOSE_FILE" pull migrate api scheduler web

echo ">>> 数据库迁移"
./deploy/migrate-ip.sh --skip-build

echo ">>> 启动服务"
./deploy/up-ip.sh --skip-build

docker compose -f "$COMPOSE_FILE" ps
echo "发布完成。访问: ${SITE_URL}"
