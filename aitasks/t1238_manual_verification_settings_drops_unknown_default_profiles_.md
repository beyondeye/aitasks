---
priority: medium
effort: medium
depends: [1219]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1219]
created_at: 2026-07-24 16:10
updated_at: 2026-07-24 16:10
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1219

## Verification Checklist

- [ ] Add `default_profiles.zzz_probe: fast` to aitasks/metadata/project_config.yaml, open `ait settings` -> Project tab, confirm the dim "preserved, not editable here (unrecognized skill): zzz_probe" hint renders below the skill rows and is not focusable/editable.
- [ ] With that probe key present, press Save on the Project tab, quit, and confirm `zzz_probe: fast` is still in project_config.yaml.
- [ ] Change a known skill row (e.g. pick) via the profile picker, Save, and confirm both the edited value and the unrecognized key are correct in the YAML.
- [ ] Blank a known skill row, Save, and confirm only that key disappeared while the unrecognized key survived.
- [ ] Hand-author a non-string key (`42: fast`) alongside a string unknown key and open the Project tab — it must render the hint listing both rather than crashing the tab.
- [ ] Remove all probe keys from project_config.yaml afterwards and confirm `ait settings` Project tab shows no unrecognized-key hint.
