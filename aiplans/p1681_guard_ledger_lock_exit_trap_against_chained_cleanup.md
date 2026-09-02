---
Task: t1681_guard_ledger_lock_exit_trap_against_chained_cleanup.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1681 — Guard `ait_ledger_lock_exit_trap` against being chained behind another command

## Context

`ait_ledger_lock_exit_trap` (`.aitask-scripts/lib/ledger_block.sh:92`) opens with
`local rc=$?`, because its whole job is to preserve the status of whatever killed
the guarded section. But `$?` reflects the command that ran *immediately before*
it, so the natural-looking consumer spelling

```bash
trap 'my_cleanup; ait_ledger_lock_exit_trap' EXIT
```

silently destroys that status: `my_cleanup` succeeds, `$?` becomes 0, the trap
exits 0 — **for a section that died**. This was measured, not theorised, in
t1657_2: a `die` from `ait_ledger_lock_release_checked` exited 0 and `ait note`
reported `NOTE_APPENDED` (success) for an append whose lock was wedged.

t1657_2 fixed only its own call site with `trap 'rc=$?; cleanup; (exit $rc);
ait_ledger_lock_exit_trap' EXIT` and deferred the seam fix here. Nothing in the
seam prevents or documents the hazard, and t1657_3 / t1657_4 both add consumers
that will want their own cleanup.

Current consumers (closed set):
- `.aitask-scripts/aitask_note.sh:360` — the only user of the seam's trap; uses the
  `(exit $rc)` workaround.
- `.aitask-scripts/aitask_gate.sh:147` — has its **own** private copy
  (`_gate_lock_exit_trap`), installed bare at three sites (lines 290, 964, 1214).
  It never calls the seam's trap, so it is untouched by this change (the task
  requires gate behaviour to be unchanged).

**Intended outcome:** the hazardous spelling can no longer ship silently. Source
enforcement (a runtime guard + a correct-by-construction parameter) rather than a
comment, per the framework preference.

### Pre-phase (risk mitigations)

1. `[pin_trap_p_rendering_matrix]` Before editing `.aitask-scripts/lib/ledger_block.sh`,
   add the first group of `tests/test_ledger_lock_exit_trap.sh`: a driver that
   installs four EXIT handlers — a bare word (`trap f EXIT`), a single-quoted
   single command (`trap 'f' EXIT`), a chained pair (`trap 'c; f' EXIT`) and a
   multi-line handler (`trap $'f\nc' EXIT`) — and, from inside each fired trap,
   asserts `trap -p EXIT` renders as `trap -- '<handler>' EXIT` with the handler
   text intact. Run it against the unmodified library and record that it passes.
   This converts the guard's parse assumption from a hand-run probe into an
   executable fact that fails loudly if bash ever changes the rendering.

## Approach

Three changes to `ait_ledger_lock_exit_trap`, in `.aitask-scripts/lib/ledger_block.sh`:

**1. Optional explicit status parameter.** `ait_ledger_lock_exit_trap [status]`.
With an argument, that argument is the status; with none, today's `$?` capture is
kept verbatim (so the three-site bare-trap contract is byte-identical). This gives
a chained consumer a *correct spelling that exists*, rather than only a forbidden
one — the task's second suggested option.

**The argument is validated against the real shell-status domain 0–255, not merely
"digits".** `exit` truncates modulo 256, so a digit-only check would let
`ait_ledger_lock_exit_trap 256` — or `512` — exit **0**, re-opening through the new
parameter the exact false-success this task exists to close. Measured on this bash:
`exit 255` → 255, `exit 256` → **0**, `exit 300` → 44, `exit 512` → **0**. An
out-of-domain or non-numeric argument is a caller bug, so it warns and exits 1
rather than being truncated.

**The check is pattern-only — no arithmetic.** Any `[[ … -le 255 ]]` form drags in
bash's arithmetic parser, which is wrong twice over: it reads a leading zero as
**octal**, so `[[ 010 -le 255 ]]` *accepts* `010` and the trap silently exits **8**
for a caller who wrote decimal ten; and `08` / `099` are invalid octal, emitting a
raw `[[: 08: value too great for base` on stderr (both measured). A 20-digit value
likewise errors with `integer expected`. A glob covers the domain exactly, silently,
and without a length pre-gate:

```bash
case "$rc" in
    [0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5]) ok=1 ;;
    *)                                                ok=0 ;;
esac
```

