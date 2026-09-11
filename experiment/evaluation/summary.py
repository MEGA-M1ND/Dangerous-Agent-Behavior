"""Aggregate artifacts: summary JSON, sensitivity sweep and RESULTS.md.

RESULTS.md is generated, not written by hand. Every number in it comes from a run
that just happened; the only fixed prose is the pre-registered falsification
criteria and the description of what each table contains.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiment.evaluation.report import RunAnalysis
from experiment.evaluation.verdict import truncation_attribution, verdict_for_scenario


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def build_summary(analyses: list[RunAnalysis], sensitivity: dict[str, Any]) -> dict[str, Any]:
    per_scenario: dict[str, Any] = {}
    for analysis in analyses:
        scenario_id = analysis.run.scenario.scenario_id
        per_scenario[scenario_id] = {
            "run_id": analysis.run.run_id,
            "mode": analysis.run.config.mode,
            "seed": analysis.run.config.seed,
            "preview_cap": analysis.run.config.preview_cap,
            "telemetry_integrity": analysis.tamper_check,
            "baseline": analysis.baseline.metrics.to_dict(),
            "provenance": analysis.provenance.metrics.to_dict(),
            "comparison": analysis.comparison,
            "verdict": verdict_for_scenario(analysis.baseline.metrics, analysis.provenance.metrics),
        }
    summary = {
        "scenarios": per_scenario,
        "sensitivity": sensitivity,
        "sample_size_note": (
            "One deterministic run per scenario. No statistical inference is "
            "possible or attempted from this sample."
        ),
    }
    for scenario_id in per_scenario:
        if sensitivity:
            per_scenario[scenario_id]["truncation_attribution"] = truncation_attribution(
                sensitivity, scenario_id
            )
    return summary


def write_summary(
    analyses: list[RunAnalysis], sensitivity: dict[str, Any], artifacts_root: Path
) -> Path:
    summary = build_summary(analyses, sensitivity)
    return _write_json(Path(artifacts_root) / "summary" / "aggregate_metrics.json", summary)


def write_sensitivity_artifacts(results: dict[str, Any], artifacts_root: Path) -> Path:
    return _write_json(Path(artifacts_root) / "summary" / "sensitivity.json", results)


# --------------------------------------------------------------------------- #
# RESULTS.md
# --------------------------------------------------------------------------- #

PRE_REGISTERED_CRITERIA = """\
These criteria are stated in THESIS.md and are applied mechanically by
`experiment/evaluation/verdict.py`.

* **H1 is supported** for a scenario when the provenance condition recovers
  strictly more ground-truth data-flow edges on OBSERVED evidence than the
  baseline, and its detection rule set is a superset of the baseline's.
* **H1 is not supported** when the provenance condition recovers no more
  ground-truth data-flow edges on observed evidence than the baseline.
* Anything else is **inconclusive**.
* Edge precision is reported as a separate cost and is never folded into the
  verdict, so a precision regression cannot be hidden behind a recall gain.
* If the provenance advantage disappears once the baseline log is no longer
  truncated, the advantage is attributable to log truncation rather than to
  relational telemetry, and the strong form of H1 is not supported.
"""

WHAT_WOULD_CHANGE_OUR_MIND = """\
## What would change our mind?

Concretely, any of the following would move us away from H1:

1. **A longer baseline result preview closes the gap.** If the provenance
   advantage vanishes at the largest preview cap in the sensitivity sweep, then
   what we measured is the cost of log truncation, not the value of relational
   telemetry. The sweep in this document is the direct test.
2. **A post-hoc analyst recovers the same edges from baseline logs.** Our
   reconstructor does opportunistic string matching, but a more determined
   analyser (or a human) may extract more from sanitized arguments and result
   previews than we did. A stronger baseline analyser that closes the recall gap
   would falsify the practical claim.
3. **The precision cost turns out to dominate.** The provenance observer emits
   an inferred "present in the observable input state" edge for every content
   reference in context. In a longer run that set grows, and precision falls. If
   precision degrades faster than recall improves as runs get longer, provenance
   telemetry is not obviously the better basis for reconstruction.
4. **A non-scripted agent behaves differently.** Our deterministic agent's
   arguments contain tokens copied verbatim from the injected document, which is
   what makes several edges observable at all. A real model that paraphrases
   rather than copies would break verbatim matching in both conditions - and
   would break it *symmetrically*, which could go either way.
