# Neurodata Without Barriers Web App

Lightweight React + FastAPI app for turning DANDI links into interactive dataset pages. The repository does not ship DANDI datasets or NWB files; users can resolve public DANDI IDs from the archive, download a small sample through the UI, or index their own local data path at runtime.

## Fastest Hosted Path

Build and run the single-container app:

```bash
cp web-app/.env.example web-app/.env
docker compose -f docker-compose.web.yml up --build
```

Open `http://127.0.0.1:8787`. The container serves the built React frontend and the FastAPI backend from the same origin, stores cache/index data in a Docker volume, and does not require local datasets in the repo.

The hosted app also includes a documentation screen at `/docs` with the suite map, hosting notes, local development commands, and data-handling policy.

## Runtime Configuration

The app can use any OpenAI-compatible local or hosted model endpoint. AI summaries gracefully show as unavailable when no model server is configured.

```bash
NEURODATA_LLM_BASE_URL=http://127.0.0.1:8001/v1
NEURODATA_LLM_MODEL=
DANDI_API_TOKEN=
NEURODATA_CORS_ORIGINS=*
NEURODATA_MCP_STORAGE_DIR=/data/.mcp-storage
```

For split hosting, build the frontend with `VITE_API_BASE_URL=https://your-api-host` and set `NEURODATA_CORS_ORIGINS` on the backend to the frontend origin.

## Local Development

Start the API:

```bash
cd web-app/backend
uv run --extra analysis uvicorn neurodata_web.main:app --reload --host 127.0.0.1 --port 8787
```

Start the frontend:

```bash
cd web-app/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

For frontend-only split hosting, build with:

```bash
VITE_API_BASE_URL=https://your-api-host npm run build
```

## Data Handling

Keep local NWB files, downloaded DANDI samples, generated figures, and session recordings outside git. The app writes derived manifests and indexes to `NEURODATA_MCP_STORAGE_DIR`; those cache files are runtime state and are ignored by the repository.
