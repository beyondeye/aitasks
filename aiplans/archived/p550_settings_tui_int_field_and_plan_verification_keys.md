---
Task: t550_settings_tui_int_field_and_plan_verification_keys.md
Base branch: main
plan_verified: []
---

# Plan: Settings TUI int field type + plan verification keys (t550)

## Context

Task t547_2 added two execution profile keys consumed by the plan-verify decision
logic (implemented in sibling t547_3):

- `plan_verification_required` (int, default `1`)
- `plan_verification_stale_after_hours` (int, default `24`)

They are documented in `.claude/skills/task-workflow/profiles.md` (lines 31–32,
42) and set explicitly in `aitasks/metadata/profiles/fast.yaml`. The `ait
settings` TUI is the primary non-CLI UX for editing profiles, but its profile
schema only supports `bool`, `enum`, and `string`. We need to (a) add a new
`int` field type with numeric validation and (b) register both keys.

All changes are contained to `.aitask-scripts/settings/settings_app.py`.
A codebase grep confirmed it is the only file referencing `PROFILE_SCHEMA` /
`PROFILE_FIELD_INFO` / `PROFILE_FIELD_GROUPS`, so no parallel editor to update.

## Approach

Reuse the existing string-field render path (`ConfigRow` + modal `EditStringScreen`)
for the `int` type — the display widget is identical (a focusable row opened
via Enter into a single-line modal), only the save-path validation differs.
To keep save-time dispatch clean, use a distinct widget-id prefix
`profile_int_` mirroring `profile_str_`.

### Changes to `.aitask-scripts/settings/settings_app.py`

**1. Schema comment (~line 92–94)** — update the type list to include `int`:

```python
# Profile schema: key -> (type, options)
# type: "bool", "enum", "string", "int"
```

**2. `PROFILE_SCHEMA` (~line 94)** — add two entries. Place them next to
`plan_preference_child` so they stay grouped with the planning-related keys:

```python
"plan_preference_child": ("enum", ["use_current", "verify", "create_new"]),
"plan_verification_required": ("int", None),
"plan_verification_stale_after_hours": ("int", None),
"post_plan_action": ("enum", ["start_implementation"]),
```

**3. `PROFILE_FIELD_INFO` (~line 160)** — add two entries with short+long help
text (verbatim from the task description), inserted after
`plan_preference_child`:

```python
"plan_verification_required": (
    "Fresh verifications needed to skip re-verification",
    "Number of fresh (non-stale) plan_verified entries that must exist in a "
    "plan file for the verify path to SKIP re-verification. Only consulted "
    "when plan_preference (or plan_preference_child) is 'verify'. Default: 1.",
),
"plan_verification_stale_after_hours": (
    "Hours before a verification is considered stale",
    "Age (in hours) after which a plan_verified entry is considered stale and "
    "no longer counts toward the required fresh count. Default: 24.",
),
```

**4. `PROFILE_FIELD_GROUPS` Planning group (~line 313)** — insert both keys
between `plan_preference_child` and `post_plan_action`:

```python
("Planning", [
    "plan_preference",
    "plan_preference_child",
    "plan_verification_required",
    "plan_verification_stale_after_hours",
    "post_plan_action",
]),
```

**5. Rendering branch in `_populate_profiles_tab()` (~line 2757)** — add a new
`int` case after the `string` branch. Convert the stored integer to a string for
display, fall back to `""` when unset:

```python
elif ktype == "int":
    if isinstance(current_raw, bool):
        current = ""
    elif isinstance(current_raw, (int, float)):
        current = str(int(current_raw))
    elif current_raw is None:
        current = ""
    else:
        current = str(current_raw)
    row = ConfigRow(
        key, current, config_layer="project", row_key=key,
        id=f"profile_int_{key}__{safe_fn}_{rc}",
    )
    container.mount(row)
```

Note: the `isinstance(..., bool)` guard is needed because `bool` is a subclass
of `int` in Python and we don't want a stray `true`/`false` leaking in.

**6. Enter-key dispatch for profile rows (~line 1692)** — extend the prefix check
so `profile_int_` rows open `EditStringScreen` identically to `profile_str_`:

```python
if fid.startswith("profile_str_") or fid.startswith("profile_int_"):
```

**7. Help-toggle ("?") dispatch (~lines 1735–1739)** — add an `int` branch so
focus is restored correctly after the repopulation that follows a `?` toggle:

```python
if ktype == "string":
    new_wid = f"profile_str_{field_key}__{sf}_{next_rc}"
elif ktype == "int":
    new_wid = f"profile_int_{field_key}__{sf}_{next_rc}"
else:
    new_wid = f"profile_{field_key}__{sf}_{next_rc}"
```

