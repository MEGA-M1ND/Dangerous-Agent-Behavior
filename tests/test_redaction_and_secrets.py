"""Credentials must never reach any artifact.

The credentials in this experiment are synthetic, but they are handled as if they
were real: no log, report, graph or reconstruction may contain a raw value.
"""

from __future__ import annotations

from pathlib import Path

from experiment.mockenv.services import MockEnvironment
from experiment.redaction import (
    BASELINE_REDACTION,
    SYNTHETIC_SECRET_PATTERN,
    credential_reference,
    sanitize_arguments,
    scrub_text,
)


def test_secret_values_are_recognisably_synthetic(tmp_path):
    environment = MockEnvironment(tmp_path / "sandbox", "clean")
    for value in environment.synthetic_secret_values():
        assert value.startswith("SYNTHETIC-")
        assert SYNTHETIC_SECRET_PATTERN.search(value)


def test_sanitize_redacts_by_argument_name_and_by_value_shape():
    sanitized = sanitize_arguments(
        {
            "username": "demo",
            "token": "SYNTHETIC-DEMO_CLOUD_TOKEN-aabbccdd",
            "nested": {"api_key": "anything"},
            "list": ["SYNTHETIC-X_Y-00112233", "harmless"],
            "loose": "SYNTHETIC-X_Y-00112233",
        }
    )
    assert sanitized["username"] == "demo"
    assert sanitized["token"] == BASELINE_REDACTION
    assert sanitized["nested"]["api_key"] == BASELINE_REDACTION
    assert sanitized["list"] == [BASELINE_REDACTION, "harmless"]
    assert sanitized["loose"] == BASELINE_REDACTION


def test_credential_reference_is_stable_and_carries_no_secret():
    value = "SYNTHETIC-DEMO_CLOUD_TOKEN-aabbccdd"
    reference = credential_reference("demo_cloud_token", value)
    assert reference == credential_reference("demo_cloud_token", value)
    assert value not in reference
    assert reference.startswith("cred://demo_cloud_token#")


def test_scrub_text_removes_secret_material_from_free_text():
    assert "SYNTHETIC-" not in scrub_text("prefix SYNTHETIC-A_B-01234567 suffix")


def test_no_synthetic_credential_appears_in_any_generated_artifact(runs, analyses, tmp_path):
    """The headline safety test: sweep every file the experiment writes."""
    from experiment.evaluation.report import write_artifacts

    secrets: set[str] = set()
    for run in runs.values():
        environment = MockEnvironment(tmp_path / f"probe-{run.run_id}", run.scenario.corpus)
        secrets.update(environment.synthetic_secret_values())
    assert secrets, "expected the mock secret store to hold synthetic credentials"

    for scenario_id, analysis in analyses.items():
        write_artifacts(analysis)
        run_dir: Path = analysis.run.run_dir
        files = [p for p in run_dir.rglob("*") if p.is_file()]
        assert files
        for path in files:
            blob = path.read_text(encoding="utf-8", errors="replace")
            for secret in secrets:
                assert secret not in blob, f"{secret!r} leaked into {path} ({scenario_id})"
            assert not SYNTHETIC_SECRET_PATTERN.search(blob), f"secret-shaped text in {path}"


def test_credential_flows_are_represented_by_reference_not_value(events):
    references = [
        e.credential_reference
        for e in events["injected"]["provenance"]
        if e.credential_reference
    ]
    assert references, "the injected scenario is expected to involve a credential"
    for reference in references:
        assert reference.startswith("cred://")
        assert "SYNTHETIC-" not in reference
