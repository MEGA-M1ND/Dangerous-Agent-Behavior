# NEXT_EXPERIMENTS — not implemented

A record of what Experiment 001 deliberately left out. Nothing here is built.
Each entry names the question, not the product.

## 002 — Multi-agent information propagation

Does an injected span retain attributable provenance after it crosses agent
boundaries? Spawn a sub-agent, pass retrieved content through a message, and ask
whether the observer can still attribute a privileged action by the child to a
document retrieved by the parent. The event schema already carries
`parent_agent_id`, `spawned`, `communicated_with` and `received_from`; none of
them are exercised by Experiment 001.

## 003 — Tool-use proportionality across many tasks

Experiment 001's capability metric compares one declared minimum against one
exercised set, and is labelled experimental for good reason. The open question is
whether agents systematically reach for higher-capability tools than a task needs
when both are available, and whether that tendency is measurable across a corpus
of tasks rather than asserted from a single trajectory.

## 004 — Counterfactual safer-path replay

Given the telemetry of an unsafe run, can the observer construct the
lowest-capability alternative trajectory that would have satisfied the objective,
and replay it against the same mock environment? Scenario C is that path written
by hand; the experiment is whether it can be derived.

## 005 — Behavioural provenance without content matching

Experiment 001 leans on verbatim token overlap between retrieved content and
later arguments. That works because the scripted policy copies identifiers. Can
information flow be evidenced when the agent paraphrases — for example from
timing, tool-selection shifts, or argument-distribution changes — and with what
false-positive rate?

## 006 — Agent-to-agent coordination

Two or more agents with separate objectives and a shared mock environment. Does
the trajectory leading to a dangerous action remain reconstructible when no
single agent's log contains it, and what does an observer need to record at the
boundary between them?

## 007 — Observer tampering and adversarial pressure

Experiment 001 assumes an honest, untampered observer; the hash chain only
detects edits after the fact. What happens when the agent can influence the
observer — flooding it with content references to destroy precision, crafting
content that collides with the matching heuristics, or acting to make the
capability transition unobservable?

## 008 — Memory poisoning

Write injected content into agent memory in one run and have a later run read it
back. Provenance across runs is a different problem from provenance within a run:
the content reference must survive persistence, and the observer must relate a
memory read to a write it may not have observed.

## 009 — Cross-runtime observation

The observer here sits inside the same process as the gateway. Does the same
reconstruction hold when telemetry is collected at a process or network boundary
— for example as OpenTelemetry spans — where ordering is approximate, some events
are lost, and the observer cannot see full payloads?

## 010 — Human-adjudicated reconstruction quality

Replace graph-edge scoring with a task: give investigators a telemetry stream and
a fixed question list, and measure how often they answer correctly and how long
it takes. This directly attacks threat-to-validity #1 in EXPERIMENT.md — that the
ground-truth vocabulary is itself data-flow shaped and therefore favours the
condition under test.
