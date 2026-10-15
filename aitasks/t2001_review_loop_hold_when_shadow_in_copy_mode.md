---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [shadow, aitask_monitormini, review_loop, tmux]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-15 09:36
updated_at: 2026-10-15 09:40
---

The minimonitor auto-recheck loop (`L`) auto-disarms with
`text_not_in_composer` whenever the shadow pane is in a **tmux mode** (in
practice copy-mode, entered by scrolling the inline Codex/Claude shadow back with
the mouse wheel). The recheck prompt never reaches the shadow agent, and the
keystrokes are instead executed as copy-mode commands.

## Symptom (reported live, 2026-10-15)

Window `agent-pick-1991`: followed agent `claude` (`%765`), shadow `codex`
0.162.1 (`%771`, 60x61, inline), minimonitor `%766`. The user armed `L` to
refresh stale concerns. The loop showed ARMED, then "delivering…", then
disarmed with "the recheck prompt is not in the shadow composer — nothing was
submitted". After the user scrolled the codex pane to the bottom, the next
re-arm delivered fine.

`~/.config/aitasks/review_loop_events/` (t1606 durable record) shows the same
signature 4 times today, all with `rounds_fired: 0` and `state: delivering`:

```
2026-10-15T06:16:23 disarm text_not_in_composer codex agent-pick-1997
2026-10-15T06:19:14 disarm text_not_in_composer codex agent-pick-1991
2026-10-15T06:19:53 disarm text_not_in_composer codex agent-pick-1991
2026-10-15T06:28:47 disarm text_not_in_composer codex agent-pick-1991   <- recorded repro
```

## Root cause (confirmed)

1. With `mouse on`, a wheel-up over an inline pane (Codex has been launched
   with `tui.alternate_screen=never` since t1900/t1902, and Claude Code is
   inline too) enters **tmux copy-mode**.
2. `capture-pane` (`capture_raw_tail`, `monitor_core.py:676`) reads the pane's
   **underlying** screen, not the copy-mode view. So `shadow_state` correctly
   reports READY for the agent, and the loop fires.
3. `monitor.send_keys(shadow_pane, prompt, literal=True)`
   (`minimonitor_app.py:4674`) sends the text to the **pane's active mode**, not
   the application. tmux runs each character as a copy-mode key binding, so
   nothing reaches codex. `send-keys` still returns rc 0 when a client is
   attached.
4. `_submit_shadow_prompt` (`minimonitor_app.py:4679`) runs its pre-Enter
   capture after the 0.5s drain. The capture still reads READY, the composer is
   empty, and the fatal `DISARM_TEXT_NOT_IN_COMPOSER` fires
   (`minimonitor_app.py:4772`).

### Evidence

- **Live recording.** A read-only sampler polled `capture-pane -p -e -t %771
  -S -15` every 40ms from arm to disarm. It recorded exactly **one** distinct
  capture (READY) between 09:27:27 and the logged disarm at 09:28:47: the screen
  never changed, so the write never reached codex.
- **Scratch repro** on a private socket (`tmux -L aitprobe_cm -f /dev/null`,
  `mode-keys vi`, pane running `cat`):
  - after `copy-mode` + `send-keys -l -- "<recheck prompt>"`: the underlying
    screen is unchanged, `#{pane_in_mode}` stays `1`, `#{selection_present}`
    becomes `1`, and `:` errors with "no current client" (it is bound to the
    goto-line `command-prompt`);
  - control: after `send-keys -X cancel`, the same `send-keys -l` lands in the
    app.
- **Not reproduced outside copy-mode.** A fresh codex 0.162.1 at 60x61 reads
  the typed prompt as BUSY at t+0.1…4.0s, so neither the wrap nor the timing
  is the cause.
- **Probably t1606's original mystery.** t1606 described the report as
  "auto-disarms almost immediately after arming … re-arming right away usually
  works", with a codex shadow, and "never reproducible synthetically". This is
  the same mechanism.

### Side effects of the swallowed keystrokes

These are worse than a lost prompt. With `mode-keys vi`, the prompt's
characters run copy-mode bindings: cursor motion, `space` = begin-selection,
`v` = rectangle toggle, `:` = goto-line `command-prompt`, which opens on the
user's attached client. The current prompt wordings
(`compose_recheck_prompt`, `review_loop.py:1296`) happen to contain no `q`,
`y` or Enter. A `q` would exit copy-mode mid-write and leak a partial prompt
into the agent. An Enter in vi copy-mode is copy-pipe-and-cancel: it copies the
selection to the buffer or clipboard, exits the mode, and does not submit.

## Fix

**Guard at the execution boundary: never send keys into a pane that is in a
mode.**

