---
Task: t461_9_unified_launch_mode_consumers.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_runner_interactive_launch.md, aiplans/archived/p461/p461_2_crew_setmode_cli.md, aiplans/archived/p461/p461_3_brainstorm_wizard_toggle.md, aiplans/archived/p461/p461_4_brainstorm_status_edit.md, aiplans/archived/p461/p461_5_per_agent_type_defaults.md, aiplans/archived/p461/p461_6_ansi_log_viewer.md, aiplans/archived/p461/p461_7_brainstorm_launch_mode_settings_tui.md, aiplans/archived/p461/p461_8_centralize_launch_mode_vocabulary.md
Base branch: main
plan_verified: []
---

# t461_9 — Unified Launch Mode Consumers (with openshell split)

## Context

Sibling task t461_8 centralized the `launch_mode` vocabulary into
`.aitask-scripts/lib/launch_modes.py`
(`VALID_LAUNCH_MODES = frozenset({"headless", "interactive", "openshell"})`,
`DEFAULT_LAUNCH_MODE`, `validate_launch_mode`, `normalize_launch_mode`,
`launch_modes_pipe`) and added a shell bridge
`.aitask-scripts/lib/launch_modes_sh.sh`. All validators and most
call sites already consume from these sources.

This task finishes the single-source-of-truth migration so every
consumer handles an arbitrary mode list driven by
`VALID_LAUNCH_MODES` alone, **and** splits the `openshell` canary
into two modes (`openshell_headless` and `openshell_interactive`)
per the user's recent realization that "openshell" really covers two
orthogonal interaction styles, not one.

Real launch semantics for both openshell variants remain stubbed;
implementing them is a follow-up task created during Step 9. Task
t456 (per-agent permissions) stays separate — it's an orthogonal
concern with a different config surface.

## Design decisions (confirmed with user)

1. **Expand scope to split openshell now.** `VALID_LAUNCH_MODES`
   becomes `{"headless", "interactive", "openshell_headless",
   "openshell_interactive"}`. Both openshell variants are registered
   in the LAUNCHERS registry with LaunchError stubs — real
   implementation is a tracked follow-up.
2. **Help-text heredocs stay static** (no shell bridge interpolation),
   but get updated to enumerate all four modes so they aren't stale
   on landing.
3. **No permissions work** (t456 remains independent).

## Files to modify

| File | Change |
|------|--------|
| `.aitask-scripts/lib/launch_modes.py` | Replace `openshell` with two variants; update module docstring |
| `.aitask-scripts/lib/launch_modes_sh.sh` | Update header comments to reflect new vocabulary (no code change) |
| `tests/test_launch_modes.py` | Update seed/validate assertions to new vocabulary; update extensibility sandbox baseline |
| `.aitask-scripts/agentcrew/agentcrew_runner.py` | Dispatch registry refactor + two openshell stubs |
| `.aitask-scripts/lib/agent_model_picker.py` | `LaunchModePickerScreen`: dynamic button loop + generic dispatch |
| `.aitask-scripts/brainstorm/brainstorm_app.py` | `AgentModeEditModal`: dynamic button loop + generic dispatch |
| `.aitask-scripts/brainstorm/brainstorm_crew.py` | 6 signature defaults + 1 fallback → `DEFAULT_LAUNCH_MODE`; 5 docstrings |
| `.aitask-scripts/aitask_crew_addwork.sh` | Help heredoc: enumerate all four modes |
| `.aitask-scripts/aitask_crew_init.sh` | Help heredoc: enumerate all four modes |
| `.aitask-scripts/aitask_crew_setmode.sh` | Help heredoc: enumerate all four modes |
| `aitasks/` (new follow-up task) | Track real `openshell_headless` + `openshell_interactive` launch semantics |

`BRAINSTORM_AGENT_TYPES` dict in `brainstorm_crew.py` is **not**
touched — per-type defaults are business logic and explicitly
exempt from the acceptance grep.

---

## Phase 1 — Vocabulary split (source of truth)

### 1.1 `.aitask-scripts/lib/launch_modes.py`

Replace the `VALID_LAUNCH_MODES` definition:

