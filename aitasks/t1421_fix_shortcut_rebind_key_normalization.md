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
