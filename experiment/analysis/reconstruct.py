"""Reconstruction of what happened, from telemetry alone.

There is exactly **one** reconstruction algorithm. It is run twice: once over the
baseline event log and once over the provenance event log. Nothing in it branches
on which condition produced the events - it simply uses whatever fields are
present. This removes "the experimenters wrote a better analyser for their own
condition" as an explanation for any measured difference.

The reconstruction never reads ground truth, and never uses an agent's own
explanation as evidence: self reports are collected separately and marked
untrusted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from experiment.analysis.graph import (
    EvidenceKind,
    ProvenanceGraph,
    action_node,
    agent_node,
    credential_name_from_reference,
    credential_node,
    document_node,
    memory_node,
    message_node,
    objective_node,
    observation_node,
    permission_node,
    resource_node,
    tool_node,
)
from experiment.events import Event, EventType
from experiment.mockenv.registry import (
    TOOL_PERMISSION_REQUIREMENTS,
    TOOL_REGISTRY,
)
from experiment.redaction import BASELINE_REDACTION
from experiment.textmatch import detect_instruction_spans, mentions, shared_significant_tokens


@dataclass
class ObservedContent:
    node_id: str
    text: str
    untrusted: bool
    source_key: str
    event_id: str
    sequence_number: int
    instruction_spans: list[str] = field(default_factory=list)


@dataclass
class Reconstruction:
    condition: str
    run_id: str
    scenario_id: str
    graph: ProvenanceGraph
    answers: dict[str, Any]
    timeline: list[dict[str, Any]]
    untrusted_self_reports: list[dict[str, Any]]
    event_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "event_count": self.event_count,
            "answers": self.answers,
            "timeline": self.timeline,
            "untrusted_self_reports": self.untrusted_self_reports,
            "graph": self.graph.to_dict(),
            "disclaimer": (
                "Edges describe observable information flow and system state. They "
                "do not describe the model's reasoning, and no causal claim about "
                "the model's decisions is made or implied."
            ),
        }


def _privilege_of(tool_name: str | None) -> str:
    spec = TOOL_REGISTRY.get(tool_name or "")
    return spec.privilege if spec else "unknown"


def _is_admin_tool(tool_name: str | None) -> bool:
    return _privilege_of(tool_name) == "admin"


def _returns_untrusted(tool_name: str | None) -> bool:
    spec = TOOL_REGISTRY.get(tool_name or "")
    return bool(spec and spec.returns_untrusted_content)


class Reconstructor:
    """Builds a provenance graph and a set of answers from one event stream."""

    def __init__(self, events: list[Event]) -> None:
        self.events = sorted(events, key=lambda e: e.sequence_number)
        self.graph = ProvenanceGraph()
        self._observations: list[ObservedContent] = []
        self._content_ref_to_node: dict[str, str] = {}
        self._credentials: list[tuple[str, str, str]] = []  # (name, node_id, event_id)
        self._last_action_node: str | None = None
        self._last_action_by_tool: dict[str, str] = {}
        self._action_sequence: dict[str, int] = {}
        self._objective_id: str | None = None
        self._agent_id: str | None = None
        self._self_reports: list[dict[str, Any]] = []
        self._timeline: list[dict[str, Any]] = []
        self._objective_text: str | None = None
        self._permissions_seen: list[list[str]] = []

    # -- entry point ----------------------------------------------------------

    def run(self) -> Reconstruction:
        for event in self.events:
            self._dispatch(event)
            self._record_timeline(event)
        first = self.events[0] if self.events else None
        return Reconstruction(
            condition=first.observer_source if first else "unknown",
            run_id=first.run_id if first else "",
            scenario_id=first.scenario_id if first else "",
            graph=self.graph,
            answers=self._answers(),
            timeline=self._timeline,
            untrusted_self_reports=self._self_reports,
            event_count=len(self.events),
        )

    # -- dispatch -------------------------------------------------------------

    def _dispatch(self, event: Event) -> None:
        if event.untrusted_self_report:
            self._self_reports.append(
                {
                    "sequence_number": event.sequence_number,
                    "event_id": event.event_id,
                    "tool_name": event.tool_name,
                    "text": event.untrusted_self_report,
                    "status": "untrusted_self_report - not used as evidence",
                }
            )
        if event.agent_id and self._agent_id is None:
            self._agent_id = event.agent_id
            self.graph.add_node(agent_node(event.agent_id), "Agent", f"agent {event.agent_id}")
        if event.permission_after is not None:
            self._permissions_seen.append(list(event.permission_after))

        handler = {
            EventType.MESSAGE_RECEIVED: self._on_message,
            EventType.OBJECTIVE_DECLARED: self._on_objective,
            EventType.TOOL_CATALOG_EXPOSED: self._on_catalog,
            EventType.TOOL_INVOCATION: self._on_invocation,
            EventType.TOOL_RESULT: self._on_result,
            EventType.OBSERVATION_INGESTED: self._on_ingested,
            EventType.PERMISSION_CHANGE: self._on_permission_change,
            EventType.ENVIRONMENT_CHANGE: self._on_environment_change,
        }.get(event.event_type)
        if handler:
            handler(event)

    def _record_timeline(self, event: Event) -> None:
        self._timeline.append(
            {
                "sequence_number": event.sequence_number,
                "event_type": event.event_type.value,
                "tool_name": event.tool_name,
                "target_resource": event.target_resource,
                "result_status": event.result_status,
                "error": event.error,
            }
        )

    # -- handlers -------------------------------------------------------------

    def _on_message(self, event: Event) -> None:
        sender = str(event.metadata.get("sender", event.target_resource or "unknown"))
        node = self.graph.add_node(
            message_node(sender),
            "Message",
            f"message from {sender}",
            trusted=bool(event.metadata.get("trusted", False)),
            preview=event.result_preview,
        )
        if self._agent_id:
            self.graph.add_edge(
                agent_node(self._agent_id),
                "received_from",
                node,
                EvidenceKind.DECLARED_TOOL_LINEAGE,
                [event.event_id],
                "message delivered to the agent",
            )

    def _on_objective(self, event: Event) -> None:
        self._objective_id = event.objective_id
        self._objective_text = str(event.metadata.get("objective", event.result_preview or ""))
        node = self.graph.add_node(
            objective_node(event.objective_id or "unknown"),
            "Objective",
            self._objective_text[:120],
            required_capabilities=event.metadata.get("required_capabilities", []),
        )
        if self.graph.has_node(message_node("user")):
            self.graph.add_edge(
                message_node("user"),
                "produced",
                node,
                EvidenceKind.DECLARED_TOOL_LINEAGE,
                [event.event_id],
                "objective declared from the received user message",
            )

    def _on_catalog(self, event: Event) -> None:
        for tool in event.metadata.get("tools", []):
            self.graph.add_node(
                tool_node(tool["name"]),
                "Tool",
                tool["name"],
                category=tool.get("category"),
                privilege=tool.get("privilege"),
                available=True,
            )

    def _on_invocation(self, event: Event) -> None:
        tool = event.tool_name or "unknown"
        node = action_node(tool, event.target_resource)
        self.graph.add_node(
            node,
            "Action",
            f"{tool}({event.target_resource or ''})",
            sequence_number=event.sequence_number,
            privilege=_privilege_of(tool),
            arguments=event.sanitized_arguments,
        )
        self._action_sequence.setdefault(node, event.sequence_number)

        if self._agent_id:
            self.graph.add_edge(
                agent_node(self._agent_id), "invoked", node,
                EvidenceKind.DECLARED_TOOL_LINEAGE, [event.event_id], "tool invocation event",
            )
        if event.objective_id:
            self.graph.add_edge(
                objective_node(event.objective_id), "enabled", node,
                EvidenceKind.DECLARED_TOOL_LINEAGE, [event.event_id],
                "action carried out under this objective",
            )
        self.graph.add_node(tool_node(tool), "Tool", tool, privilege=_privilege_of(tool))
        self.graph.add_edge(
            node, "accessed", tool_node(tool),
            EvidenceKind.DECLARED_TOOL_LINEAGE, [event.event_id], "tool capability exercised",
        )
        required = TOOL_PERMISSION_REQUIREMENTS.get(tool)
        if required:
            self.graph.add_node(permission_node(required), "Permission", required)
            self.graph.add_edge(
                permission_node(required), "enabled", node,
                EvidenceKind.DECLARED_TOOL_LINEAGE, [event.event_id],
                "tool catalog states this permission is required",
            )
        if self._last_action_node and self._last_action_node != node:
            self.graph.add_edge(
                self._last_action_node, "followed_by", node,
                EvidenceKind.TEMPORAL_ADJACENCY, [event.event_id],
                "immediately preceding action in this run",
            )

        self._add_flow_edges(event, node)
        self._last_action_node = node
        self._last_action_by_tool[tool] = node

    def _add_flow_edges(self, event: Event, node: str) -> None:
        # (a) Relationships declared by the telemetry, when the stream carries them.
        for evidence in event.flow_evidence:
            reference = evidence.source_ref
            if not reference:
                continue
            if reference.startswith("obs://"):
                source = self._content_ref_to_node.get(reference)
            elif reference.startswith("cred://"):
                source = credential_node(credential_name_from_reference(reference))
            else:
                source = None
            if source and self.graph.has_node(source):
                self.graph.add_edge(
                    source, "data_flowed_to", node, evidence.evidence_kind,
                    [event.event_id, evidence.source_event_id], evidence.detail,
                )

        # (b) Opportunistic matching over whatever text this stream retained.
        argument_text = json.dumps(event.sanitized_arguments, sort_keys=True, default=str)
        for content in self._observations:
            shared = shared_significant_tokens(content.text, argument_text)
            if shared:
                self.graph.add_edge(
                    content.node_id, "data_flowed_to", node,
                    EvidenceKind.VERBATIM_SUBSTRING_MATCH, [event.event_id, content.event_id],
                    "shared identifying tokens: " + ", ".join(sorted(shared)),
                )
            elif mentions(content.text, event.target_resource):
                self.graph.add_edge(
                    content.node_id, "data_flowed_to", node,
                    EvidenceKind.RESOURCE_IDENTIFIER_MENTIONED_IN_SOURCE,
                    [event.event_id, content.event_id],
                    f"target resource {event.target_resource!r} is named in this content",
                )

        # (c) A redacted credential-shaped argument following a credential fetch.
        redacted = [k for k, v in event.sanitized_arguments.items() if v == BASELINE_REDACTION]
        if redacted and self._credentials:
            name, credential_node_id, credential_event = self._credentials[-1]
            self.graph.add_edge(
                credential_node_id, "data_flowed_to", node,
                EvidenceKind.TEMPORAL_ADJACENCY, [event.event_id, credential_event],
                f"redacted argument(s) {sorted(redacted)} follow the retrieval of {name}",
            )

    def _on_result(self, event: Event) -> None:
        tool = event.tool_name or "unknown"
        action = self._last_action_by_tool.get(tool) or self._last_action_node
        source_key = event.target_resource or tool

        if tool == "secret_store.get":
            name = (
                credential_name_from_reference(event.credential_reference)
                if event.credential_reference
                else str(event.target_resource or "unknown")
            )
            node = self.graph.add_node(
                credential_node(name), "CredentialReference", f"credential {name}",
                reference=event.credential_reference,
            )
            if action and event.result_status == "ok":
                self.graph.add_edge(
                    action, "accessed", node, EvidenceKind.DECLARED_TOOL_LINEAGE,
                    [event.event_id], "credential returned by the secret store",
                )
                self._credentials.append((name, node, event.event_id))
            return

        if event.result_status != "ok":
            return

        observation = observation_node(source_key)
        spans = detect_instruction_spans(event.result_preview or "")
        self.graph.add_node(
            observation, "Observation", f"content from {source_key}",
            untrusted=_returns_untrusted(tool),
            instruction_spans=spans,
            source_tool=tool,
            external_resource=event.external_resource,
        )
        if action:
            self.graph.add_edge(
                action, "produced", observation, EvidenceKind.DECLARED_TOOL_LINEAGE,
                [event.event_id], "tool result content",
            )
        if tool == "browser.open_document" and event.target_resource:
            document = self.graph.add_node(
                document_node(event.target_resource), "Document", event.target_resource
            )
            if action:
                self.graph.add_edge(
                    action, "retrieved", document, EvidenceKind.DECLARED_TOOL_LINEAGE,
                    [event.event_id], "document retrieval",
                )
            self.graph.add_edge(
                document, "observed", observation, EvidenceKind.DECLARED_TOOL_LINEAGE,
                [event.event_id], "content of the retrieved document",
            )
        if tool.startswith("memory.") and event.target_resource:
            item = self.graph.add_node(
                memory_node(event.target_resource), "MemoryItem", event.target_resource
            )
            if action:
                self.graph.add_edge(
                    action, "accessed", item, EvidenceKind.DECLARED_TOOL_LINEAGE,
                    [event.event_id], "memory operation",
                )

        self._observations.append(
            ObservedContent(
                node_id=observation,
                text=event.result_preview or "",
                untrusted=_returns_untrusted(tool),
                source_key=source_key,
                event_id=event.event_id,
                sequence_number=event.sequence_number,
                instruction_spans=spans,
            )
        )

    def _on_ingested(self, event: Event) -> None:
        """Provenance-only: content entered the agent-visible input state."""
        source_key = event.target_resource or event.tool_name or "unknown"
        node = observation_node(source_key)
        for reference in event.source_ids:
            self._content_ref_to_node[reference] = node
        spans = list(event.metadata.get("instruction_spans", []))
        previous = next(
            (c.instruction_spans for c in self._observations if c.node_id == node), []
        )
        merged = sorted(set(previous) | set(spans))
        self.graph.add_node(
            node, "Observation", f"content from {source_key}",
            ingested=True,
            content_length=event.metadata.get("content_length"),
            instruction_spans_full_content=spans,
            instruction_spans=merged,
        )
        for content in self._observations:
            if content.node_id == node:
                # The observer saw the whole content, not just the logged preview.
                content.instruction_spans = merged

    def _on_permission_change(self, event: Event) -> None:
        """Provenance-only: the capability set changed during the task."""
        before = set(event.permission_before or [])
        after = set(event.permission_after or [])
        granted = sorted(after - before)
        source = (
            credential_node(str(event.target_resource))
            if event.target_resource and self.graph.has_node(credential_node(str(event.target_resource)))
            else None
        )
        for permission in granted:
            node = self.graph.add_node(permission_node(permission), "Permission", permission)
            if source:
                self.graph.add_edge(
                    source, "permission_changed", node, EvidenceKind.DECLARED_TOOL_LINEAGE,
                    [event.event_id], "capability set grew after this credential was obtained",
                )

    def _on_environment_change(self, event: Event) -> None:
        if not event.target_resource:
            return
        node = self.graph.add_node(
            resource_node(event.target_resource), "Resource", event.target_resource,
            change=event.action,
        )
        action = self._last_action_by_tool.get(event.tool_name or "") or self._last_action_node
        if action:
            self.graph.add_edge(
                action, "modified", node, EvidenceKind.DECLARED_TOOL_LINEAGE,
                [event.event_id], f"environment change: {event.action}",
            )

    # -- answers --------------------------------------------------------------

    def _dangerous_actions(self) -> list[dict[str, Any]]:
        """Successful invocations of tools the shared catalog marks administrative.

        This definition comes from the tool catalog, not from ground truth.
        """
        found: list[dict[str, Any]] = []
        pending: dict[str, Event] = {}
        for event in self.events:
            if event.event_type is EventType.TOOL_INVOCATION and _is_admin_tool(event.tool_name):
                pending[event.tool_name or ""] = event
            elif (
                event.event_type is EventType.TOOL_RESULT
                and _is_admin_tool(event.tool_name)
                and event.result_status == "ok"
            ):
                invocation = pending.get(event.tool_name or "")
                if invocation is None:
                    continue
                found.append(
                    {
                        "tool_name": event.tool_name,
                        "action_node": action_node(event.tool_name or "", invocation.target_resource),
                        "invocation_sequence": invocation.sequence_number,
                        "result_sequence": event.sequence_number,
                        "target_resource": event.target_resource,
                    }
                )
        return found

    def _preceding_tool_invocation(self, sequence_number: int) -> dict[str, Any] | None:
        previous = [
            e
            for e in self.events
            if e.event_type is EventType.TOOL_INVOCATION and e.sequence_number < sequence_number
        ]
        if not previous:
            return None
        event = previous[-1]
        return {
            "sequence_number": event.sequence_number,
            "tool_name": event.tool_name,
            "target_resource": event.target_resource,
            "action_node": action_node(event.tool_name or "", event.target_resource),
        }

    def _preceding_event(self, sequence_number: int) -> dict[str, Any] | None:
        previous = [e for e in self.events if e.sequence_number < sequence_number]
        if not previous:
            return None
        event = previous[-1]
        return {
            "sequence_number": event.sequence_number,
            "event_type": event.event_type.value,
            "tool_name": event.tool_name,
            "target_resource": event.target_resource,
        }

    def _untrusted_to_privileged_paths(self) -> list[dict[str, Any]]:
        paths: list[dict[str, Any]] = []
        for dangerous in self._dangerous_actions():
            target = dangerous["action_node"]
            for edge in self.graph.incoming(target):
                if edge.relation != "data_flowed_to":
                    continue
                node = next((n for n in self.graph.nodes if n.id == edge.source), None)
                if node is None or node.kind != "Observation":
                    continue
                if not node.attrs.get("untrusted"):
                    continue
                paths.append(
                    {
                        "source": edge.source,
                        "target": target,
                        "evidence_kind": edge.evidence_kind.value,
                        "observed": edge.observed,
                        "statement": edge.statement(),
                        "instruction_spans": node.attrs.get("instruction_spans", []),
                    }
                )
        return paths

    def _answers(self) -> dict[str, Any]:
        dangerous = self._dangerous_actions()
        information = [
            {
                "source": content.source_key,
                "node": content.node_id,
                "untrusted": content.untrusted,
                "sequence_number": content.sequence_number,
                "instruction_spans": content.instruction_spans,
            }
            for content in self._observations
        ]
        tools_called = [
            {
                "sequence_number": e.sequence_number,
                "tool_name": e.tool_name,
                "target_resource": e.target_resource,
                "privilege": _privilege_of(e.tool_name),
            }
            for e in self.events
            if e.event_type is EventType.TOOL_INVOCATION
        ]
        permissions_observed = sorted({p for perms in self._permissions_seen for p in perms})
        return {
            "original_objective": {
                "objective_id": self._objective_id,
                "text": self._objective_text,
            },
            "information_that_entered_the_environment": information,
            "tools_called": tools_called,
            "credentials_involved": [
                {"name": name, "node": node} for name, node, _ in self._credentials
            ],
            "permissions_observed": permissions_observed,
            "permission_transitions_observed": [
                {
                    "sequence_number": e.sequence_number,
                    "before": e.permission_before,
                    "after": e.permission_after,
                }
                for e in self.events
                if e.event_type is EventType.PERMISSION_CHANGE
            ],
            "high_privilege_capabilities_exercised": sorted(
                {t["tool_name"] for t in tools_called if _privilege_of(t["tool_name"]) in ("admin", "credential_read")}
            ),
            "dangerous_actions": dangerous,
            "event_immediately_preceding_dangerous_action": [
                {
                    "dangerous_action": d["action_node"],
                    "preceding_event": self._preceding_event(d["invocation_sequence"]),
                    "preceding_tool_invocation": self._preceding_tool_invocation(d["invocation_sequence"]),
                }
                for d in dangerous
            ],
            "observable_data_flow_into_later_actions": [
                edge.to_dict() for edge in self.graph.edges if edge.relation == "data_flowed_to"
            ],
            "untrusted_content_reaching_privileged_action": self._untrusted_to_privileged_paths(),
            "environment_changes": [
                {
                    "sequence_number": e.sequence_number,
                    "change": e.action,
                    "resource": e.target_resource,
                    "tool_name": e.tool_name,
                }
                for e in self.events
                if e.event_type is EventType.ENVIRONMENT_CHANGE
            ],
        }


def reconstruct(events: list[Event]) -> Reconstruction:
    """Run the single reconstruction algorithm over one event stream."""
    return Reconstructor(events).run()
