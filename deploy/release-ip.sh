#!/usr/bin/env bash
# ECS 标准发布入口（零月费）
#
# 两种模式（由 .env 决定，无需 TCR 企业版）：
#
#   A) BUQUE_IMAGE_REGISTRY 已设置 → 从 GHCR 拉镜像（免费，需 GitHub Actions Release）
#      见 deploy/release-ip-pull.sh 顶部配置
#
#   B) BUQUE_IMAGE_REGISTRY 未设置 → ECS 后台构建（慢但零费用，默认推荐起步）
#      见 deploy/release-ip-build.sh 顶部配置
#
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

if [[ -n "${BUQUE_IMAGE_REGISTRY:-}" ]]; then
  echo "模式: pull（${BUQUE_IMAGE_REGISTRY}）"
  exec "$ROOT/deploy/release-ip-pull.sh"
else
  echo "模式: build（ECS 后台构建，无镜像仓库费用）"
  exec "$ROOT/deploy/release-ip-build.sh"
fi
