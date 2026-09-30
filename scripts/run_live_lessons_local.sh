#!/usr/bin/env bash

# Локальный стенд на одном компьютере. Dev-ключи LiveKit нельзя использовать
# на публичном сервере или в занятиях с участниками из других сетей.
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -x .venv/bin/python ]]; then
  echo "Не найден .venv/bin/python. Создайте окружение проекта перед запуском." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Не найден Docker. Установите Docker и Colima или запустите LiveKit отдельно." >&2
  exit 1
fi

if ! docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
  if ! command -v colima >/dev/null 2>&1; then
    echo "Docker не запущен и Colima не найден." >&2
    exit 1
  fi
  colima start
fi

container_name="coursemc-livekit-local"
if docker container inspect "$container_name" >/dev/null 2>&1; then
  if [[ "$(docker container inspect --format '{{.State.Running}}' "$container_name")" != "true" ]]; then
    docker start "$container_name" >/dev/null
  fi
else
  docker run -d --rm --name "$container_name" \
    -p 127.0.0.1:7880:7880/tcp \
    -p 127.0.0.1:7881:7881/tcp \
    -p 127.0.0.1:7882:7882/udp \
    livekit/livekit-server:v1.13.7 \
    --dev --bind 0.0.0.0 --node-ip 127.0.0.1 --udp-port 7882 >/dev/null
fi

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Порт 8000 уже занят. Остановите предыдущий локальный сервер и повторите запуск." >&2
  exit 1
fi

echo "CourseMC: http://127.0.0.1:8000/live-lessons/"
echo "LiveKit: ws://127.0.0.1:7880 (только этот компьютер)"
echo "Остановка сайта: Ctrl+C; остановка LiveKit: docker stop $container_name"

export DJANGO_DEBUG=1
export LIVEKIT_URL=ws://127.0.0.1:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret
exec .venv/bin/python manage.py runserver 127.0.0.1:8000
