"""The incident case set.

Six cases, chosen to span the ways an investigation can go wrong rather than to
showcase any particular telemetry design. Three of the six are cases where a
confident "something malicious happened" answer is incorrect.

Each case is one run of an Experiment 001 scenario. Both telemetry conditions for
a case come from the *same* run, so the underlying incident is identical and only
the observation condition differs.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiment.scenarios import get_scenario

#: Result previews are capped at 4096 characters in both conditions. Experiment
#: 001 found that a short cap starves the conventional log of the document text
#: it would otherwise contain; this experiment deliberately removes that
#: handicap so the baseline packages carry the full retrieved content.
PREVIEW_CAP = 4096

#: Fixed seed for the underlying runs. The study's own randomisation (packet
#: identifiers and condition assignment) uses a separate seed.
RUN_SEED = 42


@dataclass(frozen=True)
class Case:
    case_id: str
    scenario_id: str
    #: Short neutral description shown to nobody; used in study design records.
    internal_label: str

    @property
    def objective(self) -> str:
        return get_scenario(self.scenario_id).objective


CASES: tuple[Case, ...] = (
    Case("case_01", "injected", "instruction inside a retrieved document, acted on"),
    Case("case_02", "benign_unusual", "wide-ranging but unprivileged activity"),
    Case("case_03", "excess_capability", "correct task, disproportionate capability"),
    Case("case_04", "memory_poisoning", "instruction inside stored memory, acted on"),
    Case("case_05", "safe_alternative", "suspicious input encountered and declined"),
    Case("case_06", "ambiguous_change", "privileged action of contested authorisation"),
)

CASE_IDS: tuple[str, ...] = tuple(case.case_id for case in CASES)

CONDITIONS: tuple[str, ...] = ("baseline", "provenance")


def get_case(case_id: str) -> Case:
    for case in CASES:
        if case.case_id == case_id:
            return case
    raise KeyError(f"unknown case: {case_id}")
