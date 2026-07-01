---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [statistics, tui]
gates: [risk_evaluated]
created_at: 2026-07-01 09:24
updated_at: 2026-07-01 09:24
---

## Origin

Spawned from t1098 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_launch_utils.py:555` — `_read_default_session` falls
  back to the literal session name `"aitasks"` for any repo without a
  `tmux.default_session`, so multiple such registered repos collide on one key.
  The stats TUI *and* the shared ring/group helpers
  (`cross_group_ring` / `cross_group_step` / `advance_group_selection`, in the
  same module, also used by `tui_switcher`) key session identity on
  `sess.session`. When two entries share `session="aitasks"`, the stats TUI's
  `_session_cache` bleeds one repo's stats onto another, `_SessionItem`
  session_keys duplicate, and left/right/group cycling becomes ambiguous.

## Diagnostic context

Surfaced while implementing t1098 (opting the stats TUI into
`discover_aitasks_sessions(include_registered=True)`). Registered repos that set
a distinct `default_session` (the case for the current user's repos) are
unaffected, which is why t1098 could ship safely. The collision is a
**pre-existing** latent issue in the shared discovery/selection layer — it
already applies to `tui_switcher`, which also calls
`discover_aitasks_sessions(include_registered=True)` — and is therefore not
specific to the stats TUI. It was scoped out of t1098 deliberately to keep that
fix small.

## Suggested fix

Give each discovered repo a **unique identity key** independent of the tmux
session name — e.g. key the stats TUI's `selected_session` / `_session_cache`
and the shared ring/group helpers on `project_root` (truly unique) or on a
synthesized stable key — while still displaying `session` for the tmux label.
Because the ring/group helpers are shared with `tui_switcher`, evaluate the
blast radius on both consumers before changing their keying, and add a
regression that constructs ≥2 registered repos both resolving to
`session="aitasks"` and asserts they remain distinguishable (distinct cache
entries, distinct list rows, unambiguous cycling).

## Acceptance Criteria

- Two+ registered repos with no `tmux.default_session` (both → `"aitasks"`) are
  shown as distinct rows in the `ait stats` TUI, each with its own stats (no
  cache bleed).
- Session cycling (left/right and `[`/`]` group nav) reaches each such repo
  unambiguously.
- `tui_switcher` behavior for the same collision is verified unchanged or
  fixed in step (whichever the chosen keying implies).
- A regression test reproduces the collision and asserts distinguishability.
