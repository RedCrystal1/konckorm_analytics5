#!/bin/bash
set -e

echo "Waiting for database..."
while ! python -c "
import os, psycopg2
psycopg2.connect(
    dbname=os.environ.get('DB_NAME','konckorm_db'),
    user=os.environ.get('DB_USER','konckorm'),
    password=os.environ.get('DB_PASSWORD',''),
    host=os.environ.get('DB_HOST','db'),
    port=os.environ.get('DB_PORT','5432'),
    connect_timeout=5
)
" 2>/dev/null; do
    echo "Database not ready, retrying in 2s..."
    sleep 2
done
echo "Database is ready."

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@"
