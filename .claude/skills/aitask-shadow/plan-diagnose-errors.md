# Diagnose skill/helper errors (in the followed agent)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the followed
agent's captured screen shows **tool-call errors or retries** — signs of a bug in
a workflow skill definition or in a helper bash script it calls (wrong parameters,
or a bug in the script itself). Your job is to diagnose those errors, surface them
as a list of candidate concerns the user can pick from, and — for the ones the
user chooses — **offer** to spin each into its own fix-task via `/aitask-explore`.

This capability is **on-request only**: run it when the user asks you to diagnose
what is going wrong. It is deliberately *not* offered proactively — the shadow
never emits unsolicited error concerns.

**Inputs:** the captured screen (shadow Step 1). Refetch with
`aitask_shadow_capture.sh` if the screen may be stale. No plan file is needed.

**Advisory-only:** present everything to the user; never drive the followed
agent's pane. The fix-task offer below runs `/aitask-explore` in **your own**
pane — never the followed pane.

## Procedure

1. **Read the captured screen** (shadow Step 1; refetch if it may be stale).

2. **Scan for error / retry signals.** Look for:
   - `InputValidationError`
   - `Tool error:`
   - `Traceback (most recent call last):`
   - bash `error:` / stderr lines (e.g. `<script>.sh: line N:`, `command not found`,
     a non-zero-exit diagnostic)
   - **repeated identical commands** — the same tool call or bash line issued 2+
     times in succession (a retry loop).

   **Do not manufacture problems.** Error-*shaped* text is not always a live
   failure: a passing test run may print the word `error:` in narrative output, an
   *intentionally* failing test may be exactly what the agent expects, and a
   traceback the agent has pasted to *discuss* is not a fresh crash. Judge whether
   each signal reflects an actual, unhandled failure the agent is stuck on. If
   nothing on screen is a genuine error/retry problem, **say so plainly** and
   emit the metadata-only block — the two fences with only the round header
   between them (step 4) — so the round is still recorded.

3. **Attribute each genuine signal to the likely skill / helper.** For each error
   cluster, identify which workflow skill or `aitask_*.sh` helper the followed
   agent was running when it hit the error, and — where inferable — whether it
   looks like a *wrong-parameter call* (the caller passed bad arguments) versus a
   *bug in the script/skill itself*. Name the concrete file(s) to look at.

4. **Present the candidate concerns, then emit the marked concern block.** First
   give the user a short human-readable list (one item per error cluster, each
   with: what failed, the likely cause, and the file to look at). Then emit the
   block per **Also emit the structured concern block (for pick-and-forward)**
   below — emit it before continuing to step 5, which asks the user to choose
   among the concerns it contains.

5. **Let the user choose which concerns to act on, then offer ONE action.** See
   the step of that name after the emit section below.

## Also emit the structured concern block (for pick-and-forward)

Append a machine-parseable copy of the *same* concerns presented in step 4, so
the user can forward a subset via minimonitor's concern picker instead of
retyping.

**Consult the rejection store before emitting.** Using the source task id
from your launch arguments or Step 2 — resolving one now if you have neither
(it is inferable from the followed agent's window name, e.g.
`agent-pick-635_3`) — run
`./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>` and drop every
fresh concern that is substantively the same as a previously-rejected entry,
even when reworded. The full contract is in the format rules below.

**Price your own suggestion: emit the impact vector.** Every concern ends its
body with `Improves: <dimension>(<magnitude>)[, …].`, then
`Worsens: <dimension>(<magnitude>)[, …].` — and **the Worsens sentence is
mandatory**, as `Worsens: nothing.` when the fix genuinely costs nothing —
then `Effort: <high|medium|low>.`, then `Disposition: …` (below). Without the
worsen side a concern is a pure demand with externalised costs, and a
codebase that absorbs every such demand is silently over-engineered: a
diagnosis whose only remedy adds mechanism around a one-line bug is a bad
trade, and saying so is your job. `Worsens: nothing.` is a *priced* empty set
and an omitted `Worsens:` is a different state — the parser distinguishes
them, so never drop the sentence to mean "nothing". The marker priority you
write is then not a free choice: it is `derive_priority(improves)`, the
strongest known magnitude on the improve side.

**Dimensions are load-bearing; magnitudes are advisory.** Naming *which*
quality moves is the information the old bare severity scalar never carried,
and it is what the reader acts on. Calibrating *how far* it moves is noisy,
so a magnitude refines a concern and never decides whether it is one. Draw
every dimension from this closed vocabulary — the parser builds its name
alternation from it, so an invented name makes the whole sentence fail to
match and it stays visibly in the body:

