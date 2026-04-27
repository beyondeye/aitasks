---
Task: t683_agent_progress_reporting_in_brainstorm.md
Worktree: (current branch — main)
Branch: main
Base branch: main
---

# Plan: Surface agent progress percentage in brainstorm Status tab

## Context

Agentcrew agents (e.g. `agent-initializer_bootstrap`) already report a progress
percentage via `ait crew status --crew <id> --agent <name> set --progress N`.
The progress is persisted to `{agent_name}_status.yaml` under the `progress`
field (integer 0–100). The agentcrew dashboard renders this as a unicode block
bar, but the brainstorm Status tab currently reads the same YAML file and
discards the `progress` field — agents in flight look static even when they're
emitting checkpoints (the `initializer.md` template emits at 20%, 45%, 70%, …).

This change surfaces the progress in the brainstorm Status tab as an inline
block bar + percent in each agent row, matching the visual style already
established by `agentcrew_dashboard.py`. Indicator is shown only when the
agent has reported `progress > 0`, to avoid clutter for Pending/Waiting agents
that haven't started yet (per user direction).

## Key file modified

- `.aitask-scripts/brainstorm/brainstorm_app.py` — `_mount_agent_row()`
  at lines 2256–2293.

## Reference pattern (reused, not duplicated)

- `.aitask-scripts/agentcrew/agentcrew_dashboard.py:246–248` — the canonical
  10-char block-bar formula:
  ```python
  bar_width = 10
  filled = int(bar_width * progress / 100) if progress else 0
  bar = "█" * filled + "░" * (bar_width - filled)
  ```
  We follow this same width/glyph choice for visual consistency between the
  two TUIs.

## Implementation

In `_mount_agent_row()` (`brainstorm_app.py:2256–2293`):

1. After the existing `status = data.get("status", "Unknown")` block (around
   line 2263), extract progress:
   ```python
   try:
       progress = int(data.get("progress", 0) or 0)
   except (TypeError, ValueError):
       progress = 0
   progress = max(0, min(100, progress))
   ```
   The `int(... or 0)` form handles the `progress: null` YAML case as well
   as missing key; the try/except handles legacy yaml that may carry a
   non-numeric value. Clamp to `[0, 100]` so a stale/buggy writer can't
   produce a bar wider than the row.

2. Build the inline bar string only when there is progress to show:
   ```python
   progress_str = ""
   if progress > 0:
       filled = int(10 * progress / 100)
       bar = "█" * filled + "░" * (10 - filled)
       progress_str = f"  {bar} {progress}%"
   ```

3. Insert `progress_str` into the rendered line between the colored status
   and the heartbeat (currently lines 2288–2291):
   ```python
   line = (
       f"  [{color}]●[/{color}] {name}{type_label}  "
       f"[{color}]{status}[/{color}]{progress_str}{hb_str}{msg_str}"
   )
   ```

That is the entire diff — roughly 8 added lines in one method. No new files,
no helper extraction (the formula is trivial and matches an existing in-tree
pattern). No CSS changes needed (the `█`/`░` glyphs render in the existing
`AgentStatusRow` `Static` widget).

## Why no extracted helper / no unit test

- The bar formula is 4 lines of arithmetic + string concat, identical to
  the one already inlined in `agentcrew_dashboard.py`. Extracting a shared
  helper would require either editing both call sites (scope creep into the
  agentcrew dashboard) or creating a one-caller helper (premature
  abstraction).
- `brainstorm_app.py` is a Textual app and is heavy to import in a unit
  test; existing tests (`tests/test_brainstorm_session.py`) target
  `brainstorm_session.py` only. Adding test infrastructure for a pure
  presentation tweak is disproportionate.
- The change is verifiable by eye in the running TUI (see Verification).

## Verification

End-to-end manual test:

1. Pick an existing brainstorm session that has at least one agent crew
   running (or start a fresh one with the initializer agent).
2. From a separate shell, simulate progress on a known agent in the crew
   (the same call agents make internally):
   ```bash
   ./.aitask-scripts/agentcrew/agentcrew_status.py --crew <crew_id> \
     --agent <agent_name> set --progress 45
   ```
3. Open `ait brainstorm` and switch to the **Status** tab.
4. Confirm the agent row shows `█████░░░░░ 45%` between the status text and
   the `♥` heartbeat marker.
5. Repeat with `--progress 0` and `--progress 100` to confirm:
   - `0` → indicator hidden (only when `progress > 0`).
   - `100` → full bar `██████████ 100%`.
6. Confirm a Pending agent (one that has never been set) shows no bar
   (default `progress: 0` → hidden).

Optional: launch a real `agent-initializer_bootstrap` and watch its
checkpoints (20%, 45%, 70%) advance the bar live as the status-tab refresh
ticks.

## Out of scope

- Refactoring `agentcrew_dashboard.py` to share the bar formula — would be
  desirable but is a separate cleanup task.
- Auto-refreshing the brainstorm status tab faster than its current cadence
  (30s interval is acceptable for the initializer's coarse checkpoints).
- Showing crew-level aggregate progress in the brainstorm session header —
  separate concern from per-agent progress.
- Touching the in-flight uncommitted edits to `brainstorm_session.py` and
  `templates/initializer.md` (those belong to a separate task — leave alone).

## Step 9: Post-Implementation

Standard task-workflow Step 9 cleanup: commit the single-file change with
`feature: <description> (t683)`, then archive via `aitask_archive.sh 683`,
then push.

## Final Implementation Notes

- **Actual work done:** Added 12 lines to `_mount_agent_row()` in
  `.aitask-scripts/brainstorm/brainstorm_app.py` (lines 2268–2277 + the
  `{progress_str}` slot in the f-string at line 2301). The block reads the
  `progress` field from the agent's already-loaded `_status.yaml` data
  dict, defensively coerces to a clamped int 0–100, builds a 10-char
  `█`/`░` bar plus a percent suffix, and renders it only when `progress > 0`.
- **Deviations from plan:** None. Implemented exactly as planned.
- **Issues encountered:** None during implementation. Worth noting for
  future readers: the file had pre-existing uncommitted edits to
  `brainstorm_session.py`, `templates/initializer.md`, and
  `tests/test_brainstorm_session.py` (unrelated work-in-progress on the
  initializer NODE_YAML auto-fill path); those were intentionally left
  untouched and excluded from this task's commit.
- **Key decisions:**
  - Inline the bar formula instead of extracting a shared helper —
    duplicates a 4-line pattern already present at
    `agentcrew_dashboard.py:246–248`, but a one-caller helper was deemed
    premature abstraction given the trivial size and existing duplication.
    A future refactor task could consolidate both call sites into
    `agentcrew_utils.py`.
  - Render only when `progress > 0` (per user direction). This keeps
    Pending/Waiting agent rows uncluttered. The 10-char width matches
    `agentcrew_dashboard` for cross-TUI visual consistency.
  - Defensive int coercion + clamp: `int(... or 0)` handles `progress: null`
    YAML; the `try/except` handles legacy yaml carrying a string. Clamp
    `[0, 100]` shields the row from a buggy writer producing an oversized
    bar.
- **Upstream defects identified:** None.
- **Verification (manual):** Validated via byte-compile (`py_compile` clean).
  Live-TUI verification per the plan's Verification section is the
  user's call — the bar formula is a literal copy of the working
  `agentcrew_dashboard` pattern, so behavioral risk is low.
