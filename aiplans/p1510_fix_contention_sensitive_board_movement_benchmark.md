---
Task: t1510_fix_contention_sensitive_board_movement_benchmark.md
Worktree: . (current-branch mode — profile 'fast' sets create_worktree: false)
Branch: main
Base branch: main
Output branch: main
---

# p1510 — Fix the contention-sensitive board-movement benchmark + stale carve-out doc

## Context

Two upstream defects spawned from t1500's Step 8b review, both surfaced while
running the full Python suite three times to verify t1500's live-test flake fix.

**1. `tests/test_board_movement.py:1429-1433`** —
`test_attribution_tier_localises_an_injected_cost` asserts a wall-clock upper
bound (each neighbour span absorbed < 25 ms of a 50 ms cost injected into
`refocus`). Run 1 of three failed with `render` = 40.0 ms; runs 2 and 3 passed,
and the test passes standalone in ~6.1 s. The module was untouched by t1500 — it
is a timing assertion exposed to CPU contention from the suite's own
`-n 4 --dist loadfile` lane.

**2. `CLAUDE.md:44-46`** — documents the serial carve-out as one module
(`tests/test_board_header_row_live.py`); the runner announces three. The list
grew when the two `*_startup_focus_live.py` modules were added and the doc did
not follow. This matters beyond tidiness: carve-out membership decides whether a
live tmux test runs against a loaded box — exactly the variable t1500's flake
turned on.

**Intended outcome — stated so it cannot be quietly downgraded:** the
neighbour-localisation claim must still be *evaluated and satisfied* under the
real `-n 4 --dist loadfile` lane. "The test stopped flaking" is **not** the
goal; a run in which the assertion declines to evaluate is a failed
verification, not a pass (see the acceptance rule in the post-phase below).

## Root cause (measured, not inferred)

`summarise()` exposes `tree_self_ms` as the **median** across samples, and the
attribution test runs at `SMOKE_PAIRS = 2` → **4 samples**. Per-sample `render`
self time on an *idle* box spans **41–119 ms**. The assertion therefore compares
the difference of two independently-medianed noisy quantities against a fixed
25 ms bound — a bound *smaller than the statistic's own run-to-run spread*. The
lower bound (`delta ≥ 40 ms`) survives only because the injected 50 ms is
unconditional and dwarfs the noise.

**Why `min` is the right instrument:** scheduling noise is strictly *additive* —
a descheduled thread only ever adds wall time to the enclosing span. The minimum
sample is therefore the estimate of the true uncontended cost, and it is
contention-invariant as long as one sample runs clean. The median is not: it
tracks the bulk of the distribution, which contention shifts wholesale. This
changes the **instrument**, not the threshold — the 0.5 factor is untouched, per
the task's explicit instruction.

### Evidence

Measured on this box: 3 clean + 3 negctrl runs at 12 samples/run, all 9
cross-run comparisons, in two conditions — idle, and with the probe and 3
busy-loop workers pinned to 2 cpus (**2.5× oversubscription**, harsher than the
4-worker lane on 24 cores).

| quantity | bound | idle | 2-cpu oversubscribed |
|---|---|---|---|
| `refocus` min-delta (signal) | ≥ 40 | +50.19 … +50.21 | **+50.09** |
| `render` **min**-delta | < 25 | −7.44 … **+2.67** | −5.47 … **+7.39** |
| `render` **median**-delta | < 25 | +0.60 … **+14.72** | −2.19 … **+10.83** |
| `layout` / `dom_query` / `check_action` min-delta | < 25 | ≤ +1.52 | ≤ +0.31 |

Two conclusions:

- The median leaves ≤ 1.7× margin *on an idle box* and was measured at 40 ms — a
  failure — in the wild; the minimum holds a ≥ 3.4× margin even at 2.5×
  oversubscription.
