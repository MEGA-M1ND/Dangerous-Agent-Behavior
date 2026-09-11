"""Artifact generation: reconstructions, graphs, metrics and reports.

Everything written here is derived from a run that has already happened. No
conclusion is written by hand; the report renders measured values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiment.analysis.detection import DetectionResult, detect
from experiment.analysis.reconstruct import Reconstruction, reconstruct
from experiment.evaluation.metrics import ConditionMetrics, compare, score
from experiment.observability.sinks import chain_digest_of, read_events
from experiment.run import RunOutput


@dataclass
class ConditionAnalysis:
    condition: str
    reconstruction: Reconstruction
    detection: DetectionResult
    metrics: ConditionMetrics


@dataclass
class RunAnalysis:
    run: RunOutput
    baseline: ConditionAnalysis
    provenance: ConditionAnalysis
    comparison: dict[str, Any]
    tamper_check: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run.run_id,
            "scenario_id": self.run.scenario.scenario_id,
            "mode": self.run.config.mode,
            "seed": self.run.config.seed,
            "preview_cap": self.run.config.preview_cap,
            "telemetry_integrity": self.tamper_check,
            "baseline": self.baseline.metrics.to_dict(),
            "provenance": self.provenance.metrics.to_dict(),
            "comparison": self.comparison,
        }


def _analyse_condition(path: Path) -> ConditionAnalysis:
    events = read_events(path)
    reconstruction = reconstruct(events)
    detection = detect(reconstruction, events)
    metrics = score(reconstruction, detection)
    return ConditionAnalysis(reconstruction.condition, reconstruction, detection, metrics)


def analyse_run(run: RunOutput) -> RunAnalysis:
    baseline = _analyse_condition(run.baseline_path)
    provenance = _analyse_condition(run.provenance_path)
    tamper_check = {
        "baseline_chain_intact": chain_digest_of(run.baseline_path)
        == run.chain_digests["baseline_logger"],
        "provenance_chain_intact": chain_digest_of(run.provenance_path)
        == run.chain_digests["provenance_observer"],
    }
    return RunAnalysis(
        run=run,
        baseline=baseline,
        provenance=provenance,
        comparison=compare(baseline.metrics, provenance.metrics),
        tamper_check=tamper_check,
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_artifacts(analysis: RunAnalysis) -> list[Path]:
    run_dir = analysis.run.run_dir
    written: list[Path] = []

    for name, condition in (
        ("reconstructed_baseline.json", analysis.baseline),
        ("reconstructed_provenance.json", analysis.provenance),
    ):
        path = run_dir / name
        _write_json(
            path,
            {
                **condition.reconstruction.to_dict(),
                "detection": condition.detection.to_dict(),
            },
        )
        written.append(path)

    graph_json = run_dir / "provenance_graph.json"
    _write_json(
        graph_json,
        {
            "run_id": analysis.run.run_id,
            "scenario_id": analysis.run.scenario.scenario_id,
            "provenance_condition_graph": analysis.provenance.reconstruction.graph.to_dict(),
            "baseline_condition_graph": analysis.baseline.reconstruction.graph.to_dict(),
        },
    )
    written.append(graph_json)

    graph_md = run_dir / "provenance_graph.md"
    graph_md.write_text(_graph_markdown(analysis), encoding="utf-8")
    written.append(graph_md)

    metrics_path = run_dir / "metrics.json"
    _write_json(metrics_path, analysis.to_dict())
    written.append(metrics_path)

    report_path = run_dir / "report.md"
    report_path.write_text(_run_report(analysis), encoding="utf-8")
    written.append(report_path)
    return written


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #

def _graph_markdown(analysis: RunAnalysis) -> str:
    lines = [
        f"# Provenance graph - {analysis.run.scenario.title}",
        "",
        f"Run `{analysis.run.run_id}` | scenario `{analysis.run.scenario.scenario_id}` | "
        f"mode `{analysis.run.config.mode}` | seed `{analysis.run.config.seed}`",
        "",
        "Solid edges are OBSERVED relationships. Dashed edges are INFERRED: they state "
        "only that information was present in the observable input state preceding an "
        "action. Neither kind is a claim about the model's reasoning.",
        "",
        "## Provenance condition",
        "",
        "```mermaid",
        analysis.provenance.reconstruction.graph.to_mermaid(),
        "```",
        "",
        "## Baseline condition",
        "",
        "```mermaid",
        analysis.baseline.reconstruction.graph.to_mermaid(),
        "```",
        "",
        "## Edge evidence (provenance condition)",
        "",
        "| source | relation | target | observed | evidence | detail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for edge in analysis.provenance.reconstruction.graph.edges:
        lines.append(
            f"| `{edge.source}` | {edge.relation} | `{edge.target}` | "
            f"{'yes' if edge.observed else 'no'} | {edge.evidence_kind.value} | {edge.detail} |"
        )
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "(none)"
    return str(value)


def _run_report(analysis: RunAnalysis) -> str:
    run = analysis.run
    baseline = analysis.baseline.metrics.values
    provenance = analysis.provenance.metrics.values

    lines = [
        f"# {run.scenario.title}",
        "",
        f"- run id: `{run.run_id}`",
        f"- scenario: `{run.scenario.scenario_id}` | corpus: `{run.scenario.corpus}` | "
        f"policy: `{run.scenario.policy}`",
        f"- mode: `{run.config.mode}` | seed: `{run.config.seed}` | "
        f"result-preview cap: `{run.config.preview_cap}` chars | clock: `{run.clock_mode}`",
        f"- adapter: `{run.adapter_descriptor}`",
        f"- events recorded: baseline {run.event_counts['baseline']}, "
        f"provenance {run.event_counts['provenance']}",
        f"- telemetry hash chains intact: {_fmt(all(analysis.tamper_check.values()))}",
        "",
        "## What the agent did",
        "",
        f"Objective: {run.scenario.objective}",
        "",
        f"Capabilities exercised: `{', '.join(run.agent_result.exercised_capabilities)}`",
        "",
        f"Final synthetic environment change set: "
        f"`{json.dumps(_environment_delta(run), sort_keys=True)}`",
        "",
        "The agent's own final answer is recorded only as an untrusted self report and "
        "is not used as evidence anywhere in this analysis:",
        "",
        f"> {run.agent_result.answer or '(none)'}",
        "",
        "## Reconstruction comparison",
        "",
        "| metric | baseline | provenance | verdict |",
        "| --- | --- | --- | --- |",
    ]
    for name, row in analysis.comparison.items():
        lines.append(
            f"| {name} | {_fmt(row['baseline'])} | {_fmt(row['provenance'])} | {row['verdict']} |"
        )

    lines += [
        "",
        "## Ground-truth steps missed",
        "",
        f"- baseline: {_fmt(baseline['event_coverage_missed'])}",
        f"- provenance: {_fmt(provenance['event_coverage_missed'])}",
        "",
        "## Ground-truth data-flow edges",
        "",
        f"- baseline recovered: {_fmt(sorted(e for e in baseline['edges_recovered'] if 'data_flowed_to' in e))}",
        f"- provenance recovered: {_fmt(sorted(e for e in provenance['edges_recovered'] if 'data_flowed_to' in e))}",
        "",
        "## Reported relationships not supported by ground truth",
        "",
        "These are over-claims: relationships the reconstruction asserted that the "
        "scenario design does not contain.",
        "",
        f"- baseline: {len(baseline['edges_unsupported_by_ground_truth'])}",
        f"- provenance: {len(provenance['edges_unsupported_by_ground_truth'])}",
        "",
        "## Source attribution",
        "",
        f"- expected untrusted source: {_fmt(baseline['source_attribution']['expected_source'])}",
        f"- baseline attributed (all evidence): {_fmt(baseline['source_attribution']['attributed_sources_all_evidence'])}",
        f"- provenance attributed (all evidence): {_fmt(provenance['source_attribution']['attributed_sources_all_evidence'])}",
        f"- baseline attributed (observed evidence only): {_fmt(baseline['source_attribution']['attributed_sources_observed_evidence_only'])}",
        f"- provenance attributed (observed evidence only): {_fmt(provenance['source_attribution']['attributed_sources_observed_evidence_only'])}",
        "",
        "## Detection",
        "",
        f"- expected rules (design intent): {_fmt(baseline['detection_rules_expected'])}",
        f"- baseline fired: {_fmt(baseline['detection_rules_fired'])}",
        f"- provenance fired: {_fmt(provenance['detection_rules_fired'])}",
        f"- baseline false-positive rules: {_fmt(baseline['detection_false_positive_rules'])}",
        f"- provenance false-positive rules: {_fmt(provenance['detection_false_positive_rules'])}",
        f"- first detection at event index: baseline {_fmt(baseline['first_detection_sequence'])}, "
        f"provenance {_fmt(provenance['first_detection_sequence'])}",
        f"- dangerous action at event index: {_fmt(baseline['dangerous_action_sequence'])}",
        "",
        "## Capability proportionality (EXPERIMENTAL)",
        "",
        f"- required (declared minimum): {_fmt(baseline['capability_proportionality']['required_capabilities'])}",
        f"- exercised: {_fmt(baseline['capability_proportionality']['exercised_capabilities'])}",
        f"- unnecessary: {_fmt(baseline['capability_proportionality']['unnecessary_capabilities_exercised'])}",
        f"- privileged unnecessary: {_fmt(baseline['capability_proportionality']['privileged_unnecessary_capabilities_exercised'])}",
        "",
    ]
    return "\n".join(lines) + "\n"


def _environment_delta(run: RunOutput) -> dict[str, Any]:
    before, after = run.environment_before, run.environment_after
    return {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }
