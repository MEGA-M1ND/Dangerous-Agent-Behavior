"""The tool gateway: the single choke point between agent and environment.

Every tool call the agent makes passes through here. The gateway executes the
call against the mock environment and emits raw observations to the telemetry
bus, which fans them out to both observation conditions.

The agent receives only :meth:`ToolGateway.call`. It holds no reference to the
bus, to either condition, or to any sink, so it cannot read or modify the
observer's record. This is the architectural separation the experiment depends
on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from experiment.events import EventType
from experiment.mockenv.registry import (
    BASE_PERMISSIONS,
    TOOL_REGISTRY,
    ToolSpec,
)
from experiment.mockenv.services import MockEnvironment, ToolOutcome
from experiment.observability.bus import Observation, TelemetryBus


@dataclass
class ToolResponse:
    """What the agent gets back. Deliberately narrow."""

    status: str
    content: Any
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def as_text(self) -> str:
        if self.content is None:
            return self.error or ""
        return self.content if isinstance(self.content, str) else str(self.content)


class ToolGateway:
    """Mediates and instruments all agent-environment interaction."""

    def __init__(self, environment: MockEnvironment, bus: TelemetryBus, agent_id: str) -> None:
        self._environment = environment
        self._bus = bus
        self._agent_id = agent_id
        self._permissions: tuple[str, ...] = tuple(BASE_PERMISSIONS)
        self.exercised_capabilities: list[str] = []

    # -- exposed to the agent -------------------------------------------------

    @property
    def permissions(self) -> tuple[str, ...]:
        return self._permissions

    def catalog(self) -> list[ToolSpec]:
        return list(TOOL_REGISTRY.values())

    def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        objective_id: str,
        self_report: str | None = None,
    ) -> ToolResponse:
        spec = TOOL_REGISTRY.get(tool_name)
        category = spec.category if spec else "unknown"
        untrusted = bool(spec and spec.returns_untrusted_content)

        self._bus.emit(
            Observation(
                event_type=EventType.TOOL_INVOCATION,
                agent_id=self._agent_id,
                objective_id=objective_id,
                action=f"invoke:{tool_name}",
                tool_name=tool_name,
                tool_category=category,
                target_resource=_target_of(arguments),
                raw_arguments=dict(arguments),
                result_status="n/a",
                self_report=self_report,
                returns_untrusted_content=untrusted,
                permissions_before=self._permissions,
                permissions_after=self._permissions,
            )
        )

        outcome: ToolOutcome = self._environment.call(tool_name, arguments, self._permissions)
        self.exercised_capabilities.append(tool_name)

        self._bus.emit(
            Observation(
                event_type=EventType.TOOL_RESULT,
                agent_id=self._agent_id,
                objective_id=objective_id,
                action=f"result:{tool_name}",
                tool_name=tool_name,
                tool_category=category,
                target_resource=outcome.target_resource or _target_of(arguments),
                raw_payload_text=_as_text(outcome.payload),
                preview_text=outcome.preview,
                result_status=outcome.status,
                error=outcome.error,
                credential_name=outcome.credential_name,
                external_resource=outcome.external_resource,
                returns_untrusted_content=untrusted,
                permissions_before=self._permissions,
                permissions_after=self._permissions,
                metadata={"payload_length": len(_as_text(outcome.payload) or "")},
            )
        )

        # Content (but never credential material) becomes part of the agent's
        # observable input state.
        if outcome.status == "ok" and outcome.payload is not None and not outcome.credential_name:
            self._bus.emit(
                Observation(
                    event_type=EventType.OBSERVATION_INGESTED,
                    agent_id=self._agent_id,
                    objective_id=objective_id,
                    action=f"ingest:{tool_name}",
                    tool_name=tool_name,
                    tool_category=category,
                    target_resource=outcome.target_resource,
                    external_resource=outcome.external_resource,
                    returns_untrusted_content=untrusted,
                    result_status="ok",
                )
            )

        if outcome.granted_permissions:
            before = self._permissions
            after = tuple(sorted(set(before) | set(outcome.granted_permissions)))
            if set(after) != set(before):
                self._permissions = after
                self._bus.emit(
                    Observation(
                        event_type=EventType.PERMISSION_CHANGE,
                        agent_id=self._agent_id,
                        objective_id=objective_id,
                        action="capability_set_changed",
                        tool_name=tool_name,
                        tool_category=category,
                        target_resource=outcome.credential_name,
                        result_status="ok",
                        permissions_before=before,
                        permissions_after=after,
                        metadata={
                            "granted": sorted(set(after) - set(before)),
                            "granted_by": "credential_acquisition",
                        },
                    )
                )

        for change in outcome.environment_changes:
            self._bus.emit(
                Observation(
                    event_type=EventType.ENVIRONMENT_CHANGE,
                    agent_id=self._agent_id,
                    objective_id=objective_id,
                    action=change["kind"],
                    tool_name=tool_name,
                    tool_category=category,
                    target_resource=change.get("resource"),
                    result_status="ok",
                    metadata={k: v for k, v in change.items() if k != "kind"},
                )
            )

        return ToolResponse(status=outcome.status, content=outcome.payload, error=outcome.error)

    # -- used by the runtime, not by the agent policy -------------------------

    def emit(self, observation: Observation) -> int:
        return self._bus.emit(observation)


def _as_text(payload: Any) -> str | None:
    if payload is None:
        return None
    return payload if isinstance(payload, str) else str(payload)


def _target_of(arguments: dict[str, Any]) -> str | None:
    for key in ("document_id", "service", "username", "resource_id", "name", "path", "key"):
        if key in arguments:
            return str(arguments[key])
    return None
