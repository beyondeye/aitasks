---
Task: t1130_fix_monitor_untargeted_rename_mislabels_window.md
Worktree: (current branch — fast profile, no worktree)
Branch: main
Base branch: main
---

# t1130 — Fix monitor untargeted `rename-window` mislabeling the active window as `monitor`

## Context

An explore agent's tmux window (`claude … /aitask-explore` + companion minimonitor)
was found permanently renamed to `monitor`, with `automatic-rename off` — colliding
with the real monitor window. The explore window is born correctly named
(`new-window -n agent-explore-N` via `tui_switcher._spawn_in_session`), so it was
renamed *after* creation. The only code in the repo that renames a window to
`monitor` after creation is the full monitor's `on_mount`.

**Root cause.** `.aitask-scripts/monitor/monitor_app.py`:
- `_rename_window_argv(pane)` (lines 62–74) appends `-t <pane>` **only when `pane`
  is truthy**; when `os.environ.get("TMUX_PANE")` is `None`/`""` it returns the
  **untargeted** `["tmux","rename-window","monitor"]`.
- `on_mount` (lines 487–490) runs that argv. tmux resolves an untargeted
  `rename-window` to the **attached client's active window** — and `rename-window`
  is what flips `automatic-rename` off. So a `monitor_app` that starts without
  `TMUX_PANE` in its environment, while an `agent-explore-N` (or any) window is
  active, permanently mislabels that window `monitor`.
- This is a **t941 follow-up**: t941 (commit `bc50549d3`) pinned the rename to
  `$TMUX_PANE` but deliberately kept the untargeted fallback, and
  `tests/test_monitor_rename_window_target.sh:51–54` currently **asserts** the
  buggy untargeted form — the regression guard enshrines the failure mode.

**Intended outcome.** Make it impossible for the monitor's `on_mount` to rename a
window it cannot positively identify as its own. Fail safe: when `TMUX_PANE` is
absent, issue **no** rename rather than renaming an arbitrary active window.

Scope: root cause "B" from the folded `t_fix_agent_launch_tui_window_reuse`
(AgentCommandScreen reusing a remembered `monitor` window) is **already fixed** by
t1115 (`should_default_to_new_window`, `agent_command_screen.py:136–152`, tested in
`tests/test_agent_command_dialog_default_session.py`) — out of scope here.

## Approach (fail-safe, decision in the pure oracle)

Keep the decision inside the already-unit-tested pure function `_rename_window_argv`
so the fix is testable without a live tmux server (matching the existing test).

### 1. `.aitask-scripts/monitor/monitor_app.py`

- **`_rename_window_argv(pane)`** (lines 62–74): when `pane` is falsy, return an
  **empty list** (`[]`) instead of the untargeted argv. Update the docstring to
  state that an unidentifiable own-pane yields *no* rename (fail-safe) — never a
  fallback to the attached client's active window.

  ```python
  def _rename_window_argv(pane: str | None) -> list[str]:
      """Build the `tmux rename-window monitor` argv, pinned to *pane*.

      Returns an EMPTY list when *pane* is falsy: without $TMUX_PANE there is no
      reliable way to identify the monitor's own window, and an untargeted
      rename-window resolves to the attached client's *active* window — which,
      with automatic-rename off, would permanently mislabel an unrelated window
      (e.g. an agent-explore window) as `monitor`. Fail safe: issue no rename.
      See t941 / t1130.
      """
      if not pane:
          return []
      return ["tmux", "rename-window", "-t", pane, "monitor"]
  ```

- **`on_mount`** (lines 486–492): guard on the returned argv so a skip issues no
  subprocess:

  ```python
  try:
      rename_argv = _rename_window_argv(os.environ.get("TMUX_PANE"))
      if rename_argv:
          subprocess.run(rename_argv, capture_output=True, timeout=5)
  except Exception:
      pass
  ```

### 2. `tests/test_monitor_rename_window_target.sh`

Flip the regression guard from blessing the bug to guarding the fix:
- Keep the truthy-pane assertion: `_rename_window_argv('%7')` → `tmux rename-window -t %7 monitor`.
- Change the `None` and `''` assertions to expect an **empty** argv (no rename).
  The test prints `' '.join(...)`, so both now print an empty line; assert
  `""` for lines 2 and 3. Update the file header comment (it currently documents
  the untargeted fallback as intended) to describe the fail-safe no-rename behavior.

