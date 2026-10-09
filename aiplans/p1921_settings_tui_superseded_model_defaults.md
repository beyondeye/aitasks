---
Task: t1921_settings_tui_superseded_model_defaults.md
Base branch: main
Output branch: main
---

# t1921 — Settings TUI: mark superseded model defaults and switch them

## Context

t1910 records model supersession (`.aitask-scripts/lib/model_supersessions.json`)
and offers newer models at `ait upgrade` / `ait codeagent check-superseded`. The
Settings TUI **Agent Defaults** tab — where users actually look at per-op
defaults — shows `claudecode/opus5` exactly like a deliberate choice. Goal: mark
superseded values (project + per-user layer), show the offered target, and let
the user switch from the tab, writing through `ConfigManager` (which owns the
commit seam `_commit` → `lib/metadata_commit.py`).

## Decisions

- **Row-scoped, layer-only switch.** A switch changes one op in the focused row's
  layer and writes **only that layer's file**. A project switch commits the
  project file (Settings' explicit-save rule, t1677); a local switch writes the
  gitignored `.local.json` and attempts **no** commit. The other layer's file is
  not rewritten (`save_codeagent` always rewrites both and always commits the
  project file, so it is not used for this). Unlike `_handle_agent_pick`'s project
  branch, the local override is not dropped — same as the CLI's `_apply_offers`.
  A user row showing `(inherits project)` has no offer of its own.
- **Fresh state at action time.** The offer is re-derived from the layer files
  re-read from disk when the user acts, and the writer re-reads the file again
  immediately before writing and refuses unless the op still holds the
  superseded value. The update is built from that fresh dict, so another
  session's edits (same op or unrelated ops) are never overwritten with cached
  state.
- **Two entry points.** (1) **Enter** on a marked row opens a small choice modal
  — "Switch to `<agent>/<new>`" / "Choose another model…" (the existing picker) /
  Cancel — so the switch is always reachable and the full target is shown.
  (2) **`o`** ("Switch to newer model") switches the focused marked row directly:
  registry-backed `Binding(..., show=False)` gated to `tab_agent`, inert under a
  modal, like every other tab action in `SettingsApp`.
- **Existing user overrides win over the new default key.** If the user has
  already bound another `settings` / `shared` action to the key `o` resolves to
  (and has not overridden the switch action itself), `check_action` returns
  `None` for the switch, so Textual falls through to the user's binding
  (`run_action` returns False on a falsy `check_action`, verified in Textual
  8.2.7). The switch stays usable via Enter, and the hint line says so instead of
  advertising the shadowed key.
- **Marker on its own wrapping line.** `ConfigRow` is `height: 1`, so a suffix on
  the row value can be clipped (the target vanishes at 80 columns). The marker is
  a separate full-width, wrapping `Static` mounted directly under the marked row:
  `⚠ superseded by <agent>/<new> — <key>/Enter: switch`.
- **Keep memory: read-only, shown dimmed.** A CLI-kept offer renders
  `superseded by <agent>/<new> (kept via check-superseded)` in dim; it is still
  switchable. The TUI never writes the kept file.
- **Warnings render inline** as a hint label at the top of the tab (not
  `notify`, which would repeat on every repopulate). A malformed table/registry
  yields warnings and no markers — never an exception.
- **Existing `d` on_key handler stays as is** (footer-convention justification):
  as a `Binding` it would collide with `sc_reset`'s `d` in the same registry
  scope; changing its key is out of scope.
- **`AgentModelPickerScreen` unchanged**: a shared lib screen used by other TUIs;
  not needed for the goal.

## Steps

### 1. `lib/model_supersession.py` — share the CLI's readers (no logic change)

Move from `aitask_model_supersession.py` into the lib (stdlib only, keeps the
3.7 constraint), returning warnings instead of printing:

- `DEFAULT_TABLE_PATH` (the lib-dir `model_supersessions.json`).
- `load_registries(metadata_dir) -> (registries, warnings)` — body of
  `_load_registries` (glob `models_*.json`, skip `models_<agent>.local.json`,
  warning text unchanged).
- `KEPT_FILENAME`, `git_common_dir(root)` (from `_git`/`_git_common_dir`),
  `kept_path(root)` (`None` outside git), `load_kept(path) -> (kept, warnings)`
  (body of `_load_kept`, same warning texts, `None` path → `{}`).

`aitask_model_supersession.py`: `DEFAULT_TABLE = Path(ms.DEFAULT_TABLE_PATH)`;
`_load_registries` / `_load_kept` become thin wrappers that `_warn()` each
warning; `_git_common_dir` delegates. CLI output stays byte-identical (pinned by
`tests/test_model_supersession.py`).

### 2. `settings/settings_app.py` — `ConfigManager` (writer owns the commit)

- `reload_codeagent()` — re-reads `codeagent`, `codeagent_project`,
  `codeagent_local` only (the switch path's fresh read; `load_all` stays for the
  existing flows). Loads all three into locals first and assigns only when every
  read succeeded, so a failure leaves the in-memory state intact; the
  `OSError` / `ValueError` (incl. `JSONDecodeError`) propagates to the caller,
  which owns the user-facing report.
- `save_codeagent_layer(layer, data)` — `"project"`: `save_project_config` +
  `self._commit([_repo_rel(CODEAGENT_CONFIG)])`, returns the `CommitResult`;
  `"local"`: `save_local_config` on the `.local.json` path, no commit, returns
  `None`. Touches no other file.
- `switch_codeagent_default(layer, key, old_value, new_value) -> (status,
  detail)`: reads the layer file from disk (`json.load`, catching
  `OSError`/`ValueError`); missing / unreadable / `defaults` not a dict →
  `("unreadable", reason)`; `defaults.get(key) != old_value` →
  `("changed", current)`; otherwise sets `defaults[key] = new_value` on **that
  fresh dict** and `save_codeagent_layer(layer, data)` → `("switched",
  commit_result)`.

### 3. `settings/settings_app.py` — `SettingsApp`

- `import model_supersession as ms`; module constant
  `SUPERSESSION_TABLE = ms.DEFAULT_TABLE_PATH` (patchable by tests).
  `_AGENT_LAYERS = {"agent_proj_": ("project", "project"), "agent_user_":
  ("local", "user")}` (offer layer name, display label).
- `_supersession_state() -> (offers, warnings)`, `offers[(layer, op)] =
  (Offer, kept)`: `ms.load_table(SUPERSESSION_TABLE)` (on
  `SupersessionError`/`OSError` → `({}, [msg])`), `ms.load_registries(METADATA_DIR)`,
  `ms.load_kept(ms.kept_path(Path.cwd()))`; per layer take `defaults` from the
  in-memory dict (skip if not a dict), drop `*-launch-mode` keys (not agent
  strings — would emit "malformed" warnings), `ms.find_offers`, map each op.
- `_switch_key_state() -> (key, shadowed_by)`: `key = resolve_key("settings",
  "agent_switch_superseded")`; if the user has not overridden that action, scan
  `keybinding_registry.iter_scope_bindings(...)` rows of scope `settings` and
  `shared` for another action whose effective key equals `key` **and** that the
  user overrode (`load_user_overrides()`); return its label as `shadowed_by`.
- `BINDINGS += Binding("o", "agent_switch_superseded", "Switch to newer model",
  show=False)`; `_AGENT_TAB_ACTIONS`; `check_action` returns `None` for it under a
  modal, off `tab_agent`, or when `_switch_key_state()` reports a shadow.
- `_populate_agent_tab`: compute state once. Warnings → a `[yellow]` hint label
  (markup-escaped) after the header hint. ≥1 pending offer → dim hint "N
  default(s) use a superseded model". After each marked `ConfigRow`, mount
  `Static(note, classes="superseded-note")` with CSS `.superseded-note { width:
  100%; height: auto; padding: 0 1 0 4; }`. Note text: pending
  `[#FFB86C]⚠ superseded by {agent}/{new}[/] [dim]— {o}/Enter: switch[/dim]`
  (just `Enter: switch` when shadowed); kept as above in dim. Footer hint gains
  `{o}: switch superseded` or, when shadowed, `Enter on a ⚠ row: switch ({o} is
  bound to {shadowed_by})`.
- New `SupersededSwitchScreen(GuardedModalScreen)` (own `DEFAULT_CSS`, `escape`
  → `dismiss(None)`): shows op, layer, current and target (wrapping labels);
  buttons → `dismiss("switch")` / `dismiss("pick")` / `dismiss(None)`.
- `_populate_agent_tab` also stores what it rendered:
  `self._displayed_offers[(layer, op)] = (f"{a}/{old}", f"{a}/{new}")`.
- Enter handler for agent rows (non-launch-mode): if `_supersession_state()` has
  an offer for `(layer, key)`, push `SupersededSwitchScreen` built from that
  offer, with a callback that calls `_switch_superseded(layer, key,
  expected=(shown_old, shown_new))` on `"switch"` (the exact pair the dialog
  displayed, bound at push time) or pushes the existing `AgentModelPickerScreen`
  on `"pick"`; otherwise unchanged behaviour.
- `action_agent_switch_superseded`: resolve focused row → `(layer, key)` (else
  warn "Select a model row on Agent Defaults"); `_switch_superseded(layer, key,
  expected=self._displayed_offers.get((layer, key)))` — `o` acts on what the
  note displayed; no displayed offer → the "no superseded model" warning.
- `_switch_superseded(layer, key, expected)`:
  1. `try: config_mgr.reload_codeagent()` `except (OSError, ValueError) as exc:`
     → `notify(f"Cannot read code-agent config: {exc} — nothing switched",
     severity="error")` and return (no write, no repopulate — in-memory state is
     intact). Covers either layer turning malformed after the tab opened.
  2. Recompute `_supersession_state()`; no offer → `notify("{key}: no
     superseded model in the {label} layer", severity="warning")`, repopulate,
     return.
  3. Fresh pair `(f"{a}/{old}", f"{a}/{new}") != expected` → `notify(f"{key}:
     the offer changed to {fresh_old} → {fresh_new} since it was shown —
     nothing switched; review the refreshed row", severity="warning")`,
     repopulate, return. (Catches a table/registry change that moves only the
     target while the source still matches.)
  4. `config_mgr.switch_codeagent_default(layer, key, *expected)`:
     - `unreadable` → `notify(f"Cannot read {file}: {reason} — nothing
       switched", severity="error")` and **return** — no reload, no repopulate
       (last valid in-memory state kept).
     - `switched` / `changed` → **guarded final refresh**: `try:
       reload_codeagent()` `except (OSError, ValueError) as exc:` → one
       notification that states the true outcome and the refresh failure —
       `switched`: `f"Switched {key} ({label}) to {a}/{new}, but the tab could
       not refresh: {exc} — fix the file, then press {r} to reload"`;
       `changed`: `f"{key} changed on disk — not switched; the tab could not
       refresh: {exc}"` — then return without repopulating (in-memory state
       unchanged, never half-assigned). On success: notify `switched` →
       "Switched {key} ({label}) to {a}/{new}" / `changed` → warning "{key}
       changed on disk to {current} — not switched"; `_populate_agent_tab()`;
       refocus `#agent_{proj|user}_{_safe_id(key)}_{self._repop_counter}` via
       `call_after_refresh` (guarded).

### 4. Tests

**New `tests/test_settings_superseded_models.py`** (unittest + `asyncio.run` +
`App.run_test`; fixture shaped like `tests/test_settings_project_groups_tab.py`:
tmp root with `aitasks/metadata/`, chdir, `keybinding_registry._reset_for_tests()`
+ `refresh_label_case()`; `settings_app.SUPERSESSION_TABLE` patched to a fixture
table `claudecode: opus5 → opus5_5`; `models_claudecode.json` with `opus5`,
`opus5_5`, `custom1`; `settings_app.commit_metadata` patched with a recorder
returning a fake `committed` result — the seam `ConfigManager._commit` calls). No
`@work` workers on this tab. Cases:

- render: project `pick: claudecode/opus5` → note under the `pick` row;
  `explain: claudecode/custom1` → none.
- **narrow render**: at `size=(80, 40)` with project
  `brainstorm-module_decomposer: claudecode/opus5`, the composited screen
  (`"\n".join(s.text for s in app.screen._compositor.render_strips())`) contains
  `superseded by claudecode/opus5_5`; negative control in the same test: the
  `ConfigRow`'s own rendered strip line does not contain the target (proves the
  separate line is what makes it visible).
