# Tool Reference

## Discovery

| Tool | Purpose |
|---|---|
| `search_dandisets` | Search or list Dandisets with pagination, ordering, draft, empty, embargoed, user, starred, and search filters. |
| `search_datasets` | Agent-first search across topic, species, modality, behavior, and brain-region terms. |
| `semantic_search_dandisets` | DANDI keyword retrieval followed by local lexical and ontology reranking. |
| `get_dandiset` | Fetch Dandiset-level metadata including draft and recent published summaries. |
| `list_dandiset_versions` | List draft and published versions for a Dandiset. |
| `get_dandiset_version_metadata` | Fetch full DANDI schema metadata for a version. |
| `get_dandiset_version_info` | Fetch Django-serialized version information. |
| `summarize_dandiset` | Return compact version metadata and sample assets. |
| `find_similar_datasets` | Find datasets similar to a source Dandiset using inferred neuroscience profile terms. |
| `find_behavioral_paradigms` | Find candidate datasets with behavioral task, paradigm, trial, stimulus, or reward hints. |

## Local Dataset Explorer

| Tool | Purpose |
|---|---|
| `register_local_dandiset` | Register a downloaded Dandiset by local path, or by DANDI id when it can be found in configured local roots. |
| `register_local_dataset` | Provider-compatible alias for registering a downloaded local DANDI dataset. |
| `list_local_dandisets` | List registered local Dandisets and their scan status. |
| `list_local_datasets` | Provider-compatible alias for listing registered local DANDI datasets. |
| `summarize_local_dandiset` | Summarize local files, metadata, subjects, modalities, NWB count, and index status. |
| `summarize_local_dataset` | Provider-compatible alias for summarizing a registered local DANDI dataset. |
| `browse_local_dandiset` | Browse direct child files and folders in a local Dandiset. |
| `browse_local_dataset` | Provider-compatible alias for browsing a registered local DANDI dataset. |
| `list_local_files` | Filter local files by glob, file type, subject, and limit. |
| `inspect_nwb_file` | Lazily inspect a local NWB file for subject/session metadata, modules, tables, intervals, and time series. |
| `validate_nwb_file` | Run NWBInspector on a local NWB file and return bounded validation messages. |
| `index_local_dandiset` | Build a cross-file subject, session, modality, trial, unit, signal, and validation index from local NWB files. |
| `index_local_dataset` | Provider-compatible alias for indexing a registered local DANDI dataset. |
| `get_dataset_subjects` | Return detected subjects from the local dataset index. |
| `get_dataset_sessions` | Return detected sessions or file-level session stand-ins from the local dataset index. |
| `get_dataset_signal_inventory` | Return local NWB signal object paths, shapes, rates, and units for analysis planning. |
| `extract_trials_table` | Extract a bounded preview of a local NWB trials table when present. |
| `generate_dataset_report` | Generate a Markdown report under MCP artifact storage. |

## Neuroscience Intelligence

| Tool | Purpose |
|---|---|
| `analyze_dandiset_neuroscience` | Extract inferred species, modalities, behaviors, brain regions, literature links, and NWB path hints. |
| `get_related_papers` | Extract DOI, PubMed, Semantic Scholar, GitHub, protocols.io, and related-resource links from DANDI metadata. |
| `get_dandiset_knowledge_graph` | Build an inferred graph of datasets, papers, species, modalities, behaviors, and brain regions. |
| `query_knowledge_graph` | Query the inferred Dandiset graph and return matching nodes plus adjacent edges. |

## Assets

| Tool | Purpose |
|---|---|
| `list_assets` | List assets in a version with path, glob, metadata, Zarr, page, page size, and order filters. |
| `list_asset_paths` | Browse direct child files and folders under a path prefix. |
| `get_asset_metadata` | Fetch global asset metadata by UUID. |
| `get_asset_info_by_id` | Fetch global Django-serialized asset information by UUID. |
| `get_version_asset_metadata` | Fetch version-scoped asset metadata. |
| `get_asset_info` | Fetch version-scoped Django-serialized asset information. |
| `get_asset_validation` | Fetch asset validation state or errors. |
| `get_asset_download_url` | Resolve a time-limited object-store URL by asset UUID. |
| `get_version_asset_download_url` | Resolve a time-limited URL scoped to Dandiset/version/asset. |

## Archive, Schemas, and Users

| Tool | Purpose |
|---|---|
| `get_archive_info` | Fetch DANDI archive service information. |
| `get_archive_stats` | Fetch archive-wide statistics. |
| `get_schema` | Fetch a schema model. |
| `list_available_schemas` | List available schema models. |
| `list_users` | List registered users where allowed. |
| `get_current_user` | Fetch authenticated user metadata. |
| `get_auth_token` | Fetch token information for the configured token. |
| `get_user_questionnaire_form` | Fetch the questionnaire form definition. |
| `search_users` | Search users by username. |
| `list_dandiset_users` | List users/owners for a Dandiset. |

## Zarr

| Tool | Purpose |
|---|---|
| `list_zarr_archives` | List Zarr archives, optionally filtered by Dandiset or name. |
| `get_zarr_archive` | Fetch Zarr archive metadata. |
| `list_zarr_files` | List files in a Zarr archive, optionally requesting download URLs. |

## Mutating Tools

These tools require `confirm=true` and usually require authentication.

| Tool | Purpose |
|---|---|
| `create_auth_token` | Create an auth token. |
| `lookup_blob_by_digest` | Fetch an existing asset blob by digest through the POST endpoint. |
| `create_dandiset` | Create a Dandiset. |
| `delete_dandiset` | Delete a Dandiset. |
| `star_dandiset` | Star a Dandiset. |
| `unstar_dandiset` | Unstar a Dandiset. |
| `unembargo_dandiset` | Unembargo a Dandiset. |
| `delete_dandiset_uploads` | Delete active/incomplete uploads in a Dandiset. |
| `set_dandiset_users` | Set Dandiset owners/users. |
| `update_dandiset_version_metadata` | Update version metadata. |
| `delete_dandiset_version` | Delete a version. |
| `publish_dandiset_version` | Publish a version. |
| `create_version_asset` | Create an asset in a version. |
| `update_version_asset` | Update asset metadata in a version. |
| `delete_version_asset` | Remove an asset from a version. |
| `initialize_upload` | Initialize a multipart upload. |
| `complete_upload` | Complete a multipart upload. |
| `validate_upload` | Validate an upload and mint an AssetBlob. |
| `submit_user_questionnaire` | Submit the user questionnaire form. |
| `create_zarr_archive` | Create a Zarr archive. |
| `request_zarr_file_uploads` | Request file upload operations for Zarr. |
| `delete_zarr_files` | Delete files from a Zarr archive. |
| `finalize_zarr_archive` | Finalize a Zarr archive. |

## Universal Tool

| Tool | Purpose |
|---|---|
| `call_dandi_api` | Call any DANDI API path. Non-GET calls require `allow_mutation=true`. |
