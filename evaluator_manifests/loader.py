"""Load evaluator manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_DIR = Path(__file__).parent / "manifests"

#: Vocabulary that must not appear in any alias used for scoring. If an alias
#: contained these, the rubric would be rewarding investigators for adopting the
#: treatment's terminology - which is the exact flaw Experiment 002 exists to
#: avoid.
FORBIDDEN_ALIAS_TERMS: tuple[str, ...] = (
    "provenance",
    "data flow",
    "data_flowed_to",
    "dataflow",
    "lineage",
    "edge",
    "graph",
    "source_ids",
    "input_event_ids",
    "obs://",
    "cred://",
    "flow_evidence",
    "observation:",
)


@dataclass(frozen=True)
class EvaluatorManifest:
    case_id: str
    raw: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    @property
    def ambiguity_level(self) -> str:
        return self.raw["ambiguity_level"]

    def alias_strings(self) -> list[str]:
        """Every alias the rubric matches against, for the vocabulary check."""
        collected: list[str] = []

        def walk(node: Any, key: str = "") -> None:
            if isinstance(node, dict):
                for child_key, child in node.items():
                    walk(child, child_key)
            elif isinstance(node, list):
                for child in node:
                    walk(child, key)
            elif isinstance(node, str) and ("alias" in key or "patterns" in key):
                collected.append(node)

        walk(self.raw)
        return collected


def load_manifest(case_id: str) -> EvaluatorManifest:
    path = MANIFEST_DIR / f"{case_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"no evaluator manifest for {case_id!r}")
    return EvaluatorManifest(case_id=case_id, raw=json.loads(path.read_text(encoding="utf-8")))


def manifest_ids() -> list[str]:
    return sorted(p.stem for p in MANIFEST_DIR.glob("*.json"))
