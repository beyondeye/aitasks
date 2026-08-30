# Plan Challenge (adversarial)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
a plan stress-tested before approving it — "poke holes in this", "what could go
wrong", "try to break it". Your job here is to be a constructive adversary:
actively look for where the plan fails, not to reassure.

**Inputs:** the captured screen (shadow Step 1) and/or the fetched plan file
(shadow Step 2). Fetch the full plan first if only a fragment is on screen. When
you (re)capture the followed pane to read the plan, use the deeper plan-review
capture — `./.aitask-scripts/aitask_shadow_capture.sh --deep` — because plans
are long and the default 200-line window can truncate earlier constraints,
decisions, or risk notes. Pass no pane id: the helper resolves your bound
followed pane itself (add `<followed_pane_id>` only if Step 1 also had to).

**Advisory-only:** present the challenges to the user; never drive the followed
agent's pane.

## Procedure

1. **Read the plan in full** and form a clear model of what it intends to do and
   how.

2. **Attack it along these axes** (skip any that don't apply; add others the plan
   invites):
   - **Regressions / breakage** — what existing behavior could this change break?
     Which load-bearing path does it touch?
   - **Missed edge cases** — inputs, states, or environments the plan does not
     handle (empty/large inputs, concurrency, error paths, platform differences,
     first-run vs upgrade).
   - **Wrong shape** — is the approach itself a mismatch for the goal? Is there a
     simpler or more robust path the plan skipped?
   - **Blast radius / "edited unaware"** — what happens when someone later edits
     one of the touched files without knowing this plan's assumptions? Hidden
     coupling, implicit contracts, duplicated sources of truth.
   - **Verification gaps** — does the plan's own verification actually prove it
     works, or could it pass while the feature is broken?
   - **Unstated dependencies** — does it rely on something not yet built, a
     specific tool version, or another task landing first?

3. **Produce a prioritized list of concrete weaknesses.** For each: a one-line
   statement of the problem, *why* it bites (the scenario that triggers it), and
   its **impact vector** — which quality dimensions incorporating the fix would
   improve, which it would worsen, and what it would cost. The closed dimension
   vocabulary and the grammar are in the emit section below; the same vector is
   what the block carries, so decide it once here. Be specific to this plan — no
   generic "consider adding tests" filler.

4. **Give each finding a disposition**, grounded in its vector rather than in
   how alarming it sounds — `blocking`, `follow-up`, or `informational`:
   - **`blocking`** — the improve side touches an *obligation dimension* for
     this plan: `goal` and `correctness` categorically, `robustness` and
     `performance` only when the task's own acceptance criteria or the plan
     itself obligates them. These are the findings that should block approval.
   - **`follow-up`** — real and net-positive, but touching no obligation
     dimension: separable improvement or separable debt, which the user could
     reasonably accept as a later task rather than a change to this plan.
   - **`informational`** — no proposed delta at all, or the point is already
     settled. Say *what* settles it (the plan's own rationale, an existing
     guard, the obligation boundary) so the user can disagree and escalate it.
     `informational` is never a parking slot for a weakness you believe is
     genuinely unaddressed — that one is `blocking` or `follow-up`.

   Order the list `blocking` first, then `follow-up`, then `informational`, by
   derived priority within each partition.

5. **Stay honest.** If the plan is genuinely solid on an axis, say so briefly
   rather than manufacturing a concern. A short list of real problems beats a
   long list of weak ones. Present everything to the user to decide.

6. **Also emit the structured concern block (for pick-and-forward)** — see the
   section of that name below, and emit it as the final output of the review.

## Also emit the structured concern block (for pick-and-forward)

After the human-readable list above, append a machine-parseable copy of the
*same* concerns so the user can tick a subset and forward them to the followed agent
via minimonitor's concern picker — instead of retyping them. This block is
**additive**: it does not replace the prose, and it does **not** relax the
advisory-only guardrail (it is text for the *user* to copy; you still never
drive the followed pane).

**Consult the rejection store before emitting.** Using the source task id
from your launch arguments or Step 2 — resolving one now if you have neither
(it is inferable from the followed agent's window name, e.g.
`agent-pick-635_3`) — run
`./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>` and drop every
fresh concern that is substantively the same as a previously-rejected entry,
even when reworded. The full contract is in the rules list below.

