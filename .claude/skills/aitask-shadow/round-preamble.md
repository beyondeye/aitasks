# Plain words and the round preamble (shared procedure)

Shared rules for every shadow review producer — `plan-challenge.md`,
`plan-assumptions.md`, `plan-diagnose-errors.md`, `impl-challenge.md`. Read
this file when a producer references it. One non-producer, `task-summarize.md`,
reads two parts only: §1 (the audience rule binds its prose too) and §6's
source-selection ladder (which plan text to read, in what order) — it writes no
snapshot and emits no round header or preamble. Single source of truth: the audience
rule, the plain-words line, the round preamble's six headings and its fixed
verdict rule, the framework-vocabulary mapping, and the snapshot protocol live
only here; the producers state the two rules in their own emit steps and point
at this file for the substance.

Both additions are **prose for the human, emitted before the concern block**.
Neither is part of the parsed format (`concern-format.md`), neither is forwarded
by the picker, and neither ever appears on a `- [` line or inside the fences.
The block body stays byte-identical to what minimonitor forwards.

## 1. Who this is for (binding audience rule)

Every plain-words line and every sentence of the preamble is written for a
reader who **will not read the plan** and has not followed the concerns in
detail. Name outcomes and behaviours, not mechanisms. No file paths, no
function names, no framework terms — unless a single word has no plain
substitute, and then unpack it in the same sentence ("the lock — the marker
that says who is working on this task — …"). If a sentence would only make
sense to someone who has the code open, rewrite it.

## 2. The plain-words line (every round, every producer)

Each item in the human-readable findings list ends with one line:

    In plain words: <one or two sentences a non-expert can follow>

Derivation order is load-bearing: **compose the concern's block body first** —
the full framing with its `Improves:` / `Worsens:` / `Effort:` /
`Disposition:` trailer — then restate *that body* in plain language: what is
wrong or missing, what goes wrong for the user if it stays, and what would
change if it were addressed. Because the line is derived from the body the
picker forwards, the two cannot diverge. It lives in the prose list only. A
concern you cannot restate plainly is a concern you do not yet understand;
go back to the body.

## 3. The round preamble — "Where this is heading" (rounds ≥ 2)

Round 1 emits no preamble. Every later round — a manual "refetch and recheck",
or minimonitor's `L` auto-loop injecting `refetch and recheck round N` —
opens with this preamble **immediately after** the one-line "which
sub-procedure, which round" announcement and **before** the findings list, so
it is always before the block. Title it `Where this is heading`, then the six
fixed headings, in this order, with these plain labels:

1. **Since last round** — bullets, each tagged *added* / *removed* /
   *changed*, and each saying what the change means for the result.
2. **Since the original plan** — cumulative, against the round-1 baseline.
   Each bullet says, in words rather than by region tag, which earlier concern
   asked for it — or "nobody asked for this".
3. **Is it still doing what was asked?** — exactly one of `same thing` /
   `does less` / `does more` / `does something different`, **always** followed
   by the two explicit lists "It no longer will: …" and "It now also will: …".
   Write "nothing" for an empty list. The label alone never stands.
4. **How much bigger did it get?** — exactly one of `not at all` /
   `a little` (tweaks inside what was already there) / `noticeably` (a new
   piece, or a new case to handle) / `a lot` (a new component, a new setting
   users see, or a new dependency), plus the list of what was added.
5. **Was each change worth it?** — one line per change from heading 2, each
   classified `needed` (fixes something that would be wrong or missing) /
   `nice to have` (better, but could have waited as its own task) /
   `not worth it` (cost more simplicity than the concern said it would, or the
   concern was only informational) / `nobody asked`. End with one count line,
   e.g. `3 needed / 1 nice to have / 1 not worth it / 0 nobody asked`.
6. **Bottom line** — exactly one of `on track` / `drifting` /
   `getting over-built`, decided by the fixed rule below, followed by
   "I'd undo …" naming which incorporations to roll back into follow-up tasks
   (or "I'd undo nothing").

**Fixed rule for the bottom line** — apply it, never re-judge it:

- `getting over-built` if any change in heading 5 is `not worth it`, or any
  `nobody asked` change is `noticeably` or larger in heading 4, or heading 3 is
  `does more` / `does something different`;
- otherwise `drifting` if heading 3 is `does less`, or only `nice to have`
  changes drove growth of `noticeably` or larger;
- otherwise `on track`.

The preamble is a comparison **done by you, reading the texts** — the round-1
baseline, the previous round's text, the current text, and your own earlier
rounds' concerns from this conversation (plus the rejected store,
`./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>`, which records what
the user declined). No diff tool is involved; the only helper makes the earlier
texts *available* (section 5).

## 4. Mapping to the framework vocabulary — for you, never in the output

The plain labels are grounded in the concern price every producer already
quotes; use this to decide, and keep the vocabulary out of the text:

| plain label | grounds in |
|---|---|
| `needed` | the concern's `Improves:` touched an obligation dimension — `goal`, `correctness`, or acceptance-criteria-obligated `robustness` / `performance`; i.e. it was `Disposition: blocking` |
| `nice to have` | `Disposition: follow-up` |
| `not worth it` | the realized `simplicity` cost exceeds the quoted `Worsens:`, or the concern was `Disposition: informational` |
| `nobody asked` | no earlier concern maps to the change |
| heading 3 | the `goal` dimension |
| heading 4 | realized `simplicity` |

