---
Task: t777_17_per_run_profile_edit_in_agentcommandscreen.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-25 10:26
---

# Plan: t777_17 — Per-run profile (E)dit in `AgentCommandScreen`

## Context

The parent task (t777) decouples per-skill execution from runtime profile
resolution by templating skills at render time. To make per-run profile
customization ergonomic, the launch dialog (`AgentCommandScreen`) gains a
**Profile** row mirroring the existing **Agent** row: a label showing the
resolved profile name and an `(E)dit` button that opens the reusable
`ProfileEditScreen` (delivered by t777_16).

**Per user clarification, the editor exposes TWO save modes:**

- **Save persistently** — write to the user-layer override at
  `aitasks/metadata/profiles/local/<name>.yaml` so subsequent runs pick up
  the change (does not modify the git-tracked project YAML).
- **Save as one-shot** — write to
  `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml`; the dialog
  rewrites `full_command`/`prompt_str` to launch with
  `--profile _skillrun_<unique>` (per t777_3 D5/D6/D8 stub contract).

Both modes target `profiles/local/` (gitignored), so the project YAML is
never touched from a launch dialog. Stale `_skillrun_*.yaml` files are
best-effort pruned (≥1 hour old) at TUI startup.

## Verified Reference Lines (re-verified 2026-05-25)

- `agent_command_screen.py:251` — `compose()` start, existing Agent row at
  255-269 (model for new Profile row).
- `agent_command_screen.py:300` — `on_mount()`, `_refresh_agent_row` call at
  line 323; new `_refresh_profile_row` slots here.
- `agent_command_screen.py:621-642` — `_apply_agent_override` /
  `_refresh_agent_row` — direct shape model for `_apply_profile_override`
  and `_refresh_profile_row`.
- `agent_launch_utils.py:103-133` — `resolve_dry_run_command()`; called
  again to recompute `full_command` once override is set.
- `aitask_codeagent.sh:447, :471, :491-492, :517` — all four agents build
  the slash command as `/aitask-pick ${args[*]}`, so prepending
  `--profile <name>` to `args` injects it cleanly into the slash command.
- `lib/profile_editor.py:616-707` — `ProfileEditScreen(profile_data,
  on_save, *, title="Edit Profile")` — needs minor signature extension
  (see step 1).
- `aitask_scan_profiles.sh` — confirms `profiles/local/*.yaml` are
  auto-discovered by the resolver and shadow same-name project profiles.
- `aitask_skillrun.sh:189-216` — confirms `_skillrun_<unique>` naming
  convention; we reuse it here.
- `aitask_board.py:3893, 3994, 4035, 4176` — four `AgentCommandScreen(...)`
  call sites. Only the two pick sites (3893, 3994) get `skill_name="pick"`
  and `default_profile=<resolved>`.

## Critical Files

- `.aitask-scripts/lib/profile_editor.py` (modify) — extend
  `ProfileEditScreen` signature to support two save callbacks; render two
  Save buttons when both callbacks are provided.
- `.aitask-scripts/lib/agent_command_screen.py` (modify) — new Profile row,
  state, modal hook, command-refresh logic, startup prune.
- `.aitask-scripts/board/aitask_board.py` (modify) — pass `skill_name`,
  `default_profile` from the two pick call sites.

No new files.

## Step Order

### 1. `lib/profile_editor.py` — extend `ProfileEditScreen` for dual-save

Replace the single `on_save` callback with two optional callbacks. Keep the
existing single-callback shape callable via the persistent slot to remain
forward-compatible. The dismiss payload becomes `(mode, updated)` for new
callers; the legacy single-callback shape still gets just `updated`.

```python
class ProfileEditScreen(ModalScreen):
    def __init__(
        self,
        profile_data: dict,
        on_save: Callable[[dict], None] | None = None,
        *,
        on_save_persistent: Callable[[dict], None] | None = None,
        on_save_one_shot: Callable[[dict], None] | None = None,
        title: str = "Edit Profile",
        persistent_button_label: str = "Save",
        one_shot_button_label: str = "Save as one-shot",
    ):
        ...
        # Resolve effective handlers:
        # - If on_save_persistent / on_save_one_shot are provided, use them.
        # - Otherwise the legacy `on_save` callback maps to the persistent slot.
        self._on_save_persistent = on_save_persistent or on_save
        self._on_save_one_shot = on_save_one_shot
        ...
```

