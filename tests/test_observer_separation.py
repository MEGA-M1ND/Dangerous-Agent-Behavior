"""The observer must sit outside the agent's decision logic.

Three claims are tested:

1. the agent runtime holds no reference to a sink, logger, observer or bus;
2. telemetry files are append-only for the duration of a run, and sealed sinks
   reject further writes;
3. the hash chain over each file detects post-hoc edits.
"""

from __future__ import annotations

import gc

import pytest

from experiment.gateway import ToolGateway
from experiment.observability.baseline import BaselineLogger
from experiment.observability.bus import TelemetryBus
from experiment.observability.observer import ProvenanceObserver
from experiment.observability.sinks import (
    AppendOnlyJsonlSink,
    AppendOnlyViolation,
    chain_digest_of,
)


def test_gateway_exposes_only_a_call_surface_to_the_agent():
    agent_visible = {"call", "catalog", "permissions", "emit"}
    public = {name for name in dir(ToolGateway) if not name.startswith("_")}
    assert public == agent_visible


def test_agent_policies_and_adapters_cannot_reach_the_telemetry(runs):
    """No policy or adapter object may hold a sink, logger, observer or bus."""
    from experiment.agent.policies import build_policy
    from experiment.agent.adapters import DeterministicModelAdapter

    forbidden = (AppendOnlyJsonlSink, BaselineLogger, ProvenanceObserver, TelemetryBus)
    for name in ("task_focused", "instruction_following", "policy_compliant"):
        adapter = DeterministicModelAdapter(build_policy(name), seed=42)
        reachable = gc.get_referents(adapter.__dict__)
        for obj in [adapter, *reachable]:
            assert not isinstance(obj, forbidden)


def test_agent_runtime_module_does_not_import_telemetry_sinks():
    import ast
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "experiment/agent/runtime.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert "experiment.observability.sinks" not in imported
    assert "experiment.observability.observer" not in imported
    assert "experiment.observability.baseline" not in imported


def test_sealed_sink_rejects_further_writes(tmp_path, events):
    sink = AppendOnlyJsonlSink(tmp_path / "events.jsonl")
    event = events["benign"]["provenance"][0]
    sink.append(event)
    sink.seal()
    with pytest.raises(AppendOnlyViolation):
        sink.append(event)


def test_hash_chain_detects_tampering(runs, tmp_path):
    run = runs["injected"]
    assert chain_digest_of(run.provenance_path) == run.chain_digests["provenance_observer"]

    tampered = tmp_path / "tampered.jsonl"
    lines = run.provenance_path.read_text(encoding="utf-8").splitlines()
    index = next(i for i, line in enumerate(lines) if '"tool_invocation"' in line)
    lines[index] = lines[index].replace('"tool_invocation"', '"agent_step"', 1)
    tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert chain_digest_of(tampered) != run.chain_digests["provenance_observer"]


def test_both_conditions_observe_the_same_run(runs):
    """Same instrumentation point, same raw facts, different retention."""
    for run in runs.values():
        assert run.event_counts["provenance"] > run.event_counts["baseline"]
