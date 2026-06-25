#!/bin/sh
set -e

if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/data/exports
  chown -R buque:buque /app/data
  exec gosu buque "$@"
fi

exec "$@"
