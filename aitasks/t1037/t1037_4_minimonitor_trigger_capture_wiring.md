---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t1037_3]
issue_type: feature
status: Implementing
labels: [aitask_monitormini, shadow, tui, clipboard]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 11:43
updated_at: 2026-06-22 10:51
---

## Context

Integration child of t1037 — wires everything together inside the minimonitor
TUI: a hotkey that captures the shadow pane bound to the followed agent, parses
its concerns (t1037_1), opens the picker modal (t1037_3), and on confirm copies
the payload to the clipboard. Plus an optional proactive auto-offer when a
fresh concerns block appears on the shadow pane.

Depends on t1037_3 (modal) and t1037_2 (producer, for live data) — and
transitively t1037_1 (parser). Read the parent t1037 first.

## Key files to modify

- `.aitask-scripts/monitor/minimonitor_app.py`
  - **Binding:** add `Binding("c", "action_pick_concerns", "Concerns",
    show=False)` to BINDINGS (lines ~142-156; `c` is currently free).
  - **Action `action_pick_concerns`:** resolve the followed agent
    (`_find_own_agent_snapshot`), then resolve the **shadow pane bound to it**
    — the pane whose `@aitask_shadow_target` (`SHADOW_TARGET_OPTION`,
    `monitor_core.py`) equals the followed pane id. minimonitor already reads
    `@aitask_shadow_target` per pane during discovery (capture format field
    parts[8]); add a reverse lookup helper (followed_pane_id -> shadow pane id).
    Degrade with a `notify(..., severity="warning")` if no shadow is running.
  - **Capture + parse:** capture the shadow pane's cleaned text and run
    `concern_parser.parse_concerns`. Prefer reusing
    `./.aitask-scripts/aitask_shadow_capture.sh <shadow_pane_id>` (parent
    constraint: "reuse the same path the shadow skill uses") via a subprocess,
    OR the existing `self._monitor.capture_pane()` + the parser's own
    cleaning — pick one and justify; the script path keeps cleaning identical
    to the shadow skill.
  - **Open modal + clipboard:** `push_screen(ConcernPickerModal(concerns,
    narrow=True), callback=...)`; in the callback build the payload via
    `build_clipboard_payload`, call `self.copy_to_clipboard(payload)`, and
    `self.notify("Concerns copied to clipboard.")`. If parse yields `[]`,
    notify "No concerns detected on the shadow pane" and do not open the modal.

## Auto-offer (optional, parent open question)

When a fresh concerns block is detected on the shadow pane during a refresh
tick, surface a one-line, non-gating offer (toast or hint) to open the picker —
keying off `has_concern_block` (t1037_1) and de-duping so it offers once per new
block (track last-seen block hash per shadow pane). Lazy (hotkey-only) is the
simpler fallback if continuous detection proves noisy; document the choice.
Per project memory, an offer must be immediate when the condition is met, with
the hotkey as the backstop — not the only trigger.

## Reference files for patterns

- Shadow wiring + `@aitask_shadow_target`: `action_launch_shadow`
  (`minimonitor_app.py` ~962-1054), `SHADOW_TARGET_OPTION` /
  `is_shadow_target` (`monitor_core.py` ~186-196), discovery filter
  (`monitor_core.py` ~954-955).
- Hotkey→modal pattern: `action_kill_own_agent` (~789-812),
  `action_pick_next_for_own` + `_on_own_next_result` (~831-894),
  `action_show_task_info` (~1100-1120).
- Clipboard: `codebrowser_app.py:147` (`self.app.copy_to_clipboard`).
- `aidocs/framework/tmux_gateway.md` — any new tmux access goes through the
  gateway (`tests/test_no_raw_tmux.sh` enforces it). `aidocs/framework/
  shadow_agent.md` — the `@aitask_shadow_target` binding semantics.
  `aidocs/framework/tui_conventions.md` — keybinding rules.

## Implementation plan

1. Add the reverse shadow-pane lookup helper (followed pane -> shadow pane via
   `@aitask_shadow_target`).
2. Add the `c` binding + `action_pick_concerns`: resolve shadow pane, capture,
   parse, guard empty, push modal, clipboard+notify on confirm.
3. Add the auto-offer (or document deferring it to lazy hotkey-only).
4. Test the real entry point (`tests/test_minimonitor_concern_action.*`):
   drive `action_pick_concerns` with a stubbed capture returning a known block
   and a clipboard spy; assert the modal opens with the parsed concerns and the
   payload reaches the clipboard. Prove no clipboard write happens before a
   confirm and no side effect when no shadow pane is found (construction-spy
   style, per project testing guidance).

## Verification steps

- New action test passes; `tests/test_no_raw_tmux.sh` still passes (gateway
  compliance).
- `python3` import/smoke of `minimonitor_app.py` (no import errors).
- Live end-to-end is covered by the t1037 manual-verification sibling.

## Notes for sibling tasks

- This closes the loop; capture any gotchas about shadow-pane resolution and
  the capture path choice for the parent's Final Implementation Notes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-22T07:51:52Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-22T07:51:54Z status=pass attempt=1 type=machine
