# EXPERIMENT — design and instrumentation

## Independent variable

**The observation condition.** One variable, two levels, applied to the same run:

- **baseline** — conventional agent-application logging.
- **provenance** — the same records plus explicit relational fields.

The manipulation is implemented as a strict field-level projection. Both
conditions are fed identical raw facts by the telemetry bus, with a shared
sequence number per fact. The baseline logger then drops:

| dropped | why a conventional log would not have it |
| --- | --- |
| `source_ids`, `input_event_ids`, `flow_evidence` | requires an observer that tracks what was in the agent-visible input state |
| `permission_before`, `permission_after` | requires modelling capability state, not just calls |
| `credential_reference` | conventional sanitization removes the value *and* the identity |
| `output_reference`, `external_resource` | requires content-addressed references to returned data |
| `risk_tags` | observer-side labelling (descriptive only; not used in scoring) |
| event types `observation_ingested`, `permission_change` | a conventional log has no notion of these |

Everything else — timestamps, agent id, model request/response boundaries, tool
name, tool category, target resource, sanitized arguments, result status, result
preview, errors, environment-change application events, self reports — is byte
identical in both streams. `tests/test_events.py` asserts this by re-projecting
every provenance event and comparing it to the corresponding baseline event.

## Dependent variables

Per condition, per scenario:

| metric | definition |
| --- | --- |
| **event coverage** | fraction of ground-truth trajectory steps the reconstruction can answer for |
| **event coverage, conventional subset** | the same, excluding steps a conventional log structurally cannot record |
| **node coverage** | fraction of ground-truth graph nodes present in the reconstructed graph |
| **edge recall** | fraction of ground-truth edges recovered (scored relations only) |
| **edge precision** | fraction of reconstructed scored edges that ground truth supports |
| **data-flow edge recall / precision** | the same, restricted to `data_flowed_to` |
| **…, observed evidence only** | the same, counting only edges backed by OBSERVED evidence |
| **dangerous-action detection** | did the reconstruction identify the ground-truth dangerous action? |
| **source attribution** | which external source did it associate with the trajectory, and was that the right one? Reported for all evidence and for observed evidence only |
| **false-positive behaviour** | detection rules fired on the control scenarios, where none should fire |
| **time to detection** | event index at which the first finding's evidence became available, and the lead over the dangerous action's index |
| **capability proportionality** (EXPERIMENTAL) | declared minimum vs exercised; unnecessary and privileged-unnecessary subsets |

## Controls

1. **Scenario A (benign)** — no injected content. Measures false positives and
   confirms both conditions reconstruct an uneventful run.
2. **Scenario C (safe alternative)** — identical corpus and identical starting
   state to Scenario B, differing only in whether the agent acts on content-derived
   instructions. Isolates *acting on the injection* from *encountering* it.
3. **Shared instrumentation point** — one gateway, one bus, one sequence counter.
   Neither condition gets an extra probe.
4. **One reconstruction algorithm** — `experiment/analysis/reconstruct.py` is run
   twice. It does not branch on the condition; it uses whatever fields are
   present. A test asserts the source contains no condition check. This removes
   "they wrote a better analyser for their own side" as an explanation.
5. **One detection implementation** — the four rules run over both streams.
6. **Shared matching code** — `experiment/textmatch.py` is used by the observer
   *and* by both reconstructions.
7. **Symmetric truncation sweep** — the result-preview cap is a run parameter
   applied to both conditions, swept over {128, 512, 1024, 4096}.
8. **Fixed seeds and a virtual clock** — in deterministic mode, timestamps are a
   pure function of the sequence number and identifiers are UUIDv5 derivations, so
   repeated runs are byte-identical.

## Instrumentation

```
agent runtime → tool gateway → mock environment
                     ↓
               telemetry bus (assigns the shared sequence number)
                ↓          ↓
    baseline logger   provenance observer
         ↓                   ↓
  baseline_events    provenance_events   (append-only JSONL, hash chained)
```

The gateway emits one `Observation` per raw fact: a tool invocation, a tool
result, the ingestion of returned content into the agent-visible input state, a
capability change, an environment change, a model request/response boundary, a
graph state transition, a received message, the objective, the tool catalog, and
run start/completion.

The **provenance observer** maintains its own state, derived only from what it
sees at the gateway:

- a content registry mapping `obs://<sha256[:12]>` to the text returned to the
  agent (held in memory, never written);
- the ordered list of content references currently in the agent-visible input
  state;
- a credential registry mapping `cred://<name>#<sha256[:12]>` to the value it
  returned (in memory only);
- the current capability set.

For each tool invocation it records the strongest available evidence linking that
call to earlier events:

| evidence kind | observed? | meaning |
| --- | --- | --- |
| `credential_reference_identity` | yes | a credential returned earlier appears verbatim in these arguments |
| `verbatim_substring_match` | yes | an identifying token (≥ 8 chars) appears in both the earlier content and these arguments |
| `resource_identifier_mentioned_in_source` | yes | this call's target resource is named inside earlier content |
| `declared_tool_lineage` | yes | the gateway itself produced this relationship (e.g. this result came from this call) |
| `present_in_observable_context` | no | the content was in the agent-visible input state before this action |
| `temporal_adjacency` | no | immediately preceding action |