```python
VALID_LAUNCH_MODES: frozenset[str] = frozenset(
    {"headless", "interactive", "openshell_headless", "openshell_interactive"}
)
```

Update the module docstring note to reflect the split:

```python
"""Single source of truth for agent launch modes.

All call sites that validate, default, or enumerate launch modes must
import from this module. The shell bridge (``launch_modes_sh.sh``)
shells out here at runtime so shell consumers stay in sync
automatically.

Modes:
    headless              — subprocess, no UI, output piped to log file.
    interactive           — tmux window or terminal fallback, full Claude
                            Code UI. Integrates with ait monitor.
    openshell_headless    — (not yet implemented) sandboxed shell subprocess
                            running the agent non-interactively. Stubbed
                            in the runner with LaunchError; picker modals
                            and validators accept it.
    openshell_interactive — (not yet implemented) sandboxed shell subprocess
                            attached to a terminal for user inspection.
                            Stubbed; same acceptance as above.

The two openshell variants are placeholders that exercise the
single-source-of-truth migration and surface missed call sites at
runtime. Real launch semantics are tracked in a follow-up task.
"""
```

No changes to `DEFAULT_LAUNCH_MODE`, the validator functions, or
`launch_modes_pipe()`. Default stays `"headless"`.

### 1.2 `.aitask-scripts/lib/launch_modes_sh.sh`

The file has no code references to specific mode names — only in
comments (lines 5–6):

```bash
#   LAUNCH_MODES_PIPE   - e.g. "headless|interactive|openshell" (sorted)
#   LAUNCH_MODES_REGEX  - e.g. "^(headless|interactive|openshell)$"
```

Update the example strings to match the new vocabulary:

```bash
#   LAUNCH_MODES_PIPE   - e.g. "headless|interactive|openshell_headless|openshell_interactive" (sorted)
#   LAUNCH_MODES_REGEX  - e.g. "^(headless|interactive|openshell_headless|openshell_interactive)$"
```

### 1.3 `tests/test_launch_modes.py`

Four assertions hardcode the old three-mode set. Update:

- **Line 27** (test_seed_vocabulary): replace
  `self.assertIn("openshell", launch_modes.VALID_LAUNCH_MODES)` with:
  ```python
  self.assertIn("openshell_headless", launch_modes.VALID_LAUNCH_MODES)
  self.assertIn("openshell_interactive", launch_modes.VALID_LAUNCH_MODES)
  ```

- **Line 32** (test_validate): replace
  `self.assertTrue(launch_modes.validate_launch_mode("openshell"))` with:
  ```python
  self.assertTrue(launch_modes.validate_launch_mode("openshell_headless"))
  self.assertTrue(launch_modes.validate_launch_mode("openshell_interactive"))
  ```

- **Lines 91–101** (test_new_mode_propagates_to_shell_bridge
  sandbox): update the inline module definition so the baseline
  `VALID_LAUNCH_MODES` matches the new canonical set:
  ```python
  (sandbox / "launch_modes.py").write_text(textwrap.dedent("""
      VALID_LAUNCH_MODES = frozenset(
          {"headless", "interactive", "openshell_headless",
           "openshell_interactive", "futuremode"}
      )
      DEFAULT_LAUNCH_MODE = "headless"
      ...
  """))
  ```

- **Line 113**: `self.assertIn("openshell", result.stdout)` →
  ```python
  self.assertIn("openshell_headless", result.stdout)
  self.assertIn("openshell_interactive", result.stdout)
  ```

No other test file assertions reference the literal `openshell`
(confirmed by grep).

---

## Phase 2 — agentcrew_runner.py dispatch registry

**File:** `.aitask-scripts/agentcrew/agentcrew_runner.py`

Current state (lines 491–596): nested `try:` with
`if launch_mode == "headless" / elif "interactive" / else: WARNING`.
Each branch independently builds `cmd`, launches a process, then
sets `status_file.pid` + `alive_path.last_heartbeat` + prints
`LAUNCHED:` in batch mode.

### 2.1 Add imports and module-level types

Near existing imports:

