#!/usr/bin/env bash
# ECS 构建状态诊断（计划第一步）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== buque 构建诊断 $(date '+%F %T') ==="
echo

PID_FILE="$ROOT/logs/docker-build.pid"
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  echo "PID 文件: $pid"
  if kill -0 "$pid" 2>/dev/null; then
    echo "构建进程: 存活"
  else
    echo "构建进程: 已死（PID 文件过期）"
  fi
else
  echo "PID 文件: 无"
fi
echo

echo "--- docker / buildkit 进程 ---"
ps aux | grep -E 'docker.*build|buildkit' | grep -v grep || echo "（无活跃 build 进程）"
echo

echo "--- 最近构建日志（末尾 20 行）---"
latest="$(ls -t "$ROOT"/logs/docker-build-*.log 2>/dev/null | head -1 || true)"
if [[ -n "$latest" ]]; then
  echo "文件: $latest"
  tail -20 "$latest"
else
  echo "（无 docker-build 日志）"
fi
echo

echo "--- 磁盘 / 内存 ---"
df -h /
if command -v free &>/dev/null; then
  free -h
else
  vm_stat | head -8
fi
echo

echo "--- Dockerfile 版本 ---"
head -1 backend/Dockerfile
echo

if [[ -f .env ]]; then
  echo "--- .env 构建加速变量 ---"
  grep -E '^(DOCKER_REGISTRY_PREFIX|UV_INDEX_URL|DEBIAN_APT_MIRROR|PLAYWRIGHT_DOWNLOAD|SITE_URL)=' .env || echo "（缺少部分变量）"
else
  echo "警告: 缺少 .env"
fi
echo

echo "--- docker 容器 ---"
docker ps -a 2>/dev/null | head -10 || echo "docker ps 失败（权限？）"
echo

if [[ -n "$latest" ]] && grep -q "构建完成" "$latest" 2>/dev/null; then
  echo "结论: 最近一次后台构建已成功，可执行:"
  echo "  ./deploy/migrate-ip.sh --skip-build"
  echo "  ./deploy/up-ip.sh --skip-build"
elif [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "结论: 构建仍在进行，跟踪: tail -f $latest"
else
  echo "结论: 无活跃构建或已失败，执行:"
  echo "  ./deploy/cleanup-stale-build.sh"
  echo "  ./deploy/build-ip-background.sh"
fi
