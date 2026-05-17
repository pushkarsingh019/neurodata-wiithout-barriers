# OpenNeuro MCP Server

OpenNeuro MCP Server is an AI-native neuroscience data interface layer for OpenNeuro. It is intentionally more than an API wrapper: it combines OpenNeuro GraphQL access, BIDS-aware parsing, ontology-based inference, semantic embeddings, paper/code enrichment hooks, metadata quality scoring, and a knowledge graph exposed through Model Context Protocol tools.

The current implementation is a production-grade foundation that can run locally with MCP today and scale into PostgreSQL/pgvector, Qdrant, and Neo4j-backed deployments.

## Capabilities

- Natural language, keyword, semantic, ontology, modality, species, task, paradigm, author, and institution search
- BIDS parsing for dataset descriptions, participants, events, file entities, sessions, derivatives, modalities, and tasks
- Behavioral neuroscience inference for reward learning, 2AFC, go/no-go, social cognition, fear conditioning, foraging, locomotion, licking, and grooming
- Dataset-paper-code linkage from DOI, `ReferencesAndLinks`, GitHub, and planned CrossRef/Semantic Scholar/PubMed enrichment
- Local deterministic embedding adapter with a clean path to hosted embedding models and pgvector/Qdrant
- Knowledge graph over datasets, papers, authors, species, modalities, paradigms, and pipelines
- Metadata quality scores, missing metadata detection, provenance, and BIDS validation hook points

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
openneuro-mcp
```

Useful environment variables:

```bash
OPENNEURO_GRAPHQL_URL=https://openneuro.org/crn/graphql
OPENNEURO_API_TOKEN=
OPENNEURO_TIMEOUT=30
```

## MCP Tools

The server exposes tools for `search_datasets`, `semantic_search`, `ontology_search`, `modality_search`, `species_search`, `task_search`, `behavioral_paradigm_search`, `author_search`, `institution_search`, `get_dataset_metadata`, `get_dataset_files`, `get_related_papers`, `find_similar_datasets`, `find_behavioral_paradigms`, `get_modalities`, `get_task_structure`, `get_subject_info`, `get_events`, `get_derivatives`, `get_analysis_pipelines`, `get_associated_code`, `get_dataset_embedding`, `query_knowledge_graph`, and `get_openneuro_mcp_roadmap`.

## Example Prompts

- Find human fMRI datasets involving social cognition.
- Find reward-learning paradigms with BIDS events.tsv trial structure.
- Get metadata quality issues for ds000001.
- Which indexed datasets share fMRI and reward learning?
- Return associated papers and GitHub repositories for ds000224.
- Summarize task structure and event timing for a go/no-go dataset.

## Architecture

Read [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) for the full design, including database schema, knowledge graph schema, indexing pipeline, deployment strategy, scaling plan, security posture, and roadmap.
