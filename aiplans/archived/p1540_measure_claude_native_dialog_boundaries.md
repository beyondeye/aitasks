---
Task: t1540_measure_claude_native_dialog_boundaries.md
Branch: main
Base branch: main
Output branch: main
---

# t1540 — Measure Claude's native-dialog boundaries

## Context

`review_loop.classify_followed_change` decides, on every minimonitor tick, whether
the **followed** agent pane did real work or merely redrew a selection cursor. For
a native (chip-less) dialog it needs a **boundary line**: a stable line rendered
above everything that moves during selection. `_native_block_start` finds the last
line matching that boundary; everything above it is compared, and a difference
means `WORK`.

Without a boundary the kind falls through to `return UNKNOWN`
(`review_loop.py:1032`). `UNKNOWN` neither opens nor resets the work latch, and
`ReviewLoopController.tick` fires only when `self.work_seen` is true — so a pane
parked at an unanchored dialog leaves the loop **armed and permanently
non-firing**, with the banner still reading `⟳ auto-recheck ARMED`. That is a
silent failure, not a visible one.

t1518 closed this for Codex and OpenCode. Building its completeness guard
(`ArmedAgentKindCoverageTests.test_every_armed_agent_kind_resolves`) forced every
kind an armed agent can report to either resolve to a boundary or be listed in
`DELIBERATELY_UNANCHORED_KINDS` with a written reason — which is how Claude's gap
became *visible* rather than merely absent. Three Claude kinds sit there today
(`review_loop.py:916-918`), all with the placeholder reason
`"no measured boundary (pre-t1518)"`.

Intended outcome: replace that placeholder with **measured** evidence — a boundary
row for every (kind, dialog) that passes the measurement, and an honest, measured
reason for anything that does not.

**Scope decisions taken with the user:**

- `claude_help_bar` is Claude's *generic* blocked-on-input footer. This task
  measures the **tool-permission dialog only**; every other help-bar surface (the
  free-text amend prompt, other numbered selections) keeps classifying `UNKNOWN`.
  That partial coverage is not merely noted — each known surface is captured
  (Step 1a-bis) and **asserted unanchored** (Step 3), with a negative control that
  fails if the regex is ever widened to reach one.
- Live acceptance is **full t1518 parity**: the checked-in live-tmux wiring test
  (Step 4a) *and* the one-off live arm-and-fire observation with a real Claude
  followed pane and a real shadow (Step 4b) — the latter as a **gate** with
  PASS/FAIL/BLOCKED consequences, not a recorded shortfall.
- The measurement runs across a **supported geometry set** — 120x30, the
  post-split height a same-window shadow leaves (the geometry the loop actually
  runs in), and the measured floor — and a row ships only if it holds at all of
  them (**B1–B4**, §1c).

## What already exists — do NOT rebuild

- **The measurement recipe** — `aidocs/framework/shadow_agent.md` §"Recipe:
  measuring a new agent's readiness surfaces" (lines 820–866). Its harness is
  **scratchpad-only by standing decision** (t1520/t1518) — do not commit a driver.
- **The B1/B2/B3 criteria and the `## Measurement` table format** —
  `aiplans/archived/p1518_arm_review_loop_for_codex_opencode_followed_panes.md`
  (Step 1, lines 94–169; the executed table, lines 568–693). Reuse verbatim —
  but note they are **not the whole bar here**: t1540 adds **B4** (§1c), and
  shipping is gated on B1–B4, not on t1518's B1–B3.
- **The three tables and their contract** — `NATIVE_DIALOG_BOUNDARIES`,
  `NATIVE_DIALOG_STRATEGIES` (defined-but-empty on purpose, consulted first),
  `DELIBERATELY_UNANCHORED_KINDS`, plus `_native_block_start` /
  `native_dialog_anchored`. No new mechanism is needed — this task adds **data**.
- **Claude is already in `REVIEW_LOOP_AGENTS`** (`review_loop.py:713`). Nothing to
  widen, no refusal wording to change, no `minimonitor_app.py` edit.
- **Claude already has one boundary row** — `("claude", "claude_plan_approval")`,
  with `PLAN_SEL1` / `PLAN_SEL2` / `PLAN_REVISED` fixtures and tests in
  `ClassifyFollowedChangeTests`. That is the shape to copy.
- **The live-wiring harness** —
  `tests/test_minimonitor_concern_smoke.py::FollowedPaneClassificationSmokeTests`
  is already parametrized over agents; its `_case(agent, kind, first, second,
  expected)` helper (line 693) and `setUpClass` loop take a new agent directly.
- **t1474's finding**: `claude_proceed`'s question renders *above* the 6-line
  `_PROMPT_DETECTION_TAIL_LINES` window, so the bottom-anchored `claude_help_bar`
  is what actually matches permission dialogs. Do not re-derive this; confirm it.

---

### Pre-phase (risk mitigations)

1. `[gate_code_on_measured_boundaries]` **The durable artifact is the checked-in
   plan `aiplans/p1540_measure_claude_native_dialog_boundaries.md`** — not the
   agent-private plan file. Step 1's measurement table goes into that file's
   `## Measurement` section with an explicit **B1 / B2 / B3 / B4 verdict per
   (kind, candidate)** — B1–B3 recorded **per geometry**, B4 once per candidate
   across the whole supported set — and is **committed before the first code
   edit**:

   ```bash
   ./ait git add aiplans/p1540_measure_claude_native_dialog_boundaries.md
   ./ait git commit -m "ait: Record t1540 Claude boundary measurement table"
   ```

   The ordering is then provable from git history rather than from a transient
   working-tree observation. Apply the gate against that committed table: a
   candidate with any verdict other than pass — **on any of B1, B2, B3 or B4, at
   any supported geometry** — ships **no** row, and its kind keeps its
   `DELIBERATELY_UNANCHORED_KINDS` entry, rewritten to the *measured* reason.
   There is exactly one authorization rule in this plan and it is B1–B4; any
   instruction that appears to authorize a row on B1–B3 alone is a defect in this
   document, not a laxer path.
   Verify: `git log --oneline -- aiplans/p1540_*.md
   .aitask-scripts/monitor/review_loop.py` shows the measurement commit strictly
   before any `review_loop.py` commit, and every shipped entry maps 1:1 onto a
   passing verdict in that committed table.

2. `[measure_at_production_geometry]` Run the Step 1 protocol at **every** geometry
   in the supported set — 120x30, the post-split compact height, and the measured
   floor — and record a verdict row per (kind, candidate) **per geometry**. 120x30
   alone is not production: a same-window shadow splits the followed pane. **Ship a
   row only if B1–B4 hold at every one of them**; a candidate that fails at any
   geometry is disqualified rather than shipped with a recorded limitation, because
   the table has no geometry dimension to scope it and the failure mode is a
   confident wrong `WORK`, not a safe `UNKNOWN`. If no candidate holds everywhere,
   ship no row and keep the exemption with the measured reason.

---

## Step 1 — Live measurement (scratchpad harness, real Claude)

Per the recipe: private socket `AITASKS_TMUX_SOCKET=t1540meas_$$` (**never** the
`-L ait` gateway), `TMUX`/`TMUX_PANE` scrubbed, 120x30, throwaway repo under the
session scratchpad. Set `AITASKS_TMUX_SOCKET` **before** importing
`monitor.monitor_core` (it is resolved once at import). Capture with the
production argv verbatim — `capture-pane -p -e -t <pane> -S -200` (200 =
`TmuxMonitor.capture_lines`; note the recipe's `-S -15` is a scrollback *floor*,
and these CLIs run on the alternate screen so any `-S` returns the whole visible
pane). Classify through the production seams: `monitor_core.classify_content` for
the kind, `review_loop.classify_followed_change` for the verdict.

Record the live `claude --version` in the table (2.1.233 on this box today).

