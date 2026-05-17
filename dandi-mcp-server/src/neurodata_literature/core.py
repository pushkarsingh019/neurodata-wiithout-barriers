from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import textwrap
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlparse

import httpx


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
PMID_RE = re.compile(r"\bPMID[:\s]+(\d+)\b", re.IGNORECASE)
PMCID_RE = re.compile(r"\bPMC\d+\b", re.IGNORECASE)
ARXIV_RE = re.compile(r"\barxiv[:\s/]+(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+\-.]*", re.IGNORECASE)


@dataclass
class PaperRecord:
    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    arxiv_id: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    abstract: str | None = None
    venue: str | None = None
    open_access: bool = False
    sources: list[str] = field(default_factory=list)
    relationship: str = "related"
    confidence_score: float = 0.0


@dataclass
class EvidenceItem:
    source_type: str
    source_id: str
    title: str
    quote: str
    score: float
    supports: str = "unknown"
    page: int | None = None
    section: str | None = None


@dataclass
class MissingPdf:
    title: str
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    arxiv_id: str | None = None
    landing_page_url: str | None = None
    known_pdf_candidates: list[str] = field(default_factory=list)
    failed_pdf_candidates: list[dict[str, str]] = field(default_factory=list)
    why_needed: str = ""
    suggested_filename: str = ""
    registration_call: str = ""


