---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Done
labels: [ait_settings, models, model_selection]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1910
implemented_with: claudecode/opus5_5
created_at: 2026-10-08 17:06
updated_at: 2026-10-09 15:26
completed_at: 2026-10-09 15:26
---

## Context

t1910 made the framework record which code-agent model supersedes which
(`.aitask-scripts/lib/model_supersessions.json`, framework-owned) and offer the
newer model for superseded defaults at the end of `ait upgrade` and on demand via
`ait codeagent check-superseded`. The Settings TUI — the main place users look at
and edit per-operation defaults — does not show this yet: an op still on
`claudecode/opus5` looks exactly like a deliberate choice. This was listed as an
out-of-scope follow-up in t1910.

## Goal

In the Settings TUI **Agent Defaults** tab, mark operations whose configured
model (project layer `codeagent_config.json` or per-user layer
`codeagent_config.local.json`) is superseded, show the model it would be
switched to, and let the user switch it from there.

## Pointers

- Reuse `.aitask-scripts/lib/model_supersession.py` — `load_table`,
  `load_registry`, `find_offers` (groups ops per superseded model and layer,
  returns warnings instead of raising), `offer_target`. Do not re-implement
  chain resolution or the "furthest registered successor" rule.
- Agent Defaults tab: `.aitask-scripts/settings/settings_app.py`
  (`_populate_agent_tab`, ~line 2223; layers loaded in `ConfigManager` as
  `codeagent_project` / `codeagent_local`, ~line 560). Writes must go through
  `ConfigManager.save_codeagent`, which commits the project layer via
  `_commit` → `lib/metadata_commit.py` (the local layer is never committed).
- Model picker: `.aitask-scripts/lib/agent_model_picker.py`
  (`AgentModelPickerScreen`) — consider also marking superseded models there.
- The CLI's "keep" memory lives in
  `<git-common-dir>/ait-codeagent-supersession-kept.json` (see
  `aitask_model_supersession.py::_load_kept`). Decide in planning whether the
  TUI shows kept offers differently (e.g. dimmed) or ignores the memory; a TUI
  marker is informational, so it must not silently write that file.
- Read `aidocs/framework/tui_conventions.md` (key bindings go through the
  shortcut registry; commit-on-save rules) and
  `aidocs/framework/testing_conventions.md` (`App.run_test` + `@work` workers).

## Verification

- `App.run_test` test: a project layer with `pick: claudecode/opus5` and a
  registry containing `opus5_5` shows the superseded marker and target on the
  `pick` row; a custom non-superseded value shows none; switching updates the
  file and goes through the existing commit seam.
- A malformed table / registry does not break the tab (warnings only).
- Website: update `website/content/docs/tuis/settings/` for the new marker and
  action; run `python3 check_links.py --build` in `website/`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-09T08:11:31Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-09T12:24:43Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-09T12:26:50Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f23a95ab1232578d

> **✅ gate:risk_evaluated** run=2026-10-09T12:26:50Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1921/risk_evaluated_2026-10-09T12:26:50Z-risk_evaluated-a1.log`