**Three channels per frame** (recipe step 4), all three recorded, none allowed to
be the sole witness: (A) **harness ground truth** — the driver knows which frame
is at-rest / working / dialog-sel1 / dialog-sel2, and for every selection step
asserts the **raw** capture changed before accepting the frame; (B) **literal
screen evidence** — plain substring searches, not the shipped regexes; (C) the
detector's own verdict. A channel disagreement invalidates the rep.

### 1a — Tool-permission dialog (the kind that matters)

Provoke cheaply and repeatably: ask Claude to run one short `Bash` command that
is not pre-approved (e.g. `touch <scratchpad>/t1540probe_<n>.txt`), so each rep
costs one small turn. **≥5 repetitions.** Per rep capture at least: at-rest,
working, dialog-selection-state-1, dialog-selection-state-2, and
dialog-with-new-output-above. Move the selection with `Down`; assert the raw
frame changed before scoring (the t1518 `Tab`-vs-`Right` incident is the worked
example of a dead keypress being silently recorded as a widget property).

**Measure across the supported geometry set, not one geometry.** 120x30 is *not*
the production geometry:
`tmux.shadow_same_window` defaults to `true`, so spawning the shadow **splits the
followed pane and roughly halves its height** (the smoke test records a 130-row
frame coming back as 65). Both things this task depends on are height-sensitive —
which kind is reported (a short pane can pull `Do you want to proceed?` into the
6-line tail, flipping `claude_help_bar` → `claude_proceed`) and whether the
boundary line is on screen at all (a tall dialog can push it off the top, so
`_native_block_start` returns `None` → `UNKNOWN`, the very failure this task
exists to remove).

This is not hypothetical: `OPENCODE_WORKING_NO_FOOTER_ROOM_RAW` is a **real**
pane-height-6 capture where the working footer is not rendered at all and both
detector brakes fail — a property found only by measuring a constrained geometry,
and its docstring explicitly forbids "fixing" it by recapturing at a normal size.

So run the full ≥5-rep protocol at **both**:

| geometry | why |
|---|---|
| 120x30, unsplit | the t1518 baseline, comparable with the shipped Codex/OpenCode rows |
| 120x**14**, i.e. the post-split height a same-window shadow leaves | the geometry the loop actually runs in |
| the measured **floor** — the smallest height at which the dialog still renders | the last height at which a row can be wrong; below it there is nothing to anchor |

Record, **per geometry**: the reported kind, the boundary index, and the
B1/B2/B3/B4 verdicts.

**Ship rule: a row ships only if B1–B4 hold at EVERY supported geometry.** There
is no "correct where it holds" disposition, because the table cannot express one:
`NATIVE_DIALOG_BOUNDARIES` is keyed `(agent, kind)` with **no geometry dimension**,
so a row measured only at 120x30 is still applied at every height the pane ever
takes. And a geometry where the candidate fails does **not** degrade to `UNKNOWN`:
`UNKNOWN` requires `_native_block_start` to return `None`, i.e. the line is not
found at all. If the line *is* found but B3 fails there, the function returns an
index, `prev_lines[:start_prev] != curr_lines[:start_curr]` is true on a pure
cursor move, and `classify_followed_change` returns **`WORK`** — a confident wrong
answer that opens the work latch and can fire the loop on a selection redraw. That
is strictly worse than the under-detection this task exists to remove.

Dispositions, therefore:

- **holds at every supported geometry** → ship the row; store a fixture trio per
  geometry.
- **fails at any supported geometry** → that candidate is **disqualified**. Try a
  narrower / lower candidate (a line nearer the options, which a short pane is less
  likely to push off screen) and re-run B1–B4 at every geometry.
- **no candidate holds everywhere** → **no row.** The exemption stays, rewritten to
  the measured reason naming the geometry that disqualified each candidate. `UNKNOWN`
  everywhere is the safe outcome and is still a real close of the recorded gap —
  the placeholder reason becomes evidence.

This also removes an internal contradiction in the earlier draft: Step 4b runs at
the split geometry, so a tall-only row could never have reached a 4b `PASS` anyway.

Store the compact captures as `CLAUDE_PERMISSION_COMPACT_*` fixtures, following
the `OPENCODE_*_COMPACT_RAW` precedent — real captures at that height, never
truncations of the tall ones.

**Define the supported set explicitly**, and record it in the table: 120x30
unsplit, the post-split compact height, and a probe at the **smallest height at
which the permission dialog still renders at all**. Below that floor the dialog is
not on screen, so there is nothing to anchor and nothing to get wrong. The repo
already carries a constant of exactly this shape for the same reason —
`_OPENCODE_MIN_LINES_BELOW_BORDER`, shipped by t1520 after a too-short pane broke
a detector — so record the measured floor even though this task adds no guard.

### 1a-bis — The other `claude_help_bar` surfaces (negative-control captures)

`claude_help_bar` is a **generic** kind and its permission-only scope will be
enforced by nothing but the new regex. One non-permission fixture passing proves
only that *that* surface is unanchored; a different help-bar surface whose text
happens to contain the boundary phrase would start anchoring and emitting
`WORK`/`SELECTION_ONLY` on a dialog that was never measured — a false positive in
the direction that actually fires the loop.

So **enumerate the known help-bar surfaces at 2.1.233 and capture one frame each**,
to become negative controls in Step 3:

- the **free-text amend prompt** (`Tab to amend`), including a rep where the
  user-typed buffer itself contains the string `Do you want to proceed?` — the
  quotable-prose false-positive class `prompt_patterns.py` already guards against;
- a **numbered-selection** surface that reports `claude_help_bar` rather than
  `claude_askuserquestion`;
- any **plan-related** surface that reports `claude_help_bar` rather than
  `claude_plan_approval`;
- any further surface observed to report the kind during the 1a reps.

For each, record the reported kind and whether the candidate boundary matches. A
surface where it matches is a **measurement finding that narrows the candidate** —
pick a more specific line and re-run 1c — not something to note and ship past.

**Record which kind the detector actually reports per rep.** `claude_proceed` and
`claude_help_bar` are mutually exclusive by geometry and by first-wins ordering
(`claude_proceed` is listed *before* `claude_help_bar` in
`PROMPT_PATTERNS_BY_AGENT["claude"]`): if `Do you want to proceed?` lands inside
the 6-line tail the reported kind is `claude_proceed`, otherwise it is
`claude_help_bar`. This is the inverse of t1518's
`codex_permission` / `codex_yes_proceed` pair and needs the same explicit
reachability note.

**Also enumerate the permission-dialog variants** rendered at 2.1.233 — Bash /
command, Edit / Write, Read, WebFetch — and check the candidate against each. If
one line does not cover them all, either use an alternation (the shipped
`claude_plan_approval` row is already an alternation, so this is precedented) or
narrow the claim and record which variants remain `UNKNOWN`.

Candidate boundary line to **confirm, not copy on faith**:

| kind | dialog | candidate line |
|---|---|---|
| `claude_help_bar` | tool permission | `Do you want to proceed?` (plus any per-variant wording found live) |
| `claude_proceed` | *same dialog* | same line |

### 1b — Workspace-trust dialog (`claude_trust_folder`)

Costs **zero model turns**: run `claude` in a fresh directory with no trust
record and the dialog renders before any prompt. ≥5 repetitions; move the
selection with `Down`/`Up`.

Candidate: the header line above the two option rows (measure it — likely the
`Accessing workspace:` / `Quick safety check:` wording t1474 recorded). This is a
pre-work gate, so also record whether the review loop can ever be armed while it
is on screen; if the answer makes a boundary meaningless, that is a **measured**
reason for keeping the exemption, which is the real deliverable either way.

> **Writing rule for this dialog, from t1474:** no text matcher can separate the
> trust dialog from a verbatim reproduction of its option block, so the plan, the
> code comments and the docs must describe those two labels **inline in prose,
> never as a copied adjacent two-line block**. Fixtures are data and are exempt.

