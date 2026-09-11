"""Study generation: runs, packets, assignment and the private material.

Public material (what a participant receives) and private material (what only the
experimenters see) are written to separate directory trees, and a test asserts
that nothing private ends up under the public one.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiment.observability.sinks import read_events
from experiment.run import RunConfig, RunOutput, execute_run
from experiment2.blinding import (
    assign_participants,
    assignment_summary,
    build_condition_map,
    packet_id,
)
from experiment2.cases import CASES, CONDITIONS, PREVIEW_CAP, RUN_SEED
from experiment2.packets import (
    FORBIDDEN_PACKET_TERMS,
    Packet,
    answers_template,
    build_packet,
    evidence_volume,
    render_questionnaire,
    render_readable,
)
from experiment2.questionnaire import QUESTIONNAIRE_VERSION

DEFAULT_ROOT = Path("artifacts/experiment_002")
DEFAULT_STUDY_SEED = 20260911
TEMPLATE_PARTICIPANT = "participant_template"

PACKET_FILES = (
    "telemetry.jsonl",
    "telemetry_readable.md",
    "questionnaire.md",
    "metadata_public.json",
    "answers_template.json",
)


@dataclass
class BuiltPacket:
    packet_id: str
    case_id: str
    condition: str
    packet: Packet
    directory: Path
    volume: dict[str, Any]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write(path, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def run_cases(root: Path, seed: int = RUN_SEED) -> dict[str, RunOutput]:
    """Execute each case once. Both conditions come from the same run."""
    runs: dict[str, RunOutput] = {}
    for case in CASES:
        runs[case.case_id] = execute_run(
            RunConfig(
                scenario_id=case.scenario_id,
                mode="deterministic",
                seed=seed,
                preview_cap=PREVIEW_CAP,
                artifacts_root=root / "private" / "runs",
            )
        )
    return runs


def check_packet_is_blind(directory: Path) -> list[str]:
    """Every term that would reveal the condition or the answer. Must be empty."""
    problems: list[str] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for term in FORBIDDEN_PACKET_TERMS:
            if term in text:
                problems.append(f"{path.name}: contains {term!r}")
    return problems


def build_packets(
    root: Path, runs: dict[str, RunOutput], study_seed: int
) -> list[BuiltPacket]:
    built: list[BuiltPacket] = []
    for case in CASES:
        run = runs[case.case_id]
        streams = {"baseline": run.baseline_path, "provenance": run.provenance_path}
        for condition in CONDITIONS:
            identifier = packet_id(study_seed, case.case_id, condition)
            packet = build_packet(identifier, case.case_id, read_events(streams[condition]))
            directory = root / "packets" / identifier

            telemetry = "\n".join(
                json.dumps(record.data, sort_keys=True) for record in packet.records
            ) + "\n"
            readable = render_readable(packet)
            volume = evidence_volume(packet, readable, telemetry)

            _write(directory / "telemetry.jsonl", telemetry)
            _write(directory / "telemetry_readable.md", readable)
            _write(directory / "questionnaire.md", render_questionnaire(packet))
            _write_json(directory / "answers_template.json", answers_template(packet))
            _write_json(
                directory / "metadata_public.json",
                {
                    "packet_id": identifier,
                    "case_reference": case.case_id,
                    "questionnaire_version": QUESTIONNAIRE_VERSION,
                    "record_count": len(packet.records),
                    "evidence_volume": volume,
                    "note": (
                        "This package contains everything you have been given for this "
                        "case. Answer from it alone."
                    ),
                },
            )

            problems = check_packet_is_blind(directory)
            if problems:
                raise RuntimeError(f"packet {identifier} is not blind: {problems}")

            built.append(
                BuiltPacket(identifier, case.case_id, condition, packet, directory, volume)
            )
    return built


def build_participant_bundle(
    root: Path, participant_id: str, sequence: list[dict[str, str]]
) -> Path:
    """Materialise one participant's packets, in their presentation order."""
    bundle = root / "packets" / participant_id
    if bundle.exists():
        shutil.rmtree(bundle)
    lines = [
        f"# Investigation set for `{participant_id}`",
        "",
        "Work through the cases in the order below, one at a time. Do not skip "
        "ahead, and do not go back and revise an earlier case after reading a "
        "later one.",
        "",
        "For each case: open the folder, read `telemetry_readable.md`, then answer "
        "`questionnaire.md` by filling in a copy of `answers_template.json`.",
        "",
        "| order | folder |",
        "| --- | --- |",
    ]
    for position, entry in enumerate(sequence, start=1):
        source = root / "packets" / entry["packet_id"]
        destination = bundle / f"{position:02d}_{entry['packet_id']}"
        destination.mkdir(parents=True, exist_ok=True)
        for name in PACKET_FILES:
            shutil.copyfile(source / name, destination / name)
        lines.append(f"| {position} | `{destination.name}` |")
    _write(bundle / "README.md", "\n".join(lines) + "\n")
    return bundle


