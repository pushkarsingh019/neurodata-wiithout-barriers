# DANDI API Coverage

This project targets the DANDI Archive Swagger/OpenAPI document at:

`https://api.dandiarchive.org/api/docs/swagger/?format=openapi`

Snapshot checked during implementation: 36 paths, 51 operations.

## Coverage Policy

- Public/read operations are exposed as named MCP tools.
- Authenticated read operations are also exposed as named tools, but may return DANDI auth errors unless `DANDI_API_TOKEN` or `DANDI_API_KEY` is set.
- Mutating operations are exposed as named tools with `confirm: false` by default. They return a blocked response until called with `confirm: true`.
- The `call_dandi_api` tool can call any current or future DANDI API path. Non-GET calls require `allow_mutation: true`.

## Named Tool Coverage

| API operation | Method | Path | MCP coverage |
|---|---:|---|---|
| `assets_read` | GET | `/assets/{asset_id}/` | `get_asset_metadata` |
| `assets_download` | GET | `/assets/{asset_id}/download/` | `get_asset_download_url` |
| `assets_info` | GET | `/assets/{asset_id}/info/` | `get_asset_info_by_id` |
| `auth_token_list` | GET | `/auth/token/` | `get_auth_token` |
| `auth_token_create` | POST | `/auth/token/` | `create_auth_token` |
| `blobs_digest_create` | POST | `/blobs/digest/` | `lookup_blob_by_digest` |
| `dandisets_list` | GET | `/dandisets/` | `search_dandisets` |
| `dandisets_create` | POST | `/dandisets/` | `create_dandiset` |
| `dandisets_read` | GET | `/dandisets/{dandiset__pk}/` | `get_dandiset` |
| `dandisets_delete` | DELETE | `/dandisets/{dandiset__pk}/` | `delete_dandiset` |
| `dandisets_star_create` | POST | `/dandisets/{dandiset__pk}/star/` | `star_dandiset` |
| `dandisets_star_delete` | DELETE | `/dandisets/{dandiset__pk}/star/` | `unstar_dandiset` |
| `dandisets_unembargo` | POST | `/dandisets/{dandiset__pk}/unembargo/` | `unembargo_dandiset` |
| `dandisets_uploads_read` | GET | `/dandisets/{dandiset__pk}/uploads/` | `list_dandiset_uploads` |
| `dandisets_uploads_delete` | DELETE | `/dandisets/{dandiset__pk}/uploads/` | `delete_dandiset_uploads` |
| `dandisets_users_read` | GET | `/dandisets/{dandiset__pk}/users/` | `list_dandiset_users` |
| `dandisets_users_update` | PUT | `/dandisets/{dandiset__pk}/users/` | `set_dandiset_users` |
| `dandisets_versions_list` | GET | `/dandisets/{dandiset__pk}/versions/` | `list_dandiset_versions` |
| `dandisets_versions_read` | GET | `/dandisets/{dandiset__pk}/versions/{version}/` | `get_dandiset_version_metadata` |
| `dandisets_versions_update` | PUT | `/dandisets/{dandiset__pk}/versions/{version}/` | `update_dandiset_version_metadata` |
| `dandisets_versions_delete` | DELETE | `/dandisets/{dandiset__pk}/versions/{version}/` | `delete_dandiset_version` |
| `dandisets_versions_info` | GET | `/dandisets/{dandiset__pk}/versions/{version}/info/` | `get_dandiset_version_info` |
| `dandisets_versions_publish` | POST | `/dandisets/{dandiset__pk}/versions/{version}/publish/` | `publish_dandiset_version` |
| `dandisets_versions_assets_list` | GET | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/` | `list_assets` |
| `dandisets_versions_assets_create` | POST | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/` | `create_version_asset` |
| `dandisets_versions_assets_paths` | GET | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/paths/` | `list_asset_paths` |
| `dandisets_versions_assets_read` | GET | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/{asset_id}/` | `get_version_asset_metadata` |
| `dandisets_versions_assets_update` | PUT | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/{asset_id}/` | `update_version_asset` |
| `dandisets_versions_assets_delete` | DELETE | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/{asset_id}/` | `delete_version_asset` |
| `dandisets_versions_assets_download` | GET | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/{asset_id}/download/` | `get_version_asset_download_url` |
| `dandisets_versions_assets_info` | GET | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/{asset_id}/info/` | `get_asset_info` |
| `dandisets_versions_assets_validation` | GET | `/dandisets/{versions__dandiset__pk}/versions/{versions__version}/assets/{asset_id}/validation/` | `get_asset_validation` |
| `info_list` | GET | `/info/` | `get_archive_info` |
| `schemas_list` | GET | `/schemas/` | `get_schema` |
| `schemas_available_list` | GET | `/schemas/available/` | `list_available_schemas` |
| `stats_list` | GET | `/stats/` | `get_archive_stats` |
| `uploads_initialize_create` | POST | `/uploads/initialize/` | `initialize_upload` |
| `uploads_complete_create` | POST | `/uploads/{upload_id}/complete/` | `complete_upload` |
| `uploads_validate_create` | POST | `/uploads/{upload_id}/validate/` | `validate_upload` |
| `users_list` | GET | `/users/` | `list_users` |
| `users_me_list` | GET | `/users/me/` | `get_current_user` |
| `users_questionnaire-form_list` | GET | `/users/questionnaire-form/` | `get_user_questionnaire_form` |
| `users_questionnaire-form_create` | POST | `/users/questionnaire-form/` | `submit_user_questionnaire` |
| `users_search_list` | GET | `/users/search/` | `search_users` |
| `zarr_list` | GET | `/zarr/` | `list_zarr_archives` |
| `zarr_create` | POST | `/zarr/` | `create_zarr_archive` |
| `zarr_read` | GET | `/zarr/{zarr_id}/` | `get_zarr_archive` |
| `zarr_files_read` | GET | `/zarr/{zarr_id}/files/` | `list_zarr_files` |
| `zarr_files_create` | POST | `/zarr/{zarr_id}/files/` | `request_zarr_file_uploads` |
| `zarr_files_delete` | DELETE | `/zarr/{zarr_id}/files/` | `delete_zarr_files` |
| `zarr_finalize` | POST | `/zarr/{zarr_id}/finalize/` | `finalize_zarr_archive` |

## Universal Fallback

Use `call_dandi_api` for any endpoint not listed above or for newly added DANDI API paths:

```json
{
  "method": "GET",
  "path": "stats/",
  "query": {},
  "body": null
}
```

For mutating calls:

```json
{
  "method": "POST",
  "path": "dandisets/000001/star/",
  "allow_mutation": true
}
```

