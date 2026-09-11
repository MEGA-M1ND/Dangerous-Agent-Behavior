"""Provenance graph model.

Node and edge identifiers follow a fixed canonical scheme so that graphs built
from different telemetry streams - and the evaluation's ground-truth manifests -
can be compared without any per-condition mapping logic.

Every edge carries its evidence and is explicitly marked OBSERVED or INFERRED.

Terminology: an edge never asserts that an earlier event caused the model to
decide anything. ``data_flowed_to`` means "information identifiable in, or
present in the observable input state preceding, the later event".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from experiment.events import EvidenceKind, is_observed

#: Relations used by this experiment, drawn from the experiment's fixed
#: vocabulary.
RELATIONS: tuple[str, ...] = (
    "retrieved",
    "observed",
    "invoked",
    "produced",
    "accessed",
    "enabled",
    "received_from",
    "spawned",
    "modified",
    "followed_by",
    "data_flowed_to",
    "permission_changed",
    "communicated_with",
)

#: Strength ordering used when the same edge is supported by several pieces of
#: evidence: the strongest one is kept.
_EVIDENCE_RANK: dict[EvidenceKind, int] = {
    EvidenceKind.CREDENTIAL_REFERENCE_IDENTITY: 5,
    EvidenceKind.VERBATIM_SUBSTRING_MATCH: 4,
    EvidenceKind.DECLARED_TOOL_LINEAGE: 3,
    EvidenceKind.RESOURCE_IDENTIFIER_MENTIONED_IN_SOURCE: 2,
    EvidenceKind.PRESENT_IN_OBSERVABLE_CONTEXT: 1,
    EvidenceKind.TEMPORAL_ADJACENCY: 0,
}


# --------------------------------------------------------------------------- #
# Canonical node identifiers
# --------------------------------------------------------------------------- #

def objective_node(objective_id: str) -> str:
    return f"objective:{objective_id}"


def agent_node(agent_id: str) -> str:
    return f"agent:{agent_id}"


def message_node(sender: str) -> str:
    return f"message:{sender}"


def document_node(document_id: str) -> str:
    return f"document:{document_id}"


def observation_node(source_key: str) -> str:
    return f"observation:{source_key}"


def tool_node(tool_name: str) -> str:
    return f"tool:{tool_name}"


def action_node(tool_name: str, target: str | None) -> str:
    return f"action:{tool_name}:{target or '-'}"


def credential_node(name: str) -> str:
    return f"credential:{name}"


def permission_node(permission: str) -> str:
    return f"permission:{permission}"


def resource_node(resource: str) -> str:
    return f"resource:{resource}"


def memory_node(key: str) -> str:
    return f"memory:{key}"


def credential_name_from_reference(reference: str) -> str:
    """``cred://demo_cloud_token#abc123`` -> ``demo_cloud_token``."""
    return reference.removeprefix("cred://").split("#", 1)[0]


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "label": self.label, "attrs": self.attrs}


@dataclass
class Edge:
    source: str
    relation: str
    target: str
    evidence_kind: EvidenceKind
    evidence_event_ids: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def observed(self) -> bool:
        return is_observed(self.evidence_kind)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source, self.relation, self.target)

    def statement(self) -> str:
        """A defensible natural-language rendering of this edge."""
        if self.relation == "data_flowed_to":
            if self.observed:
                return (
                    f"Information from {self.source} is directly identifiable in "
                    f"{self.target} ({self.evidence_kind.value})."
                )
            return (
                f"Information from {self.source} was present in the observable "
                f"input state immediately preceding {self.target} "
                f"({self.evidence_kind.value})."
            )
        qualifier = "observed" if self.observed else "inferred"
        return f"{self.source} --{self.relation}--> {self.target} ({qualifier}, {self.evidence_kind.value})."

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
            "evidence_kind": self.evidence_kind.value,
            "observed": self.observed,
            "evidence_event_ids": self.evidence_event_ids,
            "detail": self.detail,
            "statement": self.statement(),
        }


class ProvenanceGraph:
    """A small directed multigraph with evidence-bearing edges."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[tuple[str, str, str], Edge] = {}

    # -- construction ---------------------------------------------------------

    def add_node(self, node_id: str, kind: str, label: str, **attrs: Any) -> str:
        existing = self._nodes.get(node_id)
        if existing is None:
            self._nodes[node_id] = Node(node_id, kind, label, dict(attrs))
        elif attrs:
            merged = {**existing.attrs, **attrs}
            self._nodes[node_id] = Node(node_id, kind, existing.label, merged)
        return node_id

    def add_edge(
        self,
        source: str,
        relation: str,
        target: str,
        evidence_kind: EvidenceKind,
        evidence_event_ids: Iterable[str] = (),
        detail: str = "",
    ) -> None:
        if relation not in RELATIONS:
            raise ValueError(f"relation outside the experiment vocabulary: {relation}")
        candidate = Edge(source, relation, target, evidence_kind, list(evidence_event_ids), detail)
        current = self._edges.get(candidate.key)
        if current is None:
            self._edges[candidate.key] = candidate
            return
        if _EVIDENCE_RANK[evidence_kind] > _EVIDENCE_RANK[current.evidence_kind]:
            candidate.evidence_event_ids = sorted(
                set(current.evidence_event_ids) | set(candidate.evidence_event_ids)
            )
            self._edges[candidate.key] = candidate
        else:
            current.evidence_event_ids = sorted(
                set(current.evidence_event_ids) | set(candidate.evidence_event_ids)
            )

    # -- access ---------------------------------------------------------------

    @property
    def nodes(self) -> list[Node]:
        return [self._nodes[k] for k in sorted(self._nodes)]

    @property
    def edges(self) -> list[Edge]:
        return [self._edges[k] for k in sorted(self._edges)]

    def node_ids(self) -> set[str]:
        return set(self._nodes)

    def edge_keys(self) -> set[tuple[str, str, str]]:
        return set(self._edges)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def incoming(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id]

    def outgoing(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "counts": {
                "nodes": len(self._nodes),
                "edges": len(self._edges),
                "observed_edges": sum(1 for e in self._edges.values() if e.observed),
                "inferred_edges": sum(1 for e in self._edges.values() if not e.observed),
            },
        }

    # -- rendering ------------------------------------------------------------

    def to_mermaid(self) -> str:
        """Mermaid flowchart. Inferred edges are dashed."""
        lines = ["flowchart TD"]
        for node in self.nodes:
            lines.append(f'    {_mermaid_id(node.id)}["{_escape(node.label)}"]')
        for edge in self.edges:
            arrow = "-->" if edge.observed else "-.->"
            lines.append(
                f"    {_mermaid_id(edge.source)} {arrow}|{_escape(edge.relation)}| "
                f"{_mermaid_id(edge.target)}"
            )
        return "\n".join(lines)


def _mermaid_id(node_id: str) -> str:
    return "n_" + "".join(c if c.isalnum() else "_" for c in node_id)


def _escape(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ")
