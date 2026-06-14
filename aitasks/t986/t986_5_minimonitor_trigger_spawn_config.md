---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t986_4]
issue_type: feature
status: Implementing
labels: [aitask_monitormini, codeagent, ait_settings, tmux]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 16:04
updated_at: 2026-06-14 23:46
---

## Context

Child of t986 (shadow agent). The integration glue: a minimonitor trigger that
captures the followed agent's output and spawns the `shadow` agent in the **same
tmux window** by default, plus the new configuration (default agent+model;
same-window-vs-new-window placement).

**True deps:** t986_1 (multi-agent-per-window substrate — the shadow is a second
agent in the window), t986_4 (the shadow skill it launches). Builds on t986_2/3
transitively via the skill.

## Key Files to Modify / Create

- `.aitask-scripts/monitor/minimonitor_app.py`
  - Add a binding (free key `e`; `x` is the fallback) + `action_launch_shadow`.
    BINDINGS are at ~138-152. The followed agent pane comes from
    `_find_own_agent_snapshot()` (~403-422).
  - Resolve the followed pane's **pane id** (`snap.pane.pane_id`) and its task id
    (via the t986_1 pane→task map). Do **not** pre-capture the pane's output —
    the t986_4 skill captures it on demand (see "Capture contract" below).
  - Spawn the `shadow` agent in the same window by default (config-gated).
    No mode selector — the user states their request to the shadow once running.
- `.aitask-scripts/lib/agent_launch_utils.py`
  - Use `launch_in_tmux()` (555-615) to split into the existing window
    (`agent-shadow-<task_id>` naming so t986_1 classification recognizes it).
- `.aitask-scripts/aitask_codeagent.sh` / `aitask_codeagent_*` — spawn via the
  established codeagent-operation pattern (new op `shadow`).
- `aitasks/metadata/codeagent_config.json` **and** `seed/` equivalent: add
  `defaults.shadow` (e.g. `claudecode/opus4_8`).
- `.aitask-scripts/settings/settings_app.py` (`PROJECT_CONFIG_SCHEMA`) +
  `seed/project_config.yaml`: add the same-window-vs-new-window toggle (e.g.
  `tmux.shadow_same_window: true`).

## Coordination: t986_1 binding contract (LANDED)

t986_1 landed the multi-agent-per-window substrate. The shadow-classification +
lifecycle mechanism it implemented changes what this task must do at spawn time
(see the archived plan `aiplans/archived/p986/p986_1_multi_agent_window_substrate.md`,
"Notes for sibling tasks"):

- **`@aitask_shadow_target` is the authoritative classifier — NOT the window
  name.** A same-window shadow (the default placement) shares the *agent's*
  window name (e.g. `agent-pick-100`), so an `agent-shadow-*` window name only
  exists for the separate-window placement and cannot identify a same-window
  shadow. After spawning the shadow pane, this task MUST run:
  `tmux set-option -p -t <shadow_pane> @aitask_shadow_target <shadowed_agent_pane_id>`
  (via the gateway). Discovery exclusion, `kill_agent_pane_smart` counting, and
  the cleanup auto-kill all key off this option. (Step 4 of the Implementation
  Plan below is updated by this: keep the `agent-shadow-*` window name for the
  separate-window case, but the option is what makes same-window exclusion work.)
- **Auto-kill on agent exit:** ensure the shadowed agent's pane has a
  `pane-died` hook invoking `aitask_companion_cleanup.sh <agent_pane>
  <companion_pane>` so the shadow dies with its agent. Agents launched with a
  minimonitor already have this hook; an agent given only a shadow needs this
  task to attach it.
- Reusable headless API (from `monitor.monitor_core` / `tmux_monitor` shim):
  `SHADOW_TARGET_OPTION`, `is_shadow_target(value)`, `task_id_from_window_name`.

## Reference Files for Patterns

- Existing agent-spawn-from-TUI flows: `codebrowser_app.py:action_launch_agent()`
  (~1367-1418, window `agent-explain-<file>`); `monitor_app.py` pick spawns
  (`agent-pick-<id>`). Mirror the launch + (optional) companion handling.
- Agent+model resolution: `lib/agent_string.sh` (`parse_agent_string`,
  `get_cli_model_id`), `aitask_codeagent.sh` resolution chain (CLI flag →
  `.local.json` → `codeagent_config.json` → `DEFAULT_AGENT_STRING`).
- Config-key precedent: `codeagent_coauthor_domain` / `default_profiles` —
  declare in `PROJECT_CONFIG_SCHEMA`, seed in `project_config.yaml`, read at
  runtime (see t986 parent description, "Config plumbing exists").
- `maybe_spawn_minimonitor()` companion handling (agent_launch_utils.py 634-759).

## Implementation Plan

1. Add the `shadow` codeagent operation default to `codeagent_config.json` + seed.
2. Add the placement toggle to `PROJECT_CONFIG_SCHEMA` + seed `project_config.yaml`.
3. In minimonitor, add the binding + action: identify followed agent, resolve its
   pane id + task id, then spawn the shadow agent (same window by default, new
   window if the toggle says so). All tmux via the gateway.

   **Capture contract (t986_4, LANDED):** the `shadow` op emits
   `/aitask-shadow <followed_pane_id> [<task_id>]` on argv. The t986_4 skill
   captures the followed pane on demand via `aitask_shadow_capture.sh
   <followed_pane_id>` (escape-free stdout) — so this task passes the pane id,
   NOT pre-captured content (argv can't carry a full screen buffer).
4. Ensure the shadow window/pane name (`agent-shadow-*`) is what t986_1's
   classification keys on for helper-pane exclusion.

## Verification Steps

- Config read-path test (`tests/test_<...>.sh` or Python): `defaults.shadow`
  resolves through the agent-string chain; placement toggle defaults correctly
  and is overridable via `.local`/profile.
- `bash tests/test_no_raw_tmux.sh` stays green (spawn via gateway).
- `shellcheck` any new/edited shell.
- Manual (covered by t986_7): press the key in minimonitor on a followed agent →
  shadow spawns in the same window, receives the captured output, and the shadow
  pane does NOT appear in the agent list.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-14T20:46:41Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-14T20:46:42Z status=pass attempt=1 type=machine
