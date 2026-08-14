#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$project_dir"

./deploy/prepare_data.sh
./deploy/render_nginx.sh http

docker compose up -d --build web nginx
docker compose ps

echo "HTTP bootstrap is running. Point DNS to the server, then run:"
echo "  ./deploy/enable_https.sh"
