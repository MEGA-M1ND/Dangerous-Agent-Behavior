"""Two runs of the same (scenario, mode, seed) must be byte-identical."""

from __future__ import annotations

from experiment.run import RunConfig, execute_run
from experiment.scenarios import SCENARIO_ORDER


def _telemetry(run) -> tuple[str, str]:
    return (
        run.baseline_path.read_text(encoding="utf-8"),
        run.provenance_path.read_text(encoding="utf-8"),
    )


def test_repeated_runs_produce_identical_telemetry(tmp_path):
    for scenario_id in SCENARIO_ORDER:
        first = execute_run(RunConfig(scenario_id, seed=42, artifacts_root=tmp_path / "a"))
        second = execute_run(RunConfig(scenario_id, seed=42, artifacts_root=tmp_path / "b"))
        assert first.run_id == second.run_id
        assert _telemetry(first) == _telemetry(second), scenario_id
        assert first.chain_digests == second.chain_digests


def test_rerunning_into_the_same_directory_is_idempotent(tmp_path):
    first = execute_run(RunConfig("injected", artifacts_root=tmp_path))
    before = _telemetry(first)
    second = execute_run(RunConfig("injected", artifacts_root=tmp_path))
    assert _telemetry(second) == before
    assert first.run_dir == second.run_dir


def test_run_id_depends_on_scenario_mode_and_seed(tmp_path):
    a = execute_run(RunConfig("injected", seed=42, artifacts_root=tmp_path))
    b = execute_run(RunConfig("injected", seed=7, artifacts_root=tmp_path))
    assert a.run_id != b.run_id


def test_seed_does_not_change_the_deterministic_trajectory(tmp_path):
    """The deterministic agent is seed-independent by construction; record that."""
    a = execute_run(RunConfig("injected", seed=42, artifacts_root=tmp_path))
    b = execute_run(RunConfig("injected", seed=7, artifacts_root=tmp_path))
    assert a.agent_result.exercised_capabilities == b.agent_result.exercised_capabilities


def test_metrics_are_reproducible(tmp_path):
    from experiment.evaluation.report import analyse_run

    first = analyse_run(execute_run(RunConfig("injected", artifacts_root=tmp_path / "a")))
    second = analyse_run(execute_run(RunConfig("injected", artifacts_root=tmp_path / "b")))
    assert first.to_dict() == second.to_dict()
