---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [tui_switcher, codeagent, agent_chooser]
created_at: 2026-06-24 23:39
updated_at: 2026-06-24 23:39
---

## Goal

Add a command to the TUI switcher (the `j` overlay) that launches a **bare code
agent with no task** — i.e. opens the shared agent command dialog
(`AgentCommandScreen`) with **empty / no-task parameters** so the user can pick
agent / model / tmux target and then start an interactive agent that runs *no*
`/aitask-*` slash command (just `claude --model <id>`, or the equivalent for
codex / opencode).

## Background — what already exists

The two building blocks are already present and connect cleanly:

1. **The dialog** — `AgentCommandScreen`
   (`.aitask-scripts/lib/agent_command_screen.py:132`). Nothing in it requires a
   task: the `operation`, `skill_name`, and `operation_args` constructor params
   are all optional. With `operation="raw"` and an empty prompt, the resolved
   command is the bare agent binary. The **syncer** already drives the dialog
   this way (`syncer_app.py:496`, `operation="raw"`), and the **board** shows the
   `push_screen(AgentCommandScreen(...))` + result-callback pattern
   (`aitask_board.py:5247`, `:5458`).
   - Command resolution: `resolve_dry_run_command(project_root, "raw")` (no args)
     → `aitask_codeagent.sh --dry-run invoke raw` → for the `raw` op with empty
     args, `build_invoke_command` emits just `binary model_flag cli_id` with no
     prompt (`aitask_codeagent.sh:443-444`) = a bare interactive agent.
   - Agent string: `resolve_agent_string(project_root, "raw")`.

2. **The switcher** — `.aitask-scripts/lib/tui_switcher.py` already has
   agent-launch quick-jump shortcuts: `action_shortcut_explore` (`x`, line 1033)
   and `action_shortcut_create` (`n`, line 1056).

## Key design decision (resolve in planning)

The existing switcher agent-launch shortcuts (`explore`, `create`) **do not use
the dialog** — they fire-and-forget via
`self._spawn_in_session(window, "ait codeagent invoke explore")`. The request
here is explicitly to **use the agent command dialog** with empty params, which
is a **new interaction pattern for the switcher**: it must
`self.app.push_screen(AgentCommandScreen(...))` from the overlay and handle the
result callback (`launch_in_tmux(screen.full_command, result)` +
`maybe_spawn_minimonitor(...)` on a new window), the way the board does — the
switcher currently never opens a modal on top of its own overlay.

Decide in planning:
- **Dialog-based** (requested): lets the user pick agent / model / tmux target.
  More work — modal-from-overlay, callback wiring, dismiss/coordination with the
  switcher's own ModalScreen.
- vs. **direct-spawn** (matches existing explore/create, simpler, but no
  agent/model selection). The user asked for the dialog approach; flag the
  trade-off but default to dialog unless planning surfaces a blocker.

## Implementation sketch (dialog approach)

- New `action_shortcut_<name>()` in `tui_switcher.py` that builds
  `full_cmd = resolve_dry_run_command(project_root, "raw")`,
  `agent_string = resolve_agent_string(project_root, "raw")`, an empty
  `prompt_str`, a `default_window_name` like `agent-raw-{n}` (auto-numbered
  against `self._running_names`, mirroring `agent-explore-{n}` at line 1040), and
  pushes `AgentCommandScreen(..., operation="raw", operation_args=[],
  default_agent_string=agent_string)`. The result callback launches in tmux and
  spawns the minimonitor companion on a new window. Respect
  `_handle_stale_selection()` / `_ensure_session_live()` / `_teleport_if_cross()`
  like the existing actions.
  - Note the `agent-` window prefix (`_AGENT_PREFIXES`, line 175) so the new
    window is classified under the "Code Agents" group.

- **Two parallel registration sites must stay in sync** (these are a
  derive-don't-duplicate hazard):
  - `_QUICK_JUMP_BINDINGS` (line 364) — add a `Binding(<key>, "shortcut_<name>", ...)`.
  - `_HINT_ITEMS` (line 217) — add the matching bottom-hint entry.
  - (`_TUI_SHORTCUTS` at line 190 is for *TUI* switches only; `explore`/`create`
    are NOT in it, so a new agent-launch action follows the same exclusion.)
  - Consider whether the new key should be user-rebindable via the
    `shared.tui_switcher` shortcut scope (explore/create are registered through
    `register_app_bindings`).

- **Key choice:** a,b,c,g,m,n,r,s,t,x,y are taken (plus structural j / escape /
  enter / arrows / `[` / `]`). Free mnemonic candidates: `e`, `d`, `o`, `z`.
  Decide and document.

## Cleanliness / polish (optional, decide in planning)

With an empty `prompt_str` the dialog still renders its "Prompt only:" label and
"Copy Prompt" button (`agent_command_screen.py:440-444`) with empty content —
vestigial for a no-task launch. Consider suppressing that row when `prompt_str`
is empty. This touches a shared dialog used by board / monitor / syncer /
codebrowser, so guard the change to the empty-prompt case only and verify it
doesn't regress the existing callers.

## Acceptance criteria

- Pressing the new switcher key opens `AgentCommandScreen` with no task / empty
  prompt and a resolved bare-agent command for the active code agent.
- Choosing a tmux launch starts an interactive agent running no slash command,
  in a new `agent-*` window, with the minimonitor companion spawned as for other
  agent launches.
- The new key appears in the switcher's bottom hint row and behaves under
  stale-selection / inactive-session / cross-session teleport like the existing
  `explore`/`create` shortcuts.
- Tests cover the new action (command resolution + the push_screen/callback
  wiring), consistent with how `tui_switcher` / `agent_command_screen` are
  currently tested.

## Cross-agent note

This is a TUI (`tui_switcher.py`) change — pure Python, not a skill surface — so
no Claude/Codex/OpenCode skill port is implied.
