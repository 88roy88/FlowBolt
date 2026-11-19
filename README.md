# BuildApp

AI-powered web app builder. The backend is a FastAPI service; the frontend is a Vite/React app.

---

## Prerequisites

| Tool                                        | Purpose                                      |
| ------------------------------------------- | -------------------------------------------- |
| [uv](https://docs.astral.sh/uv/)            | Python package/environment manager (backend) |
| [Node.js](https://nodejs.org/) 24           | Frontend & mocks                             |
| [pnpm](https://pnpm.io/) 12                 | Node package manager (frontend & mocks)      |
| [Docker](https://www.docker.com/) + Compose | Postgres / MinIO, full-stack mode            |

---

## Install

```bash
cd backend && uv sync && cd ..
cd frontend && pnpm install && cd ..
```

## Configure

```bash
cp backend/.env.example backend/.env
```

Set `AIB_AI_API_KEY` to your [OpenRouter](https://openrouter.ai/keys) key; the default model is DeepSeek V4.1 Flash. The DB and S3 values already match Compose. `backend/.env.example` also shows other providers (vLLM, Ollama, Anthropic, Bedrock) and Opik tracing; every setting, with its default, is in `backend/src/flow44/config.py`.

---

## Run (local dev)

Start Postgres, MinIO and the mocks:

```bash
docker compose up -d postgres minio flapi-mock directory-mock
```

The first time, and after pulling new migrations, apply them:

```bash
cd backend && uv run --no-sync alembic upgrade head && cd ..
```

Then run the backend and frontend in their own terminals:

| Service  | Command                              | URL                   |
| -------- | ------------------------------------ | --------------------- |
| Backend  | `cd backend && uv run --no-sync dev` | http://localhost:8000 |
| Frontend | `cd frontend && pnpm dev`            | http://localhost:5173 |

API docs: http://localhost:8000/docs

Open http://localhost:5173 and sign in through the mock SSO popup (defaults to `dev-user`). For admin access, add `AIB_SYSTEM_ADMIN_IDS=["dev-user"]` to `backend/.env`.

Working on a mock? Stop its container and run it with hot reload: `cd mocks/<mock> && pnpm install && pnpm dev`.

---

## Docker Compose (full-stack)

```bash
docker compose build
docker compose up -d
docker compose down
```

| Service             | Port(s)    |
| ------------------- | ---------- |
| Frontend (nginx)    | 9999       |
| flapi-mock          | 6001       |
| directory-mock      | 6002       |
| Postgres            | 5432       |
| MinIO API / Console | 9000, 9001 |

A one-shot `migrate` service applies migrations before the backend starts.

---

## Database migrations

Alembic, configured in `backend/alembic.ini`:

```bash
cd backend
uv run --no-sync alembic upgrade head
uv run --no-sync alembic revision --autogenerate -m "describe change"
```

---

## Tests & lint

Backend tests need the Compose Postgres running. Before the first e2e run, install the browser: `cd frontend && pnpm exec playwright install chromium`.

```bash
cd backend
uv run --no-sync task tests      # pytest
uv run --no-sync task lint       # mypy + ruff
```

```bash
cd frontend
pnpm test          # vitest
pnpm test:e2e      # playwright
pnpm lint
pnpm typecheck
```