- `refocus` is a `time.sleep(50 ms)` floor, so it is **immune to CPU
  contention** (the thread is descheduled regardless): 50.09 loaded vs 50.19
  idle. The `undecidable` precondition below therefore cannot misfire under
  load — the lane will produce a real verdict, not a skip.

## Changes

### A. `tests/test_board_movement.py`

1. **`summarise()`** (~line 824) — add `tree_self_min_ms` alongside
   `tree_self_ms`: per-span **minimum** across samples, in ms. Purely additive;
   `tree_self_ms` / `tree_self_share` / `tree_calls` and every existing consumer
   (`test_bench_baseline`, the report printers) are untouched.

2. **`ATTR_PAIRS = 6`** — a new constant used *only* by the attribution test
   (12 samples/run, the N the table above was measured at). `SMOKE_PAIRS = 2`
   stays as-is for the other smoke tests. Expected cost ~6 s → ~11 s standalone;
   measured and reported during implementation.

3. **Extract the verdict into a pure helper**
   `attribution_localisation_verdict(clean, slow, injected_ms, neighbours)`
   → `(verdict, detail)` with `verdict ∈ {"localised", "leaked", "undecidable"}`.
   Inputs are plain stat dicts — no timing, no Textual, no child interpreter —
   so every branch is reachable from a unit test.
   - `refocus` delta **< 0.8 × injected** → `leaked` (the accounting genuinely
     failed to localise — today's lower-bound failure, semantics unchanged).
   - `refocus` delta **> 1.5 × injected** → `undecidable`. Even the
     least-contended sample of the *signal* span is distorted, so no neighbour
     claim can be trusted. This is the task's "quiet box precondition the test
     can actually verify", expressed as a property of the measurement rather
     than a guess about the machine.
     **It is a defensive backstop, not an expected outcome** — measured at
     50.09 ms loaded against a 75 ms trigger. Observing it in CI is a signal to
     investigate, never an acceptable verification result.
   - any neighbour delta **≥ 0.5 × injected** → `leaked`, naming the neighbour
     and its value.
   - otherwise `localised`.

4. **`test_attribution_tier_localises_an_injected_cost`** — keep every
   noise-immune assertion unconditional (tier installed: `check_action`/
   `focus_query` call counts, `refocus` calls == 1; the existing "control run
   already exceeds the injected cost" guard; the `tree_self_share` partition
   ≤ 1.0). Then feed `tree_self_min_ms` to the helper and branch:
   `localised` → pass; `leaked` → `self.fail(detail)`; `undecidable` →
   `self.skipTest(detail)`.
   **Two distinct emissions — human prose and a machine record. They are not
   the same string.**

   - **stderr (human)**, always:
     `attribution localisation: <verdict> | refocus +50.1 ms | worst neighbour render +7.4 ms (bound 25.0)`
   - **verdict log (machine)**, when the opt-in env var
     **`AITASK_BOARD_ATTR_VERDICT_LOG`** names a path: **append** one record
     produced by a tiny pure function
     `format_verdict_record(verdict, detail) -> str` with the format

     ```
     <verdict>\t<detail>
     ```

     — the **bare verdict token first**, anchored at line start, one of
     `localised` / `leaked` / `undecidable`, TAB, then free-form detail.
     Env-var style matches the module's existing
     `BENCH_ENV = "AITASK_BOARD_BENCH"`; absent ⇒ stderr only, so default
     behaviour is unchanged.

   **The record format and its matcher are defined together and pinned
   executably.** The canonical matcher is `^<verdict>\t`, and
   `format_verdict_record` gets a unit test asserting that each of the three
   verdicts produces a record matching `^<verdict>\t` — so the producer cannot
   drift from the consumer grep in the acceptance commands below. Logging the
   human prose line instead would silently break every acceptance check, since
   `^localised` matches no line that begins with `attribution localisation:`.

   The record is written for **all three** outcomes and **before** the
   `self.fail()` / `self.skipTest()` call raises — otherwise a skip would leave
   no trace and be indistinguishable from "the test never ran".
   **Why a file and not stderr alone:** under `run_all_python_tests.sh` pytest
   captures stdout/stderr for passing tests, and a `skipTest` still leaves the
   aggregate suite green — so the stderr line cannot establish that the claim
   was evaluated. `O_APPEND` of a sub-4096-byte record is atomic enough for
   concurrent xdist workers. Update the docstring to record why min, not median.

5. **`summarise()` contract test** (new, deterministic, no timing) — build a
   synthetic sample list whose per-span values are deliberately **asymmetric so
   that min ≠ median ≠ mean**, call `summarise()` directly, and assert:
   - `tree_self_min_ms[k]` equals the expected **minimum × 1000** (pins both the
     statistic and the ms units), and
   - `tree_self_min_ms[k] != tree_self_ms[k]` for that fixture — so an
     implementation that copy-pastes the median, uses the wrong units, or writes
     the wrong key cannot pass.
   Without this the helper tests (which take pre-built dicts) would stay green
   against a broken `summarise()`.

6. **Unit tests for the helper** — one mutation per case, each pinning a named
   outcome: clean localisation → `localised`; a neighbour absorbing 45 of 50 ms
   → `leaked` with the detail naming that neighbour; `refocus` delta 5 ms →
   `leaked`; `refocus` delta 90 ms → `undecidable`. These are the negative
   controls, and they are what make the `undecidable` branch reachable at all.

### B. `CLAUDE.md` (lines ~43-48)

Replace the stale single-module sentence with prose naming the shared rationale
plus an **explicitly delimited list block** that the guard is the sole consumer
of — so routine edits elsewhere in `### Testing` can never trip the manifest
guard:

```markdown
<!-- serial-carve-out:begin — guarded by tests/test_serial_carveout_doc_drift.sh
     against SERIAL_CARVE_OUT in tests/run_all_python_tests.sh -->
- `tests/test_board_header_row_live.py`
- `tests/test_board_startup_focus_live.py`
- `tests/test_codebrowser_startup_focus_live.py`
<!-- serial-carve-out:end -->
```

Surrounding prose: each boots a real TUI in a tmux pane under a hard wall-clock
boot budget that FAILS rather than skips, and a loaded worker pool turns that
budget into a flake (`test_board_header_row_live.py` additionally takes
`.git/index.lock` against the real repo). The `--dist loadfile` paragraph is
unchanged.

### C. `tests/run_all_python_tests.sh`

Comment-only: a reverse pointer above `SERIAL_CARVE_OUT` naming `CLAUDE.md`'s
marked block and the guard test, so the doc↔source reference is bidirectional.

### D. `tests/test_serial_carveout_doc_drift.sh` (new)

Follows `tests/test_seed_manifest_drift.sh` conventions — both sides **derived
from live source**, nothing hardcoded (a hardcoded list would just become a
third manifest to drift).

- **The two sides do not share a literal representation and must be normalized.**
  `SERIAL_CARVE_OUT` holds **bare basenames** (`test_board_header_row_live.py`)
  because `is_carved()` matches on `"${1##*/}"` — basename is the runner's
  identity notion and `tests/` is only a display prefix. The doc block shows
  reader-openable paths (`tests/test_board_header_row_live.py`). Comparing them
  literally would report drift on agreeing manifests.
  **Canonical comparison form: `tests/<basename>`** — chosen because it is what
  the doc shows and what a failure message should point at. It is produced by a
  **single `canon()` helper applied to both sides** (strip an optional leading
  `tests/`, then re-prefix `tests/`; idempotent), never by prefixing one side
  inline at the call site. The runner's array is **not** changed.
- **Source set**: bounded `awk` over the `SERIAL_CARVE_OUT=( … )` declaration in
  `tests/run_all_python_tests.sh` — the same array `is_carved()` reads — then
  `canon()`.
- **Doc set**: backticked `` `test_*.py` `` / `` `tests/test_*.py` `` tokens
  **only** from between the `serial-carve-out:begin` / `:end` markers, then
  `canon()`. The extraction deliberately accepts the unprefixed form so that a
  doc written as a bare basename is visible to the *form* check below rather
  than silently vanishing into a membership mismatch.
- **Two separate checks, each with its own failure message** — membership and
  form are different defects and must not be conflated:
  1. **Membership**: `canon()`-ed set equality in both directions, naming the
     offending entries.
  2. **Form**: every doc-block entry is written in the `tests/<name>.py` form,
     so the block stays reader-openable.
- Both sides asserted **non-empty**, and the markers asserted present, so a
  parse failure or a deleted block fails loudly instead of passing vacuously
  against two empty sets.
- **Positive control**: the real `CLAUDE.md` + real runner must PASS. This is
  what proves `canon()` is neither over- nor under-normalizing on live inputs;
  without it an over-strict `canon()` would surface only as a red suite.
- **Negative controls** against fixture copies of the doc, each mutating exactly
  one thing, all of which must be detected:
  1. an entry removed → membership drift
  2. an extra entry added → membership drift
  3. the markers deleted → hard error, not a vacuous pass
  4. an entry written as a bare basename → **form** violation *while membership
     still compares equal*. This is the normalization's own negative control: it
     pins that `canon()` runs on **both** sides, so failures 1 and 2 are real
     membership drift rather than path-shape artifacts.
  A passing negative control is a bug in the guard.
- The comparison body is a function taking a doc path, so the fixtures exercise
  the real code path, not a replica.

## Rejected alternatives

- **Widen the 0.5 factor** — rejected by the task; trades one arbitrary
  threshold for another and weakens the localisation claim.
- **Add `test_board_movement.py` to the serial carve-out** — slows the suite for
  everyone, stretches a carve-out that exists for tmux boot budgets, and hides
  the real defect (wrong estimator) rather than fixing it.
- **Best-of-N retry of the run pair** — up to 3× cost in the bad case and still
  leaves the median as the estimator; `min` buys the same robustness inside one
  run.
- **Assert on the neighbour's *share* of the injected cost** — measured not to
  help: the noise is additive and independent of the injected cost, so
  `n_delta / delta_refocus` still reads 0.8 when a 40 ms spike lands in `render`.
- **Scanning the whole `### Testing` section for test tokens** — couples routine
  documentation edits to the runner manifest; replaced by the marked block.

### Post-phase (risk mitigations)

**`contention_injection`** — after changes A–D are complete and before the
Step 8 review, evaluate the localisation claim under real contention, twice:

1. **Pinned oversubscription** — `taskset -c 0,1` the test plus 3 busy-loop
   workers (2.5× oversubscription; bounded to 2 of 24 cpus so a concurrent agent
   session is not disturbed).
2. **The real lane** — a genuine `-n 4 --dist loadfile` pytest run containing
   `tests/test_board_movement.py` plus enough sibling modules to saturate all
   four workers, driven through the verdict log rather than through captured
   output:

   ```bash
   log=$(mktemp); rm -f "$log"
   AITASK_BOARD_ATTR_VERDICT_LOG="$log" ~/.aitask/venv/bin/python -m pytest \
     tests/test_board_movement.py <saturating siblings> -n 4 --dist loadfile -v
   # executable acceptance check — not an eyeball.
   # Matcher is the documented record format: bare verdict token, TAB, detail.
   total=$(wc -l < "$log")                       # MUST be 1 (0 ⇒ never ran)
   ok=$(grep -cE '^localised\t' "$log" || true)  # MUST equal $total
   ```

   A green pytest exit is **not** sufficient: a `skipTest` leaves it green. The
   log is the only signal that distinguishes "evaluated and satisfied" from
   "declined to evaluate" and from "never ran" (empty log).

**Acceptance rule:** the log from (2) must contain exactly one line and it must
be `localised`; (1) must not produce `leaked`. An `undecidable` skip or an empty
log is **not** acceptance — it means the precondition declined to evaluate the
claim (or the test never executed), and the design must be revisited rather than
the result recorded as a pass. Record the observed verdict lines verbatim in the
Final Implementation Notes.

## Verification

1. `python3 -m unittest tests.test_board_movement.BoardMovementBenchmarkTests.test_attribution_tier_localises_an_injected_cost -v`
   — verdict `localised`; record the new wall time against the 6.1 s baseline.
2. `python3 -m unittest tests.test_board_movement -v` — whole module green.
3. The `summarise()` contract test, the `format_verdict_record` format test
   (all three verdicts match `^<verdict>\t`), and all four helper negative
   controls green.
4. `bash tests/test_serial_carveout_doc_drift.sh` — PASS against the real
   CLAUDE.md (the positive control that pins `canon()`), and all four negative
   controls detected, including the bare-basename form fixture that proves the
   normalization is applied to both sides.
5. The `contention_injection` post-phase above, to its acceptance rule.
6. `bash tests/run_all_python_tests.sh` — full suite. Read the last line
   (`PYTHON SUITE: …`) for the suite verdict; use `${PIPESTATUS[0]}` if piped.
   Run it under `AITASK_BOARD_ATTR_VERDICT_LOG` as well, because the suite line
   alone cannot tell a `localised` pass from an `undecidable` skip — both are
   green. Assert the log holds exactly one line and it matches `^localised\t`.

## Risk

### Code-health risk: low
- Test-and-docs only — no production code touched; `summarise()` gains a field
  and loses nothing, so existing consumers cannot regress · severity: low · → mitigation: none identified
- `ATTR_PAIRS = 6` roughly doubles this test's runtime (~6 s → ~11 s) on a
  module that is one file on one xdist worker · severity: low · → mitigation: none identified (measure and report the real number; drop to 4 pairs if the increase is worse than projected)

### Goal-achievement risk: low
- The claim could be satisfied vacuously if the `undecidable` precondition fired
  under the lane, reducing the outcome to flake-avoidance · severity: medium · → mitigation: inline post-phase contention_injection
- The `min`-estimator evidence is from this box only; the real lane's scheduling
  behaviour could still differ · severity: low · → mitigation: full_suite_triple_run
- The marked-block scoping means a future editor could move the carve-out list
  out of the markers and silently disarm the guard · severity: low · → mitigation: none identified (the guard errors on missing markers rather than passing, and the negative-control fixture pins that)

*(Reassessed after mitigation design: goal-achievement medium → low — the
inline `contention_injection` post-phase closes the idle-box evidence gap with
an explicit non-vacuous acceptance rule, and `full_suite_triple_run` adds the
full-lane confirmation.)*

### Planned mitigations
- timing: post-phase | name: contention_injection | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — claim could be satisfied vacuously via the undecidable skip under the lane | desc: Evaluate the localisation claim under pinned oversubscription and a real -n 4 --dist loadfile lane, requiring an observed `localised` verdict; a skip is not acceptance
- timing: after | name: full_suite_triple_run | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: high | addresses: goal-achievement — min-estimator evidence gathered on one box only | desc: Re-run the full Python suite three times under the real parallel lane (the protocol that surfaced the defect in t1500) on a quiet box with AITASK_BOARD_ATTR_VERDICT_LOG set to one shared path, then assert the log holds exactly 3 lines and all 3 match `^localised\t` — the suite's own PYTHON SUITE line cannot distinguish a pass from an undecidable skip

## Step 9 (Post-Implementation)

Current-branch mode — no worktree/branch cleanup. Merge target is `main` (plan
header). Gate: `risk_evaluated` (active set materialized at claim). Archive via
`./.aitask-scripts/aitask_archive.sh 1510`.
