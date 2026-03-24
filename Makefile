.PHONY: dev dev-backend dev-frontend dev-mocks build run install ruff ruff-all ruff-dry ruff-dry-all ruff-fix mypy mypy-all lint lint-all tests tests-all

ARGS ?= src/

# Development — run backend and frontend separately
dev: dev-backend dev-frontend dev-mocks

dev-backend:
	cd backend && uv run dev

dev-frontend:
	cd frontend && pnpm dev

dev-mocks:
	cd mocks && npm install && pnpm dev

# Install dependencies
install:
	cd frontend && pnpm install
	cd backend && uv sync

# Build Docker image
build:
	docker compose build

# Run via Docker Compose
run:
	docker compose up -d

# Stop containers
stop:
	docker compose down

# Linting & Testing
ruff:
	cd backend && uv run ruff format --config ruff.toml $(ARGS) && uv run ruff check --config ruff.toml $(ARGS)

ruff-all:
	cd backend && uv run ruff format --config ruff.toml src/ && uv run ruff check --config ruff.toml src/

ruff-dry:
	cd backend && uv run ruff format --check --config ruff.toml $(ARGS) && uv run ruff check --no-fix --config ruff.toml $(ARGS)

ruff-dry-all:
	cd backend && uv run ruff format --check --config ruff.toml src/ && uv run ruff check --no-fix --config ruff.toml src/

ruff-fix:
	cd backend && uv run ruff check --fix --config ruff.toml $(ARGS) && uv run ruff format --config ruff.toml $(ARGS)

mypy:
	cd backend && uv run mypy --config-file mypy.toml $(ARGS)

mypy-all:
	cd backend && uv run mypy --config-file mypy.toml src/

lint: mypy-all ruff-all

lint-all: lint

tests:
	cd backend && uv run pytest

tests-all: tests
