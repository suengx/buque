#!/bin/sh
# Docker build 内切换 Debian apt 源（DEBIAN_APT_MIRROR 如 mirrors.tencent.com）
set -eu
if [ -z "${DEBIAN_APT_MIRROR:-}" ]; then
  exit 0
fi
for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do
  if [ -f "$f" ]; then
    sed -i "s|deb.debian.org|${DEBIAN_APT_MIRROR}|g" "$f"
    sed -i "s|security.debian.org|${DEBIAN_APT_MIRROR}|g" "$f"
  fi
done
