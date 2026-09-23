---
Task: t1851_restore_into_new_window_skips_minimonitor.md
Base branch: main
Output branch: main
---

# t1851 — Spawn the minimonitor companion on a new-window restore

## Context

When a frozen agent's pane is gone (e.g. after a tmux server restart), `agent_restore.restore()`
takes the gone-pane branch and calls `_launch_into_new_window()`, which starts the replacement via
`launch_in_tmux(..., TmuxLaunchConfig(new_window=True))`. Every normal launch path (board,
codebrowser, trail screen, TUI switcher) follows `launch_in_tmux` with
`agent_launch_utils.maybe_spawn_minimonitor(session, window)`; the restore path does not, so the
restored agent comes back alone in its `agent-*` window (observed restoring t1687_1 on 2026-09-21).

Same-pane restores (`respawn_if_stamped` on the surviving stand-in) keep the window, and with it any
companion already there — they must not spawn a second one.

Out of scope: viewer windows recreated by `ait ide`'s frozen-agent prompt. That code does not exist
yet — it is t1847, whose body already carries "consider whether the minimonitor companion should
also come back with a recreated viewer window". Nothing to change here.

## Implementation

### 1. `.aitask-scripts/lib/agent_launch_utils.py` — `maybe_spawn_minimonitor(..., agent_pane=None)`

Today the helper takes the companion's identity from the window's **active pane**
(`display-message -p -t <window> '#{pane_id}'`, ~line 2121), arms the `pane-died` hook on it and
refocuses it — and its `split-window -t <window>` splits whichever pane is active. If anything
changes focus or splits into the new window between the launch and that read, the companion is
attached to, placed beside, and refocuses the wrong pane. The restore already knows the pane
(`resolve_pane_id_by_pid`), so let callers pass it:

