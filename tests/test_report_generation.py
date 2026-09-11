"""Artifact generation and the pre-registered verdict."""

from __future__ import annotations

import json

from experiment.evaluation.report import write_artifacts
from experiment.evaluation.summary import build_results_document, build_summary
from experiment.evaluation.verdict import verdict_for_scenario

EXPECTED_ARTIFACTS = (
    "baseline_events.jsonl",
    "provenance_events.jsonl",
    "reconstructed_baseline.json",
    "reconstructed_provenance.json",
    "provenance_graph.json",
    "provenance_graph.md",
    "metrics.json",
    "report.md",
    "run_manifest.json",
)


def test_every_run_writes_the_expected_artifacts(analyses):
    for scenario_id, analysis in analyses.items():
        write_artifacts(analysis)
        for name in EXPECTED_ARTIFACTS:
            path = analysis.run.run_dir / name
            assert path.exists(), f"{name} missing for {scenario_id}"
            assert path.stat().st_size > 0


def test_machine_readable_artifacts_parse(analyses):
    for analysis in analyses.values():
        write_artifacts(analysis)
        for name in ("metrics.json", "provenance_graph.json", "reconstructed_provenance.json"):
            json.loads((analysis.run.run_dir / name).read_text(encoding="utf-8"))


def test_graph_markdown_contains_mermaid_and_an_evidence_table(analyses):
    write_artifacts(analyses["injected"])
    text = (analyses["injected"].run.run_dir / "provenance_graph.md").read_text(encoding="utf-8")
    assert "```mermaid" in text
    assert "flowchart TD" in text
    assert "| source | relation | target | observed | evidence | detail |" in text


def test_run_report_records_the_self_report_as_untrusted(analyses):
    write_artifacts(analyses["injected"])
    text = (analyses["injected"].run.run_dir / "report.md").read_text(encoding="utf-8")
    assert "untrusted self report" in text
    assert "is not used as evidence" in text


def test_results_document_is_generated_from_measured_values(analyses):
    document = build_results_document(list(analyses.values()), sensitivity={})
    assert "# RESULTS - Experiment 001" in document
    assert "What would change our mind?" in document
    assert "No statistical inference is possible" in document
    for scenario_id in analyses:
        assert scenario_id in document


def test_summary_carries_a_verdict_for_every_scenario(analyses):
    summary = build_summary(list(analyses.values()), sensitivity={})
    for scenario_id, entry in summary["scenarios"].items():
        assert "verdict" in entry["verdict"]


def test_verdict_rule_is_mechanical(analyses):
    injected = analyses["injected"]
    verdict = verdict_for_scenario(injected.baseline.metrics, injected.provenance.metrics)
    assert verdict["verdict"] in ("supported", "not supported", "inconclusive")
    # Precision is reported as a cost and never folded into the verdict.
    assert "edge_precision_delta" in verdict


def test_verdict_is_withheld_for_control_scenarios(analyses):
    for scenario_id in ("benign", "safe_alternative"):
        analysis = analyses[scenario_id]
        verdict = verdict_for_scenario(analysis.baseline.metrics, analysis.provenance.metrics)
        assert verdict["verdict"].startswith("no verdict")


def test_cli_end_to_end(tmp_path):
    from experiment.cli import main

    code = main(
        [
            "run",
            "--scenario",
            "all",
            "--artifacts",
            str(tmp_path / "artifacts"),
            "--results",
            str(tmp_path / "RESULTS.md"),
            "--skip-sensitivity",
        ]
    )
    assert code == 0
    assert (tmp_path / "RESULTS.md").exists()
    assert (tmp_path / "artifacts" / "summary" / "aggregate_metrics.json").exists()


def test_cli_accepts_the_hyphenated_scenario_name(tmp_path):
    from experiment.cli import main

    assert main(["run", "--scenario", "safe-alternative", "--artifacts", str(tmp_path)]) == 0
