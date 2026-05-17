# IBL MCP Audit And Rebuild Report

## 1. Full Audit Report

The original implementation in this directory was useful but not yet scientifically deep. It exposed OpenAlyx REST endpoints as MCP tools, with basic session, dataset, file, insertion, channel, subject, brain-region, lab, project, tag, cache, download URL, and generic API access. That was a reasonable starting point, but it was primarily an API wrapper. It did not yet understand IBL ALF dataset conventions, behavioral trial arrays, psychometric summaries, wheel/lick/video modalities, cluster QC, spike alignment, literature linkage, semantic retrieval, or graph reasoning.

The current project structure after refactor is:

```text
ibl-mcp-server/
  pyproject.toml
  Dockerfile
  README.md
  docs/
    API_COVERAGE.md
    AUDIT_REPORT.md
  src/ibl_mcp/
    __init__.py
    client.py
    knowledge.py
    schemas.py
    server.py
    services.py
  tests/
    test_client.py
    test_server.py
    test_services.py
```

The dependency graph is:

```text
server.py
  -> client.py
  -> services.py
       -> client.py
       -> schemas.py
       -> knowledge.py
       -> numpy
schemas.py -> pydantic
client.py -> httpx
knowledge.py -> stdlib only
```

Current feature inventory:

| Area | Status |
|---|---|
| MCP server setup | Implemented with FastMCP. |
| Alyx REST integration | Implemented for common endpoints plus generic fallback. |
| ONE integration | Partial. Uses ONE-compatible Alyx endpoints and ALF conventions, but does not yet instantiate the Python ONE client/cache. |
| Auth | Token and username/password supported for Alyx-compatible deployments. |
| Session search | Implemented with common filters and Django query escape hatch. |
| Subject/lab/project search | Implemented. |
| Probe insertion search | Implemented. |
| Dataset/file search | Implemented. |
| Trial retrieval | Implemented for `.npy` ALF arrays via dataset URL resolution. |
| Behavioral summaries | Implemented for performance, bias, response/reaction time, and psychometric curve. |
| Wheel data | Implemented for wheel position/timestamps summary and optional samples. |
| Lick data | Implemented for lick timestamp arrays where available. |
| Video/pose/pupil support | Metadata availability implemented; parquet loading remains future work. |
| Spike data | Metadata and peri-event spike count alignment implemented for `.npy` arrays. |
| Cluster QC | Implemented for `.npy` cluster labels/acronyms where available; parquet metrics remain future work. |
| QC warnings | Implemented in high-level envelopes. |
| Caching | Download directory exists; no persistent metadata cache or ONE cache DB yet. |
| Async architecture | Not implemented. Current server uses sync httpx. |
| Tests | Unit tests for client, tool inventory, behavioral loading, and semantic scaffold. |
| Logging | Minimal; structured logging is still missing. |
| Deployment | `pyproject.toml`, `uv`, pip, and Dockerfile available. |

## 2. Feature Matrix

| Capability | Existing Before | Implemented Now | Remaining Gap |
|---|---:|---:|---|
| `search_sessions` | Yes | Yes | Add richer query builder and cached search index. |
| `get_session_metadata` | No | Yes | Add full ONE cache parity and lab/subject joins at scale. |
| `get_session_datasets` | Partial | Yes | Add revision-aware preferred dataset resolution. |
| `search_subjects` | Partial | Yes | Add longitudinal subject summaries/training status. |
| `search_labs` / `search_projects` | Partial | Yes | Add lab contribution analytics. |
| `search_task_protocols` | No | Yes | Replace derived protocol list with cache-backed aggregation. |
| `search_probe_insertions` | Partial | Yes | Add QC-aware insertion ranking. |
| `get_trials` | No | Yes | Add parquet/table support and full ALF object loading. |
| `get_behavior_summary` | No | Yes | Add bias block, lapse, threshold, chronometric model fitting. |
| `get_psychometric_summary` | No | Yes | Add proper psychometric fitting and confidence intervals. |
| `get_wheel_data` | No | Yes | Add movement epoch extraction and velocity smoothing. |
| `get_lick_data` | No | Yes | Add trial-aligned lick rasters and outcome comparisons. |
| `get_video_metadata` | No | Yes | Add video frame metadata and signed stream validation. |
| `get_pose_data` / `get_pupil_data` | No | Metadata | Add parquet readers and camera-specific summaries. |
| `get_spike_metadata` | Partial | Yes | Add good-unit filtering against metrics parquet. |
| `get_spike_times` | No | Metadata | Add controlled spike sample return and chunked download. |
| `get_cluster_qc` | No | Yes | Add full cluster metrics table support. |
| Multimodal alignment | No | Basic | Add robust peri-event matrix outputs and binning. |
| Papers/code | No | Static registry | Add curated bibliographic store and live GitHub metadata. |
| Semantic search | No | Lexical scaffold | Add embeddings/vector DB. |
| Knowledge graph | No | Static/session edges | Add SQLite/RDF/NetworkX graph materialization. |

