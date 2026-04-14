---
Task: t461_7_brainstorm_launch_mode_settings_tui.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/archived/t461/t461_1_*.md, aitasks/archived/t461/t461_2_*.md, aitasks/archived/t461/t461_3_*.md, aitasks/archived/t461/t461_4_*.md, aitasks/archived/t461/t461_5_*.md, aitasks/archived/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md ... aiplans/archived/p461/p461_6_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_7 — Surface brainstorm `launch_mode` defaults in config + settings TUI

## Context

t461_5 added per-agent-type `launch_mode` defaults to
`BRAINSTORM_AGENT_TYPES` (Python source of truth) and wired
`aitask_crew_init.sh --add-type` to accept an optional third
`:launch_mode` field. `aitask_brainstorm_init.sh` now passes per-type
modes through when seeding `_crew_meta.yaml`, and `brainstorm_app.py`
reads framework defaults for the wizard's initial toggle value.

What's still missing — and what t461_5 explicitly deferred to this
task — is the **user-facing configurability** of `launch_mode`. Today
the value is hardcoded in `BRAINSTORM_AGENT_TYPES`. To change a default
(say, make `explorer` interactive on this user's box) the user has to
edit `brainstorm_crew.py` directly. There is no:

- config-overlay layer for `launch_mode` in `codeagent_config.json`
  (parallel to how `agent_string` is overlaid via `brainstorm-<type>`)
- row in the `ait settings` Agent Defaults tab to view or edit it

This task adds both, mirroring the existing `agent_string` UX exactly
so the visual model stays consistent (project / user layered rows,
`[PROJECT]` / `[USER]` badges, `d` to clear user override).

## Scope and design decisions

- **Config keys**: flat `defaults.brainstorm-<type>-launch-mode` entries
  in `codeagent_config.json`, parallel to the existing
  `defaults.brainstorm-<type>` agent-string keys. Layered project →
  local exactly like agent_string.
- **Validation**: `^(headless|interactive)$`. Invalid values warn to
  stderr (in `get_agent_types()`) and fall back to the framework
  default (no crash).
- **Source of truth bridge**: `_get_brainstorm_launch_mode()` in
  `aitask_brainstorm_init.sh` (added by t461_5) currently reads
  `BRAINSTORM_AGENT_TYPES` directly. It must be rewritten to call
  `get_agent_types()` so user-config overrides flow into freshly seeded
  `_crew_meta.yaml`. The wizard helper `_brainstorm_launch_mode_default()`
  in `brainstorm_app.py` gets the same one-line switch.
- **TUI editor**: a small `LaunchModePickerScreen` ModalScreen with two
  buttons (Headless / Interactive) plus Cancel. Lives in
  `.aitask-scripts/lib/agent_model_picker.py` so it can be imported
  the same way `AgentModelPickerScreen` already is by `settings_app.py`.
  Returns the selected mode via `dismiss({"key": ..., "value": ...})`.
- **Row layout**: for each of the 5 brainstorm agent types the existing
  agent-string row pair (project + user) is followed immediately by a
  `launch_mode` row pair. The new rows use the same `ConfigRow` widget
  with new id prefixes `agent_proj_brainstorm_launch_<type>` /
  `agent_user_brainstorm_launch_<type>`. They display the resolved
  `launch_mode` value; when neither layer is set, the project row
  shows the framework default with a `(framework default)` dim hint.
- **Save flow**: a new `_handle_launch_mode_pick` callback writes
  `defaults.brainstorm-<type>-launch-mode` to either project or local
  `codeagent_config.json` via the existing
  `ConfigManager.save_codeagent()` helper. The `d` / Delete handler is
  reused unchanged — it already removes any user-layer key by row_key.

## Key Files to Modify

1. **`.aitask-scripts/brainstorm/brainstorm_crew.py`** (lines 48-71)
   - Extend the overlay loop in `get_agent_types()` to also read
     `brainstorm-<type>-launch-mode` from `defaults`.
   - Validate with `re.match(r"^(headless|interactive)$", val)`. On
     mismatch, `print(..., file=sys.stderr)` and skip the override.
   - On success, `info["launch_mode"] = val`.

2. **`.aitask-scripts/aitask_brainstorm_init.sh`** (lines 109-118)
   - Replace the body of `_get_brainstorm_launch_mode()` with a Python
     one-liner that calls `get_agent_types()` and returns
     `result[<type>]['launch_mode']`. Fall back to `"headless"` on any
     error (matches existing pattern).

3. **`.aitask-scripts/brainstorm/brainstorm_app.py`** (lines 122-127)
   - Update `_brainstorm_launch_mode_default()` to call
     `get_agent_types()` instead of reading `BRAINSTORM_AGENT_TYPES`
     directly. One-line behavioral change; keeps the
     `_WIZARD_OP_TO_AGENT_TYPE` lookup.

4. **`.aitask-scripts/lib/agent_model_picker.py`** (new class at end)
   - Add `LaunchModePickerScreen(ModalScreen)`. Accepts
     `operation: str` (the config key, e.g.
     `brainstorm-detailer-launch-mode`) and `current: str` (currently
     resolved value: `headless` or `interactive`). Renders a small
     dialog with `Label`, two `Button`s (Headless / Interactive,
     primary variant marks current), and a Cancel button. On button
     press, `dismiss({"key": operation, "value": choice})`. Esc /
     Cancel dismisses with `None`. CSS keeps the dialog narrow
     (`width: 40%`, `height: auto`, `border: thick $accent`) to
     visually distinguish from the larger `AgentModelPickerScreen`.

5. **`.aitask-scripts/settings/settings_app.py`**
   - **Import** (line ~23): add `LaunchModePickerScreen` to the
     `from agent_model_picker import (...)` block. Also import
     `BRAINSTORM_AGENT_TYPES` and `get_agent_types` from
     `brainstorm.brainstorm_crew` lazily (inside the populate function
     to avoid module load time penalty / circular risk).
   - **`_populate_agent_tab()`** (lines 1827-1941):
     - Hoist a list of the 5 brainstorm agent types from
       `BRAINSTORM_AGENT_TYPES.keys()` (sorted for determinism, or
       use the natural dict order which is insertion-stable in Py3.7+).
     - Resolve effective values once via `get_agent_types()` so we
       know each type's effective `launch_mode`.
     - In the `for key in all_keys` loop, after rendering the
       agent-string project + user rows for a `brainstorm-<type>` key,
       also render the launch_mode rows for that type:
       - Project row: `key="launch_mode"`, `row_key=f"brainstorm-{type}-launch-mode"`,
         display = the project-layer value if set, else
         `f"{framework_default}  [dim](framework default)[/dim]"`,
         `id=f"agent_proj_brainstorm_launch_{type}_{rc}"`.
       - User row (subordinate): `row_key` same as above, display =
         user-layer value if set, else `(inherits project)`,
         `id=f"agent_user_brainstorm_launch_{type}_{rc}"`.
     - Skip entire iterations where `key.endswith("-launch-mode")` so
       configured launch-mode keys don't render a duplicate
       agent-string-style row pair.
     - Track which types we've already emitted launch_mode rows for
       (e.g. via a `launch_mode_emitted: set[str]` local set), so a
       brainstorm type that is in `local_defaults` only (not project)
       still gets its launch_mode pair rendered exactly once.
     - **Edge case** — if a brainstorm type has its launch_mode set in
       config but NOT its agent_string (rare, but possible after this
       task), the type wouldn't otherwise appear in `all_keys`. Handle
       by adding a final loop after the main `for key in all_keys`
       loop: for any of the 5 brainstorm types whose launch_mode rows
       have NOT been emitted yet AND whose `brainstorm-<type>-launch-mode`
       key exists in either layer, emit the launch_mode rows under a
       fresh agent-string row pair using `(not set)` for the agent_string.
       (In practice this is unlikely; documented as a safety net.)
   - **`on_key()`** (lines 1587-1660):
     - In the Enter dispatch block for `agent_proj_*` / `agent_user_*`,
       branch on whether `fid` contains `"_brainstorm_launch_"`. If so,
       open `LaunchModePickerScreen` with the resolved current value
       (read from `focused.raw_value`, defaulting to `headless`).
       Pass the callback `self._handle_launch_mode_pick`. Set
       `_editing_layer` exactly as the existing branch does.
     - The existing `d` / Delete handler already keys off
       `agent_user_*` and calls `_clear_user_override(focused.row_key)`,
       which writes through `save_codeagent` against `local_defaults`.
       Because our new user rows have `row_key="brainstorm-<type>-launch-mode"`,
       no change is needed — clearing already removes the right key.
   - **New method `_handle_launch_mode_pick(self, result)`**: mirrors
     `_handle_agent_pick` exactly (lines 1943-1972) — just writes the
     result to the same `defaults` dict in either project or local
     codeagent config and re-runs `_populate_agent_tab()`. Could
     literally call `_handle_agent_pick(result)` since the shape is
     identical, but a separate method makes the `notify()` text more
     specific and keeps the call-site readable.
   - **`OPERATION_DESCRIPTIONS`** (lines 119-131): add 5 new entries
     for `brainstorm-<type>-launch-mode` keys with short descriptions
     ("Default launch mode (headless | interactive) for the brainstorm
     <type> agent type"). These show as the per-row dim caption.

6. **`tests/test_brainstorm_crew.py`** — extend `TestGetAgentTypes`:
   - `test_launch_mode_override_from_project`: set
     `brainstorm-detailer-launch-mode: headless` in project config,
     assert `result["detailer"]["launch_mode"] == "headless"`.
   - `test_launch_mode_local_overrides_project`: project sets headless,
     local sets interactive, assert local wins.
   - `test_launch_mode_invalid_value_falls_back`: set
     `brainstorm-explorer-launch-mode: bogus` in config, assert
     `result["explorer"]["launch_mode"] == "headless"` (framework
     default), and (optionally) capture stderr to verify a warning was
     emitted.
   - `test_launch_mode_default_when_unset`: assert framework defaults
     are returned when no config keys are set (especially `detailer`
     stays `"interactive"`).
   - `test_launch_mode_does_not_clobber_agent_string`: setting only
     `brainstorm-explorer-launch-mode` leaves
     `result["explorer"]["agent_string"]` at the framework default.

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_model_picker.py:225-503` —
  `AgentModelPickerScreen` is the canonical example of a `ModalScreen`
  with `dismiss({"key": ..., "value": ...})`. The new
  `LaunchModePickerScreen` follows the same callback shape so
  `_handle_launch_mode_pick` can mirror `_handle_agent_pick` exactly.
- `.aitask-scripts/settings/settings_app.py:1842-1909` — current
  brainstorm row construction loop (project + user pair, optional
  all-providers hint, op-desc footer). The new launch_mode rows slot
  in right after the existing `if effective_model:` block, scoped to
  the same agent type.
- `.aitask-scripts/settings/settings_app.py:1587-1610` — Enter
  dispatch for `agent_proj_*` / `agent_user_*` — extend with a
  brainstorm-launch-mode branch.
- `.aitask-scripts/settings/settings_app.py:1716-1723` — `d` / Delete
  dispatch for `agent_user_*`. **No change needed**: the handler keys
  off `row_key`, and our new user rows reuse the same `agent_user_`
  prefix and a real `brainstorm-<type>-launch-mode` row_key.
- `.aitask-scripts/settings/settings_app.py:1943-1972` —
  `_handle_agent_pick` — copy/paste/rename for
  `_handle_launch_mode_pick`.
- `.aitask-scripts/brainstorm/brainstorm_crew.py:48-71` — current
  `get_agent_types()` overlay loop is the exact place to add the
  launch_mode overlay step.

## Implementation Plan

### Step 1 — Config overlay (`brainstorm_crew.py`)

In `get_agent_types()`, after the existing
`if config_key in defaults:` block, add a parallel block for
`launch_mode`:

```python
import re  # at top of file if not already present

VALID_LAUNCH_MODES = {"headless", "interactive"}

# inside the for-loop:
launch_key = f"brainstorm-{agent_type}-launch-mode"
if launch_key in defaults:
    val = defaults[launch_key]
    if isinstance(val, str) and val in VALID_LAUNCH_MODES:
        info["launch_mode"] = val
    else:
        print(
            f"warning: invalid {launch_key}={val!r}, "
            f"expected one of {sorted(VALID_LAUNCH_MODES)}; "
            f"falling back to framework default "
            f"({info.get('launch_mode', 'headless')})",
            file=sys.stderr,
        )
```

(Use a set membership check rather than `re.match` — simpler and
equivalent for this two-value vocabulary. Add `import sys` at the top
if not already imported; it is, see line 19.)

### Step 2 — `aitask_brainstorm_init.sh` helper rewrite

Replace lines 109-118 with:

```bash
_get_brainstorm_launch_mode() {
    local agent_type="$1"
    "$PYTHON" -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from pathlib import Path
from brainstorm.brainstorm_crew import get_agent_types
print(get_agent_types(config_root=Path('.')).get('$agent_type', {}).get('launch_mode', 'headless'))
" 2>/dev/null || echo "headless"
}
```

Note: `get_agent_types()` reads `aitasks/metadata/codeagent_config.json`
relative to its `config_root` argument. Passing `Path('.')` (the repo
root, since `ait` cd's there before running scripts) makes the helper
honor user config overrides. The `2>/dev/null || echo "headless"`
fallback preserves the existing safety net for any Python import or
file-read failure.

### Step 3 — `brainstorm_app.py` wizard helper

Replace `_brainstorm_launch_mode_default()` body:

```python
def _brainstorm_launch_mode_default(wizard_op: str) -> str:
    from pathlib import Path
    from brainstorm.brainstorm_crew import get_agent_types
    agent_type = _WIZARD_OP_TO_AGENT_TYPE.get(wizard_op, "")
    return get_agent_types(config_root=Path(".")).get(
        agent_type, {}
    ).get("launch_mode", "headless")
```

The wizard runs from inside the repo root so `Path(".")` is correct.

### Step 4 — `LaunchModePickerScreen` modal

Add to `.aitask-scripts/lib/agent_model_picker.py`:

```python
from textual.containers import Horizontal  # add to imports
from textual.widgets import Button  # add to imports

class LaunchModePickerScreen(ModalScreen):
    """Pick headless/interactive launch mode for a brainstorm agent type."""

    DEFAULT_CSS = """
    #lm_dialog {
        width: 50%;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #lm_buttons { margin-top: 1; height: auto; }
    #lm_buttons Button { margin: 0 1; }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, operation: str, current: str = "headless"):
        super().__init__()
        self.operation = operation
        self.current = current if current in ("headless", "interactive") else "headless"

    def compose(self) -> ComposeResult:
        with Container(id="lm_dialog"):
            yield Label(
                f"Launch mode for: [bold]{self.operation}[/bold]",
                id="lm_title",
            )
            yield Label(
                f"Current: [#FFB86C]{self.current}[/]",
                id="lm_current",
            )
            with Horizontal(id="lm_buttons"):
                yield Button(
                    "Headless",
                    variant=("primary" if self.current == "headless" else "default"),
                    id="lm_headless",
                )
                yield Button(
                    "Interactive",
                    variant=("primary" if self.current == "interactive" else "default"),
                    id="lm_interactive",
                )
                yield Button("Cancel", variant="default", id="lm_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "lm_headless":
            self.dismiss({"key": self.operation, "value": "headless"})
        elif event.button.id == "lm_interactive":
            self.dismiss({"key": self.operation, "value": "interactive"})
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

### Step 5 — `settings_app.py` rendering & dispatch

**5a. Imports** — add `LaunchModePickerScreen` to the
`from agent_model_picker import (...)` block at line 23.

**5b. `_populate_agent_tab()`** — hoist effective launch_mode values
once at the top of the function:

```python
from brainstorm.brainstorm_crew import (
    BRAINSTORM_AGENT_TYPES,
    get_agent_types,
)
effective_types = get_agent_types()
launch_mode_emitted: set[str] = set()
```

Add a local helper inside the function:

```python
def _emit_launch_mode_rows(atype: str):
    """Render project + user launch_mode ConfigRows for one brainstorm type."""
    if atype in launch_mode_emitted:
        return
    launch_mode_emitted.add(atype)
    lm_key = f"brainstorm-{atype}-launch-mode"
    framework_default = BRAINSTORM_AGENT_TYPES.get(atype, {}).get("launch_mode", "headless")
    proj_lm = project_defaults.get(lm_key)
    local_lm = local_defaults.get(lm_key)
    # Project row
    if proj_lm is not None:
        proj_display = str(proj_lm)
        proj_raw = str(proj_lm)
    else:
        proj_display = f"{framework_default}  [dim](framework default)[/dim]"
        proj_raw = framework_default
    container.mount(ConfigRow(
        "launch_mode", proj_display, config_layer="project", row_key=lm_key,
        id=f"agent_proj_brainstorm_launch_{atype}_{rc}",
        raw_value=proj_raw,
    ))
    # User row (subordinate)
    if local_lm is not None:
        user_raw = str(local_lm)
        user_display = user_raw
    else:
        user_raw = "(inherits project)"
        user_display = user_raw
    container.mount(ConfigRow(
        "launch_mode", user_display, config_layer="user", row_key=lm_key,
        id=f"agent_user_brainstorm_launch_{atype}_{rc}",
        subordinate=True,
        raw_value=user_raw,
    ))
```

In the `for key in all_keys` loop:
- Skip launch-mode keys: at the top of the loop body,
  `if key.endswith("-launch-mode"): continue`.
- After mounting the existing project + user agent-string rows and
  the all-providers hint and op-desc, when
  `key.startswith("brainstorm-")`, extract `atype = key.removeprefix("brainstorm-")`
  and call `_emit_launch_mode_rows(atype)`.

After the main loop, add a safety-net pass for orphan launch_mode
keys (a brainstorm type configured for launch_mode but whose
agent_string isn't in either layer). For each `atype` in
`BRAINSTORM_AGENT_TYPES` not yet emitted, check if either
`brainstorm-<atype>-launch-mode` exists in any layer; if so, emit a
synthetic agent-string row pair (with `(not set)` for the project
value) followed by `_emit_launch_mode_rows(atype)`.

**5c. `on_key()` Enter dispatch** — extend the existing
`agent_proj_* | agent_user_*` branch:

```python
if fid.startswith("agent_proj_") or fid.startswith("agent_user_"):
    key = focused.row_key
    self._editing_layer = (
        "project" if fid.startswith("agent_proj_") else "user"
    )
    if "brainstorm_launch_" in fid:
        current_mode = focused.raw_value
        if current_mode == "(inherits project)":
            # Resolve from project layer
            current_mode = self.config_mgr.codeagent_project.get(
                "defaults", {}
            ).get(key, "headless")
        self.push_screen(
            LaunchModePickerScreen(key, current_mode),
            callback=self._handle_launch_mode_pick,
        )
    else:
        # existing AgentModelPickerScreen code unchanged
        ...
    event.prevent_default()
    event.stop()
    return
```

**5d. `_handle_launch_mode_pick`** — mirror `_handle_agent_pick`:

```python
def _handle_launch_mode_pick(self, result):
    if result is None:
        return
    key = result["key"]
    value = result["value"]
    layer = self._editing_layer
    if layer == "user":
        local_data = dict(self.config_mgr.codeagent_local)
        if "defaults" not in local_data:
            local_data["defaults"] = {}
        local_data["defaults"][key] = value
        self.config_mgr.save_codeagent(
            self.config_mgr.codeagent_project, local_data,
        )
    else:
        project_data = dict(self.config_mgr.codeagent_project)
        if "defaults" not in project_data:
            project_data["defaults"] = {}
        project_data["defaults"][key] = value
        local_data = dict(self.config_mgr.codeagent_local)
        if "defaults" in local_data and key in local_data["defaults"]:
            del local_data["defaults"][key]
            if not local_data["defaults"]:
                del local_data["defaults"]
        self.config_mgr.save_codeagent(project_data, local_data)
    self.config_mgr.load_all()
    self._populate_agent_tab()
    self.notify(f"Saved {key} = {value} ({layer})")
```

**5e. `OPERATION_DESCRIPTIONS`** — append:

```python
"brainstorm-explorer-launch-mode":    "Default launch mode (headless | interactive) for the explorer brainstorm agent type",
"brainstorm-comparator-launch-mode":  "Default launch mode (headless | interactive) for the comparator brainstorm agent type",
"brainstorm-synthesizer-launch-mode": "Default launch mode (headless | interactive) for the synthesizer brainstorm agent type",
"brainstorm-detailer-launch-mode":    "Default launch mode (headless | interactive) for the detailer brainstorm agent type",
"brainstorm-patcher-launch-mode":     "Default launch mode (headless | interactive) for the patcher brainstorm agent type",
```

### Step 6 — Tests

Extend `tests/test_brainstorm_crew.py::TestGetAgentTypes` with the 5
test cases listed in the Key Files section above. Run via
`bash tests/test_brainstorm_crew.py` (it's a unittest module — actually
invoked as `python tests/test_brainstorm_crew.py` per existing
patterns).

## Verification

1. **Config overlay (project layer)**:
   ```bash
   # Add to aitasks/metadata/codeagent_config.local.json
   echo '{"defaults": {"brainstorm-explorer-launch-mode": "interactive"}}' > /tmp/cfg.json
   # Apply, then verify
   python3 -c "
   from pathlib import Path
   import sys; sys.path.insert(0, '.aitask-scripts')
   from brainstorm.brainstorm_crew import get_agent_types
   t = get_agent_types(config_root=Path('.'))
   print('explorer:', t['explorer']['launch_mode'])
   print('detailer:', t['detailer']['launch_mode'])
   "
   # Expect: explorer: interactive, detailer: interactive (framework default)
   ```

2. **Crew init reflects override**: with the local override above,
   pick a fresh test task and run `./ait brainstorm init <task_num>`.
   Inspect `.aitask-crews/crew-brainstorm-<task>/_crew_meta.yaml`:
   `agent_types.explorer.launch_mode` should be `interactive`.

3. **Settings TUI**:
   - Run `./ait settings`, navigate to "Default Code Agents for
     Brainstorming" section.
   - Confirm a `launch_mode` row appears under each of the 5
     brainstorm agent types (project + user pair).
   - When neither layer has a value, the project row should display
     the framework default with a `(framework default)` annotation
     (e.g., `interactive  (framework default)` for detailer).
   - Press Enter on the detailer's `launch_mode` project row. Modal
     opens with two buttons. Click Headless. Modal closes; row
     updates to plain `headless`; codeagent_config.json contains
     `brainstorm-detailer-launch-mode: headless`.
   - Press Enter on the explorer's `launch_mode` user row. Modal
     opens. Click Interactive. Row shows `interactive` under the
     `[USER]` badge with `(d to remove)` hint. Press `d`; user
     override clears; row reverts to `(inherits project)`.

4. **Wizard initial value**: open `ait brainstorm` for a task whose
   crew was initialized AFTER an override was set. Run a `detail` op,
   then an `explore` op. The wizard launch-mode toggle initial value
   should reflect the override (not the framework default).

5. **Invalid config value**:
   ```json
   {"defaults": {"brainstorm-detailer-launch-mode": "bogus"}}
   ```
   Run `./ait brainstorm init <task>` — should not crash. stderr
   should contain a warning. `_crew_meta.yaml` should fall back to
   `interactive` (framework default for detailer).

6. **Tests**:
   ```bash
   python3 tests/test_brainstorm_crew.py
   ```
   All existing tests pass + the 5 new ones added in Step 6.

7. **Shellcheck**:
   ```bash
   shellcheck .aitask-scripts/aitask_brainstorm_init.sh
   ```
   Must remain clean.

## Dependencies

- t461_5 (archived): provides `BRAINSTORM_AGENT_TYPES` with
  `launch_mode` per entry, `aitask_crew_init.sh --add-type` third-field
  plumbing, and the `_get_brainstorm_launch_mode()` helper this task
  rewrites.
- t461_3 (archived): provides the wizard launch-mode toggle that
  consumes the framework default from `_brainstorm_launch_mode_default()`.

## Notes for sibling tasks

- The `^(headless|interactive)$` validation is now enforced in FIVE
  places (after this task): `aitask_crew_addwork.sh`,
  `aitask_crew_setmode.sh`, `agentcrew_runner.py`, `aitask_crew_init.sh`,
  and `brainstorm_crew.py::get_agent_types()`. This task adds the
  fifth copy, which makes the duplication actively painful — see the
  mandatory follow-up task below.

## Follow-up task — centralize launch_mode vocabulary (MUST CREATE during Step 9)

**Why this is mandatory, not optional:** the project plans to add
more launch modes beyond `headless` / `interactive` — e.g., launching
a code agent inside a custom sandbox via `openshell`, and potentially
others (`monitored`, etc.). With five scattered copies of the valid
mode list (shell regexes in `aitask_crew_addwork.sh`,
`aitask_crew_setmode.sh`, `aitask_crew_init.sh`; Python literals in
`agentcrew_runner.py` and `brainstorm_crew.py::get_agent_types()`),
adding a new mode would require a synchronized five-file edit with no
compile-time safety net. This task completes that landscape, so
before shipping any new mode we should refactor.

**Create a child task `t461_8_centralize_launch_mode_vocabulary`** via
the Batch Task Creation Procedure during Step 9 of this task (before
running the archive script). Use the following seed description:

- **Goal**: single source of truth for the valid launch_mode set
  plus validation helpers, consumed by all five current call sites.
- **Proposed location**: a small new module
  `.aitask-scripts/lib/launch_modes.py` exporting:
  - `VALID_LAUNCH_MODES: frozenset[str]` (initially
    `{"headless", "interactive"}`)
  - `DEFAULT_LAUNCH_MODE = "headless"`
  - `validate_launch_mode(val: str) -> bool`
  - `normalize_launch_mode(val: str | None, fallback: str = DEFAULT_LAUNCH_MODE) -> str`
    (returns the value if valid, else the fallback; used by callers
    that want to accept `None`/empty)
- **Python call sites to migrate**:
  - `brainstorm/brainstorm_crew.py::get_agent_types()` — replace the
    inline `VALID_LAUNCH_MODES` set introduced by this task.
  - `agentcrew/agentcrew_runner.py` — replace the inline validation
    added by t461_1.
- **Shell call sites**: the shell regexes in
  `aitask_crew_addwork.sh`, `aitask_crew_setmode.sh`, and
  `aitask_crew_init.sh` cannot directly import Python, so the
  follow-up task should generate a shell-compatible regex from the
  Python set via a small helper script (e.g.,
  `.aitask-scripts/lib/launch_modes_sh.sh` that shells into
  `python -c "from launch_modes import VALID_LAUNCH_MODES; print('^(' + '|'.join(sorted(VALID_LAUNCH_MODES)) + ')$')"`
  at script startup and stores the result in a local variable).
  Alternative: a build-time codegen step that writes the regex into
  a generated `.aitask-scripts/lib/launch_modes_regex.sh` file
  committed to the repo. The follow-up task should decide between
  runtime resolution vs. codegen.
- **Extensibility test**: the follow-up must include a test
  demonstrating that adding a new mode (e.g., `sandbox_openshell`) to
  `VALID_LAUNCH_MODES` is picked up by all five call sites without
  any other file edit.
- **Dependencies**: depends on t461_7 (this task) — must land after
  the config-overlay layer exists, so the refactor has a complete
  inventory of call sites to migrate.
- **Issue type**: `refactor`.
- **Priority/effort**: `priority: medium`, `effort: medium`.

This follow-up creation is a **non-negotiable** part of archiving
t461_7 — do not skip it, and do not merge it into the t461_7 diff
(keeping them separate keeps the refactor reviewable).
- The shell-side `_get_brainstorm_launch_mode()` helper now goes
  through Python `get_agent_types()` (not direct dict lookup). This
  means a syntax error in `brainstorm_crew.py` will silently make
  every type fall back to `headless` (because of the `2>/dev/null ||
  echo headless` safety net). If symptoms include "all my interactive
  defaults reverted to headless", check stderr from a manual
  `python3 -c "from brainstorm.brainstorm_crew import get_agent_types"`.
- `brainstorm_app.py::_brainstorm_launch_mode_default()` now also
  goes through `get_agent_types()`, so the wizard initial value picks
  up config overrides without any further plumbing.

## Step 9 (Post-Implementation)

Follow the standard task-workflow Step 9 with one **mandatory extra
step inserted before the archive script runs**:

1. Review → commit code changes (plain `git`) → commit plan file
   (`./ait git`) → ask before merging. Use commit prefix `feature:`
   since `issue_type: feature`.
2. **Create the `t461_8_centralize_launch_mode_vocabulary` child
   task** via the Batch Task Creation Procedure, using the seed
   description in the "Follow-up task" section above. Commit the new
   task file via `./ait git`. Do NOT implement it — just create it.
3. Run the archive script for t461_7.
4. Push.