- `goal` — the task's AC / the user's stated intent is delivered
- `correctness` — right behavior on reachable inputs
- `robustness` — stability under failure / concurrency / hostile input (includes security)
- `performance` — latency, throughput, resource cost
- `verification` — testability; proof the change works
- `maintainability` — readability, duplication, conventions; ease of safe change
- `simplicity` — amount of mechanism; the classic worsen-side

**Give each item a disposition**, grounded in its vector — `blocking`,
`follow-up`, or `informational`:
- **`blocking`** — the improve side touches an *obligation dimension*:
  `goal` and `correctness` categorically, `robustness` and `performance`
  when the workflow obligates them. A helper that crashes on every call of a
  reachable path belongs here.
- **`follow-up`** — real and net-positive, but touching no obligation
  dimension: a noisy retry, a confusing message, a latent path nothing
  currently reaches.
- **`informational`** — no proposed delta at all, or the point is already
  settled: error-shaped text that is in fact benign, or a failure the
  workflow already recovers from. Say *what* settles it so the user can
  disagree. `informational` is never a parking slot for an error you believe
  is a genuine unaddressed bug — that one is `blocking` or `follow-up`.

Emit a block delimited by an opening `===AITASK-CONCERNS===` line and a
closing `===END-CONCERNS===` line (those two exact literals; single source of
truth: `.claude/skills/aitask-shadow/concern-format.md`), with one concern per
line between them. The concern lines themselves look like:

```
Round: 1 @ 2026-08-11T14:03:27Z
- [high | aitask_pick_own.sh] The followed agent's claim call exits non-zero with `aitask_pick_own.sh: line 88: LOCK_DIR: unbound variable`, then retries the identical command three times — the helper dereferences LOCK_DIR before it is set, so every claim on this path crashes. Look at the variable's init in aitask_pick_own.sh; likely a missing default or an ordering bug rather than a bad caller argument. Improves: correctness(high), robustness(medium). Worsens: nothing. Effort: low. Disposition: blocking.
- [medium | task-workflow Step 4] The agent passes `--email ""` and the script emits `InputValidationError: email must be non-empty`, looping twice. The workflow's email-resolution branch is handing an empty string to the claim call instead of omitting the flag; the fix likely belongs in the Step 4 email branch, not the helper. Improves: correctness(medium). Worsens: simplicity(low). Effort: low. Disposition: blocking.
- [low | aitask_lock.sh] The lock helper prints its human-readable diagnostic to stdout, so the captured pane interleaves it with the structured OWNED: / LOCK_FAILED: lines the caller parses. Nothing has misparsed yet — the prefixes are distinct enough — but a caller that reads stdout line-wise inherits the hazard for free. Routing diagnostics to stderr in aitask_lock.sh would separate the two channels; how you split them is your call. Improves: maintainability(low). Worsens: nothing. Effort: low. Disposition: follow-up.
```

**Emit a round header as the first line inside the block.** Immediately
after the opening fence — before the first `- [` marker — emit exactly one
line of the form `Round: <N> @ <timestamp>`, for example
`Round: 2 @ 2026-08-11T14:03:27Z`. If the request that triggered this review
names a round ("recheck round N"), use that N; otherwise N is 1 for the
first review you run in this conversation and increments by one on each
later review you run in it (any review sub-procedure counts; a fresh shadow
session starts at 1 again — the timestamp is what disambiguates). Obtain the
timestamp by running `date -u +%Y-%m-%dT%H:%M:%SZ` — never estimate it. A
**zero-concern** review (nothing found, or suppression removed everything)
still emits the block: the two fences with only this header between them,
which is the machine-readable record that the round completed clean.

