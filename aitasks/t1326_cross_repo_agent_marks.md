---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor, aitask_monitormini, tui, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-07-29 11:58
updated_at: 2026-07-30 07:56
---

## Problem

When following many agents in `ait minimonitor` / `ait monitor`, the agents are
not equally important — some need to be prioritized. There is no way to flag a
prioritized agent, and no way for that flag to be visible from the monitor TUIs
running in *other* repos, even though the same person is driving all of them.

## Goal

Let the user mark / unmark a codeagent as *prioritized* with a single keyboard
shortcut, render the mark as a single, easily recognizable colored glyph in the
agent list, and persist the marks in a per-user file outside any repo so every
`minimonitor` / `monitor` instance across all repos shows the same marks. Old
entries are purged automatically.

## Requested behaviour

- A single-key shortcut in the agent list toggles the mark on the selected agent
  (both minimonitor and monitor).
- A single-character mark glyph with an easily recognizable colour, rendered in
  the agent row.
- Mark state stored in a per-user, git-ignored file shared across repos, so all
  monitor/minimonitor instances (in any repo) show the same marks.
- The agent's tmux window name is the identifier.
- Purge of stale entries: when the associated agent/minimonitor is gone, and by
  auto-unmarking any agent marked more than ~2 days ago.

## Exploration findings (2026-07-29)

### Current state

- **No mark/priority concept exists** anywhere in `.aitask-scripts/monitor/`, and
  the monitor package has **zero on-disk persistence** today — this feature
  introduces the first persisted state for these TUIs.
- Agent-row rendering seams:
  - minimonitor: `_agent_card_text()` — `.aitask-scripts/monitor/minimonitor_app.py:607`
    (called only from `_rebuild_pane_list`, `minimonitor_app.py:700`)
  - monitor: the row label built at `.aitask-scripts/monitor/monitor_app.py:1273`
  - The docked followed-agent panel (`_own_agent_identity_text`,
    `minimonitor_app.py:655`) is deliberately static — decide explicitly whether
    the followed agent can itself be marked.
