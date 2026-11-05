---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [sitrep, tui, monitor, tmux]
gates: [risk_evaluated]
anchor: 2175
created_at: 2026-11-05 08:36
updated_at: 2026-11-05 08:36
---

# Sitrep window: add a Python sitrep TUI beside the sitrep agent

Follow-up to t2175 (sitrep steward). Today `ait sitrep` opens ONE code-agent pane
(the `/aitask-sitrep` skill) in its own `agent-sitrep` window, plus a forced
minimonitor companion. The agent does everything, including purely deterministic
work (showing the list, harvest + refresh, dismiss, restore). Reading the list
through an agent is slow and hard to scan.

## Goal

`ait sitrep` opens a window with **three panes**:

1. the **sitrep agent** (code agent, `/aitask-sitrep`), as now but redesigned to
   focus on the genuinely agentic work;
2. a new **sitrep TUI** (Python/Textual) that shows the store in readable form;
3. the **minimonitor companion**, as now.

## Decisions taken during exploration (user-confirmed)

- **Layout:** three panes, agent + sitrep TUI + minimonitor (the minimonitor stays).
- **Moved from the agent into the TUI** (deterministic, no LLM):
  - `>s` show the list: grouped lists (Pick now / Next / Waiting, Recently done
    and Dismissed on demand) with clickable items opening a **details screen**:
    the item fields, outcome with `checked_at` age, the context map, and
    read-only pointer following (`task:` / `plan:` / `file:` read the file,
    `capture:` shows the retained passage lines from `sources/<hex>.txt`,
    `commit:` shows `git show --stat`, `trail:` / `artifact:` via
    `aitask_artifact.sh get` + `aitask_trail_gather.sh drift`). Situation text per
    theme shown too.
  - `>r` harvest + refresh: run `aitask_sitrep_harvest.sh all --root .` then
    `aitask_sitrep_refresh.sh --root .` from a key, report the result lines; plus
    auto-reload when `todo.md` changes (sha256-keyed, off the event loop, the
    `SitrepNowCounter` pattern).
  - `>x` dismiss (with a reason, `--expect-rev`, `STALE:` → re-read, never retry
    blind) and `restore todo|qa` on an unusable store (exit 4), both behind
    confirm dialogs.
  - A **Q&A log browser** (read-only view of `qa.md`, linked to the items each
    entry names).
- **Stays agentic** in the skill: `>t` triage, `>w` situation text, `>q` answers
  from the sources, `>tr` trail refresh offers, `>p` pick advice.
- **TUI → agent:** contextual keys on a selected item (e.g. "triage this",
  "ask about c<N>", "write situation", "refresh this trail") **type a request
  into the sitrep agent pane** through the tmux gateway. Guarded send: only the
  live, unfrozen agent pane stamped for this root (re-check identity at
  dispatch: pane id + pane_pid + server pid, as in the guarded-dispatch rules);
  never another pane. The agent remains advisory-only.
- **User-driven launches from item details** are in scope: e.g. on a task item
  launch `/aitask-pick <id>` in a new agent window, open the task in the board;
  on a push item show the push command. The advisory-only rule binds the sitrep
  agent, not the user acting through the TUI.
- **Dynamic shortcuts:** contextual bindings appear only when an item of the
  matching kind/state is selected (`check_action` + `refresh_bindings`, the board
  / trails pattern; re-check inside the action, a binding gate is not a guard).
  Follow `aidocs/framework/tui_conventions.md` (shortcut scopes, settings
  overrides, markup-safe rendering of store strings).

## Window identity and the one-per-root rule

Current mechanism (`.aitask-scripts/monitor/monitor_core.py`, "Sitrep window"
section; `aidocs/framework/sitrep.md` "The sitrep window"): `spawn_sitrep` runs
lookup → launch → stamp `@aitask_sitrep_root` under a per-server flock;
`match_sitrep_pane` skips frozen/dead/helper panes and prefers the stamp over a
name+cwd fallback.

Required changes:
- The TUI pane gets its **own stamp** (e.g. `@aitask_sitrep_tui_root=<canonical
  root>`) and must be classified as a **helper** by the shared `pane_is_helper` /
  `classify_window_panes` rule — otherwise the monitor lists it as an agent and
  `match_sitrep_pane`'s name+cwd fallback could take it for the agent (it shares
  window and cwd). Read `lib/helper_panes.py` and the helper-filter memories
  (frozen-first, `classify_window_panes`).
- The one-per-root enforcement covers **both roles** under the same lock:
  - nothing alive → spawn the window with agent + TUI + minimonitor;
  - agent alive, TUI missing → add the TUI to the agent's window;
  - TUI alive, agent missing (closed / exited) → respawn the agent beside the TUI
    and stamp it;
  - both alive → focus, as now. Never create a second TUI or a second agent for
    the root, also under concurrent `ait sitrep` calls (extend the live test's
    `AITASK_SITREP_SPAWN_PAUSE_FIFO` race proof to the new roles).
