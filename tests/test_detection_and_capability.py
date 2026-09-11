"""Detection heuristics and the experimental capability-proportionality metric."""

from __future__ import annotations

from experiment.analysis.capability import analyse_capabilities
from experiment.analysis.detection import RULES, detect
from experiment.analysis.reconstruct import reconstruct


def _detect(stream):
    reconstruction = reconstruct(stream)
    return detect(reconstruction, stream)


def test_controls_produce_no_findings(events):
    for scenario_id in ("benign", "safe_alternative"):
        for condition, stream in events[scenario_id].items():
            result = _detect(stream)
            assert result.findings == [], (scenario_id, condition)
            assert result.first_detection_sequence is None


def test_injected_scenario_fires_rules_in_both_conditions(events):
    baseline = _detect(events["injected"]["baseline"]).fired_rules
    provenance = _detect(events["injected"]["provenance"]).fired_rules
    assert baseline, "a well-instrumented conventional log should still notice something"
    assert baseline <= provenance, "provenance must not lose a signal the baseline has"


def test_permission_escalation_rule_needs_permission_telemetry(events):
    baseline = _detect(events["injected"]["baseline"]).fired_rules
    provenance = _detect(events["injected"]["provenance"]).fired_rules
    assert "R3_permission_escalation" not in baseline
    assert "R3_permission_escalation" in provenance


def test_every_finding_declares_its_evidence_strength(events):
    for scenario_id in ("injected",):
        for stream in events[scenario_id].values():
            for finding in _detect(stream).findings:
                assert finding.confidence in ("observed", "inferred")
                assert finding.rule_id
                assert finding.statement


def test_all_rules_are_pure_functions_of_reconstruction_and_events(events):
    """Every rule must run on both streams without error and be order-stable."""
    for stream in events["injected"].values():
        reconstruction = reconstruct(stream)
        for rule in RULES:
            first = [f.to_dict() for f in rule(reconstruction, stream)]
            second = [f.to_dict() for f in rule(reconstruction, stream)]
            assert first == second


def test_capability_proportionality_matches_the_declared_minimum(events):
    benign = analyse_capabilities(events["benign"]["baseline"])
    assert benign.unnecessary == []
    assert benign.privileged_unnecessary == []

    injected = analyse_capabilities(events["injected"]["baseline"])
    assert set(injected.privileged_unnecessary) == {"secret_store.get", "cloud.create_admin_user"}
    assert injected.disproportion == len(injected.unnecessary)


def test_capability_proportionality_is_identical_in_both_conditions(events):
    """Both conditions see the declared minimum and the exercised set."""
    for streams in events.values():
        baseline = analyse_capabilities(streams["baseline"]).to_dict()
        provenance = analyse_capabilities(streams["provenance"]).to_dict()
        assert baseline == provenance


def test_capability_metric_is_labelled_experimental(events):
    report = analyse_capabilities(events["injected"]["baseline"]).to_dict()
    assert "EXPERIMENTAL" in report["note"]
