---
Task: t553_scrolling_does_not_detach_from_tail_in_monitor.md
Base branch: main
plan_verified: []
---

# Freeze monitor preview while scrolled up (t553)

## Context

Task t532 added per-pane scroll memory for the `ait monitor` preview, and
t548 replaced the distance-from-bottom anchor with a content-line anchor so
the saved position survived tmux's rolling capture window. Together they
fixed "jumps to tail on pane switch" and made the first-scroll survive one
refresh tick.

What they did **not** fix: while the user is scrolled up on an **active**
agent pane, each 0.3 s / 3 s refresh still calls `preview.update(content)`
and re-runs the anchor restore path. The user observes the scroll position
drifting by a few lines as new output arrives — lines they're reading move
out from under the viewport.

Two concrete causes identified:

1. **Layout clamp + anchor re-assertion on every tick.** `preview.update()`
   triggers a Textual re-layout that can clamp `scroll_y`. The restore logic
   re-fires via `call_after_refresh(scroll_to(y=target_idx))`, which on
   success holds the anchor line at the top — but if the anchor rolls off
   the top of the capture buffer (`_locate_anchor` returns `None`), the code
   snaps to tail. Anchors at blank lines or duplicate boilerplate can also
   relocate to a different occurrence, shifting the view.
2. **Race between the user scroll event and the deferred
   `_record_preview_scroll` callback.** In the single refresh frame where
   the user first scrolls up from tail, `_update_content_preview` can run
   before the `call_after_refresh` callback commits state. It still sees
   `(True, None)` and calls `scroll_end`, undoing the scroll.

User feedback (confirmed via AskUserQuestion): **freeze the preview content
entirely while the user is detached from tail.** No new lines appear, no
drift, no flicker. A `PAUSED` badge replaces the `LIVE` badge in the header.
Updates resume when the user re-attaches (scrolls to the tail, presses `t`,
or switches away and comes back).

## Target file

- `.aitask-scripts/monitor/monitor_app.py` (single file — all edits here)

## Design

Freeze = don't call `preview.update(content)` for the focused pane while
its saved scroll state is `(False, ...)` (detached). Content for the
focused pane is effectively pinned to whatever was last rendered; the
user's scroll_y is not disturbed because layout does not recompute.

On **pane switch** (different `_focused_pane_id` than `_last_preview_pane_id`)
we still do the full update + anchor restore, so returning to a
previously-detached pane shows fresh content with the anchor restored to
the top of the viewport. This preserves the t548 behaviour.

On **re-attach** (`_record_preview_scroll` detects `at_bottom=True` after a
`(False, ...)` previous state, or `action_scroll_preview_tail` runs) we
fire a one-shot `call_later(self._fast_preview_refresh)` so the preview
immediately catches up to the latest capture before tail-following
resumes.

A new `user_is_scrolling` flag on `PreviewScrollContainer` closes the
race: the flag is set inside each `_on_*` handler **before** `super()`,
and cleared inside `_record_preview_scroll` once the new state is
committed. `_update_content_preview` skips content + scroll restoration
whenever `same_pane AND (is_paused OR scroll.user_is_scrolling)`, so an
in-flight scroll is never fought by a concurrent refresh tick.

A new `_preview_rendered_lines: list[str]` attribute tracks the lines
currently displayed in the preview (set whenever `preview.update()` is
called). `_record_preview_scroll` reads its anchor from this list instead
of `self._snapshots[focused_pane_id]` — otherwise the anchor_text would
mix rendered-view coordinates (`int(scroll_y)`) with live-snapshot
coordinates, and any skipped-update tick would produce a bogus anchor.

## Changes

### 1. `PreviewScrollContainer` — add `user_is_scrolling` flag (lines 123–157)

Add a class-level flag and set it at the start of every `_on_*` handler,
before delegating to `super()`. No change to the `_schedule_notify` logic.

