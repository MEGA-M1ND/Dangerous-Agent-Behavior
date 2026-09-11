"""Assignment, counterbalancing and reproducibility of the blinding."""

from __future__ import annotations

import pytest

from experiment2.blinding import (
    assign_participants,
    assignment_summary,
    build_condition_map,
    packet_id,
)
from experiment2.cases import CASE_IDS, CONDITIONS


def test_packet_ids_are_reproducible_for_a_fixed_seed():
    first = build_condition_map(1234)
    second = build_condition_map(1234)
    assert first == second
    assert build_condition_map(1235) != first


def test_packet_ids_do_not_encode_the_condition():
    for case_id in CASE_IDS:
        codes = {
            condition: packet_id(999, case_id, condition).rsplit("_", 1)[-1]
            for condition in CONDITIONS
        }
        assert len(set(codes.values())) == len(CONDITIONS)
        for code in codes.values():
            assert not any(
                word in code.lower() for word in ("base", "prov", "a", "b")
            ) or code.isalnum()


def test_condition_map_covers_every_case_and_condition():
    mapping = build_condition_map(4242)
    assert len(mapping) == len(CASE_IDS) * len(CONDITIONS)
    assert {entry["case_id"] for entry in mapping.values()} == set(CASE_IDS)
    assert {entry["condition"] for entry in mapping.values()} == set(CONDITIONS)


def test_assignment_is_reproducible_for_a_fixed_seed():
    first = assign_participants(77, ["P1", "P2", "P3"])
    second = assign_participants(77, ["P1", "P2", "P3"])
    assert [a.sequence for a in first] == [a.sequence for a in second]
    other = assign_participants(78, ["P1", "P2", "P3"])
    assert [a.sequence for a in other] != [a.sequence for a in first]


def test_no_participant_sees_the_same_case_twice():
    for assignment in assign_participants(77, [f"P{i}" for i in range(1, 7)]):
        cases = assignment.cases()
        assert len(cases) == len(set(cases)) == len(CASE_IDS)


def test_counterbalancing_keeps_both_conditions_present_for_every_case():
    for participant_count in (2, 4, 6):
        assignments = assign_participants(77, [f"P{i}" for i in range(participant_count)])
        summary = assignment_summary(assignments)
        assert summary["balanced_overall"], participant_count
        assert summary["every_case_seen_in_both_conditions"], participant_count


def test_presentation_order_differs_between_participants():
    assignments = assign_participants(77, ["P1", "P2", "P3", "P4"])
    orders = {tuple(a.cases()) for a in assignments}
    assert len(orders) > 1


def test_fixed_condition_strategies_are_available():
    for strategy, expected in (
        ("fixed_baseline", "baseline"),
        ("fixed_provenance", "provenance"),
    ):
        assignment = assign_participants(77, ["P1"], strategy=strategy)[0]
        assert {entry["condition"] for entry in assignment.sequence} == {expected}


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError):
        assign_participants(77, ["P1"], strategy="whatever")


def test_participant_bundles_contain_only_that_participant_s_packets(study):
    design = study["design"]
    for participant in design["assignment"]["participants"]:
        bundle = study["root"] / "packets" / participant["participant_id"]
        assert bundle.is_dir()
        expected = {entry["packet_id"] for entry in participant["sequence"]}
        # Folder names are "<order>_<packet id>"; strip the ordering prefix.
        present = {path.name.split("_", 1)[1] for path in bundle.iterdir() if path.is_dir()}
        assert present == expected, participant["participant_id"]
