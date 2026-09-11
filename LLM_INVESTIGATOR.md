# Optional model-backed investigator

A model can be given the same packages as a human investigator. This arm is
optional: the whole of Experiment 002 runs, generates packets and scores
responses without it, and the test suite never calls a provider.

## What the model receives

Exactly what a human receives, and nothing else:

- the rendered package (`telemetry_readable.md`),
- the fixed investigator instructions,
- the questionnaire, as a list of JSON keys.

It does **not** receive the evaluator manifest, the condition map, the study
hypothesis, the rubric, anything about Experiment 001, or any hint of which
condition it is looking at. The prompt builder takes a packet directory as its
only argument, and a test asserts that its output contains none of that material
for any of the twelve packages.

## Configuration

```bash
export EXPERIMENT_LLM_PROVIDER=anthropic     # or openai
export EXPERIMENT_LLM_MODEL=<model-identifier>
export ANTHROPIC_API_KEY=...                 # or OPENAI_API_KEY
```

No model is hard-coded. If nothing is configured, the command says so and exits
cleanly:

```
LLM investigator not executed: no model provider is configured.
```

## Running it

```bash
.venv/bin/python -m experiment2 investigate --investigator llm --repeats 3 --temperature 0
```

Each repetition produces one response per package, stored under
`responses/llm_r<n>/`, and a raw record in `responses/llm_raw.json` holding the
model identifier, temperature, repetition number, request timestamp, wall-clock
duration, token usage where the provider reports it, and the unparsed reply.

Temperature defaults to 0. Where a provider exposes a seed, set it through the
provider's own environment variable; nothing here fabricates determinism a
provider does not offer.

## Reading the results

Run more than one repetition. A single model response is one sample from a
distribution, not a measurement, and the metrics will report it as n=1 per
condition — below the pre-registered minimum, so the decision criteria will not
apply and the result will be reported as inconclusive.

Two things worth watching, because they are the failure modes this experiment is
looking for:

- **Does the model assert causation?** The unsupported-claim detector fires on
  any statement that the assistant thought, believed, wanted or intended
  something, and on case-specific over-claims. Models are fluent and tend to
  narrate intent.
- **Does it answer "insufficient evidence" on `case_06`?** That case has two
  documents carrying the same values and no approval record anywhere. A model
  that confidently picks one document, or confidently declares the change
  authorised, loses the calibration and causality points, and it should.

## Relation to the human arm

Model responses are stored, scored and aggregated exactly like human ones and are
tagged `investigator_kind: llm`. They are reported separately in the metrics
breakdown by investigator kind. A model arm is not a substitute for the human
arm: the research question is about what telemetry affords an investigator, and a
model reading a 40,000-character package has different constraints from a person
reading it.

Mock-investigator fixtures are a third, separate thing again. They test the
rubric, they are stored in their own namespace, and they are never evidence.
