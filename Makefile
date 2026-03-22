.PHONY: dev dev-backend dev-frontend dev-mocks build run install

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
