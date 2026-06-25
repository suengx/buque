#!/usr/bin/env bash
# 【紧急兜底】ECS 加载 Mac 导出的镜像。主路径请用 ./deploy/release-ip.sh（TCR pull）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ARCHIVE="${1:-/tmp/buque-images.tar.gz}"
if [[ ! -f "$ARCHIVE" ]]; then
  echo "用法: $0 [/tmp/buque-images.tar.gz]"
  exit 1
fi

echo "加载镜像: $ARCHIVE"
gunzip -c "$ARCHIVE" | docker load
echo
echo "镜像已加载。继续部署（.env 须设 BUQUE_IMAGE_REGISTRY=buque BUQUE_IMAGE_TAG=local 或对应 tag）:"
echo "  ./deploy/migrate-ip.sh --skip-build"
echo "  ./deploy/up-ip.sh --skip-build"