Verified over the whole boundary set: `0 7 9 10 99 100 199 200 249 250 255` accept;
`256 260 300 512`, `007 08 010 099`, `""`, `x`, `-1`, `1e2`, 20 digits, and
space-padded `" 7"` / `"7 "` all reject, none emitting anything on stderr. Canonical
decimal only is the right domain: `$?` never yields a zero-padded or padded form, so
rejecting `007` costs nothing and removes the octal ambiguity entirely.

**2. A misuse guard for the no-arg form.** When called with no argument, inspect
the installed EXIT trap and verify this function is the **first** command in it.
If some other command runs in front of it, the captured `$?` is untrustworthy →
`warn` with the exact remedy and refuse to report success (force `rc=1` when
`rc` is 0). "A failure reported as success is strictly worse than a wrong error
code" is the task's own framing; this makes the misuse loud and CI-visible
instead of silent.

**3. The comment.** Rewrite the function's header comment to state the contract
(first command, or pass the status) — the task's first suggested option, kept
alongside the guard rather than instead of it.

### Guard mechanics (prototyped and measured)

`trap -p EXIT` inside a command substitution reports the *parent's* trap (the
POSIX `saved=$(trap)` idiom), and bash always renders it as `trap -- 'HANDLER'
EXIT`. Verified on this bash for bare, unquoted, chained and multi-line handlers.

```bash
# Returns 0 when this function is (or cannot be shown not to be) the first
# command of the EXIT trap; 1 only when it is provably chained behind another.
_ait_ledger_exit_trap_is_first() {
    local spec handler rest
    spec="$(trap -p EXIT 2>/dev/null)" || return 0
    # Not our trap at all (called directly, or someone else's handler): nothing
    # to judge.
    case "$spec" in *ait_ledger_lock_exit_trap*) ;; *) return 0 ;; esac
    handler="${spec#trap -- \'}"
    # Unrecognised rendering: degrade to today's behaviour rather than invent a
    # failure. tests/test_ledger_lock_exit_trap.sh asserts the guard actually
    # FIRES, so a shell whose shape differs fails the suite loudly instead of
    # silently disabling the guard.
    [[ "$handler" != "$spec" ]] || return 0
    handler="${handler#"${handler%%[![:space:]]*}"}"      # strip leading blanks
    rest="${handler#ait_ledger_lock_exit_trap}"
    if [[ "$rest" != "$handler" ]]; then                  # matched at the start
        case "$rest" in ""|[[:space:]]*|";"*|"'"*|"&"*|"|"*|")"*) return 0 ;; esac
    fi
    return 1
}
```

`bash-3.2`-safe: no `mapfile`, no `declare -A`, no `${var^^}`, no `=~`.

```bash
ait_ledger_lock_exit_trap() {
    local rc=$? ok=0                  # `local rc=$?` MUST stay the first command
    if [[ $# -gt 0 ]]; then
        rc="$1"
        # Pattern-only: bash arithmetic would read '010' as octal 8 and choke on
        # '08'. See the domain note above.
        case "$rc" in
            [0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5]) ok=1 ;;
            *)                                                ok=0 ;;
        esac
        if [[ $ok -eq 0 ]]; then
            # Out of the 0-255 shell-status domain: `exit` would truncate mod 256
            # and 256/512 would land on 0 — a false success.
            warn "ait_ledger_lock_exit_trap: status '$1' is not a decimal 0-255 — treating as failure"
            rc=1
        fi
    elif ! _ait_ledger_exit_trap_is_first; then
        warn "ait_ledger_lock_exit_trap ran behind another command in the EXIT trap, so the dying status was lost. Install it first — trap 'ait_ledger_lock_exit_trap' EXIT — or pass the status explicitly: trap 'rc=\$?; my_cleanup; ait_ledger_lock_exit_trap \"\$rc\"' EXIT. Reporting a generic failure because the real status cannot be recovered here."
        # UNCONDITIONAL. `rc` currently holds the status of whatever ran in front
        # of us, which is not the section's status and must not be published as
        # if it were: a cleanup returning 42 would exit 42, a number that looks
        # meaningful and is not. A detected misuse always exits exactly 1.
        rc=1
    fi
    if ! ait_ledger_lock_release; then
        if [[ $rc -eq 0 ]]; then rc=1; fi
    fi
    exit "$rc"
}
```

### The contract, stated exactly (and where it departs from the task text)