- `o` on the project row → project file holds `opus5_5`; local file **bytes**
  unchanged (written with non-canonical formatting first); recorder called once
  with the project path.
- `o` on a local-layer marked row with the project file pre-dirtied (edited
  bytes) → only the local file changes; project bytes unchanged; recorder **not**
  called.
- freshness: after display, (a) external edit sets `pick` to `claudecode/custom1`
  → `o` writes nothing; (b) external edit changes an unrelated op → `o` switches
  `pick` and the unrelated edit survives.
- offer changed while the dialog is open: Enter → modal shows `opus5_5`; then
  rewrite the fixture table to `opus5 → opus5_6` and add `opus5_6` to the
  registry; press "switch" → file still `opus5`, warning names `opus5_6`, the
  row's note now shows `opus5_6`. Same check for `o` after a table change
  without repopulate.
- reload error: after display, write invalid JSON into the **local** file, press
  `o` on the **project** row → project file bytes unchanged, error
  notification, app still running; same with the project file malformed.
- malformed **after** the initial reload (wrap the instance's
  `config_mgr.switch_codeagent_default` so it corrupts a file and then calls the
  original): (a) the switched layer is corrupted → result `unreadable`, file not
  rewritten beyond the corruption, error notification says nothing switched,
  no exception, `reload_codeagent` not called afterwards (spy); (b) the
  **opposite** layer is corrupted → the switch lands on disk, the final refresh
  fails, one notification says "Switched … but the tab could not refresh",
  app still running, in-memory `codeagent_*` dicts equal their pre-refresh
  values.