### 1c — The four questions per candidate

All four gate shipping. B1–B3 are answered **per geometry**; B4 is answered once
per candidate over the whole supported set.

- **B1 — exactly once.** The line matches exactly once in the live capture.
  (`_boundary_index` takes the *last* match, so a stale echo higher in the tail is
  tolerated by construction; B1 is about the live frame.)
- **B2 — only while live.** The line is absent from the at-rest and working
  captures of the same repetition — including a rep whose transcript already holds
  resolved dialogs.
- **B3 — always above the change.** Its index is strictly less than the index of
  every line that differs between selection state 1 and 2. If the stripped frames
  turn out byte-identical (selection drawn purely as ANSI styling, as OpenCode
  does), record B3 as **`vacuous`**, not as a pass, and say so.
- **B4 — never confidently wrong (new in t1540, and the one that gates shipping
  across geometries).** At **every** supported geometry, the candidate must yield
  either the correct verdict or `UNKNOWN` — never a wrong confident one. The
  disqualifying observation is a selection pair classifying `WORK`: that means the
  line was located but sits at or below something that moves during selection, so
  the row would fire the loop on a cursor keypress. B4 is not implied by B1–B3
  measured at one geometry, because B1–B3 are per-frame properties and this is a
  property of the *set* of supported geometries. Record B4 as a single pass/fail
  per candidate, with the geometry that decided it.

### 1d — Positive control that the gap is real

For each measured pair, record the verdict **today, with no row shipped**: the
selection pair and the work pair must both classify `unknown`. Without this the
"after" numbers prove nothing.

### 1e — Record the table

Write the results into a `## Measurement` section of
`aiplans/p1540_measure_claude_native_dialog_boundaries.md` in t1518's format —
one row per (kind, candidate) **per geometry** with line, index, B1/B2/B3
verdicts, reps and CLI version, plus a **B4 verdict per candidate** (one pass/fail
across the whole supported set, naming the geometry that decided it) — plus the
per-capture violation totals across **every** frame taken, not only the analysed
reps. The table schema is therefore:

| kind | geometry | candidate line | index | B1 | B2 | B3 | reps | B4 (per candidate) |
|---|---|---|---|---|---|---|---|---|

A candidate with no B4 cell is **unshippable**, exactly as one with a missing B1.
Commit the table before any code edit (pre-phase gate above).

## Step 2 — Boundary rows (`.aitask-scripts/monitor/review_loop.py`)

Add rows **only** for (kind, candidate) pairs with a passing **B1–B4** verdict in
the committed table — B1–B3 passing at **every** supported geometry and B4 passing
for the candidate. B1–B3 alone is **not** sufficient authorization: they are
per-frame properties, and B4 is the one that catches a boundary located below a
moving line, which classifies a selection redraw as `WORK` and fires the loop
spuriously. Each row carries a provenance comment naming the CLI version, geometry,
capture date, task id and measured index — matching the `_CODEX_EXEC_APPROVAL_RE`
/ `_OPENCODE_PERMISSION_RE` house style. Shape:

```python
# Claude's tool-permission dialog header, measured live <date> against
# <version> at 120x30 (t1540): index <n>, exactly once per live frame, absent
# from at-rest and working frames.
#
# SCOPED BY MEASUREMENT, not by omission. `claude_help_bar` is Claude's generic
# blocked-on-input footer and also fires for the free-text amend prompt and
# other numbered selections; only the permission dialog was measured, so this
# boundary anchors only that dialog and every other help-bar surface still
# returns None -> UNKNOWN, exactly as before this row. That is the conservative
# default, unchanged — not a rotted literal. See t1542.
_CLAUDE_PERMISSION_RE = re.compile(r"...")
```

Then, in `NATIVE_DIALOG_BOUNDARIES`, `("claude", "claude_help_bar")` and — if its
verdict passed — `("claude", "claude_proceed")` mapped to the same object (the
`codex_yes_proceed` precedent: same dialog, same evidence; ship it even if the
kind proved unreachable, and record the non-reachability so the row is not later
mistaken for measured-live).

`NATIVE_DIALOG_STRATEGIES` stays defined and empty of Claude — no shape-delimited
candidate is expected here, but if one emerges the t1518 branch rule applies
verbatim: exactly one mechanism carries the key, decided by the measurement.

In `DELIBERATELY_UNANCHORED_KINDS`, **remove** each entry now carrying a row, and
for anything still exempt replace `"no measured boundary (pre-t1518)"` with the
measured reason and the task id. Leaving a kind in both tables would not fail the
guard (`_resolves` treats them as alternatives) — it would simply be a lie.

## Step 3 — Unit tests (`tests/test_review_loop.py`, `tests/review_loop_fixtures.py`)

Add the live captures to `review_loop_fixtures.py` as
`CLAUDE_PERMISSION_SEL1_RAW` / `_SEL2_RAW` / `_LATER_RAW` (and the trust trio if
that row ships), at **full captured extent** — the followed-pane rule, not the
`CODEX_*` trim-to-15 shadow habit — with a provenance paragraph in the module
docstring naming agent, version, date, socket, geometry, and which no-fire
mechanism Claude uses.

Extend the existing classes; do not duplicate them. Per (kind, dialog) ship the
4-part unit `NativeDialogBoundaryTests` already uses:

1. **No-fire direction** — `SEL1`→`SEL2` is `SELECTION_ONLY` (glyph cursor) or
   `NO_CHANGE` (styling-only cursor). Which one is asserted is itself a measured
   property, not "either is fine".
2. **Work direction** — `SEL1`→`LATER` is `WORK`. This is the direction the row
   exists for; the no-fire direction alone proves nothing because `UNKNOWN` would
   pass it.
3. **Fixture premise control** — for a glyph cursor,
   `assertNotEqual(strip(SEL1), strip(SEL2))`; for a styling-only cursor,
   `assertNotEqual(SEL1, SEL2)` **and** `assertEqual(strip(SEL1), strip(SEL2))`.
   This is what stops a dead keypress from making assertion 1 vacuous.
4. **Mechanism pinning** — exactly one of the two tables carries the key.

`ConservativeDefaultSurvivesTests.test_claude_unanchored_kinds_still_classify_unknown`
(`tests/test_review_loop.py:1612`) currently **asserts the gap** and will fail. It
is a characterization of the defect, not an invariant: rewrite it to the flipped
truth — each kind that gained a row now classifies through its boundary, each kind
still exempt still classifies `UNKNOWN` — so both directions stay pinned rather
than the assertion simply being deleted.

`ArmedAgentKindCoverageTests` needs no edit: removing an exemption while adding a
boundary keeps it green by construction. Its three negative controls are unchanged
and must stay green.

**Scope-enforcement tests — one per known help-bar surface (not one sample).**
From the 1a-bis captures, add a fixture and an assertion per surface: the amend
prompt (including the variant whose typed buffer contains `Do you want to
proceed?`), the numbered-selection surface, the plan-related surface. Each must
assert `_native_block_start(...) is None` **and** that a change under
`claude_help_bar` on that frame classifies `UNKNOWN`. Asserting only the second
would pass vacuously if the frames happened to be stripped-identical
(`NO_CHANGE` returns before any boundary lookup), so both are required.

Drive these as a table so a future surface is one row, not a new test — and pin
the table's own completeness with a premise assertion that it covers every
non-permission surface the measurement enumerated.

**Compact-geometry tests.** A shipped row holds at every supported geometry by the
Step 1a ship rule, so add the compact `SEL1`/`SEL2`/`LATER` trio and assert the
same two directions there. (The earlier draft's "assert the compact frames classify
`UNKNOWN`" case is gone: that outcome no longer ships, and the test could not have
been written for the dangerous variant of it anyway — a located-but-misplaced
boundary returns `WORK`, not `UNKNOWN`.)