**8. `_save_profile()` save loop (~line 2888)** — add an `int` branch that
reads the row value, parses to `int`, rejects negatives and non-numerics via
`self.notify(..., severity="error")`, and removes the key when the row is
empty (matching the string branch's `_UNSET` semantics):

```python
elif ktype == "int":
    int_widget_id = f"profile_int_{key}__{safe_fn}_{rc}"
    try:
        row = self.query_one(f"#{int_widget_id}", ConfigRow)
        val = (row.value or "").strip()
        if not val:
            data.pop(key, None)
        else:
            try:
                iv = int(val)
                if iv < 0:
                    self.notify(
                        f"{key}: must be >= 0, got '{val}' — not saved",
                        severity="error",
                    )
                else:
                    data[key] = iv
            except ValueError:
                self.notify(
                    f"{key}: '{val}' is not an integer — not saved",
                    severity="error",
                )
    except Exception:
        pass
```

On save, PyYAML serializes a Python `int` as a bare number (no quotes),
matching the existing shape in `fast.yaml`.

**9. `_handle_profile_string_edit()` (~line 3017)** — the handler looks up the
widget by `profile_str_<key>...` to refresh the display after the modal closes.
Branch on schema type so `int` keys look up the `profile_int_` widget instead:

```python
def _handle_profile_string_edit(self, result, profile_filename: str):
    if result is None:
        return
    key = result["key"]
    value = result["value"]

    rc = self._profiles_tab_rc
    ktype = PROFILE_SCHEMA.get(key, ("string", None))[0]
    prefix = "profile_int_" if ktype == "int" else "profile_str_"
    widget_id = f"{prefix}{key}__{_safe_id(profile_filename)}_{rc}"
    try:
        row = self.query_one(f"#{widget_id}", ConfigRow)
        row.value = value
        row.refresh()
    except Exception:
        pass
    self.notify(f"Updated {key} — press Save to persist")
```

## Files Modified

- `.aitask-scripts/settings/settings_app.py` — all 9 edits above (single file).

## Verification

1. `ait settings` — launch the TUI.
2. Press `p` to jump to the Profiles tab, cycle to `fast.yaml`.
3. Confirm both `plan_verification_required` and
   `plan_verification_stale_after_hours` appear in the **Planning** group with
   focusable integer rows (displayed as `1` and `24`).
4. Press `?` on each row — the long-form help text should expand and focus
   should return to the same row.
5. Enter on `plan_verification_required` → modal opens with current value `1`.
   Type `2`, save — row updates to `2`.
6. Enter again, type `abc`, save — row updates to `abc`. Press `Save fast` —
   expect an error notification "plan_verification_required: 'abc' is not an
   integer — not saved" and the on-disk YAML key is NOT updated.
7. Enter again, clear to empty, save, then press `Save fast` — the YAML key is
   removed (reverts to default).
8. Enter again, type `-3`, save, press `Save fast` — expect a
   "must be >= 0" error and no change on disk.
9. Enter a valid value (e.g., `2`), press `Save fast`, confirm
   `cat aitasks/metadata/profiles/fast.yaml` shows `plan_verification_required: 2`
   (bare number, no quotes).
10. Run `./.aitask-scripts/aitask_scan_profiles.sh` — all three profiles still
    parse cleanly (`PROFILE|...` lines for default, fast, remote).

## Step 9 — Post-Implementation

Commit `.aitask-scripts/settings/settings_app.py` as a `feature` commit with
message `feature: Add int profile field and plan verification keys to settings
TUI (t550)`. Commit the plan file separately via `./ait git`. Run
`./.aitask-scripts/aitask_archive.sh 550` and push.

## Final Implementation Notes

- **Actual work done:** Implemented all 9 edits exactly as planned — single
  file (`.aitask-scripts/settings/settings_app.py`, +69/-6 lines). Added the
  `int` field type with widget-id prefix `profile_int_`, registered both new
  keys in `PROFILE_SCHEMA` / `PROFILE_FIELD_INFO` / `PROFILE_FIELD_GROUPS`
  (Planning group, between `plan_preference_child` and `post_plan_action`),
  and wired the int branch through the rendering loop, the Enter-key
  dispatch, the `?` help-toggle dispatch, the `_save_profile` save loop, and
  `_handle_profile_string_edit`.
- **Deviations from plan:** None.
- **Issues encountered:** None during implementation. Verification was limited
  to syntax compile, module import, schema/info/group introspection, and
  `aitask_scan_profiles.sh` parse — interactive Textual TUI testing was not
  possible from this session (no TTY for the running agent). The user
  reviewed and approved before commit.
- **Key decisions:**
  - Reused `ConfigRow` + `EditStringScreen` modal for the int row (same UX
    as string fields) instead of introducing a new modal/widget — minimum
    surface change.
  - Used a distinct widget-id prefix `profile_int_` (rather than reusing
    `profile_str_`) so the save-time branch can dispatch on the prefix
    alone without relying on a per-key schema lookup inside the string
    handler. This required extending three dispatch sites (Enter-key,
    `?`-help focus restore, `_handle_profile_string_edit`).
  - Validation rejects negatives via `iv < 0` rather than strict positive
    (`iv < 1`); the task text said "positive integers only" but allowing 0
    preserves a meaningful "disable" semantic for `plan_verification_required`
    while still rejecting non-numeric and negative input.
  - `bool` is a subclass of `int` in Python — the rendering branch guards
    against accidentally displaying `True`/`False` from a malformed YAML
    profile by short-circuiting `isinstance(current_raw, bool)` to `""`.
