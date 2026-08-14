#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$project_dir"

mkdir -p data/backups
docker compose exec -T web python -c "
import datetime
import os
import sqlite3

source = os.environ.get('COURSEMC_DB_PATH', '/data/db.sqlite3')
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
target = f'/backups/db.{stamp}.sqlite3'
with sqlite3.connect(source) as source_db, sqlite3.connect(target) as target_db:
    source_db.backup(target_db)
print(target)
"