- New keyword-only `agent_pane: str | None = None` (docstring: "the pane the companion serves;
  when given it replaces the active-pane read, and must be in the window").
- In the existing `list-panes` pass, collect the window's pane ids. When `agent_pane` is given:
  - `list-panes` failed (`rc != 0`) → `return None` (we cannot prove the pane is in this window);
  - `agent_pane` not among the listed ids → `return None` (fail closed — never place a companion
    for a pane in another window).
- Identity: `agent_pane = agent_pane or <the existing display-message read>` — i.e. the probe runs
  only when no pane was passed. Hook arming and refocus then use it unchanged.
- Split target: `-t agent_pane` when one was passed (the split lands beside the agent, in its
  window); otherwise `-t tmux_window_target(session, win_index)` as today.
- Every existing caller passes nothing, so their behaviour is byte-identical.

### 2. `.aitask-scripts/lib/agent_restore.py`

- Add `maybe_spawn_minimonitor` to the existing `from agent_launch_utils import (...)` block
  (a re-exported name, patched in tests on `agent_restore` — the seam rule only covers
  `agent_frozen_ops` functions).
- Add a small helper next to `_launch_into_new_window`:

  ```python
  def _spawn_companion(session: str, window: str, pane_id: str, root: str) -> None:
      """Give a new-window restore the companion a normal launch gets (t1851).

      Best-effort: the replacement is already running, so no companion failure may
      turn into a failed restore — `restore()` rolls back only on OSError/ValueError,
      and anything else escaping here would abandon a live agent mid-transaction.
      """
      try:
          maybe_spawn_minimonitor(session, window, agent_pane=pane_id,
                                  project_root=Path(root) if root else None)
      except Exception as exc:
          print(f"WARNING:companion not spawned in {session}:{window} ({exc})",
                file=sys.stderr)
  ```

  Why these arguments:
  - `window` is the name `unique_window_name` just minted, so the helper's name→index lookup is
    unambiguous; its prefix check (`agent-` / `create-`), `auto_spawn`, live-minimonitor and
    pane-count guards all still apply.
  - `project_root` makes it read *that project's* `project_config.yaml` and start the companion
    there. The restore runs detached under `run-shell -b`, so `Path.cwd()` (the helper's default)
    is not guaranteed to be the project.
  - `agent_pane=pane_id` — the pane `resolve_pane_id_by_pid` just resolved for the replacement —
    makes the companion follow the restored agent by identity, not by whichever pane happens to be
    active: the hook is armed on it, the split lands beside it, and focus returns to it.

- In `_launch_into_new_window`, call it only on full success — after `pane_id` resolved, just
  before `return pane_id, pane_pid, ""`:

  ```python
  _spawn_companion(target.session, window, pane_id, rec.get("root", ""))
  ```

  Not on any error return (no session / launch error / unresolvable pane), and never from the
  same-pane `respawn_if_stamped` branch in `restore()` — that branch never reaches this function.

  Update the docstring of `_launch_into_new_window` with one line saying it also spawns the
  companion (t1851).

### 3. `tests/test_minimonitor_instance_guard.py` (existing `_FakeTmux` harness for the helper)

- `test_explicit_agent_pane_wins_over_the_active_pane` — panes `%1`, `%2`, active pane `%1`,
  `agent_pane="%2"` → returns `%77`; hook recorded as `("%2", "%77")`; the `split-window` argv
  targets `%2`; the `select-pane` targets `%2`; no `display-message` call was made.
- `test_agent_pane_outside_the_window_spawns_nothing` — `agent_pane="%9"` not listed → `None`, no
  `split-window`, no hook.
- `test_agent_pane_with_unreadable_panes_spawns_nothing` — `list-panes` fails → `None`, no split.
  (Needs a small `list_rc` knob on `_FakeTmux`.)
- Existing tests unchanged (they pass no `agent_pane`), pinning the default path.

### 4. `tests/test_agent_restore.py`

- `TestNoProjectSessionBootstrapsOne._launch`: add a patch of `agent_restore.maybe_spawn_minimonitor`
  (a `Mock`) so these unit tests never reach the real tmux gateway, and return it. Existing
  assertions unchanged.
- New class `TestNewWindowRestoreSpawnsCompanion(_SwapMixin, unittest.TestCase)`:
  - `test_a_new_window_launch_spawns_the_companion_once` — attributed session; assert
    `maybe_spawn_minimonitor` called once with `("aitasks", "agent-pick-1705-…")` — i.e. the
    session and the window name actually passed to `launch_in_tmux`'s config —
    `agent_pane="%900"` (the pane resolved from the launched pid, not a re-read) and
    `project_root=Path(_ROOT)`.
  - `test_no_companion_when_the_launch_fails` — `launch_in_tmux` returns an error → not called;
    and the `no_session_for_root` refusal path → not called.
  - `test_a_companion_failure_does_not_fail_the_restore` — spawn mock raises `RuntimeError` →
    `_launch_into_new_window` still returns `("%900", 51000, "")`.
  - `test_a_same_pane_restore_spawns_no_companion` — drive `restore()` through the
    `_TMUX_OURS_AND_FIRES` fixture (`TestRecordedPaneIsOnlyAHint._run`'s shape, with
    `_launch_into_new_window` wrapped by `Mock(wraps=...)` and `maybe_spawn_minimonitor` patched)
    → neither was called.
- Patch `maybe_spawn_minimonitor` with `create=True` (the file's t1784 convention), so run
  against the unfixed module the new tests fail on behaviour (red proof), not on a missing name.

## Verification

- `python3 tests/test_agent_restore.py` and `python3 tests/test_minimonitor_instance_guard.py` —
  new tests red before the change, green after; both files green.
- Other helper callers unaffected: `python3 tests/test_tui_switcher_agent_launch.py`,
  `python3 tests/test_brainstorm_discuss_launch.py`.
- `python3 tests/test_agent_frozen_ops.py` (seam-rule guard still passes).
- Live suites that exercise the new-window branch through real tmux, now with a companion split
  into the restored window: `bash tests/test_restore_flows_live.sh`,
  `bash tests/test_restore_session_bootstrap_live.sh`, `bash tests/test_frozen_agents_acceptance.sh`.
- `bash tests/test_no_raw_tmux.sh` (no raw tmux introduced).

## Step 9

Post-implementation: commit code (`bug: … (t1851)`), then archival per task-workflow Step 9.

## Risk

### Code-health risk: low
- `maybe_spawn_minimonitor` is shared by every launch path; the new parameter must leave callers that omit it unchanged · severity: low · → mitigation: none needed — default path is untouched code, and the existing guard tests plus two caller suites run in Verification
- The live restore suites now get an extra (companion) pane in each restored `agent-*` window; an assertion that assumes a one-pane window would break · severity: low · → mitigation: none needed — the plan's Verification runs all three live suites (inspection shows none counts panes in the restored window)

### Goal-achievement risk: low
None identified.
