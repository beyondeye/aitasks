---
Task: t1520_shadow_readiness_detector_for_opencode.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1520 — Shadow readiness detection for an OpenCode shadow

## Context

Minimonitor's `L` auto-recheck loop injects a `refetch and recheck round N` line
into the **shadow** pane when the followed agent settles. Safety contract item 5
forbids injecting into a busy shadow, so the loop needs a **positive** readiness
detector for the shadow's agent — a per-agent classifier over the raw
(ANSI-carrying) 15-line tail `monitor_core.capture_raw_tail` reads.

t1509 generalized that classifier (`review_loop._composer_state`), added the
`SHADOW_*` verdict vocabulary, `shadow_state()`, the wall-clock settle latch, and
the `codex` entry — then deliberately **split OpenCode out** into this task,
because its composer is a structurally different widget deserving its own live
evidence and its own review.

Today the tables ship `claude` and `codex` only, so a user who presses `E` to
give a Claude followed pane an **OpenCode** shadow — a real, supported pairing —
gets a visible refusal: *"shadow agent 'opencode' has no readiness detection
yet"*. This task closes that gap.

**Scope boundary:** this is the **shadow**-pane detector table.
`REVIEW_LOOP_AGENTS = ("claude",)` gates the **followed** pane and stays
untouched (`review_loop.py:499-508`); `test_wired_agents_are_still_not_loop_supported`
must keep passing.

## Measured facts handed forward from t1509 (opencode 1.18.18) — do not re-derive

- The composer is a **`┃`-gutter box**, not a glyph+text line. Positive anchor =
  the box's `╹▀▀▀…` **bottom border** + the composer status row
  (`Build · <model> · <effort>`).
- The permission dialog **replaces** the box (no border, no status row) — but it
  is **also** a `┃`-gutter box **containing blank gutter rows**, so a naive
  "a blank `┃` row exists ⇒ ready" rule false-positives on it.
- The gray placeholder hint (`Ask anything...`) is **not durable**: present on a
  fresh session, **gone after the first turn**. It cannot be the positive anchor.
- Working = blank composer box + an `⬝⬝⬝⬝ esc interrupt` footer. At-rest and
  working are **indistinguishable inside the box**; the footer is the only
  discriminator.
- **No SGR-dim anywhere** in the composer (the hint is truecolor gray
  `38;2;128;128;128`), so `_DIM_SPAN_RE` does **not** transfer.
- `PROMPT_PATTERNS_BY_AGENT["opencode"]` already carries two live t1467 patterns
  for the negative half: `opencode_question`, `opencode_permission`.

**Free finding, verified while planning:** the shipped t1467 fixtures in
`tests/test_prompt_detection.py:534-546` already render the gutter **indented**
(`  ┃  …`) and already contain **blank `  ┃` rows** in the permission dialog. So
(a) every row regex must be `^\s*┃`, not `^┃`, and (b) the blank-gutter negative
control is provably non-vacuous *before* the live session starts.

## Key files

| file | change |
|---|---|
| `.aitask-scripts/monitor/review_loop.py` | `_ordered_state` extraction, `_OPENCODE_*` constants, `_opencode_box_state` / `_opencode_state` / `_opencode_ready`, both dispatch tables |
| `tests/review_loop_fixtures.py` | `OPENCODE_*_RAW` fixtures + provenance docstring |
| `tests/test_review_loop.py` | 3 new classes; retarget `:474` |
| `tests/test_minimonitor_concern_action.py` | synthetic-key retarget of `_SHADOW_LIST_OPENCODE`'s **three** consumers; new opencode-arms cases |
| `aidocs/framework/shadow_agent.md` | **four** passages + the measurement recipe |

---

## Pre-phase (risk mitigations)

1. `[characterize_composer_state_before_extraction]` **Before** extracting
   `_ordered_state` out of `_composer_state`, run and record the current verdicts
   of `tests/test_review_loop.py::ShadowPromptReadyTests`,
   `::CodexShadowReadinessTests` (esp. `test_state_verdicts_per_fixture`),
   `::CodexIsolatedPositiveHalfTests` and `::CodexDetectorNegativeControlTests`,
   confirming they are green **against the unmodified module first**. Three of
   those call `_composer_state` directly with mutated regexes, so they are a real
   characterization baseline rather than a shape the refactor authored.

2. `[measure_opencode_settle]` **Measure the post-interaction settle window in
   wall-clock seconds, before confirming the guard it sizes.** Drive a live
   `opencode` pane on a **private tmux socket** (`AITASKS_TMUX_SOCKET=t1520meas`
   — never the live `-L ait` server), 120x30, in a throwaway repo under the
   scratchpad. Sample every **0.25 s** for ~15 s per rep using the **production
   argv verbatim** (`capture-pane -p -e -t <pane> -S -15`), stamping each capture
   with `time.monotonic()`.

   **≥ 5 repetitions each**, of four interaction kinds:
   - permission dialog, **granted** (*Allow once*) — the normal dialog→work path;
   - permission dialog, **rejected** (*Reject*) — the pathological
     **no-work-follows** case, which is what proves the deadline is the only
     release;
   - question widget (an option submitted) — if OpenCode will not produce one on
     demand, **record the null and say so**;
   - a plain turn with no interaction — measures the Enter→footer-appears gap,
     which for OpenCode is the risky one, since at-rest and working are identical
     inside the box.

   Classify every capture through the **prototype `_opencode_state`** imported
   from the working tree, not an ad-hoc regex in the harness. t1509 found two
   real defects that way (the unanchored `esc to interrupt`, and working-before-
   dialog ordering) and both would otherwise have shipped; it doubles as a live
   smoke test before any fixture is frozen.

   **…but the prototype must never be the only witness.** A missed or overly
   narrow `_OPENCODE_WORKING_RE` would label working output READY, and the
   measurement would then report "no injectable window" *because the detector is
   broken* — the detector validating itself. Record, per sample, **two
   independent channels** beside the prototype verdict:

   - **Harness-derived ground truth** — the driving script knows when it pressed
     Enter and when the turn completed, so each sample carries a
     `working|idle|dialog` label derived from the harness's own actions, not from
     the screen at all.
   - **Literal screen evidence** — plain substring searches (not the shipped
     regexes) for the footer glyph run, the border glyph, and the status row's
     separator, over the raw capture.

   **Reconciliation is a hard check, not a note.** Any sample where a channel
   says *working* while the prototype says `READY` is a **detector defect**, and
   the measurement is **invalid until the detector is fixed and the affected reps
   re-run**. Keep the raw captures on disk for the session so every number can be
   re-derived without another live run.

   **Metric — adopt t1509's mid-measurement refinement, do not re-derive it.**
   The naive "gap from the interaction leaving the screen to the working
   indicator appearing" measured zero on its first pass. The decidable quantity:

   > the **longest run of consecutive byte-identical `ready` captures that is
   > later followed, in the same repetition, by a `working` capture** — i.e. an
   > interval in which the loop would have seen ready **and** hash-stable while
   > work was still coming.

   Discount the **t+0 pre-submit artifact** (the sample taken before the pane
   repainted after Enter); t1509 saw exactly one 0.25 s sample of that shape per
   rep and correctly excluded it.

   **Pre-registered sizing rule, written down before looking at the numbers so a
   null cannot be reinterpreted afterwards:** `SHADOW_SETTLE_SECONDS` must be
   ≥ `ceil(max_observed_injectable_run) + 1.0 s`. If `max ≤ 1.0 s` — **including
   the null case** — the shipped `2.0` already satisfies it and this task ships a
   *confirmation*, which is what the acceptance criterion asks for.

   **If `max > 1.0 s` — STOP HERE. This is an approval boundary, not a Step-8
   note.** `SHADOW_SETTLE_SECONDS` is **one shared constant** across all three
   agents. The two remedies are not comparable in scope: raising the shared floor
   is a one-line change, while making it per-agent introduces a **third dispatch
   table** and changes the shared latch architecture in
   `minimonitor_app._apply_shadow_settle_latch`, with its own verification scope
   (every clock-driven latch test, plus any absolute-second assertion). Deciding
   that at Step 8 would mean the code and tests were already written against an
   unapproved architecture.

   So on that result: write `### Pre-phase RESULTS`, **do not proceed to Phase
   1**, present the measurements, and re-enter planning to amend this plan —
   choosing the remedy and its test scope — before a single line of
   `SHADOW_SETTLE_SECONDS` or any per-agent table is touched. The user's
   "decide with the data in hand" still holds; the boundary is simply where the
   decision can still change the implementation rather than audit it.

   Record **every raw number** per-rep in `### Pre-phase RESULTS`, as a
   `interaction | reps | longest injectable ready-run | notes` table.

   **Contention caveat:** several agent sessions run concurrently on this box.
   Record the 1-minute load alongside the numbers; a loaded box inflates render
   latency, biasing the measurement *upward* (fail-safe, but it must be visible
   rather than silent).

