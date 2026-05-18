from __future__ import annotations

import io
import json
import textwrap
import zipfile
from typing import Any


def build_skill_zip(
    *,
    dataset_id: str,
    summary: dict[str, Any],
    variables: list[dict[str, Any]],
    explanations: list[dict[str, Any]],
    papers: list[dict[str, Any]],
    overview: str | None,
    skill_status: dict[str, Any] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    provider = str(summary.get("provider") or "dandi").lower()
    clean_dataset_id = dataset_id
    if clean_dataset_id.startswith(f"{provider}-"):
        clean_dataset_id = clean_dataset_id[len(provider) + 1 :]
    skill_name = f"{provider}-{clean_dataset_id}-explorer"
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        dataset_context = {
            "provider": provider,
            "dataset_id": dataset_id,
            "summary": summary,
            "overview": overview,
            "variables": variables,
            "variable_explanations": explanations,
            "papers": papers,
            "skill_status": skill_status or {},
        }
        archive.writestr(
            f"{skill_name}/SKILL.md",
            _skill_md(
                dataset_id=dataset_id,
                summary=summary,
                overview=overview,
                variables=variables,
                explanations=explanations,
                skill_status=skill_status or {},
            ),
        )
        archive.writestr(
            f"{skill_name}/CHATGPT.md",
            _chatgpt_md(dataset_id=dataset_id, summary=summary, variables=variables, explanations=explanations),
        )
        archive.writestr(
            f"{skill_name}/PROMPT.md",
            _prompt_md(dataset_id=dataset_id, summary=summary),
        )
        archive.writestr(
            f"{skill_name}/references/dataset-context.json",
            json.dumps(dataset_context, indent=2, sort_keys=True, default=str) + "\n",
        )
        archive.writestr(
            f"{skill_name}/references/dataset-summary.md",
            _dataset_summary_md(dataset_id=dataset_id, summary=summary, overview=overview),
        )
        archive.writestr(
            f"{skill_name}/references/variables.json",
            json.dumps(variables, indent=2, sort_keys=True, default=str) + "\n",
        )
        archive.writestr(
            f"{skill_name}/references/variable-explanations.json",
            json.dumps(explanations, indent=2, sort_keys=True, default=str) + "\n",
        )
        archive.writestr(
            f"{skill_name}/references/variable-guide.md",
            _variable_guide_md(explanations=explanations),
        )
        archive.writestr(
            f"{skill_name}/references/papers.json",
            json.dumps(papers, indent=2, sort_keys=True, default=str) + "\n",
        )
        archive.writestr(f"{skill_name}/scripts/load_variable.py", _loader_script())
    return buffer.getvalue()


def _skill_md(
    *,
    dataset_id: str,
    summary: dict[str, Any],
    overview: str | None,
    variables: list[dict[str, Any]],
    explanations: list[dict[str, Any]],
    skill_status: dict[str, Any],
) -> str:
    title = summary.get("name") or f"DANDI {dataset_id}"
    provider = str(summary.get("provider") or "dandi").lower()
    provider_label = {"dandi": "DANDI", "openneuro": "OpenNeuro", "ibl": "IBL"}.get(provider, provider)
    description = (
        f"Use when working with {provider_label} dataset {dataset_id}, including its variables, data files, "
        "metadata, papers, loading code, and reuse planning."
    )
    return _clean_markdown(
        f"""\
        ---
        name: {provider}-{dataset_id}-explorer
        description: {description}
        ---

        # {title}

        This skill contains a complete, dataset-specific context pack for {provider_label} `{dataset_id}`.
        It was exported only after every indexed variable had a cached explanation.

        ## Cached Context Coverage

        - Provider: `{provider_label}`
        - Dataset: `{dataset_id}`
        - Variables indexed: {len(variables)}
        - Variable explanations included: {len(explanations)}
        - Export readiness: {skill_status.get("message") or "complete"}

        ## Workflow

        1. Read `references/dataset-summary.md` first for the dataset overview, citation, license, and route.
        2. Read `references/variable-guide.md` for human-readable explanations, loading code, and caveats for every variable.
        3. Search `references/variables.json` for exact NWB object paths, shapes, rates, units, and source files.
        4. Search `references/variable-explanations.json` when you need structured evidence, confidence labels, or exact context fields.
        5. Use `scripts/load_variable.py` as the loading-code template for local NWB files.
        6. Read `references/papers.json` when a question needs publication or provenance context.
        7. State uncertainty clearly when a claim is not supported by the bundled references.

        ## Using This Outside The Web App

        This export is self-contained. A user can upload `CHATGPT.md`, `PROMPT.md`,
        `references/dataset-summary.md`, `references/variable-guide.md`,
        `references/variables.json`, `references/variable-explanations.json`, and
        `references/papers.json` into ChatGPT or another assistant. The assistant should
        answer from the bundled context first and should not call the web service.

        ## Dataset Overview

        {overview or "No generated overview was available when this skill was exported."}

        ## Variable Inventory

        {_variable_inventory_block(variables)}
        """
    )


def _chatgpt_md(
    *,
    dataset_id: str,
    summary: dict[str, Any],
    variables: list[dict[str, Any]],
    explanations: list[dict[str, Any]],
) -> str:
    title = summary.get("name") or f"DANDI {dataset_id}"
    return _clean_markdown(
        f"""\
        # Using This Dataset Pack With ChatGPT

        This folder is a standalone context pack for DANDI `{dataset_id}`:
        **{title}**.

        You do not need the Neurodata Without Barriers web app to use it. Upload the
        files below into ChatGPT, a custom GPT knowledge base, Claude Projects, another
        coding assistant, or any retrieval system that accepts Markdown/JSON context.

        ## Upload These Files

        Upload these first:

        - `PROMPT.md`
        - `references/dataset-summary.md`
        - `references/variable-guide.md`
        - `references/variables.json`
        - `references/variable-explanations.json`
        - `references/papers.json`

        Optional but useful:

        - `references/dataset-context.json` for one-machine-readable bundle
        - `scripts/load_variable.py` when writing Python code for local NWB files
        - `SKILL.md` if your assistant understands Codex-style skills

        ## What Is Included

        - Dataset metadata, citation, license, and DANDI URL
        - {len(variables)} indexed NWB variables
        - {len(explanations)} variable explanations with loading code
        - Object paths, source files, shapes, rates, units, and neurodata types
        - Evidence snippets and confidence labels
        - Paper links and publication context

        ## How To Ask Good Questions

        Good prompts:

        - "Which variables encode calcium imaging activity, and how do I load them?"
        - "Explain all behavior epoch variables in this dataset."
        - "Write Python code to load `NeuralTrace` from subject m541."
        - "Which variables are useful for aligning behavior with neural activity?"
        - "What caveats should I know before reusing this dataset?"

        ## Grounding Rules For The Assistant

        The assistant should answer only from the uploaded context unless the user
        explicitly asks it to use outside knowledge. When the context is incomplete,
        the assistant should say what is missing. The assistant should preserve exact
        NWB object paths and file names when giving code.
        """
    )


def _prompt_md(*, dataset_id: str, summary: dict[str, Any]) -> str:
    title = summary.get("name") or f"DANDI {dataset_id}"
    return _clean_markdown(
        f"""\
        # Starter Prompt

        You are helping me work with DANDI dataset `{dataset_id}`:
        **{title}**.

        Use the uploaded dataset context files as your source of truth:

        - `references/dataset-summary.md` for the dataset overview, citation, license, and high-level metadata.
        - `references/variable-guide.md` for human-readable explanations and loading code for every indexed variable.
        - `references/variables.json` for exact files, object paths, shapes, rates, units, and neurodata types.
        - `references/variable-explanations.json` for structured evidence, confidence labels, and caveats.
        - `references/papers.json` for publication context.
        - `scripts/load_variable.py` as the template for loading NWB object paths locally.

        Answer from these files first. If a fact is not present in the uploaded context,
        say that it is not available in the context. When writing code, preserve exact
        file paths and NWB object paths. Prefer concise, practical answers that help me
        inspect, load, analyze, or reuse this dataset.
        """
    )


def _dataset_summary_md(*, dataset_id: str, summary: dict[str, Any], overview: str | None) -> str:
    return _clean_markdown(
        f"""\
        # DANDI {dataset_id}

        ## Overview

        {overview or "No generated overview is available."}

        ## Metadata

        - Name: {summary.get("name") or "Unknown"}
        - Version: {summary.get("version") or "draft"}
        - URL: {summary.get("url") or f"https://dandiarchive.org/dandiset/{dataset_id}"}
        - License: {summary.get("license") or "Unknown"}
        - Citation: {summary.get("citation") or "No citation found in the exported metadata."}
        """
    )


def _clean_markdown(text: str) -> str:
    dedented = textwrap.dedent(text)
    lines = dedented.splitlines()
    first = next((line for line in lines if line.strip()), "")
    indent = len(first) - len(first.lstrip(" "))
    if indent:
        lines = [line[indent:] if line.startswith(" " * indent) else line for line in lines]
    return "\n".join(lines).lstrip() + "\n"


def _variable_inventory_block(variables: list[dict[str, Any]]) -> str:
    lines = []
    for variable in variables:
        name = variable.get("name") or variable.get("variable") or variable.get("object_path") or "variable"
        file = variable.get("file") or variable.get("file_path") or "unknown file"
        object_path = variable.get("object_path") or "metadata-only"
        neurodata_type = variable.get("neurodata_type") or variable.get("kind") or "unknown"
        shape = variable.get("shape")
        unit = variable.get("unit") or variable.get("units")
        details = [f"type={neurodata_type}"]
        if shape is not None:
            details.append(f"shape={shape}")
        if unit:
            details.append(f"unit={unit}")
        lines.append(f"- `{name}` in `{file}` at `{object_path}` ({', '.join(details)})")
    return "\n".join(lines) if lines else "No variables were included."


def _variable_guide_md(*, explanations: list[dict[str, Any]]) -> str:
    lines = ["# Variable Guide", ""]
    for item in explanations:
        variable = item.get("variable") or "variable"
        context = item.get("context") or {}
        file = context.get("file") or context.get("file_path") or "unknown file"
        object_path = context.get("object_path") or "metadata-only"
        confidence = item.get("confidence_label") or "unknown"
        lines.extend(
            [
                f"## {variable}",
                "",
                f"- File: `{file}`",
                f"- Object path: `{object_path}`",
                f"- Confidence: `{confidence}`",
                "",
                "### Explanation",
                "",
                str(item.get("explanation") or "No explanation was included."),
                "",
                "### Loading Code",
                "",
                "```python",
                str(item.get("loading_code") or "# No loading code was included."),
                "```",
                "",
                "### Evidence",
                "",
            ]
        )
        evidence = item.get("evidence") or []
        if evidence:
            for evidence_item in evidence[:5]:
                title = evidence_item.get("title") or evidence_item.get("source_type") or "evidence"
                quote = evidence_item.get("quote") or ""
                lines.append(f"- **{title}**: {quote}")
        else:
            lines.append("- No evidence was included.")
        lines.append("")
    return "\n".join(lines)


def _loader_script() -> str:
    return textwrap.dedent(
        """\
        #!/usr/bin/env python
        from __future__ import annotations

        import argparse

        from pynwb import NWBHDF5IO


        def main() -> None:
            parser = argparse.ArgumentParser(description="Load an NWB object by object path.")
            parser.add_argument("nwb_path")
            parser.add_argument("object_path", help="Example: /acquisition/lick_times")
            args = parser.parse_args()

            with NWBHDF5IO(args.nwb_path, "r", load_namespaces=True) as io:
                nwb = io.read()
                obj = nwb
                for part in args.object_path.strip("/").split("/"):
                    if hasattr(obj, part):
                        obj = getattr(obj, part)
                    else:
                        obj = obj[part]
                print(obj)
                if hasattr(obj, "data"):
                    print("data shape:", getattr(obj.data, "shape", None))
                    print("first values:", obj.data[:10])


        if __name__ == "__main__":
            main()
        """
    )
