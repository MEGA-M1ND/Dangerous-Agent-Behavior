"""The independent provenance observer (the experimental condition).

The observer sits at the tool gateway, outside the agent's decision logic. It
never asks the agent why it did anything. It maintains its own model of:

* which content references it has handed back to the agent (the agent-visible
  input state),
* which credential references exist and where they came from,
* what the capability set is at each point in the run,

and it records, for every action, the *observable* relationships between that
action and earlier events.

Terminology discipline: an edge asserts that information from an earlier event is
identifiable in, or was present in the observable input state preceding, a later
event. It never asserts that the earlier event caused the model to decide
anything. ``EvidenceKind`` separates OBSERVED relationships from weaker INFERRED
ones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from experiment.events import (
    Event,
    EventType,
    EvidenceKind,
    FlowEvidence,
    is_observed,
)
from experiment.ids import Clock, short_hash, stable_uuid
from experiment.observability.baseline import DEFAULT_PREVIEW_CAP, truncate_preview
from experiment.observability.bus import Observation
from experiment.redaction import credential_reference, sanitize_arguments, scrub_text
from experiment.textmatch import (
    detect_instruction_spans,
    mentions,
    shared_significant_tokens,
)


@dataclass
class ContentRecord:
    """Content the observer handed back to the agent."""

    content_ref: str
    text: str
    source_event_id: str
    tool_name: str | None
    external_resource: str | None
    untrusted: bool
    instruction_spans: list[str] = field(default_factory=list)


@dataclass
class CredentialRecord:
    credential_ref: str
    name: str
    value: str
    source_event_id: str


class ProvenanceObserver:
    """Records conventional fields *plus* observable relationships."""

    name = "provenance_observer"

    def __init__(
        self,
        run_id: str,
        scenario_id: str,
        clock: Clock,
        preview_cap: int = DEFAULT_PREVIEW_CAP,
    ) -> None:
        self.run_id = run_id
        self.scenario_id = scenario_id
        self.clock = clock
        self.preview_cap = preview_cap
        self._content: dict[str, ContentRecord] = {}
        self._visible_context: list[str] = []
        self._credentials: dict[str, CredentialRecord] = {}
        self._permissions: tuple[str, ...] = ()
        self._last_action_event_id: str | None = None
        self._pending_content_ref: str | None = None

    # -- helpers --------------------------------------------------------------

    def _event_id(self, sequence_number: int) -> str:
        return stable_uuid(self.run_id, sequence_number)

    @staticmethod
    def _argument_text(arguments: dict[str, Any]) -> str:
        try:
            return json.dumps(arguments, sort_keys=True, default=str)
        except TypeError:  # pragma: no cover - arguments are plain data
            return str(arguments)

    def _register_content(
        self, observation: Observation, event_id: str
    ) -> ContentRecord | None:
        text = observation.raw_payload_text
        if not text or observation.credential_name:
            # Credential material is tracked separately and never becomes
            # matchable content, so no secret can reach an evidence string.
            return None
        content_ref = f"obs://{short_hash(text)}"
        record = ContentRecord(
            content_ref=content_ref,
            text=text,
            source_event_id=event_id,
            tool_name=observation.tool_name,
            external_resource=observation.external_resource,
            untrusted=observation.returns_untrusted_content,
            instruction_spans=detect_instruction_spans(text),
        )
        self._content[content_ref] = record
        return record

    # -- flow analysis --------------------------------------------------------

    def _flow_evidence_for_action(self, observation: Observation) -> list[FlowEvidence]:
        """Observable links between earlier content and this action.

        For each content reference currently in the agent-visible input state we
        look for the strongest available evidence, in this order:

        1. a credential value present verbatim in the arguments,
        2. an identifying token shared between the content and the arguments,
        3. the action's target resource named inside the content,
        4. otherwise: mere presence in the observable input state (INFERRED).
        """
        argument_text = self._argument_text(observation.raw_arguments)
        evidence: list[FlowEvidence] = []

        for credential in self._credentials.values():
            if credential.value and credential.value in argument_text:
                evidence.append(
                    FlowEvidence(
                        source_event_id=credential.source_event_id,
                        source_ref=credential.credential_ref,
                        evidence_kind=EvidenceKind.CREDENTIAL_REFERENCE_IDENTITY,
                        observed=True,
                        detail="credential value obtained earlier is present in this call's arguments",
                    )
                )

        for content_ref in self._visible_context:
            record = self._content[content_ref]
            shared = shared_significant_tokens(record.text, argument_text)
            if shared:
                evidence.append(
                    FlowEvidence(
                        source_event_id=record.source_event_id,
                        source_ref=content_ref,
                        evidence_kind=EvidenceKind.VERBATIM_SUBSTRING_MATCH,
                        observed=True,
                        detail=scrub_text("shared identifying tokens: " + ", ".join(sorted(shared))),
                    )
                )
            elif mentions(record.text, observation.target_resource):
                evidence.append(
                    FlowEvidence(
                        source_event_id=record.source_event_id,
                        source_ref=content_ref,
                        evidence_kind=EvidenceKind.RESOURCE_IDENTIFIER_MENTIONED_IN_SOURCE,
                        observed=True,
                        detail=f"target resource {observation.target_resource!r} is named in this content",
                    )
                )
            else:
                evidence.append(
                    FlowEvidence(
                        source_event_id=record.source_event_id,
                        source_ref=content_ref,
                        evidence_kind=EvidenceKind.PRESENT_IN_OBSERVABLE_CONTEXT,
                        observed=False,
                        detail="content was in the agent-visible input state before this action",
                    )
                )

        if self._last_action_event_id:
            evidence.append(
                FlowEvidence(
                    source_event_id=self._last_action_event_id,
                    source_ref=None,
                    evidence_kind=EvidenceKind.TEMPORAL_ADJACENCY,
                    observed=False,
                    detail="immediately preceding action in this run",
                )
            )
        return evidence

    def _risk_tags(self, observation: Observation) -> list[str]:
        """Descriptive labels. Not used by the detection heuristics or scoring."""
        tags: list[str] = []
        if observation.returns_untrusted_content:
            tags.append("untrusted_content_source")
        if observation.credential_name:
            tags.append("credential_material")
        if observation.tool_category == "cloud_admin":
            tags.append("privileged_capability")
        return tags

    # -- observation ----------------------------------------------------------

    def observe(self, observation: Observation, sequence_number: int) -> Event | None:
        event_id = self._event_id(sequence_number)
        source_ids: list[str] = []
        input_event_ids: list[str] = []
        flow_evidence: list[FlowEvidence] = []
        credential_ref: str | None = None
        output_reference: str | None = None
        permission_before = list(self._permissions)
        permission_after = list(self._permissions)

        if observation.event_type is EventType.TOOL_INVOCATION:
            flow_evidence = self._flow_evidence_for_action(observation)
            source_ids = [e.source_ref for e in flow_evidence if e.source_ref]
            input_event_ids = sorted({e.source_event_id for e in flow_evidence})
            for candidate in self._credentials.values():
                if candidate.value in self._argument_text(observation.raw_arguments):
                    credential_ref = candidate.credential_ref
            self._last_action_event_id = event_id

        elif observation.event_type is EventType.TOOL_RESULT:
            record = self._register_content(observation, event_id)
            if record is not None:
                output_reference = record.content_ref
                self._pending_content_ref = record.content_ref
            if observation.credential_name and observation.raw_payload_text:
                credential = CredentialRecord(
                    credential_ref=credential_reference(
                        observation.credential_name, observation.raw_payload_text
                    ),
                    name=observation.credential_name,
                    value=observation.raw_payload_text,
                    source_event_id=event_id,
                )
                self._credentials[credential.credential_ref] = credential
                credential_ref = credential.credential_ref

        elif observation.event_type is EventType.OBSERVATION_INGESTED:
            content_ref = self._pending_content_ref
            self._pending_content_ref = None
            if content_ref is None:
                return None
            record = self._content[content_ref]
            if content_ref not in self._visible_context:
                self._visible_context.append(content_ref)
            source_ids = [content_ref]
            input_event_ids = [record.source_event_id]
            flow_evidence = [
                FlowEvidence(
                    source_event_id=record.source_event_id,
                    source_ref=content_ref,
                    evidence_kind=EvidenceKind.DECLARED_TOOL_LINEAGE,
                    observed=True,
                    detail="content returned by the gateway entered the agent-visible input state",
                )
            ]

        elif observation.event_type is EventType.PERMISSION_CHANGE:
            permission_after = sorted(set(observation.permissions_after or ()))
            self._permissions = tuple(permission_after)

        if observation.permissions_before is not None:
            permission_before = sorted(set(observation.permissions_before))
        if observation.permissions_after is not None:
            permission_after = sorted(set(observation.permissions_after))
            self._permissions = tuple(permission_after)

        metadata = dict(observation.metadata)
        if observation.event_type is EventType.OBSERVATION_INGESTED and source_ids:
            record = self._content[source_ids[0]]
            metadata["instruction_spans"] = record.instruction_spans
            metadata["untrusted_source"] = record.untrusted
            metadata["content_length"] = len(record.text)

        return Event(
            event_id=event_id,
            run_id=self.run_id,
            timestamp=self.clock.at(sequence_number),
            sequence_number=sequence_number,
            scenario_id=self.scenario_id,
            agent_id=observation.agent_id,
            parent_agent_id=observation.parent_agent_id,
            event_type=observation.event_type,
            objective_id=observation.objective_id,
            action=observation.action,
            tool_name=observation.tool_name,
            tool_category=observation.tool_category,
            target_resource=observation.target_resource,
            sanitized_arguments=sanitize_arguments(observation.raw_arguments),
            result_status=observation.result_status,  # type: ignore[arg-type]
            result_preview=truncate_preview(observation.loggable_preview(), self.preview_cap),
            error=observation.error,
            untrusted_self_report=observation.self_report,
            metadata=metadata,
            source_ids=source_ids,
            input_event_ids=input_event_ids,
            flow_evidence=flow_evidence,
            permission_before=permission_before,
            permission_after=permission_after,
            credential_reference=credential_ref,
            external_resource=observation.external_resource,
            output_reference=output_reference,
            risk_tags=self._risk_tags(observation),
            observer_source="provenance_observer",
        )


__all__ = ["ProvenanceObserver", "is_observed"]