In `compose()`:

```python
with Horizontal(id="profile_edit_buttons"):
    yield Button(persistent_button_label, variant="success",
                 id="btn_profile_edit_save")
    if self._on_save_one_shot is not None:
        yield Button(one_shot_button_label, variant="primary",
                     id="btn_profile_edit_save_oneshot")
    yield Button("Cancel", variant="default", id="btn_profile_edit_cancel")
```

New handler:

```python
@on(Button.Pressed, "#btn_profile_edit_save_oneshot")
def do_save_one_shot(self):
    updated, errors = collect_profile_values(
        self.query_one, self.profile_data, id_prefix="modal",
    )
    if errors:
        for msg in errors:
            self.app.notify(msg, severity="error")
        return
    if self._on_save_one_shot is not None:
        self._on_save_one_shot(updated)
    self.dismiss(("one_shot", updated))
```

Existing `do_save` becomes `do_save_persistent`:

```python
@on(Button.Pressed, "#btn_profile_edit_save")
def do_save_persistent(self):
    updated, errors = collect_profile_values(
        self.query_one, self.profile_data, id_prefix="modal",
    )
    if errors:
        for msg in errors:
            self.app.notify(msg, severity="error")
        return
    if self._on_save_persistent is not None:
        self._on_save_persistent(updated)
    # Preserve legacy dismiss payload when caller used the single-callback shape.
    if self._on_save_one_shot is None:
        self.dismiss(updated)
    else:
        self.dismiss(("persistent", updated))
```

### 2. `agent_command_screen.py` — module-level prune helper

Add module-level constants + prune function. Called from
`AgentCommandScreen.__init__` (cheap; no-op when nothing to prune):

```python
import time
import yaml

_LOCAL_PROFILES = Path("aitasks/metadata/profiles/local")
_SKILLRUN_PRUNE_AGE_SECONDS = 3600  # 1 hour

def _prune_stale_skillrun_overrides() -> None:
    """Best-effort remove _skillrun_*.yaml in profiles/local/ older than 1h.

    1 hour is long enough that an in-flight agent run still has its override
    available (and once loaded, deleting the file on disk does not affect
    the running agent), but short enough that residue does not accumulate.
    """
    if not _LOCAL_PROFILES.is_dir():
        return
    now = time.time()
    for p in _LOCAL_PROFILES.glob("_skillrun_*.yaml"):
        try:
            if now - p.stat().st_mtime > _SKILLRUN_PRUNE_AGE_SECONDS:
                p.unlink(missing_ok=True)
        except OSError:
            continue
```

PyYAML is already a project dependency (`lib/skill_template.py`,
`settings_app.py`).

### 3. `AgentCommandScreen.__init__` — new kwargs + state

```python
def __init__(
    self,
    title: str,
    full_command: str,
    prompt_str: str,
    default_window_name: str = "",
    project_root: Path | None = None,
    operation: str | None = None,
    operation_args: list[str] | None = None,
    default_agent_string: str | None = None,
    default_tmux_window: str | None = None,
    skill_name: str | None = None,        # NEW
    default_profile: str | None = None,   # NEW
):
    super().__init__()
    # ... existing assignments unchanged ...
    self.skill_name = skill_name
    self.default_profile = default_profile
    self.current_profile_name: str | None = default_profile
    self._profile_override_name: str | None = None
    _prune_stale_skillrun_overrides()
```

The Profile row is rendered only when `self.skill_name` is truthy;
non-skill launches (brainstorm, create) get the dialog unchanged.

### 4. `compose()` — Profile row above Agent row

Insert immediately after `yield Label(self.title_text, ...)` and **before**
the existing Agent row block:

```python
if self.skill_name:
    with Horizontal(id="profile_row"):
        yield Label(
            f"Profile: {self.current_profile_name or '(default)'}",
            id="profile_row_label",
        )
        yield Button("(E)dit", variant="primary", id="btn_edit_profile")
```

Extend CSS: change `#agent_row { ... }` to
`#agent_row, #profile_row { ... }` and the same alias for the nested
selectors (`#agent_row Label`, `#agent_row Button`).

