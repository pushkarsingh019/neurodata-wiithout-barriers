from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """You write clear scientific web-app copy for neuroscience datasets.
Use only the evidence provided by the API. Do not invent protocols, variables, or conclusions.
When evidence is sparse, say what is known and what remains uncertain. Keep prose concise."""


def dataset_overview_prompt(
    *,
    summary: dict[str, Any],
    neuroscience: dict[str, Any],
    papers: list[dict[str, Any]],
) -> str:
    payload = {
        "dandi_summary": summary,
        "neuroscience_hints": neuroscience,
        "papers": papers[:8],
    }
    return (
        "Create a polished dataset overview for a web page. Return markdown with four short sections: "
        "What this dataset is, What is inside, Why it may matter, and Good next steps. "
        "Keep it grounded and under 350 words.\n\nEvidence JSON:\n"
        f"{json.dumps(payload, indent=2, default=str)[:12000]}"
    )


def variable_explanation_prompt(
    *,
    variable: str,
    variable_context: dict[str, Any],
    evidence: list[dict[str, Any]],
    loading_code: str,
) -> str:
    payload = {
        "variable": variable,
        "variable_context": variable_context,
        "evidence": evidence[:8],
        "loading_code": loading_code,
    }
    return (
        "Explain this dataset variable for a scientist who wants to reuse the data. "
        "Return markdown with: Meaning, How to load it, How it was likely generated or recorded, "
        "What to watch out for, and Evidence. Keep it under 450 words. "
        "If the evidence does not support a claim, mark it uncertain.\n\nEvidence JSON:\n"
        f"{json.dumps(payload, indent=2, default=str)[:14000]}"
    )

