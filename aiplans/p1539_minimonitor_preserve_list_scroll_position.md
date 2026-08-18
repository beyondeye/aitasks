---
Task: t1539_minimonitor_preserve_list_scroll_position.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1539 — Preserve minimonitor's list scroll position across refresh ticks

## Context

`ait monitor --mini` rebuilds its whole agent list every status-refresh tick
(default 3 s). `MiniMonitorApp._rebuild_pane_list()`
(`.aitask-scripts/monitor/minimonitor_app.py:1406`) does
`await container.remove_children()` → `await container.mount_all(widgets)` on the
`#mini-pane-list` `VerticalScroll`, and nothing saves or restores the scroll
offset. When there are more agent cards than fit in the 40-column companion
pane, any mouse-wheel / scrollbar scroll is discarded every few seconds and the
list snaps back — which makes the list unusable exactly when it overflows.

Keyboard navigation survives only incidentally: `_refresh_data` saves
`_focused_pane_id` and `_restore_focus()` re-`.focus()`es the matching card, and
Textual scrolls a newly focused widget into view. A mouse-driven scroll moves no
focus, so it has no such carrier.

Intended outcome: a scroll position the user set with the wheel or the scrollbar
survives refresh ticks, stays pinned to the bottom when it was at the bottom, and
degrades gracefully to a nearby position when the agent it was anchored on is
killed between ticks.

### Evidence gathered during planning

- **No reusable helper exists.** Every scroll save/restore in `.aitask-scripts/`
  is app- or widget-private (`monitor_app.py` `_record_scroll_for`,
  `codebrowser/history_list.py` `_restore_window_view`,
  `brainstorm/widgets.py` `on_ratio_change`, …). `monitor_shared.py` — the module
  minimonitor already imports from — holds nothing scroll-related. This fix is
  local to `minimonitor_app.py`.
- **t1257 / t1261 landed no code.** `t1257` (the board analogue) is `Postponed`;
  `t1261` is a `manual_verification` checklist. But
  `aiplans/p1257_board_auto_refresh_refocus_discards_scroll.md` contains a
  fully-reasoned Textual-8.2.7 analysis that this plan adopts — see below.
- **Probed live at Textual 8.2.7** (headless `run_test`, 40×10):
  - `card.virtual_region.y` is the scroll-independent content offset — the right
    quantity to anchor on. `scroll_to(y=…, animate=False)` re-applies it.
  - `Widget.focus()` takes `scroll_visible: bool = True`; passing `False`
    suppresses its scroll-into-view.
  - A frame boundary between `remove_children()` and `mount_all()` drives
    `max_scroll_y` to 0, and `validate_scroll_y` clamps `scroll_y` to 0.
  - Focusing a card from an *unfocused* state while scrolled scrolls to that
    card — so `_restore_focus`'s `_auto_select_own_window()` fallback
    (`minimonitor_app.py:987`, focuses `list_cards[0]`) resets to the top on
    every tick where the previously focused pane is gone.

### Decisions taken with the user

1. **The anchor wins unconditionally during a passive refresh.** The task text
   suggested "focus restore only scrolls when the focused card would otherwise
   be off-screen"; that is a deliberate deviation, because dragging the view
   back to the focused card is precisely the reported symptom for a mouse-only
   user. Keyboard navigation and `on_app_focus` are *active* gestures and keep
   today's scroll-to-focus behaviour — the refusal below is scoped to the
   refresh window only.
