---
priority: medium
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [codexcli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 11:29
updated_at: 2026-05-31 13:03
---

## Origin

Spawned from t866 during Step 8b review.

## Upstream defect

- `.agents/skills/codex_interactive_prereqs.md:1` — orphaned doc. No skill body,
  instruction layer, or template references it by name; it is copied into
  `.agents/skills/` only by the setup/install copy loops
  (`aitask_setup.sh:1766` and `install.sh:482`). The actual Codex plan-mode
  enforcement is the `/plan` typing in `aitask_codex_plan_invoke.py`, so this
  file enforces nothing at runtime.

## Diagnostic context

While relaxing forced plan mode for qa/explain (t866), the file was rewritten
for accuracy rather than removed, to avoid scope-creep into the install flow.
A full removal touches the install/setup copy loops and the aidocs references.

## Suggested fix

Delete `.agents/skills/codex_interactive_prereqs.md`; drop it from the
`for doc in codex_tool_mapping.md codex_interactive_prereqs.md` copy loops in
`aitask_setup.sh:1766` and `install.sh:482` (keep `codex_tool_mapping.md`,
which IS live-referenced by skill bodies); update the aidocs references in
`aidocs/adding_a_new_codeagent.md` (~lines 869, 1129). Read
`aidocs/aitasks_extension_points.md` first (touches the install flow).