- Glyph rendering is already centralized in
  `.aitask-scripts/monitor/monitor_shared.py`: `_state_color()` (line 71),
  `format_state_dot()` (`●`, line 82), `format_shadow_glyph()` (`◆`, line 93),
  `format_compare_mode_glyph()` (line 65). A mark glyph belongs in this module,
  shaped distinctly from `●`/`◆` so the row still reads at a glance.
  Per project convention, marked/unmarked should read as an always-on pair
  (cf. the board's ☑/☐ marks) rather than presence/absence only — confirm during
  planning.

### Identity

- `snap.pane.window_name` (`TmuxPaneInfo.window_name`,
  `.aitask-scripts/monitor/monitor_core.py:532`) is only unique **within one tmux
  session**. Sessions map 1:1 to project roots
  (`.aitask-scripts/lib/tmux_bootstrap.sh`, `AITASKS_PROJECT_<session>`;
  reader at `.aitask-scripts/lib/agent_launch_utils.py:345`).
- `TmuxMonitor.get_session_to_project_mapping()`
  (`.aitask-scripts/monitor/monitor_core.py:1358`) already returns
  `session_name → project_root` for every discovered aitasks session, **at zero
  extra tmux cost** (it piggybacks the sessions cache), and minimonitor already
  calls it every refresh (`minimonitor_app.py:441`).
- ⇒ The cross-repo key should be `(project_root_or_name, window_name)`, not the
  bare window name. Window names like `agent-pick-42` collide trivially across
  repos.

### Store location

- All existing git-ignored state is **repo-local** (`.aitask-history/`,
  `.aitask-gates/`, `.aitask-explain/` — see `.gitignore`), so it cannot be
  shared across repos.
- The only per-user cross-repo file precedent is the project registry
  `~/.config/aitasks/projects.yaml` (`.aitask-scripts/aitask_projects.sh:45`,
  overridable via `AITASKS_PROJECTS_INDEX`). Also relevant: the XDG cache helper
  at `.aitask-scripts/lib/artifact_utils.sh:83`
  (`${XDG_CACHE_HOME:-$HOME/.cache}/ait/…`).
- **Open decision for planning:** the requirement says "git-ignored file", but a
  file inside a repo cannot be cross-repo. Recommended resolution: a per-user
  file (e.g. `~/.config/aitasks/agent_marks.json`, env-overridable for tests) —
  which is inherently outside every repo and therefore never committed. Confirm
  with the user before implementing.

### Concurrency

- Many minimonitor/monitor instances write concurrently (one per followed agent,
  across repos). The only mutex in the framework is the bash mkdir-based
  `.aitask-scripts/lib/registry_lock.sh` (fail-safe, owner-token, steals only a
  provably-dead PID — documented invariants at the top of that file). **No Python
  file locking exists anywhere in the repo.**
- A Python equivalent (same invariants: never proceed unlocked, owner-token
  release, steal only a provably-dead holder) plus atomic
  write-temp-then-rename is required, or the last writer silently clobbers other
  repos' marks — exactly the t1073 failure mode.
- Read path: `_refresh_data` (`minimonitor_app.py:424`) already re-loads
  per-refresh caches (`TaskInfoCache.update_session_mapping`,
  `GateSummaryCache.clear()`), so an mtime-gated re-read of the marks file makes
  a mark set in another repo appear within one refresh tick (~3s) with no extra
  cost when unchanged.

### Purge / expiry

- `discover_aitasks_sessions()` only sees sessions on the **current tmux socket**
  (`AITASKS_TMUX_SOCKET`, `.aitask-scripts/lib/tmux_exec.py:59`). A repo whose
  tmux session simply is not running — or lives on another socket — is
  indistinguishable from a dead agent window.
- ⇒ Liveness-based purge must be **fail-closed**: drop an entry only when its
  session IS currently discoverable but the window is absent. Never purge an
  entry whose session cannot be observed.
- Age-based expiry (default ~2 days since the mark timestamp) is the safe
  general reaper and needs no tmux visibility. Each entry therefore needs a
  `marked_at` timestamp.
- Existing stale-entry UX precedent: `.aitask-scripts/lib/stale_entry_modal.py`
  (prune / repoint for STALE registry entries).
- No `ait` maintenance subcommand exists for TUI-local state — decide between a
  startup sweep, an explicit purge action/binding, and/or a helper script.

### Keybinding

- Bindings auto-register with the `?` shortcut editor via
  `register_app_bindings` (`.aitask-scripts/lib/shortcuts_mixin.py:90`), so a new
  `Binding(...)` is enough — no separate registry edit.
- Taken in minimonitor (`minimonitor_app.py:193`): `?` `tab` `enter` `k` `n` `p`
  `e` `E` `c` `j` `q` `s` `i` `I` `m` `M` `d` `↑` `↓`.
  Taken in monitor (`monitor_app.py:460`): `?` `tab` `j` `q` `s` `i` `r` `f5`
  `z` `t` `k` `n` `R` `enter` `A` `M` `L` `d`.
  **Free in both:** `space`, `x`, `f`, `g`, `b`, `v`, `w`, `y`.
- The toggle acts on the focused list card, so it should be an action guard
  (re-checked inside `action_*`), not only a binding gate.

### Implementation shape (suggested, to be confirmed in planning)

- New `.aitask-scripts/lib/agent_marks.py` — `lib/` is already on `sys.path` for
  the monitor package (`monitor_shared.py:14`), so it is importable by both TUIs
  and unit-testable standalone. Keep it a pure store + policy module (load,
  toggle, expire, liveness-sweep) with no Textual/tmux imports, so the reaper
  policy is testable without a tmux server.
- Render helper in `monitor_shared.py` beside the other glyph formatters.
- One `Binding` + `action_toggle_mark` in each of `minimonitor_app.py` and
  `monitor_app.py`.

## Coordination with t1343

`t1343_parallel_agent_file_conflict_advisory` adds a **second**, independent mark
to the same agent row: a derived, advisory conflict-safety indicator. The two are
deliberately separate features — this task's marks are *user intent*, per-user,
cross-repo, durable; t1343's are *derived*, repo-local, ephemeral — but they
share the same render seam (`_agent_card_text`, `minimonitor_app.py:607`), the
same glyph vocabulary (`monitor_shared.py`), and the same "first persisted state
for the monitor TUIs" plumbing.

Whichever lands first should choose its glyph and its shortcut key so the other
still has a distinguishable one, and should shape the store/render plumbing so
the second mark reuses it rather than forking it. Free-in-both keys are listed
under **Keybinding** above.

## Acceptance criteria

- [ ] A single-key shortcut toggles the prioritized mark on the selected agent in
      both `minimonitor` and `monitor`; the mark survives a TUI restart.
- [ ] The agent row renders a single-character mark glyph in a clearly
      recognizable colour, at render level (assert on `widget.render().plain`).
- [ ] Marks are stored in one per-user file outside any repo, keyed so that
      identically-named windows in different repos never collide.
- [ ] A mark set in one repo's monitor becomes visible in another repo's
      monitor within one refresh cycle.
- [ ] Concurrent writers cannot clobber each other's marks (test with parallel
      writers; asserted against the store API, not the TUI).
- [ ] Entries older than the configured age (default ~2 days) are auto-unmarked.
- [ ] Liveness purge is fail-closed: an entry whose session is not currently
      observable is never dropped (negative-control test).
- [ ] Unit tests for the store/policy module run without tmux; TUI tests follow
      the existing `tests/test_minimonitor_*.py` pattern; multi-session behaviour
      covered alongside `tests/test_multi_session_{monitor,minimonitor}.sh`.
- [ ] Docs updated: `website/content/docs/tuis/minimonitor/how-to.md` and the
      monitor equivalent (new shortcut + mark semantics + purge policy).

## Open questions for planning

1. Confirm the store path (`~/.config/aitasks/agent_marks.json` vs an
   `XDG_STATE_HOME` location) and its env override for tests.
2. Which key? (`x`, `space`, `f`, `g`, `b`, `v`, `w`, `y` are free in both TUIs.)
3. Can the followed agent (docked static panel in minimonitor) be marked, or only
   the general-list agents?
4. Is the mark purely visual, or should it also affect ordering (prioritized
   agents sorted first) and/or the session-bar counters? The request says a glyph
   is enough — confirm no reordering is in scope.
5. Purge trigger: startup sweep, per-refresh, an explicit action, or a helper
   script — and whether the 2-day window is user-configurable.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-30T04:56:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-30T07:27:19Z status=pass attempt=1 type=human
