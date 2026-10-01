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
echo "Остановка сайта и планировщика: Ctrl+C; остановка LiveKit: docker stop $container_name"

export DJANGO_DEBUG=1
export LIVEKIT_URL=ws://127.0.0.1:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret

# Применяем новые миграции к существующей базе только после безопасной SQLite-копии.
if ! .venv/bin/python manage.py migrate --check --noinput >/dev/null; then
  mkdir -p data/backups/local
  .venv/bin/python manage.py shell -c '
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from django.conf import settings
source = Path(settings.DATABASES["default"]["NAME"])
target = Path("data/backups/local") / (datetime.now().strftime("db.%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8] + ".sqlite3")
with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as database, sqlite3.connect(target) as backup:
    database.backup(backup)
    assert backup.execute("PRAGMA quick_check").fetchone()[0] == "ok"
print("Резервная копия:", target)
'
  .venv/bin/python manage.py migrate --noinput
fi

scheduler_pid=""
server_pid=""
stop_local_processes() {
  [[ -z "$scheduler_pid" ]] || kill "$scheduler_pid" 2>/dev/null || true
  # runserver использует дочерний процесс перезагрузки — закрываем и его.
  [[ -z "$server_pid" ]] || pkill -TERM -P "$server_pid" 2>/dev/null || true
  [[ -z "$server_pid" ]] || kill "$server_pid" 2>/dev/null || true
}
trap stop_local_processes EXIT
trap 'exit 130' INT TERM
.venv/bin/python manage.py live_lesson_scheduler &
scheduler_pid=$!
.venv/bin/python manage.py runserver 127.0.0.1:8000 &
server_pid=$!
wait "$server_pid"