```python
class PreviewScrollContainer(ScrollableContainer):
    """ScrollableContainer that reports user-driven scroll changes.
    ...
    """

    on_user_scroll: Callable[[], None] | None = None
    # Set synchronously inside each _on_* handler; cleared by
    # _record_preview_scroll after the deferred state update commits.
    # Read by _update_content_preview to skip content updates + scroll
    # restoration on the same frame as a user scroll event, avoiding a
    # race where the refresh tick would undo the user's scroll.
    user_is_scrolling: bool = False

    def _on_mouse_scroll_up(self, event) -> None:
        self.user_is_scrolling = True
        super()._on_mouse_scroll_up(event)
        self._schedule_notify()

    def _on_mouse_scroll_down(self, event) -> None:
        self.user_is_scrolling = True
        super()._on_mouse_scroll_down(event)
        self._schedule_notify()

    def _on_scroll_up(self, event) -> None:
        self.user_is_scrolling = True
        super()._on_scroll_up(event)
        self._schedule_notify()

    def _on_scroll_down(self, event) -> None:
        self.user_is_scrolling = True
        super()._on_scroll_down(event)
        self._schedule_notify()

    def _on_scroll_to(self, message) -> None:
        self.user_is_scrolling = True
        super()._on_scroll_to(message)
        self._schedule_notify()

    def _schedule_notify(self) -> None:
        if self.on_user_scroll is not None:
            self.call_after_refresh(self.on_user_scroll)
```

### 2. `MonitorApp.__init__` — add `_preview_rendered_lines` (near line 413)

```python
# Lines last passed to preview.update() for the focused pane. Used by
# _record_preview_scroll to resolve int(scroll_y) to anchor_text without
# mixing rendered-view coordinates with live-snapshot coordinates.
self._preview_rendered_lines: list[str] = []
```

### 3. `_record_preview_scroll` (lines 530–554)

- Read `anchor_text` from `self._preview_rendered_lines` instead of
  `self._snapshots[focused_pane_id]`.
- Detect re-attach (previous state detached, now at tail) and fire a
  one-shot fresh-content refresh.
- Clear `scroll.user_is_scrolling` once state is committed.

```python
def _record_preview_scroll(self) -> None:
    """Record user scroll intent for the focused pane.

    Called (via PreviewScrollContainer.call_after_refresh) once the user's
    mouse wheel / scrollbar drag / page click has committed scroll_y.
    Anchors by the text of the topmost visible line in the currently
    rendered content — stable against tmux's rolling capture.
    """
    if self._focused_pane_id is None:
        return
    try:
        scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
    except Exception:
        return
    max_y = scroll.max_scroll_y
    scroll_y = scroll.scroll_y
    at_bottom = max_y <= 0 or scroll_y >= max_y - 1
    anchor_text: str | None = None
    if not at_bottom:
        idx = int(scroll_y)
        if 0 <= idx < len(self._preview_rendered_lines):
            anchor_text = self._preview_rendered_lines[idx]

    prev = self._preview_scroll_state.get(self._focused_pane_id)
    was_detached = prev is not None and not prev[0]

    self._preview_scroll_state[self._focused_pane_id] = (at_bottom, anchor_text)
    scroll.user_is_scrolling = False

    # Re-attach → pull a fresh snapshot so tail-follow resumes on latest output.
    if was_detached and at_bottom:
        self.call_later(self._fast_preview_refresh)
```

### 4. `_update_content_preview` (lines 847–919) — full rewrite

Structure:

1. Guard on focused pane existing in snapshots (unchanged wording for the
   empty case, but also clear `_preview_rendered_lines`).
2. Compute `saved`, `is_paused = saved is not None and not saved[0]`,
   `same_pane = self._focused_pane_id == self._last_preview_pane_id`.
3. **Always** refresh the header — even when content is frozen — so the
   `PAUSED` / `LIVE` badge stays in sync with the current state.
