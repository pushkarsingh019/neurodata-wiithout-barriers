# Agent Workflows

The server includes MCP prompts that act as lightweight skills for DANDI work.

## `find_relevant_dandisets`

Use this when a user gives a topic, organism, technique, or brain region and wants candidate datasets.

Recommended agent behavior:

1. Search with concise keywords.
2. Summarize top candidates.
3. Prefer published versions and clear citations.
4. Return exact IDs, titles, versions, asset counts, and relevance notes.

## `explore_dandiset`

Use this when a user already has a Dandiset ID.

Recommended agent behavior:

1. Summarize Dandiset metadata.
2. List versions.
3. Browse path organization.
4. List relevant assets.
5. Inspect metadata and validation before download.

## `inspect_asset_for_reuse`

Use this when a user has a particular asset UUID or path.

Recommended agent behavior:

1. Fetch asset metadata and version-scoped info.
2. Check size, path, validation state, and Dandiset license/citation.
3. Explain relevance and caveats.
4. Resolve download URL only if the asset is a good candidate.

## Response Style for Agents

A useful DANDI answer should include:

- Dandiset ID.
- Version.
- Asset UUIDs and paths.
- Citation or dataset URL when available.
- License.
- Any validation caveats.
- Whether the result came from draft or published data.

