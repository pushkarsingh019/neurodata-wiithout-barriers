# OpenNeuro Semantic OS Architecture

## 1. System Architecture

The server is organized as a layered semantic data system. The ingestion layer talks to OpenNeuro GraphQL and later to DANDI, NWB, IBL, Brainlife, NeuroVault, Allen Brain Atlas, and CRCNS adapters. The BIDS layer parses dataset files, `dataset_description.json`, `participants.tsv`, `events.tsv`, `scans.tsv`, sidecars, derivatives, session structures, modalities, and task entities. The enrichment layer normalizes species, modalities, behavioral paradigms, brain regions, authors, institutions, papers, and code links. The indexing layer writes structured metadata to PostgreSQL, vectors to pgvector or Qdrant, and graph edges to Neo4j or an in-process NetworkX graph for local development. The MCP layer exposes machine-readable tools for agents and researchers.

## 2. MCP Protocol Design

Tools are read-only by default, return JSON-serializable dictionaries, support pagination or limits where relevant, and include provenance and confidence where inference is involved. Search tools are intentionally split by researcher intent: keyword search for direct OpenNeuro discovery, semantic search for embedding retrieval, ontology search for normalized neuroscience concepts, and task/paradigm/modality/species tools for controlled discovery. Dataset tools expose partial retrieval, such as file trees without large file content and concrete event parsing only after the caller provides a path.

## 3. Database Schema

Core PostgreSQL tables should include `datasets`, `dataset_versions`, `files`, `bids_entities`, `subjects`, `tasks`, `events_summaries`, `sidecars`, `derivatives`, `modalities`, `species`, `paradigms`, `papers`, `authors`, `institutions`, `code_repositories`, `metadata_quality_reports`, `inference_provenance`, and `index_jobs`. Many-to-many joins should connect datasets to authors, institutions, papers, modalities, species, paradigms, tasks, and pipelines. Vector tables should store one embedding per semantic object: dataset description, task structure, paper abstract, behavioral paradigm, and metadata field group.

## 4. Knowledge Graph Schema

Graph node labels should include `Dataset`, `Version`, `File`, `SubjectCohort`, `Task`, `EventStructure`, `Paradigm`, `Stimulus`, `MotorOutput`, `ReinforcementSchedule`, `Modality`, `Technique`, `Species`, `BrainRegion`, `Paper`, `Author`, `Institution`, `CodeRepository`, `Pipeline`, and `Repository`. Edge types should include `HAS_VERSION`, `CONTAINS_FILE`, `HAS_MODALITY`, `HAS_SPECIES`, `USES_TASK`, `USES_PARADIGM`, `HAS_STIMULUS`, `HAS_RESPONSE`, `USES_REINFORCEMENT`, `RECORDED_FROM`, `AUTHORED_BY`, `AFFILIATED_WITH`, `CITES`, `REUSED_BY`, `HAS_CODE`, `PROCESSED_BY`, `RELATED_TO`, and `SAME_CONSORTIUM_AS`.

## 5. Embedding Pipeline

The development server includes a deterministic local embedding adapter for offline tests. Production indexing should batch dataset descriptions, task descriptions, event summaries, paper abstracts, and ontology labels through an embedding provider, then persist vectors in pgvector or Qdrant. The indexer should support incremental jobs keyed by dataset id, snapshot tag, file tree hash, metadata hash, embedding model id, and pipeline version. Re-embedding should be idempotent and resumable.

## 6. API Endpoints

MCP is the primary protocol. Optional FastAPI endpoints can wrap the same service layer for `/datasets/search`, `/datasets/{id}`, `/datasets/{id}/files`, `/datasets/{id}/subjects`, `/datasets/{id}/tasks`, `/datasets/{id}/events`, `/datasets/{id}/papers`, `/datasets/{id}/embedding`, `/graph/query`, `/index/jobs`, and `/healthz`.

## 7. Tool Definitions

Implemented tools include dataset discovery, semantic search, ontology search, modality/species/task/paradigm/author/institution search, metadata retrieval, file tree retrieval, related papers, similar datasets, behavioral paradigm inference, modalities, task structure, subject info, events, derivatives, analysis pipelines, associated code, dataset embeddings, and knowledge graph queries.

## 8. Example Output

For `get_dataset_metadata("ds000001", include_files=true)`, the output contains dataset id, name, version, DOI, authors, keywords, inferred modalities, species, inferred behavioral paradigms with confidence and evidence, citation records, quality score, BIDS summary, provenance, and optionally classified file records with BIDS entities.

## 9. Deployment Strategy

Use the MCP process for local agent integration. For production, run an API/MCP service, an indexing worker, PostgreSQL with pgvector, Qdrant when distributed vector search is needed, Redis for job queues and caching, and Neo4j for graph traversal. Keep OpenNeuro GraphQL calls cached and rate-limited. Use Docker Compose for development and Kubernetes or ECS for production.

## 10. CI/CD Recommendations

CI should run Ruff, unit tests, schema migration checks, Docker build checks, and offline contract tests with mocked OpenNeuro GraphQL responses. Nightly jobs should run live smoke tests against a tiny public dataset, refresh GraphQL schema snapshots, and report API drift.

## 11. Scaling Strategy

Scale by separating interactive MCP calls from batch indexing. Store file trees and metadata snapshots in PostgreSQL, cache GraphQL responses, shard embeddings by repository and object type, and build graph projections for common questions such as lab productivity, modality-task co-occurrence, and consortium relationships. Index updates should be incremental by OpenNeuro snapshot tag and content hash.

## 12. Security Considerations

The default server is read-only. API tokens should be optional and loaded from environment variables. Logs must avoid leaking tokens, presigned URLs, participant-level sensitive metadata, or private draft identifiers. Future write tools should be isolated behind explicit permissions and audit logs. Production deployments should enforce egress allowlists, rate limits, request size limits, and dependency scanning.

## 13. Future Roadmap

The next stages are live CrossRef/Semantic Scholar/PubMed enrichment, BIDS validator subprocess integration, `scans.tsv` and sidecar aggregation, PostgreSQL migrations, pgvector persistence, Qdrant adapter, Neo4j adapter, async GraphQL client, FastAPI health and indexing endpoints, DANDI/NWB adapter, IBL adapter, NeuroVault map linkage, Brainlife app linkage, and Allen Brain Atlas region normalization.
