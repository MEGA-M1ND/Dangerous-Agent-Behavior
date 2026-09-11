"""Response handling, timing, adjudication, metrics gating and the LLM prompt."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from experiment2.adjudication import (
    anonymous_label,
    build_sheet,
    inter_rater_agreement,
    write_sheets,
)
from experiment2.investigators import llm
from experiment2.investigators.mock import PROFILES, build
from experiment2.metrics import PreregistrationMissing, compute_all, effect_size, require_preregistration
from experiment2.questionnaire import QUESTIONNAIRE_VERSION, InvestigatorResponse
from experiment2.responses import (
    MOCK_NAMESPACE,
    load_responses,
    response_counts,
    start,
    store_response,
    submit,
)
from experiment2.scoring import score_response


@pytest.fixture
def workspace(study, tmp_path) -> Path:
    """A writable copy of the built study, so tests never mutate the fixture."""
    root = tmp_path / "study"
    shutil.copytree(study["root"], root)
    return root


def _answers(packet_id: str, participant: str = "P1") -> dict:
    return {
        "participant_id": participant,
        "packet_id": packet_id,
        "investigator_kind": "human",
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "q1_objective": "Report whether the demo service is healthy.",
        "q2_classification": "dangerous",
        "q2_justification": "A privileged account was created.",
        "q3_source_type": "retrieved_document",
        "q3_source_identifier": "ops runbook",
        "q4_capability": "create admin user",
        "q5_proportionality": "unnecessary",
        "q5_explanation": "The task needed read-only calls.",
        "q6_information_flow": "strong_evidence",
        "q7_intervention": "27",
        "q8_reconstruction": "The assistant read a document and then created an admin account.",
        "q9_confidence": 80,
        "q10_missing_evidence": "Who wrote the document.",
    }


# --------------------------------------------------------------------------- #
# Timing and ingestion
# --------------------------------------------------------------------------- #

def test_timing_is_recorded_only_when_a_start_exists(workspace, study):
    packet_id = next(iter(study["conditions"]))
    start(workspace, "P1", packet_id)
    response = submit(
        workspace,
        _answers(packet_id),
        submitted_at=datetime.now(timezone.utc) + timedelta(seconds=90),
    )
    assert response.timing_is_reliable is True
    assert response.duration_seconds is not None and response.duration_seconds >= 89

    other = next(pid for pid in study["conditions"] if pid != packet_id)
    without_start = submit(workspace, _answers(other, "P2"))
    assert without_start.timing_is_reliable is False
    assert without_start.duration_seconds is None


def test_submitted_responses_round_trip_from_disk(workspace, study):
    packet_id = next(iter(study["conditions"]))
    submit(workspace, _answers(packet_id))
    loaded = load_responses(workspace)
    assert [r.packet_id for r in loaded] == [packet_id]
    assert loaded[0].q2_classification == "dangerous"


def test_invalid_responses_are_rejected(workspace, study):
    packet_id = next(iter(study["conditions"]))
    answers = _answers(packet_id) | {"q2_classification": "extremely dangerous"}
    with pytest.raises(Exception):
        submit(workspace, answers)


def test_confidence_outside_the_range_is_rejected(workspace, study):
    packet_id = next(iter(study["conditions"]))
    with pytest.raises(Exception):
        submit(workspace, _answers(packet_id) | {"q9_confidence": 140})


# --------------------------------------------------------------------------- #
# Mock quarantine
# --------------------------------------------------------------------------- #

def test_mock_responses_are_never_loaded_as_study_evidence(workspace, study, packets):
    packet_id = next(iter(study["conditions"]))
    entry = packets[packet_id]
    for profile in PROFILES:
        store_response(
            workspace,
            build(profile, f"mock_{profile}", entry["packet"], entry["case_id"]),
            MOCK_NAMESPACE,
        )
    assert load_responses(workspace) == []
    assert len(load_responses(workspace, include_mock=True)) == len(PROFILES)
    assert response_counts(workspace)["mock"] == len(PROFILES)


# --------------------------------------------------------------------------- #
# Metrics gating
# --------------------------------------------------------------------------- #

def test_metrics_refuse_to_run_before_the_preregistration_exists(workspace, tmp_path):
    empty_repository = tmp_path / "repo"
    empty_repository.mkdir()
    with pytest.raises(PreregistrationMissing):
        compute_all(workspace, empty_repository)


def test_metrics_run_once_the_preregistration_exists(workspace, study, tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "EXPERIMENT_002_PREREGISTRATION.md").write_text("# plan\n", encoding="utf-8")
    require_preregistration(repository)

    for index, packet_id in enumerate(sorted(study["conditions"])[:4]):
        submit(workspace, _answers(packet_id, f"P{index}"))
    results = compute_all(workspace, repository)
    assert results["aggregate"]["totals"]["responses"] == 4
    assert set(results["aggregate"]["by_condition"]) == {"baseline", "provenance"}
    assert results["aggregate"]["evidence_volume_by_condition"] is not None


def test_effect_size_is_withheld_when_it_would_be_meaningless():
    assert effect_size([1.0], [2.0])["computable"] is False
    assert effect_size([1.0, 1.0], [1.0, 1.0])["computable"] is False
    computed = effect_size([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
    assert computed["computable"] is True
    assert "Descriptive only" in computed["interpretation"]


# --------------------------------------------------------------------------- #
# Adjudication
# --------------------------------------------------------------------------- #

def test_adjudication_sheets_hide_the_condition_and_the_participant(workspace, study, packets):
    packet_id = next(iter(study["conditions"]))
    entry = packets[packet_id]
    response = InvestigatorResponse.model_validate(_answers(packet_id, "Alice"))
    scored = score_response(response, entry["case_id"], entry["packet"])
    sheet = build_sheet(response, scored).to_dict()
    text = json.dumps(sheet)
    assert "Alice" not in text
    assert entry["condition"] not in text
    assert sheet["label"] == anonymous_label(packet_id, "Alice")
    assert sheet["rubric"]


def test_adjudication_sheets_are_written_and_carry_the_rubric(workspace, study, packets):
    packet_id = next(iter(study["conditions"]))
    entry = packets[packet_id]
    response = InvestigatorResponse.model_validate(_answers(packet_id, "Bob"))
    scored = score_response(response, entry["case_id"], entry["packet"])
    written = write_sheets(workspace, [(response, scored)])
    assert len(written) == 1 and written[0].exists()
    assert (workspace / "adjudications" / "score_entry_template.json").exists()


def test_inter_rater_agreement_reports_honestly_with_one_adjudicator():
    single = inter_rater_agreement(
        [{"label": "answer_1", "adjudicator_id": "A", "reconstruction_score": 9}]
    )
    assert single["doubly_scored_responses"] == 0

    pair = inter_rater_agreement(
        [
            {"label": "answer_1", "adjudicator_id": "A", "reconstruction_score": 9},
            {"label": "answer_1", "adjudicator_id": "B", "reconstruction_score": 10},
            {"label": "answer_2", "adjudicator_id": "A", "reconstruction_score": 5},
            {"label": "answer_2", "adjudicator_id": "B", "reconstruction_score": 5},
        ]
    )
    assert pair["doubly_scored_responses"] == 2
    assert pair["exact_agreement_rate"] == 0.5
    assert pair["agreement_within_one_point_rate"] == 1.0


# --------------------------------------------------------------------------- #
# LLM investigator
# --------------------------------------------------------------------------- #

def test_llm_prompt_contains_no_evaluator_material_or_study_framing(study, packets):
    for packet_id, entry in packets.items():
        prompt = llm.build_prompt(entry["directory"]).lower()
        for term in (
            "provenance",
            "baseline",
            "hypothesis",
            "ground truth",
            "expected_classification",
            "acceptable_classifications",
            "ambiguity_level",
            "key_facts",
            "condition",
            "experiment",
        ):
            assert term not in prompt, f"{packet_id}: prompt leaks {term!r}"


def test_llm_prompt_is_built_from_the_public_packet_only(study, packets, tmp_path):
    """Copy one packet directory alone; the prompt must still build."""
    packet_id, entry = next(iter(packets.items()))
    isolated = tmp_path / "isolated" / packet_id
    shutil.copytree(entry["directory"], isolated)
    assert llm.build_prompt(isolated)


def test_llm_investigator_is_skipped_without_configuration(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("EXPERIMENT_LLM_PROVIDER", "anthropic")
    assert llm.is_configured() is False
    with pytest.raises(llm.LLMInvestigatorUnavailable):
        llm.investigate(Path("."), "p", "llm_r1")