## 3. Missing Feature Checklist

High priority:

- Native ONE client/cache integration. This matters because ONE handles dataset resolution, cache tables, revisions, and download details more faithfully than raw REST. Complexity: medium. Steps: optional `one-api` extra, configure cache dir, expose `one.search`, `one.list`, `one.load_dataset`, and fallback to REST.
- Revision-aware dataset selection. Scientific analyses must know which dataset revision was loaded. Complexity: medium. Steps: call `revisions`, include revision in provenance, support preferred revision filter.
- Full behavioral model summaries. Current summaries are descriptive. Complexity: medium-high. Steps: fit psychometric and chronometric curves, estimate bias/threshold/lapse, add bootstrap confidence intervals.
- Parquet support for DLC, pupil, and cluster metrics. Critical for pose and unit QC. Complexity: medium. Steps: add `pyarrow`/`pandas` optional extra, bounded row loading, camera/probe selectors.
- QC-aware search ranking. Agents should not unknowingly select low-quality sessions. Complexity: medium. Steps: normalize session, dataset, insertion, and cluster QC into a score and warnings.

Medium priority:

- Async httpx and concurrent dataset loading. Useful for multiple ALF arrays. Complexity: medium.
- Persistent metadata cache. Required for semantic/graph scale. Complexity: medium. Steps: SQLite tables for sessions, datasets, subjects, insertions, papers, and edges.
- Embedding-backed semantic search. Important for natural-language discovery. Complexity: medium-high. Steps: build records, embed with configurable provider, store vectors.
- Graph query engine. Important for cross-entity reasoning. Complexity: medium. Steps: materialize nodes/edges into SQLite or NetworkX and expose graph query DSL.
- Integration tests against known public sessions. Complexity: low-medium but network-dependent.

Lower priority:

- Mutating Alyx workflows. Useful for private deployments but not central to public IBL discovery.
- Full video streaming. Large files make this costly; metadata and targeted frame extraction should come first.

## 4. Refactored Architecture Proposal

The implementation now has a three-layer architecture:

```text
MCP tools/prompts/resources
  -> Domain service layer
       -> IBL semantic conventions, QC, summaries, alignment, graph/literature
  -> Alyx REST client
       -> Endpoint access, auth, downloads, raw fallback
```

The next architecture should add:

```text
ONE adapter
  -> one.search / one.list / one.load_dataset
  -> cache tables and revision resolution

Local store
  -> SQLite metadata cache
  -> vector index
  -> graph edge table

Analysis adapters
  -> numpy ALF arrays
  -> parquet tables
  -> NWB/DANDI readers
```

## 5. Updated MCP Tool List

Discovery and metadata:

- `list_alyx_endpoints`
- `describe_alyx_endpoint`
- `search_sessions`
- `get_session`
- `summarize_session`
- `get_session_metadata`
- `get_session_datasets`
- `search_subjects`
- `list_subjects`
- `search_labs`
- `list_labs`
- `search_projects`
- `list_projects`
- `search_task_protocols`
- `list_tags`
- `get_brain_regions`
- `list_brain_regions`
- `list_dataset_types`
- `list_data_formats`

