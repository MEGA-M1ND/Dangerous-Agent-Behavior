"""Ground truth must not leak into observation, reconstruction or detection.

Enforced three ways:

1. statically, by parsing every module in the runtime packages and rejecting any
   import of ``ground_truth``;
2. textually, by rejecting the string anywhere in those packages;
3. at runtime, by poisoning the ground-truth loader and then running a complete
   observation, reconstruction and detection cycle.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Packages that must never see ground truth.
ISOLATED_PACKAGES = (
    "experiment/observability",
    "experiment/analysis",
    "experiment/agent",
    "experiment/mockenv",
)

#: Modules outside those packages that are also part of the observed run.
ISOLATED_MODULES = (
    "experiment/gateway.py",
    "experiment/run.py",
    "experiment/events.py",
    "experiment/redaction.py",
    "experiment/textmatch.py",
    "experiment/scenarios.py",
    "experiment/ids.py",
)

#: The single module permitted to import ground truth.
PERMITTED_IMPORTER = "experiment/evaluation/metrics.py"


def _isolated_files() -> list[Path]:
    files: list[Path] = []
    for package in ISOLATED_PACKAGES:
        files.extend(sorted((PROJECT_ROOT / package).rglob("*.py")))
    files.extend(PROJECT_ROOT / module for module in ISOLATED_MODULES)
    return files


def test_isolated_modules_do_not_import_ground_truth():
    for path in _isolated_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("ground_truth"), path
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("ground_truth"), path


def _code_only(path: Path) -> str:
    """Source with comments and string literals (including docstrings) removed."""
    import tokenize

    pieces: list[str] = []
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            pieces.append(token.string)
    return " ".join(pieces)


def test_isolated_modules_do_not_reference_ground_truth_in_code():
    """Docstrings may describe the rule; no executable code may name it."""
    for path in _isolated_files():
        assert "ground_truth" not in _code_only(path), path


def test_exactly_one_module_imports_ground_truth():
    importers: list[str] = []
    for path in sorted((PROJECT_ROOT / "experiment").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            imported = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(name.startswith("ground_truth") for name in imported):
                importers.append(str(path.relative_to(PROJECT_ROOT)))
    assert sorted(set(importers)) == [PERMITTED_IMPORTER]


def test_reconstruction_runs_with_the_ground_truth_loader_poisoned(monkeypatch, tmp_path):
    """A run, reconstruction and detection cycle must not touch ground truth."""
    import ground_truth.loader as loader

    def _poisoned(*args, **kwargs):  # pragma: no cover - must never be called
        raise AssertionError("ground truth was read outside the evaluation layer")

    monkeypatch.setattr(loader, "load_ground_truth", _poisoned)

    from experiment.analysis.detection import detect
    from experiment.analysis.reconstruct import reconstruct
    from experiment.observability.sinks import read_events
    from experiment.run import RunConfig, execute_run

    run = execute_run(RunConfig("injected", artifacts_root=tmp_path))
    for path in (run.baseline_path, run.provenance_path):
        stream = read_events(path)
        reconstruction = reconstruct(stream)
        detect(reconstruction, stream)


def test_ground_truth_manifests_are_authored_from_design_not_from_output():
    import json

    for path in sorted((PROJECT_ROOT / "ground_truth" / "manifests").glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert "scenario design" in manifest["authored_from"]


def test_scenarios_and_manifests_agree():
    from ground_truth.loader import available_scenarios

    from experiment.scenarios import SCENARIO_ORDER

    assert sorted(SCENARIO_ORDER) == available_scenarios()
