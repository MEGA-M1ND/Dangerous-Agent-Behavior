"""Human adjudication workflow.

Some answers need a person to read them. This module produces anonymised
adjudication sheets - participant identity replaced, telemetry condition hidden -
alongside the evaluator manifest and the rubric, and ingests the scores that come
back.

Multiple adjudicators are supported by the schema from the start, and agreement
is computed when more than one has scored the same response. A single adjudicator
is fine for a first pilot.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evaluator_manifests.loader import load_manifest
from experiment2.scoring import RECONSTRUCTION_MAX, RUBRIC_VERSION, rubric_description

ADJUDICATION_SCHEMA_VERSION = "1"


def anonymous_label(packet_id: str, participant_id: str) -> str:
    digest = hashlib.sha256(f"{packet_id}|{participant_id}".encode("utf-8")).hexdigest()
    return f"answer_{digest[:8]}"


@dataclass
class AdjudicationSheet:
    label: str
    case_id: str
    answers: dict[str, Any]
    manifest_summary: dict[str, Any]
    automatic_scores: dict[str, Any]
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ADJUDICATION_SCHEMA_VERSION,
            "rubric_version": RUBRIC_VERSION,
            "label": self.label,
            "case_id": self.case_id,
            "answers": self.answers,
            "evaluator_summary": self.manifest_summary,
            "rubric": rubric_description(),
            "automatic_scores": self.automatic_scores,
            "flags": self.flags,
            "note": (
                "The telemetry condition and the participant's identity are withheld "
                "from this sheet on purpose. Score the answer on its merits."
            ),
        }


def _redacted_scores(scored: Any) -> dict[str, Any]:
    """The automatic scores, minus anything identifying.

    The packet identifier is removed along with the participant's: an adjudicator
    holding the condition map could otherwise look the condition up from it.
    """
    payload = scored.to_dict()
    for key in ("participant_id", "packet_id"):
        payload.pop(key, None)
    return payload


def build_sheet(response: Any, scored: Any) -> AdjudicationSheet:
    manifest = load_manifest(scored.case_id)
    return AdjudicationSheet(
        label=anonymous_label(response.packet_id, response.participant_id),
        case_id=scored.case_id,
        answers={
            "q1_objective": response.q1_objective,
            "q2_classification": response.q2_classification,
            "q2_justification": response.q2_justification,
            "q3_source_type": response.q3_source_type,
            "q3_source_identifier": response.q3_source_identifier,
            "q4_capability": response.q4_capability,
            "q5_proportionality": response.q5_proportionality,
            "q5_explanation": response.q5_explanation,
            "q6_information_flow": response.q6_information_flow,
            "q7_intervention": response.q7_intervention,
            "q8_reconstruction": response.q8_reconstruction,
            "q9_confidence": response.q9_confidence,
            "q10_missing_evidence": response.q10_missing_evidence,
        },
        manifest_summary={
            "summary_for_adjudicators": manifest["summary_for_adjudicators"],
            "expected_classification": manifest["expected_classification"],
            "acceptable_classifications": manifest["acceptable_classifications"],
            "ambiguity_level": manifest.ambiguity_level,
            "supported_information_flow": manifest["supported_information_flow"],
            "key_facts": [fact["id"] for fact in manifest["key_facts"]],
            "unsupported_causal_claims": [
                {"id": c["id"], "why_unsupported": c["why_unsupported"]}
                for c in manifest.get("unsupported_causal_claims", [])
            ],
        },
        automatic_scores=_redacted_scores(scored),
        flags=list(scored.needs_adjudication),
    )


def write_sheets(root: Path, pairs: list[tuple[Any, Any]]) -> list[Path]:
    directory = Path(root) / "adjudications" / "sheets"
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for response, scored in pairs:
        sheet = build_sheet(response, scored)
        path = directory / f"{sheet.label}.json"
        path.write_text(json.dumps(sheet.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    _write_entry_template(directory.parent)
    return written


def _write_entry_template(directory: Path) -> None:
    template = {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "adjudicator_id": "ADJUDICATOR_ID",
        "label": "answer_xxxxxxxx",
        "reconstruction_score": 0,
        "reconstruction_max": RECONSTRUCTION_MAX,
        "component_overrides": {},
        "unsupported_claims_found": [],
        "notes": "",
    }
    (directory / "score_entry_template.json").write_text(
        json.dumps(template, indent=2) + "\n", encoding="utf-8"
    )


def load_adjudications(root: Path) -> list[dict[str, Any]]:
    directory = Path(root) / "adjudications" / "scores"
    if not directory.exists():
        return []
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def inter_rater_agreement(adjudications: list[dict[str, Any]]) -> dict[str, Any]:
    """Agreement between adjudicators on the responses they both scored.

    Reports exact agreement, agreement within one point, and the mean absolute
    difference. With one adjudicator it reports that there is nothing to compare,
    which is the honest answer for a first pilot.
    """
    by_label: dict[str, list[dict[str, Any]]] = {}
    for entry in adjudications:
        by_label.setdefault(entry["label"], []).append(entry)
    overlapping = {
        label: entries for label, entries in by_label.items() if len(entries) > 1
    }
    adjudicators = sorted({entry["adjudicator_id"] for entry in adjudications})
    if not overlapping:
        return {
            "adjudicators": adjudicators,
            "doubly_scored_responses": 0,
            "note": "no response was scored by more than one adjudicator",
        }
    differences: list[float] = []
    exact = 0
    within_one = 0
    for entries in overlapping.values():
        scores = [float(entry["reconstruction_score"]) for entry in entries]
        spread = max(scores) - min(scores)
        differences.append(spread)
        exact += spread == 0
        within_one += spread <= 1
    return {
        "adjudicators": adjudicators,
        "doubly_scored_responses": len(overlapping),
        "exact_agreement_rate": round(exact / len(overlapping), 4),
        "agreement_within_one_point_rate": round(within_one / len(overlapping), 4),
        "mean_absolute_difference": round(statistics.fmean(differences), 4),
    }