- `o` on a non-superseded row / `(inherits project)` row → no file change; `o`
  after `b` (board tab) → no change.
- shortcut clash: userconfig `shortcuts: {settings: {switch_tab_board: o}}` →
  on Agent Defaults, focused marked row, `o` switches to the Board tab and
  writes nothing; back on the tab, Enter → modal → "switch" → file switched;
  hint line names Enter.
- Enter modal: "pick" opens `AgentModelPickerScreen`; Escape changes nothing.
- malformed table (invalid JSON) and malformed `models_claudecode.json` → tab
  populates, warning label present, no note.
- kept: `git init` the tmp root, write
  `.git/ait-codeagent-supersession-kept.json` → note shows `(kept`; after a
  switch the kept file bytes are unchanged.

**`tests/test_model_supersession.py`**: unit tests for `load_registries`
(skips `.local.json`, warns on invalid JSON), `load_kept` (`None` → `{}`,
malformed entries warned), `kept_path` outside git → `None`.

### 5. Website

- `website/content/docs/tuis/settings/_index.md`: in **Agent Defaults (a)**, a
  short paragraph on the `⚠ superseded by …` note (pending vs kept), Enter's
  switch dialog and **o** (focused row's layer only; a project switch is
  committed, a per-user one is not), and a relref to the `ait codeagent`
  command page for `check-superseded`; add **o** to the key table.
