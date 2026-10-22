#!/bin/sh
# Container entrypoint: migrate, seed demo data once, then run Django (private) and Next (public).
set -e
APP_DIR="${APP_DIR:-/app}"

cd "$APP_DIR/backend"
python manage.py migrate --noinput
if [ "${SEED_DEMO:-true}" = "true" ]; then
  python manage.py seed_demo
fi

# --timeout covers slow video uploads relayed by Next (see next.config.ts proxyTimeout).
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 180 --access-logfile - &
DJANGO_PID=$!

cd "$APP_DIR/web"
HOSTNAME=0.0.0.0 PORT="${PORT:-10000}" node server.js &
NEXT_PID=$!

# If either process dies, stop the container so the platform restarts it.
while kill -0 "$DJANGO_PID" 2>/dev/null && kill -0 "$NEXT_PID" 2>/dev/null; do sleep 5; done
echo "A server process exited; shutting down." >&2
kill "$DJANGO_PID" "$NEXT_PID" 2>/dev/null || true
exit 1
