#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $# == 2 && "$2" == --confirm-overwrite ]] || { echo 'Usage: bash deploy/restore.sh backups/file.dump --confirm-overwrite'; exit 1; }
[[ -f "$1" ]] || { echo 'Backup not found'; exit 1; }
docker compose stop web
trap 'docker compose start web' EXIT
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --single-transaction' < "$1"