**B4 invariant test — the one that covers the unsafe case directly.** Table-driven
over **every** stored selection pair, across every agent, kind and geometry:

```python
for name, (prev, curr, kind, agent) in SELECTION_PAIRS.items():
    self.assertIn(rl.classify_followed_change(prev, kind, curr, kind, True, agent),
                  (rl.SELECTION_ONLY, rl.NO_CHANGE, rl.UNKNOWN), name)
```

A pure cursor move must never classify `WORK` — that is the false-positive
direction that fires the loop, and it is the exact symptom of a boundary located
below a changing line. Asserting the *specific* expected verdict per pair (as the
per-row tests do) does not subsume this: it pins each pair individually, whereas
this pins the property for any pair added later, including one added for a
geometry nobody re-checked. Include a premise assertion that the table is
non-empty and covers every geometry in the supported set.

**Negative controls — each applied in isolation, each must fail, and the failing
test id recorded** (a passing negative control is itself a defect; mutate values
in-test, never delete source lines, so the failure is an assertion and not a
`NameError`/`KeyError`):

1. neuter the new Claude boundary regex → the no-fire test fails on
   `SELECTION_ONLY`/`NO_CHANGE` vs `UNKNOWN`;
2. pop `("claude", "claude_help_bar")` from `NATIVE_DIALOG_BOUNDARIES` **without**
   restoring the exemption → the completeness guard fails naming
   `claude/claude_help_bar`;
3. mutate the `LATER` fixture so nothing above the boundary differs → the work
   test fails on `WORK` vs `SELECTION_ONLY`, proving assertion 2 reads the
   above-boundary comparison and not something incidental;
4. **widen the boundary regex** so it also matches the amend-prompt frame → the
   scope-enforcement test fails naming that surface. This is the control for
   concern 3: without it, the scope tests could pass merely because the shipped
   regex is narrow by luck rather than by construction, and nothing would notice
   a later widening;
5. **retarget the boundary regex onto a line that moves during selection** (e.g.
   the option row itself) → the B4 invariant test fails on `WORK` for the selection
   pairs. This is the control proving B4 can actually catch a located-but-misplaced
   boundary, rather than passing because every stored pair happens to be benign.

## Step 4 — Live acceptance

**4a — checked-in live-tmux wiring test.** Extend
`FollowedPaneClassificationSmokeTests` in `tests/test_minimonitor_concern_smoke.py`
to cover `claude`: add `"claude"` to the `setUpClass` agent loop (a fake binary
named `claude` copied from `sys.executable`, window `agent-claude`, its own shadow
window bound via `@aitask_shadow_target`) and add the two `_case(...)` tests —
selection pair → no-fire, output-above → `WORK`. This is what proves
`agent_key_from_pane` and `classify_content` deliver the right arguments, which
the pure unit tests cannot. Observe the three fixture-hygiene traps t1518
recorded, each of which produces a false `WORK`: tmux history persisting across
paints, `\x1b[2J` scrolling the old screen into freshly-cleared history, and a
shadow *split* halving the followed pane's height. No TUI boot — it must stay in
the parallel lane and out of the serial carve-out.

**4b — live arm-and-fire observation.** A real Claude process as the **followed**
pane, a real shadow bound via `@aitask_shadow_target`, arming through the real
`MiniMonitorApp.action_toggle_review_loop` and firing through the real
`ReviewLoopController.tick`, with every tick's work signal classified from a live
`capture-pane`. Record verbatim in the plan's `## Measurement` section:

1. the loop arms with Claude as the followed pane and fires **exactly one**
   automatic round;
2. pure option-cursor movement inside Claude's question widget fires **nothing**;
3. the same for the permission dialog, once the boundary row exists.

Run 4b at the **compact/split geometry** — that is the geometry a same-window
shadow actually leaves, and under the Step 1a ship rule any row that exists has
already passed B1–B4 there, so 4b is testing the live wiring rather than
re-litigating the boundary.

Harness gotchas that produce a *silently wrong* result rather than an error:
**chunk `send-keys`** (a single long literal burst is coalesced — a 78-char prompt
arrived as `518arm.txt`), and **verify the composer is non-empty before Enter** (a
vanished send scores as `fires=0`, which reads exactly like a failed observation).
Both of these turn a harness fault into something indistinguishable from a real
`FAIL`, so neither may be skipped — a `FAIL` verdict is only admissible once both
have been checked.

### 4b is a gate, not a report

**t1518 could afford a soft shortfall; this task cannot.** There, a non-reproducing
observation had a real consequence — the agent stayed out of `REVIEW_LOOP_AGENTS`
and the loop was never armed for it. Claude is *already* in that tuple, so
transplanting t1518's "report the shortfall" sentence would leave it with no teeth
at all: the defect t1540 exists to fix **is** an armed Claude loop that silently
never fires, and 4b is the only evidence that the arm → classify → latch → fire
sequence works end to end. Unit fixtures and 4a's stub-painted panes prove
controlled classifier behaviour; they cannot fail if the real
Claude/shadow/`ReviewLoopController` sequence is broken. Closing t1540 on 4a alone
would be closing it on evidence that cannot see the defect.

So 4b yields exactly one of three verdicts, recorded verbatim in `## Measurement`:

- **PASS** — all three observations reproduce. Proceed to archival normally.
- **FAIL** — the loop observably did not arm, or did not fire, against a real
  Claude pane. This is a **defect, not a partial win**: fix it in-session and
  re-run 4b. If it cannot be fixed in-session, **t1540 does not archive** — it
  stays in-flight (the Step 9 "Defer — keep in-flight" branch), the row's comment
  records that the live path is unproven, and the failure is stated plainly in the
  Final Implementation Notes rather than framed as a shortfall.
- **BLOCKED** — 4b could not be *run* for an environment reason outside the
  session's control (no `claude` binary, no quota, no usable tmux). This is
  **unverifiable, which is not the same as negative** and must not be scored as
  either PASS or FAIL. t1540 archives, but only after a **mandatory**
  manual-verification follow-up is created (the t1541 shape, via Step 8c) carrying
  the three observations as its checklist and recorded in t1540's
  `manual_verification_tasks`. "Mandatory" means it is created, not offered: the
  Step 8c prompt's decline branch is not available for this item.

The distinction is load-bearing: collapsing BLOCKED into FAIL wedges the task on
something the session cannot fix, and collapsing FAIL into BLOCKED ships a broken
end-to-end path behind a follow-up nobody is obliged to run.

## Step 5 — Documentation

- `aidocs/framework/shadow_agent.md` — the "**Known gap, recorded rather than
  closed**" paragraph (lines 1032–1036) is now false. Rewrite it to the post-t1540
  state: which Claude kinds are anchored, what earned them, and — stated plainly,
  not implied — which help-bar surfaces are still unanchored and why that is the
  conservative default rather than a defect. Keep the bidirectional reference: the
  doc names the guard test, the table's comment names the doc.
- Describe the trust-dialog labels inline in prose only (t1474 rule above).
- No website doc change is expected — the user-facing minimonitor how-to text
  t1518 touched describes *which agents* the loop supports, and Claude's support
  is unchanged. Confirm with a grep rather than assuming.

### Post-phase (risk mitigations)

1. `[pin_unanchorable_help_bar_surface]` Add an explicit test asserting that a
   `claude_help_bar` frame that is **not** the permission dialog still classifies
   `UNKNOWN` after the row lands, and state the same scoping in the row's code
   comment. This makes the deliberate partial coverage an **asserted property**
   rather than an unnoticed hole, and pins that adding the row caused no
   behavioural change on the surfaces it does not cover.