**Price your own suggestion: emit the impact vector.** Every concern ends its
body with `Improves: <dimension>(<magnitude>)[, …].`, then
`Worsens: <dimension>(<magnitude>)[, …].` — and **the Worsens sentence is
mandatory**, as `Worsens: nothing.` when the fix genuinely costs nothing —
then `Effort: <high|medium|low>.`, then `Disposition: …` from Step 4. Without
the worsen side a concern is a pure demand with externalised costs, and a
plan that absorbs every such demand is silently over-engineered; a concern
that improves only non-obligated dimensions at a simplicity cost
self-identifies as a bad trade. `Worsens: nothing.` is a *priced* empty set
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

Emit a block delimited by an opening `===AITASK-CONCERNS===` line and a
closing `===END-CONCERNS===` line (those two exact literals; single source of
truth: `.claude/skills/aitask-shadow/concern-format.md`), with one concern per
line between them. The concern lines themselves look like:

```
Round: 1 @ 2026-08-11T14:03:27Z
- [high | Step 7 ownership guard] The guard re-runs aitask_pick_own.sh even when Step 4 already acquired the lock on this host, so every resumed task writes a second, redundant ownership commit to the data branch. It bites on the common reclaim path — crash recovery, multi-day tasks — quietly doubling the commit history each time. Gating the re-run on whether the lock is already held by this host would fix it, but I'd leave the exact guard condition to you. Improves: correctness(high), simplicity(low). Worsens: nothing. Effort: low. Disposition: blocking.
- [medium | verification] The only test asserts the script exits 0; it never reads back the file the script was supposed to write. A regression that turns the write into a silent no-op would still pass, so the test proves the script ran, not that it worked. Asserting on the written content (or a round-trip read) would close the gap — however you prefer to structure it. Improves: verification(medium). Worsens: simplicity(low). Effort: low. Disposition: follow-up.
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

Rules — all load-bearing for minimonitor's parser; match them exactly:
- One concern per line, in the form `- [priority | region] body`.
- The leading `- ` (dash **and** space) is **MANDATORY** on every concern
  line — it is the wrap-collision guard (a soft-wrapped continuation line
  never carries it, so the parser can't mistake wrapped text for a new item).
- `priority` is one of `high`, `medium`, `low`, and for a vector-bearing
  concern it is exactly `derive_priority(improves)` — the strongest known
  magnitude on the improve side, `low` when that side is absent, empty, or
  carries only unspecified magnitudes. That is the **single** mapping to this
  field: do not compute it from anything else. The picker shows the derived
  value and flags a marker that disagrees, rather than silently reconciling
  the two.
- `region` names the plan section / axis the concern targets (a step name,
  `verification`, `blast radius`, …) — it is **mandatory and never empty**
  (it is the row's only title in minimonitor's picker; an omitted one
  renders as `(no region)`) — and MUST stay **short** (≤ ~30
  chars): use an axis label or a `basename.ext:LINE` locus, never a full
  repo path (put the full path in the body instead). The whole
  `[priority | region]` marker must survive on ONE rendered row: some agent
  TUIs hard-wrap long lines with literal newlines that even a wrap-joined
  capture cannot rejoin, and a wrap *inside the bracket* makes the item
  unparseable to minimonitor.
- `body` carries the **full framing** of the concern — the problem, *why it
  bites* (the triggering scenario), and enough context for the receiving
  agent to choose **how** to address it. Match the **substance** of the
  corresponding prose item from Step 3; do **not** compress it to a bare
  one-liner — the framing is as important as the point. "One logical line" is
  a **parser constraint** (emit no literal newline mid-concern — let the
  terminal soft-wrap), **not** a brevity constraint: a rich, multi-sentence
  body that soft-wraps across several rows is correct and reassembles into
  one concern.
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
  classified in Step 4. These trailer sentences are **parsed**: minimonitor
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
  review — the plan is genuinely clean (Step 5), or suppression left you
  with nothing to forward — still emits the fences with only this header
  between them (say so in the prose). Minimonitor reads the header to show
  the round, to re-offer the picker when a later round repeats the same
  concerns, and to judge concern freshness.
