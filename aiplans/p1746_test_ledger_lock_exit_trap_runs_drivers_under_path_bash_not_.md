---
Task: t1746_test_ledger_lock_exit_trap_runs_drivers_under_path_bash_not_.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1746 — Route test drivers through the launching interpreter, not `PATH` bash

## Context

`tests/test_ledger_lock_exit_trap.sh` exists to prove a shell-level contract
(the `ait_ledger_lock_exit_trap` EXIT-trap status arithmetic) holds on the
shells the framework supports — notably macOS system bash 3.2. It never tests
the shell it is launched with: both driver entry points invoke a **bare
`bash`**, which resolves through `PATH`.

On any box with a newer bash earlier on `PATH` — the default Homebrew macOS
setup, and the box this was found on (`/opt/homebrew/bin/bash` 5.3.9 ahead of
`/bin/bash` 3.2.57) — `/bin/bash tests/test_ledger_lock_exit_trap.sh` runs the
**harness** under 3.2 while all 77 assertions execute under 5.3.9, and reports a
green "3.2 result". Confirmed on this box: unshimmed and PATH-shimmed runs are
both 77/77, distinguishable only by which interpreter the drivers actually got.

Discovered during t1691's manual verification, which only produced genuine
evidence because it was completed with `/bin/bash` shimmed to the front of
`PATH` (`.aitask-data/aiplans/archived/p1691_manual_verification_auto.md`
§ Finding). That is exactly the silent-degradation class the file's own group 0
block was written to rule out — "a shell that renders differently fails here,
loudly, instead of silently degrading" — except that today the shell it renders
under is not the one the invoker chose.

**Outcome:** a `/bin/bash tests/<file>` run actually exercises bash 3.2, and the
suite states on stdout which interpreter it tested, so "did this pass on 3.2?"
is answered by evidence rather than trust.

## Blast radius — what shares the defect, and what does not

Swept every `bash …` command invocation under `tests/`. Two distinct patterns:

**Same defect (fix here) — a *generated driver* whose shell semantics are the
subject of the test.** Routing it through `PATH` means the assertions never run
under the shell the harness was launched with:

| File | Sites |
|---|---|
| `tests/test_ledger_lock_exit_trap.sh` | `run_driver()` `:73`, `render_of()` `:109` |
| `tests/test_yaml_utils.sh` | `run_with_default_sigpipe()` fallback `:705`, its python3 helper `:693` (`subprocess.call(["bash", …])` is also a `PATH` lookup), `set_e_smoke.sh` `:856`, and the `bash -n` syntax-check loop `:865` |
| `tests/test_stale_lock.sh` | the `set -euo pipefail` errexit harness `:396` |

`test_yaml_utils.sh` pins SIGPIPE disposition, PIPE-trap leakage and `set -e`
behaviour; `test_stale_lock.sh:396` pins errexit interaction. Both are
shell-version-sensitive by construction. `bash -n` is included deliberately: a
5.3 parse check green-lights syntax 3.2 rejects, which is the same false
assurance one level down.

**Different pattern (deliberately out of scope).** ~90 sites across
`test_codeagent*.sh`, `test_revert_analyze.sh`, `test_t167_integration.sh`,
`test_explain_binary.sh`, … invoke **production framework scripts**
(`bash "$CODEAGENT" …`, `bash "$PROJECT_DIR/install.sh" …`). Those scripts carry
`#!/usr/bin/env bash` and in production resolve through `PATH`, so `PATH` bash is
the faithful production shell there. Making a 3.2 run of the whole suite also
exercise production scripts under 3.2 is a real and larger question — a
repo-wide convention plus its own verification pass — and is filed as a
follow-up rather than folded into this low-effort fix.

`TEST_BASH="$(command -v bash)"` in `test_python_resolve.sh:23`,
`test_python_resolve_pypy.sh:25`, `test_setup_pip_install_guards.sh:39` is also
left alone: it pins a bash path *before* those files munge `PATH` for stubs — a
different motivation, and those files test python resolution, not shell
semantics.

