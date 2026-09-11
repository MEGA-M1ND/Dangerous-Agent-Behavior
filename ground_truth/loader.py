"""Load ground-truth manifests.

Importing this module is what ``tests/test_ground_truth_isolation.py`` watches
for: only the evaluation layer is permitted to do it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_DIR = Path(__file__).parent / "manifests"

#: Relations the manifests enumerate exhaustively. Precision is scored only over
#: reconstructed edges in these classes, because the manifests deliberately do
#: not enumerate structural bookkeeping edges (invoked, enabled, followed_by,
#: produced, accessed).
SCORED_RELATIONS: frozenset[str] = frozenset(
    {"retrieved", "observed", "data_flowed_to", "permission_changed", "modified"}
)


@dataclass(frozen=True)
class GroundTruth:
    scenario_id: str
    description: str
    dangerous_action: dict[str, Any] | None
    untrusted_source_document: str | None
    trajectory: list[dict[str, Any]]
    nodes: list[str]
    edges: list[dict[str, str]]
    expected_detection_rules: list[str]
    expected_privileged_unnecessary_capabilities: list[str]

    @property
    def edge_keys(self) -> set[tuple[str, str, str]]:
        return {(e["source"], e["relation"], e["target"]) for e in self.edges}

    @property
    def conventional_trajectory(self) -> list[dict[str, Any]]:
        return [s for s in self.trajectory if s.get("conventionally_observable", True)]


def load_ground_truth(scenario_id: str) -> GroundTruth:
    path = MANIFEST_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"no ground-truth manifest for scenario {scenario_id!r}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return GroundTruth(
        scenario_id=data["scenario_id"],
        description=data["description"],
        dangerous_action=data.get("dangerous_action"),
        untrusted_source_document=data.get("untrusted_source_document"),
        trajectory=data["trajectory"],
        nodes=data["nodes"],
        edges=data["edges"],
        expected_detection_rules=data.get("expected_detection_rules", []),
        expected_privileged_unnecessary_capabilities=data.get(
            "expected_privileged_unnecessary_capabilities", []
        ),
    )


def available_scenarios() -> list[str]:
    return sorted(p.stem for p in MANIFEST_DIR.glob("*.json"))