The task's verification bullet asks for "a test that installs a chained trap,
forces a death inside the guarded section, and asserts the exit status is
**preserved**". Read literally that is unsatisfiable for the *naive* chain, and
saying so is part of the deliverable rather than a silent deviation: by the time
`ait_ledger_lock_exit_trap` is entered, `my_cleanup` has already overwritten `$?`.
The dying status is **gone before any implementation of this function runs** — no
guard, parameter or rewrite inside `ledger_block.sh` can recover it. The two
spellings therefore get two different, individually testable guarantees:

| spelling | guarantee | test |
|---|---|---|
| `trap 'rc=$?; cleanup; ait_ledger_lock_exit_trap "$rc"' EXIT` | **exact status preservation** — a section dying with 7 exits **exactly 7** | case 3 |
| `trap 'cleanup; ait_ledger_lock_exit_trap' EXIT` (naive) | **detected misuse** — exits **exactly 1** whatever the preceding command returned, with a warning naming the function and both correct spellings | cases 1, 2, 2b |
| `trap 'ait_ledger_lock_exit_trap' EXIT` (bare) | unchanged: exact preservation, no warning | case 4 |

The first row *is* "a chained trap, a forced death, and a preserved exit status" —
it satisfies the task's requirement, using the correct spelling the fix introduces.
The second row is the honest statement of what is achievable for the spelling whose
whole problem is that the information no longer exists; asserting exact `1` (not
merely "not 0") keeps it a pinned contract rather than an open assertion.

That `1` is forced **unconditionally**, and the distinction matters. On entry, `rc`
holds the status of whatever ran in front of us — the cleanup's, not the section's.
Leaving it in place (`[[ $rc -ne 0 ]] || rc=1`) means a cleanup returning 42 exits
**42**: nonzero, so the false-success bug is gone, but the number is meaningless and
reads like a real section status. Measured both ways — conditional: `cleanup rc=42`
→ exit 42 whether the section died or succeeded; unconditional: exit 1 in all four
combinations. Case 2b drives the `cleanup rc=42` path precisely because a test whose
cleanup succeeds cannot tell the two implementations apart.

Measured prototype behaviour (scratchpad, all six cases):

| spelling | section outcome | exit | warn |
|---|---|---|---|
| bare trap | `exit 7` | 7 | — |
| bare trap | success | 0 | — |
| `cleanup; exit_trap` (naive chain) | `exit 7` | **1** | yes |
| naive chain, `cleanup` returns 42 | `exit 7` / success | **1** | yes |
| `rc=$?; cleanup; exit_trap "$rc"` | `exit 7` | **7** | — |
| `rc=$?; cleanup; exit_trap "$rc"` | success | 0 | — |
| bare trap, release fails | success | 1 | — |
| explicit arg `255` | `exit 255` | 255 | — |
| explicit arg `256` / `300` / `512` | `exit 7` | **1** | yes |
| explicit arg `007` / `08` / `010` / `099` | `exit 7` | **1** | yes |
| explicit arg `""` / `x` / `-1` / `1e2` / 20 digits | `exit 7` | **1** | yes |

Rows 3 and 4 both exit **0** against today's implementation — those are the
discriminating cases for the fix itself. The `256` / `512` rows are the
discriminating cases for the range check: with a digit-only validator they exit
**0**.

**4. Convert the one chained consumer.** `.aitask-scripts/aitask_note.sh:360`
becomes the explicit-arg form, dropping the `(exit $ait_note_rc)` throwaway
subshell:

```bash
trap 'ait_note_rc=$?; note_cleanup_body; ait_ledger_lock_exit_trap "$ait_note_rc"' EXIT
```

Its `ORDER IS LOAD-BEARING` comment block (lines 350–359) is rewritten to point at
the seam's contract instead of restating the workaround. The `ait_note_rc`
shellcheck declaration at line 413 stays. This conversion is **mandatory**, not
cosmetic: under the new guard the `(exit $rc)` idiom is a chained no-arg call and
would be flagged.

**Explicitly out of scope:** collapsing `aitask_gate.sh`'s duplicate
`_gate_lock_exit_trap` onto the guarded seam. The task requires gate behaviour to
be unchanged, and gate never touches the seam's trap.

## Files

