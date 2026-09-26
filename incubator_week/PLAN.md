# BlueDot Incubator Week v6: application plan

- **Program:** 5 days in San Francisco, **Nov 2–6, 2026**. All expenses paid. Up to $100k in grants if they back the Friday pitch.
- **Deadline:** **Oct 28, 2026.** Target submitting by **Oct 21**, a week early.
- **Days left (from Sep 26):** 32.
- **Questions to:** joshua@bluedot.org
- **Page:** https://bluedot.org/programs/incubator-week

## What they select for (from the page)

| they want | where this repo already shows it | gap |
| --- | --- | --- |
| "Technically serious" | Preregistered falsification criteria, a truncation control, a hostile validity review written about your own design, tests that enforce blinding | none. Lead with it |
| In or next to AI safety / cyber / catastrophic risk | Agent incident reconstruction after prompt injection leads to a privileged action | none |
| "Ready to leave whatever you're doing now to build" | not visible anywhere | **you have to say this plainly in the application** |
| No polished idea needed | You have more than an idea: working code and one result | the idea is still a research question, not an organisation. See the framing below |

The week runs threat model (Mon) → build and test interventions (Tue–Wed) → pitch prep (Thu) → pitch (Fri). Your repo already has a threat model and an intervention. That means you can spend the week on the parts you don't have yet: users, go-to-market, and a second intervention.

## "I have nothing much to show": what the alumni actually had

BlueDot's own video describes past participants this way: *"They came with one hard question standing between them and a new AI safety organization: a co-founder, a threat model, a first customer, or funding."* The bar is not a finished product. It's a clear, hard question and someone who's clearly serious about it.

Look at who's on the alumni list:

| alumnus | what they had | pattern |
| --- | --- | --- |
| Cecilia Tilli | an organisation idea (propensities for multi-agent deployment). Raised $480k *after* pitching on Friday | idea + credibility, product came later |
| Alex Csaky | a field to grow (AI for epistemics). Got an EIR offer | person first, org shape found afterwards |
| Jacob Arbeid | AISI background + one thesis (automated cyber evals) | domain credibility + one sharp bet |
| safely.bio | KYC for DNA synthesis orders: **one buyer, one decision** (ship or don't ship), "the evidence behind every verdict", under $1 per check | narrow wedge, auditable verdict |
| Exona Lab | insurers pricing AI risk | an existing buyer with an existing budget |
| 0Labs | adversarial agents that expose **detection gaps** | security teams already pay for this |

Two things stand out:
1. **About half of them came in with a person and a thesis, not a product.** You have more than that: working code, a preregistered result, and a self-critical write-up.
2. **The ones with products picked one buyer and one decision.** safely.bio doesn't sell "biosecurity". It sells "should we ship this order?", with the evidence attached. That's the move this project is missing. At the moment it answers a research question ("does provenance telemetry help reconstruction?"), not a buyer's question.

So you're half right. As a research repo, it's a weak pitch. The fix is to reframe it and build one demo, not to spend months on more experiments.

## Pick a wedge (recommended: #1)

Each option reuses code you've already written.

**1. Pre-action gate: "safely.bio for agent tool calls".** *(recommended)*
Before an agent runs a privileged tool call (fetch a secret, grant admin, send money, push code), the gateway checks provenance: did untrusted retrieved content flow into this call? It returns **allow / block / ask a human**, with the evidence attached. The buyer is a platform or security team deploying agents with real credentials. The decision is "let this call through?"
- Why it fits you: `gateway.py` already sits in front of every call, and rule R1 (`untrusted_content_to_privileged_action`) already exists. In the injected run, the first detection rule fired at event 29 and the admin action came at event 36. There was room to stop it. Both conditions detected something there, but only the provenance condition could name the document responsible. That's the "evidence behind every verdict" safely.bio sells.
- Demo you can build in about a week: run the injected scenario with the gate on. The admin user is never created, and the block message names `ops-runbook-demo` as the source. Then do the same against a real model in `--mode llm`.

**2. Forensic readiness assessment (0Labs-shaped, service first).**
Run your injection scenarios against a team's agent setup and report whether *their* logs could reconstruct what happened. This is basically Experiment 001 turned into a deliverable. It can be sold as a consulting engagement before any product exists.

**3. Agent incident evidence for insurers (Exona-shaped).**
Independent, tamper-evident incident records that underwriters and claims teams can rely on. It's a large market but a slow one to get into. Save it as the "where this goes" slide rather than the wedge.

The plan below assumes #1 and folds #2 into the user conversations.

## The framing: research repo → something fundable

**One line:** *An independent flight recorder for AI agents. When an agent does something dangerous, you can reconstruct why from telemetry the agent can't write to, without trusting its own explanation.*

**Threat model (Monday material, already written in THESIS.md):**
1. Agents take privileged actions based on content they retrieve, so prompt injection turns into a credential fetch, an admin grant, or a dangerous action.
2. Conventional logs record *calls*, not *information*. Sanitisation (`token: ***`) destroys the join keys an investigator needs.
3. The agent's own explanation is produced by the system under investigation. Reasoning traces are not trustworthy evidence, and they get worse under optimisation pressure.
4. So after an incident, nobody can say with confidence what happened. That blocks accountability, insurance, and incident reporting.

**Intervention (already built):** a provenance observer at the tool gateway. It records content-ingestion events, stable credential references, capability transitions, and observed/inferred links between them. The agent has no handle on it, and it hash-chains its records.

**Evidence so far (be exact, don't inflate):**
- Experiment 001, injected scenario: observed data-flow recall **1.0 vs 0.0** for baseline logs at the default preview cap. The advantage **survives an untruncated baseline** (1.0 vs 0.67 at cap 4096). Provenance fired all 4 detection rules; baseline fired 2. Source attribution was correct only under provenance.
- **Cost, stated upfront:** edge precision is worse (0.37 vs 0.58). The observer over-claims "was in context" links.
- The agent is scripted, n=1 per scenario, and ground truth has a data-flow shape. Experiment 002 was built to attack that last point and has **0 human responses so far**.

Saying the weak points first is a strength with this audience. The repo already does it. Keep that tone.

**Who would use it (you need to test this before Oct 21):**
- **Teams running agents in production with real credentials** (security / platform / SRE). The question they'd answer: "after an agent incident, could you tell what caused it?"
- **AI insurers and underwriters.** Alumnus Exona Lab quantifies AI risk for the Lloyd's market. Claims need incident reconstruction that doesn't rely on the insured party's agent explaining itself.
- **Incident reporting regimes.** Providers of general-purpose AI models with systemic risk under the EU AI Act have to track and report serious incidents. Lab and AISI incident-response teams face the same problem.
- **AI control / eval researchers** who need trustworthy trajectory records of untrusted models.

Alumni with nearby shapes: 0Labs (adversarial agents exposing detection gaps) and Shay Yahal (enterprise AI safety, Redwood partnership). Mention the adjacency; don't claim a connection.

## 32-day plan

The application is much stronger if, by Oct 21, you can say "I ran it on real models and real people" instead of "I built the harness."

### Week 1 · Sep 26 – Oct 3: the demo + real models
- [ ] Build the pre-action gate (wedge #1): in `experiment/gateway.py`, evaluate R1 before any privileged call runs, block it, and emit the evidence. Add a `--gate` flag and a test. Record a 2-minute screen capture of the injected run being stopped. **This is your "something to show".**
- [ ] Get an API key and run `python -m experiment run --scenario injected --mode llm` across 2–3 current models, several seeds each. Record whether the injection lands, and whether provenance still attributes the action when the model **paraphrases** instead of copying identifiers verbatim. This is THESIS limitation #1 and the first question a sharp reviewer will ask.
- [ ] Recruit 4 pilot participants (engineers, SREs, security people who haven't seen the repo). Book 1-hour slots for week 2.
- [ ] Email joshua@bluedot.org with one short question: is the review rolling (does applying early help?), and is a research-stage project that is turning into an org in scope? The reply also puts your name in front of them early.

### Week 2 · Oct 4 – Oct 10: evidence
- [ ] Run the human pilot (24 responses, per HUMAN_STUDY_GUIDE.md). Don't touch the preregistration.
- [ ] Run the LLM investigator arm (LLM_INVESTIGATOR.md) on the same 12 packages.
- [ ] `python -m experiment2 metrics && python -m experiment2 report`. Whatever the result is, it goes in the application. A null result reported honestly beats no result.

### Week 3 · Oct 11 – Oct 17: users
- [ ] 5–8 short conversations with the people listed under "who would use it". Ask one question: *"Walk me through the last time an automated system did something you had to explain afterwards. What did you have?"* Write down quotes. Don't pitch.
- [ ] Write a one-page summary (problem → evidence → what you'd build → what you need).
- [ ] Show the gate demo in those conversations after the question, never before it. Ask: "would you put this in front of your agents?"

### Week 4 · Oct 18 – Oct 21: submit
- [ ] Fill in the draft answers below with your specifics. Get one person to read them cold.
- [ ] **Submit by Oct 21.** Oct 28 is a hard backstop, not the target.
- [ ] Logistics: if you're travelling internationally to SF, check visa/ESTA timing now. Some US visa appointment waits are longer than 5 weeks.

## Draft answers

The actual form (Airtable) doesn't render outside a browser, so these follow the likely questions. Adapt them to the real fields. `[[…]]` marks facts only you can fill in.

**What do you want to work on?**
> Independent incident reconstruction for AI agents. When an autonomous agent takes a dangerous action (fetching a credential it didn't need, granting itself admin, acting on an instruction hidden in a document it read), today's logs can't tell you why. The only other account comes from the agent itself, which is the system under investigation. I built a provenance observer that sits at the tool gateway, outside the agent's control. It records what content was in the agent's input state, which credential flowed where, and when its capabilities grew. In a preregistered experiment it recovered the injection-to-admin-action chain that conventional logs missed (observed data-flow recall 1.0 vs 0.0), and the advantage held when the baseline logs were untruncated. It also over-claims links (precision 0.37 vs 0.58), and I report that as a cost rather than hiding it. I'm now testing whether it helps human investigators, blinded, on operational incident-response questions. [[update with pilot/LLM results]] The product I want to build from this is a pre-action gate: it stops an agent's privileged call when untrusted content flowed into it, and shows the evidence for the block. [[link to demo]]

**Why this matters for catastrophic risk?**
> Control, accountability, and insurance all assume that after something goes wrong we can find out what happened. As agents get more autonomy and credentials, that assumption breaks. Logs record calls, not information flow, and self-reports are exactly what a manipulated or misaligned model would get wrong. An independent record that the agent can't write to is basic infrastructure for everything that comes after an incident: attribution, patching, reporting, and deciding whether to keep deploying.

**What have you built / evidence of technical seriousness?**
> github.com/mega-m1nd/dangerous-agent-behavior [[make public or share access]]. Two experiments with pre-registered falsification criteria, applied mechanically in code. A truncation control that tests whether the advantage is just log length. A test suite that enforces the ground truth never reaches the reconstruction code. A blinded human study with HMAC-coded packages and counterbalanced assignment. A validity review written as a hostile critique of my own design. [[background: what you've built/studied before]]

**Are you ready to work on this full-time?**
> [[Be direct: what you're doing now, and that you'd leave it if the week goes well. The page says this explicitly, so a vague answer here costs more than anything else.]]

**What would you do with funding?**
> [[Rough: 6 months runway; turn the observer into an OpenTelemetry-compatible collector (NEXT_EXPERIMENTS #009); run on real agent frameworks; 3 design partners from the user conversations; publish results.]]

## Questions the Friday pitch has to answer

1. Does it still work when the agent paraphrases instead of copying? (Week 1 answers this.)
2. Why is this a separate thing and not a feature in LangSmith, Datadog, or an agent framework? (Hint: independence *is* the product. The recorder can't belong to the system it records.)
3. Who pays, and who's the first user? (Week 3.)
4. What about the precision cost? (Your own answer: inferred links are marked INFERRED and kept separate from OBSERVED ones.)
5. What happens when the agent attacks the observer? (NEXT_EXPERIMENTS #007. Name it as known, open work.)