2. `[flag_scoped_boundary_for_rot_detector]` At the new row, leave a
   forward-pointing comment for t1542 (boundary-rot observability): a *scoped*
   boundary that fails to anchor on a dialog it was never measured against is
   **expected**, not rot, so t1542's signal must distinguish the two or it will
   fire constantly on `claude_help_bar`. Record the same note in this plan's Final
   Implementation Notes. Do **not** edit t1542's task file — the pointer lives at
   the code its implementer will read.
3. `[live_acceptance_is_a_gate]` Record 4b's verdict as PASS / FAIL / BLOCKED and
   act on it before archival: **FAIL** keeps t1540 in-flight (Step 9 "Defer — keep
   in-flight"), **BLOCKED** mandates the manual-verification follow-up at Step 8c,
   **PASS** archives normally. Confirm both harness gotchas (chunked `send-keys`,
   non-empty composer before Enter) before admitting any FAIL, since either fault
   is indistinguishable from a genuine one.

## Verification

- `python3 tests/test_review_loop.py` — both directions per shipped row, the
  fixture premise controls, the flipped conservative-default test, the
  completeness guard and its three existing negative controls.
- `python3 tests/test_minimonitor_concern_smoke.py` — 4a live wiring for Claude.
- `python3 tests/test_minimonitor_concern_action.py` — unchanged; confirm still
  green (it loops over `REVIEW_LOOP_AGENTS`, which this task does not modify).
- `bash tests/run_all_python_tests.sh` — **read the final stderr verdict line
  only** (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); an earlier
  `Results: N passed` line belongs to one module. Use `set -o pipefail` if piping.
- The **five** negative controls of Step 3, each applied in isolation, each with
  its named failing test id recorded.
- Ordering gate discharged: `git log` shows the `## Measurement` plan commit
  strictly before any `review_loop.py` commit, and every shipped entry maps onto a
  **B1–B4-passing** verdict in that committed table — B1–B3 at every supported
  geometry plus a B4 cell. An entry backed only by B1–B3 is a gate failure, not a
  partially-discharged gate.
- **Geometry gate:** the `## Measurement` table carries a verdict row per (kind,
  candidate) **per geometry** in the supported set, plus the measured floor. Every
  shipped row passed B1–B4 at **every** geometry in that set and has a fixture trio
  and both-direction tests per geometry. A row whose behaviour at any supported
  geometry is unmeasured, or which failed at any of them, does not ship.
- **B4 gate:** the invariant test covers every stored selection pair at every
  geometry and no pair classifies `WORK`; negative control 5 fails when the regex
  is retargeted onto a moving line.
- **Scope gate:** every non-permission help-bar surface enumerated in 1a-bis has a
  fixture and an assertion that it is unanchored, and negative control 4 fails
  when the regex is widened to reach one of them.
- **4b gate:** the verdict is recorded as PASS / FAIL / BLOCKED in
  `aiplans/p1540_*.md`, with both harness gotchas confirmed checked before any
  FAIL is admitted. FAIL ⇒ t1540 does not archive this session. BLOCKED ⇒ the
  mandatory manual-verification follow-up exists and is recorded on t1540. Do not
  archive on a 4b outcome that was never written down.
- `shellcheck` — not applicable (no shell changes).

## Risk

### Code-health risk: medium

- Adds **version-sensitive TUI literals** to a safety-relevant classification
  path; Claude Code UI churn rots them and the failure is silent in production
  (a boundary that stops anchoring returns `UNKNOWN`, so the loop simply never
  fires while the tests keep passing against the stored fixture) · severity:
  medium · → mitigation: t1542 (already spawned by t1518 for exactly this)
- `claude_help_bar` is a **generic** kind, so after this row lands an
  "anchored-but-unlocatable" frame becomes a *normal, expected* state rather than
  a symptom. That partially undermines the premise t1542 is built on, and left
  unflagged would either bury the partial coverage or make t1542's future signal
  fire constantly · severity: medium · → mitigation: inline post-phase
  pin_unanchorable_help_bar_surface, inline post-phase
  flag_scoped_boundary_for_rot_detector
- Shipping a boundary literal that was never actually measured · severity: high ·
  → mitigation: inline pre-phase gate_code_on_measured_boundaries
- The row's permission-only scope is enforced by **nothing but the regex**, so a
  boundary phrase that also occurs on another help-bar surface would emit `WORK` /
  `SELECTION_ONLY` on a dialog never measured — a false positive in the direction
  that actually fires the loop · severity: medium · → mitigation: inline
  post-phase pin_unanchorable_help_bar_surface

### Goal-achievement risk: medium

- The measurement may find **no single line** satisfying B1–B4 across every
  permission-dialog variant at 2.1.233, or may find the reported kind is never
  `claude_help_bar` in practice. Bounded and recoverable — the plan ships what
  passes and records what does not — but the headline outcome could end up
  partial · severity: medium · → mitigation: inline pre-phase
  gate_code_on_measured_boundaries
- A boundary measured only at 120x30 can change kind or move at the **split
  geometry the loop actually runs in** (`tmux.shadow_same_window` defaults to
  `true`). The table has no geometry dimension, so such a row is applied there
  regardless — and the failure is not the safe one: a line still *found* but sitting
  at or below a moving line returns an index, so a pure cursor move classifies
  `WORK` and can fire the loop spuriously, which is worse than the under-detection
  being fixed · severity: high · → mitigation: inline pre-phase
  measure_at_production_geometry
- Every checkable layer (unit fixtures, 4a stub panes) is **downstream of the same
  classifier**, so none of them can fail if the real arm → latch → fire sequence is
  broken. Closing on them alone would close t1540 on evidence that cannot see its
  own defect · severity: high · → mitigation: inline post-phase
  live_acceptance_is_a_gate
- `claude_trust_folder` may prove structurally unanchorable (a pre-work gate the
  loop can never be armed during). The deliverable then becomes a *measured*
  exemption reason rather than a row, which is still a real close of the recorded
  gap · severity: low · → mitigation: none needed (handled inside Step 1b)

### Planned mitigations

> Two entries below (`measure_at_production_geometry`, `live_acceptance_is_a_gate`)
> were added after the disposition prompt, from the user's review concerns. Both
> are recorded **inline** without a second prompt because neither has a spawnable
> form — one is a step of this task's own measurement, the other a closure gate on
> this task — and the user chose the 4b mechanism directly. Flagged here so the
> call is visible at approval rather than silently folded in.

- timing: pre-phase | name: gate_code_on_measured_boundaries | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shipping an unmeasured boundary literal; goal-achievement — no line covers every dialog variant | desc: commit the `## Measurement` table (B1–B3 per geometry, B4 per candidate) to the checked-in plan before the first code edit, and ship a row only for a candidate with a passing B1–B4 verdict in that committed table
- timing: post-phase | name: pin_unanchorable_help_bar_surface | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a generic kind's partial coverage going unnoticed | desc: assert that a non-permission `claude_help_bar` frame still classifies UNKNOWN after the row lands, and state the same scoping in the row's comment
- timing: post-phase | name: flag_scoped_boundary_for_rot_detector | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — t1542's rot signal misreading an expected scoped-anchor miss as rot | desc: leave a forward-pointing comment at the new row distinguishing "scoped boundary, dialog never measured" from "rotted literal"; do not edit t1542's task file
- timing: pre-phase | name: measure_at_production_geometry | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a boundary valid only at 120x30 misbehaving at the split geometry the loop actually runs in, where the table cannot scope it and the failure is a confident wrong WORK rather than UNKNOWN | desc: run the full rep protocol at every supported geometry (120x30, post-split compact, measured floor), record kind + index + B1–B4 per geometry, and ship a row only if B1–B4 hold at all of them; add the B4 invariant test asserting no stored selection pair ever classifies WORK
- timing: post-phase | name: live_acceptance_is_a_gate | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — closing the task on layers downstream of the classifier, which cannot observe the defect | desc: make 4b yield PASS/FAIL/BLOCKED; FAIL blocks archival (task stays in-flight), BLOCKED mandates a manual-verification follow-up recorded on t1540, and neither collapses into the other

**Reassessment after inlining** (risk-evaluation.md Steps 1–2, re-run once against
the augmented plan):

- **Code-health holds at medium.** The pre-phase gate bounds the
  *unmeasured-literal* risk (high severity) to the point where it cannot ship, but
  neither it nor the post-phases remove the residual version-sensitivity of a TUI
  literal — that is observability work, and it is t1542's, not this task's.
- **Goal-achievement holds at medium, but only after augmentation.** On the plan
  as first drafted it was **high**: the geometry gap and the evidence-circularity
  gap were both high-severity, and both were surfaced by review rather than by the
  original evaluation — the first draft measured one non-production geometry and
  let a failed live acceptance pass as a recorded shortfall. Two hard gates
  (`measure_at_production_geometry`, `live_acceptance_is_a_gate`) now make each of
  them block shipping or closure rather than degrade quietly, which is what brings
  the axis down to medium. Recorded rather than smoothed over: the original
  evaluation missed both, and the level it assigned was too low for the plan it
  was assessing.

## Step 9 reference

Post-implementation: merge to `main` (current-branch mode — nothing is cut, so the
merge step is a no-op), run the declared `risk_evaluated` gate via
`./ait gates run 1540`, then archive with
`./.aitask-scripts/aitask_archive.sh 1540`.

## Measurement

Executed **2026-08-17**, per the recipe in `aidocs/framework/shadow_agent.md`
§"Recipe: measuring a new agent's readiness surfaces". Private tmux socket
`t1540meas_main` (never the `-L ait` gateway), `TMUX`/`TMUX_PANE` scrubbed,
throwaway repo under the session scratchpad. Captures taken with the production
argv verbatim (`capture-pane -p -e -t <pane> -S -200`) and classified through the
production seams (`monitor_core.classify_content` for the kind,
`review_loop.classify_followed_change` for the verdict). Version: **Claude Code
2.1.233**, model Haiku 4.5 (the dialog is CLI-rendered; the model is recorded only
for reproducibility). Harness is scratchpad-only and not committed (t1520 standing
decision).

**Three channels per frame** (recipe step 4). (A) harness ground truth — the
driver knows which frame is at-rest / working / dialog-sel1/2/3, asserts the
composer is non-empty **before** Enter, and asserts the **raw** capture changed at
every selection step before accepting the frame; (B) literal screen evidence —
plain substring searches, not the shipped regexes; (C) the detector's own verdict.
**No channel disagreement was observed in any accepted rep.**

Totals across **every** frame taken, not only the analysed reps: **47 dialog
frames / 32 non-dialog frames, 0 B1 violations, 0 B2 violations.** ("Violation" =
a dialog frame not containing the candidate exactly once, or a non-dialog frame
containing it at all. The one deliberate self-reproduction frame — see
"Irreducible limit" below — is excluded and reported separately.)

### Verdicts — one row per (kind, geometry), B4 per candidate

Candidate boundary line for both kinds: **`Do you want to proceed?`**

| geometry | reps | reported kind | cand. index | B1 | B2 | B3 |
|---|---|---|---|---|---|---|
| 120x30 (t1518 baseline) | 5 | `claude_help_bar` | −7 | pass | pass | pass |
| 120x14 (post-split) | 5 | `claude_help_bar` | −7 | pass | pass | pass |
| 120x13 | 1 | `claude_help_bar` | −7 | pass | pass | pass |
| 120x11 | 1 | `claude_help_bar` | −7 | pass | pass | pass |
| 120x9 | 1 | `claude_proceed` | −5 | pass | pass | pass |
| 120x7 | 1 | `claude_proceed` | −5 | pass | pass | pass |
| 120x6 (floor probed) | 1 | `claude_proceed` | −5 | pass | pass | pass |

**B4 (per candidate, across the whole supported set):**

| candidate | B4 before | B4 after the `claude_help_bar` fix | deciding geometry |
|---|---|---|---|
| `Do you want to proceed?` | **FAIL** | **pass** | 120x30 / 14 / 13 / 11 |

### Two rendering regimes, both measured

The dialog is bottom-aligned and survives from **30 rows down to 6**. Two regimes,
split by whether the option list fits:

- **≥11 rows** — full three-option list; the question renders at −7, *outside*
  `_PROMPT_DETECTION_TAIL_LINES` (6), so the bottom-anchored `claude_help_bar` is
  the reported kind. This confirms t1474's structural explanation live.
- **≤9 rows** — Claude truncates the option list to the selected row only, which
  lifts the question to −5, *inside* the tail window. `claude_proceed` is listed
  before `claude_help_bar` and matching is first-wins, so it becomes the reported
  kind — and it is **stable across selection**, because the question text does not
  change.

`claude_proceed` is therefore **reachable in production**, unlike t1518's
`codex_yes_proceed`. Both kinds need the row, and both are measured, not inferred.

### Why B4 failed before: `claude_help_bar` is unstable across the dialog's own states

Measured 5/5 reps at every geometry ≥11 rows: the help bar itself changes with the
selection. With option 1 or 3 highlighted it reads `Esc to cancel · Tab to amend ·
ctrl+e to explain`; with option 2 ("Yes, and always allow …") the amend affordance
is **absent** and it reads `Esc to cancel · ctrl+e to explain`. The shipped regex
`Esc to cancel\s+·\s+Tab to amend` therefore matches options 1 and 3 but **not**
option 2, so that frame reports **no kind at all** (`awaiting_input=False`).

Consequence, measured with no boundary row involved at all:

| transition | kinds | verdict |
|---|---|---|
| option 1 → 2 | `claude_help_bar` → `''` | **`work`** |
| option 2 → 3 | `''` → `claude_help_bar` | **`work`** |
| option 1 ↔ 3 | `claude_help_bar` → `claude_help_bar` | `unknown` |

A pure cursor move already classifies as `WORK` — the spurious-fire direction.
**No boundary row can fix this**: `classify_followed_change` early-returns on
`awaiting_input is not True` and on `prev_kind != curr_kind`, both *before*
`_native_block_start` is consulted. This is a pre-existing prompt-pattern defect,
upstream of the boundary tables, and it is why this task also edits
`prompt_patterns.py` (scope confirmed with the user mid-measurement).

**The fix, measured:** widen the pattern to
`Esc to cancel\s+·\s+(?:Tab to amend|ctrl\+e to explain)`. Verified against live
frames — option 1 `True`→`True`, option 2 `False`→**`True`**, option 3
`True`→`True`, at-rest `False`→`False`. It is **backward compatible** (every line
the old regex matched still matches) and its widening is bounded to the permission
dialog's own states: `ctrl+e to explain` is the command-explanation affordance,
which only that dialog offers.

### Before / after, both directions, all seven geometries

| | selection pairs | work above the boundary |
|---|---|---|
| **before** (shipped patterns, no rows) | `unknown` on 1↔3, **`work`** on any pair crossing option 2 | `unknown` — the gap this task closes |
| **after** (pattern fix + both rows) | **`selection_only`** at every geometry, every pair | **`work`** |

### `claude_trust_folder`: no row — measured, not assumed

The workspace-trust dialog was captured live on a fresh untrusted directory (zero
model turns). It is matched by **nothing** at 2.1.233 — `awaiting_input=False` —
for two independent reasons, either of which alone is fatal:

1. **Wording.** The confirm and cancel options are now rendered as a *numbered*
   list (`❯ 1. …` / `2. …`), while `_TRUST_YES` / `_TRUST_NO` require the label to
   follow the pointer with nothing between and to be the whole line. (Described
   inline per the t1474 rule — never paste the option block.)
2. **Geometry.** The trust screen is the pre-TUI boot screen and renders
   *top*-aligned: measured at 120x30 the option rows sit at −17/−16 and the footer
   at −14, with 13 trailing blank rows, so the entire dialog is outside the 6-line
   detection window. Every one of the last six lines is empty.

Since the kind is never reported, no boundary for it can ever be consulted. It
keeps its `DELIBERATELY_UNANCHORED_KINDS` entry, with the placeholder reason
replaced by this measurement. The pattern rot itself is an **upstream defect**,
recorded for the Step 8b follow-up — it is a detection bug in its own right (an
agent blocked on the trust gate reads as idle), not a boundary matter.

### Irreducible limit, reproduced deliberately

Typing the literal text `Do you want to proceed?` into the dialog's amend box
makes the candidate appear **twice** (−7 and −6). `_boundary_index` takes the last
match, so the typed copy wins, and the reported kind flips to `claude_proceed`
because the typed line is inside the tail window. This is the documented
irreducible reproduction case (`monitor_idle_and_prompt_detection.md`: "a verbatim
reproduction is indistinguishable, so do not write one"), not a defect introduced
here. Recorded, excluded from the violation totals above, and pinned by a test.

### Gate discharge

Every entry shipped in Step 2 maps 1:1 onto a **B1–B4-passing** verdict above.
`claude_trust_folder` failed at the detection stage and ships no row.

### Step 4b — live acceptance: **PASS**

Real Claude process as the **followed** pane, a real Claude **shadow** in its own
window bound via `@aitask_shadow_target`, arming through the real
`MiniMonitorApp.action_toggle_review_loop` and firing through the real
`ReviewLoopController.tick` / `_service_review_loop`, with every tick's work
signal classified from a live `capture-pane` of the followed pane. Private socket
`t1540live`, 120x30, Claude Code 2.1.233 / Haiku 4.5.

| # | observation | result |
|---|---|---|
| 1 | loop arms with Claude as the followed pane and fires **exactly one** automatic round | **pass** — `agent_key='claude'`, armed, `rounds_injected=1`, state `fired` |
| 2 | pure option-cursor movement fires **nothing** | **pass** — `work_seen=False` after 7 ticks of `Down`, nothing injected |
| 3 | the same for the native permission dialog, with the boundary row in place | **pass** — the kind at arm time was `claude_help_bar`, i.e. the dialog is what armed and what was classified |

Observation 2 is the decisive one for this task. The debounce streak reached **7**
(well past `DEBOUNCE_TICKS`) purely from cursor movement, so the *only* thing
holding the fire was the work latch staying closed. Before t1540 stabilised
`claude_help_bar`, a move onto option 2 flipped `awaiting_input` True→False and
`classify_followed_change` returned `WORK`, which would have opened that latch and
fired a spurious round on a keypress.

Two harness faults were confirmed absent before any verdict was accepted, since
either would be indistinguishable from a real failure: `send-keys` was **chunked**
(25 chars) and the composer was asserted **non-empty before every Enter**.

**Sequencing note for anyone re-running this.** The loop debounces on
`awaiting_input AND stale`, so the pane must end *parked at a prompt*; work that
merely scrolls past and returns to an idle composer never satisfies the streak. A
**second** permission dialog is the clean stimulus — the transcript above the
boundary has changed (WORK) and the pane is awaiting input again. Staleness is
switched on only **after** arming: arming while the shadow's feedback is already
stale opens the latch immediately (the keypress *is* the user asking for a round),
which would make the fire unattributable to the boundary. A first attempt that
armed with `stale=False` and answered the dialog into an idle composer recorded
`work_seen=True, state=waiting, rounds=0` — a correct loop, an invalid probe.

Per the `live_acceptance_is_a_gate` mitigation this is a **PASS**, so archival
proceeds normally; neither the FAIL (block archival) nor the BLOCKED (mandatory
manual-verification follow-up) branch applies.

## Post-Review Changes

### Change Request 1 (2026-08-17) — both review concerns confirmed and fixed

- **Requested by user:** (1) the 120x6 geometry carried `LATER = None`, so
  `test_output_above_the_boundary_is_work` skipped it and the shipped
  `claude_proceed` row had **no work-direction assertion at that geometry** — it
  could suppress cursor movement correctly and still fail to notice real output
  in the short-pane regime. (2) `ScopedBoundaryDoesNotOverreachTests` covered only
  a single at-rest frame, so it could not show that the *generic*
  `claude_help_bar` row stays unanchored on the real amend / numbered-selection /
  plan-related surfaces, and it omitted the plan-mandated typed-phrase case. Both
  blocking; both CONFIRMED on inspection.

- **Changes made:**
  - **Concern 1.** Captured a coherent **same-session** 120x6 trio (one pane:
    dialog → `Down` → dialog #2), replacing the two floor-probe frames.
    `CLAUDE_PERMISSION_SHORT_LATER_RAW` is new. Measured at that geometry:
    selection → `selection_only`, work above the boundary → **`work`**. The
    `if later is None: continue` skip is gone, and a new
    `test_every_geometry_carries_a_full_trio` asserts structurally that no
    geometry may opt out of a direction, so the gap cannot reopen by setting a
    fixture back to `None` (negative control 6).
  - **Concern 2.** The scope table now enumerates **eight real captured
    surfaces** — two at-rest, typed, streaming, two numbered-selection widgets
    (`ASKUSER_SEL1`, `CLAUDE_DIALOG_RAW`) and two plan-related
    (`PLAN_SEL1`, `PLAN_REVISED`) — each asserting the reported kind is **not**
    `claude_help_bar`, that `_native_block_start` locates nothing, and that a
    changed frame under a forced `claude_help_bar` kind still classifies
    `UNKNOWN`. The typed-phrase case was added as
    `CLAUDE_AMEND_TYPED_PHRASE_RAW` with its own test pinning the measured
    irreducible behaviour.
  - Two further negative controls (6, 7), bringing the total to **seven**.

- **Files affected:** `tests/review_loop_fixtures.py`,
  `tests/test_review_loop.py`, `tests/test_minimonitor_concern_smoke.py`.

- **A real defect the re-run surfaced.** Retargeting negative control 7 exposed
  that the first version of it **passed** — i.e. proved nothing. Matching is
  first-wins and `claude_help_bar` is listed last, so a surface that already has
  its own earlier pattern (`claude_askuserquestion`, `claude_plan_approval`) is
  protected *structurally*: widening the help-bar regex cannot steal it. Only
  pattern-less frames (at rest, typed, streaming) are actually at risk. The
  control had to be retargeted at one of those to bite, and that asymmetry is now
  documented in the test itself so a future control is not written against a
  shielded surface.

- **A second, unrelated defect fixed.** Adding `claude` to the live-tmux smoke's
  agent loop introduced an `ETXTBSY` race: by that iteration the earlier agents'
  shadow panes are already executing the same `claude` binary, so copying over it
  fails — *racily*, which is why the first run passed and a later one did not.
  The copy is now skipped when the file already exists. Confirmed by two
  consecutive clean runs.

### Measurement addendum — 120x6 work direction

| geometry | selection | work above boundary |
|---|---|---|
| 120x6 (same-session trio) | `selection_only` | **`work`** |

Both directions are now proven at **every** geometry in the supported set, which
is what the Step 1a ship rule requires and what the earlier fixture set did not
actually deliver for the short-pane regime.

### Change Request 2 (2026-08-17) — typed-phrase case was a scope FAILURE, not an edge case

- **Requested by user:** the typed "Do you want to proceed?" fixture was an
  explicit counterexample to the plan's own scope gate. The test asserted that
  `_native_block_start` selects the **user-typed, lower** occurrence rather than
  the real permission header, and there was no selection-pair / B4 assertion for
  that state at all. Blocking; CONFIRMED.

- **Verification of the premise.** The captured layout settles it: the typed text
  lands **inside an option row** — the row reads `❯ 1. Yes, <typed text>` — and
  `_boundary_index` takes the LAST match, so a substring anchor resolves the
  boundary onto a line that **moves during selection**. That is precisely the
  failure B4 exists to forbid, and it is reachable from **user input** rather than
  from CLI churn, because the dialog's option 1 is editable via `Tab`. The earlier
  test documented that hole instead of closing it.

  It is worth being explicit that the previously-shipped behaviour was not merely
  theoretical-but-safe: the typed selection pair happened to classify
  `selection_only` only because the comparison slice `lines[:start]` **excludes
  the boundary line itself**, so the moving line was skipped by accident of
  layout. Nothing about that is a property; a copy whose index shifts between two
  frames yields different `start_prev` / `start_curr`, unequal slices, and a
  spurious `WORK`.

- **Changes made — structural fix, not a documented exception.**
  - `_CLAUDE_PERMISSION_RE` is now a **whole-line** anchor
    (`^\s*Do you want to proceed\?\s*$`). The typed copy is rejected because its
    line carries the option label; the real header still matches. Validated
    against **all 58 captured dialog frames: 0 divergences** from the previous
    substring anchor, so every B1/B2/B3/B4 verdict already recorded still holds.
    This is the same technique, for the same reason, as `claude_trust_folder`'s
    "each option line holds nothing but its label".
  - Captured a **real selection pair in the typed state**
    (`CLAUDE_AMEND_TYPED_SEL1/SEL2_RAW`) — the missing B4 evidence — and added it
    to the `SelectionNeverClassifiesWorkTests` table as a named hostile state.
  - The typed-phrase test now asserts the **safe** outcome: the boundary resolves
    to the whole-line header, and strictly ABOVE the typed copy. Asserted as an
    index identity against the whole-line occurrence rather than a literal, so
    fixture and assertion cannot drift.
  - Negative control **8**: revert the anchor to the substring form → the test
    fails with `25 != 24`, i.e. the boundary lands on the option row.

- **Files affected:** `.aitask-scripts/monitor/review_loop.py`,
  `tests/review_loop_fixtures.py`, `tests/test_review_loop.py`.

- **Disposition:** this is now a closed scope gate rather than an approved
  exception — no exception policy is needed, and the generic help-bar / proceed
  rows ship with the hostile state covered in both directions.

## Final Implementation Notes

- **Actual work done:** Measured Claude's tool-permission dialog live against
  2.1.233 across seven pane geometries (120x30 → 120x6), 5 reps at the two main
  ones, three evidence channels, 47 dialog / 32 non-dialog frames with 0 B1/B2
  violations. Shipped one shared boundary — a **whole-line** anchor on
  `Do you want to proceed?` — for **both** `("claude", "claude_help_bar")` and
  `("claude", "claude_proceed")`, and removed both from
  `DELIBERATELY_UNANCHORED_KINDS`. `claude_trust_folder` keeps its exemption, now
  with a measured reason instead of the `pre-t1518` placeholder. Tests: 13 real
  captured fixtures, a 4-part unit per geometry, a table-driven B4 invariant, an
  8-surface scope table, 3 new live-tmux cases plus `claude` added to the
  app-path arm-and-fire loops, and 8 negative controls. Docs updated in
  `shadow_agent.md` and `monitor_idle_and_prompt_detection.md`.

- **Deviations from plan:** two, both scope-widening and both confirmed with the
  user mid-task.
  1. The plan assumed the task was pure data ("no new mechanism is needed").
     Measurement found that no boundary row could work at all until an **upstream
     detection defect** was fixed, so `monitor/prompt_patterns.py` is in the diff.
  2. The plan's `claude_trust_folder` sub-step expected to ship a row or record a
     "structurally unanchorable" reason. The measured answer was neither: the
     kind is **not reported at all** on 2.1.233, so the exemption is right for a
     reason the plan did not anticipate.

- **Issues encountered:**
  - `claude_help_bar` was anchored on `Esc to cancel · Tab to amend`, but 2.1.233
    drops the amend affordance on the dialog's "always allow" option. That frame
    reported **no kind**, so a pure cursor move onto it flipped `awaiting_input`
    and `classify_followed_change` returned `WORK` — the spurious-*fire*
    direction — short-circuiting ahead of any boundary lookup. Fixed by accepting
    either affordance; strictly backward compatible.
  - Which kind is reported is **geometry-dependent**: ≥11 rows → `claude_help_bar`
    (question outside the 6-line tail); ≤9 rows → Claude truncates the option list,
    lifting the question into the tail, and `claude_proceed` wins first-match. So
    `claude_proceed` is genuinely reachable, unlike t1518's `codex_yes_proceed`.
  - Review found the 120x6 geometry shipped with `LATER = None`, so the
    `claude_proceed` row had **no work-direction assertion** at the only geometry
    where that kind is reported. Closed with a same-session trio (CR1).
  - Review found the typed-phrase case had been **documented rather than closed**:
    the dialog's option 1 is editable, so a user typing the phrase put a copy
    below the header and the last-match rule moved the boundary onto a line that
    moves during selection. Closed with a whole-line anchor (CR2).
  - The first negative control for the scope table **passed**, i.e. proved
    nothing: matching is first-wins and `claude_help_bar` is listed last, so
    surfaces with their own earlier pattern are protected structurally and only
    pattern-less frames can be over-matched. The control had to be retargeted.
  - Adding `claude` to the live-tmux smoke introduced an `ETXTBSY` race (the
    earlier shadows already execute that binary). It passed once and failed
    later — genuinely flaky. Fixed by not re-copying an existing file.
  - The first live 4b attempt recorded `work_seen=True, state=waiting, rounds=0`.
    A correct loop, an invalid probe: the debounce needs `awaiting_input AND
    stale`, so the pane must end **parked at a prompt**, and staleness must be
    switched on only after arming. Re-run with a second dialog as the stimulus.

- **Key decisions:**
  - Fix the upstream pattern rather than ship a row that cannot deliver. A
    boundary row is unreachable behind the `awaiting_input` / kind-change
    short-circuits, so shipping one alone would have been nominal.
  - **Whole-line** anchor, not a substring. The dialog's option rows are editable,
    so a substring anchor lets user input relocate the boundary onto a moving
    line. Verified identical on all 58 dialog frames, so it costs nothing.
  - Ship `claude_proceed` on measured reachability, not on the t1518
    `codex_yes_proceed` "ship it anyway" precedent — here it was observed live.
  - Keep the row **scoped** to the permission dialog and assert that scope over
    eight real surfaces, rather than widening to cover every help-bar screen.

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/prompt_patterns.py:118-120 — claude_trust_folder no longer matches Claude Code 2.1.233's workspace-trust dialog, so an agent blocked on the trust gate reads as IDLE in ait monitor / minimonitor. Two independent causes, either fatal alone: the confirm/cancel options now render as a numbered list, which the adjacency pattern cannot match, and the pre-TUI trust screen draws top-aligned (options at -17/-16, footer at -14, 13 trailing blank rows) so the whole dialog falls outside _PROMPT_DETECTION_TAIL_LINES. The existing unit tests still pass because they exercise synthetic snippets in the old geometry. Out of scope for t1540, which is about native-dialog boundaries; recorded live and indexed here.`

- **Coordination note for t1542 (boundary-rot observability):** `claude_help_bar`
  is a *generic* kind whose boundary is deliberately scoped to one dialog, so
  "anchored kind, boundary did not locate" is a **normal, expected** state for it
  rather than evidence of rot. A rot detector that does not distinguish "scoped
  boundary, dialog never measured" from "shipped literal stopped matching its own
  dialog" will fire continuously on this row. The forward pointer lives in the
  comment on `_CLAUDE_PERMISSION_RE`, at the code t1542's implementer will edit;
  t1542's task file was deliberately not modified.
