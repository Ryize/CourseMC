#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$project_dir"

if [ ! -f .env ]; then
    echo "Missing .env." >&2
    exit 1
fi

domain=$(sed -n 's/^DOMAIN=//p' .env | tail -n 1 | tr -d '\r')
email=$(sed -n 's/^LETSENCRYPT_EMAIL=//p' .env | tail -n 1 | tr -d '\r')

case "$domain" in
    *[!A-Za-z0-9.-]*|'')
        echo "DOMAIN in .env is empty or invalid." >&2
        exit 1
        ;;
esac

case "$email" in
    *'@'*) ;;
    *)
        echo "LETSENCRYPT_EMAIL in .env is empty or invalid." >&2
        exit 1
        ;;
esac

if [ ! -f "data/certbot/conf/live/$domain/fullchain.pem" ]; then
    docker compose run --rm --entrypoint certbot certbot \
        certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "$email" \
        --agree-tos \
        --no-eff-email \
        --non-interactive \
        -d "$domain" \
        -d "www.$domain"
fi

./deploy/render_nginx.sh https
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
docker compose --profile https up -d certbot

echo "HTTPS is enabled for $domain and automatic renewal is running."
