#!/usr/bin/env bash
# 【紧急兜底】Mac 本地构建完成后导出镜像，供 scp 到 ECS。
# 主路径请用：./deploy/release-ip.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${1:-/tmp/buque-images.tar.gz}"
REGISTRY="${BUQUE_IMAGE_REGISTRY:-buque}"
TAG="${BUQUE_IMAGE_TAG:-local}"
IMAGES=(
  "${REGISTRY}/buque-backend:${TAG}"
  "${REGISTRY}/buque-web:${TAG}"
)

echo "检查镜像是否存在..."
missing=()
for img in "${IMAGES[@]}"; do
  if ! docker image inspect "$img" &>/dev/null; then
    missing+=("$img")
  fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "缺少镜像: ${missing[*]}"
  echo "请先执行（ECS 为 x86，必须 amd64）:"
  echo "  DOCKER_DEFAULT_PLATFORM=linux/amd64 make docker-ip-build-ecs"
  exit 1
fi

arch="$(docker image inspect "${REGISTRY}/buque-backend:${TAG}" --format '{{.Architecture}}')"
if [[ "$arch" != "amd64" ]]; then
  echo "错误: buque-backend 架构为 $arch，ECS 需要 amd64"
  echo "请重新构建: DOCKER_DEFAULT_PLATFORM=linux/amd64 make docker-ip-build-ecs"
  exit 1
fi

echo "导出到 $OUT ..."
docker save "${IMAGES[@]}" | gzip >"$OUT"
size="$(du -h "$OUT" | cut -f1)"
echo "完成: $OUT ($size)"
echo
echo "上传到 ECS:"
echo "  scp $OUT ubuntu@<ECS_IP>:/tmp/"
echo "在 ECS 上:"
echo "  ./deploy/import-images.sh /tmp/buque-images.tar.gz"