### 5. Key binding + action

Append `Binding("e", "edit_profile", "Edit profile", show=False)` to
`BINDINGS`. Mirror `(A)gent` handling in `on_key()`:

```python
if event.key in ("e", "E"):
    if self.skill_name:
        self.action_edit_profile()
    event.prevent_default()
    return
```

Add `@on(Button.Pressed, "#btn_edit_profile")` calling
`self.action_edit_profile()`.

### 6. `action_edit_profile` — load + push modal with dual callbacks

```python
def action_edit_profile(self) -> None:
    if not self.skill_name:
        return
    from profile_editor import ProfileEditScreen
    data = self._load_active_profile_data()
    base_name = self._profile_override_name or self.current_profile_name or "(default)"
    title = f"Edit Profile: {base_name}"
    self.app.push_screen(
        ProfileEditScreen(
            data,
            on_save_persistent=self._on_profile_saved_persistent,
            on_save_one_shot=self._on_profile_saved_one_shot,
            title=title,
            persistent_button_label="Save",
            one_shot_button_label="Save as one-shot",
        )
    )

def _load_active_profile_data(self) -> dict:
    """Load the current override (if any) or the active profile YAML.

    Returns an empty dict if no file is found — the schema renders every
    field as _UNSET.
    """
    if self._profile_override_name:
        path = _LOCAL_PROFILES / f"{self._profile_override_name}.yaml"
        if path.is_file():
            with open(path) as f:
                return yaml.safe_load(f) or {}
    name = self.current_profile_name or self.default_profile
    if not name:
        return {}
    # local/ shadows project — same precedence as aitask_scan_profiles.sh.
    candidates = [
        _LOCAL_PROFILES / f"{name}.yaml",
        Path("aitasks/metadata/profiles") / f"{name}.yaml",
    ]
    for p in candidates:
        if p.is_file():
            with open(p) as f:
                return yaml.safe_load(f) or {}
    return {}
```

### 7. Persistent save handler

Always writes to user layer (`profiles/local/<name>.yaml`) — never touches
project YAML from the launch flow. Per user decision: this is intentionally
safer than mirroring source layer.

```python
def _on_profile_saved_persistent(self, updated: dict) -> None:
    if not self.skill_name:
        return
    name = self.default_profile or self.current_profile_name
    if not name:
        self.app.notify("No active profile to save", severity="error")
        return
    updated = dict(updated)
    updated["name"] = name  # preserve canonical name
    _LOCAL_PROFILES.mkdir(parents=True, exist_ok=True)
    out_path = _LOCAL_PROFILES / f"{name}.yaml"
    with open(out_path, "w") as f:
        yaml.safe_dump(updated, f, sort_keys=False)
    self.app.notify(f"Saved profile '{name}' to profiles/local/")
    # Persistent save does NOT change the dialog's command — the resolved
    # profile name is unchanged. Just clear any in-flight one-shot override.
    if self._profile_override_name:
        self._clear_one_shot_override()
    self._refresh_profile_row()
```

### 8. One-shot save handler

```python
def _on_profile_saved_one_shot(self, updated: dict) -> None:
    if not self.skill_name:
        return
    if self._profile_override_name is None:
        unique = f"{os.getpid()}_{int(time.time() * 1000)}"
        self._profile_override_name = f"_skillrun_{unique}"
    name = self._profile_override_name
    updated = dict(updated)
    updated["name"] = name
    base_desc = updated.get("description") or ""
    if "(per-run override)" not in base_desc:
        updated["description"] = f"{base_desc} (per-run override)".strip()
    _LOCAL_PROFILES.mkdir(parents=True, exist_ok=True)
    out_path = _LOCAL_PROFILES / f"{name}.yaml"
    with open(out_path, "w") as f:
        yaml.safe_dump(updated, f, sort_keys=False)
    self.current_profile_name = name
    self._apply_profile_override()
    self._refresh_profile_row()

def _clear_one_shot_override(self) -> None:
    """Reset the dialog's command back to the base profile (no override)."""
    if not self._profile_override_name:
        return
    # Leave the file on disk — prune handles cleanup.
    self._profile_override_name = None
    self.current_profile_name = self.default_profile
    if self.operation:
        new_cmd = resolve_dry_run_command(
            self._project_root, self.operation, *self.operation_args,
            agent_string=self.current_agent_string,
        )
        if new_cmd:
            self.full_command = new_cmd
            try:
                self.query_one("#agent_cmd_input", Input).value = new_cmd
            except Exception:
                pass
            self.prompt_str = f"/aitask-{self.skill_name} {' '.join(self.operation_args)}".rstrip()
```