```python
from dataclasses import dataclass
from typing import Callable

# VALID_LAUNCH_MODES is needed alongside the already-imported DEFAULT_LAUNCH_MODE
from launch_modes import DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES
```

Just before `launch_agent`:

```python
class LaunchError(Exception):
    """Raised by launcher functions when a launch precondition fails
    (e.g. no tmux/terminal available, openshell not implemented).
    Caller translates this into the standard Error-state bookkeeping."""


@dataclass
class LaunchContext:
    """Bundle of everything a launcher function needs. Built in
    launch_agent after all shared setup."""
    name: str
    agent_string: str
    short_prompt: str
    prompt_rel: str
    atype: str
    log_path: str
    alive_path: str
    status_file: str
    ait_cmd: str
    worktree: str
    batch: bool
```

### 2.2 Extract `_launch_headless`

Move lines 492–513 into a module-level function that returns the
`Popen`. The `_log_handles[name] = log_fh` assignment stays inside
this launcher since the log handle is headless-specific:

```python
def _launch_headless(ctx: LaunchContext) -> subprocess.Popen:
    log_fh = open(ctx.log_path, "a")
    cmd = [ctx.ait_cmd, "codeagent", "--agent-string", ctx.agent_string,
           "invoke", "raw", "-p", ctx.short_prompt]
    log_fh.write(f"=== Agent: {ctx.name} | Type: {ctx.atype} | "
                 f"String: {ctx.agent_string} ===\n")
    log_fh.write(f"=== Started: {now_utc()} ===\n")
    log_fh.write(f"=== Prompt file: {ctx.prompt_rel} ===\n")
    log_fh.write(f"=== Command: {' '.join(cmd)} ===\n")
    log_fh.write(f"{'=' * 60}\n")
    log_fh.flush()
    proc = subprocess.Popen(cmd, cwd=_repo_root or ".",
                            stdout=log_fh, stderr=log_fh)
    _log_handles[ctx.name] = log_fh
    return proc
```

### 2.3 Extract `_launch_interactive`

Move lines 515–591 into a module-level function. The one behavioral
change: the inner `if not launched: ... return` block — which
currently does error bookkeeping inline — becomes
`raise LaunchError(err_msg)`. The caller's existing error-state
path handles it identically.

```python
def _launch_interactive(ctx: LaunchContext) -> subprocess.Popen:
    cmd = [ctx.ait_cmd, "codeagent", "--agent-string", ctx.agent_string,
           "invoke", "raw", ctx.short_prompt]
    cmd_str = " ".join(shlex.quote(c) for c in cmd)

    launched = False
    proc: subprocess.Popen | None = None

    if is_tmux_available():
        tmux_defaults = load_tmux_defaults(Path(_repo_root or "."))
        session = tmux_defaults["default_session"]
        window_name = f"agent-{ctx.name}"
        new_session = session not in get_tmux_sessions()
        config = TmuxLaunchConfig(
            session=session, window=window_name,
            new_session=new_session, new_window=True,
        )
        proc, err = launch_in_tmux(cmd_str, config)
        if err is None:
            launched = True
            windows = get_tmux_windows(session)
            win_idx = next(
                (idx for idx, n in windows if n == window_name),
                None,
            )
            if win_idx is not None:
                pp = subprocess.run(
                    ["tmux", "pipe-pane", "-O", "-o",
                     "-t", f"{session}:{win_idx}.0",
                     f"cat >> {shlex.quote(ctx.log_path)}"],
                    capture_output=True, text=True, check=False,
                )
                if pp.returncode != 0:
                    log(f"WARN: pipe-pane failed for {ctx.name}: "
                        f"{pp.stderr.strip()}", ctx.batch)
            maybe_spawn_minimonitor(session, window_name)
        else:
            log(f"WARN: tmux launch failed for {ctx.name}: {err}",
                ctx.batch)

    if not launched:
        term = find_terminal()
        if term is not None:
            log(f"WARN: falling back to standalone terminal ({term}) "
                f"for {ctx.name} — no monitor integration", ctx.batch)
            proc = subprocess.Popen(
                [term, "-e", "sh", "-c", cmd_str],
                cwd=_repo_root or ".",
            )
            launched = True

    if not launched or proc is None:
        raise LaunchError(
            "Interactive launch requires tmux or a terminal emulator"
        )

    return proc
```

