#!/usr/bin/env bash
# 本地 Mac 验证生产镜像（与服务器同一套 docker-compose.ip.yml，仅覆盖镜像源与访问地址）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose -f docker-compose.ip.yml"

# 本地：强制直连 docker.io（覆盖 .env 里为 ECS 配置的 DOCKER_REGISTRY_PREFIX）
export DOCKER_REGISTRY_PREFIX=
export SITE_URL=http://localhost:8080
export HTTP_PORT=8080

cmd="${1:-up}"

case "$cmd" in
  build)
    $COMPOSE build
    ;;
  migrate)
    $COMPOSE run --rm --build migrate
    ;;
  up)
    $COMPOSE up -d --build
    echo "本地生产栈: http://localhost:8080"
    echo "健康检查: curl -f http://localhost:8080/api/v1/health"
    ;;
  down)
    $COMPOSE down
    ;;
  logs)
    shift || true
    $COMPOSE logs -f "${@:-api}"
    ;;
  *)
    echo "用法: $0 {build|migrate|up|down|logs [service]}"
    exit 1
    ;;
esac