1. **Pane-mode query through the gateway.** Read `#{pane_in_mode}` for the
   shadow pane (`monitor.tmux_run_async`), either with a `display-message -p -t
   <pane>` helper next to `capture_raw_tail` or as one more field in
   `shadow_query_args()` / `match_shadow_pane_info` (decide at planning; the
   second option changes a parsed format and its tests). `pane_in_mode` covers
   every mode that swallows `send-keys`: copy, view, tree, clock, buffer, etc.
   - A failed query must **fail closed**. It authorises an action, so it
     follows the `HOLD_PRE_ENTER_UNREADABLE` precedent: hold, never write.
2. **Before the literal write** in `_fire_shadow_recheck`
   (`minimonitor_app.py:4610`, after the fresh-capture and settle-latch checks,
   immediately before `send_keys`): if the pane is in a mode, return
   `("not_ready", HOLD_SHADOW_IN_MODE)` and do **not** write.
   - Add the new non-fatal code to `review_loop.py` (HOLD_* block around
     `:117`).
   - Add a `LOOP_REASON_MESSAGES` entry that is true of exactly this condition.
   - Add a `LOOP_HOLD_BANNERS` entry within the 76-cell budget (2 rows x 38
     columns), e.g. `⟳ holding: shadow pane scrolled back — will retry`.
   - The loop stays ARMED and delivers on its own once the user leaves the
     mode.
3. **Before each Enter** in `_submit_shadow_prompt`: the user can enter
   copy-mode during the 0.5s drain between the write and the Enter. At that
   point the text IS in the composer.
   - The Enter must not be sent into a moded pane.
   - Decide at planning between a bounded wait for the mode to clear and a hold
     whose message says the text is still in the composer. With a hold, the next
     fire's readiness reads BUSY and the loop holds until the user acts, so trace
     that the hold provably releases.
4. **Never cancel the user's mode** (`send-keys -X cancel`, `copy-mode -q`):
   the user is reading the shadow.
5. **Optional diagnostic hardening.** Carry the verdict that caused
   `text_not_in_composer` (`ready` vs `working`) and the pane-mode reading into
   the `review_loop_log` record, so the next unknown cause is identifiable from
   the log alone. Today the record cannot tell these apart.
6. **Docs.** Update `aidocs/framework/shadow_agent.md`, safety-contract item 6
   (`:763`, pause on uncertainty) and/or item 9 (`:807`, verified delivery), to
   state the pane-mode precondition and why capture-based readiness cannot see
   it.

The review loop is the only unattended literal-text injector:
`applink/router.py:308`, `monitor_app.py:2849/2887` and
`minimonitor_app.py:2935` all forward a key the user just pressed. So the guard
is scoped to the loop's delivery path.

## Also in scope: tests pollute the real loop-event log

`tests/test_minimonitor_concern_action.py` redirects
`AITASKS_REVIEW_LOOP_LOG_DIR` in only one class (around `:3838`). Every other
test that drives `_loop_auto_disarm` / `_loop_hold` (e.g. `:2495`
`_loop_auto_disarm("test")`) appends into the user's real
`~/.config/aitasks/review_loop_events/`:

- session files with `session: "s"`, `window: "agent-x"`,
  `project_root: "None"`, 5101 bytes each;
- `review_loop_log.MAX_SESSION_FILES = 20` retention means each test run
  **evicts real diagnostic history**. Only 3 real events survived when this
  investigation started.

Fix: redirect the log dir for the whole module (`setUpModule` /
`tearDownModule` plus `reset_session_for_tests()`, so both the pytest and the
unittest-discover backends honour it). Check `test_minimonitor_concern_smoke.py`
and any other module reaching these paths. A test asserting that the real
default dir is untouched after the module runs would pin it.

## Tests

- Fire path with a stub monitor whose pane-mode query returns `1`:
  - zero `send_keys` calls;
  - result `not_ready` / `HOLD_SHADOW_IN_MODE`;
  - controller still armed;
  - hold banner painted;
  - hold event recorded.

  Negative control: the same fixture with `0` writes the prompt. It must fail
  on pre-fix code.
- Query failure (rc != 0): no write, hold, not disarm.
- Mode flips to `1` after the write: no Enter is sent, and the outcome matches
  the planning decision in Fix item 3.
- Recovery end to end: the mode clears and the next evidence tick delivers.
  The hold must provably release; see the "fail-safe HOLD must prove its
  release" convention.
- Banner fits 2 rows at a 40-column minimonitor (existing budget test pattern).
- Real-tmux integration on a private socket (`AITASKS_TMUX_SOCKET`, per
  `shadow_agent.md` "Drive a live pane on a private socket"): a pane in
  copy-mode receives no keys from the delivery helper, stays in copy-mode, and
  shows no started selection.

## Workaround until fixed

Before pressing `L`, scroll the shadow pane back to the bottom (wheel down to
the end, or `q` in the pane) so it leaves copy-mode.
