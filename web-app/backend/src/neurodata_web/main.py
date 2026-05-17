from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from neurodata_web.config import load_config
from neurodata_web.dandi_service import DandiWebService, parse_dandi_id
from neurodata_web.llm import LocalLLMClient
from neurodata_web.schemas import (
    DatasetResolveRequest,
    DatasetResolveResponse,
    DownloadSampleRequest,
    DownloadSampleResponse,
    IndexLocalRequest,
    IndexLocalResponse,
    VariableExplainRequest,
    VariableExplainResponse,
    VariableInventory,
)
from neurodata_web.skill_export import build_skill_zip


app = FastAPI(title="Neurodata Without Barriers API", version="0.1.0")
config = load_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def service() -> DandiWebService:
    config = load_config()
    llm = LocalLLMClient(config)
    return DandiWebService(config, llm)


@app.get("/api/health")
def health() -> dict[str, object]:
    config = load_config()
    return {
        "status": "ok",
        "llm": LocalLLMClient(config).health(),
        "storage_dir": str(config.storage_dir),
    }


@app.post("/api/datasets/resolve", response_model=DatasetResolveResponse)
def resolve_dataset(payload: DatasetResolveRequest) -> DatasetResolveResponse:
    try:
        return service().resolve(payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/dandi/{dandiset_id}")
def get_dandiset(dandiset_id: str, version: str = "draft") -> object:
    try:
        return service().dataset_page(dandiset_id, version=version)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/dandi/{dandiset_id}/variables", response_model=VariableInventory)
def get_variables(dandiset_id: str, version: str = "draft") -> VariableInventory:
    try:
        return service().variables(dandiset_id, version=version)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/dandi/{dandiset_id}/variables/explain", response_model=VariableExplainResponse)
def explain_variable(dandiset_id: str, payload: VariableExplainRequest) -> VariableExplainResponse:
    try:
        return service().explain_variable(
            dataset_id=dandiset_id,
            variable=payload.variable,
            file_path=payload.file_path,
            object_path=payload.object_path,
            context=payload.context,
            version=payload.version,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/dandi/{dandiset_id}/index-local", response_model=IndexLocalResponse)
def index_local(dandiset_id: str, payload: IndexLocalRequest) -> IndexLocalResponse:
    try:
        return service().index_local(
            path=payload.path,
            dandiset_id=payload.dandiset_id or parse_dandi_id(dandiset_id),
            version=payload.version,
            inspect_limit=payload.inspect_limit,
        )
    except Exception as exc:
        return IndexLocalResponse(status="error", message=str(exc))


@app.post("/api/dandi/{dandiset_id}/download-sample", response_model=DownloadSampleResponse)
def download_sample(dandiset_id: str, payload: DownloadSampleRequest) -> DownloadSampleResponse:
    return service().download_sample(
        dandiset_id,
        version=payload.version,
        max_assets=payload.max_assets,
        max_bytes=payload.max_bytes,
    )


@app.get("/api/dandi/{dandiset_id}/skill.zip")
def download_skill(dandiset_id: str, version: str = "draft") -> Response:
    try:
        context = service().skill_context(dandiset_id, version=version)
        content = build_skill_zip(
            dataset_id=parse_dandi_id(dandiset_id),
            summary=context["summary"],
            variables=context["variables"],
            papers=context["papers"],
            overview=context["overview"],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    filename = f"dandi-{parse_dandi_id(dandiset_id)}-skill.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def frontend_dist_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "web-app" / "frontend" / "dist"


dist_dir = frontend_dist_dir()
if dist_dir.exists():
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def serve_frontend(path: str) -> FileResponse:
        candidate = dist_dir / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist_dir / "index.html")


def run() -> None:
    runtime = load_config()
    uvicorn.run("neurodata_web.main:app", host=runtime.host, port=runtime.port, reload=False)


if __name__ == "__main__":
    run()