- The TUI offers a **respawn agent** key when its agent is gone; it goes through
  the same `spawn_sitrep` path (no parallel spawn implementation).
- `maybe_spawn_minimonitor` (lib/agent_launch_utils.py) refuses windows that
  already hold a TUI process, and the minimonitor's `_check_auto_close` closes a
  companion once it is alone — both must be taught about the sitrep TUI pane so
  the companion still spawns and does not close itself / misjudge "alone" while
  the TUI is there. Decide and document what happens to the TUI and minimonitor
  when the agent exits (TUI stays and offers respawn).
- Harvest's self-skip (window name `agent-sitrep`, `SITREP_WINDOW_RE`) and the
  `h` harvest-and-close / guarded kill paths must keep treating the TUI pane as a
  non-agent; `kill_agent_run_guarded` stays pane-only.

## Skill redesign

`.claude/skills/aitask-sitrep/SKILL.md.j2`: drop the capabilities that moved to
the TUI from the menu (or reduce them to "use the TUI"), keep the startup
minimal (root check; harvest/refresh may move to the TUI's startup instead —
decide once, not both), keep the writer rules and the advisory guardrail, and
define how the agent recognises a request typed in by the TUI (same `>` codes
carrying item ids, e.g. `>t c12`, `>q c12 ...`). Regenerate goldens and update
`tests/test_sitrep_skill_contract.sh` / `tests/test_skill_render_aitask_sitrep.sh`.
Per CLAUDE.md, Claude Code first; t2199 (codex/opencode port of the sitrep
skill) consumes the slimmed skill — send it a note when the skill changes.

## Touchpoints (non-exhaustive — grep for inventories)

- `.aitask-scripts/monitor/monitor_core.py` (`spawn_sitrep`, `match_sitrep_pane`,
  `find_sitrep_pane_status`, `_sitrep_spawn_lock`, `send_keys`)
- `.aitask-scripts/monitor/sitrep_open.py`, `.aitask-scripts/aitask_sitrep.sh`
  (wire lines: new result lines for added / respawned roles; a `tui` verb or
  launcher for the TUI pane)
- `.aitask-scripts/lib/helper_panes.py` (new stamp / helper marker)
- `.aitask-scripts/lib/agent_launch_utils.py` (`maybe_spawn_minimonitor` gates)
- minimonitor auto-close; `.aitask-scripts/monitor/sitrep_close.py` (`S`, `h`)
- `.aitask-scripts/lib/tui_registry.py` / `lib/tui_switcher.py` (register the
  TUI; switcher `S` keeps working)
- new TUI module + launcher; store reads via `lib/sitrep_todo.py`
  (`load_todo_for_read`, `parse_qa`), writes only via `aitask_sitrep_todo.sh`
  verbs; harvest/refresh via their scripts
- code-agent allow-lists if new helpers are called by the skill
  (`aidocs/framework/aitasks_extension_points.md`)
- docs: `aidocs/framework/sitrep.md`, `website/content/docs/workflows/sitrep.md`,
  `website/content/docs/skills/aitask-sitrep.md` (+ a TUI page if the docs list
  TUIs); run `website/check_links.py --build`

## Acceptance

- `ait sitrep` from a cold start opens agent + sitrep TUI + minimonitor in one
  `agent-sitrep` window; a second call focuses it; concurrent calls leave one of
  each role (live tmux test).
- Closing the agent leaves the TUI, which shows "agent not running" and respawns
  it on a key; `ait sitrep` with only the TUI alive also respawns the agent;
  with only the agent alive it adds the TUI. Never two of a role per root.
- The monitor and minimonitor never list the TUI pane as an agent; the
  name+cwd fallback never matches it; the minimonitor companion still spawns and
  does not auto-close while the TUI is present.
- The TUI lists items by group, opens details, follows each pointer kind
  read-only, browses the Q&A log, runs harvest+refresh, dismisses / restores
  with confirms and `--expect-rev`, and reloads when `todo.md` changes.
- Contextual shortcuts appear only for a selected item they apply to, and every
  action re-checks its precondition.
- Agentic requests from the TUI reach only the bound, live, unfrozen agent pane
  of this root; a respawned/frozen/replaced pane is refused (test with a
  mutant per guard).
- The slimmed skill renders, goldens regenerated, contract tests pass.

This is large; planning should consider splitting into children (identity +
spawn roles; TUI read views; TUI actions + agent dispatch + launches; skill slim;
docs).
