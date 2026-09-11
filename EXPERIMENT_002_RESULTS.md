# Experiment 002 - results

Generated 2026-09-11 by `python -m experiment2 report`.

Conditions are named A (conventional logging) and B (conventional logging plus recorded relationships) in this document. Participants never saw either name.

## Status

- human investigator responses collected: 0
- model investigator responses collected: 0
- mock pipeline responses (not evidence): 48

### Pilot preparation

- participants enrolled: 4 (P1, P2, P3, P4)
- assignment: counterbalanced, between-subject within a case
- observations per condition once complete: baseline: 12, provenance: 12
- every case scheduled in both conditions: yes
- responses expected: 24; collected: 0; outstanding: 24

**Human investigator results pending.** No human responses have been collected. See HUMAN_STUDY_GUIDE.md to run the pilot.

**LLM investigator results not executed.** No model provider was configured when this document was generated. See LLM_INVESTIGATOR.md.

No study results are reported below, because there are none. The sections that follow describe what was measured about the *packages* themselves, which does not depend on any investigator.

## Evidence volume (measured, independent of any investigator)

Recorded so that "the structure helped" can be told apart from "there was simply more to read". These are averages per package.

| measure | condition A | condition B | B / A |
| --- | --- | --- | --- |
| record_count | 54.7 | 61.8 | 1.13 |
| link_record_count | 0.0 | 34.3 | n/a |
| readable_characters | 22250.8 | 40580.2 | 1.824 |
| readable_lines | 803.0 | 1102.5 | 1.373 |
| readable_estimated_tokens | 5562.7 | 10145.0 | 1.824 |
| estimated_reading_minutes_at_200_wpm | 16.9 | 27.1 | 1.604 |

This difference is not a defect to be corrected by trimming one condition. Recording relationships *is* recording more. It does mean that any accuracy difference has two candidate explanations, and this experiment cannot separate them on its own. See EXPERIMENT_002_VALIDITY.md.

## Pipeline check (not evidence)

Deterministic mock investigators were run over every package to verify that the rubric is satisfiable and that the workflow end-to-end works. These are fixtures. They are not investigators, they are not evidence, and they are stored in a separate namespace so they cannot leak into the tables above.

| profile | mean score, condition A | mean score, condition B |
| --- | --- | --- |
| keyword_scanner | 10.667 | 10.667 |
| manifest_oracle | 12.0 | 12.0 |
| naive_accuser | 4.167 | 4.167 |
| uncertainty_aware | 11.167 | 11.167 |

Mock investigators are fixtures for testing the rubric and the workflow. They are not investigators and these numbers are not experimental evidence.

Every fixture scores identically in both conditions. That is a fact about the fixtures, not about people: these profiles read only fields that both conditions contain, so by construction they cannot benefit from the recorded links. It does establish one thing about the packages, though - a mechanical reader can reach the correct answer on these cases from the conventional condition alone, so the conventional packages are not information-starved.

## What would change our mind

The pre-registered list is in EXPERIMENT_002_PREREGISTRATION.md and is reproduced here unchanged:

1. The gap tracks reading volume rather than structure.
2. Investigators can tell which condition they are in.
3. The rubric's alias lists miss correct paraphrases.
4. The cases are too easy and the conventional condition hits the ceiling.

