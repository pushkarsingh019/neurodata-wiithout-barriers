FROM node:22-slim AS frontend
WORKDIR /app/web-app/frontend
COPY web-app/frontend/package*.json ./
RUN npm ci
COPY web-app/frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8787 \
    NEURODATA_MCP_STORAGE_DIR=/data/.mcp-storage

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY dandi-mcp-server ./dandi-mcp-server
COPY web-app/backend ./web-app/backend
COPY --from=frontend /app/web-app/frontend/dist ./web-app/frontend/dist
RUN uv pip install --system -e ./dandi-mcp-server -e "./web-app/backend[analysis]"

EXPOSE 8787
VOLUME ["/data"]
CMD ["sh", "-c", "uvicorn neurodata_web.main:app --host 0.0.0.0 --port ${PORT:-8787}"]
