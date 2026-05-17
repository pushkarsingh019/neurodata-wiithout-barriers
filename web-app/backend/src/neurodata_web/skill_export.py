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
    papers: list[dict[str, Any]],
    overview: str | None,
) -> bytes:
    buffer = io.BytesIO()
    skill_name = f"dandi-{dataset_id}-explorer"
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{skill_name}/SKILL.md",
            _skill_md(dataset_id=dataset_id, summary=summary, overview=overview),
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
            f"{skill_name}/references/papers.json",
            json.dumps(papers, indent=2, sort_keys=True, default=str) + "\n",
        )
        archive.writestr(f"{skill_name}/scripts/load_variable.py", _loader_script())
    return buffer.getvalue()


def _skill_md(*, dataset_id: str, summary: dict[str, Any], overview: str | None) -> str:
    title = summary.get("name") or f"DANDI {dataset_id}"
    description = (
        f"Use when working with DANDI dataset {dataset_id}, including its variables, NWB files, "
        "metadata, papers, loading code, and reuse planning."
    )
    return textwrap.dedent(
        f"""\
        ---
        name: dandi-{dataset_id}-explorer
        description: {description}
        ---

        # {title}

        This skill contains a compact, dataset-specific context pack for DANDI `{dataset_id}`.

        ## Workflow

        1. Read `references/dataset-summary.md` first for the dataset overview, citation, license, and route.
        2. Search `references/variables.json` for the requested variable, NWB object path, modality, units, or source file.
        3. Use `scripts/load_variable.py` as the loading-code template for local NWB files.
        4. Read `references/papers.json` only when a question needs publication or provenance context.
        5. State uncertainty clearly when the references do not explain a variable or protocol.

        ## Dataset Overview

        {overview or "No generated overview was available when this skill was exported."}
        """
    )


def _dataset_summary_md(*, dataset_id: str, summary: dict[str, Any], overview: str | None) -> str:
    return textwrap.dedent(
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

