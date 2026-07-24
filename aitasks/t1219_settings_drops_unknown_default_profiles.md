---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_settings, execution_profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-07-22 18:47
updated_at: 2026-07-24 12:11
---

## Origin

Spawned from t635_36 during Step 8b review.

## Upstream defect

- `.aitask-scripts/settings/settings_app.py:233-236,2517-2527` — `default_profiles`
  keys absent from `VALID_PROFILE_SKILLS` are **silently dropped** whenever
  project settings are saved.

`save_project_settings()` rebuilds the entire `default_profiles` block from the
rendered `ConfigRow` widgets:

```python
dp = {}
for row in rows:
    if not row.id or not row.id.startswith("project_dp_"):
        continue
    ...
data["default_profiles"] = dp
```

and those rows are generated only for `sorted(VALID_PROFILE_SKILLS)`:

```python
VALID_PROFILE_SKILLS = {
    "pick", "fold", "review", "pr-import", "revert",
    "explore", "pickrem", "pickweb", "qa",
}
```

So any `default_profiles` entry the schema does not know about is discarded on
the next save — no warning, no diff shown, no error. The user's hand-authored
YAML is rewritten without it.

## Diagnostic context

Found while retiring the pickn/task-workflown staging experiment (t635_36).
`aitasks/metadata/project_config.yaml` carried `default_profiles.pickn: fast`,
which `aitask_skill_resolve_profile.sh` read correctly at runtime, but `pickn`
was never added to `VALID_PROFILE_SKILLS` when the sandbox was created (t928).
The key was therefore live-but-doomed: functional until anyone opened
`ait settings`, saved the project tab, and silently lost it.

t635_36 removed the `pickn` key as part of the retirement, so the specific
instance is gone. **The defect is generic and remains** — it applies to any
future skill whose profile key is added to the YAML before (or without) the
schema, and to any user who hand-edits `project_config.yaml`.

Note the asymmetry that makes this easy to miss: the *reader*
(`aitask_skill_resolve_profile.sh`, which greps the YAML directly) accepts any
key, while the *writer* (the settings TUI) accepts only the allow-list. The two
disagree, and the writer wins destructively.

## Suggested fix

Preserve unknown keys instead of dropping them: seed `dp` from the existing
`self.config_mgr.project_config.get("default_profiles")` and let the rendered
rows overwrite only the keys they represent, rather than starting from `{}`.
Optionally surface unknown keys as read-only rows so they are visible in the TUI.

A regression test should assert that a `default_profiles` entry not in
`VALID_PROFILE_SKILLS` survives a collect → save → load round-trip — the same
shape as `tests/test_profile_editor_rendered_gates.py`.

Consider auditing the other `PROJECT_CONFIG_SCHEMA`-driven blocks in
`save_project_settings()` for the same rebuild-from-rows pattern; this footgun
is likely not unique to `default_profiles`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-24T09:11:33Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-24T13:06:40Z status=pass attempt=1 type=human