3. `[measure_opencode_working_hash_stability]` **From the same capture stream**
   (no extra live session), answer the two questions that decide risk **G1**:

   1. **Is the working state ever byte-identical across two consecutive 0.25 s
      captures?** Claude and Codex each have a *second, independent* brake — their
      working states are animated and therefore hash-unstable, so
      `shadow_prompt_ready`'s `hash_stable` conjunct refuses them even if the
      working regex misses. Whether OpenCode has that brake is **unmeasured**. If
      it never goes byte-identical, `hash_stable` is a genuine second conjunct.
      If it can, G1 goes **high** and the conditional after-task fires.
   2. **Where does the `⬝⬝⬝⬝ esc interrupt` footer render, relative to the pane
      bottom and to the composer box?** Record `max_footer_distance_from_bottom`
      and whether the footer is consistently **below** the box's status row.

      The window is **bottom-anchored** (`capture-pane -S -15` with no `-E`
      captures from 15 lines back *to the last line*), so the footer escapes only
      when the box grows tall enough — a multi-line composer, a wrapped status
      column — to push it past the 15th line from the bottom.

      **If it can escape, that is a PRE-SHIP BLOCKER, not a follow-up.** A
      working OpenCode shadow would read `READY` with no UI drift at all, and the
      loop would inject into it — precisely the failure this feature exists to
      prevent. Do **not** ship the detector and defer the fix to
      `harden_opencode_working_detection`; that task exists for the *hash-
      stability* half of G1, not this one. Resolve it in this task by one of
      three named remedies, decided from the measurement:

      - **Make it observable** — raise the capture depth for this agent
        (`capture_raw_tail`'s `lines` is already a keyword parameter, so this is a
        per-agent argument at the call site, not a new mechanism), sized from
        `max_footer_distance_from_bottom` plus margin.
      - **Add an independent working signal** — a second in-window indicator that
        does not depend on the footer's position.
      - **Fail closed** — the window-sufficiency guard in Phase 1 step 4b, which
        returns `SHADOW_UNKNOWN` (⇒ not-ready) whenever the captured window
        cannot rule out an off-window footer.

      The fail-closed guard **ships regardless of the measurement**: it is the
      structural backstop, and its regression test (Phase 2 step 11.8) is
      constructible today by truncating a real working capture. The measurement
      decides only whether one of the first two remedies is *also* required.

   3. **Ordinary idle geometry — the guard's availability half.** A fail-closed
      guard is only safe if it does not fire on the normal case; if it did, every
      ready OpenCode pane would read `UNKNOWN`, the loop would **never fire**, and
      there would be no error and no banner to say why. Record the **idle gutter
      run height** (how many `┃` rows a resting composer box occupies) and the
      resulting **headroom** — lines between the top of the box and the top of
      the 15-line window.

      Measure it at the production geometry **and at a narrow width**, since a
      narrow pane is the realistic trigger: OpenCode wraps a right-hand status
      column into the same physical lines, so a narrow shadow split makes the box
      taller. (A shadow pane runs narrow by construction — t1187 hit exactly this
      class of problem from the other side.)

      **Criterion:** if normal idle geometry leaves less headroom than the
      footer's measured maximum offset needs, the 15-line depth is inadequate for
      OpenCode and the capture depth must be raised — the same remedy as the
      footer case, chosen from measurement rather than discovered later as "the
      loop mysteriously never fires". Record the numbers either way; Phase 2 step
      11.10 asserts the fixtures stay READY-eligible.

4. **Fixture harvest, in the same session** (ordinary plan work, not a
   mitigation — it rides the same live session because the captures and the
   timings must come from one run). Freeze these raw, ANSI preserved,
   trimmed to the last 15 lines exactly as the `CODEX_*` fixtures are:
   `OPENCODE_AT_REST_FRESH_RAW` (gray hint present),
   `OPENCODE_AT_REST_AFTER_TURN_RAW` (**the durable case**),
   `OPENCODE_TYPED_RAW`, `OPENCODE_WORKING_RAW`, `OPENCODE_PERMISSION_RAW`,
   `OPENCODE_QUESTION_RAW`, `OPENCODE_BOOT_RAW` (for the `esc interrupt`
   false-positive control), and `OPENCODE_PERMISSION_WITH_WORKING_RAW` **if that
   state occurs live**.

   Deliberately **no bare `OPENCODE_AT_REST_RAW`** — the two at-rest states
   differ enough that nobody should be able to reach for "the" at-rest fixture
   without choosing one.

   **Where a state does not occur, record the null and drop its test.** Never
   synthesise a fixture to keep a test alive: a fabricated capture proves nothing
   about OpenCode.

### Pre-phase RESULTS (measured 2026-08-16, opencode 1.18.18 / GPT-5.4, 120x30 on a private tmux socket)

**Pre-1 `[characterize_composer_state_before_extraction]`** — 20 tests green
against the **unmodified** module (`ShadowPromptReadyTests`,
`CodexShadowReadinessTests`, `CodexIsolatedPositiveHalfTests`,
`CodexDetectorNegativeControlTests`). Per-fixture verdicts recorded as the
comparison baseline: Claude at-rest `ready` / dialog `dialog` / streaming
`working` / typed `busy`; Codex at-rest `ready`, typed `busy`, working
`working`, permission / permission-with-running / question / update-prompt all
`dialog`.

**Pre-2 `[measure_opencode_settle]`** — 15 turn-level reps, 0.25 s sampling,
18 s per rep, ~71 samples per rep (~1070 samples total). Load average 1.83 at
start, 3.20 at end.

| interaction | reps | longest injectable ready-run | notes |
|---|---|---|---|
| plain turn (no interaction) | 5 | **0.00 s** | `busy` (t+0 pre-submit artifact) → `working` → `ready`, byte-identical thereafter |
| permission dialog, granted | 5 | **0.00 s** | 5/5 reached a real dialog; `working → dialog → working` **directly**, with no `ready` sample in between |
| permission dialog, rejected | 5 | **0.00 s** | 4/5 reached a real dialog; `working → dialog → ready` **permanently** — the no-work-follows case |

**Result: no injectable window reproduced across 15 turn-level repetitions.**
Per the pre-registered sizing rule `max (0.00 s) ≤ 1.0 s`, so
**`SHADOW_SETTLE_SECONDS = 2.0` is CONFIRMED UNCHANGED** and the
amended-plan approval stop did **not** trigger. As in t1509, the null result
does not cancel the latch: the `perm_reject` rows are the pathological case
(after a rejected dialog no work ever follows), which is exactly what makes the
latch's **monotonic-deadline release** load-bearing — a latch clearable only by
a `WORKING` observation would wedge there permanently.

