#!/bin/sh
set -eu

mode=${1:-http}
project_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
env_file="$project_dir/.env"

if [ ! -f "$env_file" ]; then
    echo "Missing $env_file. Copy .env.example and fill it first." >&2
    exit 1
fi

domain=$(sed -n 's/^DOMAIN=//p' "$env_file" | tail -n 1 | tr -d '\r')
case "$domain" in
    *[!A-Za-z0-9.-]*|'')
        echo "DOMAIN in .env is empty or invalid." >&2
        exit 1
        ;;
esac

template="$project_dir/deploy/nginx/$mode.conf.template"
if [ ! -f "$template" ]; then
    echo "Unknown Nginx mode: $mode" >&2
    exit 1
fi

mkdir -p "$project_dir/runtime/nginx"
sed "s/__DOMAIN__/$domain/g" "$template" \
    > "$project_dir/runtime/nginx/default.conf"

echo "Rendered Nginx $mode configuration for $domain."