### 9. `_apply_profile_override` — recompute full_command + prompt_str

Mirrors `_apply_agent_override`:

```python
def _apply_profile_override(self) -> None:
    if not self.operation or not self._profile_override_name:
        return
    extra_args = ["--profile", self._profile_override_name]
    new_args = extra_args + list(self.operation_args)
    new_cmd = resolve_dry_run_command(
        self._project_root, self.operation, *new_args,
        agent_string=self.current_agent_string,
    )
    if new_cmd:
        self.full_command = new_cmd
        try:
            self.query_one("#agent_cmd_input", Input).value = new_cmd
        except Exception:
            pass
        self.prompt_str = (
            f"/aitask-{self.skill_name} {' '.join(new_args)}".rstrip()
        )
    else:
        self.app.notify(
            f"Failed to resolve command with override profile "
            f"{self._profile_override_name}",
            severity="error",
        )
```

**Interaction with `_apply_agent_override`:** patch the existing method so
that when `self._profile_override_name` is set, it prepends
`--profile <override_name>` to `operation_args` before dry-run. Share via a
small `_build_command_args()` helper:

```python
def _build_command_args(self) -> list[str]:
    args = list(self.operation_args)
    if self._profile_override_name:
        args = ["--profile", self._profile_override_name] + args
    return args
```

Use this helper in `_apply_agent_override`, `_apply_profile_override`, and
`_clear_one_shot_override` to remove duplication.

### 10. `_refresh_profile_row`

```python
def _refresh_profile_row(self) -> None:
    if not self.skill_name:
        return
    try:
        label = self.query_one("#profile_row_label", Label)
        label.update(f"Profile: {self.current_profile_name or '(default)'}")
    except Exception:
        return
```

Also call it once from `on_mount` (next to the existing
`self._refresh_agent_row()` invocation at line 323) for initial styling
consistency.

### 11. Caller updates — `aitask_board.py`

Two pick call sites (3893, 3994) gain:

```python
skill_name="pick",
default_profile=self._resolve_pick_profile(),
```

Helper (added to the board class):

```python
def _resolve_pick_profile(self) -> str:
    try:
        result = subprocess.run(
            [".aitask-scripts/aitask_skill_resolve_profile.sh", "pick"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return (result.stdout.strip() or "default")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return "default"
```

Lines 4035 (brainstorm) and 4176 (create) — **unchanged** (no skill stub).

### 12. Wrapper sanity (no code change)

`aitask_skillrun.sh --profile-override` from t777_5 already supports the
override-file shape we write — verified at `aitask_skillrun.sh:95-97` and
`:152-216`. The TUI flow does **not** invoke `ait skillrun` (it constructs
the slash command directly), but the file format is interchangeable, so a
user can also do
`ait skillrun pick --profile-override aitasks/metadata/profiles/local/_skillrun_<unique>.yaml`
externally without surprises.

## Pitfalls

- **Profile row hidden for non-skill dialogs** — gated on `self.skill_name`;
  brainstorm/create dialogs remain visually identical. Verify by opening
  each.
- **Re-edit reuses the same `_skillrun_<unique>` file** — first one-shot
  Save creates the file; subsequent one-shot Saves overwrite it. Implemented
  by gating new-unique generation on `if self._profile_override_name is None`.
- **Agent change preserves any active override** — `_apply_agent_override`
  uses `_build_command_args()`, which includes `--profile <override>` when
  set.
- **Persistent save never touches project YAML** — always writes to
  `profiles/local/<name>.yaml`. User intent confirmed.
- **`yaml.safe_dump` field ordering** — `sort_keys=False` to mirror the
  wrapper (`aitask_skillrun.sh:208`) and keep override readable.
