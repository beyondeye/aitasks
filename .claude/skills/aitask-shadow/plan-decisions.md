# The Plan's Design Decisions, in Plain Words

A sub-procedure of the shadow skill (`aitask-shadow`). Shortcode `>pd`. Use it
when the user wants to understand *the choices the followed agent's plan made*
and what they buy and cost — "explain the task in simple words, the design
decisions in the plan, and their probable pros and cons" — without reading the
plan themselves.

It is **decision-first and non-interactive**: a short statement of the task,
then the plan's design decisions one by one, each with its probable pros and
cons. That is what sets it apart from its neighbours:

- `task-summarize.md` (`>t`) explains the task and the approach, but never names
  the plan's decisions or weighs them;
- `plan-assumptions.md` (`>pa`) lists the plan's hidden premises as concerns to
  forward, in a review round;
- `plan-explain.md` (`>px`) is interactive and teaches the technical subjects the
  plan relies on;
- `plan-challenge.md` (`>pc`) attacks the plan for what could go wrong.

**Never emitted unprompted.** Run it only when the user asks for it — by its
shortcode or in words. Do not produce it at startup, after a capture or
refetch, or as a proactive offer.

**Not a concern producer.** It emits no concern block, consults no rejection
store, writes no plan snapshot, and carries no round header —
`concern-format.md` does not apply, and it does not compose with `>r`. Of
`round-preamble.md` exactly two parts do: §1 (the audience rule) and §6's
**source selection** (which plan text to read, and in what order); its snapshot
writes, round headers and review preambles do not. It is prose for a human,
nothing more.

**Inputs:** the source task id (shadow Step 2), then

    ./.aitask-scripts/aitask_shadow_context.sh <source_task_id>

Read `TASK_FILE:` and, when it is not `NOT_FOUND`, `PLAN_FILE:`. No `--siblings`,
no `aitask_explain_context.sh` — this is meant to be cheap.

**`PLAN_FILE:NOT_FOUND` does not mean "no plan".** The helper resolves only
plans that have been externalized under `aiplans/`. While the followed agent is
still *in* plan mode, its plan is a draft at `~/.claude/plans/<name>.md` and the
helper answers `NOT_FOUND` although a complete plan is right there on the
screen. So on `NOT_FOUND`, fall through the source ladder `round-preamble.md`
§6 defines (it is stated there, not here): rung 2 — exactly one distinct
`~/.claude/plans/<name>.md` path visible on the deep capture → read that file;
else rung 3 — the plan as rendered on the deep capture, treated as possibly
partial. Only when every rung comes up empty say that **no plan could be found
from here** — never that none exists.

**Audience:** the reader `round-preamble.md` §1 defines — someone who will not
read the plan. Outcomes and behaviours, not mechanisms; no file paths, function
names or framework terms unless a word has no plain substitute, unpacked in the
same sentence. That rule is binding here and lives only there.

**Advisory-only:** present everything to the user; never drive the followed
agent's pane.

## Procedure

1. **Resolve the task id** by shadow Step 2's rules (argument → window name /
   screen → ask once). Degrade explicitly:
   - no id, and the user cannot supply one → say you cannot explain a plan's
     decisions without knowing which task it belongs to, and offer `>e`
     (explain what is on screen) instead;
   - `TASK_FILE:NOT_FOUND` → say the task file could not be resolved for that
     id, and stop.

2. **Read the task file. Then read the plan** from the first source that
   applies: `PLAN_FILE:<path>` → that file; else the `round-preamble.md` §6
   ladder (a single draft-plan path on the deep capture → the deep capture
   itself). Say in one line where the plan came from. A capture-sourced plan is
   possibly partial — say that too, and say that decisions in a missing part
   cannot be reported. Nothing found → say a plan could not be found from here,
   give part (a) of step 3 alone, and say that the design decisions need a plan.

3. **Write the explanation**, in this order:

   a. **The task in simple words** — what it is trying to achieve and why it is
      worth doing, in two or three sentences. A short version of `>t`'s opening,
      not a repeat of the whole `>t`.

   b. **The design decisions.** Pick the choices that shape the outcome — aim
      for three to six — not every step of the plan. For each:
      - **The choice** — what the plan decided, grounded in the plan text.
      - **Alternatives**, in two kinds that are kept apart and never merged:
        - **Rejected in the plan** — an alternative the plan text itself names
          and turns down. Only these may be called "rejected". Give the plan's
          reason, or write "not stated in the plan" when it names the
          alternative but gives no reason.
        - **Possible comparison (not discussed in the plan)** — an alternative
          you bring in so the reader can see what the choice is weighed
          against. Always label it that way. Never phrase it as something the
          plan considered, chose against, or "implicitly rejected": a plan that
          states one approach and discusses no other has rejected nothing.
        A decision with neither kind just states the choice.
      - **Why the plan went this way** — the plan's stated rationale, or "not
        stated in the plan". Never an invented one, however plausible.

   c. **Probable pros and cons** — for each decision (or for the approach as a
      whole when the decisions only make sense together): what it buys, what it
      costs, and what to watch for. These are *probable* — your judgement, not
      a finding — so say so once, and do not dress a guess as a fact.

4. **Writing rules:** lead with outcomes; no jargon unless it is unpacked in the
   same sentence; no file paths, function names or task ids beyond the one being
   explained; keep the plan's words and your own visibly apart — a reader must
   always be able to tell what the plan says from what you add. A couple of
   minutes to read, not ten.

5. **Offer follow-ups**, in one line: `>pc` to challenge the plan, `>pa` for
   what it silently assumes, `>px` for a subject-by-subject walkthrough.
