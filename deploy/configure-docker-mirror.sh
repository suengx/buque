#!/usr/bin/env bash
# 腾讯云 ECS 拉取 docker.io 镜像加速（解决 python/node 等 build 超时）
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 sudo 运行: sudo $0"
  exit 1
fi

DAEMON_JSON="/etc/docker/daemon.json"
MIRROR="https://mirror.ccs.tencentyun.com"

mkdir -p /etc/docker

if [[ -f "$DAEMON_JSON" ]]; then
  if grep -q "mirror.ccs.tencentyun.com" "$DAEMON_JSON" 2>/dev/null; then
    echo "已配置腾讯云 Docker 镜像加速，跳过。"
    exit 0
  fi
  echo "警告: 已存在 $DAEMON_JSON，请手动合并 registry-mirrors:"
  echo "  $MIRROR"
  exit 1
fi

cat >"$DAEMON_JSON" <<EOF
{
  "registry-mirrors": ["$MIRROR"]
}
EOF

systemctl daemon-reload
systemctl restart docker
echo "Docker 镜像加速已启用: $MIRROR"
echo "验证: docker pull python:3.12-bookworm-slim"