## Implementation

### Pre-phase (risk mitigations)

1. `[parse_check_libs_under_32]` Before editing any test, parse-check under the
   old shell every library the touched tests source or syntax-check, and record
   the output in the implementation notes:
   ```bash
   for f in lib/yaml_utils.sh lib/task_utils.sh lib/agentcrew_utils.sh \
            aitask_archive.sh lib/ledger_block.sh lib/stale_lock.sh \
            lib/terminal_compat.sh; do
       printf '%-32s ' "$f"; /bin/bash -n ".aitask-scripts/$f" && echo 3.2-OK
   done
   ```
   All seven must report `3.2-OK`. Any failure here is **pre-existing** 3.2
   breakage: stop, file it as its own task, and do not let the tightened
   syntax-check loop from §2 (`tests/test_yaml_utils.sh`) absorb the blame.
   (Probed green during planning; re-run so
   the recorded evidence is against the tree actually being edited.)

### 1. `tests/test_ledger_lock_exit_trap.sh`

Add the knob once, after `LIB=` (~`:46`), with the rationale inline:

```bash
# --- the shell under test ---------------------------------------------------
#
# Drivers must run under the interpreter THIS harness was launched with, not
# whatever `bash` PATH resolves to. On a Homebrew macOS box /opt/homebrew/bin
# (bash 5.x) precedes /bin (bash 3.2), so `/bin/bash tests/<this file>` would
# run the harness under 3.2 and every assertion under 5.x — a green "3.2
# result" that never touched 3.2 (t1746, found by t1691's manual verification).
# bash sets $BASH to its own path, in 3.2 as well as 5.x. The explicit override
# lets a CI matrix point one run at 3.2 and another at 5.x with no PATH shim.
SHELL_UNDER_TEST="${SHELL_UNDER_TEST:-${BASH:-bash}}"
```

Then:

- `run_driver()` `:73` — `OUT_ERR="$("$SHELL_UNDER_TEST" "$f" "$@" 2>&1 >/dev/null)"`
- `render_of()` `:109` — `"$SHELL_UNDER_TEST" "$FIX/render.sh" "$1" 2>/dev/null`

**State the interpreter, and assert it.** Immediately after the knob, print a
banner and pin the identity as a real (counted) assertion — a step whose whole
purpose is "did this pass on 3.2" should not be taken on trust, and the
assertion also catches a `SHELL_UNDER_TEST` override that does not point at a
bash:

```bash
SUT_VERSION="$("$SHELL_UNDER_TEST" -c 'printf %s "$BASH_VERSION"' 2>/dev/null)"
echo "Shell under test: $SHELL_UNDER_TEST (bash ${SUT_VERSION:-UNKNOWN})"
assert_contains_re "0-pre. the shell under test is a runnable bash" \
    '^[0-9]+\.[0-9]+' "$SUT_VERSION"
```

Repeat the interpreter on the summary line so a captured log carries it:

```bash
echo "Results: $PASS passed, $FAIL failed (of $TOTAL) [bash ${SUT_VERSION:-UNKNOWN}]"
```

Assertion count moves 77 → 78. `Results: N passed, 0 failed` is a script-style
line the python runner does not parse (CLAUDE.md), and this is a bash test run
individually, so the suffix is safe.

