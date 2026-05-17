from openneuro_mcp.bids import (
    classify_file,
    metadata_quality_score,
    parse_bids_entities,
    parse_events_tsv,
    parse_participants_tsv,
)
from openneuro_mcp.models import Modality, Species


def test_parse_bids_entities() -> None:
    entities = parse_bids_entities("sub-01/ses-pre/func/sub-01_ses-pre_task-social_run-1_bold.nii.gz")
    assert entities["sub"] == "01"
    assert entities["ses"] == "pre"
    assert entities["task"] == "social"
    assert entities["run"] == "1"
    assert entities["suffix"] == "bold"


def test_classify_file_modality() -> None:
    assert classify_file("sub-01/func/sub-01_task-rest_bold.nii.gz").modality == Modality.FMRI
    assert classify_file("sub-01/eeg/sub-01_task-oddball_eeg.set").modality == Modality.EEG


def test_parse_participants_tsv() -> None:
    summary = parse_participants_tsv("participant_id\tage\tspecies\nsub-01\t24\thuman\nsub-02\t31\thuman\n")
    assert summary.participant_count == 2
    assert summary.species == Species.HUMAN
    assert "age" in summary.columns


def test_parse_events_tsv_infers_paradigm() -> None:
    content = "onset\tduration\ttrial_type\tresponse\n0\t1\tgo\tlick\n2\t1\tno-go\twithhold\n"
    structure = parse_events_tsv("go-nogo", content)
    assert structure.onset_range_seconds == (0.0, 2.0)
    assert any(item.normalized_name == "go/no-go" for item in structure.inferred_paradigms)


def test_metadata_quality_score_detects_missing_fields() -> None:
    quality = metadata_quality_score({"Name": "Example"}, [classify_file("sub-01/func/sub-01_task-rest_bold.nii.gz")])
    assert quality["score"] < 1.0
    assert "BIDSVersion" in quality["missing_required_description_fields"]
