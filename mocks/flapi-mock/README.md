# flapi-mock

Development mock server for FLAPI package search/run APIs, legacy Visualis client endpoints, and mock SSO. Used by the FlowBolt backend and frontend during local development.

Default URL: **http://localhost:6001**

---

## Quick start

```bash
pnpm install
pnpm dev          # nodemon with reload
# or
pnpm start        # node server.js (no reload)
```

From the repo root:

```bash
make dev-mocks
```

Smoke test (server must be running):

```bash
pnpm test
# or against another base URL:
node test-mock.js http://localhost:6001
```

---

## API documentation

| Resource | URL |
| -------- | --- |
| Swagger UI | http://localhost:6001/docs |
| OpenAPI JSON | http://localhost:6001/openapi.json |
| OpenAPI source | [`openapi.yaml`](openapi.yaml) |

Update `openapi.yaml` when adding or changing routes, then restart the server.

---

## What it provides

### FLAPI (backend integration)

Used by `FlapiClient` in `backend/src/flow44/integrations/flapi_api.py`.

| Method | Path | Notes |
| ------ | ---- | ----- |
| GET | `/package/v1/search/{partial}` | Autocomplete by name or lookup by numeric ID |
| POST | `/package/{packageId}` | Run package (v1) |
| POST | `/package/v3/{packageId}` | Run package (v3, used by backend) |

Legacy aliases under `/api/flapi/*` call the same handlers.

**Auth:** FLAPI routes require a non-empty `Authorization` header. Any token value is accepted in the mock.

### Client / agent (legacy Visualis)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/config` | Client config (`baseUrl`, `iframeDataEvent`) |
| GET | `/api/models` | Available mock models |
| GET | `/api/libs` | Injectable library catalog |
| POST | `/api/generate` | Generate HTML snippet from cube data |
| POST | `/api/feedback` | Regenerate snippet with feedback |
| POST | `/api/model/prompt` | Mock model prompt assembly |
| GET | `/api/snippets/{runId}.html` | Fetch stored HTML snippet |

### Utility

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/health` | Health check (`{ ok: true, mock: true }`) |
| GET | `/sso` | Mock SSO login page |
| GET | `/libs/*` | Static library assets |

---

## Stub package IDs

POST run endpoints return different cube datasets depending on `packageId`:

| ID | Dataset |
| -- | ------- |
| `1` | Default sales cubes |
| `3` | Intelligence briefing |
| `4` | People & photos |
| `5` | Real-time server dashboard (metrics refresh each call) |
| `6` | People Hebrew names |
| `7` | E-commerce analytics |
| `8` | HR & workforce |
| `9` | Logistics & shipping |
| `10` | Phone devices & specs |
| `11` | Phone call records |
| `12` | Phone repairs & warranty |
| `13` | Phone market analytics |
| other | Default sales cubes |

Stub data lives in [`stubData.js`](stubData.js).

---

## Environment variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `MOCK_PORT` | `6001` | HTTP listen port |
| `BASE_URL` | `http://localhost:{MOCK_PORT}` | Base URL returned in `/api/config` and used for library injection |
| `IFRAME_DATA_EVENT` | `IFRAME_DATA` | PostMessage event name injected into generated HTML |
| `LIBS_ROOT` | `../libs` | Directory served at `/libs` |

---

## FlowBolt integration

**Backend** — set in `backend/.env`:

```env
AIB_FLAPI_BASE_URL=http://localhost:6001
```

**Frontend** — mock SSO in `frontend/.env.development`:

```env
VITE_AUTH_PROVIDER_URL=http://localhost:6001/sso
```

**Docker Compose** — the `flapi-mock` service exposes port `6001` and the backend uses `http://flapi-mock:6001`.

---

## Model mock (OpenAI-compatible)

A separate FastAPI app for deterministic LLM completions in tests:

```
model_mock/
  app.py          # POST /v1/chat/completions, POST /v1/completions
  ...
```

Run locally:

```bash
cd mocks/flapi-mock
uv run uvicorn model_mock.app:app --reload --port 6002
```

Swagger UI: http://localhost:6002/docs

Optional env vars: `MOCK_HTML_RESPONSE`, `MOCK_ECHO_USER=1`.

Python tests:

```bash
cd mocks/flapi-mock
uv run pytest tests/test_model_mock.py
```

---

## Project layout

```
flapi-mock/
  server.js         # Express app
  openapi.yaml      # OpenAPI spec (Swagger source)
  stubData.js       # Cube and search stub data
  errorBody.js      # Standard error response helper
  test-mock.js      # CLI smoke tests
  public/           # Static assets (SSO login page)
  model_mock/       # FastAPI OpenAI-compatible mock
  tests/            # Python tests for model_mock
```

---

## Troubleshooting

**Port already in use (`EADDRINUSE` on 6001)**

```bash
lsof -nP -iTCP:6001 -sTCP:LISTEN
kill <PID>
```

Then restart with `pnpm dev`.

**FLAPI calls return 401**

Send any non-empty `Authorization` header, e.g. `Authorization: Bearer mock-token`.