- **Prune TTL of 1 hour** — long enough for in-progress runs (and the agent
  has already read the file into memory by then); short enough to bound
  residue. Documented in the prune helper docstring.
- **Empty override** — if the user opens (E)dit and Saves one-shot without
  changes, an override file is still created. Acceptable: it captures the
  intent and the 1h prune cleans it up.
- **Codex slash invocation** — driven by `aitask_codex_plan_invoke.py`. The
  `${args[*]}` expansion at `aitask_codeagent.sh:491-492` includes our
  `--profile <name>` prefix unchanged; no special-casing needed.
- **`ProfileEditScreen` legacy callers** — the dual-callback signature
  preserves the legacy single-callback shape: passing only `on_save=fn`
  maps to the persistent slot, no one-shot button is rendered, and the
  dismiss payload remains `updated` (not a tuple). No existing callers
  (settings_app uses inline rendering) need to change.

## Verification

1. **Smoke import** —
   `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); \
   import agent_command_screen; from profile_editor import ProfileEditScreen"`
   succeeds.
2. **Non-skill dialog unchanged** — `ait board` → press `n` (create) →
   dialog has NO Profile row. Same for brainstorm (`b`).
3. **Pick dialog shows Profile row** — focus a task, press `p` →
   AgentCommandScreen shows `Profile: <name>` row with `(E)dit`.
4. **Edit modal opens with two save buttons** — click `(E)dit` (or press
   `e`) → `ProfileEditScreen` opens with `Save` and `Save as one-shot`
   buttons (plus Cancel).
5. **Persistent Save writes to user layer** — toggle
   `skip_task_confirmation` → click `Save` → notification "Saved profile
   '<name>' to profiles/local/" → file `profiles/local/<name>.yaml` exists
   with the toggle applied. `full_command` and `Profile:` label unchanged.
6. **One-shot Save updates command** — open `(E)dit` again, toggle another
   field, click `Save as one-shot` → `Profile:` label becomes
   `_skillrun_<digits>` → `full_command` input updates to
   `claude --model … "/aitask-pick --profile _skillrun_<digits> 42"` →
   Copy Prompt yields `/aitask-pick --profile _skillrun_<digits> 42`.
7. **One-shot file written** — `ls aitasks/metadata/profiles/local/` shows
   `_skillrun_<digits>.yaml`; YAML contents include `name: _skillrun_<digits>`
   and the toggled field.
8. **Run-in-terminal applies the override** — click `Run in terminal` →
   launched agent skill shows `Profile '<name>': …` lines reflecting the
   override.
9. **Re-edit one-shot does not multiply files** — open `(E)dit` again,
   change another field, `Save as one-shot` → still only ONE
   `_skillrun_*.yaml` in local/.
10. **Agent change preserves override** — set a one-shot override, then
    press `(A)` and pick a different model → `full_command` shows the new
    agent AND still includes `--profile _skillrun_<digits>`.
11. **Prune** — `touch -d "2 hours ago" \
    aitasks/metadata/profiles/local/_skillrun_old.yaml`, relaunch
    `ait board`, trigger pick → `_skillrun_old.yaml` is gone, fresh files
    untouched.
12. **`ait settings` Profiles tab still works** — open it; ensure inline
    profile editing remains unchanged (ProfileEditScreen signature change is
    backward-compatible since settings_app does not use the modal).
13. **`aitask_skill_verify.sh`** — runtime-only change; rerun is optional
    but harmless.

See **Step 9 (Post-Implementation)** of the task workflow for cleanup,
archival, and merge.

## Post-Review Changes

### Change Request 1 (2026-05-25 11:30) — UX feedback round 1

- **Requested by user:** Section headers / description-hint labels were
  navigable as focus-stops without visible highlight; ConfigRow's editability
  was not discoverable; ←→ did nothing.
- **Changes made:**
  - Added `DEFAULT_CSS` to `ProfileEditScreen` (focus highlight classes
    `ConfigRow.row-focused` / `CycleField.cycle-focused`, section header /
    hint styling, fixed dialog height) so the modal looks/behaves consistently
    in any App that pushes it (not just `SettingsApp` whose App-level CSS we
    had been implicitly inheriting).
  - Added a help line under the title (`↑↓: navigate | ←→: cycle | Enter:
    edit string/int | S: save | O: save one-shot | Esc: cancel`).
