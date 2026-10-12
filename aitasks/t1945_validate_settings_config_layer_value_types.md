---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ait_settings]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1910
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-11 14:47
updated_at: 2026-10-12 11:26
---

## Origin

Spawned from t1938 during Step 8b review.

## Upstream defect

- `.aitask-scripts/settings/settings_app.py:2428 — a well-formed layer with a wrong-typed value (e.g. codeagent_config.json {"defaults": null}) passes ConfigManager.load_all, replaces the loaded state, and then crashes _populate_agent_tab with AttributeError ('NoneType' object has no attribute 'keys') outside the reload's error handling; pre-existing (the pre-t1938 load_all accepted it too). Validate the defaults mapping per layer before assignment, name the offending file, and add a regression that keeps the loaded state`

## Diagnostic context

t1938 made `ConfigManager.load_all()` all-or-nothing: each JSON layer is read
once via `_read_json_layer(path)` (which rejects a non-object root and raises
`ConfigReadError` naming the file), layers are merged by `_merge_layers`, and
in-memory state is replaced only after every read succeeds.
`SettingsApp._reload_all_configs()` catches `ConfigReadError`, notifies an
error naming the file, keeps the loaded config and tabs, and returns False.

That covers parser errors and non-object roots, not wrong-typed values inside a
well-formed object. A review probe after a valid boot wrote
`{"defaults": null}` to `aitasks/metadata/codeagent_config.json` and pressed
`r`: `load_all` accepted it (`deep_merge` replaces the default `{}` with `None`),
replaced the loaded code-agent state, and the following `_populate_agent_tab`
raised `AttributeError: 'NoneType' object has no attribute 'keys'`
(`project_defaults.keys()` / `local_defaults.keys()` at settings_app.py ~2428
and ~2522). That call is outside the `try` in `_reload_all_configs`, so the app
exits. The same shape issue likely applies to other fields readers assume are
mappings/lists (board `columns`, `settings`, `column_order`).

## Suggested fix

Validate the shape of the keys readers depend on (`defaults` must be a mapping
in each code-agent layer; board `columns`/`column_order` lists, `settings`
mapping) inside `_read_json_layer`'s callers in `load_all`, before assignment,
raising `ConfigReadError(path, ...)` so the existing reload handler reports the
offending file and keeps the loaded state. Add `App.run_test` regressions next
to `tests/test_settings_reload_all.py` (`ReloadMalformedConfigTest`) asserting
the app keeps running, the error names the file, and `config_mgr.codeagent` is
unchanged.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T08:26:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-12T09:37:36Z status=pass attempt=1 type=human
