"""Study packets: blinding, separation, and that both conditions share a run."""

from __future__ import annotations

import json
from pathlib import Path

from experiment2.cases import CASE_IDS, CONDITIONS
from experiment2.packets import FORBIDDEN_PACKET_TERMS, STRIPPED_FIELDS
from experiment2.study import PACKET_FILES


def _packet_text(directory: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    )


def test_every_packet_has_the_expected_files(packets):
    for packet_id, entry in packets.items():
        for name in PACKET_FILES:
            path = entry["directory"] / name
            assert path.exists() and path.stat().st_size > 0, f"{packet_id}/{name}"


def test_packets_contain_no_condition_or_experiment_vocabulary(packets):
    for packet_id, entry in packets.items():
        text = _packet_text(entry["directory"]).lower()
        for term in FORBIDDEN_PACKET_TERMS:
            assert term not in text, f"{packet_id} leaks {term!r}"


def test_packets_contain_no_condition_mapping(study, packets):
    mapping = json.dumps(study["conditions"])
    del mapping
    for packet_id, entry in packets.items():
        text = _packet_text(entry["directory"])
        assert "condition_map" not in text
        # No packet may name any other packet, which would let a participant
        # correlate their package with someone else's.
        for other in packets:
            if other != packet_id:
                assert other not in text, f"{packet_id} names {other}"


def test_packets_contain_no_evaluator_material(packets):
    markers = (
        "expected_classification",
        "acceptable_classifications",
        "key_facts",
        "distractor_facts",
        "unsupported_causal_claims",
        "summary_for_adjudicators",
        "ambiguity_level",
        "confidence_band",
    )
    for packet_id, entry in packets.items():
        text = _packet_text(entry["directory"])
        for marker in markers:
            assert marker not in text, f"{packet_id} leaks evaluator field {marker!r}"


def test_private_material_is_outside_the_packet_tree(study):
    root: Path = study["root"]
    private = root / "private"
    assert (private / "condition_map.json").exists()
    assert (private / "evaluator_manifests").is_dir()
    packets_tree = root / "packets"
    for path in packets_tree.rglob("*"):
        assert "private" not in path.parts, path


def test_records_are_renumbered_contiguously_and_strip_identifying_fields(packets):
    for packet_id, entry in packets.items():
        records = entry["packet"].records
        assert [r.record_no for r in records] == list(range(1, len(records) + 1)), packet_id
        for record in records:
            for field in STRIPPED_FIELDS:
                assert field not in record.data, f"{packet_id} kept {field}"


def test_both_conditions_of_a_case_describe_the_same_incident(packets):
    for case_id in CASE_IDS:
        streams = {}
        for entry in packets.values():
            if entry["case_id"] == case_id:
                streams[entry["condition"]] = [
                    (r.event_type, r.tool_name, r.target_resource)
                    for r in entry["packet"].records
                    if r.event_type in ("tool_invocation", "tool_result", "environment_change")
                ]
        assert streams["baseline"] == streams["provenance"], case_id


def test_only_one_condition_records_links(packets):
    for entry in packets.values():
        links = sum(len(r.data.get("links", [])) for r in entry["packet"].records)
        if entry["condition"] == "baseline":
            assert links == 0
        else:
            assert links > 0


def test_both_conditions_carry_the_full_result_content(packets):
    """The conventional condition must not be information-starved."""
    for case_id in CASE_IDS:
        lengths = {}
        for entry in packets.values():
            if entry["case_id"] != case_id:
                continue
            lengths[entry["condition"]] = sum(
                len(str(r.data.get("result_preview", ""))) for r in entry["packet"].records
            )
        assert lengths["baseline"] == lengths["provenance"], case_id
        assert "truncated" not in str(
            [r.data.get("result_preview") for entry in packets.values() for r in entry["packet"].records]
        )


def test_evidence_volume_is_recorded_for_every_packet(study):
    volumes = {item["packet_id"]: item["evidence_volume"] for item in study["design"]["packets"]}
    assert len(volumes) == len(CASE_IDS) * len(CONDITIONS)
    for packet_id, volume in volumes.items():
        for key in ("record_count", "readable_characters", "readable_estimated_tokens"):
            assert volume[key] > 0, f"{packet_id}/{key}"
    summary = study["design"]["evidence_volume_by_condition"]
    assert summary["provenance"]["readable_characters"] > summary["baseline"]["readable_characters"]


def test_questionnaire_is_identical_across_conditions_of_a_case(packets):
    for case_id in CASE_IDS:
        texts = set()
        for entry in packets.values():
            if entry["case_id"] == case_id:
                text = (entry["directory"] / "questionnaire.md").read_text(encoding="utf-8")
                # Only the packet identifier differs.
                texts.add(text.replace(entry["packet"].packet_id, "PACKET"))
        assert len(texts) == 1, case_id
