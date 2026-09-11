"""Blinded packet identifiers and condition assignment.

Nothing an investigator receives names a condition. Packet identifiers are
derived from a study seed with HMAC, so they are reproducible for the
experimenters and uninformative to participants.

The hidden mapping lives in ``private/condition_map.json`` and is never written
into a packet directory.
"""

from __future__ import annotations

import hmac
import random
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from experiment2.cases import CASE_IDS, CONDITIONS

#: Characters used for packet codes: unambiguous when read aloud or retyped.
_ALPHABET = "ACDEFGHJKLMNPQRTUVWXY34679"


def packet_code(study_seed: int, case_id: str, condition: str, length: int = 4) -> str:
    digest = hmac.new(
        str(study_seed).encode("utf-8"), f"{case_id}|{condition}".encode("utf-8"), sha256
    ).digest()
    return "".join(_ALPHABET[b % len(_ALPHABET)] for b in digest[:length])


def packet_id(study_seed: int, case_id: str, condition: str) -> str:
    return f"{case_id}_packet_{packet_code(study_seed, case_id, condition)}"


def build_condition_map(study_seed: int) -> dict[str, dict[str, str]]:
    """packet id -> {case_id, condition}. Evaluator-only."""
    mapping: dict[str, dict[str, str]] = {}
    for case_id in CASE_IDS:
        for condition in CONDITIONS:
            mapping[packet_id(study_seed, case_id, condition)] = {
                "case_id": case_id,
                "condition": condition,
            }
    if len(mapping) != len(CASE_IDS) * len(CONDITIONS):
        raise RuntimeError("packet identifier collision; choose another study seed")
    return mapping


@dataclass
class Assignment:
    participant_id: str
    #: Ordered list of (case_id, condition, packet_id) as the participant sees them.
    sequence: list[dict[str, str]] = field(default_factory=list)

    def packet_ids(self) -> list[str]:
        return [entry["packet_id"] for entry in self.sequence]

    def cases(self) -> list[str]:
        return [entry["case_id"] for entry in self.sequence]


def assign_participants(
    study_seed: int,
    participant_ids: list[str],
    strategy: str = "counterbalanced",
) -> list[Assignment]:
    """Between-subject assignment: one condition per case per participant.

    ``counterbalanced`` alternates conditions along both axes, so each
    participant sees roughly half of each condition and each case is seen in both
    conditions across participants. No participant ever receives both conditions
    of the same case, which is what would make the manipulation obvious.

    ``fixed_baseline`` / ``fixed_provenance`` give a participant a single
    condition throughout; useful for a pure between-subject pilot.
    """
    assignments: list[Assignment] = []
    for participant_index, participant_id in enumerate(participant_ids):
        # Presentation order is shuffled per participant so that position in the
        # session is not confounded with case identity.
        order = list(CASE_IDS)
        random.Random(f"{study_seed}:{participant_id}").shuffle(order)

        sequence: list[dict[str, str]] = []
        for case_id in order:
            # The condition is keyed to the case's fixed ordinal, not to its
            # position in this participant's shuffled order. Keying it to the
            # shuffled position would let the presentation shuffle destroy
            # per-case balance (one case could land in the same condition for
            # every participant).
            case_ordinal = CASE_IDS.index(case_id)
            if strategy == "counterbalanced":
                condition = CONDITIONS[(participant_index + case_ordinal) % len(CONDITIONS)]
            elif strategy in ("fixed_baseline", "fixed_provenance"):
                condition = strategy.removeprefix("fixed_")
            else:
                raise ValueError(f"unknown assignment strategy: {strategy}")
            sequence.append(
                {
                    "case_id": case_id,
                    "condition": condition,
                    "packet_id": packet_id(study_seed, case_id, condition),
                }
            )
        assignments.append(Assignment(participant_id=participant_id, sequence=sequence))

    _check_between_subject(assignments)
    return assignments


def _check_between_subject(assignments: list[Assignment]) -> None:
    for assignment in assignments:
        seen = [entry["case_id"] for entry in assignment.sequence]
        if len(seen) != len(set(seen)):
            raise RuntimeError(
                f"{assignment.participant_id} would see the same case twice; "
                "that breaks between-subject blinding"
            )


def assignment_summary(assignments: list[Assignment]) -> dict[str, Any]:
    per_condition: dict[str, int] = {condition: 0 for condition in CONDITIONS}
    per_case: dict[str, dict[str, int]] = {
        case_id: {condition: 0 for condition in CONDITIONS} for case_id in CASE_IDS
    }
    for assignment in assignments:
        for entry in assignment.sequence:
            per_condition[entry["condition"]] += 1
            per_case[entry["case_id"]][entry["condition"]] += 1
    return {
        "participants": len(assignments),
        "observations_per_condition": per_condition,
        "observations_per_case": per_case,
        "balanced_overall": len(set(per_condition.values())) == 1,
        "every_case_seen_in_both_conditions": all(
            all(count > 0 for count in counts.values()) for counts in per_case.values()
        ),
    }