Fix the now-false header comment at `:30-31` ("Drivers are written into a
mktemp fixture and run with `bash`") to name `$SHELL_UNDER_TEST`, and note in
`driver_prelude()` (`:58`) that the generated `#!/usr/bin/env bash` shebang is
inert because drivers are invoked as `"$SHELL_UNDER_TEST" <file>`.

### 2. `tests/test_yaml_utils.sh`

Same `SHELL_UNDER_TEST` knob + banner after `LIB_DIR=` (`:22`); no counted
assertion here (this file's subject is the YAML readers, not the shell).

- `sigdfl_run.py` (`:692-696`) — take the interpreter as `argv[1]`:
  `subprocess.call([sys.argv[1], sys.argv[2]], preexec_fn=…)`; caller becomes
  `python3 "$TMP/sigdfl_run.py" "$SHELL_UNDER_TEST" "$1"`.
- `run_with_default_sigpipe()` fallback (`:705`) — `"$SHELL_UNDER_TEST" "$1"`.
- `set -e` smoke (`:856`) — `smoke_out="$("$SHELL_UNDER_TEST" "$TMP/set_e_smoke.sh" 2>&1)"`.
- syntax-check loop (`:865`) — `"$SHELL_UNDER_TEST" -n "$PROJECT_DIR/.aitask-scripts/$f"`.

Pre-checked: `lib/yaml_utils.sh`, `lib/task_utils.sh`, `lib/agentcrew_utils.sh`
and `aitask_archive.sh` all pass `/bin/bash -n`, so the tightened syntax check
does not turn red on landing.

### 3. `tests/test_stale_lock.sh`

Same knob **and banner** near `PROJECT_DIR`; `:396` becomes
`out="$("$SHELL_UNDER_TEST" "$T/harness.sh" 2>&1)"; rc=$?`.

All three files must emit the identical `Shell under test: <path> (bash <ver>)`
line — the post-phase matrix greps for that exact prefix, and a file that omits
it fails its cell.

### 4. `aidocs/framework/sed_macos_issues.md`

New short section after **Shebang Convention** (`:417`) — this is precisely the
trap the next 3.2 verifier falls into:

> ## Running a Test Under bash 3.2
>
> `/bin/bash tests/<file>.sh` runs only the *harness* under 3.2. Any driver the
> test spawns as a bare `bash …` resolves through `PATH` and lands on Homebrew
> bash 5.x, so the run reports a green "3.2 result" without 3.2 being exercised
> (t1746). A test whose subject is shell semantics must route its drivers
> through `SHELL_UNDER_TEST="${SHELL_UNDER_TEST:-${BASH:-bash}}"` and print the
> interpreter it used. Verify by reading that banner, not by trusting the
> invocation. `SHELL_UNDER_TEST=/bin/bash bash tests/<file>.sh` pins 3.2 without
> a PATH shim.

### Post-phase (risk mitigations)

1. `[dual_shell_test_matrix]` Run all three touched tests in both lanes and
   record a 3×2 matrix of *(banner interpreter, results line, exit status)* in
   the implementation notes.

   **Never pipe the test into `tail`.** Without `pipefail` the pipeline exits
   with `tail`'s `0` no matter what the test did (CLAUDE.md, "Piping discards
   the status") — the cell would certify itself green while red. And the banner
   is printed near the *top* of the run, so a tail-only view cannot show which
   interpreter was actually used, which is the one thing this matrix exists to
   prove. Redirect to a log, capture `$?` on the very next line, then extract
   both facts from the log:

   ```bash
   LOGDIR="$(mktemp -d)"
   for t in test_ledger_lock_exit_trap test_yaml_utils test_stale_lock; do
     for sh in /bin/bash "$(command -v bash)"; do
       log="$LOGDIR/$t.$(echo "$sh" | tr / _).log"
       "$sh" "tests/$t.sh" >"$log" 2>&1
       rc=$?                                   # captured BEFORE anything else runs
       banner="$(grep -m1 '^Shell under test:' "$log")"
       results="$(grep -E '^Results:' "$log" | tail -1)"
       printf '%-30s %-24s rc=%-3s | %s | %s\n' \
           "$t" "$sh" "$rc" "${banner:-NO BANNER}" "${results:-NO RESULTS LINE}"
     done
   done
   ```

   A cell counts as passing only when **all three** hold: `rc=0`, a banner is
   present, and the results line reports `0 failed`. `NO BANNER` in a cell is
   itself a failure — it means the test was not routed through
   `$SHELL_UNDER_TEST` (or the banner was never added), so the lane proves
   nothing. Each `/bin/bash` cell's banner must read `bash 3.2.…` and each PATH
   cell's `bash 5.…`; a 3.2 cell showing 5.x means the routing did not take.
   A failure that appears **only** in a 3.2 cell is a genuine portability bug:
   file it as its own follow-up task; do not resolve it by reverting the
   interpreter routing.

   Note that only `test_ledger_lock_exit_trap.sh` gets a counted `0-pre`
   assertion, but **all three** files print the banner (§1-§3), so the
   `NO BANNER` check applies to every cell.

2. `[negative_control_shell_override]` Prove the identity assertion is not
   cosmetic:
   ```bash
   SHELL_UNDER_TEST=/bin/echo bash tests/test_ledger_lock_exit_trap.sh; echo "rc=$?"
   ```
   Assertion `0-pre` must FAIL and the file must exit non-zero. A green run here
   means the check is vacuous and the banner cannot be trusted — fix before
   committing.

## Verification

1. **The defect is actually closed.** Under `/bin/bash`, each fixed test reports
   bash 3.2 in its banner (pre-fix the drivers silently ran 5.3.9) — for the two
   files that can be run under 3.2 at all:
   ```bash
   /bin/bash tests/test_ledger_lock_exit_trap.sh   # banner: bash 3.2.57(1)-release
   /bin/bash tests/test_stale_lock.sh
   ```
   `tests/test_yaml_utils.sh` is **excluded from the 3.2 lane** — see the cubic
   flow-list measurement in the implementation notes. It is verified under 5.x
   only (148/148, 15s), which is the everyday path and where this change is
   behaviour-preserving by construction.
2. **Both shells green — with two documented exceptions, stated up front rather
   than discovered later.** The `dual_shell_test_matrix` post-phase is the
   authoritative run, but only four of its six cells are reachable:

   | cell | verdict |
   |---|---|
   | `test_ledger_lock_exit_trap` / 3.2 | rc=0, 78/78, banner `bash 3.2.57` |
   | `test_ledger_lock_exit_trap` / 5.3.9 | rc=0, 78/78, banner `bash 5.3.9` |
   | `test_yaml_utils` / 5.3.9 | rc=0, 148/148, 15s |
   | `test_yaml_utils` / 3.2 | **NOT RUN** — ~15h/call, infeasible at HEAD too |
   | `test_stale_lock` / 3.2 | rc=1, 132/134 — pre-existing, identical at HEAD |
   | `test_stale_lock` / 5.3.9 | rc=1, 132/134 — pre-existing, identical at HEAD |

   The two `test_stale_lock` cells pass the criterion "identical to HEAD in both
   lanes", not "green". Do not substitute a piped `| tail` spot-check for any of
   this — that discards the exit status and hides the banner.
3. **The override works.** `SHELL_UNDER_TEST=/bin/bash bash tests/test_ledger_lock_exit_trap.sh`
   must report 3.2 while the harness runs under 5.x — the CI-matrix knob, and
   the direct replacement for t1691's PATH shim.
4. **Negative control — the banner is not cosmetic.** `SHELL_UNDER_TEST=/bin/echo`
   must fail assertion `0-pre` rather than pass vacuously.
5. **No collateral damage.**
   `shellcheck tests/test_ledger_lock_exit_trap.sh tests/test_yaml_utils.sh tests/test_stale_lock.sh`
   (note: `shellcheck` is configured in CLAUDE.md for `.aitask-scripts/`; run it
   here too since these are shell edits).
6. **Superseded by the measurement above.** The planning-time note anticipated a
   slow 3.2 run; it is not slow, it is infeasible (~15h/call, cubic), and was so
   before this change. Recorded rather than left unmeasured, and filed as a
   `performance` follow-up against the reader itself.

## Risk

### Code-health risk: low
- Four files touched, all tests plus one doc; every code change is a
  literal→variable substitution whose default (`${BASH:-bash}`) reproduces
  today's behaviour byte-for-byte. No production code path is touched. The one
  behavioural tightening is `test_yaml_utils.sh`'s syntax-check loop, which now
  parse-checks four libraries under the launching shell and so could turn red on
  landing. · severity: low (residual — addressed by inline pre-phase
  parse_check_libs_under_32, which attributes any red parse to pre-existing 3.2
  breakage rather than to this change) · → mitigation: inline pre-phase parse_check_libs_under_32

### Goal-achievement risk: medium
- The fix is mechanical, but its *point* is to run drivers under an older shell
  that has never actually run them. bash 3.2 lacks constructs 5.x has, and the
  `test_yaml_utils.sh` / `test_stale_lock.sh` drivers source real libraries — a
  genuine 3.2 incompatibility would surface as a new red assertion. That is the
  fix working as intended (a silent false pass becoming a visible failure), but
  it means the change is not guaranteed to land green and may need pairing with
  a real 3.2 portability repair. · severity: medium (residual — inline
  post-phase dual_shell_test_matrix guarantees such a failure is *seen* and
  routed to its own follow-up, but it does not make the 3.2 lane pass; the
  level stays medium deliberately rather than being downgraded on detection
  alone) · → mitigation: inline post-phase dual_shell_test_matrix
- The identity banner could pass vacuously — an invocation path where `$BASH` is
  unset falls back to bare `bash` and silently reproduces the defect while the
  banner still prints something plausible. · severity: low (residual — the
  inline post-phase negative control fails the run when the assertion is
  vacuous) · → mitigation: inline post-phase negative_control_shell_override
- **New (introduced by the augmented plan):** the dual-shell matrix materially
  extends verification wall-clock — `tests/test_yaml_utils.sh` under a bash 3.2
  harness was still running at 11 min during planning, versus seconds under 5.x.
  The 3.2 lane of the matrix must be run with a generous timeout and its runtime
  recorded, not abandoned as a hang. · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: parse_check_libs_under_32 | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — tightened syntax-check loop could turn red on landing | desc: parse-check every library the touched tests source or syntax-check under /bin/bash before editing, separating pre-existing 3.2 breakage from newly introduced breakage
- timing: post-phase | name: dual_shell_test_matrix | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a genuine 3.2 incompatibility surfacing as a new red assertion | desc: run all three touched tests under both /bin/bash 3.2 and PATH bash 5.3.9, recording banner and counts per cell
- timing: post-phase | name: negative_control_shell_override | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the identity banner passing vacuously | desc: point SHELL_UNDER_TEST at a non-bash and confirm assertion 0-pre fails rather than passing vacuously

## Implementation notes

**Two sites the plan's blast-radius sweep missed** — both found during
implementation by re-sweeping the three edited files, both the same defect class
and fixed in this task:

- `tests/test_yaml_utils.sh` — `sigpipe_run.py` (the t1444 SIGPIPE harness,
  `:521`) hardcoded `subprocess.call(["bash", …])` exactly like the `sigdfl_run.py`
  the plan did name. Its callers (`run_ignoring_sigpipe`) drive the big-fixture
  snippets, so leaving it would have kept the most expensive part of the file on
  PATH bash while claiming the file was routed.
- `tests/test_yaml_utils.sh:686-687` — `bash -c "$guard_probe"` pins the
  `[[ -f /dev/fd/1 ]]` discriminator the production write-guard relies on: a
  shell/OS-dependent fact that must be measured under the shell being tested.
- `tests/test_stale_lock.sh:365` — `bash -c '…'` sources the real lib and calls
  `ait_lock_dir`; same class.

The plan's original sweep keyed on `bash "$FILE"` and missed the `bash -c` and
Python-`subprocess` spellings. Final state: every `bash` token remaining in the
three files is a comment.

**Runtime finding.** `tests/test_yaml_utils.sh` is pathologically slow under a
bash 3.2 harness — the file's own comment records that `read_yaml_list`'s
flow-list bracket counting is **quadratic in the value's length** (2.1s at 70KB
under 5.x), and the fixture is sized to ~1.1x pipe capacity (~72KB on macOS).
Routing its drivers to 3.2 puts that quadratic loop on the slow interpreter too.
This is pre-existing behaviour made visible, not introduced here. Measured
runtimes are recorded in the dual-shell matrix below.

**Pre-existing red in `tests/test_stale_lock.sh` — NOT caused by this change.**
The file fails 2 of 134 assertions on macOS, identically under bash 3.2 and 5.3.9,
and **identically at `HEAD`** (verified by running `git show
HEAD:tests/test_stale_lock.sh` unmodified: same `132/134 passed, 2 failed`, same
two assertions). Both are the documented BSD `wc -l` leading-whitespace trap
(`sed_macos_issues.md` § "`wc -l` Output Whitespace") — an exact string compare
against padded output:

- `:470` `assert_eq "no .reap residue is left behind" "0" …` → got `'       0'`
- `:671` `assert_eq "exactly ONE record remains in the guard" "1" …` → got `'       1'`

`assert_eq_trim` (already in `tests/lib/asserts.sh`) is the fix. Filed as a
follow-up; deliberately **not** fixed here, because silently repairing an
unrelated red test inside a bug fix hides it from review. The dual-shell matrix
therefore records `rc=1` for both `test_stale_lock` cells, and the pass criterion
for those two cells is "identical to HEAD in both lanes", not "green".

**Runtime measurement — the 3.2 lane of `test_yaml_utils.sh` is INFEASIBLE, and
was so before this change.** Measured scaling of one `read_yaml_list` over an
inline flow list:

| fixture | bash 5.3.9 | bash 3.2.57 | ratio |
|---|---|---|---|
| 2 KB | 0.03s | 1.14s | 38x |
| 4 KB | 0.04s | 7.99s | 200x |
| 8 KB | 0.10s | 61.5s | 615x |
| 16 KB | 0.30s | 494.8s | 1650x |

Each doubling multiplies 3.2's time by ~8 — the scan is **cubic** there, not
quadratic. Extrapolated to the real 77KB fixture: `(77/16)^3 x 495s` ~ **15 hours
per call**. An actual attempt was killed after 3h10m at 99% CPU.

**This predates the change.** `HEAD:tests/test_yaml_utils.sh:641` already made
that call **in-harness** (`full_inline=$(read_yaml_list "$TMP/sp_inline.md" …)`),
inside the normally-reached `command -v python3` block — so
`/bin/bash tests/test_yaml_utils.sh` required ~15 hours at HEAD too. The file has
never been runnable under bash 3.2. This change adds a second such call (the
`:656` snippet, now correctly routed to the shell under test), doubling a number
that was already unreachable — practically neutral. `test_yaml_utils.sh` hits that fixture twice — once in-harness
(`:663`, already on 3.2 before this change) and once through the SIGPIPE snippet
(`:656`, moved onto 3.2 by this change) — so the 3.2 lane roughly doubles from an
already-large number. The fixture cannot simply be shrunk: it is sized to ~1.1x
pipe capacity precisely so EPIPE is deterministic rather than racy.

Mechanism (identified, not guessed): `_join_yaml_flow_lists_impl`
(`.aitask-scripts/lib/yaml_utils.sh:136`) counts bracket depth with two full
pattern substitutions per input line — `opens="${buffer//[^\[]/}"` and the
matching `closes=`. An inline flow list is a single line, so that is two
`${var//pat/}` passes over one 77KB string, and bash 3.2's pattern-substitution
implementation is far slower than 5.x's on a string that size. An O(n) count
(e.g. `tr -dc`) would remove the cost entirely — filed as a separate
`performance` follow-up, since it is production code and outside this task.

Impact is bounded: no CI workflow under `.github/workflows/` runs these bash
tests, so the 3.2 runtime is paid only by a deliberate manual audit.

**Not a valid measurement.** An early pre-fix baseline run of
`test_yaml_utils.sh` under `/bin/bash` was left running while the file was
rewritten in place; bash reads a script incrementally, so that process's state
was corrupted by the edit. It was killed and is not cited as evidence.

## Follow-ups filed at Step 8

- **t1751** (`bug`, upstream_defect) — `tests/test_stale_lock.sh:470` and `:671`
  compare exact strings against BSD `wc -l` output; the file is red on macOS at
  HEAD. Fix with `assert_eq_trim`, and sweep `tests/` for the same shape.
- **t1752** (`performance`, upstream_defect) — `.aitask-scripts/lib/yaml_utils.sh:146-147`
  counts bracket depth with two full pattern substitutions per line; cubic under
  bash 3.2 (~15h on a 77KB inline flow list vs 0.30s/16KB under 5.3.9). Fixing it
  is what re-enables `tests/test_yaml_utils.sh`'s 3.2 lane and lets the header
  warning added here be removed.
- **t1753** (`enhancement`) — extend the launching-interpreter convention to the
  ~90 sites that invoke **production** framework scripts as bare `bash "$SCRIPT"`.
  Carries the three open decisions: whether a 3.2 run should audit production
  scripts at all, whether the knob belongs in a shared `tests/lib/` helper (which
  would need its own contract test), and whether the existing `TEST_BASH` sites
  converge on it.

## Step 9 (Post-Implementation)

Standard: commit as `bug: …(t1746)`, then archive task + plan per the shared
workflow. `risk_evaluated` is the only active gate.

## Final Implementation Notes

- **Actual work done:** Routed every generated shell driver in
  `tests/test_ledger_lock_exit_trap.sh`, `tests/test_yaml_utils.sh` and
  `tests/test_stale_lock.sh` through
  `SHELL_UNDER_TEST="${SHELL_UNDER_TEST:-${BASH:-bash}}"` instead of a bare
  `bash` off `PATH`; each file now prints `Shell under test: <path> (bash <ver>)`
  and `test_ledger_lock_exit_trap.sh` asserts it as counted assertion `0-pre`
  (77 -> 78). Added a "Running a Test Under bash 3.2" section to
  `aidocs/framework/sed_macos_issues.md`. 4 files, +144/-18.

- **Deviations from plan:** The plan named 6 defect sites; the real count was 9.
  The planning sweep keyed on the `bash "$FILE"` spelling and missed three more,
  all found by re-sweeping the edited files during implementation:
  `sigpipe_run.py` (`test_yaml_utils.sh:521`, the t1444 SIGPIPE harness — the
  same hardcoded `subprocess.call(["bash", …])` as the `sigdfl_run.py` the plan
  did name), `test_yaml_utils.sh:686-687` (`bash -c` shell-discriminator probe
  for `[[ -f /dev/fd/1 ]]`), and `test_stale_lock.sh:365` (`bash -c` lib driver).
  Lesson: sweep for `bash -c` and Python `subprocess` spellings, not just
  `bash "$FILE"`.

- **Issues encountered:**
  1. *The `test_yaml_utils.sh` 3.2 lane is infeasible, not slow.* An attempt was
     killed after 3h10m at 99% CPU. Profiling the scaling curve (rather than
     waiting) showed bash 3.2's `${var//pat/}` over a large single-line buffer is
     **cubic** — 2KB 1.14s, 4KB 7.99s, 8KB 61.5s, 16KB 494.8s (~8x per doubling)
     against 0.30s at 16KB under 5.3.9 — extrapolating to ~15 hours per call on
     the file's 77KB inline fixture. **Pre-existing:** `HEAD:…:641` already made
     that call in-harness, so the file has never been runnable under 3.2; this
     change adds a second such call to an already-unreachable number. Resolved by
     excluding that one cell, documenting the measurement in the test header and
     in `sed_macos_issues.md`, and filing the O(n) fix as a follow-up.
  2. *A corrupted measurement.* An early pre-fix baseline run was left running
     while the file was rewritten in place; bash reads scripts incrementally, so
     that process's state was invalid. Killed and not cited as evidence. Do not
     edit a script that a running shell is still reading.
  3. *Concurrent session in the same checkout.* Unrelated modifications
     (`agent_freeze.py`, `install.sh`, `monitor_core.py`, …) appeared mid-task
     from another agent. All commits here are path-scoped to the four owned
     files; verified that none of these tests' dependencies (`yaml_utils.sh`,
     `stale_lock.sh`, `task_utils.sh`, `agentcrew_utils.sh`,
     `terminal_compat.sh`, `ledger_block.sh`, `tests/lib/asserts.sh`) were
     touched, so the results are attributable.