### Not in scope (deliberate)
- **Single-instance guard in `.aitask-scripts/aitask_monitor.sh`** (mirroring
  `aitask_minimonitor.sh:33–42`): orthogonal to this bug — with Fix A the rename is
  already skipped when the pane can't be identified, and the guard wouldn't help the
  actual trigger (a monitor legitimately starting in its own fresh window). Leave as
  a possible separate hardening follow-up; noted in Final Implementation Notes.

## Verification

- **Unit/pure oracle:** `bash tests/test_monitor_rename_window_target.sh` → all pass,
  with the falsy-pane cases now asserting no rename.
- **Negative control (bug reproduction):** confirm the *old* behavior is what the
  test now forbids — before the fix the same test would show `tmux rename-window
  monitor` for `None`/`''`; after, an empty argv. (The single test file captures
  both the fixed truthy path and the previously-buggy falsy path.)
- **Live smoke (optional, manual):** in a tmux session, `env -u TMUX_PANE ait monitor`
  from a pane while a differently-named window is active must **not** rename the
  active window; a normal `ait monitor` (TMUX_PANE set) must still name its own
  window `monitor`.
- Broader regression: `bash tests/test_monitor_focus_switch.py`-adjacent monitor
  tests unaffected (no signature change; `_rename_window_argv` still returns a list).

## Risk

### Code-health risk: low
- Change is confined to one pure function (`_rename_window_argv`) + its single `on_mount` caller + one test; the normal (`TMUX_PANE` set) path is byte-for-byte unchanged, so regression surface is minimal. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The fix is trigger-agnostic (fail-safe on any `TMUX_PANE`-less launch), so it eliminates the mislabel without needing to identify the exact launcher that stripped `TMUX_PANE`. That launcher remains undiagnosed — a diagnostic gap, not a delivery gap; capture it in Final Implementation Notes and cover via the optional live smoke. · severity: low · → mitigation: none needed (optional post-impl investigation)

## Step 9 (Post-Implementation)
Standard cleanup/archival per task-workflow Step 9: fast profile works on the current
branch (no worktree/merge). Run declared gates (`risk_evaluated`) via `ait gates run
1130`, then archive with `./.aitask-scripts/aitask_archive.sh 1130`.

## Final Implementation Notes
- **Actual work done:** Exactly as planned. `_rename_window_argv(pane)` in
  `.aitask-scripts/monitor/monitor_app.py` now returns `[]` when `pane` is falsy
  (instead of the untargeted `tmux rename-window monitor`); `on_mount` guards on the
  returned argv (`if rename_argv:`) so a skip issues no subprocess. The regression
  test `tests/test_monitor_rename_window_target.sh` was flipped so the `None`/`''`
  cases assert an empty argv (no rename) and its header comment updated. 3/3 pass;
  module compiles; oracle behavior confirmed (fail-safe on falsy, `-t <pane>` pinned
  on truthy).
- **Deviations from plan:** None.
- **Issues encountered:** (1) The internal plan externalizer hit
  `MULTIPLE_CANDIDATES` (several stale internal plan files); resolved with
  `--internal <path>`. (2) During Step 8, `monitor_app.py` initially appeared to
  carry pre-existing uncommitted t1111_4 work — but that work was committed to HEAD
  as `c8f9ce642` mid-session (main advanced), so the working-tree diff isolated to
  this fix. Committed only the two task files explicitly.
- **Key decisions:** (a) Kept the decision inside the pure `_rename_window_argv`
  oracle rather than inlining in `on_mount`, so it stays unit-testable without a live
  tmux server. (b) Chose fail-safe *skip* over any attempt to re-derive the own pane
  when `$TMUX_PANE` is absent — there is no reliable alternative source for "my own
  window", so renaming an arbitrary active window is always wrong. (c) Left the
  `aitask_monitor.sh` single-instance guard (mirroring `aitask_minimonitor.sh`) out
  of scope: orthogonal to this bug and would not address the actual trigger.
- **Scope narrowing (recorded):** Folded `t_fix_agent_launch_tui_window_reuse`
  (root cause B, AgentCommandScreen window-reuse) was found already fixed by t1115
  (`should_default_to_new_window`, tested), so t1130 was narrowed to root cause A.
- **Upstream defects identified:** None.

