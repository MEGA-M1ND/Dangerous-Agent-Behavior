"""Event schema shared by both observation conditions.

Both the conventional baseline logger and the provenance observer emit instances
of :class:`Event`. The *baseline* condition is produced by projecting an event
onto a strictly smaller set of fields (see
:func:`experiment.observability.baseline.project_to_baseline`), so the only
difference between the two telemetry streams is the presence of relational /
provenance fields - not logging effort, verbosity or instrumentation points.

Nothing here ever stores a secret value. Credentials are represented only by
opaque references (see :mod:`experiment.redaction`).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """Observable event kinds.

    None of these require access to the model's private reasoning. ``SELF_REPORT``
    captures an agent-emitted justification, which is stored *only* as an
    untrusted self report and never used as ground truth or as evidence.
    """

    RUN_STARTED = "run_started"
    OBJECTIVE_DECLARED = "objective_declared"
    TOOL_CATALOG_EXPOSED = "tool_catalog_exposed"
    AGENT_STEP = "agent_step"
    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    TOOL_INVOCATION = "tool_invocation"
    TOOL_RESULT = "tool_result"
    OBSERVATION_INGESTED = "observation_ingested"
    CREDENTIAL_ACCESS = "credential_access"
    PERMISSION_CHANGE = "permission_change"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    MESSAGE_RECEIVED = "message_received"
    ENVIRONMENT_CHANGE = "environment_change"
    SELF_REPORT = "self_report"
    RUN_COMPLETED = "run_completed"


class EvidenceKind(str, Enum):
    """How a claimed relationship between two events was established.

    The first four are OBSERVED: something concrete in the telemetry links the
    two events. The last two are INFERRED: the link is a weaker statement about
    what was present in the observable input state, and must never be described
    as causation.
    """

    VERBATIM_SUBSTRING_MATCH = "verbatim_substring_match"
    CREDENTIAL_REFERENCE_IDENTITY = "credential_reference_identity"
    RESOURCE_IDENTIFIER_MENTIONED_IN_SOURCE = "resource_identifier_mentioned_in_source"
    DECLARED_TOOL_LINEAGE = "declared_tool_lineage"
    PRESENT_IN_OBSERVABLE_CONTEXT = "present_in_observable_context"
    TEMPORAL_ADJACENCY = "temporal_adjacency"


OBSERVED_EVIDENCE: frozenset[EvidenceKind] = frozenset(
    {
        EvidenceKind.VERBATIM_SUBSTRING_MATCH,
        EvidenceKind.CREDENTIAL_REFERENCE_IDENTITY,
        EvidenceKind.RESOURCE_IDENTIFIER_MENTIONED_IN_SOURCE,
        EvidenceKind.DECLARED_TOOL_LINEAGE,
    }
)


def is_observed(kind: EvidenceKind) -> bool:
    """True for direct observations, False for weaker inferred relationships."""
    return kind in OBSERVED_EVIDENCE


class FlowEvidence(BaseModel):
    """Evidence that information from an earlier event was present in a later one.

    Deliberately phrased as a statement about observable state, never about the
    model's reasoning.
    """

    model_config = ConfigDict(frozen=True)

    source_event_id: str
    source_ref: str | None = None
    evidence_kind: EvidenceKind
    observed: bool
    detail: str = ""

    def statement(self) -> str:
        if self.observed:
            return f"Information from {self.source_ref or self.source_event_id} is directly identifiable in this event ({self.evidence_kind.value})."
        return f"Information from {self.source_ref or self.source_event_id} was present in the observable input state preceding this event ({self.evidence_kind.value})."


class Event(BaseModel):
    """A single observed event.

    Field groups:

    * identity/ordering - always present in both conditions
    * conventional - what a well-instrumented agent application would record
    * provenance - relational fields recorded only by the independent observer
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- identity / ordering -------------------------------------------------
    event_id: str
    run_id: str
    timestamp: datetime
    sequence_number: int
    scenario_id: str
    agent_id: str
    parent_agent_id: str | None = None
    event_type: EventType

    # --- conventional --------------------------------------------------------
    objective_id: str | None = None
    action: str | None = None
    tool_name: str | None = None
    tool_category: str | None = None
    target_resource: str | None = None
    sanitized_arguments: dict[str, Any] = Field(default_factory=dict)
    result_status: Literal["ok", "error", "denied", "n/a"] | None = None
    result_preview: str | None = None
    error: str | None = None
    untrusted_self_report: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # --- provenance (dropped by the baseline projection) ---------------------
    source_ids: list[str] = Field(default_factory=list)
    input_event_ids: list[str] = Field(default_factory=list)
    flow_evidence: list[FlowEvidence] = Field(default_factory=list)
    permission_before: list[str] | None = None
    permission_after: list[str] | None = None
    credential_reference: str | None = None
    external_resource: str | None = None
    output_reference: str | None = None
    risk_tags: list[str] = Field(default_factory=list)

    observer_source: Literal["baseline_logger", "provenance_observer"] = "provenance_observer"

    def to_jsonl(self) -> str:
        return self.model_dump_json(exclude_none=False)


#: Fields that exist only in the provenance condition.
PROVENANCE_ONLY_FIELDS: tuple[str, ...] = (
    "source_ids",
    "input_event_ids",
    "flow_evidence",
    "permission_before",
    "permission_after",
    "credential_reference",
    "external_resource",
    "output_reference",
    "risk_tags",
)

#: Event types a conventional agent log would not emit at all.
PROVENANCE_ONLY_EVENT_TYPES: frozenset[EventType] = frozenset(
    {EventType.OBSERVATION_INGESTED, EventType.PERMISSION_CHANGE}
)
