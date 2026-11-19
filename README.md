# FlowBolt

AI-powered web app builder. The backend is a FastAPI service; the frontend is a Vite/React app.

---

## Prerequisites

| Tool                                        | Purpose                                      |
| ------------------------------------------- | -------------------------------------------- |
| [uv](https://docs.astral.sh/uv/)            | Python package/environment manager (backend) |
| [pnpm](https://pnpm.io/)                    | Node package manager (frontend & mocks)      |
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

Set `AIB_AI_MODEL`, `AIB_AI_BASE_URL` and `AIB_AI_API_KEY`. `backend/.env.example` documents every setting, including provider examples (vLLM, OpenRouter, Ollama, Anthropic, Bedrock) and optional Opik tracing. The default DB values match the Compose Postgres.

## Migrate

```bash
cd backend
uv run --no-sync alembic upgrade head
```

---

## Run (local dev)

Start Postgres, MinIO and the mocks:

```bash
docker compose up -d postgres minio flapi-mock directory-mock
```

Then run the backend and frontend in their own terminals:

| Service  | Command                              | URL                   |
| -------- | ------------------------------------ | --------------------- |
| Backend  | `cd backend && uv run --no-sync dev` | http://localhost:8000 |
| Frontend | `cd frontend && pnpm dev`            | http://localhost:5173 |

API docs: http://localhost:8000/docs

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
