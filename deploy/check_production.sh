#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$project_dir"

docker compose exec -T web python manage.py check --deploy
docker compose exec -T web python manage.py showmigrations --plan
docker compose exec -T web python manage.py test --keepdb
docker compose exec -T nginx nginx -t
