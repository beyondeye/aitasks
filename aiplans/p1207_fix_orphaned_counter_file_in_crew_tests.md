---
Task: t1207_fix_orphaned_counter_file_in_crew_tests.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1207 — Make the 11 orphaned-counter test files actually enforce their assertions

## Context

Eleven bash test files under `tests/` print `FAIL:` lines and still **exit 0**.
Their assertions are unenforced: a regression in any of them is invisible.

Root cause, confirmed against the t923 migration commits (`40c255342`,
`85cdd11f6`, …): these files predate the consolidation of ~136 files' inline
assertion helpers into `tests/lib/asserts.sh`. They implemented their own
file-backed counters (`COUNTER_FILE` + `_inc_pass` / `_inc_fail`) *specifically*
because their test bodies run inside `( … )` subshells for `cd` isolation. The
migration deleted the inline helpers — whose bodies called `_inc_pass` /
`_inc_fail` — and replaced them with the shared helpers, which mutate
shell-global `PASS` / `FAIL` / `TOTAL`. It left the `COUNTER_FILE` scaffolding
and the footer that reads it untouched. So:

- assertions bump shell globals that die at subshell exit;
- `_inc_pass` / `_inc_fail` survive only at a few hand-written call sites;
- the footer reads `COUNTER_FILE`, and the exit guard tests *that* value.

The t923 verify harness (`tests/lib/assert_migration_verify.sh:23-31`) could not
catch it: its authoritative signal is the `^FAIL:` line count plus exit status,
and both were unchanged (0 and 0) before and after.

**Measured severity** (asserts inside subshells / at top level; leftover
`_inc_*` call sites):

| file | asserts in subshell / top-level | `_inc_*` sites | effect |
|---|---|---|---|
| `test_crew_runner.sh` | 37 / 0 | 4 | 4 of 41 checks counted |
| `test_crew_template_includes.sh` | 32 / 0 | 0 | counter fully dead |
| `test_crew_init.sh` | 29 / 0 | 6 | 6 of 35 counted |
| `test_brainstorm_cli.sh` | 27 / 0 | 6 | 6 of 33 counted |
| `test_crew_groups.sh` | 24 / 0 | 0 | fully dead |
| `test_crew_report.sh` | 23 / 0 | 12 | 12 of 35 counted |
| `test_crew_setmode.sh` | 19 / 0 | 4 | 4 of 23 counted |
| `test_crew_status.sh` | 24 / 30 | 21 | mixed; skip-branches fabricate passes |
| `test_launch_mode_field.sh` | 7 / 0 | 0 | fully dead |
| `test_crew_addwork_output_instructions.sh` | 6 / 0 | 0 | fully dead |
| `test_agentcrew_pythonpath.sh` | 0 / 12 | 0 | fully dead (no subshells) |

**The decisive constraint:** in 10 of 11 files *every* assertion sits inside a
top-level `( … )` subshell. Deleting `COUNTER_FILE` and initialising
`PASS=0/FAIL=0/TOTAL=0` would **not** fix them — the globals still die with the
subshell. The counters must survive the subshell, which is what the original
`COUNTER_FILE` design was for. So the fix restores that property, but **inside
the shared library** rather than reinventing it eleven times.

**Not in scope, verified:** `tests/test_crew_cleanup.sh` also has `COUNTER_FILE`
+ `_inc_*`, but it never sources `asserts.sh` and routes every check through its
own file-backed `_check_contains` — it is self-consistent and correct. Left
untouched by user decision. `test_tmux_run_parity.sh`,
`test_kill_agent_pane_smart.sh`, `test_update_multiline_yaml.sh` and
`test_deps_unblock_batch.sh` were checked and cleared: the first two never source
`asserts.sh`; the last two have no subshell blocks at all.

**Intended outcome:** all 11 files exit non-zero when any assertion fails,
through one shared mechanism, with a per-file negative control proving it and a
durable guard preventing the class from recurring.

## Implementation

### Pre-phase (risk mitigations)

