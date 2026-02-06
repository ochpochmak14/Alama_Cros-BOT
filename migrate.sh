#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is not set}"

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
  filename TEXT PRIMARY KEY,
  applied_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
SQL

for f in migrations/*.sql; do
  [ -e "$f" ] || continue
  base="$(basename "$f")"
  applied="$(psql "$DATABASE_URL" -tA -c "SELECT 1 FROM schema_migrations WHERE filename='$base' LIMIT 1;")"
  if [ "$applied" != "1" ]; then
    echo "Applying migration: $base"
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "INSERT INTO schema_migrations(filename) VALUES ('$base');"
  else
    echo "Already applied: $base"
  fi
done
