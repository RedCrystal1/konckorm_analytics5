# КонцКорма.Аналитика

Облачная платформа учёта взаиморасчётов с поставщиками для АО «Концкорма».

## Быстрый старт (разработка)

```bash
# 1. Клонировать репозиторий
git clone <repo-url> && cd konckorm_analytics

# 2. Виртуальное окружение
python -m venv .venv && source .venv/bin/activate

# 3. Зависимости
pip install -r requirements/dev.txt

# 4. Настройки
export DJANGO_SETTINGS_MODULE=config.settings.dev

# 5. Миграции и суперпользователь
make migrate
make createsuperuser

# 6. Запуск
make run
```

## Запуск через Docker

```bash
cp .env.example .env   # отредактируйте параметры
make docker-up
```

## Стек

- **Backend:** Python 3.12, Django 5.1, PostgreSQL 16, Redis 7, Celery 5.4
- **Frontend:** Django Templates, HTMX 2.0, Alpine.js 3, Bootstrap 5.3, Chart.js 4
- **Инфраструктура:** Docker, Nginx, Gunicorn

## Структура

```
apps/
├── accounts/        # Пользователи, роли, 2FA, аудит
├── dashboard/       # Главная страница, KPI-карточки
├── counterparties/  # Контрагенты и договоры
├── directories/     # Справочники (номенклатура, подразделения)
├── documents/       # Первичные документы
├── registers/       # Регистры накопления
├── analytics/       # Аналитика и KPI
├── payments/        # Платёжный календарь
├── reconciliation/  # Сверки с контрагентами
├── reports/         # Генерация отчётов (Excel/PDF)
├── data_import/     # Импорт из XML/Excel
└── notifications/   # Уведомления (in-app + email)
```

## Команды

| Команда | Описание |
|---------|----------|
| `make run` | Dev-сервер |
| `make migrate` | Миграции |
| `make test` | Тесты |
| `make lint` | Линтинг |
| `make celery` | Celery worker |
| `make docker-up` | Docker запуск |
