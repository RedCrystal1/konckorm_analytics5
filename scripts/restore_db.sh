#!/bin/bash
# Восстановление базы из бэкапа
# Использование: ./scripts/restore_db.sh /app/backups/konckorm_db_20250101_030000.sql.gz

set -euo pipefail

BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Использование: $0 <path_to_backup.sql.gz>"
    echo ""
    echo "Доступные бэкапы:"
    ls -lh "${BACKUP_DIR:-/app/backups}"/*.sql.gz 2>/dev/null || echo "  (нет бэкапов)"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Файл не найден: $BACKUP_FILE"
    exit 1
fi

DB_NAME="${DB_NAME:-konckorm_db}"
DB_USER="${DB_USER:-konckorm}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"

echo "⚠️  ВНИМАНИЕ: база ${DB_NAME} будет полностью перезаписана!"
echo "Файл: $BACKUP_FILE"
read -p "Продолжить? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Отменено."
    exit 0
fi

echo "[$(date)] Восстановление из $BACKUP_FILE..."

# Завершаем активные соединения
PGPASSWORD="${DB_PASSWORD}" psql \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" \
    2>/dev/null || true

# Пересоздаём базу
PGPASSWORD="${DB_PASSWORD}" psql \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS ${DB_NAME};" \
    -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

# Восстанавливаем
gunzip -c "$BACKUP_FILE" | PGPASSWORD="${DB_PASSWORD}" psql \
    -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --quiet

echo "[$(date)] Восстановление завершено."
echo "Не забудьте выполнить: python manage.py migrate"
