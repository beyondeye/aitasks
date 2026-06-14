---
Task: t986_5_minimonitor_trigger_spawn_config.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_1_*.md, aitasks/t986/t986_2_*.md, aitasks/t986/t986_3_*.md, aitasks/t986/t986_4_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: aiwork/t986_5_minimonitor_trigger_spawn_config
Branch: aitask/t986_5_minimonitor_trigger_spawn_config
Base branch: main
---

# Plan: t986_5 — minimonitor trigger + spawn glue + settings/config

## Context

Integration glue: a minimonitor trigger that captures the followed agent's output
and spawns the `shadow` agent in the same tmux window by default, plus the new
config. **Deps:** t986_1 (multi-agent window), t986_4 (the skill).

## Implementation steps

1. **Config:** add `defaults.shadow` to `aitasks/metadata/codeagent_config.json`
   + `seed/`; add the placement toggle (`tmux.shadow_same_window: true`) to
   `settings/settings_app.py:PROJECT_CONFIG_SCHEMA` + `seed/project_config.yaml`.
2. **minimonitor** (`monitor/minimonitor_app.py`): add binding `e`
   (+ `action_launch_shadow`); identify the followed agent via
   `_find_own_agent_snapshot()`; resolve its **pane id** (`snap.pane.pane_id`)
   and its task id (t986_1 pane→task map). Do **not** pre-capture the followed
   agent's output to feed it in — the t986_4 skill captures the pane on demand.
3. **Spawn** via the codeagent-operation pattern (new op `shadow`) +
   `agent_launch_utils.launch_in_tmux()`, window name `agent-shadow-<task_id>`
   (so t986_1 classification recognizes/excludes it), same window by default,
   new window when the toggle says so. The `shadow` op emits
   `/aitask-shadow <followed_pane_id> [<task_id>]` on argv (t986_4 contract);
   the skill calls `aitask_shadow_capture.sh <followed_pane_id>` itself.
4. All tmux via the gateway. Mirror `codebrowser_app.py:action_launch_agent()`
   and the pick spawn flows.

## Verification

- `defaults.shadow` resolves through the agent-string chain (CLI → .local → project → DEFAULT).
- Placement toggle defaults correctly and is overridable via `.local`/profile.
- Pressing the key on a followed agent spawns the shadow in the same window, feeding it the captured output, and the shadow pane is NOT listed among agents.
- `bash tests/test_no_raw_tmux.sh` stays green; `shellcheck` clean.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
