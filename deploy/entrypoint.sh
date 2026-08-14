#!/bin/sh
set -eu

database_path="${COURSEMC_DB_PATH:-/data/db.sqlite3}"
database_dir=$(dirname "$database_path")

mkdir -p "$database_dir" \
    "${COURSEMC_STATIC_ROOT:-/app/staticfiles}" \
    "${COURSEMC_MEDIA_ROOT:-/app/media}" \
    "${COURSEMC_PRIVATE_MEDIA_ROOT:-/app/private_media/lesson_solutions}"

if [ ! -f "$database_path" ]; then
    echo "Database file $database_path is missing." >&2
    echo "Run deploy/prepare_data.sh before starting the stack." >&2
    exit 1
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

exec "$@"
