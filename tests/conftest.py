"""Shared fixtures.

Every test runs the experiment into a temporary artifacts directory so the
repository's own ``artifacts/`` tree is never a test dependency.
"""

from __future__ import annotations

import pytest

from experiment.evaluation.report import analyse_run
from experiment.observability.sinks import read_events
from experiment.run import RunConfig, execute_run
from experiment.scenarios import SCENARIO_ORDER


@pytest.fixture(scope="session")
def runs(tmp_path_factory) -> dict:
    """One deterministic run per scenario, shared across the session."""
    root = tmp_path_factory.mktemp("artifacts")
    return {
        scenario_id: execute_run(RunConfig(scenario_id, artifacts_root=root))
        for scenario_id in SCENARIO_ORDER
    }


@pytest.fixture(scope="session")
def analyses(runs) -> dict:
    return {scenario_id: analyse_run(run) for scenario_id, run in runs.items()}


@pytest.fixture(scope="session")
def events(runs) -> dict:
    return {
        scenario_id: {
            "baseline": read_events(run.baseline_path),
            "provenance": read_events(run.provenance_path),
        }
        for scenario_id, run in runs.items()
    }
