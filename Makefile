.PHONY: dev dev-backend dev-frontend dev-mocks kill-ports build run install stop

# Local dev: mock (flapi-mock), FastAPI, Vite — free these before (re)starting
DEV_PORT_LEGACY := 4000
DEV_PORT_BACKEND := 8000
DEV_PORT_FRONTEND := 5173
DEV_PORT_MOCKS := 6001
DEV_PORTS := $(DEV_PORT_LEGACY) $(DEV_PORT_BACKEND) $(DEV_PORT_FRONTEND) $(DEV_PORT_MOCKS)

# All three at once: backend blocks forever if run sequentially, so we use parallel sub-makes (GNU Make).
# Single service: make dev-backend | make dev-frontend | make dev-mocks
dev: kill-ports
	+$(MAKE) -j3 dev-backend dev-frontend dev-mocks

ifeq ($(OS),Windows_NT)
kill-ports:
	@$(MAKE) -s kill-port-$(DEV_PORT_LEGACY) kill-port-$(DEV_PORT_BACKEND) kill-port-$(DEV_PORT_FRONTEND) kill-port-$(DEV_PORT_MOCKS)

kill-port-%:
	@powershell -NoProfile -Command "$$p = $*; $$seen = @{}; Get-NetTCPConnection -LocalPort $$p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $$id = [int]$$_.OwningProcess; if ($$id -gt 0 -and -not $$seen.ContainsKey($$id)) { $$seen[$$id] = $$true; Write-Host ('Stopping process tree PID ' + $$id + ' (port ' + $$p + ')'); & taskkill /PID $$id /F /T 2>$$null } }"
else
kill-ports:
	@for port in $(DEV_PORTS); do \
		$(MAKE) -s kill-port-$$port; \
	done

kill-port-%:
	@pids=$$(lsof -ti :$* 2>/dev/null || true); \
	if [ -n "$$pids" ]; then \
		echo "Stopping PID(s) $$pids on port $*"; \
		kill -9 $$pids 2>/dev/null || true; \
	fi
endif

# --no-sync avoids uv reinstalling entry points (dev.exe) on every run — fixes Windows file-in-use (os error 32)
# Use --app-dir src because backend uses src-layout (flow44 package lives under backend/src).
dev-backend: kill-port-$(DEV_PORT_BACKEND)
	cd backend && uv run --no-sync python -m uvicorn --app-dir src flow44.main:app --host 0.0.0.0 --port $(DEV_PORT_BACKEND) --reload --reload-dir src/flow44 --reload-exclude '**/__pycache__/**' --reload-exclude '**/*.pyc' --log-level info

dev-frontend: kill-port-$(DEV_PORT_FRONTEND)
	cd frontend && pnpm dev -- --port $(DEV_PORT_FRONTEND)

# server.js lives under mocks/flapi-mock (FLAPI / package mock)
dev-mocks: kill-port-$(DEV_PORT_MOCKS)
	cd mocks/flapi-mock && pnpm install && MOCK_PORT=$(DEV_PORT_MOCKS) pnpm dev

# Install dependencies (also installs Husky git hooks)
install:
	pnpm install
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
