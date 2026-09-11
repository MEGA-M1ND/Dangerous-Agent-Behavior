# Running the Experiment 002 pilot with human investigators

This is the manual part. The tooling generates packets, records timing, imports
answers and scores them; recruiting people and sitting with them is yours.

## Before you start

```bash
.venv/bin/python -m experiment2 preregister
.venv/bin/python -m experiment2 build --participants P1,P2,P3,P4
```

The first command writes `EXPERIMENT_002_PREREGISTRATION.md`. Do not skip it and
do not edit it after you have seen any results — the metrics command refuses to
run until it exists, which is the point.

The second creates, under `artifacts/experiment_002/`:

```
packets/<packet_id>/         the twelve packages, two per case
packets/<participant>/       one folder per participant, in their order
private/condition_map.json   which package is which condition  ← do not share
private/evaluator_manifests/ the answer key                    ← do not share
```

## Who to recruit

Four to six people for the first pilot. They need to be able to read a structured
log and reason about an automated system — software engineers, SREs, security
people. They must not have read this repository, and in particular must not have
read `EXPERIMENT_002.md`, the manifests, or Experiment 001's results.

If a participant has already seen one of these incidents in any form, exclude
their response for that case and record why.

## Setup for each participant

1. Give them **only** their own folder: `artifacts/experiment_002/packets/P1/`.
   Do not give them the `packets/` root, which contains both versions of every
   case.
2. Give them the briefing below. Nothing else.
3. Ask them to work the cases in the folder order, one at a time, without going
   back to revise an earlier case after reading a later one.

### Briefing to read out or paste

> You are reviewing telemetry packages from an automated-assistant deployment.
> Each package covers one task the assistant carried out. For each one, work out
> what happened and answer the questionnaire in the folder.
>
> Answer from the package alone. There is no penalty for answering that the
> evidence is insufficient, and there is a penalty for asserting more than the
> records support. Some of these packages describe incidents. Some do not.
>
> Packages come from different deployments, which instrument differently, so they
> do not all contain the same kinds of record. The absence of a kind of record is
> not itself evidence about what happened.
>
> Work at your own pace. Tell me when you open each case and when you have
> finished it.

Do not tell participants how many cases are incidents, that there are two kinds
of package, what is being compared, or anything about Experiment 001. If they ask
what the study is testing, say you will explain fully at the end, and do.

## Running a case

```bash
# when they open the case
.venv/bin/python -m experiment2 start --participant P1 --packet case_01_packet_JJ6N

# when they hand back a filled-in answers file
.venv/bin/python -m experiment2 submit --participant P1 --answers /path/to/answers.json
```

`start` is what makes timing meaningful. Without it the response is stored with
`timing_is_reliable: false` and is dropped from every timing summary — the study
would rather have no number than a made-up one.

Participants fill in a copy of `answers_template.json` from their case folder.
If they prefer paper or a document, transcribe into that template afterwards and
note in the participant log that timing came from a stopwatch rather than from
`start`.

## After each participant

Ask, and write down:

1. Did you notice differences between the packages? What did you make of them?
2. Did you develop a rule of thumb as you went? What was it?
3. Had you seen any of these incidents before?

Question 1 is the condition-leakage check and question 2 is the learning-effect
check. Store the answers in `artifacts/experiment_002/responses/<participant>/exit_notes.md`.

## Scoring

```bash
.venv/bin/python -m experiment2 metrics
.venv/bin/python -m experiment2 report
```

`metrics` scores every response, writes aggregate, per-case and per-participant
files, and produces anonymised adjudication sheets under
`adjudications/sheets/`. Each sheet hides the participant and the condition and
carries the rubric and the evaluator summary.

Review at least every response flagged in `needs_adjudication` — short answers,
and answers where no key fact matched, which are usually paraphrases the alias
lists missed. Copy `adjudications/score_entry_template.json`, fill it in, and save
it under `adjudications/scores/`. If a second adjudicator scores the same
responses, agreement statistics are computed automatically; one adjudicator is
fine for a first pilot and the tooling will say so rather than inventing a number.

## Keeping the study clean

- **Never** give a participant both versions of the same case.
- **Never** share `private/`. If a participant sees the condition map or a
  manifest, their remaining responses are void.
- Run participants separately, or at least out of earshot. Six cases with three
  benign answers is exactly the kind of thing people tell each other.
- If you change the cases, the rubric or the questionnaire after collecting any
  response, that is a new study. Say so; do not pool.

## What counts as done

A pilot is complete when you have at least eight responses per condition from at
least four participants. Below that, the pre-registered criteria do not apply and
the result is reported as inconclusive whichever way the means point.