2. **Verification is headless tests + a `manual_verification` follow-up.**
   `aidocs/framework/tui_conventions.md` ("Verify in a real pty — a headless pin
   may not fail") means a green `run_test` is not evidence for real-terminal
   focus/scroll behaviour, and a mouse-wheel gesture cannot be synthesised
   through tmux. So the automated tests pin the mechanism and the follow-up task
   pins the gesture.
3. **Both risk mitigations run inline**, against the recommendation to spawn the
   live-reproduction spike as a blocking "before" task (its `inline_risk` is
   `high` — its findings can reshape the plan). Consequence, accepted: the spike
   runs as this plan's pre-phase, so a surprising trace surfaces *mid*
   implementation rather than before it. That is why the pre-phase step carries
   an explicit **outcome gate** — a third mechanism stops the work for a plan
   revision instead of being absorbed silently. Nothing is created at Step 7 or
   Step 8d: both dispositions are inline, so the "before"/"after" creation parts
   find no lines. After inlining, goal-achievement risk is reassessed
   `high → medium`; code-health stays `medium`.

## Approach — refuse uninvited scrolls for the rebuild window, then re-apply the anchor

Two competing scrollers cannot be ordered out of each other's way. p1257
established from Textual source that the focus scroll cannot be out-raced:
`Widget.focus()` is asynchronous (`widget.py:4588`), `scroll_visible` ignores
`immediate=True` for an unlaid-out widget and re-posts itself through
`parent.call_after_refresh` (`widget.py:3764`), `Screen.set_focus` separately
schedules `scroll_to_center` (`screen.py:1138`), and tearing down the focused
widget makes Textual re-home focus onto a card of its own choosing — queueing
yet another deferred scroll. The number of pending scrolls is data-dependent, so
no fixed number of `call_after_refresh` hops wins.

p1257 reached for `allow_vertical_scroll` (`widget.py:576`) as the refusal seam.
That is **too blunt here**, and the difference matters: it refuses *every* scroll,
so a user gesture landing inside the rebuild window is silently dropped **and**
does not retire the pending restore — the stale anchor then wins over what the
user just did. The scrollbar thumb drag is the sharpest case, because
`_on_scroll_to` (`widget.py:4807`) gates on `_allow_scroll`, which is false the
moment `allow_vertical_scroll` is, and a `VerticalScroll` has no horizontal axis
to keep it true.

**Uninvited and user-driven scrolls have disjoint call paths**, so one override
each discriminates them exhaustively — verified by reading Textual 8.2.7 and
confirmed by probe:

- Every **uninvited** scroll reaches this container through
  `Screen.scroll_to_widget` (`widget.py:3525`), which walks the ancestor chain
  calling `container.scroll_to_region(...)` on each. That is the single funnel
  for `Widget.focus()` → `scroll_visible`, its deferred re-post for an
  unlaid-out widget, `Screen.set_focus`'s `scroll_to_center` (which is just
  `scroll_to_widget(center=True)`), the focus Textual re-homes when the focused
  card is torn down, and the `ScrollToRegion` message.
- Every **user gesture** lands in `_scroll_to` (`widget.py:2718`) without ever
  touching `scroll_to_region`: wheel → `_scroll_*_for_pointer` →
  `scroll_relative`; thumb drag → `_on_scroll_to` → `scroll_to`; trough / arrow
  click → `scroll_page_*`; scroll key bindings → `scroll_up` / `scroll_down` /
  `scroll_home` / `scroll_end`.

So: refuse **only** `scroll_to_region` for the rebuild window, treat any
non-`force` arrival at `_scroll_to` as the user superseding the pending restore,
and re-apply the captured anchor with `force=True` once the container can hold
it. `force=True` is the deliberate bypass on both methods, which is what keeps
our own restore from being mistaken for either.

Two consequences, both improvements over p1257's design: **no user gesture is
ever refused** (its accepted input-dropping cost disappears), and the retirement
hook does not depend on enumerating Textual's nine private `_on_*` scroll
handlers — a tenth would route through `_scroll_to` like the rest.

## Changes — `.aitask-scripts/monitor/minimonitor_app.py`

### Pre-phase (risk mitigations)