**Channel reconciliation: 0 defects.** Across every sample, literal
`esc interrupt` presence (channel B) and the prototype verdict (channel C)
agreed in both directions — no sample was labelled `ready` while the literal
evidence said working, and none `working` without it. The prototype was
therefore not validating itself.

**Pre-3 `[measure_opencode_working_hash_stability]`**

1. **Working-state hash stability — `hash_stable` IS an independent second
   brake.** At normal geometry the longest run of consecutive byte-identical
   `working` captures is **1 sample (0.25 s)**: the `■■■■⬝⬝⬝⬝` footer animates,
   so a working pane is never hash-stable. This matches Claude and Codex, so
   the conditional after-task **`harden_opencode_working_detection` does NOT
   fire** — with the one exception folded into the guard below.
2. **Footer position — it never escapes the capture.** The working footer
   renders **exactly 1 row below the box's bottom border** in **all 287**
   captures that contain it (min = max = 1).
3. **Idle geometry.** The empty composer box is a fixed **4 gutter rows** (3
   content + 1 status) at widths 120 / 60 / 40 and heights 30 / 10 / 8 / 7 / 6.
   Headroom *above* the box is never the constraint (17–22 lines at production
   heights).

#### Correction 1 — `capture_raw_tail` does not read a 15-line window

`capture-pane -S -15` carries **no `-E`**, so it captures from 15 lines back to
the **bottom of the visible pane**. OpenCode is an alternate-screen TUI
(measured: `alternate_on=1`, `history_size=0`), so there is no scrollback at all
and the capture is the **entire visible pane** — 30 lines at 120x30 — for any
`-S` value (verified identical at `-S -15`, `-5`, `-0`). The "15" is a floor on
scrollback depth, not a cap on the capture.

This falsifies the premise the task's acceptance criteria inherited from t1509
("trim each to the 15-line window `capture_raw_tail` actually reads").

#### Correction 2 — fixtures are stored at full captured extent, not trimmed to 15 lines

Trimming to the last 15 lines **removes the fresh-session hint row**: measured,
`OPENCODE_AT_REST_FRESH_RAW` trimmed to 15 lines no longer contains
`Ask anything...` at all. The verdict still reads `ready`, but for the wrong
reason — the gray-hint subtraction path never executes — which would make
negative control 11.11.4 (drop `_OPENCODE_HINT_SPAN_RE` ⇒ fresh flips to BUSY)
**vacuous**. Fixtures are therefore stored at the full captured extent, which is
what production actually reads. This honours the acceptance criterion's intent
(a fixture must not pass on content the app would never see) while correcting
its false premise; the AC's literal line count is not met, deliberately and on
recorded evidence.

#### Correction 3 — the real hazard, and the corrected window guard

The planned guard ("the gutter run reaches the first captured line") **never
fires**: `box_top` is ≥ 1 even at pane height 6. But the hazard it was meant to
catch is **real and was reproduced live**:

At **pane height 6** there is no room below the border, so the working footer is
**not rendered at all**. The composer box still reads empty ⇒ verdict `READY`,
and the capture is **byte-identical for 15+ consecutive samples** ⇒
`hash_stable` is also true. **Both brakes fail simultaneously and the loop would
inject into a working shadow.** Confirmed against an **independent, non-screen
channel**: the opencode process tree's CPU time rose `00:01:05 → 00:01:07` across
the samples, and the turn demonstrably completed (`DONE` reached).

Boundary pinned in **both** directions with live turns:

| pane height | lines below border | footer rendered | verdict while working |
|---|---|---|---|
| 8 | 2 | yes | `working` ✓ |
| **7** | **1** | **yes** | **`working` ✓** |
| **6** | **0** | **no** | **`READY` ✗ (hazard)** |

**Corrected guard: a would-be `READY` requires ≥ 1 line below the box's bottom
border; otherwise the footer could not have been shown, and the verdict is
`SHADOW_UNKNOWN`.** The threshold is the measured footer offset (exactly 1),
not a guess. This supersedes the Phase-1 step 4b trigger as written; the
regression test (11.8) and the availability test (11.10) still apply, retargeted
onto this condition.

#### New finding — an open command palette is a false `READY` (fix approved in-task)

`ctrl+p` opens OpenCode's command palette as an **overlay**: the composer box is
still rendered intact below it, so the positive half passes and the verdict is
`READY`, while Enter would run whatever command is selected. It matches
**neither** existing `opencode` pattern (`opencode_question`,
`opencode_permission`).

Anchor chosen following `prompt_patterns.py`'s own convention (geometry, not a
quotable phrase): the palette header row's label plus its right-aligned dismiss
hint. Scanned over the **entire corpus of 1130 live captures**, it matches
**exactly the 3 palette captures and nothing else** — zero false positives, and
it holds while the palette is being filtered.

Per the user's decision this is fixed in-task by adding an `opencode_palette`
entry to `PROMPT_PATTERNS_BY_AGENT["opencode"]`, which the review loop already
consumes as its negative half, and which is independently correct for
followed-pane `awaiting_input` (a palette open genuinely IS awaiting input).

#### Review round 1 — the palette anchor at compact geometry (raised as blocking)

The palette anchor is the header row, which at full size renders ~21 rows above
the bottom, while the window guard permits `READY` down to pane height 7. If a
short pane could **clip the header while leaving the composer intact**, the
negative half would miss a live overlay and an injected Enter would run the
selected command. Measured directly rather than argued.

Captured with the palette open at every ready-eligible geometry — heights 30,
12, 10, 9, 8, 7 at width 100, plus 40x7, 50x7, 60x8 and 40x10. **The header was
visible in every one, and the verdict was `dialog` in every one.** The idle
capture at the same geometries stayed `ready`, so the availability half holds
too.

The mechanism is why, and it is stronger than the concern assumed:

| geometry | composer box | status row | excluded by |
|---|---|---|---|
| 100x30 (full) | present | intact | **the pattern only** |
| 100x7–12 | present | truncated by the overlay | structure **and** pattern |
| 40x7 (narrowest+shortest) | **absent** — the palette replaces it | n/a | structure **and** pattern |

OpenCode draws the palette **centred over** the composer box at compact sizes
rather than above it, so the header cannot scroll off — and overwriting the box
also disrupts the status row and fills a content row, so the structural half
refuses independently. In every geometry where the header *could* clip, the box
is disrupted too.

Pinned by two new fixtures at the minimum geometry —
`OPENCODE_PALETTE_COMPACT_RAW` (100x7, exactly one line below the border, the
tightest that still permits `READY`) and `OPENCODE_AT_REST_COMPACT_RAW` (40x7,
the availability half) — and two tests. The header-visibility assertion is
mutation-sensitive: removing `opencode_palette` fails it. The isolated
"still refused with patterns off" assertion is over-determined at this geometry
(as the permission dialog is) and is labelled belt-and-braces rather than a
control.

#### Review round 1 — `capture_raw_tail`'s docstring contradicted the finding

`monitor_core.capture_raw_tail` still described itself as "deliberately tiny
(default 15 lines) — it reads the prompt area, not the transcript", which is the
exact false belief Correction 1 disproves and is the docstring a future detector
author would read first. Corrected in place to state the real tmux semantics
(`-S -<n>` with no `-E` reads to the bottom of the visible pane; alternate-screen
TUIs have no scrollback, so it returns the whole visible pane) plus the two
consequences that have already bitten: an on-screen marker is always in scope,
and fixtures must not be trimmed to `lines`.