class LiteratureService:
    """Real API-backed literature helper for neurodata MCP servers.

    The service is intentionally model-free. It resolves papers, retrieves/caches
    evidence, and reports uncertainty so the calling agent can synthesize prose.
    """

    def __init__(self, storage: Any, provider: str) -> None:
        self.storage = storage
        self.provider = provider
        self.cache_dir = storage.config.provider_dir / "literature"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir = self.cache_dir / "pdfs"
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.contact_email = os.getenv("NEURODATA_LITERATURE_CONTACT_EMAIL", "")
        self.semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
        self.ncbi_api_key = os.getenv("NCBI_API_KEY", "")
        self.max_pdf_mb = int(os.getenv("NEURODATA_LITERATURE_MAX_PDF_MB", "100"))

    def resolve_papers(
        self,
        dataset_id: str,
        paper_hints: Iterable[dict[str, Any] | str],
        *,
        limit: int = 10,
        relationship: str = "related",
    ) -> dict[str, Any]:
        records: list[PaperRecord] = []
        errors: list[dict[str, str]] = []
        for hint in paper_hints:
            try:
                records.extend(self._resolve_hint(hint, relationship=relationship))
            except Exception as exc:
                errors.append({"hint": str(hint), "error": str(exc)})
        papers = self._dedupe(records)[: max(limit, 0)]
        payload = {
            "dataset_id": dataset_id,
            "papers": [asdict(paper) for paper in papers],
            "errors": errors,
            "provenance": _provenance("real_api_resolution", [src for p in papers for src in p.sources]),
        }
        self.storage.upsert_record("dataset_papers", dataset_id, payload, source="neurodata_literature")
        for paper in papers:
            self.storage.upsert_record("paper", paper.paper_id, asdict(paper), source="neurodata_literature")
        return payload

    def explain_variable(
        self,
        *,
        dataset_id: str,
        variable: str,
        variable_context: dict[str, Any],
        paper_hints: Iterable[dict[str, Any] | str],
        full_text_policy: str = "auto",
        question: str | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        papers_payload = self.resolve_papers(dataset_id, paper_hints, limit=10)
        papers = [PaperRecord(**paper) for paper in papers_payload["papers"]]
        local_evidence = self._local_evidence(dataset_id, variable, variable_context, question=question)
        paper_evidence = self._paper_metadata_evidence(variable, variable_context, papers, question=question)
        evidence = sorted(local_evidence + paper_evidence, key=lambda item: item.score, reverse=True)
        confidence, reasons = self._confidence(variable, variable_context, evidence)
        full_text_used = False
        missing_pdfs: list[MissingPdf] = []

        if self._should_use_full_text(confidence, evidence, variable, full_text_policy):
            pdf_evidence, missing_pdfs = self._full_text_evidence(
                dataset_id,
                variable,
                variable_context,
                papers,
                question=question,
                limit=limit,
            )
            if pdf_evidence:
                full_text_used = True
                evidence = sorted(evidence + pdf_evidence, key=lambda item: item.score, reverse=True)
                confidence, reasons = self._confidence(variable, variable_context, evidence)

        status = "answered" if confidence >= 0.65 else "low_confidence"
        if not papers:
            status = "no_papers_found"
        elif missing_pdfs and confidence < 0.65:
            status = "pdf_required_but_missing"

        interpretation = self._interpretation(variable, variable_context, evidence, confidence)
        experiment_context = self._experiment_context(variable_context, evidence)
        result = {
            "status": status,
            "variable": variable,
            "interpretation": interpretation,
            "experiment_context": experiment_context,
            "variable_context": variable_context,
            "evidence": [asdict(item) for item in evidence[:limit]],
            "papers": [asdict(item) for item in papers],
            "confidence_score": round(confidence, 3),
            "confidence_label": _confidence_label(confidence),
            "uncertainty_reasons": reasons,
            "full_text_used": full_text_used,
            "missing_pdfs": [asdict(item) for item in missing_pdfs],
            "next_actions": self._next_actions(dataset_id, status, missing_pdfs),
        }
        self.storage.upsert_record(
            "variable_explanation",
            stable_variable_id(dataset_id, variable_context, variable),
            result,
            source="neurodata_literature",
        )
        return result

    def query_papers(
        self,
        *,
        dataset_id: str,
        question: str,
        paper_hints: Iterable[dict[str, Any] | str],
        dataset_context: dict[str, Any] | None = None,
        full_text_policy: str = "auto",
        limit: int = 8,
    ) -> dict[str, Any]:
        context = dataset_context or {}
        return self.explain_variable(
            dataset_id=dataset_id,
            variable=question,
            variable_context={"kind": "dataset_question", **context},
            paper_hints=paper_hints,
            full_text_policy=full_text_policy,
            question=question,
            limit=limit,
        )

    def register_pdf(
        self,
        *,
        dataset_id: str,
        pdf_path: str,
        doi: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        path = Path(pdf_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"PDF path does not exist: {path}")
        head = path.read_bytes()[:5]
        if head != b"%PDF-":
            raise ValueError(f"File does not look like a PDF: {path}")
        pages = extract_pdf_pages(path)
        text = "\n".join(pages[:5])
        found_doi = doi or _extract_doi(text)
        found_title = title or _guess_title(path, pages)
        paper = PaperRecord(
            paper_id=_paper_id(found_doi or found_title or str(path)),
            title=found_title or path.stem,
            doi=found_doi,
            sources=["user_pdf"],
            relationship="user_registered",
            confidence_score=0.95 if found_doi else 0.75,
        )
        chunks = _chunk_pages(paper, pages, source=str(path))
        target = self.pdf_dir / f"{paper.paper_id}.pdf"
        if target != path:
            target.write_bytes(path.read_bytes())
        payload = {
            "status": "registered",
            "dataset_id": dataset_id,
            "paper": asdict(paper),
            "pdf_path": str(target),
            "page_count": len(pages),
            "chunk_count": len(chunks),
            "matched_existing_paper": bool(found_doi),
            "confidence_score": paper.confidence_score,
        }
        self.storage.upsert_record("paper", paper.paper_id, asdict(paper), source="user_pdf")
        self.storage.upsert_record("paper_pdf", paper.paper_id, payload, source="user_pdf")
        self._store_chunks(paper.paper_id, chunks)
        self.storage.upsert_record("dataset_paper", f"{dataset_id}:{paper.paper_id}", {"dataset_id": dataset_id, "paper": asdict(paper)}, source="user_pdf")
        return payload

    def list_missing_pdfs(self, dataset_id: str) -> dict[str, Any]:
        rows = self._records("missing_pdf_request")
        missing = [row["payload"] for row in rows if row["payload"].get("dataset_id") == dataset_id]
        return {"dataset_id": dataset_id, "missing_pdfs": missing}

    def _resolve_hint(self, hint: dict[str, Any] | str, *, relationship: str) -> list[PaperRecord]:
        text = json.dumps(hint, sort_keys=True, default=str) if isinstance(hint, dict) else str(hint)
        doi = _extract_doi(text)
        pmid = _extract_pmid(text)
        arxiv_id = _extract_arxiv(text)
        url = _extract_url(text)
        title = _extract_title_hint(hint)

        records = []
        if doi:
            records.extend(
                paper
                for paper in [
                    self._semantic_scholar_by_id(f"DOI:{doi}"),
                    self._crossref_by_doi(doi),
                    self._openalex_by_doi(doi),
                    self._datacite_by_doi(doi),
                    self._europe_pmc_by_query(f'DOI:"{doi}"'),
                ]
                if paper
            )
        if pmid:
            records.extend(paper for paper in [self._pubmed_by_pmid(pmid), self._europe_pmc_by_query(f"EXT_ID:{pmid}")] if paper)
        if arxiv_id:
            records.extend(paper for paper in [self._arxiv_by_id(arxiv_id), self._semantic_scholar_by_id(f"ARXIV:{arxiv_id}")] if paper)
        if title and not records:
            records.extend(
                paper
                for paper in [
                    self._semantic_scholar_search(title),
                    self._crossref_search(title),
                    self._openalex_search(title),
                    self._pubmed_search(title),
                    self._europe_pmc_by_query(title),
                ]
                if paper
            )
        if url and not records:
            records.append(PaperRecord(paper_id=_paper_id(url), title=title or url, url=url, sources=["metadata_url"], relationship=relationship, confidence_score=0.45))
        for record in records:
            record.relationship = record.relationship or relationship
        return records

    def _semantic_scholar_by_id(self, paper_id: str) -> PaperRecord | None:
        fields = "paperId,externalIds,url,title,venue,year,abstract,citationCount,referenceCount,publicationDate,authors,openAccessPdf,fieldsOfStudy,tldr"
        data = self._get_json(f"https://api.semanticscholar.org/graph/v1/paper/{quote(paper_id, safe=':')}", params={"fields": fields}, source="semantic_scholar")
        return self._parse_semantic_scholar(data) if data else None

    def _semantic_scholar_search(self, query: str) -> PaperRecord | None:
        fields = "paperId,externalIds,url,title,venue,year,abstract,citationCount,referenceCount,publicationDate,authors,openAccessPdf,fieldsOfStudy,tldr"
        data = self._get_json("https://api.semanticscholar.org/graph/v1/paper/search", params={"query": query, "limit": 1, "fields": fields}, source="semantic_scholar")
        rows = data.get("data") if data else []
        return self._parse_semantic_scholar(rows[0]) if rows else None

    def _parse_semantic_scholar(self, data: dict[str, Any]) -> PaperRecord | None:
        title = data.get("title")
        if not title:
            return None
        external = data.get("externalIds") or {}
        oa = data.get("openAccessPdf") or {}
        tldr = data.get("tldr") or {}
        abstract = data.get("abstract") or tldr.get("text")
        return PaperRecord(
            paper_id=_paper_id(external.get("DOI") or data.get("paperId") or title),
            title=title,
            authors=[item.get("name", "") for item in data.get("authors", []) if item.get("name")],
            year=data.get("year"),
            doi=external.get("DOI"),
            pmid=external.get("PubMed"),
            pmcid=external.get("PubMedCentral"),
            arxiv_id=external.get("ArXiv"),
            url=data.get("url"),
            pdf_url=oa.get("url") if isinstance(oa, dict) else None,
            abstract=abstract,
            venue=data.get("venue"),
            open_access=bool(oa.get("url")) if isinstance(oa, dict) else False,
            sources=["semantic_scholar"],
            confidence_score=0.9,
        )

    def _crossref_by_doi(self, doi: str) -> PaperRecord | None:
        data = self._get_json(f"https://api.crossref.org/works/{quote(doi, safe='')}", params=self._crossref_params(), source="crossref")
        return self._parse_crossref(data.get("message", {})) if data else None

    def _crossref_search(self, query: str) -> PaperRecord | None:
        params = {"query.title": query, "rows": 1, **self._crossref_params()}
        data = self._get_json("https://api.crossref.org/works", params=params, source="crossref")
        items = data.get("message", {}).get("items", []) if data else []
        return self._parse_crossref(items[0]) if items else None

    def _parse_crossref(self, item: dict[str, Any]) -> PaperRecord | None:
        title = _first(item.get("title"))
        if not title:
            return None
        links = item.get("link") or []
        pdf_url = next((link.get("URL") for link in links if "pdf" in str(link.get("content-type", "")).lower()), None)
        year = _date_year(item)
        authors = [
            " ".join(part for part in [author.get("given"), author.get("family")] if part)
            for author in item.get("author", [])
            if isinstance(author, dict)
        ]
        return PaperRecord(
            paper_id=_paper_id(item.get("DOI") or title),
            title=title,
            authors=authors,
            year=year,
            doi=item.get("DOI"),
            url=item.get("URL"),
            pdf_url=pdf_url,
            abstract=_strip_tags(item.get("abstract")),
            venue=_first(item.get("container-title")),
            open_access=bool(pdf_url),
            sources=["crossref"],
            confidence_score=0.82 if item.get("DOI") else 0.65,
        )

    def _pubmed_by_pmid(self, pmid: str) -> PaperRecord | None:
        data = self._get_xml("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", params=self._ncbi_params({"db": "pubmed", "id": pmid, "retmode": "xml"}), source="pubmed")
        return _parse_pubmed_xml(data, fallback_pmid=pmid) if data else None

    def _pubmed_search(self, query: str) -> PaperRecord | None:
        data = self._get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params=self._ncbi_params({"db": "pubmed", "term": query, "retmode": "json", "retmax": 1}), source="pubmed")
        ids = data.get("esearchresult", {}).get("idlist", []) if data else []
        return self._pubmed_by_pmid(ids[0]) if ids else None

    def _europe_pmc_by_query(self, query: str) -> PaperRecord | None:
        data = self._get_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params={"query": query, "format": "json", "pageSize": 1}, source="europe_pmc")
        results = data.get("resultList", {}).get("result", []) if data else []
        if not results:
            return None
        item = results[0]
        return PaperRecord(
            paper_id=_paper_id(item.get("doi") or item.get("pmid") or item.get("title")),
            title=item.get("title") or "Untitled",
            authors=[a.strip() for a in str(item.get("authorString") or "").split(",") if a.strip()][:10],
            year=int(item["pubYear"]) if str(item.get("pubYear", "")).isdigit() else None,
            doi=item.get("doi"),
            pmid=item.get("pmid"),
            pmcid=item.get("pmcid"),
            url=f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id')}" if item.get("id") else None,
            abstract=item.get("abstractText"),
            venue=item.get("journalTitle"),
            open_access=str(item.get("isOpenAccess", "")).upper() == "Y",
            sources=["europe_pmc"],
            confidence_score=0.86,
        )

    def _openalex_by_doi(self, doi: str) -> PaperRecord | None:
        data = self._get_json(f"https://api.openalex.org/works/doi:{quote(doi, safe='')}", params=self._openalex_params(), source="openalex")
        return self._parse_openalex(data) if data else None

    def _openalex_search(self, query: str) -> PaperRecord | None:
        data = self._get_json("https://api.openalex.org/works", params={"search": query, "per-page": 1, **self._openalex_params()}, source="openalex")
        results = data.get("results", []) if data else []
        return self._parse_openalex(results[0]) if results else None

    def _parse_openalex(self, data: dict[str, Any]) -> PaperRecord | None:
        title = data.get("title") or data.get("display_name")
        if not title:
            return None
        ids = data.get("ids") or {}
        primary = data.get("primary_location") or {}
        oa = data.get("open_access") or {}
        authorships = data.get("authorships") or []
        authors = [a.get("author", {}).get("display_name", "") for a in authorships if a.get("author", {}).get("display_name")]
        abstract = _inverted_abstract(data.get("abstract_inverted_index"))
        doi = (ids.get("doi") or "").replace("https://doi.org/", "") or None
        return PaperRecord(
            paper_id=_paper_id(doi or data.get("id") or title),
            title=title,
            authors=authors[:10],
            year=data.get("publication_year"),
            doi=doi,
            url=primary.get("landing_page_url") or data.get("id"),
            pdf_url=primary.get("pdf_url"),
            abstract=abstract,
            venue=(primary.get("source") or {}).get("display_name") if isinstance(primary.get("source"), dict) else None,
            open_access=bool(oa.get("is_oa")),
            sources=["openalex"],
            confidence_score=0.82,
        )

    def _datacite_by_doi(self, doi: str) -> PaperRecord | None:
        data = self._get_json(f"https://api.datacite.org/dois/{quote(doi, safe='')}", source="datacite")
        attrs = data.get("data", {}).get("attributes", {}) if data else {}
        titles = attrs.get("titles") or []
        title = (titles[0] or {}).get("title") if titles else None
        if not title:
            return None
        creators = attrs.get("creators") or []
        content_urls = attrs.get("contentUrl") or []
        pdf_url = next((url for url in content_urls if str(url).lower().endswith(".pdf")), None)
        return PaperRecord(
            paper_id=_paper_id(doi),
            title=title,
            authors=[c.get("name", "") for c in creators if c.get("name")][:10],
            year=int(attrs["publicationYear"]) if str(attrs.get("publicationYear", "")).isdigit() else None,
            doi=doi,
            url=attrs.get("url"),
            pdf_url=pdf_url,
            abstract=next((d.get("description") for d in attrs.get("descriptions", []) if d.get("description")), None),
            open_access=bool(pdf_url),
            sources=["datacite"],
            relationship="dataset",
            confidence_score=0.76,
        )

    def _arxiv_by_id(self, arxiv_id: str) -> PaperRecord | None:
        data = self._get_text("https://export.arxiv.org/api/query", params={"id_list": arxiv_id, "max_results": 1}, source="arxiv")
        if not data or "<entry>" not in data:
            return None
        title = _xml_tag(data, "title")
        if not title:
            return None
        authors = re.findall(r"<author>\s*<name>(.*?)</name>\s*</author>", data, flags=re.S)
        return PaperRecord(
            paper_id=_paper_id(arxiv_id),
            title=_clean_xml(title),
            authors=[_clean_xml(a) for a in authors][:10],
            arxiv_id=arxiv_id,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            abstract=_clean_xml(_xml_tag(data, "summary") or ""),
            open_access=True,
            sources=["arxiv"],
            confidence_score=0.84,
        )

    def _local_evidence(self, dataset_id: str, variable: str, context: dict[str, Any], *, question: str | None) -> list[EvidenceItem]:
        text = _context_text(context)
        query = " ".join(part for part in [variable, question or ""] if part)
        score = _lexical_score(query, text)
        if not text:
            return []
        return [
            EvidenceItem(
                source_type="local_file_metadata",
                source_id=stable_variable_id(dataset_id, context, variable),
                title=f"{self.provider} variable metadata",
                quote=textwrap.shorten(text, width=900, placeholder="..."),
                score=max(score, 0.35),
                supports="variable_context",
            )
        ]

    def _paper_metadata_evidence(self, variable: str, context: dict[str, Any], papers: list[PaperRecord], *, question: str | None) -> list[EvidenceItem]:
        query = " ".join([variable, question or "", _context_text(context)])
        rows = []
        for paper in papers:
            text = " ".join(part for part in [paper.title, paper.abstract or "", paper.venue or ""] if part)
            score = _lexical_score(query, text)
            if score or paper.abstract:
                rows.append(EvidenceItem("paper_abstract", paper.paper_id, paper.title, textwrap.shorten(text, width=1000, placeholder="..."), max(score, 0.2), supports="experiment_context"))
        return rows

    def _full_text_evidence(
        self,
        dataset_id: str,
        variable: str,
        context: dict[str, Any],
        papers: list[PaperRecord],
        *,
        question: str | None,
        limit: int,
    ) -> tuple[list[EvidenceItem], list[MissingPdf]]:
        evidence: list[EvidenceItem] = []
        missing: list[MissingPdf] = []
        query = " ".join([variable, question or "", _context_text(context)])
        for paper in papers[:5]:
            chunks = self._load_chunks(paper.paper_id)
            if not chunks:
                pdf_result = self._ensure_pdf_chunks(dataset_id, paper, variable)
                if pdf_result.get("status") == "missing":
                    missing.append(MissingPdf(**pdf_result["missing_pdf"]))
                    continue
                chunks = self._load_chunks(paper.paper_id)
            for chunk in _rank_chunks(query, chunks)[:limit]:
                evidence.append(
                    EvidenceItem(
                        source_type="paper_full_text",
                        source_id=paper.paper_id,
                        title=paper.title,
                        quote=chunk["text"],
                        score=chunk["score"],
                        page=chunk.get("page"),
                        section=chunk.get("section"),
                        supports="variable_meaning",
                    )
                )
        return sorted(evidence, key=lambda item: item.score, reverse=True)[:limit], missing

    def _ensure_pdf_chunks(self, dataset_id: str, paper: PaperRecord, variable: str) -> dict[str, Any]:
        candidates = _pdf_candidates(paper)
        failures = []
        for url in candidates:
            try:
                path = self._download_pdf(url, paper)
                pages = extract_pdf_pages(path)
                chunks = _chunk_pages(paper, pages, source=url)
                self._store_chunks(paper.paper_id, chunks)
                self.storage.upsert_record("paper_pdf", paper.paper_id, {"paper": asdict(paper), "pdf_path": str(path), "source_url": url, "chunk_count": len(chunks)}, source="neurodata_literature")
                return {"status": "ok", "pdf_path": str(path)}
            except Exception as exc:
                failures.append({"url": url, "error": str(exc)})
        missing = self._missing_pdf(dataset_id, paper, candidates, failures, variable)
        self.storage.upsert_record("missing_pdf_request", f"{dataset_id}:{paper.paper_id}", {"dataset_id": dataset_id, **asdict(missing)}, source="neurodata_literature")
        return {"status": "missing", "missing_pdf": asdict(missing)}

    def _download_pdf(self, url: str, paper: PaperRecord) -> Path:
        with httpx.Client(follow_redirects=True, timeout=45, headers={"User-Agent": "neurodata-literature/0.1"}) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                content_length = int(response.headers.get("content-length") or 0)
                if content_length > self.max_pdf_mb * 1024 * 1024:
                    raise ValueError(f"PDF is larger than {self.max_pdf_mb} MB")
                chunks = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.max_pdf_mb * 1024 * 1024:
                        raise ValueError(f"PDF is larger than {self.max_pdf_mb} MB")
                    chunks.append(chunk)
                data = b"".join(chunks)
        if "pdf" not in content_type and not data.startswith(b"%PDF-"):
            raise ValueError("URL did not return PDF content")
        if not data.startswith(b"%PDF-"):
            raise ValueError("Downloaded content does not start with PDF magic bytes")
        path = self.pdf_dir / f"{paper.paper_id}.pdf"
        path.write_bytes(data)
        return path

    def _store_chunks(self, paper_id: str, chunks: list[dict[str, Any]]) -> None:
        payload = {"paper_id": paper_id, "chunks": chunks, "created_at": time.time()}
        self.storage.upsert_record("paper_chunks", paper_id, payload, source="neurodata_literature")

    def _load_chunks(self, paper_id: str) -> list[dict[str, Any]]:
        rows = self._records("paper_chunks")
        for row in rows:
            if row["record_id"] == paper_id:
                return row["payload"].get("chunks", [])
        return []

    def _missing_pdf(self, dataset_id: str, paper: PaperRecord, candidates: list[str], failures: list[dict[str, str]], variable: str) -> MissingPdf:
        filename = _safe_filename(f"{paper.year or 'paper'}-{paper.title}") + ".pdf"
        return MissingPdf(
            title=paper.title,
            doi=paper.doi,
            pmid=paper.pmid,
            pmcid=paper.pmcid,
            arxiv_id=paper.arxiv_id,
            landing_page_url=paper.url,
            known_pdf_candidates=candidates,
            failed_pdf_candidates=failures,
            why_needed=f"Available metadata/abstract evidence was not enough to confidently explain `{variable}`.",
            suggested_filename=filename,
            registration_call=f"register_paper_pdf(dataset_id={dataset_id!r}, pdf_path='/path/to/{filename}', doi={paper.doi!r}, title={paper.title!r})",
        )

    def _confidence(self, variable: str, context: dict[str, Any], evidence: list[EvidenceItem]) -> tuple[float, list[str]]:
        reasons = []
        score = 0.0
        if context:
            score += 0.25
        if any(variable.lower() in item.quote.lower() for item in evidence):
            score += 0.25
        else:
            reasons.append("The exact variable name was not found in retrieved evidence.")
        source_types = {item.source_type for item in evidence if item.score > 0.1}
        score += min(0.3, 0.1 * len(source_types))
        if any(item.source_type == "paper_full_text" for item in evidence):
            score += 0.2
        elif evidence:
            reasons.append("No full-text paper evidence was used.")
        if len(evidence) < 2:
            reasons.append("Fewer than two evidence items support the explanation.")
        generic = variable.lower() in {"data", "values", "value", "x", "y", "choice", "response", "condition", "trial_type"}
        if generic:
            score -= 0.1
            reasons.append("The variable name is generic and needs stronger supporting evidence.")
        return max(0.0, min(1.0, score)), reasons

    def _should_use_full_text(self, confidence: float, evidence: list[EvidenceItem], variable: str, policy: str) -> bool:
        if policy == "never":
            return False
        if policy == "always":
            return True
        if confidence < 0.65:
            return True
        if len(evidence) < 2:
            return True
        if variable.lower() in {"data", "values", "value", "x", "y", "choice", "response", "condition", "trial_type"}:
            return True
        return False

    def _interpretation(self, variable: str, context: dict[str, Any], evidence: list[EvidenceItem], confidence: float) -> str | None:
        if not evidence:
            return None
        label = _confidence_label(confidence)
        kind = context.get("neurodata_type") or context.get("modality") or context.get("alf_object") or context.get("suffix") or context.get("kind") or "dataset variable"
        units = context.get("unit") or context.get("units")
        parts = [f"`{variable}` is most likely a {kind}"]
        if units:
            parts.append(f"with units `{units}`")
        parts.append(f"based on {label}-confidence metadata/literature evidence.")
        return " ".join(parts)

    def _experiment_context(self, context: dict[str, Any], evidence: list[EvidenceItem]) -> dict[str, Any]:
        text = " ".join([_context_text(context)] + [item.quote for item in evidence[:5]]).lower()
        return {
            "task": context.get("task") or context.get("task_protocol") or _term_after(text, "task"),
            "species": context.get("species") or _first_present(text, ["mouse", "mice", "human", "rat", "macaque"]),
            "modality": context.get("modality"),
            "stimulus": _first_present(text, ["visual", "auditory", "odor", "stimulus", "reward"]),
            "behavior": context.get("behavior") or _first_present(text, ["choice", "lick", "wheel", "locomotion", "decision"]),
            "protocol": context.get("protocol") or context.get("task_protocol"),
        }

    def _next_actions(self, dataset_id: str, status: str, missing: list[MissingPdf]) -> list[str]:
        actions = []
        if status == "pdf_required_but_missing":
            for item in missing[:3]:
                actions.append(f"Download `{item.title}` and call {item.registration_call}")
        elif status == "low_confidence":
            actions.append("Provide a local PDF with register_paper_pdf or pass more variable context.")
        return actions

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None, source: str) -> dict[str, Any] | None:
        try:
            headers = {"Accept": "application/json", "User-Agent": "neurodata-literature/0.1"}
            if source == "semantic_scholar" and self.semantic_scholar_api_key:
                headers["x-api-key"] = self.semantic_scholar_api_key
            response = httpx.get(url, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def _get_xml(self, url: str, *, params: dict[str, Any] | None = None, source: str) -> str | None:
        return self._get_text(url, params=params, source=source)

    def _get_text(self, url: str, *, params: dict[str, Any] | None = None, source: str) -> str | None:
        try:
            response = httpx.get(url, params=params, headers={"User-Agent": "neurodata-literature/0.1"}, timeout=20)
            response.raise_for_status()
            return response.text
        except Exception:
            return None

    def _crossref_params(self) -> dict[str, str]:
        return {"mailto": self.contact_email} if self.contact_email else {}

    def _openalex_params(self) -> dict[str, str]:
        return {"mailto": self.contact_email} if self.contact_email else {}

    def _ncbi_params(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.contact_email:
            params["email"] = self.contact_email
        if self.ncbi_api_key:
            params["api_key"] = self.ncbi_api_key
        return params

    def _records(self, record_type: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.storage.config.db_path) as conn:
            rows = conn.execute(
                "SELECT record_id, payload_json FROM records WHERE provider = ? AND record_type = ?",
                (self.provider, record_type),
            ).fetchall()
        return [{"record_id": row[0], "payload": json.loads(row[1])} for row in rows]


def extract_pdf_pages(path: Path) -> list[str]:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore

        result = DocumentConverter().convert(str(path))
        page_texts: dict[int, list[str]] = {}
        for item, _level in result.document.iterate_items():
            try:
                page_no = int(item.prov[0].page_no)
            except Exception:
                continue
            text = getattr(item, "text", None) or getattr(item, "title", None) or getattr(item, "caption", None)
            if text:
                page_texts.setdefault(page_no, []).append(str(text).strip())
        if page_texts:
            return ["\n".join(page_texts.get(i, [])) for i in range(1, max(page_texts) + 1)]
    except Exception:
        pass
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        return [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"Could not extract PDF text: {exc}") from exc


def build_dataset_explorer_html(
    *,
    provider: str,
    dataset_id: str,
    title: str,
    summary: dict[str, Any],
    variables: list[dict[str, Any]],
    papers: list[dict[str, Any]],
    missing_pdfs: list[dict[str, Any]] | None = None,
) -> str:
    data = {
        "provider": provider,
        "dataset_id": dataset_id,
        "title": title,
        "summary": summary,
        "variables": variables,
        "papers": papers,
        "missing_pdfs": missing_pdfs or [],
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} dataset explorer</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f7f7f4; color: #202124; }}
    header {{ padding: 18px 24px; background: #18332f; color: white; }}
    header h1 {{ margin: 0 0 6px; font-size: 22px; }}
    header p {{ margin: 0; color: #d9e7df; }}
    main {{ display: grid; grid-template-columns: 280px minmax(420px, 1fr) 420px; height: calc(100vh - 79px); }}
    aside, section {{ overflow: auto; border-right: 1px solid #d8d8d0; }}
    aside {{ padding: 16px; background: #efeee8; }}
    section {{ padding: 16px; }}
    #detail {{ border-right: 0; background: white; }}
    input, select {{ width: 100%; box-sizing: border-box; padding: 9px; border: 1px solid #b9bbb2; border-radius: 6px; margin-bottom: 10px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ text-align: left; padding: 9px; border-bottom: 1px solid #e4e4df; font-size: 13px; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #fafaf7; z-index: 1; }}
    tr {{ cursor: pointer; }}
    tr:hover {{ background: #f0f5f2; }}
    .badge {{ display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 12px; background: #dde8e0; margin-right: 4px; }}
    .low {{ background: #f4d7d2; }}
    .medium {{ background: #f2e3b7; }}
    .high {{ background: #d8ecd8; }}
    pre {{ white-space: pre-wrap; background: #f5f5f1; padding: 12px; border-radius: 6px; overflow: auto; }}
    .muted {{ color: #62665f; }}
    .card {{ background: white; border: 1px solid #deded7; border-radius: 8px; padding: 12px; margin-bottom: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <p>{html.escape(provider)} · {html.escape(dataset_id)}</p>
  </header>
  <main>
    <aside>
      <h2>Dataset</h2>
      <div id="summary"></div>
      <h2>Papers</h2>
      <div id="papers"></div>
    </aside>
    <section>
      <input id="search" placeholder="Filter variables, paths, modalities">
      <table>
        <thead><tr><th>Variable</th><th>Path</th><th>Type</th><th>Units</th><th>Status</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </section>
    <section id="detail">
      <h2>Select a Variable</h2>
      <p class="muted">Click a row to inspect metadata and copy an MCP call for literature-backed explanation.</p>
    </section>
  </main>
  <script id="dataset-data" type="application/json">{payload}</script>
  <script>
    const data = JSON.parse(document.getElementById('dataset-data').textContent);
    const rows = document.getElementById('rows');
    const detail = document.getElementById('detail');
    const search = document.getElementById('search');
    function esc(x) {{ return String(x ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#39;'}}[c])); }}
    function text(v) {{ return Object.entries(v).map(([k,val]) => `${{k}}: ${{JSON.stringify(val)}}`).join('\\n'); }}
    function renderSummary() {{
      document.getElementById('summary').innerHTML = Object.entries(data.summary || {{}}).map(([k,v]) => `<div class="card"><b>${{esc(k)}}</b><br>${{esc(Array.isArray(v) ? v.join(', ') : v)}}</div>`).join('');
      document.getElementById('papers').innerHTML = (data.papers || []).map(p => `<div class="card"><b>${{esc(p.title)}}</b><br><span class="muted">${{esc(p.doi || p.pmid || p.url || '')}}</span></div>`).join('') || '<p class="muted">No papers resolved yet.</p>';
    }}
    function renderRows() {{
      const q = search.value.toLowerCase();
      rows.innerHTML = '';
      data.variables.filter(v => JSON.stringify(v).toLowerCase().includes(q)).forEach(v => {{
        const conf = v.confidence_label || 'unknown';
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${{esc(v.name || v.variable || v.column || v.object_path)}}</td><td>${{esc(v.file || v.file_path || v.object_path || '')}}</td><td>${{esc(v.neurodata_type || v.modality || v.kind || '')}}</td><td>${{esc(v.unit || v.units || '')}}</td><td><span class="badge ${{conf}}">${{esc(conf)}}</span></td>`;
        tr.onclick = () => showDetail(v);
        rows.appendChild(tr);
      }});
    }}
    function showDetail(v) {{
      const variable = v.name || v.variable || v.column || v.object_path || '';
      const call = {{ tool: 'explain_dataset_variable', arguments: {{ dataset_key_or_id: data.dataset_id, variable, file_path: v.file || v.file_path || null, object_path: v.object_path || null, full_text_policy: 'auto' }} }};
      detail.innerHTML = `<h2>${{esc(variable)}}</h2><div class="card"><h3>Metadata</h3><pre>${{esc(text(v))}}</pre></div><div class="card"><h3>Ask the MCP</h3><p class="muted">Paste or ask your agent to run this call.</p><pre>${{esc(JSON.stringify(call, null, 2))}}</pre></div>`;
    }}
    search.oninput = renderRows;
    renderSummary(); renderRows();
  </script>
</body>
</html>
"""


def _chunk_pages(paper: PaperRecord, pages: list[str], *, source: str) -> list[dict[str, Any]]:
    chunks = []
    for page_no, page in enumerate(pages, start=1):
        section = "Unknown section"
        for idx, para in enumerate(_paragraphs(page), start=1):
            heading = _section_heading(para)
            if heading:
                section = heading
                continue
            if len(para.split()) < 20:
                continue
            chunks.append({"chunk_id": f"{paper.paper_id}-p{page_no}-{idx}", "paper_id": paper.paper_id, "paper_title": paper.title, "page": page_no, "section": section, "text": para, "source": source})
    return chunks


def _paragraphs(text: str) -> list[str]:
    cleaned = []
    for line in text.splitlines():
        stripped = line.rstrip()
        cleaned.append(stripped[:-1] if stripped.endswith("-") else re.sub(r"\s+", " ", stripped).strip())
    paragraphs = []
    buf = []
    for line in cleaned:
        if not line:
            if buf:
                paragraphs.append(" ".join(buf))
                buf = []
            continue
        buf.append(line)
        if sum(len(part.split()) for part in buf) >= 180:
            paragraphs.append(" ".join(buf))
            buf = []
    if buf:
        paragraphs.append(" ".join(buf))
    return paragraphs


def _section_heading(text: str) -> str:
    if len(text) > 100 or len(text.split()) > 16:
        return ""
    if re.match(r"^(\d+(\.\d+)*\s+)?(abstract|introduction|background|methods?|methodology|experimental|results?|discussion|conclusion|supplementary|appendix)\b", text, re.I):
        return text[:90]
    if re.match(r"^\d+(\.\d+)*\s+[A-Z][a-zA-Z\s.,:;]+", text):
        return text[:90]
    return ""


def _rank_chunks(query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    method_bonus = {"method", "methods", "experimental", "procedure", "task", "recording", "behavior", "stimulus"}
    ranked = []
    for chunk in chunks:
        score = _lexical_score(query, chunk.get("text", ""))
        section = str(chunk.get("section") or "").lower()
        if any(term in section for term in method_bonus):
            score += 0.1
        ranked.append({**chunk, "score": round(min(1.0, score), 4)})
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def _pdf_candidates(paper: PaperRecord) -> list[str]:
    candidates = []
    for url in [paper.pdf_url, paper.url]:
        if url and str(url).lower().endswith(".pdf"):
            candidates.append(url)
    if paper.arxiv_id:
        candidates.append(f"https://arxiv.org/pdf/{paper.arxiv_id}.pdf")
    if paper.pmcid:
        candidates.append(f"https://europepmc.org/articles/{paper.pmcid}?pdf=render")
    return list(dict.fromkeys(candidates))


def stable_variable_id(dataset_id: str, context: dict[str, Any], variable: str) -> str:
    key = json.dumps({"dataset_id": dataset_id, "variable": variable, "file": context.get("file") or context.get("file_path"), "object_path": context.get("object_path"), "column": context.get("column")}, sort_keys=True, default=str)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _paper_id(value: str) -> str:
    return hashlib.sha1(str(value).lower().strip().encode()).hexdigest()[:16]


def _extract_doi(text: str) -> str | None:
    match = DOI_RE.search(text)
    return match.group(0).rstrip(".,;)") if match else None


def _extract_pmid(text: str) -> str | None:
    match = PMID_RE.search(text)
    return match.group(1) if match else None


def _extract_arxiv(text: str) -> str | None:
    match = ARXIV_RE.search(text)
    return match.group(1) if match else None


def _extract_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s<>\]\)\"']+", text)
    return match.group(0).rstrip(".,;)") if match else None


def _extract_title_hint(hint: dict[str, Any] | str) -> str | None:
    if isinstance(hint, dict):
        for key in ["title", "name", "paper_title", "citation"]:
            value = hint.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ["url", "identifier"]:
            value = hint.get(key)
            if isinstance(value, str) and not _extract_doi(value):
                return value
    text = str(hint)
    if _extract_doi(text) or _extract_url(text):
        return None
    return text.strip()[:200] if text.strip() else None


def _context_text(context: dict[str, Any]) -> str:
    return " ".join(str(v) for v in context.values() if v not in (None, "", [], {}))


def _lexical_score(query: str, text: str) -> float:
    q = {t.lower() for t in TOKEN_RE.findall(query or "") if len(t) > 2}
    t = {t.lower() for t in TOKEN_RE.findall(text or "") if len(t) > 2}
    return len(q & t) / len(q | t) if q and t else 0.0


def _dedupe_key(paper: PaperRecord) -> str:
    return (paper.doi or paper.pmid or paper.pmcid or paper.arxiv_id or paper.title).lower()


def _merge_papers(existing: PaperRecord, incoming: PaperRecord) -> PaperRecord:
    for field_name in ["doi", "pmid", "pmcid", "arxiv_id", "url", "pdf_url", "abstract", "venue", "year"]:
        if getattr(existing, field_name) in (None, "", []):
            setattr(existing, field_name, getattr(incoming, field_name))
    existing.authors = existing.authors or incoming.authors
    existing.open_access = existing.open_access or incoming.open_access
    existing.sources = sorted(set(existing.sources + incoming.sources))
    existing.confidence_score = max(existing.confidence_score, incoming.confidence_score)
    return existing


def _confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


def _provenance(method: str, sources: list[str]) -> list[dict[str, Any]]:
    return [{"method": method, "sources": sorted(set(sources)), "timestamp": time.time()}]


def _first(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    return str(value) if value else None


def _date_year(item: dict[str, Any]) -> int | None:
    for key in ["published-print", "published-online", "created", "issued"]:
        parts = item.get(key, {}).get("date-parts")
        if parts and parts[0]:
            return parts[0][0]
    return None


def _strip_tags(text: str | None) -> str | None:
    return re.sub(r"<[^>]+>", "", text).strip() if text else None


def _inverted_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    words = []
    for word, positions in index.items():
        for position in positions:
            words.append((position, word))
    return " ".join(word for _pos, word in sorted(words))


def _parse_pubmed_xml(text: str, *, fallback_pmid: str) -> PaperRecord | None:
    title = _clean_xml(_xml_tag(text, "ArticleTitle") or "")
    if not title:
        return None
    abstract = " ".join(_clean_xml(item) for item in re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", text, flags=re.S))
    doi = next((value for value in re.findall(r'<ArticleId IdType="doi">(.*?)</ArticleId>', text, flags=re.S)), None)
    pmcid = next((value for value in re.findall(r'<ArticleId IdType="pmc">(.*?)</ArticleId>', text, flags=re.S)), None)
    year_text = _xml_tag(text, "Year")
    authors = []
    for author in re.findall(r"<Author[^>]*>(.*?)</Author>", text, flags=re.S):
        last = _clean_xml(_xml_tag(author, "LastName") or "")
        fore = _clean_xml(_xml_tag(author, "ForeName") or "")
        if last or fore:
            authors.append(" ".join([fore, last]).strip())
    return PaperRecord(
        paper_id=_paper_id(doi or fallback_pmid),
        title=title,
        authors=authors[:10],
        year=int(year_text) if str(year_text).isdigit() else None,
        doi=doi,
        pmid=fallback_pmid,
        pmcid=pmcid,
        abstract=abstract or None,
        venue=_clean_xml(_xml_tag(text, "Title") or ""),
        sources=["pubmed"],
        confidence_score=0.86,
    )


def _xml_tag(text: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, flags=re.S)
    return match.group(1) if match else None


def _clean_xml(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def _guess_title(path: Path, pages: list[str]) -> str:
    first = pages[0] if pages else ""
    for line in first.splitlines()[:20]:
        line = line.strip()
        if 10 < len(line) < 200:
            return line
    return path.stem.replace("_", " ").replace("-", " ")


def _safe_filename(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:120] or "paper"


def _term_after(text: str, term: str) -> str | None:
    match = re.search(rf"{re.escape(term)}[:\s]+([a-z0-9_\- ]{{3,80}})", text)
    return match.group(1).strip() if match else None


def _first_present(text: str, terms: list[str]) -> str | None:
    return next((term for term in terms if term in text), None)


def _dedupe(records: list[PaperRecord]) -> list[PaperRecord]:
    merged: dict[str, PaperRecord] = {}
    for record in records:
        key = _dedupe_key(record)
        if key in merged:
            merged[key] = _merge_papers(merged[key], record)
        else:
            merged[key] = record
    return sorted(merged.values(), key=lambda item: item.confidence_score, reverse=True)


LiteratureService._dedupe = staticmethod(_dedupe)  # type: ignore[attr-defined]
