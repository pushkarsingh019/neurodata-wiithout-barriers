from openneuro_mcp.embeddings import InMemoryVectorIndex, cosine_similarity, embed_text
from openneuro_mcp.graph import NeuroscienceKnowledgeGraph
from openneuro_mcp.models import DatasetMetadata, Modality, Species
from openneuro_mcp.ontology import infer_modalities, infer_paradigms, infer_species


def test_ontology_inference() -> None:
    assert Modality.FMRI in infer_modalities(["human fMRI social cognition BOLD task"])
    species, confidence = infer_species(["Mus musculus mouse reward task"])
    assert species == Species.MOUSE
    assert confidence.value > 0.5
    paradigms = infer_paradigms(["two alternative forced choice reward licking"])
    assert {item.normalized_name for item in paradigms} >= {"two-alternative forced choice", "reward learning", "licking"}


def test_embeddings_are_normalized_and_searchable() -> None:
    first = embed_text("reward learning fMRI")
    second = embed_text("reward decision fMRI")
    assert 0.0 <= cosine_similarity(first, second) <= 1.0
    index = InMemoryVectorIndex()
    index.upsert("ds1", "reward learning fMRI", {"name": "Reward"})
    index.upsert("ds2", "resting state anatomy", {"name": "Rest"})
    assert index.search("reward task", limit=1)[0]["id"] == "ds1"


def test_knowledge_graph_related_datasets() -> None:
    graph = NeuroscienceKnowledgeGraph()
    graph.ingest_dataset(
        DatasetMetadata(
            id="ds000001",
            name="A",
            modalities=[Modality.FMRI],
            species=Species.HUMAN,
            authors=["Ada"],
        )
    )
    graph.ingest_dataset(
        DatasetMetadata(
            id="ds000002",
            name="B",
            modalities=[Modality.FMRI],
            species=Species.HUMAN,
            authors=["Grace"],
        )
    )
    related = graph.related_datasets("ds000001")
    assert related[0]["dataset_id"] == "ds000002"
