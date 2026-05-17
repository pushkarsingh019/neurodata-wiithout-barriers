# Tool Compatibility Matrix

This page compares the common local dataset explorer tools across DANDI, OpenNeuro, and IBL.

## Shared Tools

| Tool | DANDI | OpenNeuro | IBL |
| --- | --- | --- | --- |
| `register_local_dataset` | Yes | Yes | Yes |
| `list_local_datasets` | Yes | Yes | Yes |
| `summarize_local_dataset` | Yes | Yes | Yes |
| `browse_local_dataset` | Yes | Yes | Yes |
| `list_local_files` | Yes | Yes | Yes |
| `index_local_dataset` | Yes | Yes | Yes |
| `get_dataset_subjects` | Yes | Yes | Yes |
| `get_dataset_sessions` | Yes | Yes | Yes |
| `get_dataset_signal_inventory` | Yes | Yes | Yes |
| `generate_dataset_report` | Yes | Yes | Yes |
| `resolve_dataset_papers` | Yes | Yes | Yes |
| `query_dataset_papers` | Yes | Yes | Yes |
| `explain_dataset_variable` | Yes | Yes | Yes |
| `register_paper_pdf` | Yes | Yes | Yes |
| `list_missing_paper_pdfs` | Yes | Yes | Yes |
| `generate_dataset_explorer` | Yes | Yes | Yes |
| `explain_visual_dataset_selection` | Yes | Yes | Yes |

## Provider-Specific Local Tools

| Tool | Provider | Purpose |
| --- | --- | --- |
| `register_local_dandiset` | DANDI | DANDI-specific registration alias |
| `list_local_dandisets` | DANDI | DANDI-specific listing alias |
| `summarize_local_dandiset` | DANDI | DANDI-specific summary alias |
| `browse_local_dandiset` | DANDI | DANDI-specific browser alias |
| `index_local_dandiset` | DANDI | DANDI-specific index alias |
| `inspect_nwb_file` | DANDI | Inspect local NWB metadata, objects, tables, processing modules, and time series |
| `validate_nwb_file` | DANDI | Run NWBInspector on a local NWB file |
| `extract_trials_table` | DANDI | Preview local NWB trials table rows |
| `extract_events_table` | OpenNeuro | Preview local BIDS `events.tsv` rows |

## Same Workflow, Different Semantics

The shared tools intentionally return provider-aware data rather than forcing every provider into one rigid schema.

| Shared concept | DANDI meaning | OpenNeuro meaning | IBL meaning |
| --- | --- | --- | --- |
| Subject | NWB subject metadata or `sub-` path token | BIDS `sub-` entity and participants table | `sub-` path token |
| Session | NWB `session_id`, `ses-` path token, or file stand-in | BIDS `ses-` entity | `ses-` path token or UUID-like path token |
| Signal inventory | NWB time series and analysis objects | BIDS modality files and event/task files | ALF object/attribute files |
| Report | Dandiset/NWB report | BIDS dataset report | IBL/ALF dataset report |
| Index cache | `local-dandisets/<key>/index.json` | `local-datasets/<key>/index.json` | `local-datasets/<key>/index.json` |

## Agent Pattern

Agents should use the shared workflow first:

```text
1. register_local_dataset
2. summarize_local_dataset
3. browse_local_dataset or list_local_files
4. index_local_dataset
5. get_dataset_signal_inventory
6. generate_dataset_report
```

Then branch into provider-specific tools:

- Use DANDI's `inspect_nwb_file` and `validate_nwb_file` for NWB files.
- Use OpenNeuro's `extract_events_table` for local BIDS events.
- Use IBL's remote domain tools when a local ALF file points back to a known session or dataset record.

For literature-aware variable explanation, agents should call `explain_dataset_variable` first. The tool uses dataset metadata, real public literature APIs, abstracts, and open-access PDFs when needed. If the required full text is unavailable, the response includes `missing_pdfs` with the paper title, identifiers, download hints, and an exact `register_paper_pdf` call for the user-provided PDF.

For a visual workflow, call `generate_dataset_explorer`. It creates a static HTML artifact with the dataset summary, variables, papers, confidence badges, and copyable MCP calls for selected variables.
