#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "请先复制并填写: cp .env.example .env"
  exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
  echo "请勿 sudo 运行；请用普通用户（已加入 docker 组）执行本脚本。"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${UV_INDEX_URL:-}" ]]; then
  echo "警告: 未设置 UV_INDEX_URL，构建将直连 pypi.org（国内 ECS 会很慢）"
fi

docker compose -f docker-compose.ip.yml run --rm --build migrate
echo "数据库迁移与种子数据完成。"