#### Review round 2 — the compact-palette premise selected any pattern

The header-visibility assertion added in round 1 accepted a match from **any**
pattern in `PROMPT_PATTERNS_BY_AGENT["opencode"]`. Only `opencode_palette`
matches that capture today, so the test was not weak in practice — but a future
broad or overlapping OpenCode pattern would satisfy the premise after the header
had disappeared, masking the exact geometry contract the test exists to pin.
Confirmed and fixed rather than deferred: the assertion now checks the header
text directly **and** selects `opencode_palette` **by name**, with a guard so a
rename fails with a clear message instead of an attribute error.

The counterfactual is executable, and was run: with a broad `┃` pattern present
and the palette regex neutered, the old `any(...)` premise evaluates **True**
(masked) while the by-name form evaluates **False** (correctly fails).

Three mutations now fail with the *intended* assertion message —
palette regex neutered (`opencode_palette no longer matches at the minimum
geometry`), palette renamed (`opencode_palette pattern is gone`), and the
masking case (broad pattern added **and** palette neutered).

**Mutation-harness lesson, recorded because it produced a false "ok" twice.**
The first attempt mutated by *deleting* the `PromptPattern(...)` line. That made
the test fail — but with an `ImportError`, not the assertion, so it was failing
for the wrong reason and was not evidence. Mutations must keep the module
importable: neuter the regex (or rename the pattern) rather than removing the
line, and assert on the *failure message*, not merely on a non-zero exit.

The pre-existing Codex `test_dialog_outranks_working_when_both_are_visible`
uses the same `any(...)` shape and is deliberately left alone: its premise is
"some dialog pattern matched", which is what that ordering test actually means.

#### States that did NOT reproduce — recorded as nulls, not fabricated

- **The `opencode_question` widget** (`↑↓ select enter submit esc dismiss`).
  `ctrl+p` yields the command palette instead. `OPENCODE_QUESTION_RAW` is **not**
  captured, and negative control 11.11.6 (`dialog` outranks `working` when both
  are visible) is **dropped** rather than given a synthesised fixture — the
  permission dialog never co-renders with the working footer, because the dialog
  replaces the whole composer/footer region (measured: `esc_interrupt` is false
  in every `dialog` sample).
- **`OPENCODE_PERMISSION_WITH_WORKING_RAW`** — does not occur, for the same
  structural reason. Unlike Codex, OpenCode does **not** keep a working
  indicator on screen while parked at a dialog, so the dialog-outranks-working
  ordering is untestable for this agent and is not asserted.

---

## Phase 1 — the classifier

### The design decision, and why

**Do not force OpenCode into `_composer_state`.** Its contract
(`review_loop.py:384-437`) is single-line and one-character-glyph by
construction: `composer_re.match(line)` on one plain line, then
`line[1:].strip(pad)` — literally "drop the first character, strip the pad".
OpenCode's positive anchor is a **multi-line relationship** (a `╹▀▀▀…` bottom
border, the contiguous `┃` rows above it, a `·`-separated status row below).
Expressing that through `composer_re` would need a multiline regex over the whole
tail, which breaks the `line[1:]`/`pad` semantics, breaks `option_row_re`, and
would silently distort the Claude/Codex path. The task forbids exactly that.

**But do not duplicate the ordering either.** The order — dialog patterns →
structural positive → `working` only outranks a would-be `ready` — is the
*measured, cross-agent, load-bearing* invariant (t1509 finding 2). Copying those
seven lines into a sibling is how it drifts.

So: **extract the order into one shared helper and make the positive half
pluggable.**

1. Add `_ordered_state(raw_text, *, agent, positive, working_re)` carrying the
   empty-input guard, the negative-pattern sweep, the call to `positive(raw_text,
   plain)`, and the working promotion. Its docstring keeps t1509's "order is
   load-bearing" paragraph verbatim — it is now the single home of that rule.

2. `_composer_state` **keeps its signature verbatim** (three existing negative
   controls call it directly with mutated regexes) and delegates: its bottom-up
   glyph scan becomes the `positive` closure, its head/tail become
   `_ordered_state`. Behaviour change for claude/codex: **none**, pinned by the
   Pre-1 baseline.

### Constants

All beside the Claude/Codex block, each with a provenance comment naming version
+ date (the maintain-in-place practice). **The shapes below are the measured
structure; pin the literal codepoints and separators from the Pre-phase captures
before shipping.**

- `_OPENCODE_GUTTER_RE` — `^\s*┃(.*)$`. **Leading `\s*` is mandatory** (the
  gutter is indented) and nothing anchors on `$` — OpenCode wraps a right-hand
  status column into the same physical lines, the same reason `opencode_question`
  uses `\s+` runs rather than fixed double spaces.
- `_OPENCODE_BOX_BOTTOM_RE` — `^\s*╹▀{3,}`. **The** structural anchor.
- `_OPENCODE_STATUS_ROW_RE` — the composer status row. The mode token must stay
  generic (it is user-switchable: build/plan), but **generic must not mean
  permissive**: `^\s*\w+\s+·\s+\S+` would match a large family of `·`-separated
  OpenCode rows, and turning a future widget row into a READY anchor is exactly
  the failure the anchor exists to prevent. Pin the **full measured multi-field
  grammar** instead — the exact field count and the shape of each field
  (mode token, model identifier, effort token), whole-row, with the separator
  runs as `\s*·\s*` for the reflow reason `opencode_question` documents. The
  precise field shapes come from the Pre-phase captures; the *requirement* is
  that a row with fewer fields, or a differently-shaped field, must not match.
  Pinned by a **near-miss negative control** (Phase 2 step 11.11).
