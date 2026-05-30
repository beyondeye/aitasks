---
priority: medium
effort: high
depends: [t832_3, t832_4]
issue_type: feature
status: Implementing
labels: [cross_repo, aitask_board, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 18:29
updated_at: 2026-05-30 23:26
---

## Context

Part of t832 brainstorm decomposition. Surfaces `xdeps` / `xdeprepo`
in `aitask_board.py` task cards and the blocked-status display, and
parses the `aitasks#N_M` notation regex from
`aidocs/cross_repo_references.md` in task body text so cross-repo
references are navigable from the board.

## Three concerns bundled (TUI changes are coupled)

### 1. Card display
When a task has `xdeps:` + `xdeprepo:`, render the cross-repo dependency
line with the `<repo>#<id>` form (e.g., `xdeps: aitasks_mobile#42,
aitasks_mobile#16_2`). Visually distinguish from local `depends:`.

### 2. Blocked-status surfacing
If t832_4's blocking-logic flags a task as blocked by a cross-repo dep,
render a distinct "blocked by cross-repo" indicator (separate from
"blocked by local"). Show the cross-repo target's status inline if cheap
to fetch (`aitask_query_files.sh task-status --project <name> <id>` from
t832_1), with a graceful fallback to "UNREACHABLE" matching t832_4's
error path.

### 3. Cross-repo notation parser + navigation
When the user activates an `aitasks#N_M` reference inside a task body
or plan body shown in the board, resolve the project name via
`aitask_project_resolve.sh` and open the cross-repo task content
read-only (no edit, no lock acquisition). Closing the popup returns
to the current board session. This deliberately stops short of
*switching* the board to the cross-repo project (see Out of scope).

## Key Files to Modify

- `.aitask-scripts/board/aitask_board.py` — task-card rendering, blocked-
  status display, new key handler for activating cross-repo notation
  references, popup widget for read-only cross-repo task display.
- `.aitask-scripts/board/task_yaml.py` — already round-trips unknown keys
  via `serialize_frontmatter` (per t832_3's audit). `xdeps` / `xdeprepo`
  will be preserved by t832_3's parser changes; no new YAML work needed,
  but verify the round-trip at task-card-load time exposes the fields.
- **New file:** `.aitask-scripts/lib/cross_repo_notation.py` — minimal
  shared parser exposing `parse(text) → list[(project, task_id)]` using
  the `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$` regex. Shared so future
  TUI / script consumers (e.g., aitask_explain_context.py, monitor TUI)
  don't reinvent it.

## Reference Files for Patterns

- `aidocs/cross_repo_references.md` — canonical notation regex.
- `.aitask-scripts/aitask_project_resolve.sh` — name → root resolution.
- `.aitask-scripts/aitask_query_files.sh task-status --project <name> <id>`
  (from t832_1) — cross-repo status probe for the blocked-status display.
- `.aitask-scripts/aitask_ls.sh:calculate_blocked_status` (after t832_4
  lands) — emits `blocking_info` with `<repo>#<id>` or
  `<repo>#<id> (UNREACHABLE)` for the board to pattern-match.
- `aidocs/tui_conventions.md` — Textual TUI conventions.

## Implementation Plan

1. Author `lib/cross_repo_notation.py` with the regex parser. Unit tests.
2. In `task_yaml.py` (or wherever board reads frontmatter), expose
   `xdeps` and `xdeprepo` to the card-rendering layer.
3. Extend the task-card widget to render the cross-repo dep line with
   the distinct visual marker. Test by loading a fake task with these
   fields and visually inspecting.
4. Extend blocked-status display to recognize `<repo>#<id>` patterns in
   `blocking_info` and render the "blocked by cross-repo" indicator with
   the cross-repo target's live status (via `task-status` probe).
5. Scan task body / plan body text on display for `aitasks#N_M`
   references. Render them as activatable links (key handler).
6. On activation: resolve the project, read the cross-repo task file
   read-only (no lock), open a popup widget displaying its content. ESC
   closes the popup.

## Verification Steps

- Unit test: `tests/test_cross_repo_notation.sh` (parser unit tests covering
  valid forms, the `t` prefix tolerance, the `N_M` child form, rejection
  of malformed inputs).
- Manual run (no automated TUI test — interactive):
  - Set up two fake projects with cross-repo tasks.
  - Launch `ait board`.
  - Verify cross-repo dep line renders distinctly.
  - Verify blocked-by-cross-repo indicator appears for tasks with unmet xdeps.
  - Verify UNREACHABLE fallback when the registry points at a stale path.
  - Verify activating an `aitasks#N_M` reference opens the popup.
- `./.aitask-scripts/aitask_skill_verify.sh` passes (no skill changes,
  but TUI launch via skills shouldn't regress).

## Notes for sibling tasks

- `lib/cross_repo_notation.py` will likely be reused by `ait monitor`
  cross-repo surfacing (deferred follow-up) and by `aitask_explain_context.sh`
  (t832_2 may consume it for the `aitasks#path` notation; coordinate at
  impl time to avoid two parsers).
- Manual-verification aggregate sibling: this task is the only TUI-
  touching child in t832, so the parent's child-task checkpoint should
  offer a manual-verification sibling scoped to `[832_8]`.

## Out of scope

- **`ait monitor` cross-repo surfacing** — separate follow-up after this
  lands and its UX patterns settle.
- **Switching the board to a cross-repo project session** (full TUI
  re-mount with a different `TASK_DIR`) — UX is unsettled; the read-only
  popup is the minimum viable navigation.
- **In-board editing of cross-repo tasks** — cross-repo updates go
  through `aitask_update.sh --project <name>` (t832_7) at the script
  level; the TUI does not call it directly until UX is settled.

See parent plan §t832_8 for the full design context.