1. `[snapshot_suite_baseline]` Before editing `tests/lib/asserts.sh`, capture a
   regression baseline with the existing t923 harness — do **not** write a new
   one. Its interface is
   `assert_migration_verify.sh snapshot|check <baseline_file> <test_file>...`
   (`tests/lib/assert_migration_verify.sh:12-13`); both the baseline path and
   the file list are **required** positional arguments.

   **The cohort is the unaffected files only.** `check` compares FAIL-count and
   exit status and fails on any change — and the 11 in-scope files change their
   exit status *by design*, so including them would guarantee a red result that
   says nothing. They are covered instead by Step 0 (their own baseline), Step 3
   of Verification, and the per-file negative controls.

   ```bash
   SCRATCH=/tmp/claude-1000/-home-ddt-Work-aitasks/013a1d06-4fff-4c18-ab35-0aa3e11357f5/scratchpad
   IN_SCOPE="$SCRATCH/t1207_in_scope.txt"     # the 11 files, one relpath per line
   COHORT="$SCRATCH/t1207_cohort.txt"
   BASE_COHORT="$SCRATCH/t1207_baseline_cohort.txt"

   printf 'tests/test_%s.sh\n' crew_runner crew_template_includes crew_init \
       brainstorm_cli crew_groups crew_report crew_setmode crew_status \
       launch_mode_field crew_addwork_output_instructions agentcrew_pythonpath \
       > "$IN_SCOPE"

   # Every test file that sources the shared lib, minus the 11 in scope.
   grep -l 'lib/asserts\.sh' tests/test_*.sh | grep -vxF -f "$IN_SCOPE" > "$COHORT"
   wc -l < "$COHORT"        # record this number in the plan — it is the denominator

   bash tests/lib/assert_migration_verify.sh snapshot "$BASE_COHORT" $(cat "$COHORT")
   # … Step 1 and Step 2 edits …
   bash tests/lib/assert_migration_verify.sh check    "$BASE_COHORT" $(cat "$COHORT")
   ```

   Run `check` after Step 1 and again after Step 2. Any `CHANGED:` line is a
   blocking regression.

   **Exclusions are declared, never silent.** If a cohort member is
   prohibitively slow or environment-dependent (live-tmux modules are the likely
   candidates), remove it from `$COHORT` explicitly and list every removed path,
   with its reason, in the plan's Final Implementation Notes — an excluded file
   is a file this mitigation does not cover, and that has to be visible.

   **Index safety.** `tests/run_all_python_tests.sh:38-43` records that
   `tests/*.sh` "owns the real git index". Run the sweeps with the in-scope
   edits as the only working-tree changes, and after each sweep confirm
   `git status --porcelain` still lists exactly those files and nothing else
   (no staged entries). Abort and investigate if it does not.

### Step 0 — Baseline sweep (before any edit)

Record the 11 files' signature at HEAD, using the same harness the pre-phase
uses — a second baseline file, so the two cohorts never mix:

```bash
bash tests/lib/assert_migration_verify.sh snapshot \
    "$SCRATCH/t1207_baseline_in_scope.txt" $(cat "$IN_SCOPE")
```

Each line records `relpath|PASS|FAIL|TOTAL|EXIT`; the `FAIL` field is the
authoritative `^FAIL:` line count. Expect `EXIT=0` for all 11 — that is the
defect. Any file already showing `FAIL>0` here is emitting real failures today
that nothing enforces.

This baseline is **not** fed to `check` (these files' exit status changes by
design); it is read by hand in Verification §3 to classify each post-fix
failure as pre-existing or newly caused.

This is load-bearing, not ceremony: these assertions have **never** been
enforced, so any file already emitting `FAIL:` lines will start failing for real
after the fix. Record the baseline in the plan before touching anything — it is
the only way to tell a pre-existing failure apart from one this change caused.

### Step 1 — `tests/lib/asserts.sh`: opt-in subshell-safe counting

Add one new section (after the `_AIT_ASSERTS_LOADED` guard, before `assert_eq`)
and route every existing helper through it.

