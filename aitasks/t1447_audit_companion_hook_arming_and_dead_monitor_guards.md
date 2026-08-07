---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [minimonitor, tmux, tui]
gates: [risk_evaluated]
anchor: 1446
created_at: 2026-08-07 10:23
updated_at: 2026-08-07 10:23
---

## Origin

Surfaced while diagnosing t1446 (all minimonitor companions quitting on a
transient tmux failure). These are the findings that were explicitly held out
of t1446's scope: they are real, but none of them is the cause of that
incident, and folding them in would have muddied its acceptance criteria.

Unlike t1446, the user impact here is **not yet demonstrated** — the first job
is to establish it, then clean up what the investigation confirms.

## Finding 1 — companion panes are spawned without a cleanup hook

`maybe_spawn_minimonitor` (`.aitask-scripts/lib/agent_launch_utils.py:1465-1603`)
spawns the companion pane and returns its id, but never arms the
`pane-died` cleanup hook on the agent pane. Of its ~13 call sites, exactly one
arms a hook afterwards: the git-TUI path in
`.aitask-scripts/lib/tui_switcher.py:1367-1390`. Every board call site
(`board/aitask_board.py:8799, 8971, 9148, 9555, 9840, 9983, 9987`), the
codebrowser call site (`codebrowser/codebrowser_app.py:1421`), and the other
four `tui_switcher` call sites (~1119, ~1184, ~1215, ~1278) arm nothing.

Verified live: `aitasks:8` `%384` had a companion (its scope shows a 6h16m
lifetime ending in the t1446 event) but carries no `pane-died` hook at all.

Investigate before changing anything:

- What does the missing hook actually cost? When the agent pane dies with no
  hook and no `remain-on-exit`, tmux closes it and the orphaned companion
  should auto-close on its own (`_check_auto_close`) — i.e. the hook may be
  redundant for the *despawn* job while still mattering for the *shadow-kill*
  job in `aitask_companion_cleanup.sh`.
- Is the auto-close path the intended cleanup mechanism for these call sites?
  If so, say so in a comment at the spawn site, because the asymmetry with
  `tui_switcher` currently reads as an oversight.
- Decide one way: either every companion spawn arms the hook (best done inside
  `maybe_spawn_minimonitor` so no call site can forget — see
  [[feedback_default_new_param_in_helper_not_callers]]), or none do and the
  git-TUI path is brought in line.

## Finding 2 — the git-TUI path arms a bare `pane-died` hook

`.aitask-scripts/lib/tui_switcher.py:1386-1390` writes
`set-hook -p -t <pane> pane-died <cmd>` with no index. A bare `pane-died`
writes index `[0]` and therefore **replaces** whatever sits there — precisely
the hazard that `attach_shadow_cleanup_hook`
(`.aitask-scripts/lib/agent_launch_utils.py:1390-1445`) was written to avoid,
with its `_pane_died_hook_indices` scan, its `has_cleanup` short-circuit, and
its "append at the first free index" behaviour.

Observed consequence: `aitasks:7`'s agent `%375` had a companion minimonitor,
yet its only `pane-died` hook now points at the shadow `%386` spawned much
later — the recorded companion was swapped.

Route this site through `attach_shadow_cleanup_hook` (or a shared sibling of
it) rather than duplicating the raw `set-hook` call. Two writers of the same
tmux hook with different safety rules is the underlying defect; one owner is
the fix — see [[feedback_reuse_canonical_seam_not_parallel_reimpl]].

## Finding 3 — two single-instance guards that can never fire

Both of these test `pane_current_command` for the strings `minimonitor` /
`monitor_app`:

- `.aitask-scripts/aitask_minimonitor.sh:37` — "A monitor is already running in
  this window. Exiting."
- `.aitask-scripts/lib/agent_launch_utils.py:1569` — the overcrowding /
  duplicate-companion check inside `maybe_spawn_minimonitor`.

A live minimonitor pane reports `pane_current_command` as **`python`** (the
pane runs `ait minimonitor`, which `exec`s the venv interpreter), so neither
condition can ever be true. Confirmed against the running panes: every
minimonitor pane in every session reports `python`.

Both guards exist to prevent a second monitor in the same window; both are
dead. Replace the command-string test with something that can actually
identify a monitor pane — candidates to evaluate: matching
`#{pane_start_command}` (which does contain `ait minimonitor`), or a pane
user-option marker set at spawn time (the approach already used for shadows via
`@aitask_shadow_target`), which is robust to interpreter and launcher changes.
Prefer the marker if it holds up — see
[[feedback_prefer_structural_fix_over_fragile_invariant]].

## Acceptance criteria

- [ ] Each of the three findings is either fixed or closed with a written
      rationale for why the current behaviour is correct. "Investigated, no
      change needed" is an acceptable outcome **only** with that rationale
      recorded in the task/plan.
- [ ] Hook arming has exactly one owner. No call site can spawn a companion and
      silently skip the hook, and no code path writes an unindexed `pane-died`
      hook that can clobber another writer's entry.
- [ ] The single-instance guards either detect a real monitor pane (with a test
      that drives the positive case) or are deleted outright — a guard that
      cannot fire must not be left in place looking like protection. See
      [[feedback_narrow_except_gates_never_fail_open]] for the same principle
      applied to exception guards.
- [ ] Tests cover the guard's positive case at minimum; for the hook work,
      assert the resulting `show-hooks -p` output rather than only that the
      helper was called.

## Notes

- Do **not** touch `_check_auto_close` or `discover_window_panes` here — that
  is t1446's scope, and the two tasks will otherwise collide in
  `minimonitor_app.py` / `monitor_core.py`.
- `aidocs/framework/tmux_gateway.md` governs every raw-`tmux` call site touched
  by this work; `tests/test_no_raw_tmux.sh` enforces it.