### 2.4 Add openshell stubs

Both variants stub with LaunchError. The follow-up task will
replace these with real implementations.

```python
def _launch_openshell_headless(ctx: LaunchContext) -> subprocess.Popen:
    raise LaunchError(
        "openshell_headless launch mode is not yet implemented — "
        "tracked in follow-up task"
    )


def _launch_openshell_interactive(ctx: LaunchContext) -> subprocess.Popen:
    raise LaunchError(
        "openshell_interactive launch mode is not yet implemented — "
        "tracked in follow-up task"
    )
```

### 2.5 Define the registry

```python
LAUNCHERS: dict[str, Callable[[LaunchContext], subprocess.Popen]] = {
    "headless": _launch_headless,
    "interactive": _launch_interactive,
    "openshell_headless": _launch_openshell_headless,
    "openshell_interactive": _launch_openshell_interactive,
}

# Invariant: every mode in VALID_LAUNCH_MODES must be registered here.
# If a new mode is added to lib/launch_modes.py, the import-time
# assertion below catches a missed registration early.
assert set(LAUNCHERS.keys()) == set(VALID_LAUNCH_MODES), (
    "LAUNCHERS registry out of sync with VALID_LAUNCH_MODES: "
    f"missing={set(VALID_LAUNCH_MODES) - set(LAUNCHERS.keys())}, "
    f"extra={set(LAUNCHERS.keys()) - set(VALID_LAUNCH_MODES)}"
)
```

### 2.6 Refactor `launch_agent` dispatch body

Replace the old `if / elif / else` block with:

```python
ctx = LaunchContext(
    name=name,
    agent_string=agent_string,
    short_prompt=short_prompt,
    prompt_rel=prompt_rel,
    atype=atype,
    log_path=log_path,
    alive_path=alive_path,
    status_file=status_file,
    ait_cmd=ait_cmd,
    worktree=worktree,
    batch=batch,
)

launcher = LAUNCHERS.get(launch_mode)
if launcher is None:
    log(f"WARNING: Unknown launch_mode '{launch_mode}' for agent "
        f"'{name}', skipping", batch)
    return

try:
    proc = launcher(ctx)
except LaunchError as e:
    log(f"ERROR: {e} (agent {name})", batch)
    update_yaml_field(status_file, "status", "Error")
    update_yaml_field(status_file, "error_message", str(e))
    update_yaml_field(status_file, "completed_at", now_utc())
    agents[name]["status"] = "Error"
    return
except OSError as e:
    log(f"ERROR: Failed to launch agent '{name}': {e}", batch)
    update_yaml_field(status_file, "status", "Error")
    update_yaml_field(status_file, "error_message", f"Launch failed: {e}")
    update_yaml_field(status_file, "completed_at", now_utc())
    agents[name]["status"] = "Error"
    return

# Shared post-launch bookkeeping (hoisted out of both branches).
update_yaml_field(status_file, "pid", proc.pid)
agents[name]["pid"] = proc.pid
update_yaml_field(alive_path, "last_heartbeat", now_utc())
if batch:
    print(f"LAUNCHED:{name}:{proc.pid}")
```

Verify that `agent_string`, `short_prompt`, `prompt_rel`, `log_path`,
`alive_path`, `status_file`, `ait_cmd`, and `atype` are all computed
before the ctx is built. They are in the current layout
(lines 410–490), so this is a pure hoist with no behavior change.

---

## Phase 3 — Dynamic UI loops

Both modals already handle any mode count because they'll iterate
`sorted(VALID_LAUNCH_MODES)`. The only display consideration is
button labels: `.capitalize()` on `"openshell_headless"` gives
`"Openshell_headless"` which is ugly. Use
`mode.replace("_", " ").title()` which produces
`"Openshell Headless"` / `"Openshell Interactive"` and works for any
future mode name.

### 3.1 `LaunchModePickerScreen` (agent_model_picker.py, lines 506–562)