4. **Frozen branch** — if `same_pane AND (is_paused OR scroll.user_is_scrolling)`,
   update `_last_preview_pane_id` and return without touching the preview
   or scroll. This is the core freeze.
5. **Active branch** — otherwise, run the existing content-update logic:
   build `lines`, `preview.update(content)`, set
   `_preview_rendered_lines = lines`, and restore scroll via
   `call_after_refresh` (anchor lookup + fallback to `scroll_end`).

```python
def _update_content_preview(self) -> None:
    try:
        preview = self.query_one("#content-preview", PreviewPanel)
        header = self.query_one("#content-header", Static)
        scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
    except Exception:
        return

    if not (self._focused_pane_id and self._focused_pane_id in self._snapshots):
        header.update("[bold]Content Preview[/]")
        preview.styles.min_width = 0
        preview.update("[dim]Focus an agent or pane to see its output[/]")
        self._preview_rendered_lines = []
        self._last_preview_pane_id = self._focused_pane_id
        return

    snap = self._snapshots[self._focused_pane_id]
    saved = self._preview_scroll_state.get(self._focused_pane_id)
    is_paused = saved is not None and not saved[0]
    same_pane = (self._focused_pane_id == self._last_preview_pane_id)

    # -- Header (always refreshed so PAUSED/LIVE badge stays current) --
    pane_label = f"({snap.pane.window_index}:{snap.pane.window_name})"
    task_id = self._task_cache.get_task_id(snap.pane.window_name)
    if task_id:
        info = self._task_cache.get_task_info(task_id)
        if info:
            if self._active_zone == Zone.PREVIEW:
                pane_label += f" [bold]t{task_id}: {info.title}[/]"
            else:
                pane_label += f" [dim italic]t{task_id}: {info.title}[/]"

    if is_paused:
        tag = " [bold yellow]PAUSED[/]"
    elif self._active_zone == Zone.PREVIEW:
        tag = " [bold green]LIVE[/]"
    else:
        tag = ""

    if self._active_zone == Zone.PREVIEW:
        header.update(f"[bold white]Content Preview[/] {pane_label}{tag}")
    else:
        header.update(f"[bold]Content Preview[/] {pane_label}{tag}")

    # -- Frozen branch: skip content + scroll updates entirely --
    # Same pane as last tick AND (user detached OR user scroll in flight):
    # do not call preview.update() (no layout recompute, no scroll clamp)
    # and do not call scroll_end/scroll_to (no fighting the user).
    if same_pane and (is_paused or scroll.user_is_scrolling):
        self._last_preview_pane_id = self._focused_pane_id
        return

    # -- Active branch: render fresh content and restore scroll --
    lines = snap.content.rstrip().splitlines()
    if lines:
        content = _ansi_to_rich_text("\n".join(lines))
        preview.styles.min_width = snap.pane.width
        preview.update(content)
        self._preview_rendered_lines = lines

        if saved is None or saved[0]:
            # Tail follow (first view of this pane or at-bottom).
            self.call_after_refresh(
                lambda: scroll.scroll_end(animate=False)
            )
        else:
            anchor_text = saved[1]
            target_idx = self._locate_anchor(lines, anchor_text)
            if target_idx is None:
                # Anchor rolled off the capture buffer — snap to tail so
                # we don't get stuck on a stale position on pane-return.
                self.call_after_refresh(
                    lambda: scroll.scroll_end(animate=False)
                )
            else:
                target_f = float(target_idx)

                def _restore(t=target_f):
                    scroll.scroll_to(y=t, animate=False)
                self.call_after_refresh(_restore)
    else:
        preview.styles.min_width = 0
        preview.update("[dim](empty)[/]")
        self._preview_rendered_lines = []

    self._last_preview_pane_id = self._focused_pane_id
```

Notes on the restructure:
- Header is built exactly once per call (split out from the two `LIVE` /
  no-`LIVE` branches in the old code). `PAUSED` supersedes `LIVE`.
