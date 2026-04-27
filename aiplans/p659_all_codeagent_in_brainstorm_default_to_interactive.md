---
Task: t659_all_codeagent_in_brainstorm_default_to_interactive.md
Base branch: main
plan_verified: []
---

# Plan: Default all brainstorm code-agents to `interactive` (t659)

## Context

In the original brainstorm/agentcrew design, all code-agents that run brainstorm
operations were `headless` by default — they ran in the background and the user
saw only their final outputs. Later we added a per-agent `launch_mode` field
(with `interactive` as a valid value) so that some agent types — notably
`detailer` and `initializer` — could run in foreground tmux panes the user can
attach to. We now want **every** brainstorm agent type to default to
`interactive` so users see live output as agents work.

The framework-wide default (`DEFAULT_LAUNCH_MODE = "headless"` in
`.aitask-scripts/lib/launch_modes.py`) is intentionally **not** changed — that
constant is the fallback for non-brainstorm agentcrew flows. Only the
brainstorm per-type defaults flip.

## Files Touched

### 1. `.aitask-scripts/brainstorm/brainstorm_crew.py` (lines 44-51)

Change `BRAINSTORM_AGENT_TYPES` so the four currently-headless types become
`interactive`:

```python
BRAINSTORM_AGENT_TYPES = {
    "explorer":    {"max_parallel": 2, "launch_mode": "interactive"},  # was headless
    "comparator":  {"max_parallel": 1, "launch_mode": "interactive"},  # was headless
    "synthesizer": {"max_parallel": 1, "launch_mode": "interactive"},  # was headless
    "detailer":    {"max_parallel": 1, "launch_mode": "interactive"},  # already
    "patcher":     {"max_parallel": 1, "launch_mode": "interactive"},  # was headless
    "initializer": {"max_parallel": 1, "launch_mode": "interactive"},  # already
}
```

Why this is the only code change needed: every consumer reads from this dict
via `get_agent_types()` and uses the result as the default value:

- `brainstorm_crew.py:121,141` — `register_*` functions take
  `launch_mode: str = DEFAULT_LAUNCH_MODE` but the brainstorm wizard always
  passes the explicit value derived from `get_agent_types()`.
- `brainstorm_app.py:127-133` — `_brainstorm_launch_mode_default(wizard_op)`
  calls `get_agent_types()` and looks up `launch_mode`. Falls back to
  `DEFAULT_LAUNCH_MODE` only if the agent type is missing entirely (won't
  happen).
- `brainstorm_app.py:2954,3033` — wizard `CycleField` initial value and
  summary display both call `_brainstorm_launch_mode_default()`.
- `settings/settings_app.py:1946` — settings TUI's per-agent-type default
  display reads from `get_agent_types()` output.

So this single dict edit propagates everywhere automatically.

### 2. `aitasks/metadata/codeagent_config.json` (line 15)

Remove the project-local override that would otherwise pin explorer to
headless on this repo:

```json
{
  "defaults": {
    "pick": "claudecode/opus4_7_1m",
    ...
    "brainstorm-initializer": "claudecode/sonnet4_6"
  }
}
```

i.e. drop the trailing `"brainstorm-explorer-launch-mode": "headless"` entry
(and the comma before it). The seed config (`seed/codeagent_config.json`) has
no `brainstorm-*-launch-mode` keys, so new projects already get whatever the
framework default is.

## Files NOT Touched (deliberate)

- `.aitask-scripts/lib/launch_modes.py` — `DEFAULT_LAUNCH_MODE` stays
  `"headless"`. It's the fallback for non-brainstorm flows
  (e.g. `agentcrew` runner). Task scope is brainstorm only.
- `tests/test_brainstorm_crew.py` — `TestBrainstormAgentTypes` only asserts
  keys/structure exist; no test pins specific `launch_mode` values per type.
  No update needed.
