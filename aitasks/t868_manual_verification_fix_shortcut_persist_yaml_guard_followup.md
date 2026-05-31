---
priority: medium
effort: medium
depends: [865]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [865]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 11:16
updated_at: 2026-05-31 15:20
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t865

## Verification Checklist

- [ ] With a deliberately malformed aitasks/metadata/userconfig.yaml (e.g. add a dangling "- orphan" line after last_used_labels), launch a TUI (ait board), press ? to open the shortcut editor, rebind a key, and press s to save — confirm an error toast appears ("Cannot save shortcuts: ... Fix or delete userconfig.yaml") and the modal stays OPEN (not dismissed).
- [ ] After that failed save, confirm aitasks/metadata/userconfig.yaml is byte-for-byte unchanged — the email and last_used_labels keys are NOT erased.
- [ ] With a VALID userconfig.yaml, repeat the shortcut-editor rebind+save and confirm the normal success toast still appears and the override persists (regression check).
- [ ] With a malformed userconfig.yaml present, confirm TUIs still launch normally (read-side degrade: keybinding overrides ignored, no crash at import).
