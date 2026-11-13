#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo 'Create .env from .env.example first'; exit 1; }
if grep -Eq 'replace-with|rental.example.com' .env; then echo 'Replace example values in .env first'; exit 1; fi
chmod 600 .env
docker compose config --quiet
docker compose build --pull
docker compose up -d db
# compose waits for PostgreSQL health before running app commands.
docker compose run --rm web python manage.py migrate --noinput
# Named volumes may be owned by root. Only static collection runs as root; Gunicorn remains unprivileged.
docker compose run --rm --user root web python manage.py collectstatic --noinput
docker compose up -d --remove-orphans
docker compose exec -T web python manage.py check --deploy
echo 'Deployed. First run: docker compose exec web python manage.py createsuperuser'