```bash
# --- counters --------------------------------------------------------------
# Default: mutate the caller's in-process PASS / FAIL / TOTAL, exactly as
# before. Files whose test bodies run inside `( … )` subshells lose those
# increments at subshell exit, so they opt into a file-backed record:
#
#     assert_counters_init                 # once, after sourcing this file
#     trap 'rm -f "$AIT_ASSERT_COUNTER_FILE"' EXIT
#     ...tests...
#     assert_counters_load                 # in the footer, before reporting
#     [[ "$FAIL" -eq 0 ]] || exit 1
#
# FAIL-CLOSED CONTRACT. Once counting is enabled, any failure to persist or
# re-read the record is itself a test failure. A record that is missing,
# unreadable, truncated or recreated must NEVER be reported as "0 failures" —
# that silent false-green is the exact defect this mechanism exists to remove
# (t1207).
#
# Two design points serve that contract:
#
#   * Enablement is tracked by AIT_ASSERT_COUNTERS_ENABLED, deliberately
#     SEPARATE from the path variable. "Enabled but no usable file" is then a
#     detectable state instead of degrading silently into the no-op branch.
#   * The first line is a sentinel. `>>` RECREATES a deleted file, so
#     absence-of-file is not observable at load time — absence of the sentinel
#     is. Any append failure deletes the record on purpose, converting an
#     undetectable short count into a detectable corrupted one.
#
# With AIT_ASSERT_COUNTERS_ENABLED unset, every branch below is skipped and
# behaviour is byte-identical to the pre-t1207 library — the ~245 files that
# assert at top level are unaffected.

AIT_ASSERT_COUNTER_SENTINEL="#ait-assert-counters-v1"

assert_counters_init() {
    if ! AIT_ASSERT_COUNTER_FILE="$(mktemp "${TMPDIR:-/tmp}/ait_assert_counters_XXXXXX")"; then
        echo "FAIL: assert_counters_init could not create a counter file" >&2
        exit 1
    fi
    if ! printf '%s\n' "$AIT_ASSERT_COUNTER_SENTINEL" > "$AIT_ASSERT_COUNTER_FILE"; then
        echo "FAIL: assert_counters_init could not write $AIT_ASSERT_COUNTER_FILE" >&2
        exit 1
    fi
    AIT_ASSERT_COUNTERS_ENABLED=1
    PASS=0
    FAIL=0
    TOTAL=0
    return 0
}

# $1 = P | F. Never fails the caller directly (it usually runs deep inside a
# subshell, where a non-zero return would only abort that subshell); instead an
# unpersistable record is destroyed so assert_counters_load fails closed at the
# top level, where the exit status actually matters.
_assert_counter_append() {
    [ -n "${AIT_ASSERT_COUNTERS_ENABLED:-}" ] || return 0
    if ! printf '%s\n' "$1" >> "$AIT_ASSERT_COUNTER_FILE" 2>/dev/null; then
        rm -f "$AIT_ASSERT_COUNTER_FILE" 2>/dev/null || true
    fi
    return 0
}

# Record one passing / failing check. Callers that hand-roll a check (rather
# than using an assert_* helper) call these directly; a failing caller prints
# its own `FAIL: …` line, as the helpers do.
assert_record_pass() {
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))
    _assert_counter_append P
    return 0
}

assert_record_fail() {
    TOTAL=$((TOTAL + 1))
    FAIL=$((FAIL + 1))
    _assert_counter_append F
    return 0
}

# Re-read the file-backed record into PASS / FAIL / TOTAL. A genuine no-op when
# counting was never enabled, so a footer may call it unconditionally.
assert_counters_load() {
    local t f head
    [ -n "${AIT_ASSERT_COUNTERS_ENABLED:-}" ] || return 0

    if [ ! -r "${AIT_ASSERT_COUNTER_FILE:-}" ]; then
        echo "FAIL: assert counters enabled but the record is missing or unreadable (${AIT_ASSERT_COUNTER_FILE:-<unset>})"
        TOTAL=$((TOTAL + 1))
        FAIL=$((FAIL + 1))
        return 1
    fi
    head="$(head -n 1 "$AIT_ASSERT_COUNTER_FILE")"
    if [ "$head" != "$AIT_ASSERT_COUNTER_SENTINEL" ]; then
        echo "FAIL: assert counter record was truncated or recreated (sentinel missing) — counts cannot be trusted"
        TOTAL=$((TOTAL + 1))
        FAIL=$((FAIL + 1))
        return 1
    fi
    # `|| true`: grep -c exits 1 on zero matches, which would abort under set -e.
    # tr: BSD grep/wc pad their counts (see sed_macos_issues.md).
    t="$(grep -c '^[PF]$' "$AIT_ASSERT_COUNTER_FILE" || true)"
    f="$(grep -c '^F$'    "$AIT_ASSERT_COUNTER_FILE" || true)"
    t="$(printf '%s' "$t" | tr -d '[:space:]')"
    f="$(printf '%s' "$f" | tr -d '[:space:]')"
    TOTAL="${t:-0}"
    FAIL="${f:-0}"
    PASS=$((TOTAL - FAIL))
    return 0
}
```

