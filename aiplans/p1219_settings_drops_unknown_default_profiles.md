---
Task: t1219_settings_drops_unknown_default_profiles.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t1219 — Settings TUI silently drops unknown `default_profiles` keys

## Context

`aitasks/metadata/project_config.yaml` carries a `default_profiles:` block
mapping skill names to execution-profile names. Two pieces of code read/write
that block, and they **disagree**:

- **Reader** — `.aitask-scripts/aitask_skill_resolve_profile.sh:33-60`
  (`_extract_default_profile`) greps the YAML with awk and accepts **any** key
  under `default_profiles:`.
- **Writer** — `.aitask-scripts/settings/settings_app.py:2517-2528`
  (`SettingsApp.save_project_settings`) rebuilds the whole block **from
  scratch** (`dp = {}`) out of the rendered `ConfigRow` widgets, and those rows
  are generated only for `sorted(VALID_PROFILE_SKILLS)`
  (`settings_app.py:234-237`, rendered at `:2467-2474`).

So any `default_profiles` key the schema does not know about is discarded the
next time anyone opens `ait settings` and saves the Project tab — no warning,
no diff, no error. The writer wins, destructively. This was found in t635_36:
`default_profiles.pickn: fast` was live-but-doomed because `pickn` was never
added to `VALID_PROFILE_SKILLS`. That specific key is gone, but the defect is
generic: it hits any future skill whose profile key lands in the YAML before
(or without) the schema, and any user who hand-edits the file.

**Intended outcome:** saving the Project Config tab never loses a
`default_profiles` key it does not recognize, and the user can see that such
keys exist.

### Audit of the sibling save paths (task asked for this)

- **Top-level `PROJECT_CONFIG_SCHEMA` keys** — `save_project_settings` starts
  from `data = dict(self.config_mgr.project_config)` (`:2515`), so unknown
  *top-level* keys already survive. Only the nested `default_profiles` sub-dict
  is rebuilt from `{}`. **Not affected.**
- **`save_tmux_settings`** (`:2911-2923`) already uses the seed-then-update
  shape this fix adopts (`existing_tmux = dict(data.get("tmux") or {})`;
  `existing_tmux.update(tmux_data)`). **Not affected** by the drop bug. It does
  have an unrelated inverse quirk (clearing one known tmux key while another
  stays set leaves the cleared key's old value in place, because `update()`
  never removes) — recorded as an upstream defect, not fixed here.
- **`userconfig.yaml` `default_profiles`** — the settings TUI does not edit it
  (no widget path); out of scope.

## Requirements

1. A `default_profiles` key absent from `VALID_PROFILE_SKILLS` survives a
   render → edit → save → load round-trip through the real TUI save path.
2. Clearing a *known* skill row still removes that key (existing contract must
   not regress).
3. An empty resulting map still removes `default_profiles` entirely (existing
   contract must not regress).
4. Unknown keys are visible in the Project Config tab, read-only.

## Implementation

### 1. Preserve unknown keys on save — `.aitask-scripts/settings/settings_app.py`

In `SettingsApp.save_project_settings()` (`:2517-2528`), seed the map from the
existing config instead of `{}`, and make a cleared known row an explicit
removal:

```python
        # Collect default_profiles from individual skill rows. Seed from the
        # existing config so keys with no rendered row (skills absent from
        # VALID_PROFILE_SKILLS — hand-authored YAML, or a skill whose profile
        # key landed before the schema knew it) are preserved rather than
        # silently dropped. The rendered rows overwrite only their own keys.
        existing_dp = self.config_mgr.project_config.get("default_profiles")
        dp = dict(existing_dp) if isinstance(existing_dp, dict) else {}
        for row in rows:
            if not row.id or not row.id.startswith("project_dp_"):
                continue
            val = (row.raw_value or "").strip()
            if val:
                dp[row.row_key] = val
            else:
                dp.pop(row.row_key, None)
        if dp:
            data["default_profiles"] = dp
        else:
            data.pop("default_profiles", None)
```

Notes on the details that matter:
- `dict(existing_dp)` **copies**: `data = dict(self.config_mgr.project_config)`
  at `:2515` is shallow, so mutating the fetched sub-dict in place would also
  mutate the loaded config object.
- `isinstance(...)` guard mirrors the same guard already used when rendering
  (`:2454-2456`) — malformed YAML can put a non-dict there.
