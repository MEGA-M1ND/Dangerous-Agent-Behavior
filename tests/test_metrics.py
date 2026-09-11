"""Scoring behaviour, including the cases where the baseline wins."""

from __future__ import annotations

from experiment.analysis.detection import detect
from experiment.analysis.reconstruct import reconstruct
from experiment.evaluation.metrics import score
from ground_truth import load_ground_truth


def _score(stream):
    reconstruction = reconstruct(stream)
    return score(reconstruction, detect(reconstruction, stream))


def test_ground_truth_edges_use_only_scored_relations():
    from ground_truth.loader import SCORED_RELATIONS

    for scenario_id in ("benign", "injected", "safe_alternative"):
        for edge in load_ground_truth(scenario_id).edges:
            assert edge["relation"] in SCORED_RELATIONS


def test_both_conditions_score_perfectly_on_the_benign_control(events):
    for stream in events["benign"].values():
        values = _score(stream).values
        assert values["event_coverage_all"] == 1.0
        assert values["edge_recall"] == 1.0
        assert values["detection_false_positive_count"] == 0
        assert values["dangerous_action_false_positive"] is False


def test_edge_precision_is_measured_and_surfaced_for_both_conditions(events):
    """Precision must be reported separately so a regression cannot hide.

    This test deliberately does not assert which condition wins: the direction is
    a measured result and belongs in RESULTS.md, not in an assertion that would
    have to be edited if the result changed.
    """
    from experiment.evaluation.verdict import verdict_for_scenario

    for scenario_id, streams in events.items():
        baseline = _score(streams["baseline"])
        provenance = _score(streams["provenance"])
        assert isinstance(baseline.values["edge_precision"], float), scenario_id
        assert isinstance(provenance.values["edge_precision"], float), scenario_id
        verdict = verdict_for_scenario(baseline, provenance)
        assert verdict["edge_precision_delta"] is not None


def test_provenance_recovers_dataflow_edges_the_baseline_misses(events):
    baseline = _score(events["injected"]["baseline"]).values
    provenance = _score(events["injected"]["provenance"]).values
    assert (
        provenance["dataflow_edge_recall_observed_evidence_only"]
        > baseline["dataflow_edge_recall_observed_evidence_only"]
    )


def test_scoring_reports_over_claims_explicitly(events):
    for streams in events.values():
        for stream in streams.values():
            values = _score(stream).values
            assert isinstance(values["edges_unsupported_by_ground_truth"], list)


def test_source_attribution_separates_observed_from_inferred_evidence(events):
    provenance = _score(events["injected"]["provenance"]).values["source_attribution"]
    assert provenance["expected_source"] == "ops-runbook-demo"
    assert provenance["correct_observed_only"] is True
    # Inferred evidence brings in documents that did not determine the action.
    assert len(provenance["attributed_sources_all_evidence"]) >= len(
        provenance["attributed_sources_observed_evidence_only"]
    )


def test_dangerous_action_detection_is_scored_against_ground_truth(events):
    for condition, stream in events["injected"].items():
        assert _score(stream).values["dangerous_action_detected"] is True, condition
    for scenario_id in ("benign", "safe_alternative"):
        for stream in events[scenario_id].values():
            values = _score(stream).values
            assert values["dangerous_action_detected"] is None
            assert values["dangerous_action_false_positive"] is False


def test_conventional_subset_coverage_excludes_provenance_only_steps():
    truth = load_ground_truth("injected")
    conventional = {s["step_id"] for s in truth.conventional_trajectory}
    assert "permission_gain" not in conventional
    assert len(conventional) == len(truth.trajectory) - 1