1. `[reproduce_scroll_reset_live]` **Reproduce the reset in a real pty before
   writing any fix.** Launch `ait monitor --mini` in a 40-column tmux pane with
   more than one screenful of agent cards. Inject a `sitecustomize.py` on
   `PYTHONPATH` (the technique `aidocs/framework/tui_conventions.md` prescribes,
   which preserves the real entry point) that traces `#mini-pane-list`'s
   `scroll_y`, `max_scroll_y` and `app.focused` at the top and bottom of every
   `_refresh_data`. Pass the env with an `env` prefix on the command —
   `tmux set-environment` does not reach a pane that is already running a shell.
   Run the probe first against a state whose behaviour is already known (a list
   that does **not** overflow, where nothing should move), so an empty trace is
   distinguishable from "nothing was reset". Then scroll with the wheel and
   record which mechanism actually fires.
   **Outcome gate:** if the trace shows either hypothesised mechanism (the
   `_auto_select_own_window` focus reset, or the `validate_scroll_y` clamp at a
   frame boundary), proceed to step 1 below unchanged. If it shows a *third*
   mechanism, stop and revise the plan before implementing — the refusal-seam
   scope may need to change — and say so rather than adapting silently.
   Keep the trace output; it is the positive control the headless tests cannot
   supply.

### 1. Pure anchor math (module level, above `MiniPaneCard`)

Two module-level functions so the logic is unit-testable without Textual:

```python
def pick_scroll_anchor(card_offsets, scroll_y):
    """(pane_id, delta) for the topmost visible card, or None.

    `card_offsets` is the pre-rebuild [(pane_id, virtual_region.y), ...] in DOM
    order. Picks the last card starting at or above `scroll_y`, falling back to
    the first card. `delta` is the sub-card remainder, so a position part-way
    through a tall card survives too.
    """

def resolve_anchor_target(order, anchor_id, live_offsets):
    """Content y for `anchor_id` after the rebuild, or None.

    `order` is the pre-rebuild pane_id sequence, `live_offsets` maps the
    surviving pane_ids to their new `virtual_region.y`. When the anchor was
    killed between ticks, walks `order` outward from the anchor's index
    (nearer-above first) for the nearest survivor; returns None when nothing
    from the old list survived, which the caller turns into a clamp.
    """
```

### 2. `MiniPaneList(VerticalScroll)` — two overrides, disjoint by call path

Replaces the bare `VerticalScroll(id="mini-pane-list")` in `compose()`
(`:622`). `query_one("#mini-pane-list", VerticalScroll)` keeps working, so
`_rebuild_pane_list` is untouched. `allow_vertical_scroll` is **not** overridden
— see the Approach section for why that seam is too blunt here.

```python
def scroll_to_region(self, region, *args, **kwargs):
    # The single funnel for every UNINVITED scroll: Screen.scroll_to_widget
    # calls this on each ancestor, which is how focus()'s scroll_visible, its
    # deferred re-post, Screen.set_focus's scroll_to_center and the focus
    # Textual re-homes on teardown all arrive. No user gesture comes this way.
    if not kwargs.get("force") and getattr(self.app, "_list_scroll_lock", False):
        return Offset()          # falsy ⇒ "nothing scrolled" for the caller's arithmetic
    return super().scroll_to_region(region, *args, **kwargs)

def _scroll_to(self, x=None, y=None, *, force=False, **kwargs):
    # Anything non-forced reaching here is a real user gesture — wheel,
    # scrollbar thumb drag (ScrollTo), trough/arrow click, or a scroll key
    # binding. The restore always passes force=True, and uninvited scrolls were
    # turned away above, so this needs no allowlist of handler names.
    if not force:
        self.app._abandon_scroll_restore()
    return super()._scroll_to(x, y, force=force, **kwargs)
```

Both read `self.app` defensively (`getattr` / a narrow `except NoActiveAppError`)
because they are reachable during teardown. `_abandon_scroll_restore()` is a
no-op when no restore is pending, which is the common case with the lock off.

### 3. `MiniMonitorApp` state — **class attributes**, not `__init__`

