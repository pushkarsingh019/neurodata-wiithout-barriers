from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from neurodata_web.config import load_config
from neurodata_web.llm import LocalLLMClient
from neurodata_web.provider_service import MultiProviderWebService, cached_skill_dir, normalize_dataset_id, normalize_provider
from neurodata_web.schemas import (
    DatasetResolveRequest,
    DatasetResolveResponse,
    DownloadSampleRequest,
    DownloadSampleResponse,
    IndexLocalRequest,
    IndexLocalResponse,
    SkillPrepareResponse,
    SkillStatusResponse,
    VariableExplainRequest,
    VariableExplainResponse,
    VariableInventory,
)


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
def service() -> MultiProviderWebService:
    config = load_config()
    llm = LocalLLMClient(config)
    return MultiProviderWebService(config, llm)


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
    return get_dataset("dandi", dandiset_id, version=version)


@app.get("/api/{provider}/{dataset_id}")
def get_dataset(provider: str, dataset_id: str, version: str = "draft") -> object:
    try:
        return service().dataset_page(normalize_provider(provider), dataset_id, version=version)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/dandi/{dandiset_id}/variables", response_model=VariableInventory)
def get_variables(dandiset_id: str, version: str = "draft") -> VariableInventory:
    return get_provider_variables("dandi", dandiset_id, version=version)


@app.get("/api/{provider}/{dataset_id}/variables", response_model=VariableInventory)
def get_provider_variables(provider: str, dataset_id: str, version: str = "draft") -> VariableInventory:
    try:
        return service().variables(normalize_provider(provider), dataset_id, version=version)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/dandi/{dandiset_id}/variables/explain", response_model=VariableExplainResponse)
def explain_variable(dandiset_id: str, payload: VariableExplainRequest) -> VariableExplainResponse:
    return explain_provider_variable("dandi", dandiset_id, payload)


@app.post("/api/{provider}/{dataset_id}/variables/explain", response_model=VariableExplainResponse)
def explain_provider_variable(provider: str, dataset_id: str, payload: VariableExplainRequest) -> VariableExplainResponse:
    try:
        return service().explain_variable(
            provider=normalize_provider(provider),
            dataset_id=dataset_id,
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
    return index_provider_local("dandi", dandiset_id, payload)


@app.post("/api/{provider}/{dataset_id}/index-local", response_model=IndexLocalResponse)
def index_provider_local(provider: str, dataset_id: str, payload: IndexLocalRequest) -> IndexLocalResponse:
    try:
        return service().index_local(
            provider=normalize_provider(provider),
            path=payload.path,
            dataset_id=payload.dandiset_id or dataset_id,
            version=payload.version,
            inspect_limit=payload.inspect_limit,
        )
    except Exception as exc:
        return IndexLocalResponse(status="error", message=str(exc))


@app.post("/api/dandi/{dandiset_id}/download-sample", response_model=DownloadSampleResponse)
def download_sample(dandiset_id: str, payload: DownloadSampleRequest) -> DownloadSampleResponse:
    return service().dandi.download_sample(
        dandiset_id,
        version=payload.version,
        max_assets=payload.max_assets,
        max_bytes=payload.max_bytes,
    )


@app.get("/api/dandi/{dandiset_id}/skill-status", response_model=SkillStatusResponse)
def skill_status(dandiset_id: str, version: str = "draft") -> SkillStatusResponse:
    return provider_skill_status("dandi", dandiset_id, version=version)


@app.get("/api/{provider}/{dataset_id}/skill-status", response_model=SkillStatusResponse)
def provider_skill_status(provider: str, dataset_id: str, version: str = "draft") -> SkillStatusResponse:
    try:
        return service().skill_status(normalize_provider(provider), dataset_id, version=version)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/dandi/{dandiset_id}/skill-prepare", response_model=SkillPrepareResponse)
def prepare_skill(dandiset_id: str, version: str = "draft") -> SkillPrepareResponse:
    return provider_prepare_skill("dandi", dandiset_id, version=version)


@app.post("/api/{provider}/{dataset_id}/skill-prepare", response_model=SkillPrepareResponse)
def provider_prepare_skill(provider: str, dataset_id: str, version: str = "draft") -> SkillPrepareResponse:
    try:
        return service().prepare_skill_context(normalize_provider(provider), dataset_id, version=version)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/dandi/{dandiset_id}/skill.zip")
def download_skill(dandiset_id: str) -> FileResponse:
    return provider_download_skill("dandi", dandiset_id)


@app.get("/api/{provider}/{dataset_id}/skill.zip")
def provider_download_skill(provider: str, dataset_id: str) -> FileResponse:
    normalized_provider = normalize_provider(provider)
    normalized_id = normalize_dataset_id(normalized_provider, dataset_id)
    filename = f"{normalized_provider}-{normalized_id}-skill.zip"
    path = cached_skill_dir() / filename
    if not path.is_file():
        try:
            path = service().write_skill_zip(normalized_provider, normalized_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"Cached skill download is not available yet: {exc}") from exc
    return FileResponse(path, media_type="application/zip", filename=filename)


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