Follow the t461_8 pattern of local function-level imports in this
file to avoid disturbing top-of-file Textual import ordering. The
class already does `from launch_modes import normalize_launch_mode`
inside `__init__`; add `VALID_LAUNCH_MODES` to the same import.

New `compose`:

```python
def compose(self) -> ComposeResult:
    from launch_modes import VALID_LAUNCH_MODES
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
            for mode in sorted(VALID_LAUNCH_MODES):
                yield Button(
                    mode.replace("_", " ").title(),
                    variant=(
                        "primary" if self.current == mode else "default"
                    ),
                    id=f"lm_{mode}",
                )
            yield Button("Cancel", variant="default", id="lm_cancel")
```

New `on_button_pressed`:

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    from launch_modes import VALID_LAUNCH_MODES
    bid = event.button.id or ""
    if bid == "lm_cancel":
        self.dismiss(None)
        return
    if bid.startswith("lm_"):
        mode = bid[len("lm_"):]
        if mode in VALID_LAUNCH_MODES:
            self.dismiss({"key": self.operation, "value": mode})
            return
    self.dismiss(None)
```

**CSS**: no changes. `#lm_buttons Button { margin: 0 1; }` already
applies generically. With 4 mode buttons + Cancel = 5 buttons, the
50%-width dialog should still fit — if not, the existing CSS rule
can handle spacing but width may need a bump. Check visually and
bump to `60%` if necessary (note in Final Implementation Notes).

**Caller** (`settings/settings_app.py`): no changes — the returned
dict shape (`{"key": operation, "value": mode}`) is preserved.

### 3.2 `AgentModeEditModal` (brainstorm_app.py, lines 271–334)

`VALID_LAUNCH_MODES` is already imported at line 67.

New `compose` body (only the `else` arm changes):

```python
def compose(self) -> ComposeResult:
    with Container(id="mode_modal_dialog"):
        yield Label(
            f"Launch mode: {self.agent_name}",
            id="mode_modal_title",
        )
        yield Static(
            f"Current: [bold]{self.current_mode}[/bold]  "
            f"Status: {self.agent_status}",
            id="mode_modal_current",
        )
        if self.agent_status != "Waiting":
            yield Static(
                "[dim]launch_mode can only be changed on Waiting agents. "
                "Close this dialog and reset the agent first if needed.[/]",
                id="mode_modal_note",
            )
            with Horizontal(id="mode_modal_buttons"):
                yield Button("Close", variant="default", id="btn_mode_close")
        else:
            with Horizontal(id="mode_modal_buttons"):
                for mode in sorted(VALID_LAUNCH_MODES):
                    yield Button(
                        mode.replace("_", " ").title(),
                        variant=(
                            "primary"
                            if self.current_mode == mode
                            else "default"
                        ),
                        id=f"btn_mode_{mode}",
                    )
                yield Button("Cancel", variant="default", id="btn_mode_cancel")
```

Delete the three `@on(Button.Pressed, "#btn_mode_<x>")` decorator
methods (`_pick_headless`, `_pick_interactive`, `_cancel`). Replace
with a single method:

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    bid = event.button.id or ""
    if bid in ("btn_mode_cancel", "btn_mode_close"):
        self.dismiss(None)
        return
    if bid.startswith("btn_mode_"):
        mode = bid[len("btn_mode_"):]
        if mode in VALID_LAUNCH_MODES:
            self.dismiss(mode)
            return
    self.dismiss(None)
```

Keep `action_cancel` unchanged.

**CSS** (`#mode_modal_buttons { height: 3; align: center middle; }`)
is generic — no changes. Width is set on the container
(`#mode_modal_dialog { width: 60; ... }`). With 5 buttons the row
may need to grow to `width: 80;` — check visually and bump if the
buttons overflow. Note the final width in Final Implementation Notes.

**Caller** (`brainstorm_app.py` line ~1718 push_screen callback): no
changes — the dismiss value contract (mode string or None) is
preserved.

---