Then a mechanical transform of all 16 existing helpers — each has exactly one
`TOTAL=$((TOTAL + 1))`, one `PASS=$((PASS + 1))` and one `FAIL=$((FAIL + 1))`:

- delete the `TOTAL=$((TOTAL + 1))` line (the recorders bump `TOTAL`);
- `PASS=$((PASS + 1))` → `assert_record_pass`;
- `FAIL=$((FAIL + 1))` → `assert_record_fail`.

`assert_eq` becomes:

```bash
assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}
```

Both recorders end in `return 0` deliberately: they are the last statement of an
`if` branch inside test bodies that run under `set -e`, and a trailing
`[ -n … ] && printf` would return 1 when counting is off and abort the caller.

Update the file's header comment (lines 8-10) — it currently states the
in-process contract as unconditional.

### Step 2 — the 11 test files: one uniform edit

Per file, four changes. Illustrated on `tests/test_crew_groups.sh`:

**(a) Init block** — replace the hand-rolled counter (lines 11-25 there; same
block, different line numbers, in the other ten):

```bash
# before
COUNTER_FILE="$(mktemp "${TMPDIR:-/tmp}/ait_test_counters_XXXXXX")"
echo "0 0 0" > "$COUNTER_FILE"
trap 'rm -f "$COUNTER_FILE"' EXIT

_inc_pass() { local p f t; read -r p f t < "$COUNTER_FILE"; echo "$((p + 1)) $f $((t + 1))" > "$COUNTER_FILE"; }
_inc_fail() { local p f t; read -r p f t < "$COUNTER_FILE"; echo "$p $((f + 1)) $((t + 1))" > "$COUNTER_FILE"; }

# after  (must come AFTER the `. "$PROJECT_DIR/tests/lib/asserts.sh"` line)
# Test bodies run in `( … )` subshells, so the counters are file-backed.
assert_counters_init
trap 'rm -f "$AIT_ASSERT_COUNTER_FILE"' EXIT
```

Two ordering details: `assert_counters_init` must follow the `asserts.sh`
source line (in several files the counter block currently sits *above* it), and
in `test_agentcrew_pythonpath.sh` the existing trap also restores the cwd
(`trap 'rm -f "$COUNTER_FILE"; cd "$ORIG_DIR"' EXIT`) — keep that second action.

**(b) Call-site rename**, in the six files that still call the old helpers
(`crew_init` 6, `crew_status` 21, `crew_runner` 4, `crew_report` 12,
`crew_setmode` 4, `brainstorm_cli` 6 — 53 sites total):
`_inc_pass` → `assert_record_pass`, `_inc_fail` → `assert_record_fail`. Pure
rename: the recorders take no arguments and print nothing, matching the old
semantics exactly, so the adjacent `echo "FAIL: …"` lines stay put.

**(c) Footer** — replace the `read -r` from the dead file with a load, and use
`PASS`/`FAIL`/`TOTAL` uniformly (four files currently read into lowercase
`pass fail total`, one into `PASSES FAILS TOTAL`, one into `PASSED FAILED TOTAL`):

```bash
# before
read -r pass fail total < "$COUNTER_FILE"
echo "=== Results: $pass passed, $fail failed, $total total ==="
if [[ "$fail" -gt 0 ]]; then exit 1; fi

# after
assert_counters_load
echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="
if [[ "$FAIL" -gt 0 ]]; then exit 1; fi
```

Keep each file's existing summary wording and control flow — only the data
source and variable names change. The exit guards themselves are already
correct; they were simply reading a value nothing wrote.

`assert_counters_load` is called **bare**, never as `assert_counters_load ||
true`. All 11 files run under `set -e`, so a corrupted record aborts the script
non-zero on the spot; and for any future caller without `set -e`, the load also
bumps `FAIL` before returning 1, so the existing exit guard fires anyway. Both
paths are non-zero — there is no arrangement in which an unusable record prints
"0 failed" and exits 0.

**(d) Dead comment sweep** — the t923 migration left `# --- Test helpers ---`
banners with nothing under them (`test_launch_mode_field.sh:31-33`) and blank
runs where the inline block was removed (`test_crew_groups.sh:31-35`,
`test_crew_runner.sh:31-36`). Remove them.

### Step 3 — `tests/test_crew_runner_config_delivery.sh`: retire the stale note