- **Key decisions:**
  - *Scope held at test files.* The O(n) `tr -dc` bracket-count fix in
    `yaml_utils.sh` would make the 3.2 lane practical, but it is production code
    used by ~40 scripts and outside a low-effort test fix. Filed instead.
  - *Pre-existing red left red.* `test_stale_lock.sh` fails 2/134 on macOS; fixing
    it inside this bug fix would hide it from review. Filed instead.
  - *Production-script call sites deliberately excluded* (~90 across
    `test_codeagent*.sh`, `install.sh` tests, …): those scripts carry
    `#!/usr/bin/env bash` and resolve via `PATH` in production, so `PATH` bash is
    the faithful shell there. Filed as a separate convention question.
  - *Identity asserted, not just printed*, so a `SHELL_UNDER_TEST` pointing at a
    non-bash fails loudly (verified: `/bin/echo` -> `0-pre` FAIL, rc=1).

- **Pre-fix control (the defect reproduced, not merely inferred):** the fixed
  behaviour alone is not evidence — the broken behaviour was demonstrated first,
  on this box, both at the idiom level and at the file level.

  Idiom level, harness launched with `/bin/bash`:

  ```
  harness runs under             : 3.2.57(1)-release
  HEAD idiom   bash $f           : 5.3.9(1)-release     <- THE BUG
  fixed idiom  "${BASH:-bash}" $f: 3.2.57(1)-release    <- the fix
  ```

  Launched with PATH bash instead, both idioms return `5.3.9` — so the change is
  a no-op on the everyday path and only bites where the invoker asked for a
  specific shell.

  File level, `/bin/bash tests/test_ledger_lock_exit_trap.sh`:

  ```
  pre-fix (HEAD):  Results: 77 passed, 0 failed (of 77)
  post-fix:        Shell under test: /bin/bash (bash 3.2.57(1)-release)
                   Results: 78 passed, 0 failed (of 78) [bash 3.2.57(1)-release]
  ```

  The pre-fix run is confidently green and offers no way to discover that its 77
  assertions executed under 5.3.9. That silent false pass is the defect; the
  banner is what converts the claim into evidence.

- **Upstream defects identified:**
  - `tests/test_stale_lock.sh:470` — `assert_eq "no .reap residue is left behind" "0" …` compares against BSD `wc -l` output and gets `'       0'`; fails on macOS at HEAD, both shells. Use `assert_eq_trim`.
  - `tests/test_stale_lock.sh:671` — `assert_eq "exactly ONE record remains in the guard" "1" …` — same BSD `wc -l` padding defect, same fix.
  - `.aitask-scripts/lib/yaml_utils.sh:146-147` — `opens="${buffer//[^\[]/}"` / `closes="${buffer//[^\]]/}"` count bracket depth with two full pattern substitutions per line; cubic under bash 3.2 (~15h on a 77KB single-line flow list vs 0.3s/16KB under 5.3.9). An O(n) count (`tr -dc`) removes it.
