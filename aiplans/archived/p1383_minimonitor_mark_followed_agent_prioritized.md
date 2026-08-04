---
Task: t1383_minimonitor_mark_followed_agent_prioritized.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1383 — minimonitor: `space` marks the **followed** agent

## Context

`ait minimonitor` is a companion pane bound to exactly one code agent — the one
it *follows*, pinned in the docked `── this agent ──` panel. Today `space`
(`AgentMarksMixin.action_toggle_mark`, `monitor_shared.py:321`) resolves its
target through `_get_focused_pane_id()`, i.e. the highlighted card in the
scrollable list. The followed agent is structurally unreachable that way: it is
dropped from the list (`_rebuild_pane_list`, `minimonitor_app.py:864-869`) and
rendered as plain, non-focusable `Static`s (`_maybe_build_own_agent_panel`,
`:820`). So the one agent this pane exists to watch is the one agent it cannot
mark.

**Confirmed design change (supersedes the task's "Key choice" section).** Rather
than adding a second key, `space` in the minimonitor is *retargeted*: it toggles
the mark on the followed agent, independent of list focus. One key, one target.
The full monitor (`ait monitor`) is unchanged — it follows nothing, so focus is
its only sensible target, and it remains the place to mark any *other* agent.
Minimonitor list rows keep rendering `★`/`☆` (read-only), so marks set from
`ait monitor` or another repo stay visible.

Outcome: from an agent's own minimonitor, `space` flags that agent as
prioritized, the docked panel shows `★`/`☆`, and every other monitor TUI in
every repo agrees within one refresh cycle.

## Acceptance-criteria correction (do this first, in Step 7)

`aitasks/t1383_…md` currently states:

> The list-agent `space` behaviour is unchanged; the new key never toggles a
> list agent, and `space` never toggles the followed agent.

That criterion encodes the rejected two-key design and is now false by
construction. Rewrite the **Acceptance criteria** and **Key choice** sections of
the task file to the confirmed design before implementing — no silent deviation.
Replacement criterion: *"`space` in the minimonitor toggles the followed agent
regardless of list focus; minimonitor list cards are no longer togglable and
render marks read-only; `ait monitor`'s focus-scoped `space` is unchanged."*

## Approach

### 1. `.aitask-scripts/monitor/monitor_shared.py` — split the mixin's write path

Extract the body of `action_toggle_mark` (`:321-385`) into a target-agnostic
sink, leaving the action a thin focus-resolving caller. Nothing about the write
changes — the `PaneCategory.AGENT` guard, strict-root resolution, the
`MARKED:` / `UNMARKED:` / `LOCK_BUSY` / `ERROR:` branches, and the
`invalidate → _refresh_marks → call_later(_refresh_data)` tail all move
**verbatim**.

```python
async def _toggle_mark_for(self, snap: PaneSnapshot) -> None:
    """Toggle the prioritized mark on `snap`. The shared write path.

    Target resolution belongs to the caller: the full monitor resolves through
    live focus (:meth:`action_toggle_mark`); the minimonitor resolves through
    the agent it follows (``MiniMonitorApp.action_toggle_mark``, t1383). Both
    reach this one sink, so the guards and the four outcome branches are
    written once.
    """
    # ... existing body from the `if snap.pane.category != PaneCategory.AGENT`
    #     guard through `self.call_later(self._refresh_data)`, unchanged ...

async def action_toggle_mark(self) -> None:
    """Toggle the prioritized mark on the *focused* agent card.

    ... existing live-focus-vs-cached-`_focused_pane_id` comment block and the
    modal-dispatch NOTE preserved verbatim ...
    """
    pane_id = self._get_focused_pane_id()
    if not pane_id:
        return
    snap = self._snapshots.get(pane_id)
    if snap is None:
        return
    await self._toggle_mark_for(snap)
```

Keeping the `AGENT` guard inside the sink matters: minimonitor's own resolver is
already AGENT-only, but the monitor's list holds `OTHER` cards
(`test_minimonitor_other_section.SharedMarkGuardTests`) and that contract must
not move.

### 2. `.aitask-scripts/monitor/minimonitor_app.py` — override the action

Next to `action_show_own_task_info` (`:1840`), mirroring its resolution and its
warning wording verbatim:

```python
async def action_toggle_mark(self) -> None:
    """Toggle the prioritized mark on the agent this minimonitor follows.

    Deliberately NOT the focused list card, and deliberately not a *second*
    key beside the inherited one (t1383). A minimonitor is a companion pane
    bound to exactly one agent, so `space` here means "the agent I am
    watching" — one key, one target, whatever the list highlights. The full
    monitor keeps the inherited focus-resolved action: it follows nothing, so
    focus is its only target, and it stays the place to mark other agents.

    List rows still render ★/☆ so marks set from `ait monitor` or another
    repo remain visible here; they are simply read-only.
    """
    snap = self._find_own_agent_snapshot()
    if snap is None:
        self.notify("No followed agent in this window", severity="warning")
        return
    await self._toggle_mark_for(snap)
```

`_find_own_agent_snapshot` (`:515`) is AGENT-scoped on purpose, so a window
renamed off the `agent-` prefix refuses — exactly as `k` / `n` / `e` / `E` / `I`
already do.

**Binding label** (`:201`) — `show=False`, but the label *is* what the `?`
shortcut editor displays, so it must stop saying the wrong thing:

```python
Binding("space", "toggle_mark", "Mark followed agent", show=False),
```

The key itself is unchanged, so `tests/test_shortcuts_registry_coverage.sh` and
the "exactly one `space` binding per app" assertion in
`tests/test_monitor_agent_marks.py:255-270` stay green.

### 3. Render `★`/`☆` in the docked panel, and keep it live

The panel is one-shot (`_own_panel_built`, `:243-246`). A once-built glyph would
go stale: marks live in `~/.config/aitasks/agent_marks.json`, can be set from
`ait monitor` or another repo, and **expire after ~2 days**. So the glyph — and
only the glyph — is repainted per tick.

- Leave `_own_agent_identity_text` (`:791`) **untouched**. It stays the
  glyph-free identity string, which is what keeps
  `tests/test_monitor_shadow_status.py:493` and the `IDENTITY_NO_STATUS`
  assertion in `tests/test_multi_session_minimonitor.sh:376` meaningful.
- In `__init__` beside `_own_panel_built` (`:243`):
  `self._own_card: Static | None = None`,
  `self._own_identity_text: str = ""`,
  `self._own_mark_state: bool | None = None`.

  **`_own_mark_state` is deliberately tri-state.** `True`/`False` are the two
  glyphs; `None` means *nothing markable here* — render no glyph at all. It is
  both the current state and the repaint's change-detector, so the
  agent → renamed transition is a state change like any other rather than a
  case the repaint has to special-case.
- Card text is a function of the **frozen identity** plus the **live** mark
  state, so the repaint never needs a snapshot it may no longer have:

  ```python
  def _own_card_text(self, marked: bool | None) -> str:
      """Docked-panel text: the frozen identity line, plus the mark glyph.

      The mark is the ONE thing this panel refreshes. That is not a breach of
      the static-panel contract (t944 / t1133 / t1322), which excludes live
      *agent status* — the state dot, compare-mode and shadow glyphs, the
      COMPLETED badge. A mark is a durable **user annotation**, not status:
      `format_mark_glyph`'s docstring already places it outside the live-state
      cluster, and it can change without the agent changing at all (set from
      another repo, or expired by TTL).

      ``marked is None`` ⇒ there is nothing markable here (the window was
      never an agent, or was renamed off the ``agent-`` prefix after the panel
      was built) ⇒ **no glyph**, matching `_other_card_text`. The glyph is
      present exactly when `space` would act, which is the invariant that
      keeps a read-only ☆ from appearing on a pane whose `space` refuses.
      """
      if marked is None:
          return self._own_identity_text
      return f"{format_mark_glyph(marked)} {self._own_identity_text}"
  ```

  The glyph prefixes the bold name line; the wrapped title lines keep their
  two-space indent and so align under the name. `_own_agent_identity_text`'s
  wrap width is unchanged.
- `_maybe_build_own_agent_panel` (`:820`) captures the frozen identity and the
  initial mark state, and mounts `Static(self._own_card_text(...), …)`:

  ```python
  self._own_identity_text = self._own_agent_identity_text(own_snap)
  self._own_mark_state = (
      self._is_marked(own_snap)
      if own_snap.pane.category == PaneCategory.AGENT
      else None
  )
  ...
  card = Static(self._own_card_text(self._own_mark_state), classes="mini-own-card")
  ...
  self._own_card = card
  ```

- New per-tick repaint, called from `_refresh_data` immediately after
  `await self._maybe_build_own_agent_panel()` (`:470`) — `_refresh_marks()`
  already ran earlier in the same tick (`:451`), and `_set_session_root_map`
  before that (`:444`), which `_is_marked` depends on:

  ```python
  def _refresh_own_mark(self) -> None:
      """Repaint the docked panel's ★/☆ when the mark state changes.

      One `set` lookup per tick when nothing changed, and a single
      `Static.update` when something did. Four sources converge on this one
      code path: a local `space`, a mark set from `ait monitor` or another
      repo, TTL expiry, and the followed window being **renamed out of the
      agent category** — which drops the state to `None` and removes the
      glyph, rather than stranding the last-rendered ★ on a pane that `space`
      now refuses. (The identity text stays frozen through a rename, per
      `_maybe_build_own_agent_panel`'s one-shot contract; only the glyph
      tracks reality.)
      """
      if self._own_card is None:
          return
      snap = self._find_own_agent_snapshot()
      marked = self._is_marked(snap) if snap is not None else None
      if marked == self._own_mark_state:
          return
      self._own_mark_state = marked
      self._own_card.update(self._own_card_text(marked))
  ```

  Note `marked == self._own_mark_state` compares tri-state values, so
  `False` (unmarked agent) and `None` (nothing markable) are distinct and the
  transition between them repaints. A panel built for a non-agent window that
  is later renamed *into* the agent category likewise grows its glyph — the
  header still reads "this window", which is the pre-existing one-shot
  behaviour and out of scope here.

The local-toggle path needs no special casing: `_toggle_mark_for` already ends
with `invalidate → _refresh_marks → call_later(self._refresh_data)`, so the
keypress and the cross-repo case converge on `_refresh_own_mark`.

### 4. Key-hints panel (`compose`, `:275-285`)

`"space:mark (★ prioritized)"` → `"space:mark ★ (followed agent)"` (29 cols,
inside the 38-col budget; still contains the `"space:mark"` substring
`tests/test_monitor_agent_marks.py:292` asserts).

### 5. `website/content/docs/tuis/minimonitor/how-to.md`

- **Line 176** — the note to reverse. Rewrite (not append):

  > **Note:** `Space` always acts on the followed agent — the one pinned at the
  > top — never on the highlighted card. Marking the agent you are watching is
  > what makes it stand out *elsewhere*: the mark is per-user and cross-repo, so
  > it tells every other view (`ait monitor`, another project's minimonitor)
  > that this is the agent that matters. To mark some *other* agent, use
  > [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}), where `Space` acts on
  > the focused card.

- **Lines 161-175** (the "How to Mark an Agent as Prioritized" section) — change
  "the selected agent" to the followed agent, and state that list rows show
  marks read-only. The storage / cross-repo / cleanup paragraphs are unchanged.
- **Line 41** (card anatomy) — note the list glyph is display-only here.
- **Lines 110-115** (the static-panel note) — add that the mark is the one
  element of the pinned card that updates, and why (durable user annotation, not
  live status), so it does not read as contradicting the neighbouring prose.
- **Line 254** (Key Bindings Quick Reference) — `Space` → "Toggle the prioritized
  mark (`★`) on the **followed** agent — shared across all your projects".

`website/content/docs/tuis/monitor/*` are unchanged (monitor semantics
unchanged). The v0.30.0 blog post is a dated record and is left alone.

## Tests

### New — `tests/test_minimonitor_own_mark.py`

Mock-based, `MiniMonitorApp.__new__`, modelled on
`tests/test_minimonitor_own_task_info.py` (fixture shape) and
`tests/test_monitor_agent_marks_action.py` (`_run_marks_cmd` recording double,
real `MarksView` over a temp store, `asyncio.run(...)` driving).

*Resolution — the discriminating cases.* Each must fail against the inherited
focus-resolved action:

1. **A different list card is focused** (a real `mm.MiniPaneCard`, per t1282's
   deviation) while the followed agent resolves → `_run_marks_cmd` called
   **once** with exactly `["toggle", realpath(root), "<followed window>"]`,
   asserted token-by-token. This is the regression the task describes.
2. **A card from a different repo/session is focused** → still the *followed*
   agent's root and window; assert it is not the focused card's.
3. **Nothing focused** → still toggles the followed agent. (The old code
   returned silently here, so this discriminates in the opposite direction.)
4. **No followed agent** (`_find_own_agent_snapshot() → None`) → warns
   "No followed agent in this window", `_run_marks_cmd` never called.
5. **Followed window renamed off `agent-`** (`OTHER` category) → same warning,
   no write — the AGENT-only resolver contract.
6. `MARKED:` and `LOCK_BUSY` each route correctly through the override (one
   assertion apiece; the full four-outcome matrix stays on the shared sink in
   `test_monitor_agent_marks_action.py`).
7. Structural: `MiniMonitorApp.action_toggle_mark is not
   AgentMarksMixin.action_toggle_mark` — the override exists, and is a
   coroutine.

*Render level — state matrix.* `panel.mounted[1].render().plain`, driving
`_maybe_build_own_agent_panel` / `_refresh_own_mark` against a real `MarksView`
over a temp store. These isolate the repaint logic:

8. Unmarked agent → contains `☆`, not `★`; marked agent → `★`, not `☆`.
9. A followed window that was **never** an agent (`OTHER` at build) renders
   **no** glyph — neither `★` nor `☆`.
10. **Agent → renamed transition.** Build the panel with a *marked* AGENT
    (asserts `★`), then make `_find_own_agent_snapshot()` unresolvable (the
    window renamed off the `agent-` prefix → `OTHER`), run the repaint, and
    assert the card now contains **neither** `★` nor `☆` — the stale-star case.
    Then rename back and assert the glyph returns. This is the case a
    build-time `_own_panel_is_agent` freeze would fail.
11. **Static contract still holds**, asserted alongside the new glyph so the
    exception reads as scoped: the docked card contains no `●`, no
    `SHADOW_GLYPH`, no compare-mode `≈`/`=`, no COMPLETED badge — and the
    frozen identity text (window name + task title) is byte-identical before
    and after a mark flip.
12. Hint panel advertises the new wording and no line exceeds
    `_HINT_WIDTH_BUDGET` (38).

*Wiring — driven through a real refresh cycle.* Tests 8-11 call
`_refresh_own_mark()` directly, so they would all pass if the production call
were **missing from `_refresh_data`, or placed before `_refresh_marks()` /
before `_set_session_root_map()`**. That is the defect class this task is most
exposed to, so the AC-level proof must go through the real entry point — a
mounted app via `app.run_test()`, following
`tests/test_monitor_agent_marks.py::MountedRenderTests` and
`tests/test_monitor_modal_space_dispatch.py` (which already mounts *both* TUIs):

13. **Cross-repo flip through one real cycle.** Mount `MiniMonitorApp`, install a
    fake `_monitor` (session→root mapping + `capture_all_async` returning a
    followed-agent snapshot) and a `MarksView` over a temp store. `await
    app._refresh_data()` → query `#mini-own-agent .mini-own-card`, assert `☆`.
    Then write the mark **straight into the store file** (simulating `ait
    monitor` or another repo — no keypress, no call to any mark method).
    `await app._refresh_data()` again → assert the mounted card now renders
    `★`. Nothing but `_refresh_data` is invoked between the two assertions, so
    a missing or misordered production call fails here.
14. **TTL expiry through the same cycle:** rewrite the stored mark with a
    `marked_at` older than the TTL window, run one more `_refresh_data()`, and
    assert the panel is back to `☆`.
15. **Local `space` through the same cycle:** `await app.action_toggle_mark()`
    with a recording `_run_marks_cmd` that actually toggles the temp store,
    then one `_refresh_data()` → `★`. This closes the loop the action's own
    `call_later(self._refresh_data)` relies on.

Fixture requirements for the mounted harness (name them in the test module so
the next reader does not rediscover them): stop `_refresh_timer` after mount;
override `_run_marks_cmd` so `_maybe_purge_marks` spawns no subprocess; stub
`_maybe_offer_concerns`; and make the auto-close check inert so `_refresh_data`
cannot quit the app mid-test.

### Updated

- `tests/test_monitor_agent_marks_action.py` — `ArgvContractTests`,
  `GuardTests` and `OutcomeTests` currently drive `action_toggle_mark` for
  `BOTH_APPS` via `_get_focused_pane_id`. Retarget them at the shared sink
  `_toggle_mark_for(snap)` (still both apps), and keep one `MonitorApp`-only
  class for the focus-resolution half. Minimonitor's resolution moves to the new
  file. `ObservationTests` / `PurgeSchedulingTests` are untouched.
- `tests/test_minimonitor_other_section.py` — `SharedMarkGuardTests`: keep the
  "Marks apply to agent panes only" assertion for `MonitorApp` and for the
  shared sink; for `MiniMonitorApp` invert it to *a focused `OTHER` card is
  ignored and the followed agent is toggled instead*. `OwnAgentPanelTests._app`
  gains `app._init_agent_marks()` (the panel path now reads `_marks_view`),
  mirroring `_mk_list_app` at `:118`.
- `tests/test_monitor_modal_space_dispatch.py` — `test_space_with_focus_off_the_card_does_not_toggle`
  inverts for the minimonitor half (focus is irrelevant there now); document the
  asymmetry in its docstring. The modal cases stay green and become *more*
  load-bearing for the minimonitor, since there is no longer a focus guard
  behind them — say so in the module header.
- `tests/test_multi_session_minimonitor.sh` — Tier 1g should stay green
  (`_own_agent_identity_text` unchanged, panel still two `Static`s); re-run and
  confirm rather than assume.

### Negative controls

Three, one per failure direction. Each is a **single** mutation, shown to make
the suite exit 1 on the *named* tests, then restored with `Edit` only — never
`git checkout --`, which would wipe a concurrent session's in-flight edits.

1. **Resolution.** Delete the `MiniMonitorApp.action_toggle_mark` override
   (falling back to the inherited focus-resolved action) → cases 1, 2 and 3
   must fail.
2. **Stale glyph.** Replace `_refresh_own_mark`'s tri-state with the
   early-return form (`if snap is None: return`) → case 10 must fail while
   8, 9 and 11 still pass, proving case 10 is what discriminates it.
3. **Wiring.** Remove the `self._refresh_own_mark()` call from `_refresh_data`
   → cases 13-15 must fail while 8-11 still pass. If 8-11 also fail, the
   direct-call tests are not as isolated as claimed and the split is wrong.

## Verification

1. `python3 tests/test_minimonitor_own_mark.py` — new suite passes.
2. `bash tests/run_all_python_tests.sh` — **read only the last line**
   (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`, on stderr; piping discards
   the exit status).
3. `bash tests/test_multi_session_minimonitor.sh`,
   `bash tests/test_shortcuts_registry_coverage.sh`.
4. Negative control above, shown to make the suite exit 1, then restored.
5. **Live acceptance (real tmux pane, real keypress — not `send-keys`):** launch
   `ait minimonitor` in an agent window with ≥1 other agent running. Press
   `space` with a *different* list card highlighted → the docked panel flips to
   `★` and the other card is unaffected. Capture the pane at 40 columns and
   confirm the docked card still reads. Then mark/unmark the same agent from
   `ait monitor` and confirm the docked panel follows within one refresh cycle.
   Finally `tmux rename-window` the followed window off the `agent-` prefix and
   confirm the glyph disappears within a cycle (the frozen name stays) and that
   `space` then warns — the real category transition behind test 10.

## Risk

### Code-health risk: low

- Blast radius is small and mostly mechanical: `monitor_shared.py` (extract a
  sink, no behaviour change), `minimonitor_app.py` (one override, one wrapper,
  one per-tick repaint), one doc file, one new test file, three test files
  updated. · severity: low · → mitigation: none needed (covered in-task)
- The docked panel's "built once, no live refresh" contract (t944 / t1133 /
  t1322) gets its first exception. Bounded by scoping the repaint to the glyph
  alone — identity text and the agent-vs-window header stay one-shot — and by
  re-asserting every excluded element (`●`, shadow glyph, compare-mode, COMPLETED)
  plus byte-identical identity text in the same test that asserts the new `★`. ·
  severity: low · → mitigation: none needed (pinned by test 11)
- Mixing a frozen identity with a live glyph creates one genuinely tricky
  state: the followed window renamed out of the agent category *after* the
  panel was built. The tri-state `_own_mark_state` makes "nothing markable"
  an explicit value rather than an early return, so the glyph is present
  exactly when `space` would act; pinned by test 10 with its own negative
  control. · severity: low · → mitigation: none needed
- Extracting `_toggle_mark_for` touches the write path shared by both TUIs. The
  extraction is verbatim and the monitor's own tests continue to drive it, so a
  regression there surfaces immediately. · severity: low · → mitigation: none needed

### Goal-achievement risk: low

- The behaviour change is user-directed and unambiguous (one key, one target),
  and the two directions that could go wrong — focus winning over the followed
  agent, and a stale once-built glyph — each have a discriminating test with a
  negative control. · severity: low · → mitigation: none needed
- The one accepted trade-off: minimonitor can no longer mark a *list* agent, so
  marking an agent you are not following requires `ait monitor`. Confirmed with
  the user; list rows keep rendering marks so nothing becomes invisible. ·
  severity: low · → mitigation: none needed

## Final Implementation Notes

- **Actual work done:** Implemented as planned.
  `monitor_shared.py` gained `AgentMarksMixin._toggle_mark_for(snap)` — the
  category guard, strict-root resolution, the four outcome branches and the
  `invalidate → _refresh_marks → call_later(_refresh_data)` tail, all moved
  verbatim — leaving `action_toggle_mark` a thin focus-resolving caller.
  `minimonitor_app.py` overrides `action_toggle_mark` to resolve through
  `_find_own_agent_snapshot()`, relabels the `space` binding
  ("Mark" → "Mark followed agent", which is what the `?` shortcut editor
  shows), and renders the mark in the docked panel via a frozen
  `_own_identity_text`, a tri-state `_own_mark_state`, `_own_card_text(marked)`
  and a new `_refresh_own_mark()` called from `_refresh_data` right after the
  panel build. Hint line: `space:mark ★ (followed agent)`.
  New `tests/test_minimonitor_own_mark.py` (25 tests in four classes);
  `test_monitor_agent_marks_action.py`, `test_minimonitor_other_section.py` and
  `test_monitor_modal_space_dispatch.py` updated;
  `website/content/docs/tuis/minimonitor/how-to.md` rewritten in five places and
  one clarifying sentence added to the monitor's how-to.

- **Deviations from plan:** Two, both additive.
  1. **A composited-width test pair was added** (`CompositedWidthTests`) that
     the plan did not call for. Writing the plan's manual step as a headless
     40-column composite surfaced a real regression (below), and a comment
     recording the bound would not have been falsifiable.
  2. **`test_monitor_modal_space_dispatch.py` needed a second snapshot.** The
     plan only foresaw inverting one test. In fact every minimonitor case in
     that file needed a *followed* agent (window 1) **and** a list card
     (window 2): with a single snapshot the followed agent is excluded from the
     list, so no card mounts and the positive control cannot run. The shared
     `_instrument` now installs both plus `_session` / `_own_window_index`.

- **Issues encountered:**
  - **A visible layout regression, found by rendering rather than by test.**
    The glyph costs 2 columns on a line the docked panel — unlike the list rows
    — never truncates. Composited at 40 columns, a 38-character name folds *and*
    strands the glyph alone on line 1 (3 lines where there were 2).
    A non-breaking separator does **not** fix it: Rich splits words on `\s`,
    and Python's `\s` matches U+00A0, so ` ` is still a break opportunity.
    Measured the actual bound instead — names ≤36 are unaffected — and checked
    real window names on the live tmux socket: `agent-pick-1383`,
    `agent-pick-1243_5`, `agent-raw-1`, i.e. 11-17 characters. The case is
    unreachable in practice, so the fold is accepted, documented in
    `_own_card_text`'s docstring with the U+00A0 finding, and pointed at
    **t1351** (minimonitor row-width audit). `CompositedWidthTests` pins the 36
    bound and was shown to fail at 37.
  - `Static.update()` works on an *unmounted* widget in this Textual version
    (verified before relying on it), which is what lets the layer-2 render
    matrix stay mock-based.
  - `_FakeMonitor` doubles in the cycle-driven tests need `control_state()`:
    `_rebuild_session_bar` reads it on every real tick.

- **Key decisions:**
  - **`space` retargeted, not duplicated.** The task proposed a *second* key
    (`*` or an uppercase letter) beside the focus-scoped `space`. The user
    rejected that during planning: a minimonitor is a companion pane bound to
    one agent, so `space` there can only sensibly mean "the agent I am
    watching". The task file's "Key choice" and "Acceptance criteria" sections
    were rewritten *before* implementing rather than deviating silently.
    Consequence, confirmed: minimonitor list cards are no longer togglable
    (they still render marks read-only); `ait monitor` is unchanged and remains
    the way to mark any other agent.
  - **Tri-state `_own_mark_state`, not a build-time "is agent" flag.** The
    panel's identity is frozen at build, so freezing markability too would
    strand a `★` on a window later renamed off the `agent-` prefix. `None`
    means "nothing markable" and renders no glyph, making the invariant *the
    glyph is present exactly when `space` would act* — and making the rename an
    ordinary state change rather than a special case.
  - **Three test layers, three single-mutation negative controls.** Resolution
    / render-matrix / wiring are separated precisely so each control breaks one
    layer and leaves the others green — which is itself asserted (control 3
    requires 13-15 to fail *while* 8-11 pass). Without the cycle-driven layer,
    a `_refresh_own_mark()` call missing from `_refresh_data`, or ordered before
    `_refresh_marks()`, would have passed the whole suite.
  - The AGENT-only guard stayed in the shared sink rather than moving to the
    monitor: the monitor's list holds `OTHER` cards, and the minimonitor's own
    resolver is AGENT-only, so the guard is unreachable there but still correct
    to keep centralized.

- **Upstream defects identified:** None.

- **Build verification:** `bash tests/run_all_python_tests.sh` →
  `PYTHON SUITE: PASSED (runner=pytest, exit=0)`, 3188 passed / 2 skipped plus
  the serial carve-out. `bash tests/test_multi_session_minimonitor.sh` → 43/43.
  `bash tests/test_shortcuts_registry_coverage.sh` → PASS.
  `bash tests/test_no_raw_tmux.sh` → PASS.
  Live acceptance in a real tmux pane with a real keypress is **not** covered by
  the above and remains outstanding.

- **Concurrency note:** `tests/test_board_movement.py` was modified in the
  worktree by a concurrent session (t1243_5 area) throughout this task and was
  deliberately left unstaged.

## Post-implementation

Step 9 of the shared workflow handles cleanup, merge, and archival.