Its header (lines 19-26) documents this defect as unfixed and explains that the
t1196 checks were placed in a new harness to route around it. After this change
the claim is false. Rewrite the paragraph to state the current rule — assertions
in that file are at top level, so it needs no counter file — and drop the
"pre-existing defect, logged separately" sentence.

### Step 4 — `tests/test_asserts_counters.sh` (new): mechanism + drift guard

A new self-contained test, structured like the healthy majority (top-level
asserts, `PASS=0/FAIL=0/TOTAL=0`, `[[ "$FAIL" -eq 0 ]] || exit 1`).

Behaviour is probed by running scenarios in a **child `bash -c`** that sources
the real `tests/lib/asserts.sh` and prints its counters, then asserting on that
output at top level. The guard test cannot use the counters it is testing to
judge itself.

1. **Subshell failure propagates** — `assert_counters_init`; a failing
   `assert_eq` inside `( … )`; `assert_counters_load` → prints `FAIL=1 TOTAL=1`.
   This is the exact scenario that is broken today.
2. **Subshell pass propagates** — same shape, passing assert → `FAIL=0 PASS=1`.
3. **Mixed** — one pass in a subshell, one fail at top level → `PASS=1 FAIL=1
   TOTAL=2`.
4. **Opt-out unchanged** — without `assert_counters_init`, a top-level failing
   assert still bumps in-process `FAIL`, and no counter file is created. Pins
   the no-op guarantee for the ~245 files that never opt in.
5. **`set -e` safety** — a child running `set -e` with a failing assert inside a
   subshell reaches its footer (the recorders return 0).
6. **Record deleted after init** — child: `assert_counters_init`, a passing
   assert inside `( … )`, then `rm -f "$AIT_ASSERT_COUNTER_FILE"`, then a
   second assert (whose `>>` recreates the file *without* the sentinel), then
   the footer. The child must exit **non-zero** and print the
   `sentinel missing` line. This is the concrete proof that a lost record
   cannot read as "0 failed".
7. **Record truncated after init** — same, but `: > "$AIT_ASSERT_COUNTER_FILE"`
   instead of `rm`. Child exits non-zero.
8. **Record unwritable** — `chmod 0444` the record, run an assert (the append
   fails, so the recorder deletes it), then load. Child exits non-zero. Skip
   with an explicit `SKIP:` line when running as root, where the mode is not
   enforced.
9. **Enabled with no file** — export `AIT_ASSERT_COUNTERS_ENABLED=1` without
   ever calling `assert_counters_init`, then `assert_counters_load`. Child
   exits non-zero. Pins that enablement is tracked separately from the path.
10. **Drift guard** — scan `tests/*.sh`, ignoring comment-only lines. No file may
   *both* source `asserts.sh` and (a) define `_inc_pass`/`_inc_fail`, or (b)
   reference a bare `COUNTER_FILE` (regex `(^|[^A-Z_])COUNTER_FILE`, so
   `AIT_ASSERT_COUNTER_FILE` does not match). `test_crew_cleanup.sh` passes: it
   never sources `asserts.sh`.

### Step 5 — docs

`CLAUDE.md` §Testing and `website/content/docs/development/_index.md` both say
bash tests are self-contained and print their own PASS/FAIL summary. Add one
sentence to each: tests whose bodies run in subshells must call
`assert_counters_init` / `assert_counters_load`, because the shared helpers'
in-process counters do not survive a subshell. This is the only doc surface that
describes the convention — there is no existing `aidocs/` page for it.

### Post-phase (risk mitigations)

1. `[assert_negctrl_anchor]` Make the negative-control loop in Verification §4
   unable to pass vacuously. For each of the 11 files it must:
   - locate the injection anchor explicitly and **hard-fail the whole
     verification** (non-zero exit, named file) when the anchor is absent or
     matches zero lines — never skip the file silently;
   - assert the injected line is present in the copy after the edit (`grep -c`
     on the exact injected text equals 1);
   - run the copy **before** injection and require exit 0 (positive control),
     then after injection and require non-zero.
   A file whose control cannot be shown to fail is reported as a verification
   failure, not counted as a pass.

## Verification

**1. Mechanism guard** — `bash tests/test_asserts_counters.sh` passes.

**2. No collateral damage to the unaffected cohort** — the pre-phase
`assert_migration_verify.sh check` run reports `VERIFY OK` over `$COHORT`. This
replaces any hand-picked sample: the cohort is derived, its size is recorded,
and every exclusion is named.

