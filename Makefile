.PHONY: help run migrate seed test lint format celery beat docker-up docker-down docker-logs

help:           ## Показать справку
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

run:            ## Запустить dev-сервер
	python manage.py runserver

migrate:        ## Создать и применить миграции
	python manage.py makemigrations
	python manage.py migrate

seed:           ## Загрузить демо-данные
	python manage.py loaddata fixtures/roles.json

test:           ## Запустить тесты
	pytest --cov=apps --cov-report=term-missing

lint:           ## Проверить код
	ruff check apps/
	black --check apps/

format:         ## Отформатировать код
	black apps/
	ruff check --fix apps/

celery:         ## Запустить Celery worker
	celery -A config worker -l info

beat:           ## Запустить Celery Beat
	celery -A config beat -l info

docker-up:      ## Запустить всё через Docker
	cd docker && docker compose up -d --build

docker-down:    ## Остановить Docker
	cd docker && docker compose down

docker-logs:    ## Логи Docker
	cd docker && docker compose logs -f web celery_worker

createsuperuser: ## Создать суперпользователя
	python manage.py createsuperuser
