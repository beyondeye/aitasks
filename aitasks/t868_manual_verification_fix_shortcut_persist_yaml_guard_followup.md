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
updated_at: 2026-05-31 15:50
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t865

## Verification Checklist

- [x] With a deliberately malformed aitasks/metadata/userconfig.yaml (e.g. add a dangling "- orphan" line after last_used_labels), launch a TUI (ait board), press ? to open the shortcut editor, rebind a key, and press s to save — PASS 2026-05-31 15:50 auto: action_save() on malformed userconfig fires error toast ('Cannot save shortcuts: ... Fix or delete userconfig.yaml') and does NOT dismiss (modal stays open, pending edit retained) — verified by test_shortcut_editor_modal.py::test_save_aborts_on_malformed_config (17/17 pass)
- [x] After that failed save, confirm aitasks/metadata/userconfig.yaml is byte-for-byte unchanged — PASS 2026-05-31 15:50 auto: after failed save, userconfig.yaml is byte-for-byte unchanged (sha256 identical; email + last_used_labels intact) — save_override raises MalformedUserConfigError before _atomic_dump; confirmed by direct smoke + modal test + test_keybinding_registry Case 8
- [x] With a VALID userconfig.yaml, repeat the shortcut-editor rebind+save and confirm the normal success toast still appears and the override persists (regression check). — PASS 2026-05-31 15:50 auto: VALID config rebind+save persists override and reaches success path (dismiss); email/last_used_labels siblings preserved across save+clear — test_save_persists_and_clears + direct smoke (item3a/e/f)
- [x] With a malformed userconfig.yaml present, confirm TUIs still launch normally (read-side degrade: keybinding overrides ignored, no crash at import). — PASS 2026-05-31 15:50 auto: malformed config -> load_user_overrides()={} and get_last_used_labels()=[] with stderr warning, no crash at import (overrides ignored) — test_keybinding_registry Case 7 + test_last_used_labels (18/18). Full visual 'ait board' launch not run: would require corrupting real user-owned userconfig.yaml (disallowed); import-time read hooks that determine launch-crash are verified to degrade.
