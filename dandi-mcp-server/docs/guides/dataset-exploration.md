# Dataset Exploration

This workflow helps an agent move from a broad scientific question to specific reusable assets.

## 1. Search Broadly

Use `search_dandisets` with concise topic, organism, modality, and brain-area terms.

Good search terms:

- `motor cortex`
- `visual cortex calcium imaging`
- `hippocampus electrophysiology`
- `mouse behavior`

## 2. Compare Candidates

For each candidate, inspect:

- Dandiset ID and name.
- Draft and published version summaries.
- Asset count and total size.
- Contributors and citation.
- License.
- Measurement technique and anatomy metadata when present.

Useful tools:

- `get_dandiset`
- `list_dandiset_versions`
- `summarize_dandiset`

## 3. Prefer Stable Versions

Use published versions for reproducible work. Draft is acceptable for exploration, but the agent should label it as draft.

## 4. Browse Organization

Use `list_asset_paths` at the root first. Then browse subject/session prefixes.

Example prompt:

```text
Use dandi to browse the root of Dandiset 000006 draft and identify whether assets are organized by subject or session.
```

## 5. Filter Assets

Use `list_assets` with `glob`, `path`, or metadata flags.

Examples:

```text
List NWB assets in Dandiset 000006 draft with page size 20.
```

```text
List assets under path sub-anm369962/ in Dandiset 000006 draft.
```

## 6. Inspect Before Download

Use:

- `get_asset_metadata`
- `get_asset_info`
- `get_asset_validation`
- `get_version_asset_metadata`

The agent should report:

- Asset UUID.
- Asset path.
- Size.
- Validation status or validation errors.
- Exact Dandiset/version.
- Whether the asset appears relevant to the research question.

## 7. Resolve Download URL Last

Only call `get_asset_download_url` or `get_version_asset_download_url` after the asset is likely relevant.

!!! tip
    Keep asset inspection separate from download. This makes the agent cheaper, faster, and less likely to pull huge files accidentally.

