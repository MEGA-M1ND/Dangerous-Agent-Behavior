"""Aggregation over investigator responses.

The pre-registered primary metric is the reconstruction score. Everything else is
secondary and reported alongside it, never folded into it.

Statistical discipline: this is a pilot. Means, medians and counts are reported;
an effect size is computed only when both groups have at least two observations
and some variance, and it is labelled as descriptive. No p-values are produced,
because at pilot sizes they would be theatre.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from evaluator_manifests.loader import load_manifest
from experiment2.cases import CASE_IDS, CONDITIONS
from experiment2.questionnaire import InvestigatorResponse
from experiment2.responses import load_responses
from experiment2.scoring import RECONSTRUCTION_MAX, RUBRIC_VERSION, ScoredResponse, score_response
from experiment2.study import load_condition_map, load_packet

PREREGISTRATION_FILE = "EXPERIMENT_002_PREREGISTRATION.md"

#: Minimum observations per condition before an effect size is even computed.
MIN_FOR_EFFECT_SIZE = 2


class PreregistrationMissing(RuntimeError):
    """Aggregation is refused until the pre-registration exists on disk."""


def require_preregistration(repository_root: Path) -> Path:
    path = Path(repository_root) / PREREGISTRATION_FILE
    if not path.exists():
        raise PreregistrationMissing(
            f"{PREREGISTRATION_FILE} does not exist. Metrics are not computed before "
            "the analysis plan is written down."
        )
    return path


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 4) if values else None


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 4) if values else None


def _stdev(values: list[float]) -> float | None:
    return round(statistics.stdev(values), 4) if len(values) > 1 else None


def _rate(flags: list[bool]) -> float | None:
    return round(sum(1 for f in flags if f) / len(flags), 4) if flags else None


def effect_size(baseline: list[float], provenance: list[float]) -> dict[str, Any]:
    """Hedges' g, computed only when it means anything at all."""
    if len(baseline) < MIN_FOR_EFFECT_SIZE or len(provenance) < MIN_FOR_EFFECT_SIZE:
        return {
            "computable": False,
            "reason": f"fewer than {MIN_FOR_EFFECT_SIZE} observations in at least one condition",
        }
    pooled_variance = (
        (len(baseline) - 1) * statistics.variance(baseline)
        + (len(provenance) - 1) * statistics.variance(provenance)
    ) / (len(baseline) + len(provenance) - 2)
    if pooled_variance == 0:
        return {"computable": False, "reason": "no variance in either condition"}
    d = (statistics.fmean(provenance) - statistics.fmean(baseline)) / (pooled_variance ** 0.5)
    total = len(baseline) + len(provenance)
    correction = 1 - (3 / (4 * total - 9)) if total > 3 else 1.0
    return {
        "computable": True,
        "hedges_g": round(d * correction, 4),
        "n_baseline": len(baseline),
        "n_provenance": len(provenance),
        "interpretation": (
            "Descriptive only. At pilot sample sizes an effect size is an "
            "observation about these particular responses, not an estimate of a "
            "population parameter."
        ),
    }


def score_all(
    root: Path, responses: list[InvestigatorResponse]
) -> list[tuple[ScoredResponse, str]]:
    """Score each response and tag it with its (evaluator-only) condition."""
    condition_map = load_condition_map(root)
    scored: list[tuple[ScoredResponse, str]] = []
    for response in responses:
        entry = condition_map.get(response.packet_id)
        if entry is None:
            raise KeyError(f"response references an unknown packet: {response.packet_id}")
        packet = load_packet(root, response.packet_id)
        manifest = load_manifest(entry["case_id"])
        scored.append((score_response(response, entry["case_id"], packet, manifest), entry["condition"]))
    return scored


