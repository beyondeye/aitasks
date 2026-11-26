---
Task: t2363_fix_agent_dialog_profile_selection_and_narrow_editor.md
Base branch: main
Output branch: main
---

# t2363 — Profile selector in the agent launch dialog + narrow profile editor

## Context

Launching `/aitask-pick` from **minimonitor** (~31-40 col pane) the user cannot
choose a different execution profile: the launch dialog's Profile row only has
`(E)dit`, and `(E)dit` opens a profile editor that has no narrow mode — 80%
width, one-line field rows that clip long option lists with no way to scroll to
them. Separately, every profile path in `AgentCommandScreen` is cwd-relative, so
a dialog opened for a task in **another** project (minimonitor/monitor
`build_pick_screen(target_root, …)`) reads and writes the wrong project's
profiles. Outcome: a working profile selector (wide and narrow), an editor that
is usable at 31-40 cols, and profile I/O rooted at `project_root`.

Work happens on the current branch (`main`, profile `fast`), no worktree.

## Design decisions

- **Selector = a `Pr(o)file` button + small picker modal, not an inline
  `Select`.** Measured: at 31/35/40 x 44 the narrow dialog has **0 rows of
  slack** — the tmux tab already fills its 39-row max (inner 34 rows, Run/Cancel
  at the bottom edge) and `test_action_buttons_fit_vertically_on_open` pins it.
  An inline Select stacked in the narrow row adds 3 rows; a Select beside
  `(E)dit` in 27 columns truncates names. The narrow profile row stays at
  today's 4 rows: a 1-row status line + one row of two half-width buttons.
- **Key `o`/`O`** (`Pr(o)file`). Free in the dialog's `BINDINGS` and `on_key`
  (`c p r d e a u t s n w m escape`), and no host opens the dialog with `o`
  (t1296 collision class avoided).
- **The profile row only exists for profile-aware skills.** Canonical rule
  (`aitask_skillrun.sh:71`): a skill is profile-aware iff
  `.claude/skills/aitask-<skill>/SKILL.md.j2` exists. Measured for the dialog's
  callers: pick, resume, trail, qa, brainstorm-discuss → yes; **work-report and
  explain → no** (no stub, no `--profile` parse). Today their dialogs still show
  the row, and `(E)dit` → one-shot already prepends a `--profile _skillrun_…`
  those skills cannot apply. The gate hides the whole row (selector **and**
  edit) for them, so neither control can inject an argument the skill ignores.