- **Files affected:** `.aitask-scripts/lib/profile_editor.py`,
  `.aitask-scripts/lib/agent_command_screen.py` (dialog max-height 80% → 90%
  to fit the new Profile row).

### Change Request 2 (2026-05-25 11:50) — bottom-button truncation

- **Requested by user:** After the CSS additions, the dialog buttons
  (Save / Save-as-one-shot / Cancel) were partially clipped at the bottom.
- **Changes made:** Switched `#profile_edit_dialog` from `height: auto +
  max-height: 80%` to a fixed `height: 90%`, gave the scroll container
  `height: 1fr` so it consumes the remaining space, and used explicit
  `height: 1` on the title/help labels. Buttons now reliably visible.
- **Files affected:** `.aitask-scripts/lib/profile_editor.py`.

### Change Request 3 (2026-05-25 12:10) — left/right arrows still inert

- **Requested by user:** ←→ in the modal still did not cycle CycleField
  options despite all the prior fixes.
- **Root cause (via tmux pane capture + diagnostic notify):** the board's
  App-level `BINDINGS` declared `Binding("left", "nav_left", priority=True)`
  and `Binding("right", "nav_right", priority=True)`. App-level priority
  bindings fire **before** any modal screen binding. The board's existing
  `action_nav_left` / `action_nav_right` DID have modal-aware fallbacks
  (`if isinstance(focused, CycleField): focused.cycle_prev()`), but the
  isinstance check referenced the board's OWN `CycleField` class
  (`aitask_board.py:847`) — a distinct class from `profile_editor.CycleField`.
  So the modal's CycleField was never matched.
- **Changes made:** Duck-typed the modal-mode arrow handling in
  `aitask_board.action_nav_left` / `action_nav_right` to call
  `getattr(focused, "cycle_prev"/"cycle_next", None)` and invoke if callable.
  Removed the now-redundant priority bindings I had temporarily added to
  ProfileEditScreen.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `.aitask-scripts/lib/profile_editor.py`.

### Change Request 4 (2026-05-25 12:25) — keyboard shortcuts for Save buttons

