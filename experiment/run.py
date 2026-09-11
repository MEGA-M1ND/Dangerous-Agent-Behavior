"""Run orchestration: execute one scenario and produce its telemetry.

This module wires the pieces together and writes the two event logs. It performs
no analysis, no scoring and no reporting.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from experiment.agent.adapters import (
    DeterministicModelAdapter,
    LLMConfig,
    LLMModelAdapter,
    ModelAdapter,
)
from experiment.agent.policies import build_policy
from experiment.agent.runtime import AgentResult, run_agent
from experiment.events import EventType
from experiment.gateway import ToolGateway
from experiment.ids import Clock, run_id_for
from experiment.mockenv.services import MockEnvironment
from experiment.observability.baseline import DEFAULT_PREVIEW_CAP, BaselineLogger
from experiment.observability.bus import Observation, TelemetryBus
from experiment.observability.observer import ProvenanceObserver
from experiment.observability.sinks import AppendOnlyJsonlSink
from experiment.scenarios import Scenario, get_scenario

AGENT_ID = "agent-001"
DEFAULT_ARTIFACTS_ROOT = Path("artifacts")


@dataclass(frozen=True)
class RunConfig:
    scenario_id: str
    mode: str = "deterministic"
    seed: int = 42
    preview_cap: int = DEFAULT_PREVIEW_CAP
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT

    @property
    def deterministic(self) -> bool:
        return self.mode == "deterministic"


@dataclass
class RunOutput:
    run_id: str
    scenario: Scenario
    config: RunConfig
    run_dir: Path
    baseline_path: Path
    provenance_path: Path
    agent_result: AgentResult
    environment_before: dict[str, Any]
    environment_after: dict[str, Any]
    chain_digests: dict[str, str]
    adapter_descriptor: str
    clock_mode: str
    event_counts: dict[str, int] = field(default_factory=dict)

    def manifest(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario.scenario_id,
            "scenario_title": self.scenario.title,
            "objective": self.scenario.objective,
            "objective_id": self.scenario.objective_id,
            "corpus": self.scenario.corpus,
            "policy": self.scenario.policy,
            "required_capabilities": list(self.scenario.required_capabilities),
            "mode": self.config.mode,
            "seed": self.config.seed,
            "preview_cap": self.config.preview_cap,
            "adapter": self.adapter_descriptor,
            "clock": self.clock_mode,
            "agent_answer": self.agent_result.answer,
            "agent_steps": self.agent_result.steps,
            "exercised_capabilities": self.agent_result.exercised_capabilities,
            "final_permissions": list(self.agent_result.final_permissions),
            "environment_before": self.environment_before,
            "environment_after": self.environment_after,
            "event_counts": self.event_counts,
            "telemetry_chain_digests": self.chain_digests,
        }


def build_adapter(scenario: Scenario, config: RunConfig) -> ModelAdapter:
    if config.deterministic:
        return DeterministicModelAdapter(build_policy(scenario.policy), config.seed)
    if config.mode == "llm":
        return LLMModelAdapter(LLMConfig.from_environment(), scenario.objective)
    raise ValueError(f"unknown mode: {config.mode}")


def execute_run(config: RunConfig) -> RunOutput:
    scenario = get_scenario(config.scenario_id)
    random.seed(config.seed)  # nothing here is random; set for reproducibility hygiene

    run_id = run_id_for(scenario.scenario_id, config.mode, config.seed)
    run_dir = Path(config.artifacts_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    clock = Clock(deterministic=config.deterministic)
    environment = MockEnvironment(run_dir / "sandbox", scenario.corpus)
    environment_before = environment.snapshot()

    baseline_path = run_dir / "baseline_events.jsonl"
    provenance_path = run_dir / "provenance_events.jsonl"
    baseline_sink = AppendOnlyJsonlSink(baseline_path)
    provenance_sink = AppendOnlyJsonlSink(provenance_path)

    bus = TelemetryBus(
        conditions=[
            (BaselineLogger(run_id, scenario.scenario_id, clock, config.preview_cap), baseline_sink),
            (ProvenanceObserver(run_id, scenario.scenario_id, clock, config.preview_cap), provenance_sink),
        ],
        clock=clock,
    )

    gateway = ToolGateway(environment, bus, AGENT_ID)
    adapter = build_adapter(scenario, config)

    bus.emit(
        Observation(
            event_type=EventType.RUN_STARTED,
            agent_id=AGENT_ID,
            objective_id=scenario.objective_id,
            action="run_started",
            result_status="ok",
            permissions_before=gateway.permissions,
            permissions_after=gateway.permissions,
            metadata={
                "scenario_id": scenario.scenario_id,
                "mode": config.mode,
                "seed": config.seed,
                "adapter": adapter.descriptor,
                "clock": clock.mode,
                "preview_cap": config.preview_cap,
            },
        )
    )
    bus.emit(
        Observation(
            event_type=EventType.MESSAGE_RECEIVED,
            agent_id=AGENT_ID,
            objective_id=scenario.objective_id,
            action="user_message",
            target_resource="user",
            raw_payload_text=scenario.objective,
            result_status="ok",
            external_resource="local://user",
            metadata={"sender": "user", "trusted": True},
        )
    )
    bus.emit(
        Observation(
            event_type=EventType.OBJECTIVE_DECLARED,
            agent_id=AGENT_ID,
            objective_id=scenario.objective_id,
            action="objective_declared",
            raw_payload_text=scenario.objective,
            result_status="ok",
            metadata={
                "objective": scenario.objective,
                "required_capabilities": list(scenario.required_capabilities),
            },
        )
    )
    bus.emit(
        Observation(
            event_type=EventType.TOOL_CATALOG_EXPOSED,
            agent_id=AGENT_ID,
            objective_id=scenario.objective_id,
            action="tool_catalog_exposed",
            result_status="ok",
            metadata={
                "tools": [
                    {"name": spec.name, "category": spec.category, "privilege": spec.privilege}
                    for spec in gateway.catalog()
                ]
            },
        )
    )

    agent_result = run_agent(
        gateway=gateway,
        adapter=adapter,
        objective=scenario.objective,
        objective_id=scenario.objective_id,
        agent_id=AGENT_ID,
    )

    if agent_result.answer:
        bus.emit(
            Observation(
                event_type=EventType.SELF_REPORT,
                agent_id=AGENT_ID,
                objective_id=scenario.objective_id,
                action="final_answer",
                result_status="ok",
                self_report=agent_result.answer,
                metadata={"note": "stored as an unverified self report, never as ground truth"},
            )
        )

    environment_after = environment.snapshot()
    bus.emit(
        Observation(
            event_type=EventType.RUN_COMPLETED,
            agent_id=AGENT_ID,
            objective_id=scenario.objective_id,
            action="run_completed",
            result_status="ok",
            permissions_before=gateway.permissions,
            permissions_after=gateway.permissions,
            metadata={"steps": agent_result.steps},
        )
    )

    chain_digests = bus.seal()
    output = RunOutput(
        run_id=run_id,
        scenario=scenario,
        config=config,
        run_dir=run_dir,
        baseline_path=baseline_path,
        provenance_path=provenance_path,
        agent_result=agent_result,
        environment_before=environment_before,
        environment_after=environment_after,
        chain_digests=chain_digests,
        adapter_descriptor=adapter.descriptor,
        clock_mode=clock.mode,
        event_counts={
            "baseline": baseline_sink.count,
            "provenance": provenance_sink.count,
        },
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(output.manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output


__all__ = ["RunConfig", "RunOutput", "execute_run", "AGENT_ID"]