## Phase 4 — brainstorm_crew.py signature and docstring cleanup

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py`

`DEFAULT_LAUNCH_MODE` and `VALID_LAUNCH_MODES` are already imported
(line 28). No new imports needed.

### 4.1 Replace literal `"headless"` defaults with `DEFAULT_LAUNCH_MODE`

| Line | Function | Change |
|------|----------|--------|
| ~105 | `_run_addwork` | `launch_mode: str = "headless"` → `= DEFAULT_LAUNCH_MODE` |
| ~125 | `_run_addwork` body | `.get("launch_mode", "headless")` → `.get("launch_mode", DEFAULT_LAUNCH_MODE)` |
| ~356 | `register_explorer` | `launch_mode: str = "headless"` → `= DEFAULT_LAUNCH_MODE` |
| ~398 | `register_comparator` | ditto |
| ~434 | `register_synthesizer` | ditto |
| ~472 | `register_detailer` | ditto |
| ~508 | `register_patcher` | ditto |

Verify line numbers at edit time — the task description's numbers
may have drifted.

### 4.2 Update docstrings

Five `register_*` docstrings currently say:

```
launch_mode: Launch mode for the agent ("headless" or "interactive").
```

Change to:

```
launch_mode: Launch mode for the agent; one of VALID_LAUNCH_MODES
    (defaults to DEFAULT_LAUNCH_MODE).
```

### 4.3 Leave `BRAINSTORM_AGENT_TYPES` unchanged

Per-type defaults in `BRAINSTORM_AGENT_TYPES` (lines 40–46) are
business logic. Acceptance grep explicitly exempts this dict.
`get_agent_types()` already validates config overrides against
`VALID_LAUNCH_MODES`.

---

## Phase 5 — Help-text heredocs (static update, four modes)

Leave the heredocs `<<'HELP'` (quoted — no expansion) to avoid
unintended variable substitution. Update the literal enumeration to
include all four modes.

### 5.1 `.aitask-scripts/aitask_crew_addwork.sh` line 49

```
-  --launch-mode <mode>      Launch mode: 'headless' (default) or 'interactive'
+  --launch-mode <mode>      Launch mode (default: headless). One of:
+                            headless, interactive, openshell_headless,
+                            openshell_interactive.
```

### 5.2 `.aitask-scripts/aitask_crew_init.sh` line 45

```
-                            third field sets launch_mode (headless|interactive).
+                            third field sets launch_mode, one of:
+                            headless, interactive, openshell_headless,
+                            openshell_interactive.
```

### 5.3 `.aitask-scripts/aitask_crew_setmode.sh`

Line 32 (usage):

```
-Usage: ait crew setmode --crew <id> --name <agent> --mode <headless|interactive>
+Usage: ait crew setmode --crew <id> --name <agent> --mode <MODE>
```

Line 41:

```
-  --mode <mode>     New launch mode: 'headless' or 'interactive'
+  --mode <MODE>     New launch mode. One of: headless, interactive,
+                    openshell_headless, openshell_interactive.
```

The `<MODE>` placeholder in the usage line keeps the usage synopsis
short while the options section enumerates the full list.

No shell bridge changes needed. The `launch_modes_sh.sh` regex
validation continues to gate the accepted set dynamically.

---

## Phase 6 — Create follow-up task (in implementation, before archival)

After the refactor passes tests, create a new top-level task tracking
real `openshell_headless` and `openshell_interactive` launch
semantics. A single task covers both variants since they'll likely
share sandbox-setup infrastructure.

```bash
./.aitask-scripts/aitask_create.sh --batch \
    --name "openshell_launch_semantics" \
    --priority low --effort medium \
    --type feature \
    --labels agentcrew \
    --desc-file <followup_description.md>