- **Requested by user:** Add keyboard shortcuts for the Save and Save-as-one-shot buttons.
- **Changes made:** Added `s`/`S` → `action_save_persistent`, `o`/`O` →
  `action_save_one_shot` bindings (both as standard non-priority bindings —
  no Input widget is focused inside this modal, only CycleField / ConfigRow,
  so the letters don't conflict). Relabeled buttons "(S)ave" / "Save as
  (O)ne-shot" and refreshed the help line.
- **Files affected:** `.aitask-scripts/lib/profile_editor.py`.

## Final Implementation Notes

- **Actual work done:**
  - Extended `lib/profile_editor.py::ProfileEditScreen` with a dual-save
    signature (`on_save_persistent` / `on_save_one_shot` kwargs +
    `persistent_button_label` / `one_shot_button_label`), legacy single
    `on_save` shape preserved. Added self-contained `DEFAULT_CSS`, a help
    line, S/O keyboard shortcuts (`action_save_persistent` /
    `action_save_one_shot` delegate to the existing button handlers), and a
    module-private `_NoArrowsVerticalScroll` subclass that strips the
    `left`/`right` scroll bindings of `VerticalScroll`.
  - In `ProfileEditScreen.on_mount`: set `can_focus = False` on the inner
    scroll and seed focus on the first `CycleField` / `ConfigRow` so the
    first arrow press lands on an editable field.
  - `lib/agent_command_screen.py`: new module-level
    `_prune_stale_skillrun_overrides()` (1 hour TTL on
    `_skillrun_*.yaml`), new constructor kwargs `skill_name` /
    `default_profile`, new `Profile` row in `compose()` (above the existing
    Agent row, with shared CSS via `#agent_row, #profile_row` aliasing),
    `e` keybinding (also wired via `on_key` for parity with `(A)gent`/`(U)se`),
    new methods `_load_active_profile_data`, `_on_profile_saved_persistent`,
    `_on_profile_saved_one_shot`, `_apply_profile_override`,
    `_clear_one_shot_override`, `_build_command_args`, `_refresh_profile_row`.
    `_apply_agent_override` now goes through `_build_command_args()` so an
    agent change after a one-shot override preserves the `--profile
    <override>` injection.
  - `board/aitask_board.py`: new `_resolve_pick_profile()` helper; the two
    pick `AgentCommandScreen(...)` call sites (3893 / 3994) gain
    `skill_name="pick"` + `default_profile=...`; brainstorm (4035) and
    create (4176) remain unchanged. `action_nav_left` / `action_nav_right`
    now duck-type on `cycle_prev` / `cycle_next` so the modal's CycleField
    is cycled regardless of which class it is.
  - Dialog max-height in `agent_command_screen.py` bumped from 80% → 90%
    to accommodate the new Profile row without clipping bottom buttons.

- **Deviations from plan:**
  - The plan reused `VerticalScroll` directly; in practice Textual 8.1.1
    `VerticalScroll.BINDINGS` claims `left`/`right` for
    `scroll_left`/`scroll_right`. Subclassed it as `_NoArrowsVerticalScroll`
    (module-private) with those bindings stripped, so the focused CycleField's
    own arrow handling is never shadowed.
  - The plan assumed the board's `action_nav_left`/`action_nav_right`
    isinstance check would work transparently. It did not — there are two
    independent `CycleField` classes (`profile_editor` vs `aitask_board`).
    Duck-typed the check.
  - The plan called for `e` to be a `BINDINGS` entry. I also kept an
    `on_key` mirror so it works regardless of which key-routing path
    activates first (parity with the existing `(A)gent`/`(U)se` handling
    in the same file).

- **Issues encountered:**
  - Three rounds of UX feedback (focus highlight, button truncation, ←→
    not firing) → all captured in Post-Review Changes above. Root cause of
    the ←→ issue was non-obvious — required reading `aitask_board.py`'s
    App-level priority bindings AND noticing the board has its own
    `CycleField` class.
  - Bash classifier was temporarily unavailable for ~30 minutes during
    smoke-test execution. Waited it out; once auto mode disabled, tests
    ran fine.

- **Key decisions:**
  - **One-shot override file lives in `profiles/local/` (Strategy B per the
    initial design question)** rather than going through `ait skillrun
    --profile-override` (Strategy A). Reason: this lets `(P)rompt Copy`
    work for free — the slash command `/aitask-pick --profile
    _skillrun_<unique> 42` is self-contained and the agent's stub resolves
    the override by name. Cleanup is handled by `_prune_stale_skillrun_overrides()`
    (1h TTL) at every AgentCommandScreen `__init__`.
  - **Persistent save always lands in `profiles/local/` (user layer)** —
    confirmed by user. Never touches the git-tracked `profiles/<name>.yaml`
    from a launch dialog.
  - **`ProfileEditScreen` is fully self-contained for CSS** — does not
    rely on the surrounding App's CSS. This decouples it from `SettingsApp`
    (where the App-level CSS originally lived) and lets any App push it
    cleanly.
  - **Help line in the modal is essential** — without it, the user
    cannot discover that ConfigRow string/int fields are editable via
    Enter (focus highlight alone does not convey "editable"). Future
    profile-related modals should keep this convention.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - `aitask_board.action_nav_left` / `action_nav_right` now duck-type on
    `cycle_prev` / `cycle_next`. Any sibling modal that adds a cycle-able
    widget (e.g. t777_20 if it adds a per-skill overrides browser) gets
    arrow-key cycling for free.
  - The `_skillrun_<pid>_<ms>` naming convention is shared with
    `aitask_skillrun.sh:189-216`. Keep it in sync if t777_20 introduces
    another override path.
  - The new `ProfileEditScreen` dual-save signature is a strict superset
    of the legacy single-`on_save` shape. Future callers can opt into
    either mode; `settings_app.py` still uses inline rendering and is
    unaffected.
  - The prune helper (`_prune_stale_skillrun_overrides`) fires at every
    AgentCommandScreen construction. If t777_20 introduces a new entry
    point that does not go through AgentCommandScreen, consider lifting
    the prune call to a shared place (e.g. `aitask_pick_own.sh --sync`
    or a startup helper).

