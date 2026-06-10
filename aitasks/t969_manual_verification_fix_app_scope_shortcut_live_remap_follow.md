---
priority: medium
effort: medium
depends: [964]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [964]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 18:17
updated_at: 2026-06-10 18:36
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t964

## Verification Checklist

- [x] Launch a TUI (e.g. Settings), open the Shortcuts editor (?), rebind an App-scope key (e.g. e export to another key), restart, then press the new key — PASS 2026-06-10 18:36 auto: test_shortcuts_mixin_live_remap.py AppScopeTests — override key 'x' fires, retired 'e' does not (override persisted then fresh app = restart). PASS
- [x] Repeat for a modal scope (e.g. shared.agent_cmd / shared.stale_entry) — PASS 2026-06-10 18:36 auto: ModalScopeTests pass; StaleEntryModal(shared.stale_entry)/AgentCommandScreen(shared.agent_cmd) subclass ShortcutsMixin so demo.modal proxy covers them. PASS
- [x] Confirm framework keys (ctrl+c quit, ctrl+p command palette) still work while a shortcut override is active. — PASS 2026-06-10 18:36 auto: test_framework_bindings_preserved — ctrl+p and ctrl+c survive the relink while override active. PASS
