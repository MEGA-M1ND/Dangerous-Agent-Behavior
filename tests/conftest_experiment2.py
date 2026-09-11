"""Shared Experiment 002 fixtures, imported by tests/conftest.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from experiment2.study import DEFAULT_STUDY_SEED, build_study, load_condition_map, load_packet


@pytest.fixture(scope="session")
def study(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("experiment_002")
    design = build_study(
        root=root, study_seed=DEFAULT_STUDY_SEED, participants=["P1", "P2", "P3", "P4"]
    )
    return {"root": Path(root), "design": design, "conditions": load_condition_map(root)}


@pytest.fixture(scope="session")
def packets(study) -> dict:
    return {
        packet_id: {
            "packet": load_packet(study["root"], packet_id),
            "case_id": entry["case_id"],
            "condition": entry["condition"],
            "directory": study["root"] / "packets" / packet_id,
        }
        for packet_id, entry in study["conditions"].items()
    }
