---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [trails, board, cross_repo]
gates: [risk_evaluated]
created_at: 2026-10-12 17:19
updated_at: 2026-10-12 17:19
---

## Goal

Implementation trails should show cross-repo dependencies. When a task in a
trail is blocked by a task in another registered repo (`xdeprepo` + `xdeps`),
the trail view must say so, and the user should be able to jump from the
`ait trails` TUI of one repo to the **linked** trail(s) in the other repo's
`ait trails` TUI.

Some limits are accepted (see Out of scope). The aim is to know when a trail
task is blocked by another repo, and to move between the related trails.

## Current state (exploration findings)

### 1. Cross-repo blockers are invisible in By-Trail / `ait trails`

- The status logic already exists:
  `TaskManager.cross_repo_dep_display()` and `get_xdep_status()`
  (`.aitask-scripts/board/board_task_manager.py`, ~line 936). It returns per-ref
  display strings (`backend#42 [Implementing]`, `backend#42 (UNREACHABLE)`)
  and an `xdep_blocked` flag, which fails closed (unreachable means blocked).
- The board's normal `TaskCard` (`board_widgets.py`, ~lines 400-448) shows it
  as a `↗ …` line and the `🌐 blocked (cross-repo)` chip.
- `TrailTaskCard` (`board/board_trail_view.py`, ~line 345) **overrides
  `compose` completely** and shows only title, trail badges, status badge,
  drift and ops hint. So a trail member blocked by another repo looks
  unblocked.
- `_rerender_trail` (`board/board_trail_screen.py`, ~line 669) deliberately
  does NOT clear `xdep_status_cache`. Its docstring states the precondition:
  "A future trail card that reads is_modified / lock_map must either refresh
  that state itself or stop using this helper". This applies to xdep state
  too. Refreshing the xdep status must not block the UI thread (the reason
  that helper avoids `refresh_board()`, t1268).
- Members that themselves live in another repo (`proj#id` entries) are shown
  as `TrailGhostCard` with `ghost_kind="cross_repo"` and `landed=False` always
  (`build_trail_lanes`, ~line 204). They never show their live status, even
  when Done in their own repo. Consider showing their live status through the
  same xdep status lookup.

### 2. The trail document has no cross-repo edges

- `lib/trail_gather.py` reads only `depends`, `verifies` and
  `risk_mitigation_tasks` (`_canonical_refs`). `xdeps`/`xdeprepo` are never
  read, so:
  - an `xdeps` edge can't be recorded as a `hard_depends` relation (the
    `lib/trail_schema.py` validator requires `hard_depends` to mirror a
    recorded `depends` edge);
  - `xdeps` doesn't constrain wave ordering in `/aitask-trail` (the skill
    uses the INPUT depends csv as hard facts);
  - editing `xdeps` never makes a trail STALE.
- Decide in planning whether the live board-side display (finding 1) is
  enough, or whether `xdeps` should also enter the snapshot records (digest
  and drift contract: adding a field to `task_record` changes every stored
  digest, so this needs a migration story) and the skill's ordering rules.

### 3. No navigation to a linked trail in the other repo

Existing building blocks:
- The TUI switcher (`lib/tui_switcher.py`) already lists the aitasks tmux
  sessions of different projects (`discover_aitasks_sessions`) and jumps
  between them with `switch-client`. `trails` is shortcut `i` in the
  switcher.
- `ait trails` (`board/trails_app.py`) keeps one in-memory tab per opened
  trail (`TrailSession`, `TrailTabStrip`).

Missing:
- **A way to open a given trail at launch.** `trails_app.py main()` accepts
  only `--tasks-dir`. A `--trail <handle>` (open/focus that trail's tab) is
  needed for a jump target, and for a running instance in the other session
  some way to hand it the handle (or launch a new window).
- **Trail discovery in another repo.** `lib/trail_discovery.discover_trails()`
  is bound to cwd and TASK_DIR (artifact CLI paths are cwd-relative). Finding
  the other repo's trails means running discovery from that repo's root
  (resolve the root via `aitask_project_resolve.sh`, never a sibling path).
- **A "linked trail" relation.** Proposed definition: trail B (repo Y) is
  linked to trail A (repo X) when some member of A has `xdeprepo: Y` and an
  `xdeps` entry that is a member of B. The reverse direction (B's members
  `xdeps` into X) should be found too, so the jump works both ways. Planning
  should decide whether `proj#id` members also count as links.
- **A key or action** on a focused trail card (or the trail summary) that
  lists the linked trails in the other repo and jumps there: switch to the
  other project's tmux session and open or focus that trail in its
  `ait trails`. Shortcut scope rules: `ait trails` shares
  `TRAIL_BINDINGS` with the board (scope `"board"`). A new binding must be
  declared on both surfaces (hidden and non-dispatching where unsupported).
  See `aidocs/framework/tui_conventions.md`.

## Suggested shape

This is probably big enough to split into children at planning time, e.g.:
1. Cross-repo blocked indicator (and live status for cross-repo ghost
   members) on By-Trail / `ait trails` cards, with a non-blocking xdep
   status refresh.
2. `ait trails --trail <handle>` launch/focus support.
3. Cross-repo linked-trail discovery helper, run in the other repo's root
   through the registry.
4. Jump action: pick a linked trail and switch to the other project's
   session / `ait trails`.
5. (Optional, decide in planning) `xdeps` in gatherer records and in the
   skill's wave-ordering rules.

## Out of scope / accepted limitations

- Topic and multi-topic trails rooted in another repo
  (`cross_repo_topic_unsupported` stays).
- A trail stays an artifact owned by a local task. Showing a repo-X trail
  inside repo Y's TUI is not required; the jump goes to the other repo's own
  trails.

## Side finding (separate defect, not part of this task)

`trail_gather.py` `cmd_snapshot` makes the single scope id the owner, even when
that id is in another repo (`/aitask-trail proj#42` gives `OWNER:proj#42`).
The skill's write step then strips it to the bare id and runs
`aitask_artifact.sh create 42 …`, which puts the trail on **local** t42 (the
wrong task) or fails. This should be tracked as its own bug task. Two
possible fixes: reject a foreign owner and require a local `--owner`, or have
the skill ask for one.

## Docs

User-facing docs must describe the new indicator and the jump
(`website/content/docs/workflows/cross_project_dependencies.md` and the
trails TUI page). Run `check_links.py` after editing.
