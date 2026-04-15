.PHONY: dev dev-backend dev-frontend dev-mocks kill-ports build run install stop

# Local dev: mock (flapi-mock), FastAPI, Vite — free these before (re)starting
DEV_PORTS := 4000 8000 5173

# All three at once: backend blocks forever if run sequentially, so we use parallel sub-makes (GNU Make).
# Single service: make dev-backend | make dev-frontend | make dev-mocks
dev:
	+$(MAKE) -j3 dev-backend dev-frontend dev-mocks

ifeq ($(OS),Windows_NT)
# taskkill /T = whole tree; unique PIDs (IPv4+IPv6 duplicate rows); brief sleep so handles drop before uv
kill-ports:
	@powershell -NoProfile -Command "$$ports = @(4000,8000,5173); $$seen = @{}; foreach ($$p in $$ports) { Get-NetTCPConnection -LocalPort $$p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $$id = [int]$$_.OwningProcess; if ($$id -gt 0 -and -not $$seen.ContainsKey($$id)) { $$seen[$$id] = $$true; Write-Host ('Stopping process tree PID ' + $$id + ' (port ' + $$p + ')'); & taskkill /PID $$id /F /T 2>$$null } } }; Start-Sleep -Seconds 2"
else
kill-ports:
	@for port in $(DEV_PORTS); do \
		pids=$$(lsof -ti :$$port 2>/dev/null || true); \
		if [ -n "$$pids" ]; then \
			echo "Stopping PID(s) $$pids on port $$port"; \
			kill -9 $$pids 2>/dev/null || true; \
		fi; \
	done
endif

# --no-sync avoids uv reinstalling entry points (dev.exe) on every run — fixes Windows file-in-use (os error 32)
# Use --app-dir src because backend uses src-layout (flow44 package lives under backend/src).
dev-backend: kill-ports
	cd backend && uv run --no-sync python -m uvicorn --app-dir src flow44.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src/flow44 --log-level info

dev-frontend: kill-ports
	cd frontend && pnpm dev

# server.js lives under mocks/flapi-mock (FLAPI / package mock)
dev-mocks: kill-ports
	cd mocks/flapi-mock && pnpm install && pnpm dev

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
