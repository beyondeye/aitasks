---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_settings, execution_profiles]
gates: [risk_evaluated]
anchor: 1219
created_at: 2026-07-24 16:09
updated_at: 2026-07-24 16:09
---

## Origin

Spawned from t1219 during Step 8b review.

## Upstream defect

- `.aitask-scripts/settings/settings_app.py:2530-2545` — a non-string *value*
  for a *known* `default_profiles` key (e.g. `pick: 42`, valid YAML) makes
  `save_project_settings()` raise `AttributeError: 'int' object has no
  attribute 'strip'` at `(row.raw_value or "").strip()`, because
  `_populate_project_tab` passes `raw_value=profile_name` uncoerced. Confirmed
  pre-existing by re-running the probe with t1219's changes stashed.
- `.aitask-scripts/settings/settings_app.py:2925-2937` — `save_tmux_settings()`
  merges with `existing_tmux.update(tmux_data)`, and a cleared key is simply
  absent from `tmux_data` rather than removed. So blanking one tmux setting
  while another remains set silently retains the cleared key's old value; the
  key is only dropped when *every* tmux row is blank. Inverse of the
  `default_profiles` bug fixed in t1219, in the sibling save path.

## Diagnostic context

t1219 fixed the *key* side of the Project Config tab's `default_profiles`
handling: `save_project_settings()` rebuilt the block from `{}`, so keys absent
from `VALID_PROFILE_SKILLS` were silently dropped. The fix seeds the map from
the live config and makes a blanked row an explicit `dp.pop()`.

Two adjacent problems were found while doing that and were deliberately left
out of t1219's scope:

1. **Value-side type assumption.** The key-side fix (`str(k)` normalization for
   display, original types retained for save) does nothing for values.
   `_populate_project_tab` passes `raw_value=profile_name` straight from the
   parsed YAML, and `ConfigRow.__init__` does not coerce
   (`.aitask-scripts/lib/profile_editor.py:483-499`). A user typo like
   `pick: 42` therefore lands an `int` in `raw_value`, and the very next save
   calls `.strip()` on it. Verified against the real `SettingsApp` in a
   temp-repo probe, both with and without t1219's changes — identical
   `AttributeError` either way, so it is genuinely pre-existing.

2. **Clear semantics in the sibling save path.** t1219's plan audited the other
   `project_config.yaml` writers. `save_tmux_settings()` was found to already
   use the correct seed-then-update shape for *preservation* (it was the
   in-repo precedent t1219 followed), but its removal path is the mirror-image
   bug: `update()` never deletes, so a key cleared in the TUI is only actually
   removed when the whole `tmux_data` map comes back empty.

Note the two defects pull in opposite directions and want the same underlying
contract: a per-key "set or clear" decision derived from the rendered rows,
with values normalized to strings at the row boundary.

## Suggested fix

For (1): coerce at the row boundary — pass `raw_value` as a string when
building `ConfigRow`s in `_populate_project_tab` (mirroring `_format_yaml_value`
usage for the `project_cfg_` rows), and/or make the collectors tolerant with
`str(row.raw_value or "").strip()`. Prefer fixing at the render site so
`raw_value` has one type everywhere.

For (2): give `save_tmux_settings()` the same explicit-removal branch t1219
added to `save_project_settings()` — track which schema keys the rendered rows
report as blank and `pop()` them from `existing_tmux`, instead of relying on
the all-empty fallback.

Regression tests should follow `tests/test_settings_default_profiles_unknown_keys.py`
(mount the real `SettingsApp`, drive the app's own save method, assert the YAML
round-trip), including a negative control that fails without the fix.
