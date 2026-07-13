# Forge developer commands. Everything runs from the repo root.

.PHONY: dev dev-down api worker beat web migrate revision test lint fmt seed

dev:            ## start postgres + redis (foreground services run separately)
	docker compose -f infra/docker-compose.yml up -d postgres redis

dev-down:
	docker compose -f infra/docker-compose.yml down

api:            ## run the FastAPI server with reload
	cd backend && uv run uvicorn forge.main:app --reload --port 8000

worker:
	cd backend && uv run celery -A forge.workers.celery_app worker -Q default,ingestion,enrichment,reviews,analytics -l info

beat:
	cd backend && uv run celery -A forge.workers.celery_app beat -l info

web:
	cd frontend && pnpm dev

migrate:        ## apply migrations
	cd backend && uv run alembic upgrade head

revision:       ## create a migration: make revision m="add sources"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .

seed:           ## load demo sources and articles
	cd backend && uv run python -m forge.seed
