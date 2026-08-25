---
priority: medium
effort: medium
depends: [1609]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1609]
anchor: 1605
followup_kind: manual_verification
created_at: 2026-08-25 22:18
updated_at: 2026-08-25 22:18
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1609

## Verification Checklist

- [ ] In `ait settings` -> Project Config, set `verify_build` to a multi-word command starting with `[` (e.g. `[ -f Makefile ] && echo ok`), save, and confirm the on-disk project_config.yaml holds it as a PyYAML single-quoted BLOCK item. This TUI -> PyYAML -> reader boundary is the production trigger named in p1609's Context and the one path no fixture-level test crosses.
- [ ] With that saved config, run the build_verified gate against a real task (`ait gates run <id>`) and confirm it PASSES rather than recording exit 127 "command not found".
- [ ] Set `verify_build` to a genuinely unparseable command (`for x in`) with `gate_command_exit_contract: [verify_build]`, run the gate, and confirm it records status=fail with result "malformed verify_build command (cannot parse)" -- NOT status=skip.
- [ ] Confirm the revised website/content/docs/tuis/settings/how-to.md guidance matches what the TUI actually accepts: both flow-style and block list forms work, and the comma caveat applies only to inline-list items (a scalar `"pytest -k 'a,b'"` is read whole).