Declared at class level next to the existing class-level constants. This is
load-bearing for the test suite: five modules build the app with
`MiniMonitorApp.__new__(...)` and hand-set only the attributes they need
(`tests/test_minimonitor_other_section.py:99`, `test_monitor_session_divider.py`,
`test_multi_session_minimonitor.sh`, …), so an `__init__`-only default would
`AttributeError` there.

```python
_list_scroll_lock = False
_pending_scroll_state = None        # (at_bottom, anchor_id, delta, order) | None
_scroll_restore_gen = 0
_scroll_lock_timer = None
_SCROLL_RESTORE_MAX_ATTEMPTS = 8    # frames
_SCROLL_LOCK_TIMEOUT = 0.5          # s — well inside the 3 s tick
```

### 4. Capture + restore wiring in `_refresh_data` (`:711`, around `:858`)

Deliberately **not** inside `_rebuild_pane_list`: that method's container is a
`_FakeContainer` stub (`remove_children` / `mount_all` only) in every existing
test, and touching `scroll_y` / `max_scroll_y` / `query()` there would break all
of them. The task text explicitly allows either site. No minimonitor test drives
`_refresh_data`, so this site is free.

```python
saved_pane_id = self._focused_pane_id          # existing, :716
...
self._capture_list_scroll()                    # NEW — before the rebuild
gen = self._scroll_restore_gen = self._scroll_restore_gen + 1
self._list_scroll_lock = True
# Fail-safe armed HERE, on the acquisition line: Screen._invoke_and_clear_callbacks
# has no per-callback try, so an exception in an earlier callback of the batch
# drops the restore entirely and a release scheduled inside it would never run —
# leaving the list permanently un-scrollable.
self._scroll_lock_timer = self.set_timer(
    self._SCROLL_LOCK_TIMEOUT, lambda: self._abandon_scroll_restore(gen))

await self._rebuild_pane_list()                # existing, :858
self._restore_focus(saved_pane_id)             # existing, :860
self.call_after_refresh(self._restore_list_scroll, gen, 0)
```

New methods:

- **`_capture_list_scroll()`** — `query_one("#mini-pane-list", VerticalScroll)`
  (narrow `except NoMatches: return`, for the pre-compose ticks). Skips entirely
  when `_pending_scroll_state is not None`: a tick landing mid-restore must reuse
  the first snapshot, because re-capturing would record the transient zeros of a
  half-laid-out rebuild. Records
  `(at_bottom, anchor_id, delta, order)` where
  `at_bottom = max_scroll_y <= 0 or scroll_y >= max_scroll_y - 1`, and the rest
  comes from `pick_scroll_anchor` over
  `[(c.pane_id, c.virtual_region.y) for c in container.query(MiniPaneCard)]`.
- **`_restore_list_scroll(gen, attempt)`** — returns immediately if
  `gen != self._scroll_restore_gen` (superseded). Readiness is a **range**
  condition, not a size condition: `force=True` bypasses
  `allow_vertical_scroll` but **not** `validate_scroll_y`'s clamp, so a restore
  issued before `max_scroll_y` is computed silently yields 0. While
  `attempt < _SCROLL_RESTORE_MAX_ATTEMPTS` and the target exceeds
  `max_scroll_y`, re-post via `call_after_refresh`; falling through the budget
  restores what fits, which is the right answer when the list genuinely shrank.
  Then `scroll_end(animate=False, force=True)` if `at_bottom`, else
  `scroll_to(y=target, animate=False, immediate=True, force=True)`. In a
  `finally`: clear `_pending_scroll_state`, stop the fail-safe timer, and
  `call_after_refresh(self._release_list_scroll_lock, gen)` — one extra flush so
  focus scrolls deferred by the rebuild are still refused.
