#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$project_dir"

if [ ! -f .env ]; then
    echo "Missing .env. Copy .env.example and fill production values." >&2
    exit 1
fi

mkdir -p \
    data/database \
    data/static \
    data/media \
    data/private_media \
    data/backups \
    data/certbot/www \
    data/certbot/conf \
    runtime/nginx

if [ ! -f data/database/db.sqlite3 ]; then
    if [ ! -f db.sqlite3 ]; then
        echo "Source db.sqlite3 is missing; refusing to create an empty site." >&2
        exit 1
    fi
    cp db.sqlite3 data/database/db.sqlite3
    cp db.sqlite3 "data/backups/db.initial.$(date +%Y%m%d-%H%M%S).sqlite3"
    echo "Copied the existing database into persistent storage."
fi

if [ ! -f runtime/nginx/default.conf ]; then
    ./deploy/render_nginx.sh http
fi

if [ "$(id -u)" = "0" ]; then
    chown -R 1000:1000 \
        data/database \
        data/static \
        data/media \
        data/private_media \
        data/backups
fi

echo "Persistent data directories are ready."