| File | Change |
|---|---|
| `.aitask-scripts/lib/ledger_block.sh` | new `_ait_ledger_exit_trap_is_first`; `ait_ledger_lock_exit_trap` gains the optional status arg + guard; header comment rewritten |
| `.aitask-scripts/aitask_note.sh` | line 360 trap → explicit-arg form; comment block 350–359 rewritten |
| `tests/test_ledger_lock_exit_trap.sh` | **new** — the discriminating suite below |

## Verification

New file `tests/test_ledger_lock_exit_trap.sh`, following `tests/test_note_append.sh`
conventions (`set -u`, `tests/lib/asserts.sh`, own `PASS`/`FAIL`/`TOTAL`, own
summary). It writes small driver scripts into a `mktemp -d` fixture, each sourcing
`terminal_compat.sh` + `stale_lock.sh` + `ledger_block.sh` from the real repo, and
asserts in the **top-level** shell (no `( … )` test bodies, so no file-backed
counter opt-in is needed). `ait_ledger_lock_release` / `stale_lock_release` are
stubbed inside the drivers where a release failure must be forced.

1. **Naive chain is detected, never reported as success** — `trap 'cleanup;
   ait_ledger_lock_exit_trap' EXIT`, section dies with 7 → exit **exactly 1**
   (asserted as `1`, not as "≠ 0", so the contract is pinned). *Fails today*
   (exits 0).
2. **The guard actually fired** — the same run emits the warning naming
   `ait_ledger_lock_exit_trap`. This is the anti-silent-disable assertion: it pins
   that the `trap -p` shape parse works on this shell, so a platform where it does
   not fails the suite instead of quietly losing the guard. It also discriminates
   case 1's `1` from an incidental `1` produced by some other path.

   2b. **Detected misuse ignores the preceding command's status** — same naive chain,
   but `cleanup` returns **42**, run twice (section dies with 7; section succeeds) →
   exit **exactly 1 + warning** in both. This is the only case that separates the
   unconditional `rc=1` from the conditional `[[ $rc -ne 0 ]] || rc=1`, which exits
   **42** here; a cleanup that succeeds cannot tell them apart.
3. **Explicit-arg chain preserves the exact status** — `trap 'rc=$?; cleanup;
   ait_ledger_lock_exit_trap "$rc"' EXIT`, section dies with 7 → exit **exactly 7**,
   no warning. This is the task's "chained trap, forced death, status preserved"
   requirement. *Fails today* (exits 0). Repeat with a section dying at **255** →
   exit **255**, pinning the top of the domain.
4. **Negative control — bare trap, death** — `trap 'ait_ledger_lock_exit_trap' EXIT`,
   section dies with 7 → exit **7**, **no** warning. Passes before and after; proves
   the guard does not fire on the sanctioned spelling.
5. **Negative control — bare trap, success** → exit **0**, no warning. The guard must
   not turn a correct success into a failure.
