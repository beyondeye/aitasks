---
Task: t1587_manual_verification_concern_picker_edit_payload_before_copy_.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1587 — Auto-execution record (manual verification of t1582)

Autonomous strategy: each item was executed live, then this record was written
retroactively. Every item reached `pass`; nothing was deferred or skipped.

## Fixture

One isolated tmux server (`-L ait_t1587`, private `TMUX_TMPDIR`,
`AITASKS_TMUX_SOCKET` exported into every fixture process, `AITASK_SHADOW_DIR`
pointed at a scratch dir so the real rejection store was never touched):

- window `agent-pick-999999` (name chosen so `task_id_from_window_name` resolves
  a task id and `classify_pane` returns `AGENT`)
  - pane `%0` — followed "agent"
  - pane `%1` — "shadow", printing a real `===AITASK-CONCERNS===` block with a
    `Round:` header and three canonical `- [priority | region] body` markers,
    stamped `@aitask_shadow_target=%0`
  - pane `%2` — the **real `ait minimonitor`**, launched through
    `.aitask-scripts/aitask_minimonitor.sh`, re-pinned to its 40-column
    companion width
- window `mon` — the **real `ait monitor`**, launched through
  `.aitask-scripts/aitask_monitor.sh`, resized to 80x40 for item 8
- window `sink` — a `cat > file` pane used as a genuine paste target

Everything from the tmux capture inward was production code:
`aitask_shadow_capture.sh` -> `capture_shadow_text` -> `concern_parser` ->
`ConcernPickerModal` / `ConcernPayloadEditModal` -> `apply_concern_pick_result`
-> `copy_to_system_clipboard`. Keys were delivered with `tmux send-keys` and
state was read back with `tmux capture-pane`, `tmux show-buffer` and
`tmux paste-buffer`.

**Substitution, stated plainly:** the followed agent and its shadow were fixture
panes, not a live coding-agent CLI and a live `aitask-shadow` companion. The
concern block was hand-written in the exact form a shadow emits. What the
checklist called out as missing — a synthetic host `App` instead of a real
capture -> parse -> forward round trip — was eliminated: the host App was the
real minimonitor / monitor, and the block was read off a real pane.

## Execution Log

### Item 1 — end-to-end in a live minimonitor companion pane
- Approach: TUI interaction (live tmux).
- Action: booted the fixture, `send-keys c` to the minimonitor pane.
- Output: the picker rendered "3 concern(s) · forward, reject, or spin off ·
  round 1, 17:40:00Z" with the three parsed rows and a help line naming
  `[e] edit payload`.
- Verdict: pass.

### Item 2 — editor seeded with the real outgoing payload
- Approach: TUI interaction.
- Action: `Space` on the first row, then `e`.
- Output: the editor opened *over* the still-open picker, holding
  `I have some concerns: please verify them and if valid please address in the
  plan`, a blank line, then
  `- [high | monitor_shared.py:3062 action_save] ...` — the built payload,
  byte-for-byte.
- Verdict: pass.

### Item 3 — span select, type over, save, confirm, paste (both TUIs)
- Approach: TUI interaction + a real paste.
- Action (minimonitor): six `S-Right` to select `I have`, typed
  `EDITED-BY-USER`, `ctrl+s`, `Enter`.
- Action (full monitor): `End`, four `S-Left`, typed `MONITOR-EDIT`, `ctrl+s`,
  `Enter`.
- Output: `tmux show-buffer` returned the edited text in both cases, and the
  toast read "Edited payload copied to clipboard." (the edited-path wording).
  A second minimonitor round produced `PASTE-CHECK ...` and
  `tmux paste-buffer` into the sink pane wrote exactly that text to disk.
- Verdict: pass.

### Item 4 — `e` with nothing ticked
- Approach: TUI interaction.
- Action: `e` on a picker with no forwarded rows.
- Output: no editor; toast "Nothing marked for forwarding — press Space on a
  row first". The picker stayed open and unchanged.
- Verdict: pass.

### Item 5 — empty buffer refused, Esc still cancels
- Approach: TUI interaction.
- Action: `e`, `F7` (TextArea `select_all`), `BSpace`, `ctrl+s`, then `Esc`.
- Output: the editor stayed open showing "Editor is empty — nothing to copy.
  Esc to cancel, or type a payload."; `Esc` then returned to the picker with the
  row still ticked.
- Verdict: pass.

### Item 6 — edit invalidated by a later selection change
- Approach: TUI interaction.
- Action: `e`, typed `STALE-EDIT `, `ctrl+s`, `Down`, `Space` (second row now
  forwarded), `Enter`.
- Output: two toasts — "Selection changed after editing — copied the regenerated
  payload, your edit was discarded." and "Concerns copied to clipboard." (the
  *unedited* wording). `show-buffer` held the regenerated two-concern payload
  with no `STALE-EDIT`.
- Verdict: pass.

### Item 7 — rejection store gets the original marker text
- Approach: TUI interaction + file inspection.
- Action: one run that both edited the payload (`MANGLED-PAYLOAD-` prefix) and
  rejected the third concern with `r`, then `Enter`; then `c` + `R` on the next
  round.
- Output: clipboard held the mangled edit; `<store>/999999/rejected.md` held
  `- [low | tests/test_concern_picker_modal.py] The narrow-tier drift guard
  duplicates the CSS literal.` — identical to the source block line — and the
  `R` view rendered that same line.
- Verdict: pass.

### Item 8 — mouse Save / Cancel at 80 columns
- Approach: TUI interaction with injected SGR mouse sequences
  (`ESC [ <0;col;row M` / `m`) into the pane, with the monitor window resized to
  80x40.
- Action: located `Save` at column 25 and `Cancel` at column 42 on row 33, then
  clicked each.
- Output: clicking `Save` on an edited buffer dismissed to the intact picker and
  `Enter` copied the edit ("Edited payload copied to clipboard."); clicking
  `Save` on an *emptied* buffer reproduced the same refusal toast and kept the
  editor open; clicking `Cancel` dismissed with no override, and the following
  `Enter` copied the canonical payload with the "Concerns copied to clipboard."
  wording.
- Verdict: pass.

## Cleanup

- `tmux -L ait_t1587 kill-server` (all fixture panes, both TUIs, the sink).
- Removed the private tmux tmpdir `/tmp/claude-1000/t1587tmux`.
- The scratch rejection store lived under the session scratchpad only; the
  repository's `.aitask-shadow/` was never written.
- No repository file was modified by the fixture.