The preamble closes the loop on the impact vector: did the plan pay the price
each concern quoted, only that price — and did it pay anything nobody quoted?

## 5. What you compare, per producer

| producer | "the plan" means | baseline for heading 2 | previous round for heading 1 |
|---|---|---|---|
| `plan-challenge.md`, `plan-assumptions.md` | the plan text | the round-1 plan snapshot (`plan_r1.md`) | the previous round's plan snapshot |
| `impl-challenge.md` | the code change | **the approved plan** (committed; `aitask_shadow_context.sh`) against the change as it now stands — heading 2 reads "Since implementation started" and is always answerable | the previous round's diff snapshot (`diff_r<N-1>.md`) when present; otherwise your own previous round's findings only, and say so |
| `plan-diagnose-errors.md` | the error picture on the followed screen | your round-1 findings | your previous round's findings |

**Implementation rounds have no git baseline for "last round".** The task
workflow keeps implementation uncommitted until its "Commit changes" step, and
every revision overwrites the working tree, so git only ever exposes the
*current* diff. Heading 2 — what was going to be built versus what now exists —
is the load-bearing comparison for implementation rounds; heading 1 is
best-effort from the diff snapshot below. Build nothing more elaborate for it.

## 6. Snapshot protocol

The store is `.aitask-shadow/<task_id>/` — the same per-task directory as the
rejection store, same task-id validation, same mutex, atomic writes, pruned at
archive. Two verbs:

    ./.aitask-scripts/aitask_shadow_rejected.sh snapshot <task_id> <N> [--kind plan|diff] [--partial]   (text on stdin)
    ./.aitask-scripts/aitask_shadow_rejected.sh snapshots <task_id>

`snapshot` prints one line, `SNAPSHOT:<kind>|<N>|<complete|partial>|<path>`.
The path is last and may itself contain `|`, so split on at most the first
three separators. `LOCK_BUSY` (exit 3), exit 2 (bad id, bad round, empty
input) or exit 4 (write failure) mean the snapshot was **skipped**: say so and
continue — a missing snapshot is never a blocker. No task id ⇒ no snapshot;
say so. N is the same round number the block header will carry.

### Plan rounds (`plan-challenge.md`, `plan-assumptions.md`)

At the start of every round, after reading the plan, save the plan text.
**Source preference — the first that applies:**

1. **The externalized plan.** `aitask_shadow_context.sh <task_id>` returned
   `PLAN_FILE:<path>` and its content matches what is on the followed screen
   (after the followed agent leaves plan mode, the workflow externalizes the
   plan immediately):

       ./.aitask-scripts/aitask_shadow_rejected.sh snapshot <task_id> <N> < <path>

2. **The followed agent's draft-plan file.** The deep capture shows **exactly
   one distinct** path of the form `~/.claude/plans/<name>.md` anywhere on the
   followed screen — the plan-approval dialog, a Write/Edit line, any other
   mention. That file on disk is the clean, complete current plan (it is the
   document the agent is editing, not a rendering of it), so prefer it over
   any capture even when no Write/Edit line is visible:

       ./.aitask-scripts/aitask_shadow_rejected.sh snapshot <task_id> <N> < <that path>

   More than one distinct path, or none ⇒ fall through.

3. **A widened deep capture, delimited to the latest rendering — else
   partial.** Scrollback is not a document: a plan longer than the default
   400-row window loses its opening while the capture still "succeeds", and an
   ordinary revision cycle leaves an *older complete* rendering above a
   *truncated current* one, so "the title appears somewhere" proves nothing.
   Capture wider:

       SHADOW_PLAN_CAPTURE_LINES=2000 ./.aitask-scripts/aitask_shadow_capture.sh --deep

   Delimit: keep only the text from the **last** occurrence of the plan's
   title line (the first top-level heading you identified while reading the
   plan) to the end of the capture. That segment is the snapshot **only if**
   every top-level heading you identified while reading the plan occurs in it
   **exactly once** — a repeated heading means two generations are mixed, a
   missing one means the current rendering lost its head. Otherwise retry once
   with `4000` and re-check. If the check still fails, snapshot the delimited
   segment (or the whole capture when the title never appears) with
   `--partial`, and say so in the prose. A terminal capture that cannot be
   delimited is **always** partial, never complete — never claim a baseline
   you did not verify.

### Implementation rounds (`impl-challenge.md`)

After assembling the composite diff (its Inputs step 2 — commits, index,
working tree, untracked, exactly as resolved there), save that same text:

    <the composite diff text> | ./.aitask-scripts/aitask_shadow_rejected.sh snapshot <task_id> <N> --kind diff

One pipe; it is the only thing that makes heading 1 answerable in an
uncommitted working tree.

### Reading back (round ≥ 2)

Run `snapshots <task_id>`; each line is
`SNAPSHOT:<kind>|<N>|<complete|partial>|<path>`, or the single line
`NO_SNAPSHOTS`. Read the round-1 file and the previous round's file for your
kind. A `partial` round-1 plan ⇒ say "the original-plan baseline is partial
(capture window), so 'since the original plan' may miss early sections". A
missing file (a fresh shadow session, an earlier skipped snapshot) ⇒ say which
comparison is unavailable and fill that heading from what you do have — never
fabricate a baseline.
