---
Task: t1025_3_settings_tui_project_group_editor.md
Parent Task: aitasks/t1025_design_project_group_grouping_and_tui_navigation.md
Sibling Tasks: aitasks/t1025/t1025_1_*.md, aitasks/t1025/t1025_2_*.md, aitasks/t1025/t1025_4_*.md
Archived Sibling Plans: aiplans/archived/p1025/p1025_1_*.md, aiplans/archived/p1025/p1025_2_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-18 16:53
---

# Plan: settings-TUI project-group editor (t1025_3)

## Context

Third child of t1025. Adds the **primary user-facing surface for managing
per-user project-group membership** to the settings TUI, consuming the data
layer t1025_1 shipped and the navigation t1025_2 wired.

**Verify-path correction (why this plan differs from the task/old plan).** The
task file and the pre-verify plan assumed t1025_3 would call **Python
membership-edit model methods in t1025_1's model layer** and do an **atomic
Python rename via `build_registry_yaml`**. Re-reading t1025_1's archived plan
against the current code shows that path was **deliberately not built**
(decision **D5**): t1025_1 kept the **bash CLI (`ait projects group …`) as the
single registry-mutation authority** and introduced **no Python writer**. Its
Final Notes explicitly instruct t1025_3 to *"mutate via `ait projects group
set/unset/sync` … reuse `validate_project_group_slug` for pre-flight; never
write `projects.yaml` directly."* This plan follows the delivered architecture.

### Delivered surface this task builds on (verified in current tree)

- **Bash CLI** `cmd_group()` in `.aitask-scripts/aitask_projects.sh:747` —
  verbs `list` / `set <name> <group>` / `unset <name>` / `sync`. `set` slug-
  validates and rejects; `unset` writes the `-` sentinel. Atomic full-file
  rewrite helper `set_registry_group()` (`:730`). **No `rename` verb exists.**
- **Python (read-only / pure, reusable):** `validate_project_group_slug()`
  (`agent_launch_utils.py:312`), `--validate-slug` CLI shim (`:1288`),
  `group_sessions` / `default_selected_group` / `advance_selected_group`,
  `GroupedSessions`, `PROJECT_GROUP_UNGROUPED_LABEL` (`:678`). No mutation API.
- **Settings TUI** `.aitask-scripts/settings/settings_app.py` (3439 lines):
  `TabbedContent` with 7 `TabPane`s composed at `:1378-1396`, each populated by
  a `_populate_<tab>_tab()` method run in `on_mount` (`:1399`); tab-switch
  action→pane map `_TAB_SWITCH_ACTIONS` (`:161`, rebindable, drives footer
  hints); modal patterns `ProfilePickerScreen` (`:922`, `FuzzySelect` list) and
  `NewProfileScreen` (`:960`, `Input`+`CycleField`+buttons). `subprocess` is
  already imported and used (`:11`, `:3071`).

## Approach (one line)

A new **"Project Groups" `TabPane`** lists registered repos under their current
group (read from `ait projects group list`); per-repo and per-group actions
**shell out to `ait projects group set/unset/sync/rename`**, pre-validating slugs
with the existing Python validator. Rename is supported by adding one **atomic
`group rename` verb to the bash CLI** (the single writer authority).

## Steps

### 1. Bash: add atomic `group rename <old> <new>` (`aitask_projects.sh`)

- Add a `rename_registry_group()` helper beside `set_registry_group()`
  (`:730`): one `awk -F'|'` pass that rewrites **every** row whose 5th field
  (`project_group`) equals `<old>` to `<new>`, then one `build_registry_yaml |
  atomic_write` — same atomic single-rewrite shape as `set_registry_group`.
  Carry all 5 fields through. Rename-into-an-existing slug **merges** (both
  groups' rows end up with `<new>`), matching the task's stated semantics.
- Add a `rename)` case to `cmd_group()`: require `<old>` and `<new>`; reject if
  `<new>` fails `validate_group_slug` (reuse the existing bash validator already
  called by `set`); error if no row currently has group `<old>` (nothing to
  rename); then call `rename_registry_group`. Add the verb to the `group`
  usage/help block (`:839`) and the dispatcher header comment (`:77-81`).
- Note: rename operates on the **stored registry** group value (not the
  config-fallback effective value) — consistent with `set`/`unset` writing the
  registry. A config-only-grouped repo is unaffected by rename (the user assigns
  it explicitly first); document this in the help one-liner.

### 2. Settings TUI: "Project Groups" tab (`settings_app.py`)

- **Compose** (`:1378-1396`): add
  `with TabPane(self.label("switch_tab_project_groups", "Project Groups"), id="tab_project_groups"): yield VerticalScroll(id="project_groups_content")`.
- **Register the tab switch:** add `"switch_tab_project_groups": "tab_project_groups"`
  to `_TAB_SWITCH_ACTIONS` (`:161`) and a default key binding (`g` is free vs the
  existing a/b/c/m/p/s/t) to `SettingsApp.BINDINGS` so the footer hint and
  rebind-in-Shortcuts behavior follow automatically.
- **`_populate_project_groups_tab()`** (call it from `on_mount`, `:1399`):
  - Read groups→members by shelling out to `ait projects group list`
    (`subprocess.run`, capture stdout); parse its grouped output (real group
    headers `slug:` then indented members, ending with the `(ungrouped):`
    bucket; `[STALE]` suffix preserved for display).
  - Render rows (a `DataTable` or `ListView` of `repo  ·  group`), grouped under
    headers, plus a top action bar with buttons: **Assign/Change group**,
    **Clear group**, **Rename group**, **Sync from configs**, **Refresh**.
    Mirror the existing pane structure (label + hint + controls) used by
    `_populate_project_tab` (`:2224`).
- **Mutating actions — all shell out, never write YAML:**
  - *Assign / Change* → push an `AssignGroupScreen(ModalScreen)` (modeled on
    `NewProfileScreen` `:960`): repo name (preset) + `Input` for the slug.
    **Pre-validate** the typed slug with the Python validator before shelling
    out — call `validate_project_group_slug` (import from `agent_launch_utils`)
    and show an inline error on reject, *before* any subprocess. On accept:
    `ait projects group set <repo> <slug>`.
    *(Create is implicit: assigning a repo to a not-yet-existing slug creates
    the group — no separate "create" op, matching t1025_1's model.)*
  - *Clear* → `ait projects group unset <repo>` (repo → "(ungrouped)").
  - *Rename* → a `RenameGroupScreen(ModalScreen)`: select the source group
    (from the parsed real-group list) + `Input` for the new slug (same
    pre-validate). On accept: `ait projects group rename <old> <new>`.
  - *Sync* → `ait projects group sync`.
  - After every mutation: surface the CLI's exit code / stderr (the `set`/`sync`
    paths `die` with a sourced message on invalid input) as a TUI notification,
    then **re-run `_populate_project_groups_tab()`** to reflect the new state.
- **Shell-out helper:** add a small `_run_projects_group(*args)` wrapper around
  `subprocess.run(["./ait", "projects", "group", *args], …)` returning
  `(rc, stdout, stderr)`, so the four call sites share error handling. Resolve
  the repo-root `ait` the same way existing subprocess sites do.

### 3. Out of scope (left to the right owners)

- **Docs / terminology rollout** → sibling **t1025_4** (do not touch
  `aidocs/`/website here).
- **Live manual verification** of the TUI flow → sibling **t1025_5**.
- No changes to discovery, `group_sessions`, or the other TUIs (t1025_1/_2).

## Verification

- **CLI (`tests/test_projects_cmd.sh`)** — extend the existing `group`
  block (currently covers list/set/unset/sync, `:121+`) with `rename`:
  - happy path: `group set a g1`, `group set b g1`, `group rename g1 g2` →
    both `a` and `b` now `project_group: g2`, no `g1` remains.
  - rename-into-existing **merges**: members of `g1` and `g2` all become `g2`.
  - invalid new slug rejected (non-zero, registry unchanged).
  - renaming a non-existent group errors (nothing rewritten).
  - field-preservation: a row's `path`/`last_opened`/`git_remote` survive the
    rename (only field 5 changes).
- **Settings TUI smoke (new `tests/test_settings_project_groups_tab.py`,
  pattern: `tests/test_settings_shortcuts_tab.py`)** — mount `SettingsApp`
  against a temp `HOME`/registry fixture and assert: the `tab_project_groups`
  pane mounts and lists the fixture's grouped + ungrouped repos; the slug
  pre-validation rejects a bad slug *before* any subprocess fires (assert via a
  subprocess spy / `validate_project_group_slug` call) — proving no-write-on-
  invalid; a valid assign issues exactly `ait projects group set <repo> <slug>`.
- `shellcheck .aitask-scripts/aitask_projects.sh`.
- Run `bash tests/test_projects_cmd.sh` and `tests/run_all_python_tests.sh`.

## Risk

### Code-health risk: medium
- `settings_app.py` is a large, central TUI; the change is **additive** (new
  tab + two modal screens + a subprocess wrapper, no edits to existing tabs/
  panes), so blast radius is bounded — but a new tab touches `compose`,
  `_TAB_SWITCH_ACTIONS`, `BINDINGS`, and `on_mount`, which must stay in sync. ·
  severity: medium · → mitigation: covered in-task by the tab-mount smoke test.
- New `group rename` extends the **registry-writer authority**; a wrong awk
  field-index or a missed slug-validation could corrupt registry rows or drop
  the group. · severity: medium · → mitigation: covered in-task — mirrors the
  tested `set_registry_group` atomic-rewrite pattern + the rename/merge/field-
  preservation/invalid-slug regression tests in `test_projects_cmd.sh`.
- Shelling out from the TUI adds subprocess error-handling surface (rc/stderr
  must reach the user, not be swallowed). · severity: low · → mitigation:
  covered in-task by the shared `_run_projects_group` wrapper + notification.

### Goal-achievement risk: low
- The approach now matches the **delivered** architecture (CLI authority + reuse
  of the pure validator/listing), so every editor op maps to a concrete,
  already-tested CLI verb; the only net-new piece (`group rename`) is small and
  follows an existing pattern. · severity: low · → mitigation: None.
- Interactive TUI behavior a unit test can't fully exercise (focus, modal flow,
  live registry) is **already owned by the planned sibling t1025_5** manual
  verification — not a gap in this task. · severity: low · → mitigation: None.

## Step 9
Standard child archival (see parent plan / task-workflow Step 9). Final
Implementation Notes must record, for sibling t1025_4 (docs): the new
`ait projects group rename <old> <new>` verb (atomic, merge-on-collision,
registry-value semantics) and that the settings editor is CLI-backed (no Python
registry writer), so docs describe the CLI verbs as the source of truth.
