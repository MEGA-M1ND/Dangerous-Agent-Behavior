# THESIS — Experiment 001

## Motivation

When an autonomous agent takes a harmful action, the first question is *how did
it get there?* The usual answer is to read the agent's logs and, increasingly, to
read the model's reasoning trace. Both are weak foundations.

Conventional agent logs are a record of *calls*, not of *information*. They say
which tool ran with which arguments, but they do not say which earlier piece of
retrieved content was in the input state when those arguments were chosen, which
credential the redacted `token: ***` actually was, or when the agent's capability
set grew. Sanitization, which is necessary, destroys exactly the join keys an
investigator needs.

Reasoning traces are worse as evidence, for a different reason: they are produced
by the system under investigation. An agent that has been manipulated by injected
content will narrate a plausible story about why it did what it did. A model
whose trace is optimised against will produce traces that look good. Treating
either as ground truth means trusting the subject of the investigation.

This experiment asks whether an *independent observer*, positioned outside the
agent's decision logic and recording only observable relationships, can
reconstruct the trajectory better than conventional logs — without needing the
agent's account of itself at all.

## Hypotheses

**H1.** Provenance-aware telemetry — an independent record of the relationships
among objective, retrieved content, memory, messages, tool availability, tool
invocation, permissions, credential references, and resulting environment changes
— enables substantially better reconstruction of the sequence and data flow
leading to a dangerous action than conventional agent logs of the same run.

**H0.** Provenance-aware telemetry provides no meaningful reconstruction
advantage over conventional agent logs of the same run.

A null or negative result is a valid outcome and is reported as such.

## Falsification criteria

These are pre-registered and are applied mechanically by
`experiment/evaluation/verdict.py`. They are not adjusted after seeing results.

For a scenario that contains ground-truth data-flow edges:

1. **H1 is supported** when the provenance condition recovers strictly more
   ground-truth data-flow edges *on OBSERVED evidence* than the baseline, **and**
   the set of detection rules it fires is a superset of the baseline's.
2. **H1 is not supported** when the provenance condition recovers no more
   ground-truth data-flow edges on observed evidence than the baseline.
3. Anything else is **inconclusive** — for example, more edges recovered but a
   detection rule lost.

Additional pre-registered conditions:

4. **Edge precision is a separate cost.** It is reported alongside the verdict
   and never folded into it, so a recall gain cannot conceal a precision
   regression. If the provenance condition over-claims relationships, that is a
   negative result about provenance telemetry and is stated as one.
5. **The truncation control.** The experiment sweeps the result-preview cap
   applied identically to both conditions. If the provenance advantage disappears
   at the largest cap — where the baseline log contains the same text the
   observer saw — then the advantage at the default cap is attributable to log
   truncation, not to relational telemetry, and the **strong form of H1 is not
   supported**.
6. **Control scenarios carry no verdict.** The benign and safe-alternative runs
   contain no ground-truth data-flow edges; they measure false-positive
   behaviour instead. A condition that raises warnings there is worse, not
   better.

## What this experiment deliberately does not do

- It does not log, request, or reason about the model's private chain of
  thought. The provenance observer has no access to it and does not want it.
- It does not treat any agent-emitted explanation as evidence. Self reports are
  stored under `untrusted_self_report` and are excluded from graph construction,
  detection and scoring. A test asserts that no edge's evidence mentions them.
- It does not claim causation. An observed data-flow edge asserts that a string
  from an earlier source is identifiable in a later event. An inferred edge
  asserts only that the source was present in the observable input state. Neither
  asserts anything about why the model chose what it chose.
- It does not build a machine-learned detector. Four transparent heuristics,
  readable on one page, stand in for one.

## Assumptions

Each of these is a place the experiment could be wrong.

1. **Conventional logs do not record capability transitions.** We model the
   baseline as recording tool calls, arguments, results and application events,
   but not "the agent's permission set grew from X to Y". We believe this
   reflects common practice. If a deployment does record capability transitions,
   one ground-truth step and detection rule R3 move to the baseline's side.
2. **Sanitization destroys credential identity in conventional logs.** The
   baseline logs `token: ***REDACTED***`; the provenance stream carries
   `cred://demo_cloud_token#<hash>` in a dedicated field. Both hide the value;
   only the second preserves identity. A deployment that logs stable credential
   *references* has, in effect, adopted part of the provenance condition.
3. **Result previews are truncated in practice.** The default cap is 512
   characters, applied identically to both conditions. Criterion 5 above exists
   because this assumption carries a lot of weight.
4. **The declared minimum capability set is a legitimate input.** It is a
   least-privilege statement written by the operator with the task, carried in
   the `objective_declared` event, and visible identically to both conditions.
5. **Tool-catalog metadata (category, privilege, whether a tool returns untrusted
   content) is shared static configuration**, available to any analyst in either
   condition. It is not smuggled telemetry.
6. **A scripted policy is an acceptable stand-in for a model** *for the purpose
   of asking what telemetry affords*. See the limitations below.

## Limitations

**The agent is simulated, and that is the biggest limitation.** The deterministic
policies are scripted. They react to retrieved content — the unsafe policy parses
the credential name, tool and account name out of whatever instruction span it
finds, rather than replaying a fixed list — but they are not a model, and they do
not have a model's failure modes. In particular the policy *copies identifiers
verbatim* from the document into its tool arguments. That is what makes several
edges observable by string matching in the first place. A real model that
paraphrased would weaken verbatim matching, symmetrically, in both conditions.
Results here speak to **what the telemetry affords**, not to how agents behave.

Others:

- **n = 3 scenarios, one run each.** No statistical claim is made or possible.
  Every number in RESULTS.md is a single measurement.
- **One injection style, one dangerous action.** A single imperative span in a
  single retrieved document leading to a single admin call.
- **Ground truth is authored by the same people who built the observer.** It is
  written from the scenario design rather than from reconstruction output, and a
  test asserts that provenance, but this is not independent adjudication.
- **The ground-truth vocabulary is data-flow shaped**, which structurally favours
  a data-flow observer. This is stated again in EXPERIMENT.md as the strongest
  threat to validity.
- **Single agent, single runtime, no adversary against the observer.** The
  observer is assumed honest and untampered. See NEXT_EXPERIMENTS.md.
- **The capability-proportionality metric is not validated.** It is labelled
  EXPERIMENTAL in code and in every artifact that reports it.

## How to disagree with this experiment

Run it. Then change the thing you doubt: raise `--preview-cap` to 4096 and see
whether the gap closes; write a stronger baseline reconstructor; replace the
scripted policy with `--mode llm`; rewrite the ground-truth manifests in a
vocabulary you prefer. The pieces are separated so that each of those is a small
change, and the verdict rule will report the new answer without being asked to
be kind.
