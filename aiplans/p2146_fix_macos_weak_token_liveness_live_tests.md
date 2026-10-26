---
Task: t2146_fix_macos_weak_token_liveness_live_tests.md
Base branch: main
Output branch: main
---

# t2146 — make the weak-token live tests platform-correct on macOS

## Context

t2142 fixed the macOS AF_UNIX socket-path overflow. With that fixed, four live
tmux suites now get far enough to fail on something t2142 never touched. macOS
has no `/proc`, so `get_pid_starttime_kind` returns `ps`, a token with only
one-second resolution. `lock_holder_liveness` (`.aitask-scripts/lib/pid_anchor.sh:253-278`)
deliberately answers `unknown` for a matching `ps` token. A token that coarse
cannot rule out a PID reused within the same second, so only a `proc` token can
give `alive`. The tests hard-code the Linux verdict:

| suite | failing on macOS | why |
|---|---|---|
| `tests/test_lock_anchor_tmux_live.sh` | 1/11 — "reads back as alive" | expects `alive` |
| `tests/test_live_endpoint_tmux_live.sh` | 11/16 | the resolver answers `LIVE_NONE:holder_unknown` (`aitask_live_endpoint.sh:195-198`) before it reaches the agent check or the pane mapping |
| `tests/test_note_with_live_composition.sh` | 6/117 — 1e/1f/1g, 3a/3f/3g | same resolver gate |
| `tests/test_sync_holder_pane_live.sh` | 6/51 — S1c, S1h, S1i, S1c-a, S1c-e, S2c | `aitask_sync.sh:1240-1244` sends a non-`alive` holder to `unknown_liveness`, whose stderr line is fixed text (no `@holder_action` pane naming) |

Separately, `tests/test_tmux_control.sh:22` defaults `PYTHON_BIN` to bare
`python3`. Here that is `/usr/bin/python3`, which has no PyYAML, so importing
`monitor.tmux_control` → `monitor_core` fails.

**Decision (confirmed with the user): a test-side fix.** Each test asserts the
verdict that is correct for the token kind the product records. Cases that only
mean something with a provably-alive holder print a visible
`SKIP: … — not counted` line when the token is weak. A stronger macOS token is
product work and goes to a follow-up. It is feasible: a probe on this machine
read a microsecond start time through
`proc_pidinfo(PROC_PIDTBSDINFO)` via ctypes. The CLI `sysctl kern.proc.pid.<n>`
is an unknown oid on Darwin, so there is no pure-shell route.

Work on the current branch (profile `fast`), no worktree.

## Implementation

### 0. Pre-fix control (run before editing anything)

Run each suite on this macOS host and record the failing assertion names and
counts. These are the control the fix is measured against:
`test_lock_anchor_tmux_live.sh`, `test_live_endpoint_tmux_live.sh`,
`test_note_with_live_composition.sh`, `test_sync_holder_pane_live.sh`,
`test_tmux_control.sh`. All of them use `require_isolated_tmux`, not
`require_clean_ait_server`, so they run inside this tmux session. t2142 ran
them here.

**Sweep for the same root cause beyond the named four.** Also run these on
macOS: `tests/test_crash_recovery_pid_anchor.sh` (line 350 asserts `alive`
unconditionally) and `tests/test_lock_live_holder_gate.sh` (lines 215 and 261
assert `alive`). These are the non-live suites that consume real tokens. Also
run each sibling that defaults to bare `python3` and imports `monitor.*`,
with `/usr/bin/python3`:
`test_tmux_run_parity.sh`, `test_tmux_control_resilience.sh`,
`test_kill_agent_pane_smart.sh`, `test_multi_agent_window_substrate.sh`,
`test_frozen_standin_spike.sh`.
Rule: if a failure is the same one-line expectation swap or the same
`PYTHON_BIN` default, fix it here and report it as **scope expansion**. If it
needs restructuring, file a follow-up task. Never drop it silently.

### 1. Shared helper — `tests/lib/proc_fixtures.sh`

Add these next to `dead_pid_fixture`, inside the existing load guard. They use
the same identity the product records, never `uname`, so each test follows the
token kind the lock really carries.

