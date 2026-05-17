# MCP Tool Catalog

| Tool | Purpose |
| --- | --- |
| `search_datasets` | Keyword/list search through OpenNeuro GraphQL |
| `semantic_search` | Vector search over indexed semantic objects |
| `ontology_search` | Concept-normalized search combining query, modality, species, and paradigm |
| `modality_search` | Search by fMRI, MRI, EEG, MEG, iEEG, PET, behavior, video, derivatives |
| `species_search` | Search by human, mouse, rat, macaque, or other normalized species |
| `task_search` | Search by BIDS task or task-like metadata |
| `behavioral_paradigm_search` | Search by behavioral paradigms and assays |
| `author_search` | Search by author |
| `institution_search` | Search by institution or consortium |
| `get_dataset_metadata` | Enriched metadata, DOI, authors, modalities, paradigms, quality, provenance |
| `get_dataset_files` | BIDS-classified OpenNeuro snapshot file trees |
| `get_related_papers` | DOI/reference extraction and literature enrichment plan |
| `find_similar_datasets` | Graph-based related dataset retrieval |
| `find_behavioral_paradigms` | Paradigm inference from text and optional dataset files |
| `get_modalities` | Dataset modality inference |
| `get_task_structure` | Task and event file summary |
| `get_subject_info` | `participants.tsv` parsing |
| `get_events` | Concrete `events.tsv` parsing |
| `get_derivatives` | Derivative/preprocessing discovery |
| `get_analysis_pipelines` | Pipeline inference from derivatives |
| `get_associated_code` | GitHub/code link extraction |
| `get_dataset_embedding` | Dataset embedding vector |
| `query_knowledge_graph` | Graph traversal over indexed entities |
| `get_openneuro_mcp_roadmap` | Architecture and integration roadmap |

## Local Dataset Explorer

| Tool | Purpose |
| --- | --- |
| `register_local_dataset` | Register a downloaded local OpenNeuro/BIDS dataset by path or dataset id |
| `list_local_datasets` | List registered local OpenNeuro/BIDS datasets |
| `summarize_local_dataset` | Summarize local files, subjects, sessions, tasks, modalities, participants, and events |
| `browse_local_dataset` | Browse direct child files and folders inside a local dataset |
| `list_local_files` | Filter local BIDS files by glob, file type, subject, and limit |
| `index_local_dataset` | Build a local BIDS index over subjects, sessions, tasks, events, and modality inventory |
| `get_dataset_subjects` | Return detected subjects from the local index |
| `get_dataset_sessions` | Return detected sessions from the local index |
| `get_dataset_signal_inventory` | Return local file/signal inventory with modality, suffix, task, and subject fields |
| `extract_events_table` | Extract a bounded preview of a local `events.tsv` file |
| `generate_dataset_report` | Generate a Markdown report under MCP artifact storage |
