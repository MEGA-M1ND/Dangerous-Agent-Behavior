"""Deterministic identifiers and clocks.

Reproducibility requires that two runs of the same (scenario, mode, seed) produce
byte-identical telemetry. We therefore derive every identifier from a namespace
hash rather than from randomness, and we drive timestamps from a virtual clock in
deterministic mode.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

# Fixed namespace so run/event ids are stable across machines and interpreters.
_NAMESPACE = uuid.UUID("6f1c2f6e-5a3d-4c0f-9a5f-0b7c9d1e2f30")

# Virtual epoch used in deterministic mode. Chosen arbitrarily but fixed.
VIRTUAL_EPOCH = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
VIRTUAL_TICK = timedelta(milliseconds=50)


def stable_uuid(*parts: object) -> str:
    """A UUIDv5 derived from the given parts; identical inputs -> identical id."""
    return str(uuid.uuid5(_NAMESPACE, "|".join(str(p) for p in parts)))


def run_id_for(scenario_id: str, mode: str, seed: int) -> str:
    return "run-" + stable_uuid(scenario_id, mode, seed)[:12]


def short_hash(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


class Clock:
    """Virtual (deterministic) or wall clock.

    Deterministic mode advances a fixed tick per observed event so that timestamps
    are a pure function of the sequence number.
    """

    def __init__(self, deterministic: bool = True) -> None:
        self.deterministic = deterministic

    def at(self, sequence_number: int) -> datetime:
        if self.deterministic:
            return VIRTUAL_EPOCH + VIRTUAL_TICK * sequence_number
        return datetime.now(timezone.utc)

    @property
    def mode(self) -> str:
        return "virtual" if self.deterministic else "wall"
