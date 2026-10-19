---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t1231_3]
issue_type: documentation
status: Implementing
labels: [verification, ait_settings]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: verification_failure
implemented_with: claudecode/opus5_5
created_at: 2026-10-19 16:37
updated_at: 2026-10-19 16:52
---

## Failed verification item from t1231_3

> [t1231_3] Confirm the settings reference tables now match the live TUI — every tab, every key, including the previously-missing Shortcuts row.

### Observed (t1231_4 autonomous verification, 2026-10-19)

`website/content/docs/tuis/settings/reference.md` matches the live TUI on the
**Tabs** table (nine tabs, same order and keys — the Shortcuts row is present)
and on the **Global** table, but its **Within Tabs** table omits keys the live
TUI binds and shows on screen:

- **Profiles tab** — `w` / `v` / `x` (Save / Revert / Delete profile; the
  buttons render `(W) Save`, `Re(V)ert`, `(X) Delete` and the hint reads
  `w/v/x: save/revert/delete`), and `Tab` (switch pane, also in that hint).
  None of them appear in any settings page.
- **Shortcuts tab** — `d` (Reset scope) and `l` (Lint coherence) are described
  only in `_index.md` ("Two buttons act on the table"), not in the reference
  table.

Source of truth: the `BINDINGS` list of `SettingsApp` in
`.aitask-scripts/settings/settings_app.py` (the `profile_*` and `sc_*`
bindings, tab-gated by `check_action`) and each tab's on-screen hint line.
Run `python3 check_links.py --build` in `website/` after the edit.

### Source

- **Manual-verification task:** `aitasks/t1231/t1231_4_manual_verification_configurable_git_branch_artifact_backend.md` (item #20)
- **Origin feature task:** t1231_3
- **Origin archived plan:** `aiplans/archived/p1231/p1231_3_artifact_documentation.md`

### Commits that introduced the failing behavior

- a8a32dffc documentation: Document ait artifact, its backends and the Artifacts settings tab (t1231_3)

### Files touched by those commits

- aidocs/unified_artifact_design.md
- seed/project_config.yaml
- tests/test_website_doc_lists.sh
- website/content/docs/commands/artifact.md
- website/content/docs/commands/_index.md
- website/content/docs/concepts/artifacts.md
- website/content/docs/concepts/attachments.md
- website/content/docs/concepts/git-branching-model.md
- website/content/docs/concepts/implementation-trails.md
- website/content/docs/concepts/_index.md
- website/content/docs/development/task-format.md
- website/content/docs/skills/aitask-trail.md
- website/content/docs/tuis/settings/how-to.md
- website/content/docs/tuis/settings/_index.md
- website/content/docs/tuis/settings/reference.md
- website/content/docs/workflows/implementation-trails.md

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1231_4 item #20.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-19T13:52:31Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-19T14:02:45Z status=pass attempt=1 type=human
