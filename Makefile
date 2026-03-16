.PHONY: dev dev-backend dev-frontend build run clean install

# Development — run backend and frontend separately
dev: dev-backend dev-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && pnpm dev

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
