---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitormini, tmux, website, scratchpad]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
folded_tasks: [1388]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-20 09:46
updated_at: 2026-10-20 09:49
---

## Goal

While driving a code agent, the user often wants a **scratchpad**: a small notes
editor to paste fragments of the agent's (or its shadow's) output into, so they
do not have to scroll back through either pane later. Add a scratchpad pane that
is:

- **spawned from minimonitor** (a new key next to `e`/`E`), bound to the
  followed code agent;
- placed in a **vertical split of the main code-agent pane** (above or below the
  agent; configurable), not of the shadow pane: the shadow is optional and narrow
  (`tmux.shadow_pane_width`, default 60), while the agent pane always exists;
- a basic editor with copy/paste;
- **persistent per task** when the agent is an aitask agent (`agent-pick-<id>`,
  and also `qa` / `resume` windows): the notes survive killing the agent and
  reappear the next time a scratchpad is opened for the same task;
- **dropped when the task is archived**.

## Exploration findings

### Spawn path — mirror the shadow

- Shadow spawn chain: `minimonitor_app.py` `action_launch_shadow` (~3762) →
  `_spawn_shadow` (~3868, per-app policy adapter) → `monitor_core.spawn_shadow`
  (~3899) → `lib/agent_launch_utils.py` `launch_in_tmux` (~2048, split branch
  ~2109) with a `TmuxLaunchConfig` (~93).
- For the scratchpad: `split_direction="vertical"`, `split_target_pane=<followed
  agent pane>`, `split_size=<rows>`, `split_before=True` when it goes above. Note
  `split_size` is typed `int`; a percentage would need the type fixed, not
  smuggled through `str()`.
- Copy the shadow's create-safety rules (`aidocs/framework/shadow_agent.md`
  "Spawn path and binding", ~215–391): live duplicate lookup that **refuses on an
  unverifiable query** (`find_shadow_pane_status` shape, never the snapshot
  cache), re-check right before launch, `resolve_pane_id_by_pid`, stamp the
  binding option with one retry and **kill the new pane if the stamp fails**, then
  `attach_companion_cleanup_hook`. `companion_pane` is decided per app, never read
  from `TMUX_PANE` inside shared code.
- Minimonitor keys already taken include c d e E f i I j k L m M n p P q s Z
  space tab enter. Choose an unused key and check `lib/keybinding_registry.py` /
  `lib/shortcut_scopes.py` (the shortcut-scope rules in
  `aidocs/framework/tui_conventions.md`). Decide in planning whether the full
  monitor also gets the action; if it does, its adapter passes
  `companion_pane=None`, `select_window=False`, as for the shadow.
- The task id comes from `TaskInfoCache.get_task_id_for_pane` →
  `task_id_from_window_name` (`monitor_core.py` ~4123/4434, regex
  `^agent-(pick|qa|resume)-(\d+(?:_\d+)?)$`).

### The app

- New `ait scratchpad` Textual app (e.g. `.aitask-scripts/scratchpad/scratchpad_app.py`)
  plus launcher `aitask_scratchpad.sh` cloned from `aitask_frozenagent.sh`. Wire
  it into the `./ait` dispatcher (case entry and help text, and add it to the
  update-check skip list next to `minimonitor|frozenagent` because it must start
  fast) and into `lib/tui_registry.py` with `in_switcher=False`. Register its
  module in `KNOWN_BINDING_SOURCES` (`lib/shortcut_scopes.py`).
- Editing uses `TextArea`. Copy the key-handling pattern from
  `monitor_shared.py` `ConcernPayloadEditModal` (~4684): `ctrl+s` and `escape`
  are not in `TextArea.BINDINGS`, so they bubble up. Remember that a focused
  TextArea swallows plain letter keys, so app-level actions need modifier keys.
- Copy goes through `lib/tui_clipboard.py` `copy_to_system_clipboard` (OSC 52
  plus a tmux buffer); calling `app.copy_to_clipboard` directly is banned
  (`tests/test_tui_clipboard_seam.sh`). Paste comes from the terminal's bracketed
  paste. Text from the agent and shadow panes is copied with tmux copy-mode as
  usual.
- Optional, minimal: a "grab the last N lines of the followed agent / shadow"
  action using the existing capture seams (`capture_shadow_text`, `capture-pane`
  through the gateway). Defer it to a follow-up if it grows.
- **Autosave**: the pane is killed by the companion-cleanup hook when the agent
  dies, so the app cannot rely on a clean exit. Save on change (debounced,
  roughly 1s) plus on exit, with atomic writes. The design must state the maximum
  loss window.

### Persistence — model on the shadow rejection store

- Store: gitignored `.aitask-scratchpad/<task_id>/notes.md` (bare id, no `t`;
  env override like `AITASK_SHADOW_DIR`). Copy `aitask_shadow_rejected.sh`'s
  structure: `ait_atomic_render` writes, `lib/registry_lock.sh` mutex,
  `resolve_task_id` validation, and a prune that refuses to delete outside its own
  root and uses `find -type f` + `rmdir`, never `rm -rf`.