- `seed/codeagent_config.json` — already has no `brainstorm-*-launch-mode`
  keys; new projects pick up the framework default cleanly.
- `settings/settings_app.py:142-147` description strings (`"Default launch
  mode (headless | interactive) for the explorer..."`) — these list valid
  values, not the default; remain accurate.
- `website/content/` — no docs reference brainstorm launch_mode defaults.

## Verification

1. **Test suite still green:**
   ```bash
   bash tests/test_brainstorm_crew.py
   ```
   Should pass — assertions are structural only.

2. **Lint:**
   ```bash
   shellcheck .aitask-scripts/aitask_*.sh   # no shell scripts changed; sanity only
   python -m py_compile .aitask-scripts/brainstorm/brainstorm_crew.py
   ```

3. **Manual smoke (TUI):**
   - Run `ait brainstorm` (or `ait b`) in a brainstorm session.
   - Start the `explore` op via the wizard.
   - On the Confirm step, the summary line should read
     `Launch mode: interactive (editable below)` and the `CycleField` should
     start at `interactive`.
   - Repeat with `compare`, `hybridize` (synthesizer), `patch` — each should
     default to `interactive`.
   - `detail` and the initializer step (first time entering a session) were
     already `interactive` — verify unchanged.

4. **Settings TUI:**
   - Run `ait settings` → code-agents page.
   - Each `brainstorm-<type> launch_mode` row should show `interactive` as
     the current default (no override active for any type).

## Step 9 (Post-Implementation)

Standard archival — single task, no children, no separate worktree (profile
`fast` → `create_worktree: false`). Plan + code committed in two commits per
the workflow. Run `ait archive 659` via the workflow script in Step 9.

## Final Implementation Notes

- **Actual work done:**
  - `BRAINSTORM_AGENT_TYPES` in `.aitask-scripts/brainstorm/brainstorm_crew.py`
    flipped: `explorer`, `comparator`, `synthesizer`, `patcher` changed from
    `"headless"` → `"interactive"`. `detailer` and `initializer` already
    `interactive`. All six brainstorm agent types now default to `interactive`.
  - Project-local override `brainstorm-explorer-launch-mode: "headless"`
    removed from `aitasks/metadata/codeagent_config.json` so this project also
    picks up the new default.
  - Three test assertions in `tests/test_brainstorm_crew.py` updated:
    `test_launch_mode_override_from_project` (line 436),
    `test_launch_mode_invalid_value_falls_back` (line 454), and
    `test_launch_mode_default_when_config_present` (4 assertions + new
    `initializer` check at line 459-468). All 34 brainstorm_crew tests pass.

- **Deviations from plan:** Plan claimed test suite was structural-only and
  needed no updates. Three tests in `TestGetAgentTypes` actually pin per-type
  `launch_mode` values directly — caught only after running the suite. Tests
  updated alongside the production change in the same commit.

- **Issues encountered:** None blocking. The `test_launch_mode_invalid_value_falls_back`
  test docstring still says "falls back to framework default" but the actual
  fallback target is the value already in `BRAINSTORM_AGENT_TYPES["explorer"]
  ["launch_mode"]` (post-warning, the dict's existing value is preserved).
  The docstring is mildly inaccurate but unchanged — it described the
  pre-existing behavior already, and the behavior itself is unchanged. Left
  the docstring intact to minimize churn.

- **Key decisions:**
  - `DEFAULT_LAUNCH_MODE` in `lib/launch_modes.py` left at `"headless"` —
    only brainstorm per-type defaults flipped. The constant remains the
    fallback for non-brainstorm agentcrew flows.
  - Project-local override removed (per user-confirmed Q1 in plan mode) so
    this repo's brainstorm explorer also runs interactive by default.
  - Two pre-existing unrelated modifications to
    `.aitask-scripts/aitask_brainstorm_delete.sh` and
    `tests/test_brainstorm_cli.sh` were left untouched and not committed in
    this task — they predate this session.
