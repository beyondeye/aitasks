---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, textual, shortcuts]
gates: [risk_evaluated]
anchor: 1418
followup_kind: upstream_defect
created_at: 2026-08-05 10:49
updated_at: 2026-08-13 23:07
---

## Origin

Spawned from t1418 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/shortcuts_mixin.py:117-131` — `_relink_live_bindings` removes the default key with `mapping.get(old_key)` using the *raw* binding key, but Textual stores the live keymap under the normalized key name (`?` → `question_mark`, `#` → `number_sign`). For any punctuation/special key the removal silently no-ops: the override key is added while the default stays live, so the old key keeps firing after a rebind (defeating the method's stated purpose) and the footer keeps displaying the old key. Plain-letter rebinds are unaffected.
- `.aitask-scripts/board/aitask_board.py:6470-6478` — at startup in a real terminal the search `Input` takes focus, and a focused `Input` consumes printable characters, so Textual drops every single-character binding from `active_bindings`. The board's footer therefore shows only 4 non-printable movement keys (`shift+↑/↓`, `^↑/^↓`) until the user presses Escape. Pre-existing, but it means the footer is nearly empty on the screen the user first sees.

## Diagnostic context

Both were surfaced while verifying t1418's multi-row footer in a real tmux terminal.

**Defect 1** was found while testing that the `+N more (<key>)` overflow affordance
follows a user remap of the shortcuts editor. Injecting a `shared`-scope override of
`open_shortcuts_editor` to `f2` produced a live keymap containing **both** entries:

```
app._bindings.key_to_bindings -> ['question_mark', 'f2']  # both live
```

`register_app_bindings` correctly substituted the key (`app.BINDINGS` carried `f2`),
so the defect is isolated to the `_relink_live_bindings` removal step. The footer then
renders `?` because the default key is still present and sorts first. This also means
pressing the *old* key still fires the action after a rebind.

Note `?` is registered under the `shared` scope (`shortcuts_mixin.py:196`), and
`register_app_bindings` (`keybinding_registry.py:127`) deliberately does not shadow
shared actions into the app scope — so `resolve_key("board", "open_shortcuts_editor")`
returns `None`. That is correct by design and is *not* part of this defect; t1418's
widget works around it by resolving the key display from the composed binding.

**Defect 2** was found when the live board showed only 4 footer keys. Confirmed
pre-existing with a control that mounts the stock single-row `Footer` on the same
board: identical 4-key result, `focused: Input`, 236 cards rendered. So it is not
caused by the multi-row footer.

## Suggested fix

For defect 1: normalize the key before the lookup — resolve the binding key through the
same normalization Textual applies when building `key_to_bindings` (e.g. via
`textual.keys` / `Binding.parse_key`) before `mapping.get(old_key)`, and add a
regression test that rebinds a punctuation key (`?`) and asserts the default key is
**absent** from the live keymap and the new key present. A plain-letter rebind must
stay green as the control.

For defect 2: decide whether the board should leave the search box unfocused at
startup (the documented behavior — `website/content/docs/tuis/board/_index.md` says
"Both start unfocused") or focus the board area instead, so the footer is populated on
first paint. Verify in a real terminal, not only under `run_test`, since the two
disagree here.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:36Z.054b308a574acd6a4ee6addd from=t1794_9 from_verified=yes at=2026-09-22T06:09:36Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1421_fix_shortcut_rebind_key_normalization.md) cites stale line anchors: aitask_board.py:6470-6478.
