---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_settings]
gates: [risk_evaluated]
anchor: 1910
followup_kind: upstream_defect
created_at: 2026-10-09 15:25
updated_at: 2026-10-09 15:25
---

## Origin

Spawned from t1921 during Step 8b review.

## Upstream defect

- `.aitask-scripts/settings/settings_app.py:_reload_all_configs` — the `r` (reload all) action raises `DuplicateIds` for `btn_profile_add_new` when it repopulates the Profiles tab (async `remove_children` + same-id remount); reproduced on HEAD under `App.run_test`.

## Diagnostic context

While testing t1921 (superseded model defaults on the Agent Defaults tab), a test pressed `r` after writing a keep-memory file to force a repopulate. Settings crashed with:

```
textual._node_list.DuplicateIds: Tried to insert a widget with ID 'btn_profile_add_new', but a widget already exists with that ID
```

The same crash reproduces with the committed (pre-t1921) `settings_app.py` loaded in a minimal fixture (`aitasks/metadata/` with `userconfig.yaml` + `codeagent_config.json`), `SettingsApp().run_test(size=(140, 60))`, `pilot.press("r")`. `_reload_all_configs` repopulates every tab back to back; `_populate_profiles_tab` remounts fixed-id widgets (e.g. `btn_profile_add_new`) before the previous children's async removal completes. Other tabs avoid this with the `_repop_counter` id suffix.

t1921 stopped recommending `r` in its refresh-failure messages ("fix the file, then reopen Settings"); once `r` works, those messages could point at it again.

## Suggested fix

Give the Profiles tab's fixed-id widgets the `_repop_counter` suffix (or `await` the `remove_children()` before remounting), then add an `App.run_test` regression test that presses `r` and asserts the app keeps running and every tab repopulates. Verify in a real terminal as well.
