---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t929_3]
issue_type: documentation
status: Implementing
labels: [ait_brainstorm, ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 18:15
updated_at: 2026-06-24 18:28
boardidx: 20
---

## Context

Surfaced while trying to understand how `ait brainstorm` controls the code
agent spawned by each **node operation**, and where the per-operation defaults
(agent binary + model + launch mode) are defined. The mechanism is real but
scattered and undocumented; this task **documents** it on the (not-yet-existing)
brainstorm website docs page and **closes a small settings-TUI gap**.

**Relationship to t929_3 (dependency):** `t929_3` (child of t929, incorporates
folded t776) already plans the general brainstorm TUI docs page
(`website/content/docs/tuis/brainstorm/_index.md`) — launch flow, session
layout, DAG view, operations, module ops. It does **not** cover the
agent-control / model-defaults surface. This task is gated `depends: t929_3` so
its agent-defaults documentation slots into the page t929_3 creates (as a
reference subsection or a sibling `reference.md`), rather than racing to create
the page. Coordinate, don't duplicate.

## How brainstorm agent control works today (verified)

1. **Operation -> agent type** (hardcoded 1:1 map): `_WIZARD_OP_TO_AGENT_TYPE`
   in `.aitask-scripts/brainstorm/brainstorm_app.py:167`. The 8 node ops +
   bootstrap map to 9 agent types:
   `explore->explorer`, `compare->comparator`, `synthesize->synthesizer`,
   `detail->detailer`, `patch->patcher`,
   `module_decompose->module_decomposer`, `module_merge->module_merger`,
   `module_sync->module_syncer`, plus `initializer` (at `init`).

2. **Agent type -> binary + model** (where defaults live):
   `aitasks/metadata/codeagent_config.json`, under `defaults`, keys
   `brainstorm-<agent_type>` -> `"<binary>/<model>"` (e.g.
   `"claudecode/opus4_8"`). Layered resolution:
   hardcoded `BRAINSTORM_AGENT_TYPES` (`brainstorm_crew.py:48`) ->
   project `codeagent_config.json` -> per-user `codeagent_config.local.json`
   (gitignored), merged by `lib/config_utils.py::load_layered_config`.
   Current defaults: comparator/patcher/initializer = `sonnet4_6`; the rest
   (explorer, synthesizer, detailer, module_decomposer/merger/syncer) =
   `opus4_8`.

3. **Launch mode**: hardcoded default `interactive` for all types
   (`BRAINSTORM_AGENT_TYPES`), overridable via config key
   `brainstorm-<agent_type>-launch-mode`, and **user-selectable per operation**
   in the wizard via a `CycleField` (`brainstorm_app.py` ~7820); default loaded
   by `_brainstorm_launch_mode_default()` (~`brainstorm_app.py:179`).

4. **Binding happens at crew-init time**: `aitask_brainstorm_init.sh:107`
   registers each agent type into the crew
   (`ait crew init --add-type "<type>:<agent_string>:<launch_mode>"`). Per-node
   ops then call `ait crew addwork --type <agent_type>` (via
   `brainstorm_crew.py::_run_addwork`, ~line 129). Changing a model therefore
   requires editing `codeagent_config[.local].json` and starting a **new**
   session.

## Settings-TUI editing support — already largely implemented

The settings TUI ("Agent Defaults" tab, `_populate_agent_tab` at
`.aitask-scripts/settings/settings_app.py:1828`) **already** renders every
brainstorm agent type present in `codeagent_config.json` `defaults` as an
editable row — agent-string picker (`AgentModelPickerScreen`) + paired
launch-mode picker (`LaunchModePickerScreen`), with project/user layer
separation and persistence via `ConfigManager.save_codeagent()`
(`settings_app.py:446`, writing project json + `.local.json` override). Because
the tab iterates the **config keys** (union of project + local `defaults`), all
9 types — including the 3 `module_*` types — already appear and are editable.

**The one genuine gap:** `OPERATION_DESCRIPTIONS`
(`settings_app.py:113-132`) only defines helper-text entries for 6 types
(explorer, comparator, synthesizer, detailer, patcher, initializer) and their
`-launch-mode` variants. The 3 `module_*` types
(`brainstorm-module_decomposer`, `brainstorm-module_merger`,
`brainstorm-module_syncer`) and their `-launch-mode` variants have **no
description entries**, so their settings rows render without the descriptive
italic helper text the other 6 get.

## Scope / deliverables

1. **Documentation (primary, depends on t929_3):** Add an agent-control /
   model-defaults section to the brainstorm website docs (the page t929_3
   creates). Cover, all verified against code:
   - the operation -> agent-type map (table of the 9 types);
   - where defaults live (`codeagent_config.json` `defaults`,
     `brainstorm-<type>` and `brainstorm-<type>-launch-mode` keys), the
     layered project/local override model, and that changes take effect on a
     new session;
   - launch-mode default vs per-op wizard override;
   - how to change a model/launch mode via the settings TUI "Agent Defaults"
     tab (project vs user layer).
   Follow `aidocs/framework/documentation_conventions.md` (current-state-only,
   "autonomous" not "auto-execution", genericize agent names, generic
   placeholder project names, no "sister"). Remember `_index.md` website page
   index bullet if a new page is added.
2. **Settings-TUI gap (small enhancement):** Add `OPERATION_DESCRIPTIONS`
   entries for `brainstorm-module_decomposer`, `brainstorm-module_merger`,
   `brainstorm-module_syncer` and their `-launch-mode` variants
   (`settings_app.py:113-132`), matching the wording style of the existing 6.
3. **(Optional "reorganize" consideration, assess cleanliness first):** The
   defaults are split across `BRAINSTORM_AGENT_TYPES` (launch_mode +
   max_parallel), `codeagent_config.json` (agent strings + launch-mode
   overrides), and `OPERATION_DESCRIPTIONS` (settings help text). Evaluate
   whether a single source-of-truth list of brainstorm agent types is worth
   consolidating, or whether the documentation alone resolves the
   "understand it" goal. Do not over-engineer — prefer documenting the current
   layout unless a low-blast-radius consolidation is clearly clean.

## Key files

- `.aitask-scripts/brainstorm/brainstorm_app.py` (`_WIZARD_OP_TO_AGENT_TYPE`:167; launch-mode default:~179; wizard CycleField:~7820)
- `.aitask-scripts/brainstorm/brainstorm_crew.py` (`BRAINSTORM_AGENT_TYPES`:48; `get_agent_types`:60; `_run_addwork`:129)
- `.aitask-scripts/aitask_brainstorm_init.sh` (crew --add-type registration:107)
- `aitasks/metadata/codeagent_config.json` (brainstorm-* defaults:9-17)
- `.aitask-scripts/settings/settings_app.py` (`OPERATION_DESCRIPTIONS`:113-132 — GAP; `_populate_agent_tab`:1828)
- `.aitask-scripts/lib/config_utils.py` (`load_layered_config`, `save_*`)
- NEW/EDIT: `website/content/docs/tuis/brainstorm/` (coordinate with t929_3)

## Cross-agent note

Settings TUI is framework Python (not a skill), so no per-agent skill port is
needed. If the doc page wording references the supported code agent by name,
genericize per documentation conventions.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-24T15:28:47Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-24T15:28:48Z status=pass attempt=1 type=machine