- **`_abandon_scroll_restore(gen=None)`** — called from the fail-safe timer with
  the generation it was armed for, and from `MiniPaneList._scroll_to` with none
  (meaning "whatever is current"). No-op if `gen` is stale, or if nothing is
  pending. Otherwise **retires the generation** (`_scroll_restore_gen += 1`) as
  well as clearing `_pending_scroll_state` and unlocking. Retiring is the
  load-bearing half: unlocking alone would leave a late `_restore_list_scroll`
  passing its own guard and forcing the stale offset over the scroll the user
  just performed — which is exactly the thumb-drag failure this design is built
  to avoid — and would leave the next tick reusing the stale snapshot.
- **`_release_list_scroll_lock(gen)`** — clears the lock if `gen` is current.

### 5. `_restore_focus` (`:1000`) — stop it scrolling

`card.focus(scroll_visible=False)`. With the lock held this is belt-and-braces
rather than the mechanism, but it removes a queued no-op scroll per tick and
makes the "anchor is authoritative" decision legible at the call site.
`_auto_select_own_window` (`:981`) is **not** changed — it is also reached from
`on_app_focus` (`:991`), an active gesture that must keep scrolling; the lock is
what neutralises it on the refresh path.

### Post-phase (risk mitigations)

1. `[assert_lock_never_sticks]` Add two tests to
   `tests/test_minimonitor_scroll_preservation.py` covering the stuck-lock
   failure mode directly, not by inference from the happy path:
   - drive several consecutive `_refresh_data` ticks and assert that once each
     settles, `_list_scroll_lock` is `False` **and** `_pending_scroll_state` is
     `None` — so neither the lock nor the snapshot can accumulate across ticks;
   - make `_restore_list_scroll` raise (patch it to throw on first call) and
     assert that after `_SCROLL_LOCK_TIMEOUT` a `card.focus()` scrolls into view
     again — i.e. the lock released. This pins the "fail-safe armed on the
     acquisition line, not inside the restore" decision, which is otherwise
     invisible and easy to undo in a later edit. Assert the generation was
     **retired** (a subsequent stale `_restore_list_scroll(old_gen, 0)` must be
     inert), not merely that the lock cleared.

## Verification

**Automated** — new `tests/test_minimonitor_scroll_preservation.py`, run with
`python3 tests/test_minimonitor_scroll_preservation.py` and via
`bash tests/run_all_python_tests.sh --test-dir tests`:

1. *Pure* (no Textual app): `pick_scroll_anchor` — topmost-visible pick, the
   sub-card `delta`, empty list → `None`, `scroll_y` above every card → first
   card. `resolve_anchor_target` — anchor survives; anchor killed → nearest
   surviving neighbour; nothing survives → `None`.
2. *Behavioural, `run_test(size=(40, 12))`* against a real `MiniPaneList` with
   real `MiniPaneCard`s, pinning both headless-reproducible reset mechanisms
   from the probes: (a) the `_auto_select_own_window` fallback focusing
   `cards[0]` from an unfocused state, and (b) the frame-boundary clamp between
   `remove_children()` and `mount_all()`. Each asserts the post-restore
   `scroll_y` matches the captured anchor, plus the at-bottom case stays pinned
   after a card above the fold disappears, and the killed-anchor case lands on
   the neighbour rather than 0.
3. *User-input supersedes the restore* — one case per gesture class, each posted
   at the container while the lock is held, asserting the gesture lands **and**
   that the subsequently-fired `_restore_list_scroll` is inert (the generation
   was retired):
   - `ScrollTo` — the **scrollbar thumb drag**; the path that motivated this
     design and the one a per-handler allowlist misses;
   - `events.MouseScrollDown` — the wheel;
   - `scrollbar.ScrollDown` — a trough / arrow click;
   - `action_scroll_down()` — a scroll key binding.

   Plus the converse: a `force=True` `scroll_to` / `scroll_end` (our own
   restore) must **not** retire the generation.
4. *Negative control* (one mutation, named failing test id): delete the
   `_scroll_to` override so no gesture retires the restore; the `ScrollTo`
   thumb-drag case above must then fail with the stale anchor winning. Recorded
   in the test module docstring. A second, separate mutation — dropping the
   `scroll_to_region` refusal — must fail case 2(a).