- `_preview_rendered_lines` is reset on every content write (and on the
  no-focused-pane branch), never stale-held across a pane switch.
- The anchor-not-found `scroll_end` fallback is unchanged in intent but
  runs less often now — on pane switches and the first tick after the
  user re-attaches, not on every refresh.

### 5. `action_scroll_preview_tail` (lines 1152–1161)

Already sets `_preview_scroll_state[pane] = (True, None)`. Add a
`call_later(self._fast_preview_refresh)` so the re-engaged tail shows the
latest output instead of the frozen content. Also type the `query_one` as
`PreviewScrollContainer` for consistency (functionally identical).

```python
def action_scroll_preview_tail(self) -> None:
    """Jump preview to the bottom and re-engage tail-follow."""
    try:
        scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
    except Exception:
        return
    scroll.scroll_end(animate=False)
    if self._focused_pane_id is not None:
        self._preview_scroll_state[self._focused_pane_id] = (True, None)
        # Pull fresh content so tail-follow resumes on the latest output.
        self.call_later(self._fast_preview_refresh)
    self.notify("Tail follow")
```

### 6. No changes needed for

- `_refresh_data` — its stale-entry cleanup still runs and is correct.
  `_preview_rendered_lines` is tied to the currently focused pane; it
  does not need per-pane cleanup, and `_update_content_preview` resets it
  on pane switch / empty.
- `_fast_preview_refresh` — already calls `_update_content_preview`, which
  now handles the frozen branch internally.
- `_manage_preview_timer` — the 0.3 s fast-refresh timer is still
  started/stopped exactly as before; the freeze branch is what prevents
  it from disturbing a scrolled-up user.
- `action_toggle_scrollbar` — out of scope (pre-existing bug noted in
  t548 post-review).

## Verification

No unit tests exist for the monitor TUI (interactive Textual). Validation
is a manual run in a real tmux session with ≥2 agent windows producing
continuous output so the capture buffer rolls:

1. **Syntax check:**
   `python3 -c "import ast; ast.parse(open('.aitask-scripts/monitor/monitor_app.py').read())"`
2. **Freeze holds across refreshes:** Start `ait monitor`, focus an agent
   pane, mouse-wheel up ~10 lines. Watch through multiple 3 s ticks and,
   if in PREVIEW zone, multiple 0.3 s fast-refresh ticks. **Expect:** the
   preview content does NOT shift by even one line. The lines visible in
   the viewport stay byte-for-byte identical. Header shows `PAUSED` in
   yellow.
3. **Header toggles PAUSED↔LIVE:** From the frozen state, press `Tab`
   into the PREVIEW zone and back. Expect the tag stays `PAUSED` (not
   `LIVE`) because the saved state is still `(False, anchor)`.
4. **Re-attach via scroll to bottom:** From the frozen state, mouse-wheel
   down until the viewport is at tail. Expect the preview immediately
   updates with the latest content, header changes from `PAUSED` to
   `LIVE` (or no tag in PANE_LIST zone), and subsequent refreshes
   tail-follow.
5. **Re-attach via `t` key:** Repeat scenario 2 to freeze, then press
   `t`. Expect same outcome as scenario 4.
6. **Pane switch while detached:** Freeze on agent A. Arrow to agent B.
   Expect B shows latest content at tail (fresh view). Arrow back to A.
   Expect A shows its latest snapshot with the old anchor line restored
   to the top of the viewport (or snapped to tail if the anchor has
   rolled off the buffer). Header shows `PAUSED` because A's saved state
   is still `(False, anchor)` — user is expected to press `t` or scroll
   to tail to re-engage live follow.
7. **Tail follow still works when attached:** With no scroll-up action,
   watch the preview. New lines append at the bottom as agents emit
   output, viewport stays at tail, header shows `LIVE` in PREVIEW zone.
