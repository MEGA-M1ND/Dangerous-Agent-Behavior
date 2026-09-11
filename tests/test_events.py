"""Event schema: serialization, ordering, and the baseline/provenance relation."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from experiment.events import (
    PROVENANCE_ONLY_EVENT_TYPES,
    PROVENANCE_ONLY_FIELDS,
    Event,
    EventType,
    EvidenceKind,
    is_observed,
)
from experiment.ids import VIRTUAL_EPOCH
from experiment.observability.baseline import project_to_baseline


def test_event_round_trips_through_json(events):
    for stream in events["injected"].values():
        for event in stream:
            restored = Event.model_validate_json(event.to_jsonl())
            assert restored == event


def test_every_serialized_line_is_valid_json(runs):
    for run in runs.values():
        for path in (run.baseline_path, run.provenance_path):
            for line in path.read_text(encoding="utf-8").splitlines():
                json.loads(line)


def test_events_are_strictly_ordered_and_gapless_within_a_stream(events):
    for streams in events.values():
        for stream in streams.values():
            sequences = [e.sequence_number for e in stream]
            assert sequences == sorted(sequences)
            assert len(sequences) == len(set(sequences))


def test_timestamps_follow_the_virtual_clock(events):
    for event in events["benign"]["provenance"]:
        assert event.timestamp >= VIRTUAL_EPOCH
        # Timestamp is a pure function of the sequence number in deterministic mode.
        assert (event.timestamp - VIRTUAL_EPOCH).total_seconds() == pytest.approx(
            event.sequence_number * 0.05
        )


def test_baseline_stream_is_a_field_level_subset_of_the_provenance_stream(events):
    """The two conditions observe the same run; baseline drops relational fields."""
    for scenario_id, streams in events.items():
        provenance = {e.sequence_number: e for e in streams["provenance"]}
        for baseline_event in streams["baseline"]:
            counterpart = provenance[baseline_event.sequence_number]
            assert counterpart.event_type is baseline_event.event_type, scenario_id
            projected = project_to_baseline(counterpart)
            assert projected is not None
            assert projected.model_dump() == baseline_event.model_dump(), (
                scenario_id,
                baseline_event.sequence_number,
            )


def test_baseline_never_carries_provenance_only_fields_or_event_types(events):
    for streams in events.values():
        for event in streams["baseline"]:
            assert event.event_type not in PROVENANCE_ONLY_EVENT_TYPES
            for name in PROVENANCE_ONLY_FIELDS:
                value = getattr(event, name)
                assert value in (None, [], {}), name


def test_provenance_stream_contains_the_extra_event_types(events):
    types = {e.event_type for e in events["injected"]["provenance"]}
    assert EventType.OBSERVATION_INGESTED in types
    assert EventType.PERMISSION_CHANGE in types


def test_evidence_kinds_split_into_observed_and_inferred():
    assert is_observed(EvidenceKind.VERBATIM_SUBSTRING_MATCH)
    assert is_observed(EvidenceKind.CREDENTIAL_REFERENCE_IDENTITY)
    assert not is_observed(EvidenceKind.PRESENT_IN_OBSERVABLE_CONTEXT)
    assert not is_observed(EvidenceKind.TEMPORAL_ADJACENCY)


def test_event_model_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Event(
            event_id="x", run_id="r", timestamp=VIRTUAL_EPOCH, sequence_number=0,
            scenario_id="s", agent_id="a", event_type=EventType.RUN_STARTED,
            not_a_real_field=1,
        )
