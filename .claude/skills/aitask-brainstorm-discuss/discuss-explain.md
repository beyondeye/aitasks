# Explain a proposal in simple words, fully

**Advisory-only:** never edit proposal files, node YAML or any brainstorm session
state, and never run a mutating `ait brainstorm` command — present everything to the user.

A sub-procedure of the brainstorm discuss skill (`aitask-brainstorm-discuss`).
Serves `>e`. Use it when the user wants a proposal explained but may not share the
technical background it assumes. Adapted from the shadow companion's plan
explainer, re-aimed at a brainstorm design proposal.

**"Simple words but complete" is the contract:** the vocabulary is plain, the
coverage is total. Nothing in the proposal is skipped because it is hard to say
simply.

**Inputs:** the one proposal the user named (handle or node id). With no operand
and exactly one proposal listed at Step 0, use it; with several, ask which one in
one line. Read `discuss-audience.md` before writing — its audience rule binds the
walkthrough.

## Procedure

1. **Read the proposal in full** from its `PROPOSAL:` path. If it refers to the
   brainstormed task's goal and that context is needed to explain *why*, read the
   `TASK_FILE:` too (only then).

2. **Identify the technical subjects the proposal rests on** — the tools,
   mechanisms, patterns and domain terms it assumes the reader already knows.
   Aim for the handful that actually matter for understanding *this* proposal,
   not an exhaustive glossary.

3. **Offer per-subject depth — let the user choose.** Use `AskUserQuestion`
   (multiSelect) with the detected subjects as options plus "All of them" and
   "None — just explain the proposal". Only expand the subjects they picked.
   (`AskUserQuestion` allows at most four options: when there are more subjects,
   list them in the message and offer the most important ones as options — the
   "Other" free-text answer covers the rest.)

4. **For each chosen subject, give:**
   - **Introduction** — what it is, in one or two plain sentences.
   - **Motivation** — *why this proposal leans on it*: what problem it solves
     here, what would be worse without it. Tie it to the proposal, not to the
     abstract.

5. **Walk through the proposal in plain language.** Go section by section, in the
   proposal's own order, weaving in the chosen subject introductions where each
   first matters. Lead with outcomes ("once this is in place, X works") over
   mechanism. Every section gets covered; a section you would rather skip gets a
   plain one-line summary, not silence. Call out explicitly anything that affects
   the user's decision — risk, irreversibility, cost, what would need to be
   checked.

6. **Invite follow-ups.** Offer to go deeper on any subject or section, to
   compare it with another proposal (`>c`), or to check it for flaws (`>f`). The
   goal is the user understanding the proposal well enough to judge it — not a
   lecture.