```

Description body (drafted at implementation time, after the exact
LaunchError messages and location are known):

> Implement real launch semantics for `openshell_headless` and
> `openshell_interactive` in `.aitask-scripts/agentcrew/agentcrew_runner.py`.
>
> Both modes are currently registered in `LAUNCHERS` but raise
> `LaunchError("... not yet implemented — tracked in follow-up task")`.
>
> Open design questions:
> - What does "openshell" mean concretely? Proposal: a sandboxed
>   subprocess running a shell (not Claude Code), with the work
>   prompt as the shell's initial input or a preloaded history entry.
>   The headless variant pipes the shell's stdout/stderr to the log
>   file and runs non-interactively; the interactive variant opens a
>   terminal (tmux window or fallback terminal) attached to the shell
>   so a human can drive it.
> - What sandboxing: chroot? namespaces? None? Just a scoped working
>   directory?
> - How do prompts flow: positional arg? stdin? heredoc?
> - Does the runner still own the lifecycle, or is openshell launch
>   fire-and-forget?
>
> Acceptance: both modes launch successfully in the e2e canary,
> pipe-pane integration works for the interactive variant, and
> `tests/test_brainstorm_crew.py` is extended with at least one case
> per variant (using a mock shell or a minimal `echo`-based stub).

The new task's ID is recorded in Final Implementation Notes so
future readers can follow the trail.

---

## Verification

**Unit tests:**

```bash
python3 tests/test_launch_modes.py       # vocabulary canonical tests
python3 tests/test_brainstorm_crew.py    # crew defaults / config
```

`test_launch_modes.py` is updated in Phase 1.3. `test_brainstorm_crew.py`
should pass unchanged since it tests business logic (per-type defaults)
which remains untouched.

**Regression tests:**

```bash
bash tests/test_crew_setmode.sh
bash tests/test_crew_init.sh
bash tests/test_launch_mode_field.sh
python3 tests/test_brainstorm_dag.py
```

The crew shell tests may include help-text or error-message
assertions. The t461_8 final notes confirm `test_crew_setmode.sh`
already uses the dynamic `"must be one of:"` prefix rather than
hardcoding mode names, so validation assertions should be immune.
Re-run anyway and update if anything fails.

**Lint:**

```bash
shellcheck .aitask-scripts/aitask_crew_addwork.sh \
           .aitask-scripts/aitask_crew_init.sh \
           .aitask-scripts/aitask_crew_setmode.sh
```

**Acceptance grep** — must return no matches outside
`launch_modes.py`, `BRAINSTORM_AGENT_TYPES`, test files, and human
docs/comments:

```bash
grep -rnE '"headless".*"interactive"|headless\|interactive' .aitask-scripts/
```

**Smoke test — four-mode canary end-to-end:**

1. In a crew sandbox:
   - `ait crew setmode --crew <id> --name <agent> --mode openshell_headless`
     → `UPDATED:<agent>:openshell_headless`
   - Same for `openshell_interactive`.
   - Error path: `ait crew setmode ... --mode bogus` → validation
     error listing all four modes.
2. Start the runner. Expect both openshell agents to transition to
   `Error` with `error_message` matching their stub LaunchError;
   other agents launch normally; runner loop does not crash.
3. Open `ait brainstorm` TUI, edit a Waiting agent:
   - Four mode buttons present (Headless, Interactive, Openshell
     Headless, Openshell Interactive), with the current one
     highlighted.
   - Pick each openshell variant and confirm the yaml updates.
   - Confirm the modal width still fits (bump CSS if overflow).
4. Open the settings TUI launch-mode picker. Same four-button
   behavior and persistence.
5. Revert any test data before archival.

**Fourth/fifth-mode extensibility check** (optional drive-by): add a
throwaway `"devcontainer"` to `VALID_LAUNCH_MODES` and confirm the
`assert set(LAUNCHERS.keys()) == set(VALID_LAUNCH_MODES)` import-time
check fires with a clear message, then revert.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9:
- Commit code changes with `refactor: <summary> (t461_9)`
- Commit plan file separately via `./ait git` with
  `ait: Update plan for t461_9`
- Create the follow-up task (Phase 6)
- Run `./.aitask-scripts/aitask_archive.sh 461_9`
- Push via `./ait git push`

Since this is a child task, the archived plan is the primary
reference for subsequent sibling tasks. Final Implementation Notes
must capture:
- Any line-number drift in `brainstorm_crew.py` signatures
- Whether any CSS width needed bumping for 4-button layouts
- The exact wording of both LaunchError messages (so the follow-up
  task can reference them)
- The follow-up task's ID and its registered scope
- Any test assertions that needed updates beyond Phase 1.3