def _group_summary(rows: list[ScoredResponse]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    scores = [float(r.reconstruction_score) for r in rows]
    component_keys = [c.key for c in rows[0].components]
    return {
        "n": len(rows),
        "reconstruction_score": {
            "mean": _mean(scores),
            "median": _median(scores),
            "stdev": _stdev(scores),
            "min": min(scores),
            "max": max(scores),
            "max_possible": RECONSTRUCTION_MAX,
            "raw": scores,
        },
        "component_means": {
            key: _mean(
                [float(c.points) for r in rows for c in r.components if c.key == key]
            )
            for key in component_keys
        },
        "classification_exact_rate": _rate([r.secondary["classification"]["exact"] for r in rows]),
        "classification_acceptable_rate": _rate(
            [r.secondary["classification"]["acceptable_match"] for r in rows]
        ),
        "source_type_acceptable_rate": _rate(
            [r.secondary["source_attribution"]["type_acceptable"] for r in rows]
        ),
        "source_type_preferred_rate": _rate(
            [r.secondary["source_attribution"]["type_preferred"] for r in rows]
        ),
        "proportionality_acceptable_rate": _rate(
            [r.secondary["proportionality"]["acceptable_match"] for r in rows]
        ),
        "information_flow_acceptable_rate": _rate(
            [r.secondary["information_flow"]["acceptable_match"] for r in rows]
        ),
        "intervention_good_rate": _rate([r.secondary["intervention"]["good"] for r in rows]),
        "intervention_verdicts": {
            verdict: sum(1 for r in rows if r.secondary["intervention"]["verdict"] == verdict)
            for verdict in sorted({r.secondary["intervention"]["verdict"] for r in rows})
        },
        "false_accusation_rate": _rate([r.secondary["false_accusation"] for r in rows]),
        "unsupported_causal_claims_per_response": _mean(
            [float(r.secondary["unsupported_causal_claim_count"]) for r in rows]
        ),
        "responses_with_any_unsupported_claim_rate": _rate(
            [r.secondary["unsupported_causal_claim_count"] > 0 for r in rows]
        ),
        "distractors_cited_per_response": _mean(
            [float(r.secondary["distractor_citation_count"]) for r in rows]
        ),
        "mean_confidence": _mean([float(r.secondary["confidence"]) for r in rows]),
        "mean_confidence_when_classification_wrong": _mean(
            [
                float(r.secondary["confidence_on_wrong_classification"])
                for r in rows
                if r.secondary["confidence_on_wrong_classification"] is not None
            ]
        ),
        "mean_calibration_error": _mean([float(r.secondary["calibration_error"]) for r in rows]),
        "missing_evidence_fraction": _mean(
            [
                float(r.secondary["missing_evidence"]["fraction"])
                for r in rows
                if r.secondary["missing_evidence"]["fraction"] is not None
            ]
        ),
        "mean_duration_seconds_reliable_only": _mean(
            [
                float(r.secondary["duration_seconds"])
                for r in rows
                if r.secondary["timing_is_reliable"] and r.secondary["duration_seconds"] is not None
            ]
        ),
        "responses_with_reliable_timing": sum(
            1 for r in rows if r.secondary["timing_is_reliable"]
        ),
        "responses_needing_adjudication": sum(1 for r in rows if r.needs_adjudication),
    }


def aggregate(root: Path, scored: list[tuple[ScoredResponse, str]]) -> dict[str, Any]:
    by_condition = {
        condition: [row for row, cond in scored if cond == condition] for condition in CONDITIONS
    }
    summary = {condition: _group_summary(rows) for condition, rows in by_condition.items()}

    comparison: dict[str, Any] = {}
    baseline_scores = [float(r.reconstruction_score) for r in by_condition["baseline"]]
    provenance_scores = [float(r.reconstruction_score) for r in by_condition["provenance"]]
    comparison["reconstruction_score"] = {
        "baseline_mean": _mean(baseline_scores),
        "provenance_mean": _mean(provenance_scores),
        "difference": (
            round(statistics.fmean(provenance_scores) - statistics.fmean(baseline_scores), 4)
            if baseline_scores and provenance_scores
            else None
        ),
        "effect_size": effect_size(baseline_scores, provenance_scores),
    }
    for metric in (
        "classification_acceptable_rate",
        "source_type_preferred_rate",
        "intervention_good_rate",
        "false_accusation_rate",
        "responses_with_any_unsupported_claim_rate",
        "distractors_cited_per_response",
        "mean_confidence_when_classification_wrong",
        "missing_evidence_fraction",
        "mean_duration_seconds_reliable_only",
    ):
        comparison[metric] = {
            "baseline": summary["baseline"].get(metric),
            "provenance": summary["provenance"].get(metric),
        }

    design_path = Path(root) / "study_design.json"
    design = json.loads(design_path.read_text(encoding="utf-8")) if design_path.exists() else {}

    return {
        "rubric_version": RUBRIC_VERSION,
        "primary_metric": "reconstruction_score (0-12, deterministic rubric)",
        "totals": {
            "responses": len(scored),
            "participants": len({row.participant_id for row, _ in scored}),
            "cases": len({row.case_id for row, _ in scored}),
            "by_condition": {c: len(rows) for c, rows in by_condition.items()},
            "by_investigator_kind": {
                kind: sum(1 for row, _ in scored if row.investigator_kind == kind)
                for kind in sorted({row.investigator_kind for row, _ in scored})
            },
        },
        "by_condition": summary,
        "comparison": comparison,
        "evidence_volume_by_condition": design.get("evidence_volume_by_condition"),
        "statistical_note": (
            "Pilot data. Report counts and means; do not claim significance. An "
            "effect size is computed only where both conditions have at least "
            f"{MIN_FOR_EFFECT_SIZE} observations and some variance."
        ),
    }


def per_case(scored: list[tuple[ScoredResponse, str]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for case_id in CASE_IDS:
        rows = [(row, cond) for row, cond in scored if row.case_id == case_id]
        if not rows:
            continue
        manifest = load_manifest(case_id)
        output[case_id] = {
            "ambiguity_level": manifest.ambiguity_level,
            "expected_classification": manifest["expected_classification"],
            "by_condition": {
                condition: _group_summary([row for row, cond in rows if cond == condition])
                for condition in CONDITIONS
            },
        }
    return output


def per_participant(scored: list[tuple[ScoredResponse, str]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for participant_id in sorted({row.participant_id for row, _ in scored}):
        rows = [(row, cond) for row, cond in scored if row.participant_id == participant_id]
        output[participant_id] = {
            "responses": len(rows),
            "investigator_kinds": sorted({row.investigator_kind for row, _ in rows}),
            "by_condition": {
                condition: _group_summary([row for row, cond in rows if cond == condition])
                for condition in CONDITIONS
            },
            "per_case_scores": {
                row.case_id: {"condition": cond, "score": row.reconstruction_score}
                for row, cond in rows
            },
        }
    return output


def compute_all(
    root: Path, repository_root: Path, include_mock: bool = False
) -> dict[str, Any]:
    require_preregistration(repository_root)
    responses = load_responses(root, include_mock=include_mock)
    scored = score_all(root, responses)
    return {
        "aggregate": aggregate(root, scored),
        "per_case": per_case(scored),
        "per_participant": per_participant(scored),
        "responses": [row.to_dict() | {"condition_evaluator_only": cond} for row, cond in scored],
    }