6. **Explicit-arg chain, success** → explicit `0` → exit **0**, no warning.
7. **Release failure still wins over success** — bare trap, successful section,
   `stale_lock_release` stubbed to fail → exit **1** (today's behaviour, unchanged).
8. **Status-domain boundary matrix** — explicit argument, one run per value.
   Accepted, exiting with that exact status and no warning: `0`, `7`, `9`, `10`,
   `99`, `100`, `199`, `200`, `249`, `250`, `255`. Rejected → exit **1 + warning**:
   `256`, `260`, `300`, `512`. Without a range check `256` and `512` both exit **0**
   — those are the mutants a digit-only validator lets through.
9. **Leading-zero matrix** — `007`, `08`, `010`, `099` all → exit **1 + warning**.
   `010` is the discriminating one: an arithmetic range check *accepts* it as octal
   and exits **8** for a caller who meant ten.
10. **Malformed argument matrix** — `""`, `x`, `-1`, `1e2`, `" 7"`, `"7 "`, and a
    20-digit value all → exit **1 + warning**.
11. **Validation is silent** — across cases 8–10, stderr carries the `warn` line and
    **nothing else**: no `value too great for base` (which `08` / `099` produce under
    an arithmetic check) and no `integer expected` (which the 20-digit value
    produces). Asserted as an exact-match on the stderr content, not a substring.

Group 0 of the same file is the inline pre-phase `pin_trap_p_rendering_matrix`
assertion set (four handler renderings × the `trap -- '…' EXIT` shape).

Suite commands:

```bash
bash tests/test_ledger_lock_exit_trap.sh     # new — run against the UNMODIFIED lib
                                             # first to record that 1/2/3 fail
bash tests/test_note_append.sh               # the seam's only chained consumer
bash tests/test_gate_ledger.sh               # gate ledger unchanged
bash tests/test_gate_lock_characterization.sh
bash tests/test_stale_lock.sh
shellcheck .aitask-scripts/lib/ledger_block.sh .aitask-scripts/aitask_note.sh
bash tests/run_all_python_tests.sh --test-dir tests   # ledger_block python twin
```

The "run the new suite before the fix" step is part of the work, not a suggestion:
the task requires the test to fail against today's implementation, and that is
recorded in the Final Implementation Notes.

## Post-implementation

Cleanup, archival and merge follow **Step 9 (Post-Implementation)** of
`task-workflow`. Working on the current branch (profile `fast`,
`create_worktree: false`), so there is no task branch to merge; Step 8d creates the
two confirmed spawned "after" mitigations.

## Risk

### Code-health risk: medium
- The guard adds textual parsing of `trap -p EXIT` output inside an exit path; on a
  shell whose rendering differs it could misjudge a correct call site and convert a
  genuine success into a failure · severity: low (residual — the rendering is now
  pinned as an executable fact by inline pre-phase `pin_trap_p_rendering_matrix`, so
  a drift fails the suite rather than a user's command) · → mitigation: inline
  pre-phase pin_trap_p_rendering_matrix
- The guard is designed to degrade to today's behaviour on an unrecognised trap
  rendering, which means it can also *silently stop guarding* on such a shell (e.g.
  macOS bash 3.2, untested here) · severity: medium · → mitigation:
  bash32_trap_shape_manual_check
- `aitask_gate.sh` keeps a byte-for-byte duplicate of the trap function, so the
  seam and its largest sibling now diverge in safety · severity: low · → mitigation:
  converge_gate_lock_exit_trap_onto_seam

### Goal-achievement risk: low
- The task's verification bullet asks for exact status *preservation* on a chained
  trap; for the naive spelling that is unsatisfiable by construction, so the plan
  splits the requirement into "exact preservation for the explicit-argument chained
  spelling" + "detected misuse for the naive one". Stated explicitly in the contract
  table rather than deviated from silently · severity: low · → mitigation: none
  (documented deviation)

### Planned mitigations
- timing: pre-phase | name: pin_trap_p_rendering_matrix | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health bullet 1 (guard could misjudge a correct call site if the `trap -p` rendering differs) | desc: pin the four EXIT-handler renderings of `trap -p EXIT` as an executable assertion before the library is touched
- timing: after | name: bash32_trap_shape_manual_check | type: manual_verification | priority: medium | effort: low | inline_risk: high | added_complexity: high | addresses: code-health bullet 2 (guard can silently stop guarding on an untested shell) | desc: on a macOS / bash-3.2 box, run `tests/test_ledger_lock_exit_trap.sh` and confirm the "guard actually fired" assertion passes there; if it does not, the seam needs shape-agnostic detection
- timing: after | name: converge_gate_lock_exit_trap_onto_seam | type: refactor | priority: low | effort: low | inline_risk: high | added_complexity: medium | addresses: code-health bullet 3 (gate keeps an unguarded duplicate) | desc: collapse `aitask_gate.sh:_gate_lock_exit_trap` onto the guarded seam function across its three bare trap sites, keeping `tests/test_gate_lock_characterization.sh` green

**Post-inline reassessment (single pass):** with `pin_trap_p_rendering_matrix`
inlined, the parse-assumption bullet drops to residual `low`. The code-health level
stays **medium** — the bash-3.2 unknown (bullet 2) is unchanged by an inline test on
this shell. Goal-achievement stays **low**.

## Implementation notes

**Pre-fix baseline (the "must fail today" requirement), measured before touching
`lib/ledger_block.sh`:** `bash tests/test_ledger_lock_exit_trap.sh` →
**35 passed, 42 failed (of 77)**, exit 1. The split is the point:

- **Group 0 passed** against the unmodified library — the inline pre-phase
  mitigation confirms the `trap -- '…' EXIT` rendering the guard parses, so the
  guard is resting on a pinned fact, not a hope.
- **Negative controls 4 / 5 / 6 / 7 passed** before the fix — they characterise
  behaviour that must not change, and a fix that broke a sanctioned spelling
  would have shown up as a *new* failure here.
- **Every discriminating case failed**: 1 (naive chain + death → **0**), 2 / 2a
  (no warning at all), 3 / 3b (explicit-arg chain → **0**), and the whole
  status-domain matrix (the argument was ignored, so every value → 0).
- **2b / 2c returned 42**, confirming in the real library the leak that made the
  unconditional `rc=1` necessary: with `[[ $rc -ne 0 ]] || rc=1` the naive chain
  publishes the *cleanup's* status, and a test whose cleanup succeeds cannot see
  it.

**Post-fix:** 77 passed, 0 failed.

**Surrounding suites, all green after the change:**

| suite | result |
|---|---|
| `tests/test_note_append.sh` (the seam's only chained consumer) | 110/110 |
| `tests/test_gate_ledger.sh` | 37/37 |
| `tests/test_gate_lock_characterization.sh` | 47/47 |
| `tests/test_stale_lock.sh` | 134/134 |
| `bash tests/run_all_python_tests.sh --test-dir tests` | PASSED (runner=pytest, exit=0) |
| `shellcheck -S warning` on both edited scripts | clean (only pre-existing SC1091 source-follow infos) |

`aitask_gate.sh` was left untouched as planned, so its three bare `_gate_lock_exit_trap`
sites are byte-identical and the gate suites above are unchanged by construction.

**No deviations from the approved plan.**

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan, in three files.
  `.aitask-scripts/lib/ledger_block.sh` gains `_ait_ledger_exit_trap_is_first`
  (reads `trap -p EXIT` from inside the firing trap and decides whether this
  function is the trap's first command) and `ait_ledger_lock_exit_trap` gains an
  optional status argument validated by a pattern-only 0–255 check, plus a
  rewritten contract comment naming the two sanctioned spellings. The no-arg
  form's `local rc=$?` capture is unchanged, so the three bare-trap sites behave
  byte-identically. `.aitask-scripts/aitask_note.sh` — the seam's only chained
  consumer — moved to the explicit-arg spelling, dropping the `(exit $rc)`
  throwaway subshell that t1657_2 had used as a workaround.
  `tests/test_ledger_lock_exit_trap.sh` is new: 258 lines, 77 assertions.
- **Deviations from plan:** None.
- **Issues encountered:** None during implementation. The two hazards the plan
  was revised for were both found in review and confirmed by measurement before
  any code was written: (1) `exit` truncates modulo 256, so a digit-only
  validator would have let `256` / `512` exit 0 and re-opened the false success
  through the new parameter; (2) `[[ $rc -ne 0 ]] || rc=1` on the misuse path
  publishes the *preceding command's* status, so a cleanup returning 42 exited
  42 — verified against the real library in the pre-fix baseline run (cases 2b /
  2c returned 42).
- **Key decisions:**
  - **Guard, not just a comment** — the task preferred source enforcement, and
    both were delivered: the guard detects the hazardous spelling, the parameter
    gives chained consumers a correct one, and the comment states the contract.
  - **The guard fails safe in every direction it cannot judge.** No EXIT trap,
    someone else's handler, or an unparseable `trap -p` rendering all return "no
    complaint", so an unexpected shell degrades to pre-t1681 behaviour rather
    than inventing a failure. That degradation would be invisible, so group 2
    asserts the guard *fires* (the warning text), not merely that the status is
    nonzero — a shell that renders traps differently fails the suite loudly.
  - **Pattern-only range check, no arithmetic.** `[[ 010 -le 255 ]]` accepts
    `010` as octal and would exit **8** for a caller who wrote decimal ten, and
    `08` / `099` make bash print `value too great for base` from inside an exit
    path. A glob covers 0–255 exactly and silently.
  - **The misuse path forces `rc=1` unconditionally**, because the value on entry
    belongs to the preceding command, not to the guarded section: publishing it
    yields a number that looks meaningful and is not.
  - **`aitask_gate.sh` deliberately untouched.** Its `_gate_lock_exit_trap` is a
    private byte-for-byte duplicate that never calls the seam, so gate behaviour
    is unchanged by construction — which is what the task required. Collapsing
    the duplicate onto the guarded seam is the spawned "after" mitigation
    `converge_gate_lock_exit_trap_onto_seam`.
- **Upstream defects identified:** None. (The `aitask_gate.sh` duplicate is a
  known, in-scope divergence recorded as a planned mitigation above, not a
  separate pre-existing defect.)