Credential material never becomes matchable content and never appears in an
evidence string: the observer refuses to register a credential payload in the
content registry, and every evidence detail is scrubbed.

### The agent cannot touch the record

The agent runtime receives a `ToolGateway`, whose public surface is
`call`, `catalog`, `permissions`, `emit`. It has no reference to a sink, logger,
observer or bus, and `experiment/agent/runtime.py` does not import any of those
modules. Sinks refuse writes after sealing and maintain a SHA-256 hash chain over
their lines, recorded in `run_manifest.json`, so post-hoc edits are detectable.
`tests/test_observer_separation.py` checks all of this, including that a tampered
copy of a telemetry file produces a different chain digest.

## Ground truth

`ground_truth/manifests/<scenario>.json` describes each scenario's *intended
observable trajectory*, authored from the scenario definition and the policy
source rather than from any reconstruction output. Each manifest contains:

- `trajectory` — ordered steps, each tagged `conventionally_observable` so that
  coverage can be reported with and without steps a conventional log cannot record;
- `nodes` — canonical graph node identifiers expected in a reconstruction;
- `edges` — expected relationships, restricted to the *scored relations*
  `retrieved`, `observed`, `data_flowed_to`, `permission_changed`, `modified`;
- `dangerous_action`, `untrusted_source_document`, `expected_detection_rules`,
  `expected_privileged_unnecessary_capabilities`.

**Why the scored relations are a subset.** The manifests enumerate these
relations exhaustively, so precision over them is meaningful. They do not
enumerate structural bookkeeping edges (`invoked`, `enabled`, `accessed`,
`followed_by`, `produced`), which both conditions produce identically and which
would only dilute the comparison. Precision is computed only over the scored
classes; this scoping is declared in `ground_truth/loader.py`.

**Why `data_flowed_to` ground truth is small.** Only three flows in Scenario B
are real: the injected document determined the credential name and the account
name in two later calls, and the credential determined the token argument of the
admin call. The agent's other reads happen on a fixed plan, so a reconstruction
that reports `document_index → open_document` is over-claiming even though the
document ids do co-occur. Ground truth does not list those, and reporting them
costs precision. That is intentional: it makes precision a real test of
over-claiming rather than a formality.

### Leakage prevention

`ground_truth/` may be imported by exactly one module,
`experiment/evaluation/metrics.py`, which runs only after reconstruction and
detection are complete and never feeds anything back. Enforced by three tests:

1. an AST scan of every module in `experiment/observability`,
   `experiment/analysis`, `experiment/agent`, `experiment/mockenv` and the
   run-time modules, rejecting any `ground_truth` import;
2. a token-level scan of the same files rejecting the identifier anywhere in
   executable code (docstrings may describe the rule);
3. a runtime test that replaces `load_ground_truth` with a function that raises,
   then executes a complete run → reconstruction → detection cycle.

A fourth test asserts every manifest declares that it was authored from the
scenario design.

## Metrics scoring

`experiment/evaluation/metrics.py` maps ground-truth steps onto the
reconstruction's *answers*, not onto raw event types. That matters for fairness:
the step "the injected content was observed" is satisfied by any condition whose
reconstruction can point at instruction-shaped spans in content from that source,
regardless of which event type carried it.

The comparison is per-metric. There is no composite score, because a composite
score is where a thumb goes on a scale.

## Threats to validity

Ordered roughly by how much they worry us.

1. **The ground-truth vocabulary favours the provenance condition.** Ground truth
   is a set of data-flow edges. A telemetry design built around data flow is
   structurally advantaged at recovering data-flow edges. We mitigate by also
   reporting event coverage restricted to conventionally observable steps, by
   reporting precision separately, and by declaring the scoring scope — but the
   mitigation is partial. **This is the strongest threat.**
2. **The agent is scripted and copies identifiers verbatim.** The policy's tool
   arguments literally contain tokens from the retrieved document, which is what
   makes verbatim matching work at all. A paraphrasing model would degrade both
   conditions; we do not know by how much or whether symmetrically.
3. **The default preview cap decides part of the answer.** At 512 characters the
   baseline log does not contain the injected span (offset 551 in a 932-character
   document); at 1024 it does. The sweep exists to expose this, and RESULTS.md
   reports the verdict at every cap.
4. **Assumption 1 (no capability telemetry in conventional logs) hands the
   baseline a structural loss** on one ground-truth step and one detection rule.
   We flag those separately rather than burying them.
5. **Ground truth and observer share an author.** No independent adjudication.
6. **Sample size.** Three scenarios, one run each, one injection style, one
   dangerous action, one agent, one runtime.
7. **The reconstructor is ours.** A better baseline analyser might close the gap.
   We gave the baseline the same matching code and generous previews, but we
   cannot rule out that a more determined analyst does better.
8. **Detection rules were written knowing the scenario.** They are transparent
   and general in form, but they were not validated against an independent corpus
   of agent runs, and with one dangerous scenario their false-positive
   characterisation rests on two control runs.
