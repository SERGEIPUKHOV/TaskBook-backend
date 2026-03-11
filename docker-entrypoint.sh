#!/bin/sh
set -eu

if [ "${SKIP_BOOTSTRAP:-0}" != "1" ]; then
  python -m app.bootstrap_db
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ -n "${GUNICORN_WORKERS:-}" ]; then
  workers="$GUNICORN_WORKERS"
else
  cores="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)"
  workers=$((cores * 2 + 1))
fi

exec gunicorn app.main:app \
  --workers "$workers" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout "${GUNICORN_TIMEOUT:-30}" \
  --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
  --access-logfile - \
  --error-logfile -