- **Profiles are identified by `name`** (what `--profile` resolves —
  `aitask_skill_render.sh:81-83` matches the scanner's name column), mapped to
  their file through `aitask_scan_profiles.sh` run from `project_root`.
  - **First scanner row per name wins**, exactly like the renderer's
    `awk … $3==n {print $2; exit}` (the scanner merges by *filename*, so two
    files can declare one name). That single name→file map backs the picker,
    the edit load and the persistent save, and keeps OptionList ids unique.
  - **A name must be a single safe token to be selectable**:
    `^[A-Za-z0-9_][A-Za-z0-9._-]*$` (it becomes one `--profile` argv token and a
    `<skill>-<profile>-/` directory name). Others (`my profile`, a quoted
    `"fast"`) are listed **disabled** with the reason, never passed.
  - `_skillrun_*` one-shot overrides are excluded from the list.
- **A profile-aware dialog always knows its real default.** The board Trail,
  board Resume and codebrowser QA callers pass `skill_name` but no
  `default_profile`, while their stubs resolve one
  (`aitask_skill_resolve_profile.sh <skill>`). The dialog resolves it itself
  when the caller omits it (`resolve_skill_profile(skill_name, project_root)`,
  the helper `build_pick_screen` already uses), so Edit loads the real profile
  and persistent Save has a target. No "(skill default)" pseudo-option is
  needed.
- **The launched agent resolves profiles in the same environment the dialog
  did.** The default is still sent **without** `--profile` (the task's
  acceptance contract). The launched stub then resolves the default
  (`aitask_skill_resolve_profile.sh`, honors `USERCONFIG` / `PROJECT_CONFIG`)
  and looks the profile file up (`aitask_skill_render.sh` → scanner, honors
  `PROFILES_DIR` / `LOCAL_PROFILES_DIR`). Both run in the agent's own
  environment: the TUI's for a terminal run, the **tmux server's** for a tmux
  run. So a named `--profile` alone does not protect the lookup either;
  reproduced: `profile 'fast' not found` with an inherited empty
  `PROFILES_DIR`. The dialog therefore **carries its target-root profile
  environment into the command**. Every command it holds gets
  `-u PROFILES_DIR -u LOCAL_PROFILES_DIR -u USERCONFIG -u PROJECT_CONFIG`
  inserted into the leading `env` word that every resolver-built command
  starts with (t1850, `agent_launch_utils.resolve_dry_run_command` docstring).
  This is a pure string transform, no re-resolution. `env -u` still execs,
  so `#{pane_pid}` stays the agent (t1465), and it is supported by GNU and
  BSD/macOS `env`; the repo already uses it (`aitask_note.sh:1242`). The
  dialog, the launched resolver and the launched renderer then read the same
  files: the target root's, found from each script's own `SCRIPT_DIR`.
- **State changes only after the command resolves.** Every path that changes
  which profile the run uses (select, one-shot save, override clear) builds the
  candidate args, resolves them, and commits state + UI only on success; on
  failure the previous command, prompt, row label and edit target all stay as
  they were.
- **Editor narrow mode = compact two-line rows.** A `compact` flag on
  `CycleField` / `ConfigRow` renders the label on line 1 and only the current
  value on line 2 (`◀ value ▶  i/n`), height auto (set as an inline style so no
  App-level `CycleField { height: 1 }` can override it). Left/Right still cycle.
  Clicks act only on the rendered controls: the click row is read back from
  what Textual actually rendered, so a label that wraps (e.g.
  `manual_verification_followup_mode:` at 31 cols) is inert on every one of its
  physical lines; `◀` goes back, the rest of the control line goes forward. The
  settings TUI never passes `compact`, so its rendering and click mapping are
  unchanged.

## Implementation steps

### Pre-phase (risk mitigations)

1. [characterize_profile_edit_flows] **Before any change to
   `agent_command_screen.py`**, create `tests/test_agent_command_profile_select.py`
   with the temp-root fixture of step 5.2, but pinning today's behaviour only:
   - one-shot save → command args start with `--profile _skillrun_<…>`, the
     override file is written under `profiles/local/`, row label updates;
   - persistent save with no override → writes `local/<default>.yaml`, the
     rerender helper is invoked with `<default>`;
   - persistent save after a one-shot → the override is cleared and the
     command has no `--profile`;
   - `_load_active_profile_data()` returns the override's data while it is
     active, the default profile's data otherwise.
   Run it on the unmodified code (with `cwd` switched to the temp root for
   this run only, since the old paths are cwd-relative) and record the green
   result in the plan's Final Implementation Notes. These cases stay in the
   file through the refactor; only expectations that encode an intended
   change are updated (persistent save targets the *selected* profile, paths
   resolve under `project_root` with cwd elsewhere, row label shows the
   one-shot badge, a resolver-shaped command gains the `env -u …` flags), and
   each such edit is named in the Final Implementation Notes.

### 1. `profile_editor.py` — profile scan helper + picker modal

File: `.aitask-scripts/lib/profile_editor.py`

1. Add `PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")`,
   `ProfileInfo` (dataclass: `name`, `filename`, `description`, `usable: bool`)
   and `scan_profiles(project_root: Path) -> list[ProfileInfo]`:
   - uses `target_root_profile_env()` from `agent_launch_utils` (step 3.0) —
     the **one** env shared by the scan, the default resolution, the rerender
     and (as `env -u` flags) the launch command;
   - runs `<root>/.aitask-scripts/aitask_scan_profiles.sh` with `cwd=root`,
     `timeout=5`, `env=target_root_profile_env()`;
   - parses `PROFILE|<file>|<name>|<desc>` with `split("|", 3)`, in scanner
     order; skips names starting with `_skillrun_`; **keeps the first row per
     name** (renderer parity); `usable = bool(PROFILE_NAME_RE.match(name))`;
     returns `[]` on any failure / `NO_PROFILES`.
2. Add `ProfilePickerScreen(GuardedModalScreen)`:
   - ctor `(profiles, current: str | None, default: str | None, narrow=False)`;
   - compose: `Container#profile_pick_dialog` → title `Label("Select profile")`,
     `OptionList#profile_pick_list` with one option per profile, **id =
     `f"p{index}"`** (never the raw name, so no name can break id rules) and a
     local `index → name` map. Prompt: `<name>` + ` (default)` when
     `name == default`, description dimmed on a second line; an unusable one is
     `disabled=True` with `— cannot be passed as --profile` instead of the
     description. Hint label `Enter: select · Esc: cancel`;
   - `on_mount`: highlight `current`, focus the list; `OptionSelected` →
     `dismiss(name)`; `escape` binding → `dismiss(None)`;
   - CSS: `width: 60%; height: auto; max-height: 80%`; narrow class (added in
     compose like `AgentCommandScreen`) → `width: 100%; min-width: 30;
     padding: 0 1; border: round $accent`.

### 2. `profile_editor.py` — compact rows + `ProfileEditScreen` narrow mode

1. `CycleField.__init__(…, compact: bool = False)`: store it; when set add class
   `compact` and `self.styles.height = "auto"`.
   - `render()`: compact → `f"  {label}:\n  [dim]◀[/] [bold reverse] {value} [/] [dim]▶  {i+1}/{n}[/]"`
     (escaped like today); non-compact unchanged.
   - `on_click`, compact only: read the clicked physical row back from the
     render — `self.render_lines(Region(0, event.y, self.size.width, 1))`
     (widget coordinates, `event.offset`), plain text via `Strip.text`. A row
     that contains neither `◀` nor `▶` is a label row, **including a wrapped
     label continuation** → ignore. On a control row: `x` on the `◀` cell
     (its index in that row's text, ±0) → `cycle_prev()`; any other cell →
     `cycle_next()`. This keys on what is actually drawn, so it holds however
     the label or value wraps at any width. Non-compact keeps
     `_option_index_at` (untouched). Verify the coordinate frame
     (`event.offset` vs `get_content_offset`) with a probe at the start of
     this step and pin it in the test below.
2. `ConfigRow.__init__(…, compact: bool = False)`: compact → height auto inline
   style; `render()` → `f"  [bold]{key}:[/bold]\n    {value}"` (no
   `[PROJECT]` badge — the modal hard-codes it and it costs 11 columns; the
   subordinate form is not used by the modal).
3. `compose_profile_fields(…, compact: bool = False)`: forward to every
   `CycleField` / `ConfigRow`; in compact the hint labels use a 2-space indent
   instead of 6.
4. `ProfileEditScreen.__init__(…, narrow: bool = False)`; compose adds the
   `narrow` class, passes `compact=self._narrow`, and uses a two-line help text
   in narrow (`↑↓ move · ←→ cycle · Enter edit` / `S save · O one-shot · Esc
   cancel`) and the shorter one-shot label `(O)ne-shot`.
5. CSS (`DEFAULT_CSS`), narrow variant only:
   `ProfileEditScreen.narrow #profile_edit_dialog { width: 100%; height: 100%;
   min-width: 30; padding: 0 1; border: round $accent; }`, title/help
   `height: auto; padding: 0`, help `text-align: left`,
   `#profile_edit_scroll { scrollbar-size-vertical: 1; margin: 0; }`,
   `.section-hint { width: 100%; padding: 0 0 0 1; }` (so hints wrap instead
   of clipping), `.section-header { padding: 1 0 0 0; }`, CycleField/ConfigRow
   `padding: 0`, buttons row `layout: vertical; height: auto;` with
   `Button { width: 1fr; margin: 0; min-width: 0; }`.

### 3. `agent_command_screen.py` — rooted paths

File: `.aitask-scripts/lib/agent_command_screen.py` (and
`.aitask-scripts/lib/agent_launch_utils.py` for 3.0)

0. In `agent_launch_utils.py`, next to `resolve_dry_run_command` (it owns the
   `env` prefix contract):
   - `PROFILE_ENV_OVERRIDES = ("PROFILES_DIR", "LOCAL_PROFILES_DIR",
     "USERCONFIG", "PROJECT_CONFIG")`. The scanner (hence the renderer and the
     rerender helper) honors the first two, and
     `aitask_skill_resolve_profile.sh` the last two. Without them every helper
     derives its paths from its own `SCRIPT_DIR`, i.e. the target root;
   - `target_root_profile_env() -> dict[str, str]`: `os.environ` copy minus
     those names;
   - `with_target_root_profile_env(cmd: str) -> str`: when `cmd` starts with
     the word `env` (every resolver-built command does, t1850), insert
     `-u <NAME>` for each name right after it, skipping a name already unset
     there (idempotent). Otherwise return `cmd` unchanged (an unknown shape,
     e.g. a test's `"c"`, is never rewritten).
1. Replace `_PROFILES_DIR` / `_LOCAL_PROFILES_DIR` constants with
   `_profiles_dir(root)` / `_local_profiles_dir(root)` (root /
   `aitasks/metadata/profiles`).
2. `_prune_stale_skillrun_overrides(project_root: Path)`; `__init__` calls it
   with `self._project_root`.
3. Persistent-save rerender: `[str(root / ".aitask-scripts" /
   "aitask_skill_rerender.sh"), name]` with `cwd=root` (the helper resolves
   agent skill roots relative to cwd) **and `env=target_root_profile_env()`**
   (its renderer re-runs the scanner, which would otherwise follow an
   inherited `PROFILES_DIR` and report `profile '<name>' not found`).
   **Read the exit status**: the helper runs under `set -euo pipefail`, so a
   failed render exits non-zero. Notify separately: the YAML write success
   (`Saved profile '<name>' to profiles/local/`), then on a non-zero exit or
   an `OSError` / timeout a warning `Profile saved, but refreshing its skill
   variants failed (exit <n>): <last stderr line>` — never a success message
   for a refresh that did not happen.
4. `resolve_skill_profile(skill, project_root)` passes
   `env=target_root_profile_env()` too, so the default a cross-project dialog
   shows is the target project's.

### 4. `agent_command_screen.py` — profile support gate, selection state, selector

1. **Gate.** Add module helper `skill_is_profile_aware(project_root, skill)` →
   `(root / ".claude/skills" / f"aitask-{skill}" / "SKILL.md.j2").is_file()`
   (the `aitask_skillrun.sh:71` rule). `__init__` sets
   `self._profiles_enabled = bool(skill_name) and skill_is_profile_aware(…)`.
   Then, when `_profiles_enabled` and the caller passed no `default_profile`
   (board Trail / Resume, codebrowser QA), set
   `default_profile = resolve_skill_profile(skill_name, project_root)` — the
   same resolution the skill's stub runs, so the dialog's "default" is the
   profile the run would really use.
   Every profile surface — the row in `compose`, `o`/`e` keys and bindings,
   `action_select_profile`, `action_edit_profile`, the save callbacks and
   `_effective_profile_arg` — keys on `_profiles_enabled` instead of
   `skill_name`. `skill_name` keeps its other role (the `/aitask-<skill>`
   prompt). Result: work-report and explain dialogs show no profile row and
   their command is exactly the one the caller passed.
2. State: `self._selected_profile = default_profile` (the real profile the run
   uses), keep `default_profile`, `_profile_override_name` (`_skillrun_*`) and
   `current_profile_name` (= override or selected, as today), plus a lazy
   `self._profile_infos: list[ProfileInfo] | None` cache (+ name→info map).
3. Args: `_profile_args(selected, override) -> list[str]` builds
   `["--profile", X] + operation_args` where X = override if set, else
   `selected` when it differs from `default_profile`; **the default gets no
   flag** (task contract). The caller's `operation_args` already containing
   `--profile` → no second flag.
   `_build_command_args()` = `_profile_args(self._selected_profile,
   self._profile_override_name)`.
3b. **Carry the env.** When `_profiles_enabled`, `__init__` applies
   `with_target_root_profile_env` to the caller's `full_command` (a pure
   string transform, so constructing a screen still runs no resolver), and
   `_commit_command` applies it to every re-resolved command, including the
   agent-change path (`_apply_agent_override`). So whatever `full_command` a
   host reads after dismiss (Run, Copy cmd, tmux) unsets the four names. A
   user edit in the Input is kept as typed (`_store_command`, unchanged).
4. **Resolve-then-commit.** `_resolve_candidate(args) -> str | None` calls
   `resolve_dry_run_command(root, operation, *args, agent_string=…)` and
   changes nothing. `_commit_command(cmd, args)` sets `full_command`,
   `#agent_cmd_input`, `prompt_str = f"/aitask-{skill_name} {' '.join(args)}".rstrip()`
   and the visible `#agent_cmd_prompt_label` (today it goes stale). Profile
   paths use it like this:
   - **select** (`_on_profile_picked(name)`): `None` → nothing; an unknown or unusable name → notify, nothing (defensive; the picker
     disables those); same as current selection with no override → nothing.
     Else `args = _profile_args(name, None)`; resolve; on failure notify
     `Could not resolve the command for profile '<name>' — kept '<current>'`
     and **return with all state untouched** (override still active, label,
     command, prompt, edit target unchanged). On success: commit the command,
     then drop any override (notify "One-shot edits discarded"), set
     `_selected_profile` / `current_profile_name`, refresh the row.
   - **one-shot save**: write the override file, resolve
     `_profile_args(selected, new_name)`; on failure notify and do **not** set
     `_profile_override_name` (the orphan file is left to the 1h prune); on
     success commit, then set the override state and refresh.
   - **clear override** (after a persistent save): resolve
     `_profile_args(selected, None)`; on failure keep the override state and
     notify; on success commit and clear.
   `_apply_profile_override` is removed (its two callers use the above);
   `_apply_agent_override` keeps its current shape (agent change, not profile).
5. Compose (only when `_profiles_enabled`): `Horizontal#profile_row` containing
   - `Horizontal#profile_status`: `Label#profile_row_label`
     (`Profile: <selected or (default)>`) and `Label#profile_oneshot_badge`
     (`(one-shot)` while an override is active, otherwise `hidden` — replaces
     showing the raw
     `_skillrun_<pid>_<ms>` name);
   - `Horizontal#profile_buttons`: `Button("Pr(o)file", id="btn_select_profile")`
     and the existing `(E)dit`.
   CSS wide: `#profile_status { width: auto; height: 3; }`, both labels
   `height: 3; content-align: left middle`, `#profile_buttons { width: auto;
   height: 3; }`. CSS narrow (the row is already `layout: vertical`):
   `#profile_status { width: 100%; height: 1; }`,
   `#profile_row_label { width: 1fr; height: 1; text-wrap: nowrap;
   text-overflow: ellipsis; }` (a long name ends in `…`),
   `#profile_oneshot_badge { width: auto; height: 1; }` (always fully shown —
   the badge is what must survive truncation), `#profile_buttons { width: 100%;
   height: 3; layout: horizontal; }` with its buttons `width: 1fr;
   min-width: 0`. Rows: 1 + 3 = 4, as today.
6. `BINDINGS += o/O → select_profile`; `on_key` gains an `o`/`O` branch next to
   `e`/`E` (same Input/Select early-return and opening-debounce ordering).
7. `action_select_profile()`: no-op unless `_profiles_enabled`; scan (cached);
   empty → `notify("No execution profiles found", severity="warning")`; else
   push `ProfilePickerScreen(infos, current=_selected_profile,
   default=default_profile, narrow=self._narrow)` → `_on_profile_picked`.
8. Edit follows the selection, all through the one name→info map:
   - `action_edit_profile` title uses `_selected_profile` (+ ` (one-shot)`),
     and passes `narrow=self._narrow` to `ProfileEditScreen`;
   - `_load_active_profile_data`: override → `local/<override>.yaml` under
     root; else the selected profile's scanned file under root, falling back
     to `local/<name>.yaml` then `<name>.yaml`;
   - `_on_profile_saved_persistent`: target name = `_selected_profile` (not
     `default_profile`); writes `local/<basename of that name's scanned
     filename>` (fallback `<name>.yaml`) under root — so a profile whose file
     name differs from its `name` is not duplicated; invalidates the scan
     cache; then the clear-override path above;
   - `_on_profile_saved_one_shot`: writes under root's `local/` (path above).

### 5. Tests

1. `tests/test_agent_command_dialog_narrow.py`:
   - `_isolate`: the prune stub becomes `lambda *a, **k: None`;
   - wide goldens: add `btn_select_profile` and the shifted `btn_edit_profile`
     to `_WIDE_HEADER` (deliberate wide-layout change; regenerate the numbers
     from a run and check only the profile-row entries moved);
   - new test: in narrow at every `_PANE_SIZES`, `#profile_row` stays 4 rows
     and both profile buttons sit inside the dialog;
   - new test (31x44 and 40x44, both tabs): after selecting a long profile name
     (≥ 30 chars, fixture-provided) **and** after a one-shot save on it,
     `#profile_status` is 1 row inside the dialog, `#profile_oneshot_badge` is
     displayed fully inside the dialog, the rendered status line ends with `…`
     plus the badge when truncated, and every `_ACTIONS[tab]` button is inside
     the dialog with `scroll_y == 0`.
2. `tests/test_agent_command_profile_select.py` (started in the pre-phase) — a
   temp project root (not cwd) holding a copy of the real
   `aitask_scan_profiles.sh`, a stub `aitask_skill_rerender.sh` that records
   argv + cwd, `.claude/skills/aitask-pick/SKILL.md.j2` (profile-aware marker),
   profiles `default` / `fast` / `remote`, `zz_other.yaml` declaring
   `name: remote` (duplicate name, later in scanner order), `spaced.yaml`
   declaring `name: my profile`, a long-named profile, and an old
   `local/_skillrun_old.yaml`; `resolve_dry_run_command` patched to echo its
   args (and to return `None` on demand). Cases:
   - `o` opens `ProfilePickerScreen`; options exclude `_skillrun_*`, the default
     is marked, `remote` appears once (mapped to `remote.yaml`), `my profile`
     is present but disabled; choosing `remote` → command and prompt carry
     `--profile remote`; choosing `fast` (the default) → no `--profile`
     (the task's acceptance case); every command the dialog holds — on open
     and after each choice — starts `env -u PROFILES_DIR -u LOCAL_PROFILES_DIR
     -u USERCONFIG -u PROJECT_CONFIG …`, exactly once;
   - `_on_profile_picked("my profile")` is refused with state unchanged;
   - **resolution failure with an active one-shot**: one-shot save on `fast`,
     then the resolver returns `None` for `--profile remote` → override still
     set, `full_command`, input value, `prompt_str`, prompt label, row label,
     badge and the edit-load target are all the pre-attempt values;
   - one-shot save whose resolution fails → no override state is set;
   - `(E)dit` after selecting `remote` loads `remote.yaml` (not
     `zz_other.yaml`) from the temp root; persistent save writes
     `<root>/…/local/remote.yaml` (not `fast`) and the rerender stub ran with
     `remote` in `<root>`;
   - one-shot save → `--profile _skillrun_…`, file under the temp root; a
     following persistent save clears it back to `--profile remote`; selecting
     another profile while a one-shot is active drops the override;
   - the stale `_skillrun_old.yaml` under the temp root is pruned on
     construction;
   - **profile-support gate**: a dialog built like the board's work-report
     call (`operation="work-report"`, `skill_name="work-report"`, no
     `SKILL.md.j2` for it in the fixture) has no `#profile_row`, `o`/`e` do
     nothing, and `full_command` / `prompt_str` equal the caller's originals
     (`--columns … --tasks …`, no `--profile`);
   - **board Trail call shape with a configured default**: the fixture adds
     `.claude/skills/aitask-trail/SKILL.md.j2`, a copy of the real
     `aitask_skill_resolve_profile.sh`, and `project_config.yaml` in the
     **block form** the shell resolver parses (`_extract_default_profile`
     reads an indented key; the inline `{trail: remote}` form resolves to
     `default`):
     ```yaml
     default_profiles:
       trail: remote
     ```
     A dialog built exactly like
     `board_trail_screen.py:1839` (`skill_name="trail"`, no `default_profile`)
     shows `Profile: remote`, `(E)dit` loads `remote.yaml`'s fields, a
     persistent save writes `local/remote.yaml`, and picking `remote` (marked
     default) leaves the command without `--profile`;
   - **inherited profile-directory overrides**: with `os.environ` patched so
     `PROFILES_DIR` / `LOCAL_PROFILES_DIR` point at an empty directory and
     `USERCONFIG` / `PROJECT_CONFIG` at empty files: the picker still lists the
     temp root's profiles, the Trail default still resolves to `remote`, and a
     persistent save writes `<root>/…/local/remote.yaml` and runs the rerender
     stub, which records `${PROFILES_DIR-unset}` / `${LOCAL_PROFILES_DIR-unset}`
     → both `unset`. A positive control runs the same stub with the raw
     inherited env and records the override, so the check can fail;
   - **launch chain under inherited overrides (real resolver + real
     renderer)**, in its own temp root: a copy of `.aitask-scripts/` (minus
     `__pycache__`) and of `.claude/skills/` (authoring dirs only, no rendered
     `*-` dirs), so the real `aitask_skill_resolve_profile.sh` and
     `aitask_skill_render.sh` run there and write only there. Its
     `project_config.yaml` sets `default_profiles:` / `  trail: remote`
     (block form). The test process env sets `PROFILES_DIR` /
     `LOCAL_PROFILES_DIR` to an empty dir and `USERCONFIG` to a file naming
     `fast` for `trail`. Build the board-Trail-shaped dialog, drive its real
     Run path (`run_terminal` → dismiss `"run"`) and read
     `screen.full_command` as the hosts do. Then **simulate the launched
     stub** with that command's own `env` prefix: take the leading `env` and
     its `-u` tokens via `shlex.split`, and run with the same inherited env
     (a) `aitask_skill_resolve_profile.sh trail` when the command has no
     `--profile` (the effective default), else the named profile; and (b)
     `aitask_skill_render.sh aitask-trail --profile <effective> --agent claude`
     (the renderer takes the full skill name, as the stub calls it; the
     default resolver takes the short `trail`).
     Assert, at each of three points (on open, after picking `fast`, after
     switching back to `remote`): effective profile == row label, and the
     render exits 0 having rendered `.claude/skills/aitask-trail-<effective>-/`.
     The default point has no `--profile`; `fast` has one.
     **Negative control:** the same two commands run *without* the `-u`
     tokens resolve `fast` and/or fail with `profile '…' not found`, so the
     assertions can fail. This replaces any reliance on a stubbed resolver for
     the env question;
   - **refresh failure is reported as such**: the rerender stub exits 3 with a
     stderr line → the YAML is written, the dialog shows the save notice plus a
     `warning` naming exit 3 and that line, and no refresh-success notice;
     exit 0 → no warning;
   - picker in narrow at 40x44: every option inside the dialog.
3. `tests/test_profile_editor_narrow.py` — `ProfileEditScreen(narrow=True)`
   at 31x44 and 40x44: `narrow` class present; every `CycleField` and
   `ConfigRow` region is inside the dialog's content region horizontally and
   its rendered lines contain its current value (not clipped); the help lines
   are fully rendered; compact clicks at 31 cols on
   `manual_verification_followup_mode` (whose label wraps — the test asserts
   it renders on ≥2 label rows first): a click on each label row, including
   `x=2` of the continuation row, changes nothing; a click on `◀` → previous;
   on the value and on `▶` → next; the same three control clicks on a short
   field whose label does not wrap; wide
   (`narrow=False`) `CycleField` stays one row with the old one-line render.
   Plus `scan_profiles` unit cases: first-per-name, `_skillrun_` exclusion,
   `usable` flag, inherited `PROFILES_DIR` / `LOCAL_PROFILES_DIR` ignored, and
   `target_root_profile_env()` drops exactly the four variables;
   `with_target_root_profile_env` cases: a resolver-shaped
   `env AITASK_AGENT_STRING=x claude …` gains the four `-u` flags right after
   `env`, a second call changes nothing, a non-`env` command is returned
   unchanged, and the result still execs one process (`env` stays the first
   word; `tests/test_launch_agent_string_env.py` still passes).
4. Run: the three files above, `tests/test_profile_editor_*.py`,
   `tests/test_agent_command_dialog_*.py`, `tests/test_brainstorm_guarded_dismiss.py`,
   `tests/test_pick_launch_argv.py`, `tests/test_pick_command_screen.py`,
   `tests/test_launch_agent_string_env.py`, the host dispatch tests
   (`tests/test_*dialog_run_dispatch.py`, `tests/test_trails_app.py`,
   `tests/test_brainstorm_discuss_launch.py`), then
   `bash tests/run_all_python_tests.sh`
   (verdict from the last line, `set -o pipefail`).

### 6. Docs

- `website/content/docs/skills/aitask-pick/execution-profiles.md`, section
  "Editing the profile in a launch dialog" → "Choosing and editing the profile
  in a launch dialog": the row appears for profile-aware skills; **Pr(o)file**
  picks any profile for this run (the default is marked). Choosing another
  profile adds `--profile <name>` to the command, and choosing the default
  removes the flag. Names that are not a single safe token are shown but
  cannot be chosen; **(E)dit** edits the selected profile, and (S)ave writes that
  profile's file under `profiles/local/`. Current-state prose only.
- `website/content/docs/concepts/skill-templating.md` bullet: mention
  **Pr(o)file** next to **(E)dit**.
- Run `python3 check_links.py --build` (from `website/`).

## Verification

- Tests in step 5 pass; full Python suite verdict `PASSED`.
- Manual: `ait minimonitor` → pick launch dialog in a ~40-col pane → `o` lists
  profiles, choose `remote` → command shows `--profile remote`; `e` opens the
  editor full-width with two-line rows and every value readable; save writes
  `aitasks/metadata/profiles/local/remote.yaml`. Board work-report dialog: no
  Profile row.

## Risk

### Code-health risk: medium
- Reworking the profile state (selected / default / one-shot override) and the command re-resolution in a dialog with 8 host call sites could regress the existing one-shot / persistent edit flows, which have no direct tests today · severity: medium · → mitigation: inline pre-phase characterize_profile_edit_flows
- The profile-support gate removes the Profile row from the work-report and explain dialogs, a visible behaviour change on two hosts · severity: low · → mitigation: none (the row could only inject a `--profile` those skills ignore; step 5.2 pins the work-report command)
- Adding the `env -u …` flags changes the command of every profile-aware dialog (pick, resume, trail, qa, brainstorm-discuss): it is visible in the Input, and host tests that compare a resolver-shaped `screen.full_command` to the caller's original could fail · severity: medium · → mitigation: none (the transform skips non-`env` commands, so fake commands in host tests are untouched; the full Python suite runs in step 5.4; any host test that pins a real resolver string is updated and named in the Final Implementation Notes)
- Resolving the default for Trail / Resume / QA dialogs adds one `aitask_skill_resolve_profile.sh` subprocess (5s timeout, falls back to `default`) when those dialogs open, and changes their row from `(default)` to the real name · severity: low · → mitigation: none (same helper `build_pick_screen` runs on every pick dialog; step 5.2 pins the Trail shape)
- The `compact` flag on `CycleField` / `ConfigRow` is shared with the settings TUI's Profiles tab; a change to the default path would alter that TUI · severity: low · → mitigation: none (default off; step 5.3 pins the wide render)
- The wide dialog's golden layout shifts (new `Pr(o)file` button), deliberately · severity: low · → mitigation: none (goldens regenerated, only profile-row entries may move)

### Goal-achievement risk: low
- The narrow profile row must hold a truncating status line plus two buttons in ~27 columns to stay at 4 rows; Textual sizing (`min-width`, ellipsis) could clip the badge or labels · severity: low · → mitigation: none (step 5.1 long-name + one-shot test at 31/40 cols)

Reassessed after inlining the pre-phase and the review fixes: code-health stays **medium** (blast radius across hosts is unchanged; the regression paths are now pinned), goal-achievement stays **low**.

### Planned mitigations
- timing: pre-phase | name: characterize_profile_edit_flows | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — regression of one-shot/persistent edit flows | desc: pin today's one-shot/persistent/clear/load behaviour in tests before refactoring the dialog's profile state

## Step 9 (Post-Implementation)

Commit code and plan separately per Step 8, then archival/merge per Step 9 of
the task workflow (current-branch mode: no worktree to remove).
