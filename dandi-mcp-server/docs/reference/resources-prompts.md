# Resources and Prompts

## Resources

| Resource | Purpose |
|---|---|
| `dandi://dandisets/recent` | Recently modified non-empty public Dandisets. |
| `dandi://dandiset/{dandiset_id}` | Dandiset summary record. |
| `dandi://dandiset/{dandiset_id}/{version}` | Dandiset version metadata. |
| `dandi://dandiset/{dandiset_id}/{version}/assets` | First page of assets for a version. |
| `dandi://asset/{asset_id}` | Asset metadata. |
| `dandi://archive/info` | Archive service information. |
| `dandi://archive/stats` | Archive statistics. |
| `dandi://schemas/available` | Available DANDI schema models. |
| `dandi://zarr/{zarr_id}` | Zarr archive metadata. |

## Prompts

| Prompt | Purpose |
|---|---|
| `find_relevant_dandisets` | Search strategy for a topic, species, or modality. |
| `explore_dandiset` | Guided workflow for one Dandiset. |
| `inspect_asset_for_reuse` | Checklist for deciding whether a specific asset is useful. |

## Prompt Usage Examples

```text
Use the find_relevant_dandisets prompt for hippocampus electrophysiology in mouse.
```

```text
Use the explore_dandiset prompt for Dandiset 000006 and the question "delay response task electrophysiology".
```

```text
Use the inspect_asset_for_reuse prompt for Dandiset 000006 draft asset a5ad932b-b893-4522-b989-8f406d78e4e0.
```

