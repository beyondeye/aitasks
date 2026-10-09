---
priority: medium
effort: low
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
created_at: 2026-10-09 15:56
updated_at: 2026-10-09 16:11
---

## Origin

Spawned from t1930 during Step 8b review.

## Upstream defect

- `.aitask-scripts/settings/settings_app.py:4527 — action_reload_configs/_reload_all_configs does not catch config_mgr.load_all() errors; pressing r with a malformed codeagent_config.json crashes the Settings TUI with an uncaught JSONDecodeError`

## Diagnostic context

t1930 fixed the `DuplicateIds` crash on `r` (reload all), which needed a project with no execution profiles. t1921 had changed its refresh-failure message to say "fix the file, then reopen Settings" instead of pointing at `r`, and t1930 checked whether `r` could be recommended again. A scratch `App.run_test` script booted Settings with a valid `aitasks/metadata/codeagent_config.json`, overwrote the file with `{not json`, and pressed `r`. `_reload_all_configs` calls `self.config_mgr.load_all()` → `load_layered_config(...)`, which raises `JSONDecodeError`. `action_reload_configs` catches nothing, so the app exits (`app.is_running` is False). So t1930 left t1921's "reopen Settings" message unchanged.

`ConfigManager.reload_codeagent()` (settings_app.py ~662) already shows the all-or-nothing pattern: it reads every layer before assigning, raises OSError / ValueError, and leaves in-memory state untouched for the caller to report.

## Suggested fix

Make `load_all()` all-or-nothing (or catch `(OSError, ValueError)` in `action_reload_configs`): notify an error naming the unreadable file and keep the current in-memory config and tabs. Add an `App.run_test` regression next to `tests/test_settings_reload_all.py`. Once `r` survives a malformed file, t1921's "fix the file, then reopen Settings" message (settings_app.py ~2843, pinned by `tests/test_settings_superseded_models.py:576` asserting "press r" is absent) could point at `r` instead.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-09T13:11:41Z status=pass attempt=1 type=human