- Gitignore: add a `setup_scratchpad_gitignore` next to
  `setup_shadow_store_gitignore` (`aitask_setup.sh` ~2898, registered ~5099–5115)
  and add the line to the repo's own `.gitignore`.
- Archival: add `prune_scratchpad` beside `prune_shadow_rejections`
  (`aitask_archive.sh` ~203). Call it best-effort and honour `--dry-run` at all
  three sites: `archive_parent` ~274, `archive_child` ~516, and the parent
  auto-archive ~569. Decide explicitly whether folded tasks (`handle_folded_tasks`
  ~322) prune too; today shadow data is not pruned there.
- **Non-task agents** (window not matching the regex): take the minimal option.
  Either refuse with a notification, or open an unsaved scratchpad with a visible
  "not saved" marker. Decide in planning. Do **not** add a new persistence key
  (for example the frozen-agent `@aitask_record` id) in this task; that can be a
  follow-up.
- **One scratchpad per task**: two agents on the same task, or spawns from both
  the monitor and the minimonitor, must not create two editors writing the same
  file. Make the duplicate guard keyed on the task (e.g. a
  `@aitask_scratchpad_task` option, or the store lock held by the running app),
  not only on the followed pane.

### Shared code with the frozen-agent work — generalize the helper-pane rule

The rule "is this pane a helper or a real agent" is hard-coded for exactly two
markers (`@aitask_shadow_target`, `@aitask_monitor_kind`) and repeated in:

- `monitor_core._parse_list_panes` + `_LIST_PANES_FORMAT` / `_LIST_PANES_ARITIES`
  (~2527–2680). Arity is a closed set: extend it in the same change or discovery
  silently returns nothing (`tests/test_list_panes_arity_characterization.py`);
- `FROZEN_AWARE_PANE_FORMAT` / `_FROZEN_AWARE_ARITY` / `classify_window_panes` /
  `count_other_real_agents` (~1068–1136), used by `kill_agent_pane_smart` and
  `lib/agent_freeze.py` `_other_real_agents` (~1353);
- `aitask_companion_cleanup.sh`: job 1 kills panes whose `@aitask_shadow_target`
  equals the dying pane; job 2 counts siblings. As written, a scratchpad pane
  would keep the minimonitor alive and would not be killed with its agent;
- `tests/test_cleanup_rule_parity.sh` keeps the bash and Python copies in step.

Instead of adding a third hard-coded marker, introduce **one "bound helper pane"
concept**, for example a shared helper-target option or a small closed set of
target options defined in one place. Shadow and scratchpad then both use it:
excluded from discovery and snapshots, never counted as a real agent, killed when
their target dies, and never killed when a sibling dies while the target lives.
Keep the frozen rules unchanged: a dying `@aitask_frozen` pane makes cleanup
abstain, and a frozen stand-in counts as a real agent. Freezing respawns the
agent in the **same pane id** (`respawn-pane -k`, which fires no `pane-died`), so
a scratchpad binding survives freeze and restore. Verify, and document, what
happens to the scratchpad when a frozen record is **dropped**: `drop_record`
kills the stand-in with `kill-pane`, which may not fire `pane-died`, so bound
helpers may be left behind. The same question applies to shadows today.

Update the `@aitask_*` pane-option inventory in
`aidocs/framework/tmux_gateway.md` (~172) and the companion-pane sections of
`aidocs/framework/tui_conventions.md` (~747–888: add the scratchpad as a
companion case). Respect the raw-tmux gateway rule (`tests/test_no_raw_tmux.sh`);
only `aitask_companion_cleanup.sh` is allowlisted for raw tmux.

### Folded-in bug (t1388)

`_find_sibling_pane_id` rung 2 (the raw `list-panes` fallback behind minimonitor
`tab` / `enter`) takes the first non-self pane with no helper filter. A
scratchpad pane widens this hole: `enter` could type into the scratchpad. Fix it
with the generalized helper rule; see the merged t1388 section below for its
acceptance criteria.

## Website documentation (required)

Write user-facing docs following `aidocs/framework/documentation_conventions.md`
(current state only), and run `python3 check_links.py --build` in `website/`
afterwards:

- New `website/content/docs/tuis/scratchpad/` section (`_index.md` + `how-to.md`,
  plus `reference.md` for keys and config). Cover what the scratchpad is, how to
  open it from minimonitor, placement, editing / copy / paste keys, where notes
  are stored, when they persist (aitask agents only) and when they are dropped
  (archival), autosave behaviour, and the non-task-agent behaviour chosen above.
- `website/content/docs/tuis/minimonitor/how-to.md`: a "How to Open a Scratchpad"
  section next to "How to Launch a Shadow Agent", and the new key in
  minimonitor's key list / `_index.md`.