Behavior:

- `search_behavioral_sessions`
- `get_trials`
- `get_behavior_summary`
- `get_psychometric_summary`
- `get_wheel_data`
- `get_lick_data`
- `get_video_metadata`
- `get_pose_data`
- `get_pupil_data`

Neural:

- `search_neural_recording_sessions`
- `search_probe_insertions`
- `list_insertions`
- `get_insertion`
- `get_probe_metadata`
- `get_spike_metadata`
- `get_spike_times`
- `get_cluster_qc`
- `list_trajectories`
- `list_channels`

Alignment:

- `align_behavior_to_events`
- `align_spikes_to_events`

Literature, code, semantic, graph:

- `get_related_papers`
- `get_associated_code`
- `semantic_search`
- `find_similar_sessions`
- `query_knowledge_graph`

Raw/ops:

- `list_datasets`
- `get_dataset`
- `list_files`
- `get_dataset_download_urls`
- `download_url`
- `get_cache_info`
- `get_cache_zip_url`
- `list_revisions`
- `list_downloads`
- `list_tasks`
- `call_alyx_api`
- `confirmed_mutating_alyx_api`

## 6. ONE / ALYX Integration Design

Current implementation uses Alyx REST and ALF dataset conventions. This is correct for public OpenAlyx access but incomplete for full ONE behavior. The future adapter should:

1. Use REST for lightweight metadata and no-extra-install deployments.
2. Use optional ONE for cache-backed search, revision-aware dataset resolution, and canonical dataset loading.
3. Include provenance fields for Alyx endpoint, ONE cache version, dataset UUID, revision, collection, URL, and local path.
4. Keep `call_alyx_api` as an escape hatch but route common workflows through semantic tools.

## 7. Behavioral Neuroscience Design

The behavioral layer should treat split ALF arrays as a trial table. Current support loads choices, contrasts, feedback, reward, response, movement, go cue, stimulus onset, intervals, and probabilityLeft where present. Next steps:

- Build a canonical trial table model.
- Add psychometric fitting: bias, threshold, lapse rates, confidence intervals.
- Add chronometric curves: response/reaction time by signed contrast and correctness.
- Add training status using subject/session history.
- Add cross-lab comparison tools with QC-aware aggregation.

## 8. Neural Data Design

The neural layer should model probe insertions, channels, clusters, spikes, LFP, and brain regions. Current support detects spike/cluster datasets, loads simple cluster labels/acronyms, and counts spikes around events. Next steps:

- Add chunked spike loading and controlled return sizes.
- Add good-unit filtering from `clusters.metrics.pqt` and labels.
- Add region-aware unit selection using channels/trajectories.
- Add LFP availability and event-aligned LFP snippets.

## 9. Multimodal Alignment Design

Current alignment tools support wheel/lick signals and spike counts around trial events. The mature design should:

- Normalize all event names through a trial-event ontology.
- Return peri-event matrices with binning options.
- Support condition splits: correct/error, left/right, contrast, probabilityLeft.
- Align pose/pupil/video features once parquet support is added.

## 10. QC And Provenance Strategy

All high-level tools now return:

- `data`: structured result
- `qc`: warnings with risk, code, message, affected fields
- `provenance`: source, Alyx URL, endpoint, session id, dataset ids/names
- `next_actions`: agent-friendly follow-up suggestions

The next QC step is a normalized score:

```text
session_qc + dataset_exists + insertion_qc + cluster_qc + missing_modality_flags -> confidence score
```

No high-level analysis result should be returned without warnings when expected arrays are absent.

## 11. Paper / Code Linkage Strategy

Current implementation includes a static curated registry for core IBL behavior, brain-wide map, and repeated-site resources. Next steps:

- Store DOI, BibTeX, abstracts, projects, release tags, data UUIDs, and GitHub repos.
- Add live GitHub release/readme retrieval.
- Link release tags and project names to papers.
- Link sessions to papers through projects/tags once the metadata cache is available.

