#!/bin/sh
# Apply database migrations, then start the API. Safe to run on every start: Alembic only applies
# what is missing. (With several replicas, run migrations as a separate one-off step instead.)
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting GamePulse API on port ${PORT:-8000}"
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
  --no-server-header
