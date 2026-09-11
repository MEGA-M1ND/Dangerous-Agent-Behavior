"""Evaluator material must not reach the investigator-facing code paths.

Experiment 001 isolated its ground truth to a single importer. Experiment 002
does the same for its evaluator manifests, with one deliberate exception that is
named here rather than hidden: the ``manifest_oracle`` mock reads them on
purpose, which is why its output is never study evidence.
"""

from __future__ import annotations

import ast
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Modules that build, blind or deliver packets, or that drive an investigator.
#: None of them may see evaluator material.
INVESTIGATOR_FACING = (
    "experiment2/packets.py",
    "experiment2/blinding.py",
    "experiment2/study.py",
    "experiment2/questionnaire.py",
    "experiment2/responses.py",
    "experiment2/cases.py",
    "experiment2/reporting.py",
    "experiment2/investigators/llm.py",
)

#: The only modules permitted to import evaluator manifests.
PERMITTED_IMPORTERS = {
    "experiment2/scoring.py",
    "experiment2/metrics.py",
    "experiment2/adjudication.py",
    # Reads manifests on purpose, to prove the rubric is satisfiable. Its output
    # is stored in a separate namespace and never counted as evidence.
    "experiment2/investigators/mock.py",
}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    return names


def _code_only(path: Path) -> str:
    pieces: list[str] = []
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type not in (tokenize.COMMENT, tokenize.STRING):
                pieces.append(token.string)
    return " ".join(pieces)


def test_investigator_facing_modules_do_not_import_evaluator_manifests():
    for relative in INVESTIGATOR_FACING:
        path = PROJECT_ROOT / relative
        assert not any(
            name.startswith("evaluator_manifests") for name in _imports(path)
        ), relative


def test_investigator_facing_modules_do_not_reference_evaluator_manifests_in_code():
    for relative in INVESTIGATOR_FACING:
        assert "evaluator_manifests" not in _code_only(PROJECT_ROOT / relative), relative


def test_only_the_permitted_modules_import_evaluator_manifests():
    importers = set()
    for path in sorted((PROJECT_ROOT / "experiment2").rglob("*.py")):
        if any(name.startswith("evaluator_manifests") for name in _imports(path)):
            importers.add(str(path.relative_to(PROJECT_ROOT)))
    assert importers == PERMITTED_IMPORTERS


def test_experiment_001_packages_never_see_experiment_002_material():
    """Experiment 001 must remain a standalone experiment."""
    for path in sorted((PROJECT_ROOT / "experiment").rglob("*.py")):
        names = _imports(path)
        assert not any(name.startswith("experiment2") for name in names), path
        assert not any(name.startswith("evaluator_manifests") for name in names), path


def test_manifests_are_authored_from_design_not_from_responses():
    from evaluator_manifests import load_manifest, manifest_ids

    for case_id in manifest_ids():
        authored = load_manifest(case_id)["authored_from"]
        assert "scenario design" in authored
        assert "investigator response" in authored


def test_cases_and_manifests_agree():
    from evaluator_manifests import manifest_ids

    from experiment2.cases import CASE_IDS

    assert sorted(CASE_IDS) == manifest_ids()


def test_scoring_never_reads_a_packet_directory():
    """Scoring works from the response and the manifest, not from the delivery tree."""
    source = _code_only(PROJECT_ROOT / "experiment2" / "scoring.py")
    assert "read_text" not in source
    assert "packets" not in source or "Packet" in source


def test_experiment_001_telemetry_is_byte_identical_to_its_committed_artifacts(tmp_path):
    """Experiment 002 extended shared modules; Experiment 001 must be untouched.

    Skipped if the committed artifacts are absent (a fresh checkout that has not
    run Experiment 001 yet).
    """
    import hashlib

    import pytest

    from experiment.run import RunConfig, execute_run
    from experiment.scenarios import SCENARIO_ORDER

    committed = PROJECT_ROOT / "artifacts"
    if not any(committed.glob("run-*")):
        pytest.skip("Experiment 001 artifacts are not present in this checkout")

    for scenario_id in SCENARIO_ORDER:
        run = execute_run(RunConfig(scenario_id, artifacts_root=tmp_path))
        for name in ("baseline_events.jsonl", "provenance_events.jsonl"):
            reference = committed / run.run_id / name
            assert reference.exists(), reference
            assert (
                hashlib.sha256(reference.read_bytes()).hexdigest()
                == hashlib.sha256((run.run_dir / name).read_bytes()).hexdigest()
            ), f"{scenario_id}/{name} changed"
