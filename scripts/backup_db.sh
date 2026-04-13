#!/bin/bash
# Скрипт резервного копирования PostgreSQL
# Использование: ./scripts/backup_db.sh
# Crontab: 0 3 * * * /app/scripts/backup_db.sh >> /var/log/backup.log 2>&1

set -euo pipefail

# ── Настройки ──
BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
DB_NAME="${DB_NAME:-konckorm_db}"
DB_USER="${DB_USER:-konckorm}"
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Начало бэкапа базы ${DB_NAME}..."

# Дамп + gzip
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=plain \
    --no-owner \
    --no-privileges \
    --verbose \
    2>/dev/null | gzip > "$BACKUP_FILE"

FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Бэкап создан: $BACKUP_FILE ($FILESIZE)"

# Удаляем старые бэкапы
DELETED=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +${RETENTION_DAYS} -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date)] Удалено старых бэкапов: $DELETED (старше $RETENTION_DAYS дней)"
fi

# Проверка целостности
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "[$(date)] Проверка целостности: OK"
else
    echo "[$(date)] ОШИБКА: бэкап повреждён!"
    exit 1
fi

echo "[$(date)] Бэкап завершён успешно."
