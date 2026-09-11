"""Command-line interface.

    python -m experiment run --scenario benign
    python -m experiment run --scenario injected
    python -m experiment run --scenario safe-alternative
    python -m experiment run --scenario all --seed 42
    python -m experiment sensitivity

Everything runs locally, offline, against the synthetic mock environment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiment.evaluation.report import RunAnalysis, analyse_run, write_artifacts
from experiment.evaluation.summary import (
    write_results_document,
    write_sensitivity_artifacts,
    write_summary,
)
from experiment.observability.baseline import DEFAULT_PREVIEW_CAP
from experiment.run import RunConfig, execute_run
from experiment.scenarios import SCENARIO_ORDER

#: Preview caps swept by the sensitivity analysis. The injected document is 932
#: characters long and the injected instruction starts at offset 551, so caps
#: below and above that offset bracket the effect of log truncation.
SENSITIVITY_CAPS: tuple[int, ...] = (128, 512, 1024, 4096)


def _normalise(scenario: str) -> str:
    return scenario.replace("-", "_")


def _run_scenarios(
    scenario_ids: list[str], mode: str, seed: int, preview_cap: int, artifacts: Path
) -> list[RunAnalysis]:
    analyses: list[RunAnalysis] = []
    for scenario_id in scenario_ids:
        config = RunConfig(
            scenario_id=scenario_id,
            mode=mode,
            seed=seed,
            preview_cap=preview_cap,
            artifacts_root=artifacts,
        )
        run = execute_run(config)
        analysis = analyse_run(run)
        written = write_artifacts(analysis)
        analyses.append(analysis)
        print(f"[{scenario_id}] run {run.run_id}: {len(written) + 3} artifacts in {run.run_dir}")
    return analyses


def command_run(args: argparse.Namespace) -> int:
    scenario = _normalise(args.scenario)
    scenario_ids = list(SCENARIO_ORDER) if scenario == "all" else [scenario]
    artifacts = Path(args.artifacts)

    analyses = _run_scenarios(scenario_ids, args.mode, args.seed, args.preview_cap, artifacts)

    sensitivity: dict[str, Any] = {}
    if scenario == "all" and args.mode == "deterministic" and not args.skip_sensitivity:
        sensitivity = run_sensitivity(args.seed, artifacts)

    summary_path = write_summary(analyses, sensitivity, artifacts)
    print(f"summary: {summary_path}")

    if scenario == "all":
        results_path = write_results_document(analyses, sensitivity, Path(args.results))
        print(f"results: {results_path}")

    for analysis in analyses:
        print(
            f"  {analysis.run.scenario.scenario_id}: "
            f"baseline flow-recall(observed)="
            f"{analysis.baseline.metrics.values['dataflow_edge_recall_observed_evidence_only']} "
            f"provenance="
            f"{analysis.provenance.metrics.values['dataflow_edge_recall_observed_evidence_only']}"
        )
    return 0


def run_sensitivity(seed: int, artifacts: Path) -> dict[str, Any]:
    """Re-run every scenario at several result-preview caps.

    The cap is applied identically to both conditions, so this is a symmetric
    sweep, not a handicap on one side.
    """
    from experiment.evaluation.verdict import verdict_for_scenario

    results: dict[str, dict[str, Any]] = {}
    root = artifacts / "sensitivity"
    for cap in SENSITIVITY_CAPS:
        for scenario_id in SCENARIO_ORDER:
            config = RunConfig(
                scenario_id=scenario_id,
                mode="deterministic",
                seed=seed,
                preview_cap=cap,
                artifacts_root=root / f"cap-{cap}",
            )
            analysis = analyse_run(execute_run(config))
            entry = verdict_for_scenario(analysis.baseline.metrics, analysis.provenance.metrics)
            entry["baseline_event_coverage"] = analysis.baseline.metrics.values["event_coverage_all"]
            entry["provenance_event_coverage"] = analysis.provenance.metrics.values["event_coverage_all"]
            entry["baseline_dataflow_precision"] = analysis.baseline.metrics.values["dataflow_edge_precision"]
            entry["provenance_dataflow_precision"] = analysis.provenance.metrics.values["dataflow_edge_precision"]
            results.setdefault(scenario_id, {})[str(cap)] = entry
    write_sensitivity_artifacts(results, artifacts)
    return results


def command_sensitivity(args: argparse.Namespace) -> int:
    results = run_sensitivity(args.seed, Path(args.artifacts))
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experiment",
        description="Experiment 001 - independent reconstruction of dangerous agent behavior",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run one scenario or all of them")
    run_parser.add_argument(
        "--scenario",
        default="all",
        choices=["benign", "injected", "safe-alternative", "safe_alternative", "all"],
    )
    run_parser.add_argument("--mode", default="deterministic", choices=["deterministic", "llm"])
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--preview-cap", type=int, default=DEFAULT_PREVIEW_CAP)
    run_parser.add_argument("--artifacts", default="artifacts")
    run_parser.add_argument("--results", default="RESULTS.md")
    run_parser.add_argument(
        "--skip-sensitivity", action="store_true", help="skip the preview-cap sweep"
    )
    run_parser.set_defaults(func=command_run)

    sensitivity_parser = subparsers.add_parser(
        "sensitivity", help="sweep the result-preview cap and re-score both conditions"
    )
    sensitivity_parser.add_argument("--seed", type=int, default=42)
    sensitivity_parser.add_argument("--artifacts", default="artifacts")
    sensitivity_parser.set_defaults(func=command_sensitivity)
    return parser


def main(argv: list[str] | None = None) -> int:
    from experiment.agent.adapters import LLMConfigurationError

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except LLMConfigurationError as exc:
        parser.exit(2, f"llm mode is not configured: {exc}\n")
