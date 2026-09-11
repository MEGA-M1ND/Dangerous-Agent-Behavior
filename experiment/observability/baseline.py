"""Conventional agent-application logging (the baseline condition).

This is intended to be a *strong* baseline: everything a well-instrumented agent
application could reasonably record is here - timestamps, agent identity, model
request/response boundaries, tool names and categories, sanitized arguments,
result status, result previews, errors, and basic application events such as
environment changes.

What it does not contain is the explicit relational/provenance information
introduced by the independent observer: which prior outputs were present in the
input state of a later call, which credential reference flowed where, and how the
capability set changed over time.
"""

from __future__ import annotations

from experiment.events import (
    PROVENANCE_ONLY_EVENT_TYPES,
    PROVENANCE_ONLY_FIELDS,
    Event,
)
from experiment.ids import Clock, stable_uuid
from experiment.observability.bus import Observation
from experiment.redaction import sanitize_arguments, scrub_text

DEFAULT_PREVIEW_CAP = 512


def truncate_preview(text: str | None, cap: int) -> str | None:
    if text is None:
        return None
    text = scrub_text(text)
    if cap >= 0 and len(text) > cap:
        return text[:cap] + f"...[truncated, {len(text)} chars total]"
    return text


class BaselineLogger:
    """Records the conventional subset of each observation."""

    name = "baseline_logger"

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

    def observe(self, observation: Observation, sequence_number: int) -> Event | None:
        if observation.event_type in PROVENANCE_ONLY_EVENT_TYPES:
            # A conventional agent log has no notion of "content entered the
            # observable input state" or "the capability set changed".
            return None
        return Event(
            event_id=stable_uuid(self.run_id, sequence_number),
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
            metadata=dict(observation.metadata),
            observer_source="baseline_logger",
        )


def project_to_baseline(event: Event) -> Event | None:
    """Strip every provenance-only field from an event.

    Used by tests to verify that the baseline stream really is a field-level
    subset of the provenance stream observed over the same run, and by the
    preview-cap sensitivity analysis.
    """
    if event.event_type in PROVENANCE_ONLY_EVENT_TYPES:
        return None
    blanked: dict[str, object] = {}
    for name in PROVENANCE_ONLY_FIELDS:
        field = Event.model_fields[name]
        # Fields declared with a default factory (the list-valued ones) blank to an
        # empty list; optional scalar fields blank to None.
        blanked[name] = field.default_factory() if field.default_factory else None
    return event.model_copy(update={**blanked, "observer_source": "baseline_logger"})