- The `else: dp.pop(...)` branch is what keeps requirement 2 true once the map
  is pre-seeded; without it, clearing a known row would leave its old value.
- `save_yaml_config` uses `sort_keys=False` (`lib/config_utils.py:167-172`), so
  preserved keys keep their original position and newly-set keys append.

### 2. Surface unknown keys read-only — `_populate_project_tab()` (`:2457-2475`)

After the `for skill in sorted(VALID_PROFILE_SKILLS)` loop and before
`continue`, mount a plain informational `Label` (no `ConfigRow`, no widget id)
when unknown keys are present:

```python
                unknown = sorted(set(dp_values) - VALID_PROFILE_SKILLS)
                if unknown:
                    container.mount(Label(
                        "      [dim]preserved, not editable here (unrecognized "
                        f"skill): {escape(', '.join(unknown))}[/dim]",
                        classes="section-hint",
                    ))
```

Add `from rich.markup import escape` to the imports (the same import is already
used in `.aitask-scripts/board/aitask_board.py:16` and
`.aitask-scripts/monitor/monitor_shared.py:37`).

**Why a `Label` and not a `ConfigRow`:** `_safe_id()` (`:314-316`) only maps
`.`, ` `, `-` → `_`, so rendering arbitrary YAML keys as widgets is unsafe —
an unknown key `pr_import` would collide with known `pr-import`'s widget id
(Textual `DuplicateIds`), and a key containing `/` or `:` would be an invalid
id. Either would crash the whole Project tab. A `Label` carries no id and is
inherently read-only, which is exactly what the task asked for.

### 3. Update the schema help text — `PROJECT_CONFIG_SCHEMA["default_profiles"]` (`:224-231`)

Extend `detail` to state that unrecognized keys are shown but not editable here
and are preserved on save, so the TUI's own help matches the new behavior.

### 4. Regression test — `tests/test_settings_default_profiles_unknown_keys.py` (new)

Modelled on `tests/test_settings_learn_skill_guide.py` (same `_Fixture` shape:
`tempfile` repo root, `os.chdir`, `keybinding_registry._reset_for_tests()`,
`refresh_label_case()`, `SettingsApp().run_test()`), because that file already
proves the **real** user-facing save path rather than a proxy.

Seed `project_config.yaml` with a known and an unknown key:

```yaml
default_profiles:
  pick: fast
  someskill_not_in_schema: fast
```

Cases:
1. `test_unknown_key_survives_save` — mount the app, call
   `app.save_project_settings()` with rows untouched, reload the YAML: both
   `pick` and `someskill_not_in_schema` are still present.
   **Negative control:** assert `someskill_not_in_schema` is not in
   `VALID_PROFILE_SKILLS` so the test proves the unknown-key path, not a
   silently-widened allow-list.
2. `test_editing_a_known_row_preserves_unknown` — set the `pick` row's
   `raw_value` to `default`, save, reload: `pick == "default"` **and** the
   unknown key still present.
3. `test_clearing_a_known_row_still_removes_it` — blank the `pick` row, save,
   reload: `pick` gone, unknown key still present, `default_profiles` still
   present (requirement 2 not regressed by the seeding).
4. `test_all_keys_cleared_removes_the_block` — start from a config whose
   `default_profiles` holds **only** known keys, blank every rendered row,
   save: `default_profiles` absent from the YAML entirely (requirement 3).
5. `test_unknown_key_is_visible_in_the_tab` — assert some `Label` under
   `#project_content` renders text containing `someskill_not_in_schema`
   (render-level check, not a model check).

## Verification

```bash
# 1. New regression test — must pass.
python3 tests/test_settings_default_profiles_unknown_keys.py

# 2. Prove the harness can actually fail: temporarily revert the
#    save_project_settings() hunk (dp = {}) and re-run — cases 1/2/3 must fail
#    and the process must exit non-zero. Restore the fix afterwards by undoing
#    that edit (do NOT `git checkout --` the file: it carries an unrelated
#    in-flight change from another session).
python3 tests/test_settings_default_profiles_unknown_keys.py; echo "exit=$?"

# 3. Neighbouring settings tests still pass (same app, same save path).
python3 tests/test_settings_learn_skill_guide.py
python3 tests/test_settings_project_groups_tab.py
python3 tests/test_settings_shortcuts_tab.py
python3 tests/test_settings_brainstorm_descriptions.py
python3 tests/test_profile_editor_rendered_gates.py

# 4. Manual smoke (optional): add `default_profiles.zzz_probe: fast` to
#    aitasks/metadata/project_config.yaml, run `ait settings`, open the Project
#    tab (the unknown key shows as a dim read-only hint), press Save, quit, and
#    confirm `zzz_probe` is still in the YAML. Remove the probe afterwards.
```

