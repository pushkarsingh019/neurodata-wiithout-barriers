Use the configured MCP servers only.

I want to work with these neuroscience datasets or sessions:

- DANDI dandiset: 000026
- OpenNeuro dataset: ds000001
- IBL/OpenAlyx session: f8787d77-74f9-41c2-bdd6-a1cbd420091a

For each dataset/session:

1. Use the relevant MCP server tools to fetch metadata.
2. Summarize what the dataset/session is, but clearly separate directly observed MCP/tool facts from your interpretation.
3. List the most useful next questions I could ask if I wanted to analyze it.
4. Identify safe small metadata or file download paths.
5. Do not download large data.
6. If a download might be useful, identify the exact MCP tool or command and explain the expected size/risk first.
7. Do not infer modalities, probes, imaging methods, species, task details, or QC conclusions unless they are present in the tool output.

Return:

- A section for DANDI.
- A section for OpenNeuro.
- A section for IBL.
- A final table with dataset, modality, subject/sample scope, useful first files, and download risk.
