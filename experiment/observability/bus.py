"""The single instrumentation point and its fan-out.

The tool gateway emits one :class:`Observation` per raw fact about the run. The
bus stamps it with a shared sequence number and hands the *same* observation to
both conditions:

* :class:`~experiment.observability.baseline.BaselineLogger` - conventional agent
  application logging.
* :class:`~experiment.observability.observer.ProvenanceObserver` - an independent
  observer that additionally records relationships.

Because both conditions see identical raw facts, any measured difference is
attributable to what each condition *retains and relates*, not to where the
instrumentation was placed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from experiment.events import Event, EventType
from experiment.ids import Clock
from experiment.observability.sinks import AppendOnlyJsonlSink


@dataclass
class Observation:
    """One raw fact about the run, before any condition-specific processing."""

    event_type: EventType
    agent_id: str
    objective_id: str | None = None
    parent_agent_id: str | None = None
    action: str | None = None
    tool_name: str | None = None
    tool_category: str | None = None
    target_resource: str | None = None
    raw_arguments: dict[str, Any] = field(default_factory=dict)
    #: Full result text, used only for in-memory provenance matching.
    raw_payload_text: str | None = None
    #: Text safe to persist as a result preview. Defaults to raw_payload_text.
    preview_text: str | None = None
    result_status: str | None = None
    error: str | None = None
    self_report: str | None = None
    credential_name: str | None = None
    external_resource: str | None = None
    returns_untrusted_content: bool = False
    permissions_before: tuple[str, ...] | None = None
    permissions_after: tuple[str, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def loggable_preview(self) -> str | None:
        return self.preview_text if self.preview_text is not None else self.raw_payload_text


class Condition(Protocol):
    """A way of observing the run."""

    name: str

    def observe(self, observation: Observation, sequence_number: int) -> Event | None: ...


class TelemetryBus:
    """Allocates shared sequence numbers and fans observations out to sinks."""

    def __init__(
        self,
        conditions: list[tuple[Condition, AppendOnlyJsonlSink]],
        clock: Clock,
    ) -> None:
        self._conditions = conditions
        self._clock = clock
        self._sequence = 0

    @property
    def clock(self) -> Clock:
        return self._clock

    def emit(self, observation: Observation) -> int:
        """Record one observation in every condition. Returns its sequence number."""
        sequence_number = self._sequence
        self._sequence += 1
        for condition, sink in self._conditions:
            event = condition.observe(observation, sequence_number)
            if event is not None:
                sink.append(event)
        return sequence_number

    def seal(self) -> dict[str, str]:
        return {condition.name: sink.seal() for condition, sink in self._conditions}