## 12. Semantic Search Design

Current implementation provides a deterministic lexical semantic scaffold over dataset ontology and papers. It is intentionally honest: not embeddings yet. Future implementation:

- Create documents for sessions, subjects, labs, projects, dataset types, brain regions, papers, and behavioral summaries.
- Embed with configurable provider.
- Store vectors locally.
- Support `semantic_search`, `find_similar_sessions`, `find_similar_behavior`, and `find_similar_papers`.

## 13. Knowledge Graph Schema

Proposed node labels:

- `Session`
- `Subject`
- `Lab`
- `Project`
- `TaskProtocol`
- `Dataset`
- `DatasetType`
- `Collection`
- `ProbeInsertion`
- `Trajectory`
- `Channel`
- `BrainRegion`
- `QCState`
- `BehaviorSummary`
- `Publication`
- `Repository`
- `Protocol`

Proposed edges:

- `Session HAS_SUBJECT Subject`
- `Session FROM_LAB Lab`
- `Session IN_PROJECT Project`
- `Session USES_TASK_PROTOCOL TaskProtocol`
- `Session HAS_DATASET Dataset`
- `Dataset HAS_TYPE DatasetType`
- `Dataset IN_COLLECTION Collection`
- `Session HAS_PROBE_INSERTION ProbeInsertion`
- `ProbeInsertion HAS_TRAJECTORY Trajectory`
- `ProbeInsertion HAS_CHANNEL Channel`
- `Channel IN_BRAIN_REGION BrainRegion`
- `Session HAS_QC QCState`
- `Project LINKED_TO_PAPER Publication`
- `Publication HAS_CODE Repository`

## 14. Implemented Code Changes

Implemented in this pass:

- Added Pydantic response/QC/provenance schemas.
- Added domain service layer for neuroscience-aware outputs.
- Added dataset ontology for trials, wheel, licks, video, pose, pupil, spikes, clusters, and LFP.
- Added behavior summaries, psychometric summaries, trial loading, wheel/lick loading, video metadata, spike metadata, cluster QC, behavior alignment, and spike-event alignment.
- Added paper/code lookup scaffold.
- Added semantic search scaffold.
- Added knowledge graph query scaffold.
- Added Dockerfile.
- Expanded tests.

## 15. Test Results

Latest local test command:

```bash
uv --cache-dir .uv-cache run --extra dev pytest
```

Latest result:

```text
13 passed
```

## 16. Deployment Instructions

Local:

```bash
uv sync --extra dev
uv run ibl-mcp
```

MCP Inspector:

```bash
uv run mcp dev src/ibl_mcp/server.py
```

Docker:

```bash
docker build -t ibl-mcp-server .
docker run --rm -i -v "$PWD/data:/data" ibl-mcp-server
```

Environment variables:

- `IBL_ALYX_BASE_URL`
- `IBL_ALYX_TIMEOUT`
- `IBL_ALYX_TOKEN`
- `IBL_ALYX_USERNAME`
- `IBL_ALYX_PASSWORD`
- `IBL_MCP_DOWNLOAD_DIR`

## 17. Roadmap For Broader Neurodata Integration

DANDI:

- Link IBL sessions/assets to DANDI NWB where available.
- Add NWB readers for trials, units, electrodes, and acquisitions.
- Share graph entities between DANDI Dandisets and IBL Alyx sessions.

OpenNeuro:

- Add BIDS dataset search and subject/session/task indexing.
- Cross-map BIDS tasks to IBL task protocol concepts.

NWB:

- Add PyNWB optional extra.
- Normalize NWB trials/units/electrodes into the same tool envelope as IBL ALF arrays.

Brainlife:

- Add app/pipeline provenance nodes.
- Link derived outputs to source sessions/datasets.

Allen Brain Atlas:

- Add Allen region ontology lookup and hierarchy traversal.
- Support parent/child region expansion for probe/channel searches.
- Add coordinate-to-region and region-to-sessions graph queries.
