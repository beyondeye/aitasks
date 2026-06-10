---
task: 969
type: manual_verification
strategy: autonomous
verifies: [964]
created_at: 2026-06-10 18:30
---

# Auto-Verification Execution — t969 (verifies t964)

t964 fixed a framework-wide bug where a per-TUI key rebind reached
`self.BINDINGS` (registry / footer hint / tab title) but NOT Textual's
*live* keymap, so pressing the new key did nothing. The fix
(`ShortcutsMixin._relink_live_bindings`) moves each remapped binding onto its
override key in `self._bindings` after `super().__init__()` copies the
default-key map.

The interactive checklist (open editor, rebind, restart, press the new key)
is verified here via `tests/test_shortcuts_mixin_live_remap.py`, which is a
faithful automated proxy: it persists the override to disk, then constructs a
*fresh* app instance (equivalent to a restart reading persisted config) and
asserts behaviour with real Textual `pilot` key-presses — not just
`self.BINDINGS` inspection.

## Execution Log

### Item 1 — App-scope rebind fires new key, retires old (restart)
- Item text: Launch a TUI (e.g. Settings), open the Shortcuts editor (?),
  rebind an App-scope key (e.g. `e` export to another key), restart, then
  press the new key — confirm the action fires and the old key no longer does.
- Approach: CLI invocation — run `python3 tests/test_shortcuts_mixin_live_remap.py`.
- Action run: `python3 tests/test_shortcuts_mixin_live_remap.py`
- Output (trimmed): `Ran 6 tests in 0.472s / OK`. Relevant tests:
  `AppScopeTests.test_override_key_fires_and_default_retired` (presses override
  `x` → action fires; presses retired default `e` → does not fire) and
  `test_live_keymap_keys_reflect_override` (`x` in live keymap, `e` absent).
  The override is saved via `shortcut_persist.save_override` then a fresh
  `_DemoApp()` is built — the persisted-then-reinit path models the restart.
- Verdict: pass

### Item 2 — Modal-scope rebind fires inside the modal
- Item text: Repeat for a modal scope (e.g. shared.agent_cmd /
  shared.stale_entry) — confirm the rebound key fires inside the modal.
- Approach: CLI invocation + source confirmation.
- Action run: `python3 tests/test_shortcuts_mixin_live_remap.py` (ModalScopeTests)
  plus `grep` of `_shortcuts_scope` / `ShortcutsMixin` usage.
- Output (trimmed): `ModalScopeTests.test_modal_override_key_fires_and_default_retired`
  and `test_modal_live_keymap_keys_reflect_override` pass via a modal pushed by
  a host app. Confirmed the named modals subclass the mixin:
  `stale_entry_modal.py:88 class StaleEntryModal(ShortcutsMixin, ModalScreen)`
  scope `shared.stale_entry`; `agent_command_screen.py:132 class
  AgentCommandScreen(ShortcutsMixin, ModalScreen)` scope `shared.agent_cmd`.
  Both register through the same `ShortcutsMixin` code path the test exercises.
- Verdict: pass

### Item 3 — Framework keys survive an active override
- Item text: Confirm framework keys (ctrl+c quit, ctrl+p command palette)
  still work while a shortcut override is active.
- Approach: CLI invocation.
- Action run: `python3 tests/test_shortcuts_mixin_live_remap.py`
  (`AppScopeTests.test_framework_bindings_preserved`).
- Output (trimmed): asserts `ctrl+p` and `ctrl+c` remain in
  `app._bindings.key_to_bindings` while a `demo` override is active — the
  relink moves only the remapped action, leaving framework bindings in the
  shared map intact.
- Verdict: pass

## Cleanup

None — no scratch files or tmux sessions were created. Verification ran the
existing test suite directly (the tests use their own `tempfile` workspace,
self-cleaned in `tearDown`).