**Three-way, fail-closed.** Only two outcomes select a branch: `strong`, and
the *supported* `ps` limitation, `weak`. Everything else is a fixture or
identity failure and has to fail the test. That covers: `pid_anchor.sh` not
sourced, no usable token (`-` / empty), kind `none` or an unrecognised kind,
and a `ps` kind whose token does not re-derive from `ps`. Collapsing any of
these into `weak` would let the platform-correct `unknown` assertion pass over
broken identity recording, because the product also answers `unknown` for a
missing token (review finding, verified: stubbing `_pid_starttime_ps` to fail
gives token `-`, kind `none`, and both sides `unknown`).

```bash
# liveness_token_class <pid> — classify the identity token this host records
# for a LIVE <pid>. stdout + status:
#   strong (0)  kind `proc`: lock_holder_liveness can answer `alive`
#   weak   (0)  kind `ps` with a real, re-derivable ps token: the supported
#               no-/proc limitation (macOS/BSD); liveness reads `unknown` BY
#               DESIGN (pid_anchor.sh)
#   nothing, status 2   pid_anchor.sh is not sourced (fixture setup error)
#   nothing, status 3   no usable token, or kind none / unrecognised, or a ps
#                       kind whose token does not match ps: identity is broken
# Status 2/3 print a diagnostic on stderr. Callers MUST treat them as a test
# failure, never as "weak".
liveness_token_class() {
    local pid="${1:-}" kind tok
    declare -F get_pid_starttime_kind >/dev/null && declare -F get_pid_starttime >/dev/null || {
        echo "proc_fixtures: source .aitask-scripts/lib/pid_anchor.sh before liveness_token_class" >&2
        return 2
    }
    kind="$(get_pid_starttime_kind "$pid")"
    tok="$(get_pid_starttime "$pid")"
    if [[ -z "$tok" || "$tok" == "-" ]]; then
        echo "proc_fixtures: pid '$pid' has no usable identity token (kind=$kind)" >&2
        return 3
    fi
    case "$kind" in
        proc) echo strong ;;
        ps)
            [[ "$(_pid_starttime_ps "$pid" 2>/dev/null)" == "$tok" ]] || {
                echo "proc_fixtures: pid '$pid' kind=ps but its token does not re-derive from ps" >&2
                return 3
            }
            echo weak ;;
        *)  echo "proc_fixtures: pid '$pid' has unrecognised token kind '$kind'" >&2
            return 3 ;;
    esac
}

# expected_live_verdict <pid> — the verdict a LIVE <pid> reads back as here:
# `alive` (strong) or `unknown` (weak). On a class failure it prints NOTHING
# and returns that status. An assert_eq against it then fails loudly
# ("" vs the product's verdict) instead of agreeing on `unknown`.
expected_live_verdict() {
    local cls rc=0
    cls="$(liveness_token_class "$1")" || rc=$?
    (( rc == 0 )) || return "$rc"
    case "$cls" in strong) echo alive ;; weak) echo unknown ;; esac
}

# skip_weak_token <what> — announce a case that needs a provably-alive holder
# and cannot have one on this host. Same "— not counted" shape as the
# suite's other conditional skips.
skip_weak_token() {
    echo "SKIP: $1 (weak ps identity token, no /proc — liveness reads unknown by design) — not counted" >&2
}
```

**Caller rule, for all four suites.** Classify each holder pid **once**, up
front, with `cls="$(liveness_token_class "$PID")" || rc=$?`. A non-zero status
is a counted `FAIL: <label>: identity fixture invalid (status N)` followed by
the summary and exit 1. It never picks the weak branch and never skips. Only
`strong` or `weak` reaches the branching below. `TOKEN_CLASS` names the variable
used in steps 2-5 (`HOLDER_CLASS` / `LIVE_CLASS` / `PANE_CLASS` per file).

Source `proc_fixtures.sh` in each of the four suites, right after `pid_anchor.sh`.
`test_live_endpoint_tmux_live.sh` sources `pid_anchor.sh` only inside Case 4,
so move that source up to the top of the file. `test_sync_holder_pane_live.sh`
does not source it at all yet, so add it there.

### 2. `tests/test_lock_anchor_tmux_live.sh`

