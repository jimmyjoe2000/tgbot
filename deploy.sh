#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker 未安装，请先安装 Docker Engine。"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose 插件不可用，请先安装 Docker Compose Plugin。"
  exit 1
fi

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "已根据 .env.example 生成 .env，请先填写真实配置后重新执行。"
  else
    echo "缺少 .env 和 .env.example，无法继续部署。"
  fi
  exit 1
fi

docker compose pull --ignore-pull-failures
docker compose build --pull
docker compose up -d

echo "部署完成。"
echo "Swagger: http://localhost:8000/docs"
echo "Health:  http://localhost:8000/api/v1/health"
