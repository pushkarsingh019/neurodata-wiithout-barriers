Use the configured MCP servers only.

Demo task: visually explore DANDI:001097/0.240814.1849.

Required behavior:

1. Call the DANDI `generate_dataset_explorer` tool with:
   - `dataset_key_or_id`: `001097`
   - `version_or_tag`: `0.240814.1849`
   - `include_papers`: `true`
   - `open_in_browser`: `true`
2. Do not make PNG plots, matplotlib figures, notebooks, or ad hoc scripts.
3. After the tool returns, report:
   - `html_path`
   - `file_url`
   - `opened`
   - `summary.variable_count`
   - `summary.paper_count`
4. If `opened` is false, tell the user to open `file_url` or run `open_command`.
5. If the user asks about a clicked variable, call `explain_dataset_variable` with the selected variable name, file path, object path, and `full_text_policy: "auto"`.

Expected demo outcome: the browser opens a static HTML dataset explorer with selectable NWB variables, paper context, and copyable MCP calls.
