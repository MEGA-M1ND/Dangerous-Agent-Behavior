"""Command line for Experiment 002.

    python -m experiment2 preregister
    python -m experiment2 build --participants P1,P2,P3,P4
    python -m experiment2 start --participant P1 --packet case_01_packet_XXXX
    python -m experiment2 submit --participant P1 --answers path/to/answers.json
    python -m experiment2 investigate --investigator mock --profile keyword_scanner
    python -m experiment2 investigate --investigator llm --repeats 3
    python -m experiment2 metrics
    python -m experiment2 report

Order matters in one place: `preregister` must run before `metrics`, and the
metrics command refuses otherwise.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from experiment2 import reporting
from experiment2.investigators import mock
from experiment2.metrics import PreregistrationMissing, compute_all, score_all
from experiment2.responses import (
    MOCK_NAMESPACE,
    load_responses,
    response_counts,
    start,
    store_response,
    submit,
)
from experiment2.scoring import score_response
from experiment2.study import (
    DEFAULT_ROOT,
    DEFAULT_STUDY_SEED,
    build_study,
    load_condition_map,
    load_packet,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def command_preregister(args: argparse.Namespace) -> int:
    root = Path(args.root)
    design_path = root / "study_design.json"
    design = reporting.load_json(design_path)
    text = reporting.build_preregistration(design or None)
    target = Path(args.output)
    reporting.write_document(target, text)
    reporting.write_document(root / "preregistration.md", text)
    print(f"pre-registration written: {target}")
    if not design:
        print("note: run `build` first to include measured evidence-volume figures")
    return 0


def command_build(args: argparse.Namespace) -> int:
    participants = [p.strip() for p in (args.participants or "").split(",") if p.strip()]
    design = build_study(
        root=Path(args.root), study_seed=args.seed, participants=participants
    )
    print(f"packets: {len(design['packets'])} in {Path(args.root) / 'packets'}")
    print(f"participant bundles: {len(design['assignment']['participants'])}")
    ratio = design["evidence_volume_by_condition"]["provenance_over_baseline"]
    print(
        "evidence volume, condition B over condition A: "
        f"characters x{ratio['readable_characters']}, "
        f"reading time x{ratio['estimated_reading_minutes_at_200_wpm']}"
    )
    return 0


def command_start(args: argparse.Namespace) -> int:
    path = start(Path(args.root), args.participant, args.packet)
    print(f"started: {path}")
    return 0


def command_submit(args: argparse.Namespace) -> int:
    answers = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    response = submit(Path(args.root), answers, args.participant)
    print(
        f"stored {response.packet_id} for {response.participant_id} "
        f"(timing reliable: {response.timing_is_reliable})"
    )
    return 0


def command_investigate(args: argparse.Namespace) -> int:
    root = Path(args.root)
    condition_map = load_condition_map(root)
    if args.investigator == "mock":
        return _run_mock(root, condition_map, args)
    return _run_llm(root, condition_map, args)


def _run_mock(root: Path, condition_map: dict, args: argparse.Namespace) -> int:
    profiles = [args.profile] if args.profile else list(mock.PROFILES)
    written = 0
    for packet_id, entry in sorted(condition_map.items()):
        packet = load_packet(root, packet_id)
        for profile in profiles:
            response = mock.build(profile, f"mock_{profile}", packet, entry["case_id"])
            store_response(root, response, MOCK_NAMESPACE)
            written += 1
    summary = _mock_summary(root, condition_map, profiles)
    _write_json(root / "metrics" / "mock_pipeline_check.json", summary)
    print(f"mock responses written: {written} (namespace {MOCK_NAMESPACE}; not evidence)")
    for profile, row in sorted(summary["by_profile"].items()):
        print(f"  {profile:18s} A={row['baseline']}  B={row['provenance']}")
    return 0


def _mock_summary(root: Path, condition_map: dict, profiles: list[str]) -> dict[str, Any]:
    scores: dict[str, dict[str, list[float]]] = {
        profile: {"baseline": [], "provenance": []} for profile in profiles
    }
    for packet_id, entry in sorted(condition_map.items()):
        packet = load_packet(root, packet_id)
        for profile in profiles:
            response = mock.build(profile, f"mock_{profile}", packet, entry["case_id"])
            scored = score_response(response, entry["case_id"], packet)
            scores[profile][entry["condition"]].append(float(scored.reconstruction_score))
    return {
        "by_profile": {
            profile: {
                condition: round(statistics.fmean(values), 3) if values else None
                for condition, values in conditions.items()
            }
            for profile, conditions in scores.items()
        },
        "note": (
            "Mock investigators are fixtures for testing the rubric and the "
            "workflow. They are not investigators and these numbers are not "
            "experimental evidence."
        ),
    }


def _run_llm(root: Path, condition_map: dict, args: argparse.Namespace) -> int:
    from experiment2.investigators import llm

    if not llm.is_configured():
        print(
            "LLM investigator not executed: no model provider is configured. "
            "See LLM_INVESTIGATOR.md."
        )
        return 0
    records: list[dict[str, Any]] = []
    for packet_id, entry in sorted(condition_map.items()):
        for repetition in range(1, args.repeats + 1):
            run = llm.investigate(
                packet_dir=root / "packets" / packet_id,
                packet_id=packet_id,
                participant_id=f"llm_r{repetition}",
                repetition=repetition,
                temperature=args.temperature,
            )
            store_response(root, run.response, f"llm_r{repetition}")
            records.append({"packet_id": packet_id, **run.record()})
            print(f"  {packet_id} repetition {repetition}: recorded")
        del entry
    _write_json(root / "responses" / "llm_raw.json", records)
    print(f"model responses recorded: {len(records)}")
    return 0


def command_metrics(args: argparse.Namespace) -> int:
    root = Path(args.root)
    try:
        results = compute_all(root, REPOSITORY_ROOT, include_mock=args.include_mock)
    except PreregistrationMissing as exc:
        print(f"refusing to compute metrics: {exc}")
        return 2
    _write_json(root / "metrics" / "aggregate.json", results["aggregate"])
    _write_json(root / "metrics" / "per_case.json", results["per_case"])
    _write_json(root / "metrics" / "per_participant.json", results["per_participant"])
    _write_json(root / "metrics" / "scored_responses.json", results["responses"])

    responses = load_responses(root, include_mock=args.include_mock)
    if responses:
        from experiment2.adjudication import write_sheets

        scored = score_all(root, responses)
        by_packet = {(r.participant_id, r.packet_id): r for r in responses}
        pairs = [
            (by_packet[(row.participant_id, row.packet_id)], row)
            for row, _ in scored
            if (row.participant_id, row.packet_id) in by_packet
        ]
        sheets = write_sheets(root, pairs)
        print(f"adjudication sheets: {len(sheets)}")
    print(f"responses scored: {results['aggregate']['totals']['responses']}")
    return 0


def command_report(args: argparse.Namespace) -> int:
    root = Path(args.root)
    design = reporting.load_json(root / "study_design.json")
    metrics = {
        "aggregate": reporting.load_json(root / "metrics" / "aggregate.json"),
        "per_case": reporting.load_json(root / "metrics" / "per_case.json"),
    }
    if not metrics["aggregate"]:
        metrics = None
    mock_check = reporting.load_json(root / "metrics" / "mock_pipeline_check.json") or None

    results = reporting.build_results(design, metrics, mock_check, response_counts(root))
    validity = reporting.build_validity(design)
    reporting.write_document(Path(args.results), results)
    reporting.write_document(root / "reports" / "RESULTS.md", results)
    reporting.write_document(Path(args.validity), validity)
    reporting.write_document(root / "reports" / "VALIDITY_REVIEW.md", validity)
    print(f"results: {args.results}")
    print(f"validity review: {args.validity}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experiment2",
        description="Experiment 002 - blinded investigator reconstruction",
    )
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    prereg = subparsers.add_parser("preregister", help="write the pre-registration")
    prereg.add_argument("--output", default="EXPERIMENT_002_PREREGISTRATION.md")
    prereg.set_defaults(func=command_preregister)

    build = subparsers.add_parser("build", help="run the cases and generate blinded packets")
    build.add_argument("--seed", type=int, default=DEFAULT_STUDY_SEED)
    build.add_argument("--participants", default="", help="comma-separated participant ids")
    build.set_defaults(func=command_build)

    started = subparsers.add_parser("start", help="record that a participant has begun a packet")
    started.add_argument("--participant", required=True)
    started.add_argument("--packet", required=True)
    started.set_defaults(func=command_start)

    submitted = subparsers.add_parser("submit", help="import a completed questionnaire")
    submitted.add_argument("--participant")
    submitted.add_argument("--answers", required=True)
    submitted.set_defaults(func=command_submit)

    investigate = subparsers.add_parser("investigate", help="run an automated investigator")
    investigate.add_argument("--investigator", choices=["mock", "llm"], default="mock")
    investigate.add_argument("--profile", choices=list(mock.PROFILES))
    investigate.add_argument("--repeats", type=int, default=1)
    investigate.add_argument("--temperature", type=float, default=0.0)
    investigate.set_defaults(func=command_investigate)

    metrics = subparsers.add_parser("metrics", help="score responses and aggregate")
    metrics.add_argument("--include-mock", action="store_true")
    metrics.set_defaults(func=command_metrics)

    report = subparsers.add_parser("report", help="write the results and validity documents")
    report.add_argument("--results", default="EXPERIMENT_002_RESULTS.md")
    report.add_argument("--validity", default="EXPERIMENT_002_VALIDITY.md")
    report.set_defaults(func=command_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