def build_study(
    root: Path = DEFAULT_ROOT,
    study_seed: int = DEFAULT_STUDY_SEED,
    participants: list[str] | None = None,
    run_seed: int = RUN_SEED,
) -> dict[str, Any]:
    root = Path(root)
    runs = run_cases(root, seed=run_seed)
    built = build_packets(root, runs, study_seed)

    participant_ids = participants or []
    assignments = assign_participants(study_seed, [TEMPLATE_PARTICIPANT, *participant_ids])
    for assignment in assignments:
        build_participant_bundle(root, assignment.participant_id, assignment.sequence)

    # -- private material --------------------------------------------------- #
    private = root / "private"
    _write_json(private / "condition_map.json", build_condition_map(study_seed))
    manifests_source = Path(__file__).resolve().parents[1] / "evaluator_manifests" / "manifests"
    manifests_target = private / "evaluator_manifests"
    manifests_target.mkdir(parents=True, exist_ok=True)
    for path in sorted(manifests_source.glob("*.json")):
        shutil.copyfile(path, manifests_target / path.name)

    # -- study design ------------------------------------------------------- #
    real_assignments = [a for a in assignments if a.participant_id != TEMPLATE_PARTICIPANT]
    design: dict[str, Any] = {
        "study_seed": study_seed,
        "run_seed": run_seed,
        "preview_cap": PREVIEW_CAP,
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "cases": [
            {
                "case_id": case.case_id,
                "run_id": runs[case.case_id].run_id,
                "objective": case.objective,
                "packets": {
                    condition: packet_id(study_seed, case.case_id, condition)
                    for condition in CONDITIONS
                },
            }
            for case in CASES
        ],
        "packets": [
            {
                "packet_id": item.packet_id,
                "case_id": item.case_id,
                "record_count": item.volume["record_count"],
                "evidence_volume": item.volume,
            }
            for item in built
        ],
        "assignment": {
            "strategy": "counterbalanced, between-subject within a case",
            "participants": [
                {"participant_id": a.participant_id, "sequence": a.sequence}
                for a in assignments
            ],
            "summary": assignment_summary(real_assignments) if real_assignments else None,
        },
        "evidence_volume_by_condition": _volume_by_condition(built),
        "note": (
            "Packet identifiers and assignment are derived from study_seed; the "
            "underlying runs are derived from run_seed. Both are reproducible."
        ),
    }
    _write_json(root / "study_design.json", design)

    for directory in ("responses", "adjudications", "metrics", "reports"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    return design


def _volume_by_condition(built: list[BuiltPacket]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for condition in CONDITIONS:
        items = [b for b in built if b.condition == condition]
        summary[condition] = {
            key: round(sum(b.volume[key] for b in items) / len(items), 1)
            for key in (
                "record_count",
                "link_record_count",
                "readable_characters",
                "readable_lines",
                "readable_estimated_tokens",
                "estimated_reading_minutes_at_200_wpm",
            )
        }
    baseline, provenance = summary["baseline"], summary["provenance"]
    summary["provenance_over_baseline"] = {
        key: round(provenance[key] / baseline[key], 3) if baseline[key] else None
        for key in baseline
    }
    return summary


def load_condition_map(root: Path = DEFAULT_ROOT) -> dict[str, dict[str, str]]:
    """Evaluator-side lookup. Never read by packet generation or by investigators."""
    return json.loads((Path(root) / "private" / "condition_map.json").read_text(encoding="utf-8"))


def load_packet(root: Path, packet_id_value: str) -> Packet:
    """Rebuild a packet object from its written telemetry, for scoring."""
    from experiment2.packets import PacketRecord

    path = Path(root) / "packets" / packet_id_value / "telemetry.jsonl"
    records = [
        PacketRecord(record_no=json.loads(line)["record_no"], data=json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    case_id = records[0].data.get("objective_id", "") if records else ""
    del case_id
    return Packet(packet_id=packet_id_value, case_id="", records=records)
