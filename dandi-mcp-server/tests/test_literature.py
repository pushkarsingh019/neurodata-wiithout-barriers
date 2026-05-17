from __future__ import annotations

import httpx

from dandi_mcp.storage import MCPStorage, StorageConfig
from neurodata_literature import LiteratureService, build_dataset_explorer_html


def test_literature_service_resolves_doi_with_real_client_shape(monkeypatch, tmp_path) -> None:
    storage = MCPStorage(StorageConfig(provider="dandi", root_dir=tmp_path))
    service = LiteratureService(storage, "dandi")

    def fake_get(url: str, **kwargs):
        request = httpx.Request("GET", url)
        if "semanticscholar" in url:
            return httpx.Response(
                200,
                request=request,
                json={
                    "paperId": "abc",
                    "externalIds": {"DOI": "10.1234/example", "PubMed": "123"},
                    "title": "Example task paper",
                    "authors": [{"name": "Ada Lovelace"}],
                    "year": 2024,
                    "abstract": "A behavioral task with choice variables.",
                    "openAccessPdf": {"url": "https://example.test/paper.pdf"},
                },
            )
        return httpx.Response(404, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)

    result = service.resolve_papers("000001", ["https://doi.org/10.1234/example"])

    assert result["papers"][0]["doi"] == "10.1234/example"
    assert result["papers"][0]["pdf_url"] == "https://example.test/paper.pdf"
    assert "semantic_scholar" in result["papers"][0]["sources"]


def test_explain_variable_reports_missing_pdf_when_full_text_needed(monkeypatch, tmp_path) -> None:
    storage = MCPStorage(StorageConfig(provider="dandi", root_dir=tmp_path))
    service = LiteratureService(storage, "dandi")
    hints = [{"title": "Choice behavior paper", "url": "https://example.test/paper"}]
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, *args, **kwargs: httpx.Response(404, request=httpx.Request("GET", url)),
    )

    result = service.explain_variable(
        dataset_id="000001",
        variable="choice",
        variable_context={"name": "choice", "kind": "trials_column"},
        paper_hints=hints,
        full_text_policy="always",
    )

    assert result["status"] == "pdf_required_but_missing"
    assert result["missing_pdfs"]
    assert "register_paper_pdf" in result["missing_pdfs"][0]["registration_call"]


def test_dataset_explorer_html_embeds_variables_and_tool_call() -> None:
    html = build_dataset_explorer_html(
        provider="dandi",
        dataset_id="000001",
        title="Example dataset",
        summary={"subjects": ["sub-01"]},
        variables=[{"name": "choice", "file": "sub-01.nwb", "confidence_label": "low"}],
        papers=[{"title": "Example paper", "doi": "10.1234/example"}],
    )

    assert "Example dataset" in html
    assert "choice" in html
    assert "explain_dataset_variable" in html
