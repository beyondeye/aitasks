---
Task: t1037_4_minimonitor_trigger_capture_wiring.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_1_*.md, aitasks/t1037/t1037_2_*.md, aitasks/t1037/t1037_3_*.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_*_*.md
Worktree: (current branch — fast profile)
Branch: (current branch)
Base branch: main
---

# Plan: Minimonitor trigger + capture wiring + auto-offer (t1037_4)

Closes the loop inside `minimonitor_app.py`. Depends on t1037_3 (modal),
t1037_2 (producer for live data), t1037_1 (parser).

## 0. Prerequisites

`monitor.concern_parser` (parser + `has_concern_block` + `build_clipboard_payload`)
and `monitor_shared.ConcernPickerModal` exist. Read `aidocs/framework/
tmux_gateway.md`, `shadow_agent.md`, `tui_conventions.md`.

## tmux gateway compliance (MANDATORY)

**Every** tmux interaction this task adds or changes MUST route through the
shared command-helper gateway — `lib/tmux_exec.py` (Python:
`self._monitor.tmux_run([...])`) or `lib/tmux_exec.sh` (shell: `ait_tmux ...`).
Never call `tmux` directly; `tests/test_no_raw_tmux.sh` enforces this and will
fail the build otherwise. This applies to all three tmux touchpoints here:
- the **`-J` capture** (add the `-J` flag to the existing gateway `capture-pane`
  call — both `aitask_shadow_capture.sh:76` (`ait_tmux capture-pane …`) and any
  in-app `self._monitor.tmux_run(["capture-pane", "-J", "-p", …])` are already
  gateway calls; just add the flag);
- the **reverse shadow-pane lookup** (read `@aitask_shadow_target` via the
  existing pane-discovery format / `tmux_run`, not a raw `tmux show-options`);
- any **pane-option / select-pane** call.
Run `bash tests/test_no_raw_tmux.sh` as part of verification.

## 1. Reverse shadow-pane lookup

The shadow pane carries `@aitask_shadow_target = <followed_pane_id>`
(`SHADOW_TARGET_OPTION`, `monitor_core.py`). minimonitor already reads this per
pane during discovery (capture format field, parts[8]). Add a helper:
`_find_shadow_pane_for(followed_pane_id) -> str | None` that scans known
panes/snapshots for the one whose `@aitask_shadow_target` == followed pane id.
(The followed agent is `_find_own_agent_snapshot()`.)

## 2. Binding + action

- Add `Binding("c", "action_pick_concerns", "Concerns", show=False)` to BINDINGS
  (~142-156; `c` is free).
- `action_pick_concerns`:
  1. `snap = self._find_own_agent_snapshot()`; warn + return if none.
  2. `shadow_pane = self._find_shadow_pane_for(snap.pane.pane_id)`; if none →
     `notify("No shadow agent running — press 'e' to launch one", warning)`.
  3. **Capture (MUST be wrap-joined):** the capture handed to `parse_concerns`
     must be `tmux capture-pane -J`-joined — the parser space-joins continuation
     lines, which corrupts raw mid-word soft-wrap (see the **capture-join
     contract** in `aidocs/framework/shadow_concern_format.md`, established by
     t1037_1). Options: (a) run
     `./.aitask-scripts/aitask_shadow_capture.sh <shadow_pane>` (reuses the
     shadow skill's cleaning) — but **verify/add `-J`** to that helper's
     `capture-pane` call, since it currently omits it (the shadow skill reads
     prose and tolerates soft-wrap; the parser does not). Changing the shared
     helper has its own blast radius — adding `-J` only improves prose reading,
     but confirm. Or (b) use a gateway `capture-pane -J -p` directly (still
     through the gateway per `test_no_raw_tmux.sh`). Pick one and justify in
     notes.
  4. `concerns = parse_concerns(text)`; if empty →
     `notify("No concerns detected on the shadow pane")` and stop.
  5. `push_screen(ConcernPickerModal(concerns, narrow=True), callback=self._on_concerns_picked)`.
- `_on_concerns_picked(selected)`: if `None`/empty → return. Else
  `payload = build_clipboard_payload(selected)`,
  `self.copy_to_clipboard(payload)`,
  `self.notify("Concerns copied to clipboard.")`.

## 3. Auto-offer (proactive)

During the refresh tick, when a shadow pane's capture newly contains a concern
block (`has_concern_block`), surface a one-line non-gating offer (toast/hint)
to press `c`. De-dupe per shadow pane by hashing the detected block so it offers
once per new block (store `last_block_hash` keyed by shadow pane id). Per
project memory the offer fires immediately when detected; the hotkey is the
backstop, not the only trigger. If continuous detection proves noisy, document
deferring to lazy hotkey-only and leave a TODO — but implement the immediate
offer if feasible.

## 4. Tests — tests/test_minimonitor_concern_action.*

- Stub the capture to return a known block; install a clipboard spy on the app.
  Drive `action_pick_concerns`: assert the modal is pushed with the parsed
  concerns; simulate confirm → payload reaches the clipboard spy with preamble +
  selected items.
- **No side effect before confirm:** clipboard spy untouched until the callback
  fires (construction-spy style).
- **No shadow pane:** action notifies and pushes nothing, writes nothing.
- `tests/test_no_raw_tmux.sh` still passes.

## 5. Verification

- Action test passes; `test_no_raw_tmux.sh` passes; `minimonitor_app.py`
  imports cleanly.
- Live end-to-end → the t1037 manual-verification sibling.

## 6. Final Implementation Notes (fill at completion)

Record the capture-path choice (script vs gateway) and shadow-pane resolution
gotchas for the parent's Final Implementation Notes.

See parent t1037 and **Step 9 (Post-Implementation)** for archival/merge.
