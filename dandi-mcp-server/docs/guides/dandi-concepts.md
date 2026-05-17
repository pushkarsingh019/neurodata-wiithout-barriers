# DANDI Concepts

## Dandisets

A Dandiset is the dataset package unit in DANDI. It has an identifier such as `000006`, metadata such as title, contributors, license, citation, experimental context, and one or more versions.

Agents should report Dandiset identifiers exactly. A good answer should say `DANDI:000006`, not merely "the ALM dataset."

## Versions

DANDI has draft and published versions. Draft versions may change. Published versions are better for reproducibility because they are stable archival releases.

When an agent is doing literature-grade or reproducible analysis, it should usually:

1. List versions with `list_dandiset_versions`.
2. Prefer the most recent published version when the needed assets are present.
3. Fall back to `draft` only when the user specifically needs draft content or no published version exists.

## Assets

Assets are files or Zarr assets inside a Dandiset version. Common file formats include NWB for neurophysiology and BIDS-style layouts for imaging or microscopy workflows.

Agents should inspect asset path, size, metadata, and validation state before recommending downloads.

## Paths

DANDI assets often use subject/session-style paths, for example:

```text
sub-anm369962/sub-anm369962_ses-20170309.nwb
```

Use `list_asset_paths` for folder-like browsing and `list_assets` for filtered asset pages.

## Zarr

DANDI supports Zarr archives for large array-style data. Use `list_zarr_archives`, `get_zarr_archive`, and `list_zarr_files` to inspect Zarr metadata and file listings.

## Schemas

DANDI metadata follows schema models. Use `list_available_schemas` and `get_schema` when an agent needs to understand expected metadata fields.

