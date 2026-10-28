---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor, applink]
followup_kind: upstream_defect
created_at: 2026-10-28 23:26
updated_at: 2026-10-28 23:26
---

## Origin
Spawned from aitasks_go#t17_3 (Go tmux key translation + send-keys) during Step 8b review.
The Go port reproduces `translate_key` verbatim and fixed these at the Go send/adapter layer;
the Python monitor (desktop preview forwarding and the applink `forward_key` verb) still has them.
All three were confirmed live against a private tmux 3.8 server with a raw-mode `od` pane.

## Upstream defects
- `.aitask-scripts/monitor/monitor_core.py:3665-3680` — `send_keys` passes a keys argument ending in
  `;` bare (`send-keys -t P -l -- ;`). tmux's argv parser treats an argument ending in `;` as a command
  separator (a trailing `\;` is rewritten to `;`), so the `;` keystroke — or the trailing `;` of any
  literal text — is silently dropped: rc 0, nothing delivered.
- `.aitask-scripts/monitor/monitor_core.py:160-161` — `translate_key` turns `ctrl+<Textual name>` into
  `C-<name>` for names tmux does not know: `C-backslash`, `C-underscore`, `C-right_square_bracket`,
  `C-circumflex_accent`, `C-left_square_bracket`, `C-at`, every other `C-<punctuation name>`,
  `C-backspace`, `C-escape`, every `C-shift+…`, `C-f13`…, `C-decimal`/`C-add`/… (kitty keypad),
  `C-media_play`, `C-caps_lock`, …. tmux `send-keys` falls back to typing an unknown name as literal
  text, so e.g. ctrl+\ (byte 0x1c in a legacy terminal) types the 11 characters `C-backslash` into the
  agent pane.
- `.aitask-scripts/monitor/monitor_core.py:143-169` — Textual 8.2.7 misreadings reach the pane as junk:
  F13–F18 sent as `ESC [ 25~ … 32~` arrive as `\x19 \x1a \x1c \x1d \x1f` / Space (F13 types ^Y);
  application-keypad comma/equals/Begin (`ESC O l` / `X` / `E`) are split into `alt+shift+o` + a letter
  and type `Ol`/`OX`/`OE`; kitty keypad Begin (`CSI 57427u`) types U+E053.

## Diagnostic context
The aitasks_go fixture `keyfwd/testdata/textual_keys.json` (generator `gen_textual_keys.py`, Textual
8.2.7 + this repo's real `translate_key` loaded via ast) lists every affected sequence with Python's
result; aitasks_go `keyfwd/keyfwd_live_test.go` (`TestUnknownNamesConfirmedLive`) enumerates which
names tmux 3.8 types as text.

## Suggested fix
- `send_keys`: if `keys` ends with `;`, send `keys[:-1] + "\;"`.
- `translate_key` (or `forward_key`): map unknown names to tmux-valid ones as aitasks_go `keyfwd/fix.go`
  does — `C-<glyph>` for `@ [ \ ] ^ _ / ?`, the plain glyph for other punctuation, `C-h` for
  ctrl+backspace, `Escape` for ctrl+escape, `C-S-<Key>` for ctrl+shift on special keys, the ctrl form
  for other ctrl+shift keys — and drop (return None for) names tmux cannot express and the junk
  misreadings above.
- Also worth checking: whether the Python `run_via_control` retry can re-send a key whose control-mode
  request was written but whose reply was lost (aitasks_go fixed the Go equivalent with at-most-once
  send-keys).