5. **The ground-truth vocabulary is the result.** Ground truth is expressed as
   data-flow edges. A reconstruction built on data-flow telemetry is structurally
   advantaged at recovering data-flow edges. An evaluation framed in a different
   vocabulary (for example: "could an on-call engineer answer these five
   questions correctly?") might not reproduce the gap.
6. **Permission telemetry is cheap to add conventionally.** We assume a
   conventional agent log does not record capability transitions. If that
   assumption is wrong for real deployments, rule R3 and one ground-truth step
   move to the baseline's side of the ledger.
"""


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "(none)"
    return str(value)


def _scenario_table(summary: dict[str, Any], metric: str) -> list[str]:
    lines = ["| scenario | baseline | provenance | verdict |", "| --- | --- | --- | --- |"]
    for scenario_id, entry in summary["scenarios"].items():
        row = entry["comparison"].get(metric)
        if row is None:
            continue
        lines.append(
            f"| {scenario_id} | {_fmt(row['baseline'])} | {_fmt(row['provenance'])} | {row['verdict']} |"
        )
    return lines


def build_results_document(analyses: list[RunAnalysis], sensitivity: dict[str, Any]) -> str:
    summary = build_summary(analyses, sensitivity)
    scenarios = summary["scenarios"]

    lines = [
        "# RESULTS - Experiment 001",
        "",
        "Generated by `python -m experiment run --scenario all`. Every number below "
        "comes from the run that produced this file; nothing here is written by hand.",
        "",
        "## Runs",
        "",
        "| scenario | run id | mode | seed | preview cap | baseline events | provenance events | hash chains intact |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for analysis in analyses:
        entry = scenarios[analysis.run.scenario.scenario_id]
        lines.append(
            f"| {analysis.run.scenario.scenario_id} | `{analysis.run.run_id}` | "
            f"{analysis.run.config.mode} | {analysis.run.config.seed} | "
            f"{analysis.run.config.preview_cap} | {analysis.run.event_counts['baseline']} | "
            f"{analysis.run.event_counts['provenance']} | "
            f"{_fmt(all(entry['telemetry_integrity'].values()))} |"
        )

    lines += ["", "## Reconstruction quality", "", "### Event coverage (all ground-truth steps)", ""]
    lines += _scenario_table(summary, "event_coverage_all")
    lines += [
        "",
        "### Event coverage restricted to conventionally observable steps",
        "",
        "This excludes ground-truth steps that a conventional agent log structurally "
        "cannot record (in this experiment: the capability transition).",
        "",
    ]
    lines += _scenario_table(summary, "event_coverage_conventional_subset")
    lines += ["", "### Ground-truth edge recall (all scored relations)", ""]
    lines += _scenario_table(summary, "edge_recall")
    lines += ["", "### Ground-truth edge precision (all scored relations)", ""]
    lines += _scenario_table(summary, "edge_precision")
    lines += ["", "### Data-flow edge recall, OBSERVED evidence only", ""]
    lines += _scenario_table(summary, "dataflow_edge_recall_observed_evidence_only")
    lines += ["", "### Data-flow edge precision (all evidence)", ""]
    lines += _scenario_table(summary, "dataflow_edge_precision")

    lines += [
        "",
        "## Detection and attribution",
        "",
        "| scenario | expected rules | baseline fired | provenance fired | baseline FP | provenance FP |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for scenario_id, entry in scenarios.items():
        b, p = entry["baseline"], entry["provenance"]
        lines.append(
            f"| {scenario_id} | {_fmt(b['detection_rules_expected'])} | "
            f"{_fmt(b['detection_rules_fired'])} | {_fmt(p['detection_rules_fired'])} | "
            f"{_fmt(b['detection_false_positive_rules'])} | "
            f"{_fmt(p['detection_false_positive_rules'])} |"
        )

    lines += [
        "",
        "### Source attribution",
        "",
        "| scenario | expected source | baseline (observed evidence) | provenance (observed evidence) | provenance (all evidence) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for scenario_id, entry in scenarios.items():
        attribution_b = entry["baseline"]["source_attribution"]
        attribution_p = entry["provenance"]["source_attribution"]
        lines.append(
            f"| {scenario_id} | {_fmt(attribution_b['expected_source'])} | "
            f"{_fmt(attribution_b['attributed_sources_observed_evidence_only'])} | "
            f"{_fmt(attribution_p['attributed_sources_observed_evidence_only'])} | "
            f"{_fmt(attribution_p['attributed_sources_all_evidence'])} |"
        )

    lines += [
        "",
        "### Time to first detection (event index within the stream)",
        "",
        "| scenario | baseline | provenance | dangerous action at |",
        "| --- | --- | --- | --- |",
    ]
    for scenario_id, entry in scenarios.items():
        lines.append(
            f"| {scenario_id} | {_fmt(entry['baseline']['first_detection_sequence'])} | "
            f"{_fmt(entry['provenance']['first_detection_sequence'])} | "
            f"{_fmt(entry['baseline']['dangerous_action_sequence'])} |"
        )

    lines += [
        "",
        "## Capability proportionality (EXPERIMENTAL)",
        "",
        "Identical in both conditions by construction: the declared minimum travels in "
        "the objective event and the exercised set is visible in tool invocations, both "
        "of which the baseline records.",
        "",
        "| scenario | required | exercised | unnecessary | privileged unnecessary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for scenario_id, entry in scenarios.items():
        capability = entry["baseline"]["capability_proportionality"]
        lines.append(
            f"| {scenario_id} | {_fmt(capability['required_capabilities'])} | "
            f"{_fmt(capability['exercised_capabilities'])} | "
            f"{_fmt(capability['unnecessary_capabilities_exercised'])} | "
            f"{_fmt(capability['privileged_unnecessary_capabilities_exercised'])} |"
        )

    lines += ["", "## Pre-registered decision rule", "", PRE_REGISTERED_CRITERIA, "", "### Verdict per scenario", ""]
    lines += ["| scenario | verdict | detection superset | edge-precision delta (provenance - baseline) |", "| --- | --- | --- | --- |"]
    for scenario_id, entry in scenarios.items():
        verdict = entry["verdict"]
        lines.append(
            f"| {scenario_id} | {verdict['verdict']} | {_fmt(verdict['detection_superset'])} | "
            f"{_fmt(verdict['edge_precision_delta'])} |"
        )

    if sensitivity:
        lines += [
            "",
            "## Sensitivity to result-preview truncation",
            "",
            "The result-preview cap is applied identically to both conditions. The "
            "injected document is 932 characters long and the injected instruction "
            "begins at offset 551, so caps below and above that offset bracket the "
            "effect of log truncation. At the largest cap the baseline log contains "
            "the same text the observer saw, so any remaining gap is attributable to "
            "relational fields rather than truncation.",
            "",
            "| scenario | cap | verdict | baseline flow-recall (observed) | provenance flow-recall (observed) |",
            "| --- | --- | --- | --- | --- |",
        ]
        for scenario_id, per_cap in sorted(sensitivity.items()):
            for cap in sorted(per_cap, key=int):
                entry = per_cap[cap]
                lines.append(
                    f"| {scenario_id} | {cap} | {entry['verdict']} | "
                    f"{_fmt(entry['baseline_dataflow_recall_observed'])} | "
                    f"{_fmt(entry['provenance_dataflow_recall_observed'])} |"
                )
        lines += ["", "### Does the advantage survive an untruncated baseline?", ""]
        for scenario_id, entry in scenarios.items():
            attribution = entry.get("truncation_attribution", {})
            if attribution.get("available"):
                lines.append(
                    f"- **{scenario_id}**: verdict at cap "
                    f"{attribution['largest_cap']} is "
                    f"`{attribution['verdict_at_largest_cap']}`; advantage survives an "
                    f"untruncated baseline: "
                    f"{_fmt(attribution['advantage_survives_untruncated_baseline'])}"
                )

    lines += [
        "",
        "## Sample size",
        "",
        summary["sample_size_note"],
        "",
        WHAT_WOULD_CHANGE_OUR_MIND,
    ]
    return "\n".join(lines) + "\n"


def write_results_document(
    analyses: list[RunAnalysis], sensitivity: dict[str, Any], path: Path
) -> Path:
    path.write_text(build_results_document(analyses, sensitivity), encoding="utf-8")
    return path
