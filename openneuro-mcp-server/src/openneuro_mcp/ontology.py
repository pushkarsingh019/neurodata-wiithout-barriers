from __future__ import annotations

from dataclasses import dataclass

from openneuro_mcp.models import BehavioralParadigm, Confidence, Modality, Species


MODALITY_TERMS: dict[Modality, tuple[str, ...]] = {
    Modality.FMRI: ("bold", "func", "fmri", "functional mri", "resting state"),
    Modality.MRI: ("anat", "t1w", "t2w", "mri", "structural"),
    Modality.DIFFUSION_MRI: ("dwi", "diffusion", "dti"),
    Modality.EEG: ("eeg", "electroencephalography"),
    Modality.MEG: ("meg", "magnetoencephalography"),
    Modality.IEEG: ("ieeg", "ecog", "seeg", "intracranial"),
    Modality.PET: ("pet", "positron"),
    Modality.BEHAVIOR: ("beh", "events.tsv", "behavior", "task"),
    Modality.PHYSIOLOGY: ("physio", "stim", "recording", "cardiac", "respiration"),
    Modality.VIDEO: ("video", "movie", "pose", "camera", ".mp4", ".avi"),
    Modality.DERIVATIVE: ("derivatives", "preproc", "fmriprep", "freesurfer", "qsiprep"),
}

SPECIES_TERMS: dict[Species, tuple[str, ...]] = {
    Species.HUMAN: ("human", "homo sapiens", "participant", "subject age", "sex"),
    Species.MOUSE: ("mouse", "mice", "mus musculus", "murine"),
    Species.RAT: ("rat", "rattus", "rattus norvegicus"),
    Species.MACAQUE: ("macaque", "monkey", "macaca", "nonhuman primate"),
}

PARADIGM_TERMS: dict[str, dict[str, object]] = {
    "two-alternative forced choice": {
        "terms": ("2afc", "two alternative", "two-alternative", "forced choice"),
        "category": "decision-making",
        "responses": ("left", "right", "choice"),
    },
    "go/no-go": {
        "terms": ("go/no-go", "go nogo", "nogo", "no-go"),
        "category": "inhibitory control",
        "responses": ("go", "withhold", "lick", "press"),
    },
    "reward learning": {
        "terms": ("reward", "reinforcement", "prediction error", "conditioning"),
        "category": "learning",
        "reinforcement": ("reward", "punishment", "omission"),
    },
    "social cognition": {
        "terms": ("social", "theory of mind", "faces", "interaction"),
        "category": "social behavior",
        "stimuli": ("faces", "agents", "social scenes"),
    },
    "fear conditioning": {
        "terms": ("fear conditioning", "shock", "conditioned stimulus", "freezing"),
        "category": "aversive learning",
        "reinforcement": ("shock", "aversive stimulus"),
    },
    "foraging": {
        "terms": ("foraging", "patch", "harvest", "search behavior"),
        "category": "naturalistic behavior",
        "responses": ("locomotion", "choice"),
    },
    "locomotion": {
        "terms": ("locomotion", "wheel", "running", "walking"),
        "category": "motor behavior",
        "responses": ("running", "walking", "wheel movement"),
    },
    "licking": {
        "terms": ("lick", "licking", "lickometer", "spout"),
        "category": "orofacial behavior",
        "responses": ("lick",),
    },
    "grooming": {
        "terms": ("grooming", "self-groom"),
        "category": "spontaneous behavior",
        "responses": ("grooming",),
    },
}


@dataclass(frozen=True)
class OntologyMatch:
    label: str
    confidence: float
    evidence: tuple[str, ...]


def infer_modalities(texts: list[str], paths: list[str] | None = None) -> list[Modality]:
    haystack = _haystack(texts + (paths or []))
    matches: list[Modality] = []
    for modality, terms in MODALITY_TERMS.items():
        if any(term in haystack for term in terms):
            matches.append(modality)
    return matches or [Modality.UNKNOWN]


def infer_species(texts: list[str]) -> tuple[Species, Confidence]:
    haystack = _haystack(texts)
    best = Species.UNKNOWN
    evidence: list[str] = []
    for species, terms in SPECIES_TERMS.items():
        found = [term for term in terms if term in haystack]
        if found:
            best = species
            evidence = found
            break
    return best, Confidence(value=0.85 if evidence else 0.15, evidence=evidence)


def infer_paradigms(texts: list[str]) -> list[BehavioralParadigm]:
    haystack = _haystack(texts)
    paradigms: list[BehavioralParadigm] = []
    for normalized, spec in PARADIGM_TERMS.items():
        terms = tuple(spec["terms"])  # type: ignore[arg-type]
        found = [term for term in terms if term in haystack]
        if not found:
            continue
        paradigms.append(
            BehavioralParadigm(
                name=normalized.title(),
                normalized_name=normalized,
                category=str(spec.get("category")) if spec.get("category") else None,
                stimuli=list(spec.get("stimuli", ())),
                responses=list(spec.get("responses", ())),
                reinforcement=list(spec.get("reinforcement", ())),
                confidence=Confidence(value=min(0.95, 0.45 + 0.15 * len(found)), evidence=found),
            )
        )
    return paradigms


def _haystack(texts: list[str]) -> str:
    return " ".join(str(text).lower() for text in texts if text)