8. **Race: scroll up from tail:** While at tail, mouse-wheel up sharply.
   Expect the viewport moves up by the wheel delta and **stays** there
   — it should NOT snap back to tail on the next tick (this is the race
   that `user_is_scrolling` closes).
9. **Multi-line freeze stability:** Freeze on a pane whose agent produces
   an ANSI-colored status line every second (e.g., a progress bar).
   Expect the content under the anchor stays stable; the status line is
   NOT re-rendered into the viewport.
10. **Pane close while detached:** Freeze on agent A, then close A's
    tmux window externally. Expect the pane list drops A on the next 3 s
    refresh, `_preview_scroll_state` drops A via the existing stale
    cleanup, and the preview falls back to `"Focus an agent or pane…"`.

Manual verification only — no automated tests for the monitor TUI.

## Step 9 reference

After implementation and manual verification, follow task-workflow
Step 9 (commit + archive via `./.aitask-scripts/aitask_archive.sh 553`
+ push). No separate branch / worktree was created (profile `fast`:
`create_worktree: false`), so the merge sub-steps are skipped.

## Final Implementation Notes

- **Actual work done:** All five documented changes applied to
  `.aitask-scripts/monitor/monitor_app.py` exactly as specified in the
  Design / Changes sections:
  1. `PreviewScrollContainer` — added `user_is_scrolling: bool = False`
     class attribute with explanatory comment; set to `True` at the top
     of every `_on_*` handler before `super()`.
  2. `MonitorApp.__init__` — added `self._preview_rendered_lines: list[str] = []`
     initialization immediately after `_last_preview_pane_id`.
  3. `_record_preview_scroll` — rewritten to read anchor from
     `self._preview_rendered_lines`, capture the previous detach state,
     commit new state, clear `scroll.user_is_scrolling`, and fire
     `call_later(self._fast_preview_refresh)` on re-attach transition.
  4. `_update_content_preview` — full rewrite. Early-return empty branch
     clears `_preview_rendered_lines`. Header built once per call with
     `PAUSED` (yellow) superseding `LIVE` (green) when the saved state
     is `(False, anchor)`. Frozen branch (`same_pane AND (is_paused OR
     scroll.user_is_scrolling)`) returns before touching preview / scroll.
     Active branch renders content, stores `lines` into
     `_preview_rendered_lines`, and restores scroll via the existing
     tail-follow / anchor / snap-to-tail logic.
  5. `action_scroll_preview_tail` — `query_one` retyped to
     `PreviewScrollContainer`; `call_later(self._fast_preview_refresh)`
     fires when `_focused_pane_id` is not `None`, so tail re-engagement
     pulls a fresh snapshot instead of sitting on frozen content.
- **Deviations from plan:** None. The edits match the plan verbatim
  modulo whitespace/import context. The plan's "No changes needed for"
  section (`_refresh_data`, `_fast_preview_refresh`, `_manage_preview_timer`,
  `action_toggle_scrollbar`) was respected — those functions were not
  touched.
- **Issues encountered:** None during implementation. `ast.parse` on
  `monitor_app.py` succeeded after the edits. Pre-existing unrelated
  uncommitted changes to `.aitask-scripts/brainstorm/brainstorm_crew.py`
  and untracked `.aitask-scripts/lib/launch_modes.py` /
  `launch_modes_sh.sh` / `tests/test_launch_modes.py` were noticed and
  deliberately excluded from the t553 commit (they belong to a different
  in-progress task).
- **Key decisions:** None beyond what the plan already decided. The
  freeze-entirely-when-detached approach (as confirmed in the Context
  section of the plan) is the shipped behavior. PAUSED badge lives in
  `_update_content_preview`'s header block rather than in a separate
  reactive watcher.
- **Build verification:** `python3 -c "import ast;
  ast.parse(open('.aitask-scripts/monitor/monitor_app.py').read())"`
  passes. Project has no automated test suite for the Textual monitor
  TUI; full functional verification (scenarios 1–10) is manual in a
  real tmux session per the plan's Verification section.
