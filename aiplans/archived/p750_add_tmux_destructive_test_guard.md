---
Task: t750_add_tmux_destructive_test_guard.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Adds a shared pre-flight guard `tests/lib/require_no_tmux.sh` and wires it into the 8 tests that destructively manipulate tmux. The guard aborts (exit 2) with a clear, actionable message if `$TMUX` is set (test invoked from inside a tmux pane) or if any tmux server is reachable on the user's default socket (`tmux list-sessions` returns 0). The aborted message names the offending sessions and tells the user to run from a fresh terminal outside tmux, killing any existing server only after saving in-progress work.

## Files Modified

### New

- **`tests/lib/require_no_tmux.sh`** (new, ~60 lines)
  - Exposes a single function `require_no_tmux`.
  - Guard 1: `[[ -n "${TMUX:-}" ]]` → "cannot run from inside a tmux session" + invocation hint.
  - Guard 2: `command -v tmux && tmux list-sessions >/dev/null 2>&1` → "refuses to run while other tmux sessions are alive. Detected sessions: <names>" + recovery steps.
  - Idempotent via `_AIT_REQUIRE_NO_TMUX_LOADED` (matches the `lib/venv_python.sh` convention).
  - Does not depend on tmux being installed for guard 1; guard 2 silently skips when tmux is absent (in which case the test's own `SKIP: tmux not available` check handles it).

### Modified (sourcing the helper)

For each test below, the helper is sourced after the existing tmux/Python availability `SKIP` checks and before any `mktemp`/`new-session` operation.

- **`tests/test_kill_agent_pane_smart.sh`** — added `SCRIPT_DIR=` (the test previously only tracked `REPO_ROOT`); sourced the helper before fixture creation.
- **`tests/test_multi_session_monitor.sh`** — sourced the helper after the existing `lib/venv_python.sh` source.
- **`tests/test_multi_session_primitives.sh`** — sourced the helper after the existing `LIB_DIR=` setup.
- **`tests/test_tmux_control.sh`** — added `SCRIPT_DIR=`; sourced the helper before `make_fixture` is defined.
- **`tests/test_tmux_control_resilience.sh`** — added `SCRIPT_DIR=`; sourced the helper before `make_fixture` is defined.
- **`tests/test_tmux_exact_session_targeting.sh`** — sourced the helper after the existing `PROJECT_DIR=` setup.
- **`tests/test_tmux_run_parity.sh`** — added `SCRIPT_DIR=`; sourced the helper before fixture creation.
- **`tests/test_tui_switcher_multi_session.sh`** — sourced the helper after the existing `lib/venv_python.sh` source.

## Probable User Intent

Triggered by a confirmed tmux-session crash on `2026-05-05 09:18:53` that killed every pane in the user's `aitasks` tmux server (PID 3132), including 15+ hour wall-clock TUIs holding 200 MB–800 MB of state. Diagnosis correlated the crash window with a fixture tmux server named `ait_killsmart_595689` whose name signature uniquely matches `tests/test_kill_agent_pane_smart.sh:42` (`SESSION="ait_killsmart_$$"`). The user confirmed the test was run from inside the aitasks tmux session.

The tests *do* attempt isolation via `TMUX_TMPDIR=$(mktemp -d)` + `unset TMUX`, but historical leak paths (kill-server cleanup, pane-id collisions, control-client teardown) have shown that isolation can fail. Rather than chase a precise leak path through 8 tests' worth of subprocess and asyncio code, the user requested a defense-in-depth pre-flight guard that simply refuses to run any of these tests from a context where a leak could harm in-progress work.

This aligns with the user-memory note `feedback_tmux_stress_tasks_outside_tmux.md`: "for tasks whose tests destructively manipulate tmux (kill -KILL clients, kill-session, kill-server), surface the risk and recommend running implementation from a shell outside the user's aitasks tmux."

## Final Implementation Notes

- **Actual work done:**
  - Created `tests/lib/require_no_tmux.sh` exposing `require_no_tmux()`.
  - Wired the helper into 8 destructive tmux tests, each at the right insertion point (after SKIP-if-no-tmux/no-python checks, before fixture/server creation).
  - Verified live: with `TMUX=...` set, the guard fires with the inside-tmux message; with `TMUX` unset but the user's `aitasks` server alive, the guard fires with the "other sessions alive" message naming `aitasks`. Exit code is 2 in both cases.
  - Verified syntax with `bash -n` on all 8 modified tests + the new helper.

- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).

- **Issues encountered:** N/A.

- **Key decisions:**
  - **Shared helper, not inline copy-paste.** All 8 tests share the same risk pattern, so the guard is a single-source-of-truth function in `tests/lib/`. Matches the `feedback_single_source_of_truth_for_versions.md` user-memory rule and the existing `tests/lib/venv_python.sh` convention.
  - **No opt-out env var.** The user explicitly asked the guard to "abort the test … because it can cause crashes." Adding `AIT_TEST_ALLOW_TMUX=1` would invite the very footgun the guard exists to prevent. Anyone who genuinely needs to bypass it can comment out the helper source line locally.
  - **Exit code 2** (not 1) so a future test runner can distinguish "guard refused" from a real assertion failure.
  - **Both guards in one helper.** Guard 1 ($TMUX set) is strictly redundant with guard 2 (sessions alive), but produces a more specific error message — worth keeping the user-facing clarity.
  - **`paste -sd, -`** to comma-join the session names — portable across BSD and GNU coreutils.
  - **Did NOT investigate the underlying leak path** in `monitor.tmux_monitor.kill_agent_pane_smart` or `monitor.tmux_control` that allowed the original crash. The guard prevents recurrence; root-causing the leak path is a candidate for a follow-up task if the project wants to remove the guard later or trust the isolation in CI without ssh.
