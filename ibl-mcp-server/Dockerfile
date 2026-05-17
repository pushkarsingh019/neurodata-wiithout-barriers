FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV IBL_ALYX_BASE_URL=https://openalyx.internationalbrainlab.org
ENV IBL_MCP_DOWNLOAD_DIR=/data/downloads

VOLUME ["/data"]

CMD ["ibl-mcp"]