- `_OPENCODE_WORKING_RE` — anchored on the `⬝⬝⬝⬝` spinner-glyph run, **never** a
  bare `esc interrupt` alternation (the Codex lesson: an unanchored form
  false-positives on boot/tip text for ~0.5 s, and a false `working` **clears**
  the caller's settle latch).
- `_OPENCODE_HINT_SPAN_RE` — the truecolor gray span, local replacement for
  `_DIM_SPAN_RE`. **A subtractor, never the positive anchor** — the hint is gone
  after the first turn.

### `_opencode_box_state(raw_text, plain, *, <regexes as keyword defaults>)`

Keyword-default regexes so the negative controls can substitute one without
copying the function.

1. Bottom-up, find the **bottom border**. Absent ⇒ `SHADOW_DIALOG` (the dialog
   replaces the box) — same fail-safe as `_composer_state`'s fall-off case.
2. Require a **status row adjacent to the border** — the next non-blank line
   below it, not merely "somewhere below" — else `SHADOW_DIALOG`. Adjacency
   matters: a search over everything below the border would let any unrelated
   `·`-separated row later in the pane corroborate a stray border. The border is
   primary; the status row corroborates, so a future release drawing a stray
   border cannot alone produce a false READY.
3. The gutter rows are the **contiguous `┃` run immediately above the border**.
   Empty run ⇒ `SHADOW_DIALOG` (a border with no input area).
4. All rows blank after the gutter ⇒ `SHADOW_READY`. Otherwise re-check the
   corresponding **raw** rows with `_OPENCODE_HINT_SPAN_RE` subtracted: nothing
   left ⇒ it was the placeholder hint ⇒ `SHADOW_READY`; else ⇒ `SHADOW_BUSY`.

4b. **Window-sufficiency guard — fail closed rather than assume.** A would-be
   `READY` is only trustworthy if the captured window was large enough to have
   *shown* a working footer had one been present. The window is bottom-anchored,
   so the risk is a tall composer box pushing the footer off the top of it. If
   the box's contiguous gutter run reaches the **first captured line** — i.e. the
   window starts inside, or immediately above, the box, leaving no room above it
   for the footer to have been observed — downgrade the verdict to
   `SHADOW_UNKNOWN`.

   `SHADOW_UNKNOWN` (not `BUSY`, not `DIALOG`) is the honest verdict: it means
   *unknowable*, which `_ready_from_state` maps to `None` and the caller already
   treats as never-injectable. It also arms the settle latch, since it is neither
   READY nor WORKING — the correct conservative behaviour. This guard ships
   whatever the measurement says; it is the structural backstop behind the footer
   regex, and the one thing that keeps a missed footer fail-safe rather than
   fail-dangerous.

Then `_opencode_state` = `_ordered_state(..., positive=_opencode_box_state,
working_re=_OPENCODE_WORKING_RE)` and `_opencode_ready` =
`_ready_from_state(_opencode_state(...))`.

**How the three hard questions are answered:**

| question | answer |
|---|---|
| box-border + status-row anchor | steps 1 and 2, both required |
| at-rest-after-a-turn vs at-rest-fresh vs typed, without `_DIM_SPAN_RE` | after-a-turn hits step 4's *first* branch with **no hint machinery involved at all** (which is why it is the primary fixture); fresh survives hint subtraction to a bare gutter; typed does not |
| blank-gutter false positive | the dialog has no border, so step 1 returns DIALOG **before any gutter row is examined**; the gutter walk is additionally contiguity-anchored to the border, so it can only ever see the composer's own rows |

### Dispatch + comments

5. Add `"opencode"` to **both** tables (lowercase — `shadow_state` normalizes
   with `.strip().lower()`).

6. **Rewrite the comment above `SHADOW_READY_DETECTORS` (`:482-484`)** — its
   worked example is literally *"a Claude followed pane can have an OpenCode
   shadow — agents without a detector must refuse at ARM time"*, which this change
   makes false. Re-point it at the general case (a future/unrecognised agent) and
   state that **no shipped `AGENT_KEYS` member lacks a detector any more**.

7. Extend the section comment at `:322-331` with the OpenCode bullet: box
   composer, no SGR-dim, blank-gutter dialog rows, footer-only working
   discriminator — and why a sibling positive half over a widened shared one.

No new app state, so the `__new__`-built test app harnesses need no mirroring —
the trap t1509 hit (`RecheckInjectionSmokeTests` missing new fields) does not
recur here.

## Phase 2 — fixtures and tests

`tests/review_loop_fixtures.py`

8. Add the Pre-4 literals and an **OpenCode provenance paragraph** in the shape
   of the Codex one: version, date, geometry, capture command, and the measured
   properties the fixtures encode — two at-rest fixtures because the hint is not
   durable, and `OPENCODE_PERMISSION_RAW` named as load-bearing (it is the
   blank-gutter control's subject, not decoration).

`tests/test_review_loop.py` — three classes mirroring the Codex set

9. **`OpenCodeShadowReadinessTests`** — after-a-turn ready (listed first, on
   purpose); fresh-with-hint ready; typed/working/every dialog not-ready;
   hash-instability blocks; `None`/`""` indeterminate; the explicit
   `{fixture: SHADOW_*}` verdict table; and `test_opencode_is_in_both_dispatch_tables`
   (the existing drift test pins *parity*, not **membership**).

10. **`OpenCodeIsolatedPositiveHalfTests`** — `setUp` empties
    `PROMPT_PATTERNS_BY_AGENT["opencode"]`, `tearDown` restores:
    - dialogs still not-ready with the pattern list disabled ⇒ the exclusion is
      **structural**;
    - `test_the_disabling_is_real` — harness negative control: the list really is
      `[]`, at-rest is still `True`, working is still `False`;
    - `test_the_dialog_really_has_no_composer_box` — **premise assertion**:
      neither the border nor the status-row regex matches
      `OPENCODE_PERMISSION_RAW`. The day OpenCode starts drawing the box behind
      the dialog, this fails **loudly** instead of the structural guard silently
      degrading to pattern-only exclusion.

11. **`OpenCodeDetectorNegativeControlTests`** — one mutation each, each with a
    named failing assertion:
    1. **the blank-`┃`-row control** (the task's headline): build the naive rule
       as a real predicate, assert it **matches both** the permission dialog and
       at-rest (so it demonstrably cannot tell them apart), then assert the
       shipped classifier returns `DIALOG` / `READY` respectively;
    2. **drop the border anchor** (substitute a match-everything regex through
       the keyword default) ⇒ the dialog reads `SHADOW_READY`;
    3. **drop `_OPENCODE_WORKING_RE`** ⇒ the working fixture flips to
       `SHADOW_READY` — the highest-value control on this agent, because the
       footer is the *sole* discriminator;
    4. **drop `_OPENCODE_HINT_SPAN_RE`** ⇒ the **fresh** fixture flips to
       `SHADOW_BUSY` while **after-a-turn stays READY** — the assertion proving
       the hint is *subtracted*, not *relied on*;
    5. `test_an_unanchored_esc_interrupt_would_false_positive_on_boot` — **ship
       only if the live boot text actually contains the phrase**; otherwise
       record the null and drop it;
    6. `test_dialog_outranks_working_when_both_are_visible` — **only if
       `OPENCODE_PERMISSION_WITH_WORKING_RAW` was captured**; assert the premise
       (both signals inside the 15-line window) then the verdict;
    7. `test_claude_and_codex_are_unchanged_by_the_ordering_extraction` —
       characterization guard over every `CLAUDE_*` and `CODEX_*` fixture against
       the Pre-1 baseline.
    8. **`test_a_working_pane_whose_footer_fell_outside_the_window_is_not_ready`**
       — the beyond-tail regression test, and the executable proof of the
       window-sufficiency guard. Derive the input from the **real**
       `OPENCODE_WORKING_RAW` by dropping its leading lines until the footer is
       gone and the gutter run reaches the first line — a truncation of genuine
       captured output, never a fabricated screen. Assert:
       - the premise: `_OPENCODE_WORKING_RE` finds **nothing** in the truncated
         capture (so the footer really is unobservable, and the test is not
         passing for some other reason);
       - the verdict: `_opencode_state` returns `SHADOW_UNKNOWN`, and
         `shadow_prompt_ready(..., hash_stable=True)` returns **`None`** — *not*
         `True`. Without the guard this returns `READY`/`True`, which is the
         inject-into-a-working-shadow failure; this test is the one that fails.

       **This test alone is not sufficient** — see step 11.9. It proves the
       classifier's verdict, not that the verdict stops a delivery.
    9. **`test_a_truncated_working_opencode_shadow_is_never_injected_into`**
       (in `tests/test_minimonitor_concern_action.py`, the app level) — the
       delivery-path proof. A correct verdict does not by itself prove no input
       is sent: `_fire_shadow_recheck` takes its **own fresh capture** and
       re-validates (`minimonitor_app.py:2833-2836`), so a dispatch regression
       (wrong `shadow_key`), a stale-capture regression, or a delivery-path
       regression could still send while every detector test stays green.

       Arm the loop with an **OpenCode** shadow and drive it to the point of
       delivery, using the existing `_LoopFakeMon.raw_tails` queue pattern that
       t1509 already uses for the Claude typed/dialog cases (`:1912-1959`):
       queue ready tails for the tick-time captures and the **truncated working
       tail for the fresh pre-send capture**, so the two-step verification is the
       thing under test. Assert:
       - **no `send_keys` call was recorded at all** — neither the prompt write
         nor a bare Enter (contract item 9: Enter is never sent after a failed
         prompt write, and here nothing should be written in the first place);
       - the controller did not reach `FIRED` — the episode stays not-ready and
         the streak is preserved rather than consumed.

       Run the same shape once more with the truncated tail supplied at
       **tick** time, so both capture points are covered.
    10. **`test_ordinary_idle_geometry_is_not_swallowed_by_the_window_guard`** —
       the guard's **other** direction. A fail-closed guard that fires on normal
       idle geometry would make every ready pane `UNKNOWN` and silently prevent
       every automatic recheck — the loop would simply never fire for OpenCode,
       with no error and no banner. Assert that **both** at-rest fixtures (fresh
       and post-turn) do **not** trigger the guard and still classify
       `SHADOW_READY`, and assert the guard's trigger condition is specifically
       *not* met for them. Pinning both directions is what keeps the guard a
       guard rather than an off switch.
    11. **`test_a_near_miss_separator_row_does_not_satisfy_the_status_row_rule`**
       — the status-row grammar control. Take another **real** captured
       `·`-separated OpenCode row (from `OPENCODE_QUESTION_RAW`, the boot/tip
       screen, or any other captured non-composer row) and assert
       `_OPENCODE_STATUS_ROW_RE` does **not** match it, while the genuine status
       row in `OPENCODE_AT_REST_AFTER_TURN_RAW` does. If no near-miss row exists
       anywhere in the captures, say so in `### Pre-phase RESULTS` and pin the
       grammar instead by asserting that a **field-count-reduced** variant of the
       real row (one separator removed) stops matching — still derived from real
       output, never invented.

`tests/test_minimonitor_concern_action.py` — the arm-refusal retarget

12. **The problem, precisely:** `AGENT_KEYS = ("claude", "codex", "opencode")`,
    so once `opencode` gains a detector **no real agent key can reach**
    `minimonitor_app.py:2559` (arm) or `:2666` (mid-loop). Both guards would go
    vacuous. A guard that loses its only subject is deleted, not satisfied.

    Add a **synthetic** key + pane-list fixture beside `_SHADOW_LIST_OPENCODE`,
    with a comment stating what it stands in for: **the next agent wired into
    `AGENT_KEYS` ahead of its detector** — a real, reachable state, so the guard
    is future-proofing rather than dead code.

    **The `_resolve_shadow_agent_key` override is mandatory, not convenient.**
    Without it the real resolver runs `agent_key_from_pane` → rung 1 answers `""`
    → rung 2 shells out to `pgrep`/`ps` against a real pid on the box. The test
    would be slow, nondeterministic, and — worse — would land on the
    **`"" ⇒ could not resolve`** branch, silently proving the wrong thing. Each
    retargeted test therefore asserts both the premise (`assertNotIn(key,
    SHADOW_READY_DETECTORS)`) and `assertNotIn("could not resolve", …)`.

13. **Retarget all three consumers**, none deletable:
    - `test_refuses_shadow_agent_without_detector_naming_it` (`:1587`) — arm-time;
    - `test_mid_loop_swap_to_undetectable_shadow_disarms_naming_it` (`:2037`) —
      mid-loop auto-disarm;
    - `ShadowAgentResolutionGenerationTests.test_mid_loop_abandons_a_superseded_lifecycle`
      (`:1678-1694`) — its inline comment is `# unsupported => would disarm`; its
      whole point is that a superseded lifecycle mutates nothing, so its subject
      must stay an undetected agent or it stops proving anything.

14. **New:** `test_the_refusal_names_the_pane_command_not_the_resolved_key` —
    drive a case where command and key **differ** (`_SHADOW_LIST_NODE` + the
    synthetic key), since the notify interpolates `shadow_command`. In the
    primary test the two are equal on purpose, so "names it" is honest about what
    it names; here the contract is pinned rather than accidentally true.

15. **New positive counterparts** — without these the retarget removes all
    coverage of the pairing this task enables:
    `test_opencode_shadow_of_a_claude_pane_now_arms` (reusing
    `_SHADOW_LIST_OPENCODE`, which the retarget frees up; **no resolver override
    needed** — opencode is a native bin, so rung 1 resolves it) and
    `test_mid_loop_swap_to_an_opencode_shadow_keeps_the_loop_armed` (give
    `_loop_app` an `OPENCODE_AT_REST_*` raw tail instead of its
    `CLAUDE_AT_REST_RAW` default, so the detector under test is fed its own
    agent's capture).

16. **Retarget `test_failed_capture_and_unknown_agent_are_indeterminate`**
    (`tests/test_review_loop.py:474`): drop the now-false `"opencode" is None`
    assertion (it will return `False`), keep `"gemini"` and `""`, **add a premise
    assertion** (`assertNotIn("gemini", SHADOW_READY_DETECTORS)`) so the case
    cannot go vacuous, and rewrite the comment to state the new fact: no member of
    `AGENT_KEYS` is undetected any more, so the unknown-agent case is now carried
    by keys that are not agents at all.

17. **Rejected alternative, recorded so it is not re-proposed:** a
    `set(AGENT_KEYS) <= set(SHADOW_READY_DETECTORS)` tripwire. It states the new
    world exactly, but it would **forbid the very state the refusal branch exists
    to handle** — wiring a fourth agent key before writing its detector is a
    legitimate intermediate state the guard degrades gracefully for. A test that
    turns graceful degradation into a build break is worse than no test.

18. **Parallel-lane constraint (no action, do not break it):** both modules run in
    the pytest `-n <workers> --dist loadfile` pool. The isolated-positive-half
    class mutates the module-global `PROMPT_PATTERNS_BY_AGENT`; that is safe
    *only* because `--dist loadfile` keeps a whole file on one worker. Use the
    same save-in-`setUp` / restore-in-`tearDown` shape — never a bare
    module-level mutation.

## Phase 3 — docs

19. `aidocs/framework/shadow_agent.md` — **four** passages, not one:
    1. `:623-628` — *"`SHADOW_READY_DETECTORS` ships `claude` and `codex`"* → all
       three; and the *"(currently `opencode`)"* parenthetical on the arm refusal
       must **not** be replaced with another agent name — say the branch now
       stands for a future agent wired ahead of its detector and is exercised with
       a synthetic key. Add OpenCode to *"a Claude pane can legitimately have a
       Codex shadow"*.
    2. Safety-contract item **5** (`:544-552`) — *"the dim placeholder hint strips
       identically to typed text"* is now agent-specific and partly false. Add one
       sentence: OpenCode's composer is a `┃`-gutter **box** anchored on its
       bottom border + status row, carries **no SGR-dim**, and its hint is a
       truecolor gray span absent entirely after the first turn — so the dim-strip
       discriminator does not transfer.
    3. Safety-contract item **6** (`:572`) — still true in the abstract; add that
       **no shipped agent key lacks a detector today**, so the path is exercised
       with a synthetic key.
    4. Item **5b** — update only if the pre-phase stop resulted in an amended
       plan that changes
       `SHADOW_SETTLE_SECONDS`; record the OpenCode measurement beside the Codex
       one either way.

20. **The measurement recipe** (user's decision: a documented recipe, not a
    committed script). Add a short subsection to `shadow_agent.md` recording the
    reproducible method, so the *third* agent's task does not rebuild it from
    scratch a third time: private socket, 120x30, production `capture-pane -p -e
    -S -15` argv, 0.25 s sampling, ≥5 reps per interaction kind, classification
    through the real detector, and the **longest-injectable-ready-run** definition
    with the t+0 pre-submit artifact excluded. Prose only — describe dialog
    structure, never paste an option block (that page's own rule).

21. `aidocs/framework/monitor_idle_and_prompt_detection.md` — its t1509
    cross-reference is agent-neutral and needs no correction. Optionally add one
    clause: shadow-side *composer* shapes differ **structurally** per agent (glyph
    line vs gutter box), which is why they live in `review_loop.py` rather than
    this file's flat pattern list. Re-read before deciding rather than assuming.

    *(Sweep already run: `SHADOW_READY|readiness detect` across all markdown
    returns exactly one file — `shadow_agent.md`. Nothing in `docs/`, the
    website, or any skill claims anything here.)*

## Verification

**Pre-ship conditions — none deferrable to a manual-verification follow-up:**

- Every fixture trimmed to the 15-line window; every non-reproducing state
  recorded as an explicit null rather than synthesised.
- The Pre-2 numbers recorded, with the two independent evidence channels
  reconciled against the prototype's verdicts, and `SHADOW_SETTLE_SECONDS`
  confirmed against the pre-registered rule — or, if it fails the rule,
  implementation **stopped** for an amended-plan approval rather than continued.
- The Pre-3 footer-position **and idle-headroom** numbers recorded, and — if the
  footer can escape the window, or idle geometry leaves insufficient headroom —
  the chosen in-task remedy implemented, not deferred. The window-sufficiency
  guard ships either way, pinned in **both** directions: the beyond-tail
  regression test (it fires when it must) and the idle-geometry test (it does not
  fire when it must not).
- The delivery-path test asserts **no `send_keys` at all** for a truncated
  working OpenCode tail, at both the tick-time and pre-send capture points — a
  correct classifier verdict is not by itself proof that nothing was injected.
- **Every negative control mutation-verified**: apply the mutation, watch *that
  named test* fail, revert. t1509's experience is the reason this is explicit —
  one of its ordering tests initially *passed under mutation* because the
  fixture's 15-line window excluded the discriminating line, which is what forced
  `CODEX_PERMISSION_WITH_RUNNING_RAW` into existence.

**Commands:**

```bash
python3 tests/test_review_loop.py
python3 -m unittest tests.test_minimonitor_concern_action -v
python3 tests/test_prompt_detection.py      # owns the other OpenCode gutter fixtures
bash tests/run_all_python_tests.sh          # final stderr verdict line ONLY
```

Read only `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`; do not pipe to `tail`
without `pipefail`. No shell scripts are touched, so `shellcheck` does not apply;
the measurement harness is scratchpad-only and is not committed.

**Live acceptance (the real entry point, not just unit tests):** in a real
`ait minimonitor`, follow a Claude agent, `E`-launch an **OpenCode** shadow, press
`L` — the loop must **arm** instead of refusing, must fire one automatic recheck,
and must not inject while that shadow is mid-output or parked at the permission
dialog.

## Step 9 (Post-Implementation)

Merge and archival follow the shared task-workflow Step 9. Code commits use
`feature: <description> (t1520)`; task/plan files go through `./ait git` with the
`ait:` prefix. Several agent sessions are active in this repo — stage explicit
paths, never `git commit -a`, and verify staged content before committing.

## Coordination

- **t1509** — shipped the generic `_composer_state`, `shadow_state`, the
  wall-clock settle latch and the pid-carrying shadow seam this task builds on.
- **t1529** — manual-verification follow-up created at Step 8c, covering the
  live behaviour no fixture can: arming with a real OpenCode shadow, the
  hold cases (working / permission dialog / open command palette / typed
  text / short pane), the narrow-split availability check, and the
  Claude+Codex regression.
- **t1524** (`surface_never_settled_shadow`, still `status: Ready`) — the durable
  answer to silent per-agent pattern drift. This task **increases its value** (a
  third agent now depends on it). Do **not** spawn a duplicate; note the new
  dependant in t1524.

## Risk

### Code-health risk: medium

- Extracting `_ordered_state` out of `_composer_state` touches the shared
  claude+codex path of an **injecting** loop, where a subtle behaviour change is a
  silent regression · severity: low (residual — the pre-phase records the
  pre-extraction verdicts, so the refactor has a baseline it did not author) ·
  → mitigation: inline pre-phase characterize_composer_state_before_extraction
- Two structural positive halves now exist, so the measured dialog→positive→
  working **order** could drift between them · severity: low · → mitigation: none
  (the order lives in exactly one function, `_ordered_state`; both detectors reach
  it through the same call, so drift now requires editing the shared helper, which
  every agent's tests cover)
- A third agent's worth of version-pinned terminal-UI constants accumulates in one
  module · severity: low · → mitigation: none (it is the module's documented
  maintain-in-place practice; **t1524** is the durable answer and already exists)

### Goal-achievement risk: medium

- **The `⬝⬝⬝⬝ esc interrupt` footer is the ONLY at-rest/working discriminator for
  OpenCode.** If the regex drifts *or the footer simply scrolls out of the 15-line
  `capture_raw_tail` window*, a working shadow reads READY and the loop injects
  mid-work — the exact failure the feature exists to prevent. Note the direction:
  Claude/Codex detector drift is **fail-safe** (composer regex misses ⇒ never
  ready); this one is **fail-dangerous**, and unlike them OpenCode's second brake
  (hash instability from an animated indicator) is **unmeasured** · severity: low
  (residual — the **window-sufficiency guard ships unconditionally**, converting a
  missed footer from fail-dangerous to fail-safe, and is pinned by the beyond-tail
  regression test; the pre-phase measures both brakes before the detector ships,
  and an escaping footer is a pre-ship blocker resolved in this task, not
  deferred) · → mitigation: inline pre-phase
  measure_opencode_working_hash_stability (+ conditional after-task
  harden_opencode_working_detection, for the hash-stability half only)
- `SHADOW_SETTLE_SECONDS` is one shared constant; a measured OpenCode window
  > 1.0 s forces a decision that changes Claude and Codex behaviour · severity:
  low (residual — the pre-phase measures it and the decision is raised at Step 8
  with the data, rather than guessed) · → mitigation: inline pre-phase
  measure_opencode_settle
- The isolated-positive-half claim rests entirely on the dialog having **no**
  composer box. A future release that draws the box behind the dialog degrades the
  structural guard to pattern-only, **silently** · severity: medium · →
  mitigation: none beyond `test_the_dialog_really_has_no_composer_box`, which
  asserts the premise by name so a refreshed fixture fails loudly
- The window-sufficiency guard fails closed, so an over-eager version would make
  every ready OpenCode pane `UNKNOWN` and silently disable the loop for this agent
  with no error and no banner — a fail-safe direction, but an invisible one ·
  severity: low (residual — the pre-phase records idle gutter height and headroom
  at production *and* narrow widths, and step 11.10 pins the fixtures as still
  READY-eligible, so the guard is held to both directions) · → mitigation: inline
  pre-phase measure_opencode_working_hash_stability
- The status-row anchor must stay generic over the user-switchable mode token, and
  an over-permissive grammar would let a future `·`-separated widget row
  corroborate a stray border into a false READY · severity: low · → mitigation:
  none beyond the pinned full-field grammar, the border-adjacency requirement, and
  the near-miss negative control (Phase 2 step 11.9)
- The settle measurement classifies captures through the prototype detector, so a
  narrow working regex could label working output READY and make the measurement
  *look* safe — the detector validating itself · severity: low (residual — the
  pre-phase records harness-derived ground truth and literal screen evidence as
  two independent channels, and a disagreement invalidates the measurement rather
  than being noted) · → mitigation: inline pre-phase measure_opencode_settle
- The gray hint span is **theme-derived**; a non-default theme makes the
  fresh-session hint read as typed text · severity: low · → mitigation: none —
  fail-safe (holds, never fires), **self-healing after one turn** (the hint is gone
  thereafter), and documented in the constant's comment. Deliberately not patched
  with a literal-text fallback: a second unmeasured mechanism is worse than one
  documented, fail-safe, self-healing gap
- The `╹▀▀▀` border / status row are pinned to 1.18.18 and OpenCode ships fast ·
  severity: low · → mitigation: none (fail-safe: no border ⇒ DIALOG ⇒ never ready;
  covered by t1524)

### Planned mitigations

- timing: pre-phase | name: characterize_composer_state_before_extraction | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the `_ordered_state` extraction touches the shared claude+codex detector path | desc: Record the existing Claude/Codex detector verdicts against the UNMODIFIED `_composer_state` before extracting `_ordered_state`, so the refactor has a characterization baseline it did not author.
- timing: pre-phase | name: measure_opencode_settle | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — `SHADOW_SETTLE_SECONDS` is one shared constant across all three agents, and the prototype must not be its own only witness | desc: Measure OpenCode's post-interaction settle window live in wall-clock seconds at 0.25s sampling, >=5 reps each across granted permission, rejected permission, question widget and a plain no-interaction turn, using t1509's longest-injectable-ready-run metric and the pre-registered sizing rule; classify through the prototype detector but record harness-derived ground truth and literal screen evidence as two independent channels, treating any disagreement as a detector defect that invalidates the measurement; STOP for an amended-plan approval rather than proceeding to Phase 1 if the measured maximum exceeds 1.0s.
- timing: pre-phase | name: measure_opencode_working_hash_stability | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the esc-interrupt footer is OpenCode's sole at-rest/working discriminator and fails DANGEROUS | desc: From the same capture stream, determine whether OpenCode's working state is ever byte-identical across two consecutive 0.25s captures (does `hash_stable` act as an independent second brake, as it does for Claude/Codex?) and whether the footer can render beyond the bottom-anchored 15-line window; an escaping footer is a PRE-SHIP BLOCKER resolved in this task by raising the per-agent capture depth or adding an independent working signal, on top of the window-sufficiency guard that ships unconditionally. Also record ordinary idle gutter height and window headroom at production and narrow widths, so the fail-closed guard is sized to fire on the dangerous case without swallowing the normal one.
- timing: after | name: harden_opencode_working_detection | type: enhancement | priority: high | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — the hash-stability half of the fail-dangerous working-detection risk | desc: CONDITIONAL — spawn at Step 8d only if measure_opencode_working_hash_stability shows OpenCode's working state can go byte-identical across two consecutive captures, i.e. `hash_stable` does not act as an independent second brake the way it does for Claude and Codex. Add one: a longer required hash streak for this agent, or a corroborating in-window signal. Deliberately NOT the remedy for an out-of-window footer — that case is a pre-ship blocker handled inside t1520. | created: not-required(condition unmet)

**Step 8d disposition — `harden_opencode_working_detection` NOT created.** Its
spawn condition was measured **false**: across 15 turn-level reps the longest
run of consecutive byte-identical `working` captures was **1 sample (0.25 s)**,
so `hash_stable` does act as an independent second brake for OpenCode, exactly
as for Claude and Codex. The residual it guarded is covered twice over —
hash-instability at normal geometry, and `_OPENCODE_MIN_LINES_BELOW_BORDER`
wherever the footer cannot render at all. Recorded here rather than silently
skipped so the unmet condition, not an oversight, is what closed it.

## Final Implementation Notes

- **Actual work done:** Extracted `_ordered_state` out of `_composer_state` so
  the measured verdict order (dialog → structural positive → `working` only
  outranks a would-be `ready`) lives in exactly one function while the positive
  half is pluggable. Added OpenCode's sibling positive half
  (`_opencode_box_state`) plus `_opencode_state` / `_opencode_ready`, six
  `_OPENCODE_*` constants, and `opencode` in both dispatch tables. Added an
  `opencode_palette` pattern to `prompt_patterns.py`. Nine live fixtures, 30 new
  tests across three modules, and doc corrections in `shadow_agent.md`,
  `monitor_idle_and_prompt_detection.md` and `monitor_core.capture_raw_tail`.
  Final: 9 files, +977/−71. `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.

- **Deviations from plan:** Four, all measurement-driven and recorded in
  `### Pre-phase RESULTS` above.
  1. **Fixtures are NOT trimmed to 15 lines**, contrary to the task's stated
     acceptance criterion. `-S -15` carries no `-E`, and these agents run on the
     alternate screen, so production reads the whole visible pane; trimming was
     measured to drop the fresh-session hint row and make a negative control
     vacuous. The AC's intent (never pass on content production cannot see) is
     honoured; its literal line count is not.
  2. **The planned window guard never fires.** Its trigger ("the gutter run
     reaches the first captured line") is unreachable — `box_top` is ≥1 even at
     pane height 6. Replaced with a measured one: ≥1 line below the box border,
     the footer's exact offset.
  3. **`OPENCODE_QUESTION_RAW` and the dialog-outranks-working control were
     dropped, not faked.** The question widget never reproduced, and unlike
     Codex, OpenCode does not keep a working indicator up during a dialog, so
     that ordering is untestable for this agent.
  4. **An unplanned fix shipped:** the `opencode_palette` pattern, for a
     false-READY found during measurement (user-approved scope change).

- **Issues encountered:**
  - The **command palette** reads as READY: it is an overlay that leaves the
    composer box intact, so no structural check can see it. Fixed via a pattern,
    which is the only half that can exclude an overlay.
  - The **fail-dangerous hazard was real and reproduced**: at pane height 6 the
    working footer has no room to render, so an empty box reads READY *and* the
    capture is byte-identical — both brakes fail together. Confirmed against an
    independent channel (the opencode process tree's CPU time). This is what the
    window guard exists for; boundary pinned at h=7 (fires) vs h=6 (hazard).
  - **Two negative controls could not be built as specified.** The permission
    dialog and the compact palette are each *over-determined* — several
    independent anchors refuse them — so no single mutation flips either to
    ready. Both were relabelled belt-and-braces and replaced by controls that
    do discriminate (the status-row anchor; the by-name header assertion).
  - **A mutation harness produced two false "ok" verdicts.** Deleting a
    `PromptPattern(...)` line made the test fail with an `ImportError` rather
    than the assertion — failing for the wrong reason is not evidence. Mutations
    must keep the module importable (neuter the regex, don't delete the line)
    and be judged on the failure *message*, not the exit status. Re-run
    correctly; all guards now verified on corrected evidence.

- **Key decisions:**
  - **Sibling positive half, shared order.** OpenCode's gutter box does not fit
    `_composer_state`'s one-character-glyph contract, so it got its own
    structural half rather than distorting the shared one — but the order was
    extracted rather than duplicated, so it cannot drift between the two shapes.
  - **`SHADOW_SETTLE_SECONDS` stays 2.0**, confirmed by measurement (0.00 s
    injectable window across 15 reps), so the pre-registered approval stop never
    triggered and no per-agent table was introduced.
  - **`harden_opencode_working_detection` does not fire**: `hash_stable` is a
    genuine independent second brake for OpenCode (max 1 identical working
    sample), exactly as for Claude and Codex.
  - **The arm-time refusal keeps a synthetic subject** rather than a
    `set(AGENT_KEYS) <= set(SHADOW_READY_DETECTORS)` tripwire, which would turn
    a legitimate intermediate state (a new agent key landing before its
    detector) into a build break.
  - **`REVIEW_LOOP_AGENTS` untouched** — this task is the shadow side; widening
    the followed side remains its own task with its own evidence.

- **Cross-module fix folded in (not deferred):**
  `monitor_core.capture_raw_tail`'s docstring described itself as "deliberately
  tiny … the prompt area, not the transcript" — the exact false premise this
  task disproved, and the first thing a future detector author reads. Corrected
  in place in this task, so nothing remains to spawn for it.

- **Upstream defects identified:** None
