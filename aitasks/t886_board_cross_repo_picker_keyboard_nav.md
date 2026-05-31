---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui, upstream_defect_followup]
created_at: 2026-05-31 18:45
updated_at: 2026-05-31 18:45
---

The cross-repo reference picker on the `ait board` TUI
(`CrossRepoRefPickerScreen`, `.aitask-scripts/board/aitask_board.py:1893`)
is keyboard-navigable only to its first (auto-focused) item. With two or
more cross-repo references on a task, the 2nd+ entries and the Cancel
button are reachable only by mouse.

## Root cause

The board registers `Binding("tab", "focus_search", priority=True)` (and
`Binding("escape", "focus_board", priority=True)`) at the App level
(`aitask_board.py:3577-3578`). Because these are `priority=True`, Textual
checks them before the focused widget — and they still fire while a
`ModalScreen` (the picker) is on the screen stack. So pressing **Tab**
inside the picker moves focus to the board's search input instead of
cycling to the next `CrossRepoRefItem`. Arrow keys don't help either: the
picker items are plain focusable `Static` widgets with no arrow
focus-movement, and `check_action` already disables board card-nav
(`nav_up/down/left/right`) over modals — but it does NOT disable
`focus_search` / `focus_board`.

## Repro

1. Create a task with two cross-repo refs (e.g. `xdeps: [1]` +
   `xdeprepo: <projB>` plus a `<projC>#1` body notation), open `ait board`.
2. Focus the card, press `#` to open the picker (shows ≥2 refs + Cancel).
3. Press Tab — focus jumps to the board search input; the picker's 2nd
   ref / Cancel never receive focus. Only the first ref is selectable via
   Enter; Escape is the only keyboard way out.

## Suggested fix

In `BoardApp.check_action` (`aitask_board.py:3634`), return `False` for
`focus_search` and `focus_board` when `len(self.screen_stack) > 1`,
mirroring the existing `nav_*` guard at `:3641` — so Tab/Escape fall
through to the active modal. Alternatively, give
`CrossRepoRefPickerScreen` explicit `up`/`down`/`tab` bindings (or replace
the focusable-`Static` list with an `OptionList`/`ListView`) so it owns
its own item navigation.

## Provenance

Found during manual-verification task t832_9 while driving the t832_8
board cross-repo features in a live tmux session. Items 35/36 of t832_9
still passed (verified via the first picker item and the single-ref
direct-open path). See
`aiplans/p832/p832_9_manual_verification_auto.md` ("Upstream defects
identified").