**3. Clean run of all 11** — every file exits 0. Where a file exits non-zero,
diff its `^FAIL:` lines against Step 0's `t1207_baseline_in_scope.txt`: a
failure already present in the baseline is pre-existing and routes to
`triage_enforced_crew_test_failures`; a failure absent from it was caused by
this change and blocks. Fixing a genuine failure by weakening the assertion is
out of bounds either way.

**4. Per-file negative control — mandatory, one per touched file.** Scripted, so
it is reproducible rather than a one-off manual break:

```bash
# for each of the 11: copy, inject a guaranteed-failing assert INSIDE the first
# subshell body, run the copy, require a non-zero exit.
cp "tests/test_$f.sh" "tests/negctrl_$f.sh"      # not test_* — stays out of the glob
# insert `    assert_eq "NEGCTRL" "a" "b"` after the first `cd "$TMPDIR_T` line
bash "tests/negctrl_$f.sh" >/dev/null 2>&1; rc=$?
[ "$rc" -ne 0 ] || echo "NEGCTRL FAILED TO FAIL: $f"
rm -f "tests/negctrl_$f.sh"
```

The injection point must be **inside a subshell** — a top-level failing assert
would prove nothing, since subshell propagation is the entire defect. For
`test_agentcrew_pythonpath.sh` (no subshells) inject at top level, which is
correct for that file.

Two controls frame it:
- **Positive control first:** run each unmodified copy and confirm it exits 0,
  so a non-zero result is attributable to the injected assertion and not to the
  copy being broken.
- **Pre-fix control:** run the same injection against the HEAD version of two
  representative files (`test_crew_groups.sh`, fully dead; `test_crew_report.sh`,
  partially live) in a `git worktree` at `HEAD`, and confirm they exit **0** —
  direct evidence that the defect was real and that the fix is what closed it.

**5. Lint** — `shellcheck tests/lib/asserts.sh tests/test_asserts_counters.sh`
and the 11 edited files. `TOTAL` may need the existing
`# shellcheck disable=SC2034` treatment where a footer no longer reads it.

## Step 9 (Post-Implementation)

Standard: merge to `main`, archive the task and this plan.

## Risk

### Code-health risk: medium
- `tests/lib/asserts.sh` is sourced by **256** test files, and this change
  rewrites all 16 of its helpers to route through two new recorders. A mistake
  in the recorders' exit status — e.g. a trailing `[ -n … ] && printf` returning
  1 when counting is off — would abort test bodies suite-wide under `set -e`,
  far outside the 11 files in scope · severity: medium · → mitigation: inline
  pre-phase snapshot_suite_baseline
- The 11 per-file edits are uniform but hand-applied across four touch points
  each (init block, call-site rename, footer, dead-comment sweep); a missed
  footer leaves that file silently unenforced, which looks exactly like success
  · severity: low · → mitigation: covered in-plan by the Step 4 drift guard (a
  missed footer still references a bare `COUNTER_FILE`, which the guard rejects)

### Goal-achievement risk: medium
- The per-file negative control injects a failing assertion after the first
  `cd "$TMPDIR_T` line. If a file's first subshell does not match that anchor,
  the injection lands outside the subshell — or nowhere — and the control
  proves nothing while still *looking* green. A negative control that cannot
  fail is the same blind spot this task exists to remove · severity: medium ·
  → mitigation: inline post-phase assert_negctrl_anchor
- The ~270 assertions across these 11 files have never been enforced. Turning enforcement on may
  reveal genuine pre-existing failures, forking the task into unplanned repair
  work — with a standing temptation to weaken the assertion instead of fixing
  the code · severity: medium · → mitigation: triage_enforced_crew_test_failures

### Planned mitigations
- timing: pre-phase | name: snapshot_suite_baseline | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — 256 files source asserts.sh | desc: Capture the t923 harness's per-file FAIL-count + exit-status baseline over every file sourcing asserts.sh before the library edit, and re-check after Steps 1 and 2.
- timing: post-phase | name: assert_negctrl_anchor | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — negative control may pass vacuously | desc: Hard-fail the per-file negative control when its injection anchor is missing, assert the injected line landed, and require a passing pre-injection run as positive control.
- timing: after | name: triage_enforced_crew_test_failures | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement — newly enforced assertions may reveal real failures | desc: Repair any genuine pre-existing failures that enforcement exposes in the 11 crew/brainstorm test files in a dedicated task, never by weakening the assertion.
