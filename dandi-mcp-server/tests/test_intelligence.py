from __future__ import annotations

from dandi_mcp.intelligence import (
    build_knowledge_graph,
    extract_literature_links,
    semantic_rank,
    summarize_neuroscience_metadata,
)


def test_neuroscience_summary_extracts_behavior_modalities_and_nwb_paths() -> None:
    metadata = {
        "identifier": "000001",
        "name": "Mouse visual decision task with Neuropixels",
        "description": "Mice perform a go/no-go visual stimulus task for water reward.",
        "citation": "Example et al. https://doi.org/10.1234/example.paper",
        "about": [{"name": "visual cortex"}],
    }
    assets = [
        {"path": "sub-M1/ses-20200101/sub-M1_ses-20200101_task-visual.nwb"},
        {"path": "sub-M2/ses-20200102/behavior_video.mp4"},
    ]

    summary = summarize_neuroscience_metadata(metadata, assets)

    assert summary["species"] == ["mouse"]
    assert "extracellular electrophysiology" in summary["modalities"]
    assert "decision making" in summary["behaviors"]
    assert "licking" in summary["behaviors"]
    assert summary["brain_regions"] == ["visual cortex"]
    assert summary["nwb"]["nwb_asset_count"] == 1
    assert summary["nwb"]["likely_tasks_from_paths"] == ["task-visual"]
    assert summary["literature"][0]["kind"] == "doi"


def test_semantic_rank_uses_ontology_overlap() -> None:
    records = [
        {"identifier": "000001", "name": "Mouse Neuropixels reward task"},
        {"identifier": "000002", "name": "Human fMRI resting state"},
    ]

    matches = semantic_rank("mouse ephys reward behavior", records)

    assert matches[0].record["identifier"] == "000001"
    assert "mouse" in matches[0].matched_terms


def test_literature_extraction_handles_related_resources_and_code_links() -> None:
    metadata = {
        "citation": "A paper 10.5555/ABC.DEF and code https://github.com/example/repo",
        "relatedResource": [
            {
                "identifier": "10.7777/protocol.paper",
                "relation": "dcite:IsSupplementTo",
            }
        ],
    }

    links = extract_literature_links(metadata)
    kinds = {link["kind"] for link in links}

    assert "doi" in kinds
    assert "github" in kinds
    assert "dcite:IsSupplementTo" in kinds


def test_knowledge_graph_connects_dataset_to_scientific_entities() -> None:
    metadata = {
        "identifier": "000003",
        "name": "Rat hippocampus navigation",
        "description": "Rat spatial navigation in a maze with extracellular electrophysiology.",
    }

    graph = build_knowledge_graph(metadata)

    node_ids = {node["id"] for node in graph["nodes"]}
    edge_types = {edge["type"] for edge in graph["edges"]}
    assert "dandiset:000003" in node_ids
    assert "species:rat" in node_ids
    assert "brain_regions:hippocampus" in node_ids
    assert "STUDIES_BEHAVIOR" in edge_types
