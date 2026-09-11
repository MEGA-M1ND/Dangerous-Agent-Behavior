"""Append-only, tamper-evident JSONL sinks.

The agent runtime never receives a reference to a sink. Beyond that structural
separation, each sink maintains a hash chain over the lines it has written, so
that any later edit to an event file is detectable. This supports the claim that
the observer's record is append-only for the duration of a run; it is not a
security control and is not presented as one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterator

from experiment.events import Event

GENESIS = "0" * 64


class AppendOnlyViolation(RuntimeError):
    """Raised when something tries to write to a sealed sink."""


class AppendOnlyJsonlSink:
    """Writes events as JSON lines, one per line, in emission order."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Truncate once at construction so a re-run of the same run_id starts
        # clean; afterwards the handle only ever appends.
        self.path.write_text("", encoding="utf-8")
        self._handle = self.path.open("a", encoding="utf-8")
        self._sealed = False
        self._chain = GENESIS
        self._count = 0

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def count(self) -> int:
        return self._count

    @property
    def chain_digest(self) -> str:
        return self._chain

    def append(self, event: Event) -> None:
        if self._sealed:
            raise AppendOnlyViolation(f"sink already sealed: {self.path}")
        line = event.to_jsonl()
        self._handle.write(line + "\n")
        self._handle.flush()
        self._chain = hashlib.sha256((self._chain + line).encode("utf-8")).hexdigest()
        self._count += 1

    def seal(self) -> str:
        if not self._sealed:
            self._handle.close()
            self._sealed = True
        return self._chain


def read_events(path: Path) -> list[Event]:
    """Load a JSONL event file back into typed events."""
    events: list[Event] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(Event.model_validate_json(line))
    return events


def chain_digest_of(path: Path) -> str:
    """Recompute the hash chain of a file on disk, for tamper checking."""
    chain = GENESIS
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            chain = hashlib.sha256((chain + line).encode("utf-8")).hexdigest()
    return chain


def iter_raw(path: Path) -> Iterator[dict]:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)