5. Regression: `python3 tests/test_minimonitor_other_section.py`,
   `bash tests/test_multi_session_minimonitor.sh`,
   `python3 tests/test_monitor_session_divider.py` — the `_FakeContainer` suites
   that must stay green, proving the capture stayed out of `_rebuild_pane_list`.

**Manual** — a `manual_verification` follow-up task is spawned at Step 8c
carrying the task's own three checks, which need a real 40-column tmux pane and a
physical wheel: position holds across several ticks; a bottom-pinned list stays
pinned when an agent above the fold is killed; a mid-list position survives its
own anchor agent being killed.

## Risk

### Code-health risk: medium
- A stuck scroll lock permanently suppresses scroll-into-view on
  `#mini-pane-list`, so keyboard navigation stops following the focused card off
  the fold. Narrower than p1257's equivalent failure (the list stays scrollable
  by wheel, drag and key throughout, because the lock never gates user input),
  but still a silent degradation. Structurally mitigated by the fail-safe timer
  armed on the acquisition line. · severity: medium · → mitigation: inline
  post-phase assert_lock_never_sticks
- Four new state fields, four new methods and a widget subclass land on
  `_refresh_data`, the 3 s hot path of an already 3478-line module, with
  deferred-callback + generation-token ordering that is easy to get subtly
  wrong on a later edit. · severity: medium · → mitigation: inline post-phase
  assert_lock_never_sticks
- `compose()` swaps a bare `VerticalScroll` for `MiniPaneList`; five test
  modules stub that container out via `_FakeContainer` and
  `MiniMonitorApp.__new__`, so the class-attribute defaults and the
  keep-capture-out-of-`_rebuild_pane_list` placement are load-bearing rather
  than stylistic. · severity: low · → mitigation: none (covered by the
  regression suites listed in **Verification**)

### Goal-achievement risk: medium
- **The reported reset was never reproduced.** Headless `run_test` probing
  reproduced two *plausible* mechanisms (the `_auto_select_own_window` fallback
  focusing `cards[0]`; the frame-boundary `validate_scroll_y` clamp) but not the
  reporter's real-terminal wheel gesture, and
  `aidocs/framework/tui_conventions.md` states a headless pin is not evidence
  for focus/scroll behaviour. The design is mechanism-agnostic on purpose —
  refuse every uninvited scroll, then re-apply the anchor — which is what makes
  it likely to hold regardless; but "likely" is not "verified against the actual
  cause". · severity: high · → mitigation: inline pre-phase
  reproduce_scroll_reset_live

- The task closes without the user-visible symptom being confirmed gone: a
  mouse-wheel gesture in a 40-column tmux pane cannot be synthesised, so the
  real check lands in a follow-up. · severity: medium · → mitigation: the
  `manual_verification` follow-up already planned in **Verification** above and
  offered natively at Step 8c

### Planned mitigations
- timing: pre-phase | name: reproduce_scroll_reset_live | type: bug | priority: high | effort: medium | inline_risk: high | added_complexity: medium | addresses: goal-achievement — the reported reset was never reproduced | desc: trace scroll_y/max_scroll_y/focused per refresh tick in a real 40-column tmux pane and record which mechanism actually resets the offset, before writing the fix
- timing: post-phase | name: assert_lock_never_sticks | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a stuck scroll lock leaves the list permanently un-scrollable | desc: pin that the lock and the pending snapshot clear after every tick, and that the acquisition-line fail-safe unlocks and retires the generation when the restore itself raises

## Post-implementation

Step 9 (Post-Implementation) handles cleanup, archival and merge as usual.
No documentation change is required: the fix is internal to one TUI and
`aidocs/framework/tui_conventions.md` gains nothing new — the refusal-seam
technique it uses is already documented in `aiplans/p1257_*.md`. Revisit at
Step 8 if the `docs_updated` spec disagrees.
