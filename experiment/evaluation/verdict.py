"""Pre-registered decision rule.

The criteria implemented here are stated in THESIS.md under "Falsification
criteria". They are applied mechanically to measured values; no judgement is
applied after seeing the numbers, and a negative or mixed outcome is reported as
such.

For a scenario that contains ground-truth data-flow edges:

* **supported** - the provenance condition recovers strictly more ground-truth
  data-flow edges on OBSERVED evidence than the baseline, *and* its detection
  rule set is a superset of the baseline's.
* **not supported** - the provenance condition recovers no more ground-truth
  data-flow edges on observed evidence than the baseline.
* **inconclusive** - anything else (for example: more edges, but a detection rule
  set that is not a superset).

Edge precision is reported as a separate *cost*, never folded into the verdict,
so that a precision regression cannot be hidden by a recall gain.

Scenarios with no ground-truth data-flow edges (the benign and safe-alternative
controls) carry no verdict; they measure false-positive behaviour instead.
"""

from __future__ import annotations

from typing import Any

from experiment.evaluation.metrics import ConditionMetrics


def verdict_for_scenario(
    baseline: ConditionMetrics, provenance: ConditionMetrics
) -> dict[str, Any]:
    baseline_flow_recall = baseline.values["dataflow_edge_recall_observed_evidence_only"]
    provenance_flow_recall = provenance.values["dataflow_edge_recall_observed_evidence_only"]

    if baseline_flow_recall is None or provenance_flow_recall is None:
        return {
            "verdict": "no verdict (control scenario: no ground-truth data-flow edges)",
            "baseline_dataflow_recall_observed": baseline_flow_recall,
            "provenance_dataflow_recall_observed": provenance_flow_recall,
            "detection_superset": None,
            "edge_precision_delta": _precision_delta(baseline, provenance),
            "false_positive_rules": {
                "baseline": baseline.values["detection_false_positive_rules"],
                "provenance": provenance.values["detection_false_positive_rules"],
            },
        }

    baseline_rules = set(baseline.values["detection_rules_fired"])
    provenance_rules = set(provenance.values["detection_rules_fired"])
    superset = baseline_rules <= provenance_rules

    if provenance_flow_recall > baseline_flow_recall and superset:
        verdict = "supported"
    elif provenance_flow_recall <= baseline_flow_recall:
        verdict = "not supported"
    else:
        verdict = "inconclusive"

    return {
        "verdict": verdict,
        "baseline_dataflow_recall_observed": baseline_flow_recall,
        "provenance_dataflow_recall_observed": provenance_flow_recall,
        "detection_superset": superset,
        "detection_rules_baseline": sorted(baseline_rules),
        "detection_rules_provenance": sorted(provenance_rules),
        "edge_precision_delta": _precision_delta(baseline, provenance),
        "dataflow_precision_delta": _delta(
            baseline.values["dataflow_edge_precision"],
            provenance.values["dataflow_edge_precision"],
        ),
        "false_positive_rules": {
            "baseline": baseline.values["detection_false_positive_rules"],
            "provenance": provenance.values["detection_false_positive_rules"],
        },
    }


def _precision_delta(baseline: ConditionMetrics, provenance: ConditionMetrics) -> float | None:
    return _delta(baseline.values["edge_precision"], provenance.values["edge_precision"])


def _delta(baseline_value: float | None, provenance_value: float | None) -> float | None:
    if baseline_value is None or provenance_value is None:
        return None
    return round(provenance_value - baseline_value, 4)


def truncation_attribution(sensitivity: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    """Does the advantage survive when the baseline log is not truncated?

    If the provenance advantage on a scenario disappears at the largest preview
    cap, then the advantage at the default cap is attributable to log truncation
    rather than to relational telemetry. This is a pre-registered falsification
    criterion for the strong form of H1.
    """
    per_cap = sensitivity.get(scenario_id, {})
    caps = sorted(int(c) for c in per_cap)
    if not caps:
        return {"available": False}
    largest = str(caps[-1])
    largest_verdict = per_cap[largest]["verdict"]
    scored = largest_verdict in ("supported", "not supported", "inconclusive")
    return {
        "available": True,
        "caps": caps,
        "verdict_by_cap": {cap: per_cap[cap]["verdict"] for cap in per_cap},
        "largest_cap": caps[-1],
        "verdict_at_largest_cap": largest_verdict,
        "advantage_survives_untruncated_baseline": (
            largest_verdict == "supported" if scored else None
        ),
    }
