---
priority: medium
effort: medium
depends: [t826_9, t826_6, t826_7]
issue_type: feature
status: Done
labels: [cross_repo, aitask_projects, tui_switcher]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 12:03
updated_at: 2026-05-26 18:54
completed_at: 2026-05-26 18:54
---

## Context

Spun off from t826_5 brainstorm (`aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`).

The user-facing payoff of the brainstorm. Wires STALE entries into
the TUI switcher's Session: row (dimmed, with `(stale)` suffix), and
gives the user an inline modal to prune or repoint when they select
one. Also handles the race condition where an entry was OK at
switcher mount but becomes STALE before bootstrap fires.

Depends on the status-aware registry helper from t826_6 and the
`remove`/`update` verbs from t826_7. Does NOT depend on
prune/doctor — those are CLI flows, parallel to this work.

## Key Files to Modify

- `.aitask-scripts/lib/tui_switcher.py` — `_render_session_row`
  (line ~465), spawn entry points (`_switch_to`,
  `action_shortcut_explore`, `action_shortcut_create`,
  `_ensure_session_live`).
- `.aitask-scripts/lib/stale_entry_modal.py` — **new** modal file.
- `.aitask-scripts/lib/tmux_bootstrap.sh` — extend
  `spawn_session_detached` to fail cleanly with
  `BOOTSTRAP_FAILED:stale_path` when the marker is missing.

## Reference Files for Patterns

- t826_2 plan (`aiplans/archived/p826/p826_2_*.md`) — the
  `_ensure_session_live` helper and the spawn entry-point list.
- Existing `lib/` modal example with self-contained CSS (see memory
  `feedback_modal_self_contained_css`) — modals must carry their
  own `DEFAULT_CSS` because `lib/` modals get pushed by multiple
  Apps that don't share top-level CSS.
- `agent_launch_utils.py::discover_aitasks_sessions` — the refresh
  call after a registry mutation.

## Implementation Plan

1. **Render dimmed STALE rows** (`_render_session_row`, ~line 465):
   when the session is `is_stale=True`, render the segment with
   `Style(dim=True)` and a ` (stale)` suffix. Width-constrained
   case: fall back to `✗` glyph if the row would otherwise wrap
   (codify the breakpoint when implementing — start with a simple
   "always show `(stale)` suffix, accept truncation"). The `▶`
   attached-session marker remains exclusive to the live attached
   session.

2. **Selection handler — `_handle_stale_selection`** (new helper):
   - Called at the top of each spawn entry point (`_switch_to`,
     `action_shortcut_explore`, `action_shortcut_create`) before
     `_ensure_session_live`.
   - Find the selected entry in `self._all_sessions`. If
     `is_stale`, push `StaleEntryModal` (modal) and **return
     True** (caller short-circuits).

3. **`StaleEntryModal`** (`.aitask-scripts/lib/stale_entry_modal.py`):
   - Self-contained `DEFAULT_CSS` (focus highlight, sections,
     button heights — do NOT depend on App-level CSS).
   - Header: `Stale registry entry: <name>` + path line.
   - Options: `[P]rune` / `[R]epoint` / `[C]ancel`.
   - On Prune: `subprocess.run(["./.aitask-scripts/aitask_projects.sh",
     "remove", name, "--force"])`. On non-zero, notify user.
   - On Repoint: push a second small text-input modal asking
     `New path:`. Submit triggers
     `subprocess.run(["./.aitask-scripts/aitask_projects.sh",
     "update", name, new_path])`. Show stderr on failure.
   - On Cancel: just dismiss.
   - **After Prune or Repoint succeeds**: re-run
     `discover_aitasks_sessions(include_registered=True)` and rebuild
     the Session row in the parent App. Easiest: the modal posts a
     `RegistryRefresh` message; the App handler re-runs discovery
     and updates `self._all_sessions`.

4. **Bootstrap helper race-handling**
   (`.aitask-scripts/lib/tmux_bootstrap.sh`):
   - At the top of `spawn_session_detached`, after expanding the
     project_root arg, verify the marker file exists:
     `[[ -f "$project_root/aitasks/metadata/project_config.yaml" ]]`.
     If missing, `echo "BOOTSTRAP_FAILED:stale_path" >&2` and
     exit with code `42` (or another distinct non-zero).
5. **`_ensure_session_live` catches the structured failure**:
   - Already catches non-zero from the subprocess. Add a check:
     if stderr contains `BOOTSTRAP_FAILED:stale_path`, push the
     same `StaleEntryModal` (same modal as step 2/3) for the
     entry. This handles the race where the entry was OK at
     mount but went STALE before user hit Enter.

## Verification Steps

**Unit / regression tests:**
- New `tests/test_stale_entry_modal.py`:
  - Modal renders with self-contained CSS (no App-level fallback
    needed).
  - Prune action calls `aitask_projects.sh remove --force`
    (mock subprocess).
  - Repoint action calls `aitask_projects.sh update`.
  - Cancel dismisses cleanly.
- Extend `tests/test_discover_include_registered.py` to assert
  STALE-but-name-matching-a-live-entry is suppressed (live wins).

**Lint:**
- `shellcheck .aitask-scripts/lib/tmux_bootstrap.sh` — clean.

**Manual verification (extend t826_4 checklist):**
- Add registry entry pointing at a non-existent path. Open
  `ait ide`, press `j`. Verify Session: row shows the entry dimmed
  with `(stale)` suffix.
- Select the STALE entry → press any TUI shortcut → modal opens.
  Prune branch: confirm registry entry gone, switcher row refreshed.
- Repeat with a fresh STALE entry → choose Repoint → enter a real
  project path → confirm registry repointed and row turns into a
  live/inactive entry (no longer stale).
- Race-condition test: open switcher; in another shell, delete the
  marker file of a previously-OK registered project. Without
  closing the switcher, select that project. Confirm bootstrap
  fails cleanly and the same StaleEntryModal pops up.

## Out of Scope

- `prune` / `doctor` CLI flows — children C/D.
- Visual indicators for OK-but-inactive entries — already shipped
  in t826_2 (no marker; activity implied by switch-vs-spawn).
- Auto-clone integration in the modal — clone stays a `doctor
  --clone` flow per brainstorm decision #3.