- `website/content/docs/tuis/_index.md` and `website/content/docs/commands/_index.md`:
  list `ait scratchpad`.
- `website/content/docs/tuis/settings/reference.md` (and the minimonitor
  configuration notes): any new `tmux.scratchpad_*` keys (position, size).
- `website/content/docs/tuis/frozenagent/how-to.md`: a short note that a bound
  scratchpad stays open across freeze and restore.
- If the full monitor gets the action too, also update
  `website/content/docs/tuis/monitor/how-to.md` / `reference.md`.

## Acceptance criteria

- [ ] The minimonitor key opens a scratchpad in a vertical split of the followed
      agent's pane. Position and size are configurable; a second press is refused
      while one is open for the same task.
- [ ] The binding is stamped or the pane is killed. The scratchpad never appears
      in agent lists or snapshots, is closed when its agent dies, and does not keep
      the minimonitor alive on its own.
- [ ] The helper-pane rule is defined once and used by discovery,
      `classify_window_panes`, cleanup and freeze. `test_cleanup_rule_parity.sh`
      covers scratchpad panes; arity tests are updated.
- [ ] Notes persist across killing and re-picking the agent for the same task, and
      are pruned by archival (parent, child, auto-archived parent). Tests cover
      prune safety (refuses outside its root) and `--dry-run`.
- [ ] Autosave survives a hard kill of the pane within the stated loss window
      (tested).
- [ ] Copy uses the `tui_clipboard` route; the seam test still passes.
- [ ] t1388 acceptance criteria met (rung 2 filters helper panes, with a negative
      control).
- [ ] Website docs listed above are written, and `check_links.py --build` passes.
- [ ] aidocs (`tmux_gateway.md` option inventory, `tui_conventions.md` companion
      cases) are updated.

## Merged from t1388: minimonitor sibling fallback shadow filter


## Context

Surfaced while implementing **t1382** (renamed agent windows in the monitor
TUIs). Pre-existing; t1382 narrowed the exposure but did not close it.

`_find_sibling_pane_id` in `.aitask-scripts/monitor/minimonitor_app.py` backs
the minimonitor's `tab` (focus the agent) and `enter` (send Enter to the agent)
keys. It resolves the followed agent in two rungs:

1. The followed-pane snapshot, which excludes shadow and companion panes by
   construction (they never enter `_snapshots`).
2. If that returns `None`, a raw `tmux list-panes` on the own window, taking
   the **first pane that is not this minimonitor's own pane**.

Rung 2 has no shadow filter. Its own docstring names the hazard it is meant to
avoid — "so that a shadow or other helper pane sharing the window is never
mistaken for the agent (t986)" — but that guarantee comes only from rung 1. If
rung 1 misses and a shadow shares the window, `tab` moves focus to the shadow
and, worse, `enter` sends a keystroke into the **shadow's** agent CLI rather
than the followed agent's.

## What t1382 already changed

Rung 1 was switched from `_find_own_agent_snapshot` (AGENT-only) to
`_find_own_window_snapshot` (category-agnostic), so a window renamed off the
`agent-` prefix now resolves at rung 1 instead of falling through. That closed
the common path. Rung 2 is still reachable when no snapshot resolves at all —
e.g. `_own_window_index` is unset (tmux window-index detection lagging the
first refresh), or the snapshot set is empty on an early tick.

## Proposed fix

Filter rung 2 the way discovery does — read `@aitask_shadow_target` alongside
`pane_id` and skip any pane carrying a non-empty value:

```
list-panes -t <own_window_id> -F "#{pane_id}\t#{@aitask_shadow_target}"
```

then apply `is_shadow_target()` (`monitor/monitor_core.py`), which is already
the pure, unit-tested predicate for exactly this field. Consider also skipping
companion panes via the same `_is_companion_process` check the discovery path
uses, so a second minimonitor in the window cannot be selected either.

## Acceptance criteria

- [ ] Rung 2 of `_find_sibling_pane_id` skips panes carrying
      `@aitask_shadow_target`
- [ ] A test drives rung 2 directly (force rung 1 to return `None`) with a
      window containing `[minimonitor, shadow, agent]` and asserts the **agent**
      pane id is returned — with a negative control proving the test fails
      against the unfiltered fallback
- [ ] Decide explicitly whether companion panes are also filtered at rung 2,
      and record the decision either way
- [ ] The docstring's t986 guarantee is true of both rungs, not just rung 1

## Reference

- `.aitask-scripts/monitor/minimonitor_app.py` — `_find_sibling_pane_id`,
  `_find_own_window_snapshot`
- `.aitask-scripts/monitor/monitor_core.py` — `is_shadow_target`,
  `SHADOW_TARGET_OPTION`, `_parse_list_panes`
- `aidocs/framework/shadow_agent.md` — the marker is the authoritative shadow
  classifier
- Archived plan for t1382 (`Upstream defects identified`)

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1388** (`t1388_minimonitor_sibling_fallback_shadow_filter.md`)
