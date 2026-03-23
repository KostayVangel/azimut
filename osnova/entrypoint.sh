#!/usr/bin/env sh
set -e

echo "Starting entrypoint script..."

: "${DB_HOST:=postgres-db}"
: "${DB_PORT:=5432}"

echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
while ! nc -z ${DB_HOST} ${DB_PORT}; do
  echo "Waiting for postgres..."
  sleep 1
done

echo "Database available, running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ] && [ -n "${DJANGO_SUPERUSER_EMAIL}" ]; then
  echo "Creating superuser (if not exists)..."
  python manage.py createsuperuser --noinput --username "${DJANGO_SUPERUSER_USERNAME}" --email "${DJANGO_SUPERUSER_EMAIL}" || true
fi

GUNICORN_CMD_ARGS="--bind=0.0.0.0:8000 --workers=${GUNICORN_WORKERS:-3} --log-level=info"
echo "Starting gunicorn: $GUNICORN_CMD_ARGS"
exec gunicorn osnova.wsgi:application $GUNICORN_CMD_ARGS