.PHONY: dev dev-backend dev-frontend dev-mocks build run run-all clean install

# Development — run backend and frontend separately
dev: dev-backend dev-frontend

dev-backend:
	cd backend && uv run dev

dev-frontend:
	cd frontend && pnpm dev

dev-mocks:
	cd mocks && npm install && node server.js

# Install dependencies
install:
	cd frontend && pnpm install
	cd backend && uv sync

# Build frontend for production
build-frontend:
	cd frontend && pnpm build

# Build Docker image
build:
	docker compose build

# Run via Docker Compose
run:
	docker compose up -d

run-all:
	docker compose up -d --build

# Stop containers
stop:
	docker compose down

# Clean up workspaces and data
clean:
	docker compose down -v
	rm -rf backend/data

# Logs
logs:
	docker compose logs -f app
