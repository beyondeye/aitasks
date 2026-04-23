---
Task: t627_ait_monitor_live_preview_refresh_stop.md
Base branch: main
plan_verified: []
---

# Plan: Fix `ait monitor` preview refresh stalling + tail-follow flicker (t627)

## Context

Two related bugs in the `ait monitor` Textual TUI's content preview pane (`.aitask-scripts/monitor/monitor_app.py`):

**Bug 1 — preview auto-refresh stops without user intent.** The 3 s tick (`set_interval` at line 588) keeps firing and the agent-list status updates correctly, but the preview content stops redrawing. The user has to switch agents, Tab into the preview, or type into the live pane to "unstick" it. The user wants the *paused* semantics (header shows `PAUSED`, no refresh) preserved — the issue is that pause activates **accidentally**, not that pause itself is wrong.

Diagnosis (verified against Textual 8.1.1 source under `/usr/lib/python3.14/site-packages/textual/`):

- `_record_preview_scroll` (`monitor_app.py:608`) is the only writer of `_preview_scroll_state`. It only fires from `PreviewScrollContainer._schedule_notify`, which only fires from the four `_on_*` overrides at lines 149–172. Those handlers cover **only user input**: mouse wheel (`_on_mouse_scroll_*`), scrollbar arrow clicks (`_on_scroll_up/_on_scroll_down`, posted from `scrollbar.py:341,346`), and scrollbar thumb drag (`_on_scroll_to`, posted from `scrollbar.py:394`).
- The render-path `scroll.scroll_end(animate=False)` at lines 999–1001 / 1008–1010 goes through Textual's private `_scroll_to` (widget.py:2864/2876), which does **not** post any `ScrollTo`/`ScrollUp`/`ScrollDown` message — so it never triggers any of the `_on_*` overrides.
- The "switch focus to preview unsticks it" path is explained by Textual's auto-scroll-into-view: focusing `PreviewPanel` causes the parent `PreviewScrollContainer` to be scrolled (via `scroll_to_widget` → posts `ScrollTo`), which fires our `_on_scroll_to`, which schedules `_record_preview_scroll`, which (assuming the panel ends up at the bottom) saves `at_bottom=True` and unpauses.

So the actual trigger for accidental pause is **the user mouse-wheeling while their cursor happens to be over the preview pane** (hover-scroll). Today the at-bottom check at line 624 is `scroll_y >= max_y - 1`, so even a single wheel notch (which scrolls by ≥1 line) pushes scroll_y below the threshold and the pane pauses. Once paused, only user-driven actions that re-fire `_record_preview_scroll` with `at_bottom=True` (or actions that change `same_pane`) resume tail-follow.

**Bug 2 — preview flickers on every 3 s refresh in tail-follow mode (when not focused on preview).** Each tick the visible content briefly scrolls up by a few lines and then snaps back to the bottom.

Diagnosis: in tail-follow mode (saved is None or `saved[0]` is True), the render does:

```python
preview.update(content)                                      # marks dirty, async layout
self.call_after_refresh(lambda: scroll.scroll_end(animate=False))
```

`scroll.scroll_end(animate=False)` internally does **another** `call_after_refresh(_lazily_scroll_end)` (widget.py:3041), so there are two deferred refresh hops between `preview.update()` and the actual `scroll_y` assignment. During those hops the viewport shows the new (longer) content at the *old* `scroll_y`, which is no longer at the bottom — hence the visible upward-then-downward flicker.

Intended outcome:

1. Casual hover-scrolling does not pause the preview. Real user scroll-up still pauses (header turns `PAUSED`, refresh stops).
2. Tail-follow refresh in PANE_LIST zone shows new content arriving at the bottom without a visible scroll-up-then-back-down jump.
3. The `PAUSED` semantic ("if paused, no refresh") is preserved verbatim. The freeze guard at line 985 is unchanged.

## Approach

Two surgical edits, each in a different region of `_update_content_preview`'s neighborhood. No changes to the freeze guard, to `PreviewScrollContainer`, to focus handling, or to the 0.3 s fast-preview path.

### Fix 1 — at-bottom dead zone (Bug 1)

Increase the at-bottom tolerance in `_record_preview_scroll` so single accidental wheel notches stay inside the "still at bottom" envelope. Change `monitor_app.py:624` from:

```python
at_bottom = max_y <= 0 or scroll_y >= max_y - 1
```

to:

```python
# Dead zone of 5 lines so an accidental hover-scroll wheel notch
# (≥1 line in Textual) doesn't pause tail-follow. A real scroll-up
# (Page Up, scrollbar drag, sustained wheel scroll) still moves
# scroll_y well past the threshold and pauses normally.
AT_BOTTOM_DEAD_ZONE = 5
at_bottom = max_y <= 0 or scroll_y >= max_y - AT_BOTTOM_DEAD_ZONE
```

`AT_BOTTOM_DEAD_ZONE` lives as a module-level constant near the top of the file (next to `PREVIEW_DEFAULT_SIZE` at the import block) so the magic number isn't buried.