**Staging caution:** `.aitask-scripts/settings/settings_app.py` already has an
uncommitted hunk from another session (a comment tweak in
`_populate_shortcuts_tab`, ~`:3658`). Stage this task's changes explicitly and
verify `git diff --cached` contains only my hunks before committing.

## Risk

### Code-health risk: low
- The change is three small, local edits in one file plus a new self-contained
  test; the seed-then-update shape it adopts is already the in-repo precedent
  (`save_tmux_settings`, `settings_app.py:2911-2923`), so it adds no new
  pattern. · severity: low · → mitigation: TBD
- Pre-seeding the map makes a cleared known row a *no-op* unless the explicit
  `dp.pop(row.row_key, None)` branch is present — a plausible way to break the
  existing "blank clears the key" contract. · severity: medium ·
  → mitigation: TBD (covered by test case 3)

### Goal-achievement risk: low
- Requirement coverage is direct: the reported defect is exactly "rebuild from
  `{}` drops unrecognized keys", and the fix seeds from the live config. The
  reader/writer asymmetry was verified in source, not assumed. · severity: low
  · → mitigation: TBD
- The read-only visibility surface is a `Label`, so it is asserted at render
  level rather than through a widget model; a future refactor of the hint
  labels could silently drop it without failing anything else. · severity: low
  · → mitigation: TBD (covered by test case 5)

## Post-Review Changes

### Change Request 1 (2026-07-24 11:05)

- **Requested by user:** The unknown-key hint assumes every YAML mapping key is
  a string. `sorted(set(dp_values) - VALID_PROFILE_SKILLS)` raises `TypeError`
  for a config holding both an unquoted numeric key (`42:`, parsed as `int`)
  and a string unknown key; a lone numeric key sorts fine but then reaches
  `', '.join(unknown)` and raises there. Opening the Project Config tab would
  crash instead of preserving and showing hand-authored unknown entries.
  Normalize keys for display/sorting only, keep the original mapping for save,
  and add a regression case. Disposition: blocking.

- **Verified:** Valid, both failure modes reproduced. One mechanism
  correction: the *set difference* is safe (`{42, 'x'} - {'pick'}` needs no
  ordering) — `sorted()` raises on the mixed case and `join()` on the
  lone-numeric case. The crash outcome is as described. Reachable from plain
  hand-authored YAML: `42:` → `int`, `true:` → `bool`, `null:` → `None`, all of
  which `aitask_skill_resolve_profile.sh` still greps successfully.

- **Changes made:** `_populate_project_tab()` now builds the hint with
  `sorted(str(k) for k in dp_values if k not in VALID_PROFILE_SKILLS)` — the
  membership test is type-safe for any hashable key, and `str()` is applied
  for **display only**, so `dp_values` (and therefore the mapping seeded into
  `save_project_settings`) keeps each key's original YAML type. Two regression
  classes added to the test file: `NonStringKeyTests` (mixed `int` + `str`
  unknown keys — asserts the hint lists both **and** that `dp[42] == "fast"`
  survives the save with its int type intact) and `LoneNonStringKeyTests` (the
  join-only path). Both were confirmed to fail with the exact reported
  `TypeError`s before the fix and to pass after.

- **Files affected:** `.aitask-scripts/settings/settings_app.py`,
  `tests/test_settings_default_profiles_unknown_keys.py` (now 9 tests).

- **Not changed (recorded as an upstream defect instead):** a non-string
  *value* for a **known** key (`pick: 42`) crashes the save with
  `AttributeError: 'int' object has no attribute 'strip'`. Confirmed
  pre-existing by re-running the probe with this task's changes stashed —
  it fails identically. Out of scope for the key-side concern raised here.

## Step 9 (Post-Implementation)

Standard: merge approval (working on current branch — no worktree to merge or
clean up), run `./ait gates run 1219` for the declared `risk_evaluated` gate,
then `./.aitask-scripts/aitask_archive.sh 1219` and push.