- Classify `$PANE_PID` per the caller rule. A class failure is a counted FAIL.
- Close the sentinel hole in the existing equality checks. Lines 231-232
  compare `get_pid_starttime` / `get_pid_starttime_kind` against the recorded
  values, and both sides can be `-` / `none`. Add `rec_tok` ≠ `-`/empty and
  `rec_kind` ∈ {`proc`,`ps`} assertions, stated separately ("the claim recorded
  a usable identity token").
- Line 233: compare with `"$(expected_live_verdict "$PANE_PID")"` instead of
  the literal `alive`, and put the class/kind in the label. No case is skipped:
  on both platforms the verdict is asserted, not waived. Update header bullet 3.

### 3. `tests/test_live_endpoint_tmux_live.sh`

- Factor the duplicated summary/exit block into `report_and_exit()` and use it
  at every place that prints the summary today.
- After `0a` (claim succeeded) and before Case 2, add a **weak-token block**
  that runs when `PANE_CLASS` (caller rule, from `$PANE_PID`) is `weak`. A
  class failure is a counted FAIL and `report_and_exit`, never this block:
  - `W1.` unseeded t1 → `LIVE_NONE:holder_unknown`, exit 0 (the liveness gate
    answers before the agent check: a successful resolution, never `holder_dead`)
  - `W2.` after `write_task 1 "claudecode/opus5"` → still
    `LIVE_NONE:holder_unknown`. This shows the seed is not what decides here,
    which is the weak-token counterpart of the Case 2/Case 1 ordering pair.
  - `skip_weak_token "Cases 1-4: PID→pane correlation needs a provably-alive holder"`
    then `report_and_exit`.
- Add a header paragraph explaining the platform split.

### 4. `tests/test_note_with_live_composition.sh`

- Classify `$LIVE_PID` (= `$$`) once into `LIVE_CLASS`, per the caller rule. A
  failure here is a counted FAIL plus summary/exit. In addition, `LIVE_TOKEN`
  must not be `-`: the forged `remote_host` / `live_lock` YAML embeds it, so a
  sentinel there would test a different lock. Add a helper:
  `live_reason() { if [[ $LIVE_CLASS == strong ]]; then echo "$1"; else echo LIVE_NONE:holder_unknown; fi; }`.
  When the token is weak, print one line before 1e:
  `NOTE: weak identity token — 1e-1g expect holder_unknown (the liveness gate answers first); write-before-live is still asserted in full`.
- 1e/1f/1g: pass `"$(live_reason LIVE_NONE:agent_unknown)"`, and likewise for
  `agent_unsupported:codex` and `no_pane`. The other five `assert_durable_first`
  checks per case are unchanged. That composition contract is what §1 tests,
  and it holds on both platforms.
- §3: classify `$PANE_PID` into `PANE_CLASS` (caller rule; a failure is a
  counted `3-setup` FAIL that skips the rest of §3 like the existing setup
  failure does).
  - 3a selects its expected reason from `PANE_CLASS`.
  - 3c/3d/3e/3h are unchanged.
  - 3f/3g: when strong, as today. When weak, assert `3f-weak.` line 2 ==
    `LIVE_NONE:holder_unknown`, then `skip_weak_token "3f/3g: the positive LIVE_PANE line"`.
- Update the comment at line 104 ("holder_unknown cannot arise from a real
  claim on this machine"). That is true on Linux only.

### 5. `tests/test_sync_holder_pane_live.sh`

- After the holder pane starts: `HOLDER_CLASS` from `liveness_token_class "$PANE_PID"`.
  A class failure goes to the file's existing `fail_setup` (exit 1). Then
  `EXPECT_REASON` = `live_lock` (strong) | `unknown_liveness` (weak).
- Source `.aitask-scripts/lib/pid_anchor.sh` + `tests/lib/proc_fixtures.sh` here.
  The fixture's `lock_yaml_live` (`tests/lib/sync_fixture.sh:131`) derives its
  own token. On macOS it writes `pid_starttime: -` with kind `ps`, so the
  product reads `unknown` through the **no-token** path, not the weak-token
  path. That is the same sentinel hole, inside the fixture. Fix
  `lock_yaml_live` to record `get_pid_starttime` / `get_pid_starttime_kind`
  from `pid_anchor.sh`, so the macOS lock carries a real `ps` token and the
  `unknown_liveness` verdict comes from the supported limitation.
  `sync_fixture.sh` sources `"$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"`
  itself (it already requires `PROJECT_DIR`). It has **10 callers**:
  `test_sync_auto_commit_scoping`, `_autostash_ignored`, `_protect_paths`,
  `_holder_pane_live`, `_fetch_exclusion`, `test_metadata_partial_sync_recovery`,
  `test_sync_failopen_probes`, `_rebase_gate`, `_guarded_merge`,
  `_deferral_and_quarantine`. Run all ten on macOS **before** the change (add
  this to step 0) and after it. The verdict stays `unknown` on macOS and
  `alive` on Linux (the same `/proc` field 22), so no caller should change
  outcome. Any caller that does change is a finding to report, not something
  to paper over.
- S1c and S1c-a assert `$EXPECT_REASON`.
- S1h/S1i, S1c-e and S2c come from the `live_lock` `@holder_action` wording.
  When strong, as today. When weak, assert the `unknown_liveness` wording
  instead: `"the holder could not be verified as gone"`. Use it once in S1 as
  `S1h-weak.`; S1i, S1c-e and S2c are skipped through `skip_weak_token`.
- S1d/S1e/S1f, S2a/S2b, S3 and E1/E2 already pass on macOS (pane resolution runs
  for `unknown_liveness` too, `aitask_sync.sh:1108`) and stay unconditional.
- Add a header line about the platform split.

### 6. `tests/test_tmux_control.sh`

Replace line 22 with the pattern from `tests/test_tmux_spawn_path_live.sh:44-46`:

```bash
# The cases import monitor.tmux_control -> monitor_core, which needs `yaml`; a
# bare system python3 may lack it, so resolve the framework interpreter.
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$REPO_ROOT/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="${PYTHON_BIN:-$(require_ait_python 2>/dev/null || echo python3)}"
```

An explicit `PYTHON_BIN` still wins. Apply the same change to any sibling the
step-0 sweep finds failing in the same way (scope expansion).

### 7. Lint

`shellcheck` every edited file, including `tests/lib/proc_fixtures.sh`.

### Post-phase (risk mitigations)

1. [linux_strong_token_pin] In `tests/test_crash_recovery_pid_anchor.sh`, near
   Test 8, source `tests/lib/proc_fixtures.sh` (if it is not already sourced)
   and add:
   - unconditional, live pid: `liveness_token_class "$ANCHOR_PID_8"` exits 0 and prints `strong` or `weak`. `expected_live_verdict` is non-empty and equals `lock_holder_liveness` on the pid's real token/kind.
   - inside the existing `uname == Linux` guard: the class is `strong` and `expected_live_verdict` == `alive`. This pins Linux CI to the strong branch, so the skip path cannot be taken there without a failure.
   - unconditional **negative contract cases** (the review finding), each run in a `( … )` subshell, checking stdout empty plus the exact status:
     a. identity broken: override `_pid_starttime_ps() { return 1; }` **and** `_pid_starttime_proc() { return 1; }` → status 3. This is the reviewer's simulation, made portable. It is the case where both sides would have agreed on `unknown`, and `expected_live_verdict` must now print nothing.
     b. dead pid (`dead_pid_fixture`) → status 3 (no token).
     c. unrecognised kind: override `get_pid_starttime_kind() { echo bogus; }` → status 3.
     d. ps-kind mismatch: override `get_pid_starttime_kind() { echo ps; }` and `get_pid_starttime() { echo 123456789; }` (a /proc-shaped token next to a `ps` kind) → status 3. Do **not** stub `_pid_starttime_ps` for this. On a host without /proc, `get_pid_starttime` reads that same function, so the re-derive check would compare the stub with itself and pass (verified in planning: that version printed `weak`, rc 0).
     The cases (a)-(d) were checked against a scratch copy of the helper in planning: (a) rc 3, (b) rc 3, (c) rc 3, corrected (d) rc 3, live `$$` → `weak` rc 0 on this macOS host. The reviewer's simulation reproduced too: token `-`, kind `none`, product `unknown`.
     e. not sourced: `bash -c '. tests/lib/proc_fixtures.sh; liveness_token_class $$'` → status 2.
     This file asserts in its own top-level shell. If any new assertion has to run inside `( … )`, the counters must move out of the subshell. Assert on captured `$(…)`/status values in the parent shell, or opt into `assert_counters_init` / `assert_counters_load` as CLAUDE.md requires.
   - If step 0 shows line 350's unconditional `alive` fails on macOS, switch it to `expected_live_verdict` (scope expansion).
   - Pre-fix control: temporarily revert the helper to the first design (non-`proc` ⇒ `unknown`), watch negative case (a) fail, then restore.

## Verification

1. **Pre-fix control** (step 0): record the failures for each suite.
2. **Post-fix, macOS**: run each of the four suites plus `test_tmux_control.sh`
   on its own, with `PYTHON_BIN` **unset**, so the venv default is what gets
   exercised. Each must end `ALL TESTS PASSED`.
   Check that the `SKIP: … — not counted` / `NOTE:` lines appear on stderr. The
   control assertions (W1/W2, 3f-weak, S1h-weak) must run and pass, which shows
   the macOS branch asserts something and is not empty.
   Also check that every suite's class line (or equivalent) shows `weak` from a
   real `ps` token, not a sentinel.
3. **Linux route**: no Linux box here. Show that the strong-token branch is
   still the one Linux takes (see the post-phase mitigation), and read the diff
   to confirm every strong branch is the original assertion unchanged.
4. Re-run the sweep suites from step 0 that were fixed in scope.
5. `shellcheck` is clean on all edited files.

## Risk

### Code-health risk: low
- The new platform branch could take the weak/skip path for the wrong reason: a missing `pid_anchor.sh` source, a `-` token, kind `none`, or a `return 2` read as "weak". On macOS that would hide broken identity recording behind an `unknown` that matches the product's. On Linux it would quietly skip the correlation cases (review finding: the first design did exactly this). Addressed in the main body by the three-way, fail-closed `liveness_token_class`, and pinned by the post-phase's negative contract cases. Linux CI would then go green while quietly skipping the pane-correlation and `live_lock` cases, with coverage lost and nobody told. · severity: medium · → mitigation: inline post-phase linux_strong_token_pin
- Four suites get edited by hand. The strong branch could drift from the original assertions, which would change what Linux tests. · severity: low · → mitigation: none (diff review in Verification 3)

### Goal-achievement risk: low
- On macOS the PID→pane correlation, the agent check and the `live_lock` stderr naming stay unexercised (explicit SKIPs). The suites go green, but macOS live delivery is still degraded in the product. This was accepted by design; the product fix is separate. · severity: low · → mitigation: macos_strong_pid_token

### Planned mitigations
- timing: post-phase | name: linux_strong_token_pin | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: platform branch silently routes Linux to the weak/skip path | desc: Contract test for liveness_token_class — Linux pin (strong, alive), a both-platform agreement check against lock_holder_liveness, and negative cases (broken identity, dead pid, bogus kind, ps mismatch, unsourced) that must fail closed
- timing: after | name: macos_strong_pid_token | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: macOS live features stay degraded (weak ps token ⇒ unknown) | desc: Add a strong macOS identity token kind (proc_pidinfo PROC_PIDTBSDINFO start time, µs) to pid_anchor.sh so lock_holder_liveness can return alive on macOS; then drop the weak-token SKIPs in the four live suites

## Step 9 (Post-Implementation)

Current-branch mode: no merge. Commit code (`bug: … (t2146)`) and the plan
separately, then run gates (`risk_evaluated`), archive with
`./.aitask-scripts/aitask_archive.sh 2146`, and push.

## Final Implementation Notes (to fill)

The **Upstream defects identified** bullet should record
`.aitask-scripts/lib/pid_anchor.sh:66 — macOS has only the weak ps token, so
every live-holder consumer (ait note --with-live, sync pane naming, the
LOCK_LIVE_HOLDER gate) degrades to unknown there`, and note that it is covered
by the `macos_strong_pid_token` after-mitigation (Step 8d). In Step 8b, decline
a duplicate.
