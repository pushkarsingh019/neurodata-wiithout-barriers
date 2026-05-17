# DANDI MCP

The DANDI MCP server provides structured MCP access to the DANDI Archive and a local analysis layer for downloaded Dandisets. It is useful before download, during asset selection, and after download when users need to understand local NWB files.

## What It Is For

Use the DANDI MCP when you need to:

- Search Dandisets by topic, organism, modality, behavior, or brain region.
- Inspect Dandiset metadata, versions, citations, contributors, licenses, and schema fields.
- Browse asset paths before downloading large files.
- Inspect asset metadata and validation state.
- Resolve time-limited download URLs.
- Inspect Zarr archive metadata and files.
- Register a downloaded Dandiset locally.
- Inspect local NWB files with PyNWB.
- Run NWBInspector validation.
- Build a cross-file dataset index of subjects, sessions, trials, units, processing modules, and signals.
- Generate a Markdown report for a downloaded Dandiset.
- Explain NWB variables with uncertainty-aware evidence from DANDI metadata, real literature APIs, and open-access or user-registered PDFs.
- Generate a static HTML dataset explorer for clicking through NWB variables.

## Remote Archive Tools

DANDI archive tools are read-oriented by default:

| Area | Representative tools |
| --- | --- |
| Discovery | `search_dandisets`, `search_datasets`, `semantic_search_dandisets` |
| Metadata | `get_dandiset`, `list_dandiset_versions`, `get_dandiset_version_metadata`, `summarize_dandiset` |
| Assets | `list_assets`, `list_asset_paths`, `get_asset_metadata`, `get_asset_info`, `get_asset_validation` |
| Downloads | `get_asset_download_url`, `get_version_asset_download_url` |
| Zarr | `list_zarr_archives`, `get_zarr_archive`, `list_zarr_files` |
| Neuroscience intelligence | `analyze_dandiset_neuroscience`, `get_related_papers`, `resolve_dataset_papers`, `query_dataset_papers`, `explain_dataset_variable`, `find_similar_datasets`, `get_dandiset_knowledge_graph` |
| Visual exploration | `generate_dataset_explorer`, `explain_visual_dataset_selection` |
| Escape hatch | `call_dandi_api` |

Mutating tools exist for authenticated archive workflows, but they are guarded by explicit confirmation flags.

## Local Dataset Tools

DANDI supports the shared local explorer names:

```text
register_local_dataset
list_local_datasets
summarize_local_dataset
browse_local_dataset
list_local_files
index_local_dataset
get_dataset_subjects
get_dataset_sessions
get_dataset_signal_inventory
generate_dataset_report
```

It also keeps DANDI-specific aliases:

```text
register_local_dandiset
list_local_dandisets
summarize_local_dandiset
browse_local_dandiset
index_local_dandiset
```

## Local NWB Tools

DANDI has additional NWB-specific tools:

| Tool | Purpose |
| --- | --- |
| `inspect_nwb_file` | Lazily summarize a local NWB file, including subject metadata, acquisition, stimulus, processing modules, intervals, trials, units, and time series |
| `validate_nwb_file` | Run NWBInspector and return bounded validation messages |
| `extract_trials_table` | Return a bounded preview of the NWB trials table when present |

The implementation avoids loading full arrays by default. It reads shapes, object names, metadata, rates, units, and table schemas first.

## Literature-Aware Variable Explanation

Use `explain_dataset_variable` when an NWB object path, time series name, or table column is unclear. The tool first uses local NWB metadata and DANDI metadata, then resolves associated papers through public APIs such as Semantic Scholar, Crossref, PubMed, Europe PMC, OpenAlex, DataCite, and arXiv. If confidence is low, it attempts open-access full text. If the needed PDF cannot be retrieved, it returns a `pdf_required_but_missing` response with the paper title, DOI or URL, and a `register_paper_pdf` call.

Use `generate_dataset_explorer` to create a static HTML artifact that lists variables, files, papers, confidence status, and copyable MCP calls for clicked variables.

## Example: Explore A Downloaded Dandiset

Register by explicit path:

```json
{
  "path": "/data/001097",
  "dataset_id": "001097"
}
```

Then index and inspect:

```json
{
  "dataset_key": "DANDI_001097_0.240814.1849"
}
```

Useful next calls:

```text
summarize_local_dataset
index_local_dataset
get_dataset_signal_inventory
inspect_nwb_file
validate_nwb_file
generate_dataset_report
```

## Local Output

The DANDI local explorer writes derived artifacts under MCP storage:

```text
<storage-root>/dandi/local-dandisets/<dataset-key>/manifest.json
<storage-root>/dandi/local-dandisets/<dataset-key>/index.json
<storage-root>/dandi/artifacts/<dataset-key>/dataset-report.md
```

Source Dandiset files are not modified.

## Dependencies

The archive API tools require `httpx` and `mcp`. The local NWB tools require PyNWB, h5py, and NWBInspector. Install them with:

```bash
cd dandi-mcp-server
uv sync --extra analysis
```

For development:

```bash
uv sync --extra dev
```

## Current Boundaries

The DANDI local explorer currently focuses on metadata, structure, validation, and bounded table previews. It does not yet perform full numerical analysis, plotting, remote NWB streaming, or arbitrary array extraction. Those are natural next layers on top of the indexed NWB object inventory.