Format rules — all load-bearing for minimonitor's parser; match them exactly:
- One concern per line, in the form `- [priority | region] body`.
- The leading `- ` (dash **and** space) is **MANDATORY** on every concern line
  — it is the wrap-collision guard (a soft-wrapped continuation line never
  carries it, so the parser can't mistake wrapped text for a new item).
- `priority` is one of `high`, `medium`, `low`, and for a vector-bearing
  concern it is exactly `derive_priority(improves)` — the strongest known
  magnitude on the improve side, `low` when that side is absent, empty, or
  carries only unspecified magnitudes. That is the **single** mapping to this
  field: do not compute it from anything else. The picker shows the derived
  value and flags a marker that disagrees, rather than silently reconciling
  the two.
- `region` names the offending skill / helper (a script name, a skill step,
  etc.) — it is **mandatory and never empty** (it is the row's only title in
  minimonitor's picker; an omitted one renders as `(no region)`) — and MUST
  stay **short** (≤ ~30 chars): use a bare script name or a
  `basename.ext:LINE` locus, never a full repo path (put the full path in
  the body instead). The whole `[priority | region]` marker must survive on
  ONE rendered row: some agent TUIs hard-wrap long lines with literal
  newlines that even a wrap-joined capture cannot rejoin, and a wrap
  *inside the bracket* makes the item unparseable to minimonitor.
- `body` carries the **full framing** — what failed, *why it bites* (the error
  and the likely cause), and the concrete file to look at. Match the substance
  of the corresponding prose item; do **not** compress it to a bare one-liner.
  "One logical line" is a **parser constraint** (emit no literal newline
  mid-concern — let the terminal soft-wrap), not a brevity constraint.
- **Impact vector.** End the body with
  `Improves: <dimension>(<magnitude>)[, …].`,
  `Worsens: <dimension>(<magnitude>)[, …].` or `Worsens: nothing.`, and
  `Effort: <high|medium|low>.` — and the Worsens sentence is mandatory, in
  both forms: a priced-nothing worsen side and an omitted one are different
  states and the parser reads them differently. Dimension names come only
  from the closed vocabulary above; the dimension names are the load-bearing
  part and magnitudes are advisory, so an uncertain magnitude is still worth
  naming its dimension for.
- **Disposition.** End the body with `Disposition: blocking.`,
  `Disposition: follow-up.` or `Disposition: informational.`, exactly as
  classified above. These trailer sentences are **parsed**: minimonitor
  groups the picker by disposition, dimming `informational`. An omitted
  disposition makes the finding show up as needing attention.
- The trailer sentences must be the **last thing in the body** — they are
  matched only as a terminal run, so anything written after them is not read
  as a trailer. Their order within that run is free.
- Order items `blocking` first, then `follow-up`, then `informational`,
  matching the prose list, by derived priority within each partition.
- **Suppress previously-rejected concerns.** Before emitting, run
  `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>`. Exactly three
  outcomes are defined: the single line `NO_REJECTIONS` means nothing is
  rejected; a printed body is the user's previously-rejected concerns; and
  **anything else** — a non-zero exit (a malformed task id exits `2`), empty
  output, or output matching neither shape — means you could not consult the
  store, so emit every fresh concern and state that rejection suppression was
  skipped. Never read an error as "nothing was rejected". Drop a fresh
  concern only when it is substantively the same as a rejected one; when
  unsure, **keep it and say why** (fail-open). Whenever N ≥ 1 were dropped,
  report `Suppressed N previously-rejected concern(s).` in the prose before
  the block. When no task id can be resolved, say suppression was skipped.
- **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
  auto-offer only fires on a complete block.
- **Round header.** The first line after the opening fence is
  `Round: <N> @ <timestamp>` and nothing else. It MUST come **before** the
  first `- [` marker — placed after an item it is absorbed into that item's
  body and the round is lost — and it must never itself begin with `- [`.
  Take N from the request when it names a round ("recheck round N"), else
  count from 1 within this conversation; get the timestamp from
  `date -u +%Y-%m-%dT%H:%M:%SZ`, never by estimate. A **zero-concern**
  review — no genuine error/retry signal (step 2) survived suppression —
  still emits the fences with only this header between them (say so in the
  prose). Minimonitor reads the header to show the round, to re-offer the
  picker when a later round repeats the same concerns, and to judge concern
  freshness.

## Step 5 — Let the user choose which concerns to act on, then offer ONE action

   Ask
   the user which of the presented concerns actually warrant their own fix-task —
   use `AskUserQuestion` (multiSelect) with one option per concern plus a
   "None — just keep the marked concerns" choice. For each concern the user
   selects, **offer** to launch `/aitask-explore` seeded with a prompt naming that
   concern's skill / helper path(s) and the captured error excerpt, so the bug
   becomes its own scoped fix-task. Only on explicit confirmation do you launch it,
   in **your own** pane.

   Scope (v1): the offered action is **`/aitask-explore` with a seed prompt
   only** — do not branch into direct batch task creation here (a possible later
   enhancement). Never auto-launch, and never send anything to the followed pane.