Why 5: Textual's default mouse wheel sensitivity scrolls 1–3 lines per notch; 5 covers single-notch and two-notch accidents without making it noticeably harder to enter pause intentionally (Page Up scrolls a full viewport, well past 5).

This is the minimum-blast-radius fix. It does not change *what happens when paused* — pause still freezes refresh, exactly as today. It only changes *when pause activates*.

### Fix 2 — eliminate tail-follow flicker (Bug 2)

Use `immediate=True` on the two tail-follow `scroll_end` call sites so we collapse the second deferred hop. Change `monitor_app.py:999–1001`:

```python
self.call_after_refresh(
    lambda: scroll.scroll_end(animate=False)
)
```

to:

```python
self.call_after_refresh(
    lambda: scroll.scroll_end(animate=False, immediate=True)
)
```

And the same change at `monitor_app.py:1008–1010` (the anchor-rolled-off fallback that also snaps to tail).

`immediate=True` on `scroll_end` (widget.py:3038–3041) skips the inner `call_after_refresh(_lazily_scroll_end)` and runs `_lazily_scroll_end` synchronously inside our outer callback. Since our outer callback fires *after* the layout from `preview.update()` has settled, `max_scroll_y` is already the correct new value when `_lazily_scroll_end` reads it, and `_scroll_to(animate=False)` assigns `scroll_y = new max_scroll_y` in the same frame as the content render. Net: the user-visible flicker collapses from "visible 1–2 frames at old scroll_y" to "consistent at new bottom".

The anchor-restore branch (line 1014–1016) is **not** changed — it uses `scroll.scroll_to(y=anchor_idx, animate=False)` where `y=anchor_idx` is exact (not a "scroll to current max_y" closure), so the second deferral isn't needed and there's no analogous flicker. (Plus it only runs in paused state, which after Fix 1 will be a deliberate action, so a tiny extra frame of delay is harmless.)

Pause path is untouched (no `scroll_end` call when paused — the anchored-restore branch is used instead).

## Critical files to modify

- `.aitask-scripts/monitor/monitor_app.py`:
  - Add `AT_BOTTOM_DEAD_ZONE = 5` near other module constants (top of file).
  - Line 624 — replace literal `1` with `AT_BOTTOM_DEAD_ZONE`.
  - Lines 999–1001 — add `immediate=True` to `scroll_end` call.
  - Lines 1008–1010 — same `immediate=True` addition.

That is the entire diff. No new methods, no API changes, no new imports.

## What is intentionally NOT changed

- The freeze guard at line 985 (`if same_pane and (is_paused or scroll.user_is_scrolling)`). Pause-to-freeze stays exactly as today.
- The `PAUSED` header badge at line 970.
- `PreviewScrollContainer` and its `user_is_scrolling` flag. The set-synchronously-clear-after-refresh contract is preserved.
- The 0.3 s fast-preview timer (`_manage_preview_timer`, `_fast_preview_refresh`).
- Focus handling, key forwarding, auto-switch.
- `action_scroll_preview_tail` (the `t` key) — still works as the explicit "resume tail" escape hatch.

## Verification

1. **Bug 1 — hover-scroll no longer pauses casually:**
   - Open `ait monitor` with at least one streaming agent.
   - Focus an agent in the pane list (don't Tab to preview).
   - Move the mouse cursor over the preview pane and **make a single wheel notch's worth** of accidental scroll. Header should still show `LIVE`/no-pause tag, preview should keep ticking every ~3 s.
   - Now mouse-wheel deliberately several notches up (or press Page Up via scrollbar). Header should show `PAUSED`, preview should freeze (this is intended).
   - Press `t` (the existing Tail binding at line 450). Should resume.

2. **Bug 2 — no flicker in tail-follow:**
   - Same setup, focus on agent in pane list (preview at bottom, `LIVE`).
   - Watch the preview for 30 s. Each 3 s refresh should show new content arriving at the bottom without any visible upward jump. Before the fix, the visible content briefly scrolls up ~5–10 lines and then snaps back; after the fix, no jump.
   - Pick an agent with high output rate (e.g., `watch -n 0.5 date`) to make the flicker most visible.

3. **Pause behavior unchanged:**
   - In preview zone (`PAUSED`), wait 30 s. No content refresh, scroll position stays exactly where the user put it. (Same as before fix.)

4. **Preview-zone live mode unchanged:**
   - Tab into preview zone. 0.3 s fast-preview timer should run as today, content updates every 0.3 s with no flicker (this path uses scroll_end with immediate=True after the fix, but the fast cadence already masked any flicker pre-fix).

5. **Static check:**
   ```bash
   python3 -c "import ast; ast.parse(open('.aitask-scripts/monitor/monitor_app.py').read())"
   ```
   No monitor-specific tests under `tests/` to run.

## Step 9 (Post-Implementation)

Standard task-workflow archival. Commit message: `bug: Fix ait monitor preview pause activation + tail-follow flicker (t627)`. Update plan file with Final Implementation Notes. Run `./.aitask-scripts/aitask_archive.sh 627`, then `./ait git push`.
