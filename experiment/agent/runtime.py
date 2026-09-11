"""LangGraph agent runtime.

The graph is deliberately small: decide -> act -> (loop) -> end. Its only job is
to give the experiment a real orchestration loop with observable state
transitions, so that the telemetry is produced by an agent runtime rather than by
a straight-line script.

The runtime holds a :class:`~experiment.gateway.ToolGateway` and nothing else. It
has no reference to any sink, logger or observer, and therefore cannot read or
alter the observational record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from experiment.agent.adapters import AgentAction, AgentView, ModelAdapter
from experiment.events import EventType
from experiment.gateway import ToolGateway
from experiment.observability.bus import Observation

MAX_STEPS = 16


class AgentState(TypedDict, total=False):
    objective: str
    objective_id: str
    step: int
    done: bool
    answer: str
    action: dict[str, Any]
    observations: list[str]


@dataclass
class AgentResult:
    answer: str
    steps: int
    exercised_capabilities: list[str]
    final_permissions: tuple[str, ...]


def run_agent(
    gateway: ToolGateway,
    adapter: ModelAdapter,
    objective: str,
    objective_id: str,
    agent_id: str,
    max_steps: int = MAX_STEPS,
) -> AgentResult:
    catalog = gateway.catalog()

    def _step_event(name: str, state: AgentState) -> None:
        gateway.emit(
            Observation(
                event_type=EventType.AGENT_STEP,
                agent_id=agent_id,
                objective_id=objective_id,
                action=f"graph_node:{name}",
                result_status="ok",
                metadata={"step": state.get("step", 0)},
            )
        )

    def decide(state: AgentState) -> AgentState:
        _step_event("decide", state)
        view = AgentView(
            objective=state["objective"],
            step=state.get("step", 0),
            observations=list(state.get("observations", [])),
            tools=catalog,
        )
        gateway.emit(
            Observation(
                event_type=EventType.MODEL_REQUEST,
                agent_id=agent_id,
                objective_id=objective_id,
                action="model_request",
                result_status="n/a",
                metadata={
                    "adapter": adapter.descriptor,
                    "tools_offered": len(catalog),
                    "observations_in_context": len(view.observations),
                    "step": view.step,
                },
            )
        )
        action = adapter.decide(view)
        gateway.emit(
            Observation(
                event_type=EventType.MODEL_RESPONSE,
                agent_id=agent_id,
                objective_id=objective_id,
                action=f"chose:{action.kind}",
                tool_name=action.tool_name,
                raw_arguments=dict(action.arguments),
                result_status="ok",
                self_report=action.self_report,
                metadata={"adapter": adapter.descriptor},
            )
        )
        return {"action": _action_to_dict(action)}

    def act(state: AgentState) -> AgentState:
        _step_event("act", state)
        action = _action_from_dict(state["action"])
        step = state.get("step", 0) + 1
        if action.kind != "tool" or not action.tool_name:
            return {"done": True, "answer": action.answer or "", "step": step}

        response = gateway.call(
            action.tool_name,
            action.arguments,
            objective_id=objective_id,
            self_report=action.self_report,
        )
        text = response.as_text()
        adapter.ingest(action.tool_name, action.arguments, text, response.ok)
        observations = list(state.get("observations", []))
        observations.append(f"{action.tool_name}: {text}")
        return {"step": step, "observations": observations, "done": False}

    def should_continue(state: AgentState) -> str:
        if state.get("done") or state.get("step", 0) >= max_steps:
            return "stop"
        return "continue"

    graph = StateGraph(AgentState)
    graph.add_node("decide", decide)
    graph.add_node("act", act)
    graph.add_edge(START, "decide")
    graph.add_edge("decide", "act")
    graph.add_conditional_edges("act", should_continue, {"continue": "decide", "stop": END})
    compiled = graph.compile()

    initial: AgentState = {
        "objective": objective,
        "objective_id": objective_id,
        "step": 0,
        "done": False,
        "answer": "",
        "observations": [],
    }
    final = compiled.invoke(initial, config={"recursion_limit": max_steps * 3 + 10})

    return AgentResult(
        answer=final.get("answer", ""),
        steps=final.get("step", 0),
        exercised_capabilities=list(gateway.exercised_capabilities),
        final_permissions=gateway.permissions,
    )


def _action_to_dict(action: AgentAction) -> dict[str, Any]:
    return {
        "kind": action.kind,
        "tool_name": action.tool_name,
        "arguments": action.arguments,
        "self_report": action.self_report,
        "answer": action.answer,
    }


def _action_from_dict(data: dict[str, Any]) -> AgentAction:
    return AgentAction(
        kind=data["kind"],
        tool_name=data.get("tool_name"),
        arguments=data.get("arguments") or {},
        self_report=data.get("self_report"),
        answer=data.get("answer"),
    )


__all__ = ["run_agent", "AgentResult", "MAX_STEPS"]
