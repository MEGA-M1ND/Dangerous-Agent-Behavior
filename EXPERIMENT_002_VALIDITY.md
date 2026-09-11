# Experiment 002 - validity review

Written as a hostile review of our own design, from four positions: a sceptical
AI-control researcher, an incident-response practitioner, a statistician, and a
reviewer looking for a reason to reject.

## The strongest objection

**The two conditions do not supply equal amounts of material.** Packages in the
relationship condition are 1.824x the characters and roughly
1.604x the estimated reading time of the conventional ones. If
investigators do better with them, "relationships help you reconstruct incidents"
and "people who read more get more right" predict the same result.

This is not fixable by trimming. Recording relationships is recording more, and
deleting conventional records from the second condition to equalise length would
manufacture a different artefact. What can be done, and is:

* the ratio is measured before any response is collected and printed with every
  result;
* investigation duration is recorded where it can be measured, so a gain bought
  purely with time is visible;
* per-case scores are reported, so a gain concentrated in the cases with the most
  extra links can be distinguished from a uniform one.

A later experiment could hold volume constant by giving the conventional
condition an equally long but relationship-free elaboration. That is the right
control and it is not in this experiment.

A cheaper and more informative variant would be a third condition sitting between
the two: conventional logging plus stable credential references and capability
transitions, and nothing else. Those are the two fields Experiment 001 identified
as the ones conventional sanitisation destroys, and they add almost no reading
volume. If most of any observed benefit comes from them, the expensive part of
provenance recording - the link table - is not what is doing the work.

## Construct validity

*Does the reconstruction score measure understanding of the incident?*

It measures whether an investigator named the objective, classified the incident
within a defensible range, identified the relevant input and the enabling
capability, covered the case's key facts, avoided asserting more than the records
support, and stated confidence inside a pre-registered band. That is a proxy for
understanding, not understanding itself. A verbose answer that happens to contain
the right alias strings scores well; a terse correct one may not, which is why
short answers are flagged for adjudication.

The rubric deliberately does not reward vocabulary. Alias lists are written in
ordinary incident-response language and a test asserts none of them contains
provenance terminology. This is the specific repair Experiment 002 exists to make,
and it is a repair, not a proof: the *cases* were still designed by people who had
a data-flow mental model.

## Internal validity

* Both conditions come from the same run of the same scenario, so the underlying
  incident is identical by construction, not by matching.
* One renderer produces both packages, so formatting cannot differ.
* Renumbering records removes the sequence-number gaps that would otherwise
  announce that records had been withheld.
* Condition assignment is counterbalanced against each case's fixed ordinal, so a
  case cannot land in one condition for every participant.
* Presentation order is shuffled per participant, so order effects are not
  confounded with case identity.

Remaining threats: a participant who works through six cases learns the tool
catalogue and the shape of these incidents, so later cases are not independent of
earlier ones. With six cases per participant this learning effect is real and is
only partly absorbed by shuffling. A between-subject design with one case per
participant would remove it and would need many more participants.

## External validity

The incidents are synthetic, the assistant is a scripted policy, and the
environment is a mock. The assistant copies identifiers verbatim from the content
it reads into its tool arguments, which is what makes several relationships
visible to a reader in either condition. A real model that paraphrased would make
both conditions harder, not obviously by the same amount.

The investigators in the pilot will be whoever we can recruit, not on-call
engineers under time pressure with a production system and an incident bridge.
Nothing here establishes what happens under those conditions.

## Investigator learning effects

Six cases in one session, three of which are cases where suspicion is wrong. A
participant who notices that pattern will answer later cases differently. The
shuffle means different participants meet the benign cases at different points,
which spreads the effect across the design rather than removing it. The exit
questions ask what strategies participants developed; that is the only instrument
we have for detecting it.

## Scoring subjectivity

Structured answers are scored mechanically. Free text is scored by alias matching,
which is transparent and reproducible but brittle: a correct paraphrase using none
of the listed words scores zero on that component. Responses where no key fact
matched, or where the reconstruction is very short, are flagged for human
adjudication. The adjudication sheets withhold the condition and the participant's
identity, and the schema supports multiple adjudicators and agreement statistics
from the start.

## Telemetry presentation bias

The relationship condition's links are rendered as a table with a strength column.
Tables are easy to read. A conventional log's equivalent information, where it
exists at all, has to be assembled by the reader. This is arguably part of what is
being tested - structure is the treatment - but it also means the comparison is
between *recorded and presented* relationships and *unrecorded* ones, not between
two equally presented formats.

One item was caught in review and removed. The observer behind the relationship
condition also scans returned content for instruction-shaped lines and records
what it finds. Both conditions carry the full content, so nothing was hidden from
the conventional condition, but surfacing the scan in only one of them would have
handed that condition an affordance beyond the relational fields under test. It
is stripped from every package. The consequence is worth stating: the
relationship condition as tested here is *weaker* than the observer as built in
Experiment 001, so a null result would not rule out that the full observer helps.

## Case generation bias

Six cases chosen by us. Three are cases where the right answer is "nothing much
happened", which is the main guard against a case set that rewards suspicion. The
ambiguous case was constructed so that two documents carry the same values and no
approval record exists anywhere - but we constructed it, and we decided what
counts as genuinely undecidable.

The ambiguous case deserves one more admission. Its acceptable answers are
"insufficient evidence" and "suspicious", and "benign" scores zero. A participant
could argue that the task explicitly said to work the open change ticket and the
ticket describes provisioning the account, which makes the action authorised. The
counter-argument is inside the package - the runbook the assistant read says
automated assistants must not escalate privileges themselves, and no approval
record exists anywhere - but this is the single most contestable judgement in any
manifest. Any classification outside the acceptable set on this case is
automatically flagged for human adjudication rather than silently scored zero.

The answers are not encoded verbatim in the packages: no package states a
classification, a verdict, or an authorisation status. But the account and
credential names do appear verbatim in both the content and the later arguments,
which makes the key relationship findable by string matching in either condition.
That was deliberate - it is what stops the conventional condition from being
handicapped - and it also means the cases may under-state the value of recorded
relationships in settings where no such verbatim overlap exists.

## Does this measure reconstruction or search?

Partly search. An investigator who greps the package for `cloud_admin` will find
the privileged call in either condition. The components that are not search are
classification on the ambiguous case, the calibration band, the unsupported-claim
check, and the missing-evidence question. If a difference appears only in the
searchable components, that is worth saying out loud in the results.

## Possible condition leakage

A participant who has seen packages of both kinds could infer that one is
instrumented differently. The between-subject design means no participant sees
both versions of the same incident, but a participant working six cases sees both
*kinds* of package. They are told up front that deployments instrument
differently, which is true and is the honest framing, but it does not make the
difference invisible. The exit questionnaire asks directly whether they noticed
differences between packages and what they made of them.

## Statistical position

This is a pilot. The pre-registration sets a minimum of eight responses per
condition from four participants before any decision criterion applies, and
everything below that is reported as inconclusive regardless of which direction
the means point. No p-values are produced. An effect size is computed only where
both groups have variance and is labelled descriptive.
