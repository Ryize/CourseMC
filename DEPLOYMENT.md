# CourseMC: production deployment

The production stack consists of three Docker Compose services:

- `web`: Django 5.2 under Gunicorn;
- `nginx`: HTTPS termination, reverse proxy, public static and media files;
- `certbot`: automatic Let's Encrypt renewal.

The Django container is not published on the host. Private lesson solutions are
mounted only into `web` and are never exposed by Nginx.

## Server requirements

- Ubuntu server with ports `22`, `80`, and `443` available;
- Docker Engine and the Docker Compose plugin;
- DNS `A` records for `coursemc.ru` and `www.coursemc.ru` pointing to the server.

## First deployment

Clone the repository into `/opt/coursemc`, then create the production
environment file:

```bash
cd /opt/coursemc
cp .env.example .env
chmod 600 .env
```

Fill every required secret in `.env`. Generate `DJANGO_SECRET_KEY` with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

The repository database is copied to persistent storage only when the server
database does not exist. Existing production data is never overwritten:

```bash
./deploy/first_deploy.sh
```

Copy the current `media/` and `private_media/` contents into `data/media/` and
`data/private_media/` before switching DNS.

After both DNS records resolve to the new server, enable HTTPS:

```bash
./deploy/enable_https.sh
```

## Validation and backups

```bash
./deploy/check_production.sh
./deploy/backup_database.sh
docker compose ps
docker compose logs --tail=200 web nginx
```

Backups are stored in `data/backups/`. The entire `data/` directory is ignored
by Git and must be included in an external server backup policy.

## Updating

Create a database backup before every update:

```bash
cd /opt/coursemc
./deploy/backup_database.sh
git pull --ff-only origin master
docker compose up -d --build web nginx
docker compose --profile https up -d certbot
./deploy/check_production.sh
```

Do not copy or commit `.env`, `data/`, `runtime/`, `config.py`, or private SSH
keys.