- `reference.md`: add **o** row; mention Enter's switch dialog on marked rows.
- `how-to.md`: short "Switch a superseded default" how-to.
- Do **not** edit `website/content/docs/commands/codeagent.md` (another
  session's uncommitted changes).
- `cd website && python3 check_links.py --build`.

## Verification

- `python3 tests/test_settings_superseded_models.py`
- `python3 tests/test_model_supersession.py` (CLI output unchanged)
- `python3 tests/test_settings_commit_on_save.py`,
  `tests/test_settings_project_groups_tab.py`, `tests/test_shortcut_scopes.py`,
  `tests/test_settings_shortcuts_tab.py`
- `bash tests/run_all_python_tests.sh` — last-line verdict, `set -o pipefail`.
- `cd website && python3 check_links.py --build`.

## Post-implementation

Step 9 of task-workflow: code commit `feature: … (t1921)` path-scoped, plan via
`aitask_task_commit.sh`, gates run, archive.

## Risk

### Code-health risk: low
- Moving `_load_registries` / `_load_kept` / `_git_common_dir` into the lib could change the CLI's warning text or kept-file handling · severity: low · → mitigation: none (existing `tests/test_model_supersession.py` CLI cases pin output; wrappers keep the exact strings)
- The shadow check reads registry internals through `iter_scope_bindings` / `load_user_overrides`; a later registry change could silently stop detecting a clash · severity: low · → mitigation: none (the clash test pins it)

### Goal-achievement risk: low
- The dimmed `(kept)` rendering is a design choice the task left open; a user may prefer kept offers hidden · severity: low · → mitigation: none (one-line change if review disagrees)
- The live repo config has no superseded defaults, so the note is only observable through the test fixture · severity: low · → mitigation: none (render-level and narrow-width cases cover it)

## Post-Review Changes

### Change Request 1 (2026-10-09 10:30)
- **Requested by user:** (1) malformed `models_claudecode.json` must not crash Settings — restore the standard-provider test; (2) switch-dialog buttons overflowed the dialog at 80 columns; (3) a write failure in the switch raised out of the App; (4) git common-dir discovery ran on every offer check.
- **Changes made:** `ConfigManager.load_all` skips an unreadable/invalid model registry (the tab's warning names it); `SupersededSwitchScreen` stacks full-width buttons in a `Vertical`; `switch_codeagent_default` returns `("write_failed", reason)` on `OSError`, reported as "may not have been saved" and followed by a guarded refresh from disk; the keep-memory location is discovered once per app (`_kept_memory_path`) while the file is still re-read each check. Tests: standard-provider malformed registry, dialog composited at 80×40, write-failure (PermissionError), git discovery count == 1 with a kept file written after display picked up on repopulate. Each fix mutant-checked (reverting it fails its test).
- **Files affected:** `.aitask-scripts/settings/settings_app.py`, `tests/test_settings_superseded_models.py`

### Change Request 2 (2026-10-09 11:10)
- **Requested by user:** (1) valid-JSON but wrong-shape standard registries (`{"models": null}`) still crashed the tab; (2) the write-failure notice claimed current disk state before the refresh ran, and a failed refresh was silent; (3) the refresh-failure hint recommended `r`, whose full reload crashes with DuplicateIds (pre-existing, on HEAD) — track separately.
- **Changes made:** `ConfigManager.load_all` keeps a registry only when `models` is a list and filters it to dict entries; `write_failed` is now reported once, after the guarded refresh — "now shows what is on disk" only when the refresh succeeded, otherwise "could not refresh … the display still shows the last config it could read"; refresh-failure hints say "fix the file, then reopen Settings" instead of naming `r`. Tests: wrong-shape registry (null models, non-dict entries) incl. the Models tab; write failure with a corrupted opposite layer; refresh-failure message no longer names `r`. Mutant-checked.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`, `tests/test_settings_superseded_models.py`

## Final Implementation Notes
- **Actual work done:** `lib/model_supersession.py` gained the shared readers (`DEFAULT_TABLE_PATH`, `load_registries`, `KEPT_FILENAME`, `git_common_dir`, `kept_path`, `load_kept`); the CLI now wraps them with identical warnings. `ConfigManager` gained `reload_codeagent` (all-or-nothing), `save_codeagent_layer` (one layer; only project commits) and `switch_codeagent_default` (fresh read, value check, `switched`/`changed`/`unreadable`/`write_failed`). `SettingsApp` marks superseded values with a wrapping note line under the row (pending vs dimmed kept), shows warnings inline, switches via `o` (registry Binding, gated to the tab, yields to an existing user binding on the same key) or Enter → `SupersededSwitchScreen` (GuardedModalScreen, stacked buttons), always against the exact pair shown. Website settings `_index.md` / `reference.md` / `how-to.md` documented. New `tests/test_settings_superseded_models.py` (25 tests), 4 lib tests in `tests/test_model_supersession.py`, writer pin in `tests/test_metadata_writer_inventory.py`.
- **Deviations from plan:** `ConfigManager.load_all` now tolerates unreadable / wrong-shape standard model registries (review: the task's "malformed registry only warns" criterion was otherwise unmeetable); write failure handling and git-dir caching added after review (see Post-Review Changes). User-layer notes are indented under the └ row.
- **Issues encountered:** the first malformed-registry test crashed in `ConfigManager.load_all` before any new code ran — fixed in scope after review. Pressing `r` under `run_test` raises DuplicateIds — pre-existing (reproduced against HEAD's `settings_app.py`); the feature's tests repopulate the tab directly and its messages no longer recommend `r`.
- **Key decisions:** row/layer-scoped switch that never touches the other layer's file; kept memory read-only and shown dimmed; offers recomputed from disk at action time and compared against what was displayed; `AgentModelPickerScreen` unchanged; existing `d` on_key handler left as is (a `d` Binding would clash with `sc_reset` in the same registry scope). Each guard was mutant-checked (reverting it fails a test).
- **Upstream defects identified:**
  - `.aitask-scripts/settings/settings_app.py:_reload_all_configs — the r (reload all) action raises DuplicateIds for btn_profile_add_new when it repopulates the Profiles tab (async remove_children + same-id remount); reproduced on HEAD under App.run_test`
