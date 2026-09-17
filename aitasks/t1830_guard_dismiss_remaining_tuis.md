---
priority: medium
effort: high
depends: []
issue_type: bug
status: Ready
labels: [tui, textual, modal_dismiss]
gates: [risk_evaluated]
anchor: 1816
followup_kind: risk_mitigation
created_at: 2026-09-17 12:57
updated_at: 2026-09-17 12:57
---

## Origin

Risk-mitigation ("after") follow-up for t1816, created at Step 8d after implementation landed.

## Risk addressed

code-health: the other TUIs' ~314 dismiss sites stay unguarded.

- The ~314 sites in other TUIs remain unguarded after this task, so the convention is enforced only in brainstorm · severity: low · → mitigation: guard_dismiss_remaining_tuis

## Goal

Convert board/monitor/settings/syncer/chatlink/other TUI screens to `lib/guarded_dismiss.GuardedModalScreen` and extend the AST enforcement test to their directories.

t1816 introduced `.aitask-scripts/lib/guarded_dismiss.py` (`GuardedDismissMixin`, `GuardedModalScreen`). Textual 8.2.7's `Screen.dismiss` calls `app.pop_screen()`, which pops whatever screen is on top. A stale key still dispatched to a closed modal therefore pops the screen beneath it, and with only one screen left it raises `ScreenStackError`, which kills the TUI. t1816 converted every brainstorm screen, `lib/section_viewer.SectionViewerScreen`, and the whole `diffviewer/` package, replacing `DiffViewerScreen.action_back`'s direct `app.pop_screen()` with `self.dismiss()`. The rule is documented in `aidocs/framework/tui_conventions.md` ("Modal dismissal: subclass `GuardedModalScreen`, never bare `ModalScreen`").

Scope:
- Switch every `ModalScreen` / `Screen` subclass in `board/aitask_board.py` (~89 dismiss sites), `monitor/monitor_shared.py` (~40), `settings/settings_app.py` (~37), `chatlink/wizard.py` (~16), `syncer/upgrade_screens.py` (~15), `syncer/settings_screens.py` (~11), and every other TUI to `GuardedModalScreen`, or to `GuardedDismissMixin, Screen` for a non-modal base.
- Convert the shared `lib/` screens as well, including those reached through app-level mixins from any TUI: `TuiSwitcherOverlay`, `ShortcutEditorModal`, `StaleEntryModal`, `_RepointInputScreen`, `AgentCommandScreen`, `AgentModelPickerScreen`, `LaunchModePickerScreen`, `KeyCaptureScreen`, `EditStringScreen`, `ProfileEditScreen`, `SyncConflictScreen`. `KeyCaptureScreen` / `ShortcutEditorModal` use `ModalScreen[T]` generics, so check that `GuardedModalScreen` subscripting still works (or add a generic alias).
- Replace every direct `app.pop_screen()` / `self.app.pop_screen()` that closes the calling screen with `self.dismiss()`.
- Extend `_screen_source_files()` in `tests/test_brainstorm_guarded_dismiss.py` (or move the enforcement into a repo-wide test) so it covers every TUI directory and `lib/`. It checks for unguarded screen bases and for direct `pop_screen` calls.
- Audit each converted screen for a dismiss issued while a child screen is legitimately on top (worker/timer/`call_later` paths). Under the guard that dismiss becomes a logged no-op. Result callbacks are safe because Textual runs them via `call_next` after the child pops.
- Coordinate with t1450 (board modal Escape result loss), which owns the dismiss-result rule in the same doc.
