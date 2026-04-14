---
priority: low
effort: medium
depends: [t461_6]
issue_type: feature
status: Implementing
labels: [agentcrew, brainstorming, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 11:04
updated_at: 2026-04-14 11:48
---

## Context

Follow-up to t461_5. That task added per-agent-type `launch_mode`
defaults in `BRAINSTORM_AGENT_TYPES` (Python source of truth), extended
`aitask_crew_init.sh --add-type` to accept an optional third field
`:launch_mode`, and wired `aitask_brainstorm_init.sh` to pass per-type
modes through when initializing a crew. What's still missing is the
user-facing configurability: `launch_mode` is currently not overridable
via `codeagent_config.json` nor surfaced in the `ait settings` TUI, so
users have to edit `brainstorm_crew.py` directly to change the default
for a type.

This task adds that UX by teaching the config layer and settings TUI
about per-type `launch_mode`, parallel to how `agent_string` is already
handled.

## Key Files to Modify

1. `.aitask-scripts/brainstorm/brainstorm_crew.py` — in
   `get_agent_types()` (lines 48-71), overlay `launch_mode` from
   `codeagent_config.json` in the same loop that currently overlays
   `agent_string`. New config keys: `defaults.brainstorm-<type>-launch-mode`
   (e.g., `brainstorm-detailer-launch-mode: interactive`).
2. `.aitask-scripts/aitask_brainstorm_init.sh` — replace the direct
   `BRAINSTORM_AGENT_TYPES` lookup in `_get_brainstorm_launch_mode()`
   (introduced by t461_5) with a call to `get_agent_types()` so user
   config overrides propagate into the freshly-seeded `_crew_meta.yaml`
   at crew init time. The helper should now return the EFFECTIVE
   launch_mode (framework default overlaid by config), not just the
   hardcoded dict value.
3. `.aitask-scripts/settings/settings_app.py` — add a second
   ConfigRow per brainstorm agent type showing `launch_mode`.
   Pattern: see the existing `brainstorm-*` agent-string ConfigRows
   around lines 1850-1892 (project row = GREEN `[PROJECT]`, optional
   user row = ORANGE `[USER]` with `(d to remove)` hint). The new
   rows should live in the same "Default Code Agents for
   Brainstorming" section, immediately below the corresponding
   agent-string row for each type. Edit action opens a small modal
   (headless/interactive) — either a new small modal class or reuse
   CycleField from t461_3's wizard toggle.
4. `aitasks/metadata/codeagent_config.json` (if brainstorm defaults
   are set there) — optionally add example `brainstorm-<type>-launch-mode`
   entries as the project-level defaults (e.g.,
   `brainstorm-detailer-launch-mode: interactive`). This is optional
   since the framework default already lives in `BRAINSTORM_AGENT_TYPES`.

## Reference Files for Patterns

- `.aitask-scripts/settings/settings_app.py:1850-1892` — existing
  `brainstorm-*` agent-string ConfigRow pair (project + user),
  including the section header and `AgentModelPickerScreen` open
  logic at line 1594-1605. Use this as the template for the
  `launch_mode` rows and editing modal.
- `.aitask-scripts/settings/agent_model_picker.py` — existing modal
  for agent/model selection. A new `LaunchModePickerScreen` (or a
  simpler `CycleField`-based widget) should follow the same
  ModalScreen pattern.
- `.aitask-scripts/brainstorm/brainstorm_crew.py:48-71` —
  `get_agent_types()` already reads `brainstorm-<type>` from config
  via `load_layered_config` and overlays `agent_string`. Add a
  second overlay step for `launch_mode` from
  `brainstorm-<type>-launch-mode`. Validate that the config value
  matches `^(headless|interactive)$` — fall back to framework
  default on invalid values (warn to stderr, don't crash).
- `.aitask-scripts/brainstorm/brainstorm_app.py` — the wizard's
  `_brainstorm_launch_mode_default()` helper currently reads
  `BRAINSTORM_AGENT_TYPES` directly. After this task, it should
  call `get_agent_types()` instead so wizard initial values also
  reflect user config overrides. (Minor one-line change.)

## Implementation Plan

1. **Overlay `launch_mode` in `get_agent_types()`**: extend the
   existing overlay loop to also read `brainstorm-<type>-launch-mode`
   from config, validate against `^(headless|interactive)$`, and
   update `info["launch_mode"]` when present.

2. **Update `_get_brainstorm_launch_mode()`** in
   `aitask_brainstorm_init.sh` to call `get_agent_types()` instead of
   reading `BRAINSTORM_AGENT_TYPES` directly. Keep the fallback to
   `"headless"` on error. This ensures the seeded `_crew_meta.yaml`
   at `ait brainstorm init` time picks up user config overrides.

3. **Update `_brainstorm_launch_mode_default()`** in
   `brainstorm_app.py` to also call `get_agent_types()` so the
   wizard's initial toggle value respects user overrides.

4. **Build a `LaunchModePickerScreen`** (ModalScreen) in
   `.aitask-scripts/settings/settings_app.py` or a new file. It
   shows the current mode and two buttons (Headless / Interactive)
   plus Cancel. Callback returns the selected mode.

5. **Add ConfigRows for `launch_mode`** in the brainstorm section.
   For each of the 5 agent types:
   - Insert a second ConfigRow immediately after the existing
     agent-string row: id = `brainstorm_launch_<type>_proj` /
     `brainstorm_launch_<type>_user`.
   - Label: `  launch_mode` (indented under the type's agent-string
     row so it visually groups).
   - Value: the resolved project/user value, displayed with the
     same `[PROJECT]`/`[USER]` badges.
   - Enter opens `LaunchModePickerScreen`; callback writes to
     `codeagent_config.local.json` (for user rows) or
     `codeagent_config.json` (for project rows) under
     `defaults.brainstorm-<type>-launch-mode`.

6. **Document the new config keys**: add a small note in
   `aidocs/` or the relevant brainstorm docs page (or mention in
   the settings TUI help text) that `brainstorm-<type>-launch-mode`
   can be set alongside `brainstorm-<type>` to override the
   framework default.

## Verification Steps

1. Set `brainstorm-explorer-launch-mode: interactive` in
   `aitasks/metadata/codeagent_config.local.json`. Run
   `ait brainstorm init <test_task>`. Confirm the fresh
   `_crew_meta.yaml` has `agent_types.explorer.launch_mode: interactive`.
2. Open `ait settings`. Navigate to "Default Code Agents for
   Brainstorming" section. Confirm a `launch_mode` row appears
   under each agent type, showing current values with
   `[PROJECT]`/`[USER]` badges.
3. Press Enter on the detailer `launch_mode` row. Modal opens.
   Select Headless. Confirm the row updates and the underlying
   config file has the new value.
4. Open a brainstorm session for the same task, run a `detail` op,
   leave the wizard toggle at its default. Confirm the toggle
   initial value now reflects the override (Headless).
5. `shellcheck` clean on `aitask_brainstorm_init.sh`. Existing
   brainstorm tests still pass.

## Dependencies

- t461_5 (archived): provides the `BRAINSTORM_AGENT_TYPES` dict
  with `launch_mode` per entry and the
  `aitask_crew_init.sh --add-type` third-field plumbing. Without
  it, there is no field to overlay or display.
