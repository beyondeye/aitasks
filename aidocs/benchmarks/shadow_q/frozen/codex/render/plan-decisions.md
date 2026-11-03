# The Plan's Design Decisions, in Plain Words

A sub-procedure of the shadow skill (`aitask-shadow`). Shortcode `>pd`. Use it
when the user wants to know *which real trade-offs the followed agent's plan
made* — "explain the task in simple words, the design decisions in the plan,
and their pros and cons" — without reading the plan themselves.

It is **decision-first and non-interactive**: a short statement of the task,
then the few choices in the plan that were genuine trade-offs, each with its
pros and cons. That is what sets it apart from its neighbours:

- `task-summarize.md` (`>t`) explains the task and the approach, but never names
  the plan's decisions or weighs them;
- `plan-assumptions.md` (`>pa`) lists the plan's hidden premises as concerns to
  forward, in a review round;
- `plan-explain.md` (`>px`) is interactive and teaches the technical subjects the
  plan relies on;
- `plan-challenge.md` (`>pc`) attacks the plan for what could go wrong.

**Signal, not coverage.** The value of this answer is in what it leaves out. A
plan is mostly choices that had no real alternative — they follow from the task,
from a project convention, or from being the only thing that works. Reporting
those buries the two or three choices that actually traded one good thing for
another. Do not try to be complete.

**Never emitted unprompted.** Run it only when the user asks for it — by its
shortcode or in words. Do not produce it at startup, after a capture or
refetch, or as a proactive offer.

**Not a concern producer.** It emits no concern block, consults no rejection
store, writes no plan snapshot, and carries no round header —
`concern-format.md` does not apply, and it does not compose with `>r`. Of
`round-preamble.md` only §6's **source selection** applies (which plan text to
read, and in what order); its snapshot writes, round headers and review
preambles do not. It is prose for a human, nothing more.

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

**Audience:** someone who has not read the plan but knows the project. Use plain
words, and name the concrete thing a decision is about — the command, the file,
the mechanism — when that is the clearest way to say it. Unpack a term only when
a reader of the project would not know it.

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
   itself). Say in one line where the plan came from, and that it may be
   partial when it came from a capture. Nothing found → say a plan could not
   be found from here, give the task in a few sentences, and stop.

3. **Select the decisions — this is the whole job.** A choice qualifies only
   when **all** of these hold:
   - a competent engineer could reasonably have gone another way;
   - each way gives up something real — the alternative would have bought
     something this choice does not;
   - getting it wrong would matter to the outcome.

   Leave out everything else: what the task itself dictates, what a project
   convention dictates, routine housekeeping (tests, docs, renames, wiring), and
   any choice whose only "cost" is trivial. There is no target number. One or
   two is normal; none is a valid answer — then say the plan is
   straightforward and why.

4. **Write the answer:**
   - **The task**, in two or three plain sentences: what it achieves and why it
     is worth doing.
   - **The decisions**, most consequential first. For each, a short paragraph:
     what the plan chose, the realistic alternative, and the plan's reason for
     its choice — or "the plan does not say why" when it gives none. Then:

         Pros: …
         Cons: …

     Write only real pros and cons. If you cannot name a real con, the choice
     was not a trade-off — drop it.
   - **Anything left out**, in at most one line ("The rest — docs, tests,
     wiring — follows directly from the task."), so the reader knows the
     omission was deliberate.

   **Keep the plan's words and yours apart.** Never say the plan considered or
   rejected an option it does not mention. When the alternative is your own,
   say so in passing ("the obvious other route would have been …"); never
   invent a rationale the plan does not give.

5. **Offer follow-ups**, in one line: `>pc` to challenge the plan, `>pa` for
   what it silently assumes, `>px` for a subject-by-subject walkthrough.
