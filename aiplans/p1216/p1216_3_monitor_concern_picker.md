---
Task: t1216_3_monitor_concern_picker.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Sibling Tasks: aitasks/t1216/t1216_4_monitor_shadow_spawn.md, aitasks/t1216/t1216_5_manual_verification_monitor_shadow_pane_view_and_concern_pic.md
Archived Sibling Plans: aiplans/archived/p1216/p1216_1_shared_shadow_seam.md, aiplans/archived/p1216/p1216_2_monitor_shadow_zone.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-29 22:00
---

# p1216_3 — Concerns in the full monitor (badge + toast + picker)

## Context

`ait monitor` is the best TUI for switching between sessions, but shadow
concerns are still reachable only from `ait minimonitor`. t1216_1 lifted the
shared seam and t1216_2 added the `SHADOW` zone; this third child delivers the
parent's **third** acceptance criterion — from `ait monitor`, shadow concerns
can be parsed and picked through the existing `ConcernPickerModal`, with the
same clipboard payload semantics as minimonitor.

`ConcernPickerModal` already lives in `monitor_shared.py:677` and its docstring
already names t1216_3 as the second pusher — `monitor_app.py` just never pushes
it. Make that true; write no second modal, no second parser, no second lookup.

The N-agent problem shapes everything: minimonitor has exactly one followed
agent and can afford a `-J` subprocess capture every tick. The monitor shows N
agents, so the **badge** must be free for all of them.

Depends on **t1216_1** (`concern_block_signature`, `_SENTINEL_SAFE_COLS`,
`capture_shadow_text`, `compute_shadow_staleness`) and **t1216_2**
(`_current_shadow_pane_id`, `_reconcile_shadow_state`) — both landed.

---

## Plan verification (2026-07-29)

Re-verified against `main` @ `a39a2611c`. The plan was written before t1216_1 /
t1216_2 landed, so **every line anchor in it is stale**: `monitor_app.py` is now
**2724 lines** (was 2070). It is clean in the working tree. Nineteen substantive
corrections, folded into the steps below. Corrections 13-16 came from a review
pass on the first verified draft, 17-18 from a second, and 19 from a third; all
seven were confirmed against the source, and 17 turned out to be worse than
reported (it defeats two dedup maps, not one).

**All three review passes found the same root cause** — state read at *write*
time instead of snapshotted at *launch* time, across an await — in a different
place each time (15: a guard released before the modal closed; 18: a pane id
reused after focus moved; 19: a trigger signature re-read after the tick
advanced). Corrections 15, 18 and 19 are therefore one family, and the standing
control is the rule in "Notes for sibling tasks": **snapshot before the await,
pass it explicitly, re-check identity after**.

### Anchor refresh at implementation time (HEAD moved to `1fb008967`)

`main` advanced **eight commits during this session**, touching every file this
plan modifies (`monitor_shared.py` +328, `monitor_core.py` +220,
`monitor_app.py` +105, `minimonitor_app.py` +285). Re-verified before writing any
code — **no correction changed**, only line numbers:

| Symbol | Verified at | Now |
|---|---|---|
| `monitor_app._refresh_data` | 866 | **873** |
| `monitor_app._format_agent_card_text` | 1255 | **1331** |
| `monitor_app._current_shadow_pane_id` | 1710 | **1787** |
| `monitor_app._reconcile_shadow_state` | 1785 | **1862** (prune loop **1915-1921**) |
| `monitor_app.check_action` | 1984 | **2061** |
| `monitor_app.on_key` | 2040 | **2117** |
| `monitor_shared.SHADOW_GLYPH` / `format_shadow_glyph` | 88 / 91 | **118** / **121** |
| `monitor_shared.ConcernPickerModal.__init__` | 731 | **1011** |
| `minimonitor_app._unparsed_msg` | 96 | **104** |

Design assumptions re-confirmed against the new HEAD: `c` is still free in
`MonitorApp.BINDINGS` (460-476); `monitor_app.py` still has **zero** concern /
clipboard references; `ConcernPickerModal.__init__` still takes
`(concerns, narrow, stale, unrecovered)`; `capture_shadow_text`
(`monitor_core.py:400`) still catches **only** `asyncio.TimeoutError` at :445,
so correction 14 stands; the `_reconcile_shadow_state` prune loop still resolves
every agent's shadow, so correction 7 applies unchanged.

One t1322 interaction worth naming: `format_shadow_glyph` is now documented as
*"deliberately single-argument"* because a shadow has no task and must never
render in the COMPLETED colour. Adding a keyword-only `has_concerns` does not
weaken that — it is orthogonal to `completed`, which stays un-passable — and all
four existing call sites in `test_monitor_shadow_status.py` /
`test_monitor_completed_status.py` pass one positional argument, so they remain
valid.

### Anchor re-map (`monitor_app.py`) — as verified at `a39a2611c`

| Symbol | Plan said | Actually |
|---|---|---|
| `BINDINGS` | 391-410 | **458-477** (`c` still free ✓) |
| `__init__` | — | **479-566** (shadow block **529-550**) |
| `_refresh_data` | 702-781 | **866-953** |
| ` └ `commit_snapshots` / `self._snapshots = snaps` | — | 882 / **885** |
| ` └ `_preview_scroll_state` prune | 734-745 | **897-909** |
| ` └ `_reconcile_shadow_state()` call | — | **943** |
| ` └ `_rebuild_pane_list` / previews | — | 945 / 946-947 |
| ` └ `call_after_refresh(_restore_focus, …)` | — | **952-954** |
| `_format_agent_card_text` | 1022-1054 | **1255-1288** |
| ` └ `get_shadow_snapshot` / `format_shadow_glyph` | 1028 / 1037 | **1261** / **1270** |
| `_current_shadow_pane_id` | (t1216_2) | **1710-1720** |
| `_reconcile_shadow_state` | — | **1785-1850** (all-agent loop **1837-1848**) |
| `check_action` | 1417-1421 | **1984-1988** |
| `on_key` | 1457-1501 | **2040-2097** (modal early-return **2043-2045**) |
| `format_shadow_glyph` (`monitor_shared`) | L86-92 | **91-98**, `SHADOW_GLYPH` **88** |
| `ConcernPickerModal` | 593 | **677**, `__init__` **731** |

### Corrections

1. **`capture_shadow_text` is MODULE-LEVEL, not a `TmuxMonitor` method.**
   `monitor_core.py:400`, `async def capture_shadow_text(shadow_pane, *, lines=None)`.
   The plan's Step 5 `await self._monitor.capture_shadow_text(shadow_pane)` is an
   `AttributeError`. Import it (via the `monitor.tmux_monitor` shim, which
   re-exports it at 47-55) and call it free-standing, as minimonitor's own
   delegating seam does (`minimonitor_app.py:1257-1261`).

2. **`ConcernPickerModal` gained a fourth parameter since the plan was written.**
   `__init__(concerns, narrow=False, stale=False, unrecovered=0)`
   (`monitor_shared.py:731`). t1274 added `unrecovered_markers()` to
   `concern_parser` (:416) and minimonitor now (a) passes
   `unrecovered=len(unrecovered_markers(text))` to the modal and (b) replaces the
   bland *"No concerns detected"* with `_unparsed_msg(lost)` when a block was
   emitted but **all** its markers were malformed. Shipping the monitor without
   this would put a **known-false** "no concerns" message on a brand-new surface.
   **Scope addition (stated):** port both. `_unparsed_msg` is module-level in
   `minimonitor_app.py:96-105`; lift it to `monitor_shared.py` as
   `unparsed_concerns_msg` rather than importing app→app or writing a second copy.

3. **There is no tick-computed staleness in the monitor.** Plan Step 5 item 7
   says "reuse the tick-computed value … as minimonitor does" — minimonitor has
   `_shadow_feedback_stale` because it runs `_update_shadow_freshness` every other
   tick for its **one** agent. Replicating that for N agents means N
   `get_pane_option` round-trips per tick. Instead compute
   `compute_shadow_staleness` **on demand**: once when a toast is about to fire
   for the selected agent, and once on `c`.

4. **The eviction rule contradicted the plan's own sibling note — resolved with
   the user (2026-07-29).** The PINNED table said *"Followed pane loses its
   shadow entirely → entry **evicted**"*, while "Notes for sibling tasks" said
   *"a respawned shadow for the same agent should not silently re-offer an
   identical block"* — eviction on shadow loss produces exactly that re-offer.
   **Decision: retain.** Evict only when the followed **agent pane leaves
   `_snapshots`**. The badge still goes off, because it derives from the
   *current* signature being absent, not from the offered map. This also avoids
   inventing a per-agent grace counter: `get_shadow_snapshot()` returns `None`
   for both a dead shadow and a one-tick capture blip (t1133's `LifecycleTests`
   establish blips are normal), so literal eviction would need one or would
   re-toast on every blip. **Step 0 amends the task file's PINNED table** so the
   task and the plan agree — this is a product-policy change, not an
   implementation detail.

5. **`_reconcile_shadow_state` must stay sync.** `tests/test_monitor_shadow_zone.py`
   calls it directly at six sites (447, 456, 464, 467, 474, 485) and asserts its
   `Zone` return. So the async concern work cannot live inside it. Split:
   a **sync** `_scan_concern_signatures()` (no I/O) for the badge, and an
   **async** `_offer_concerns()` for the toast.

6. **Keep the blocking I/O off the tick — worker, but NOT `exclusive`.**
   `_offer_concerns` can block for up to 3 s (`capture_shadow_text`) + 2 s
   (`get_pane_option`). Awaiting it inline stretches the 3 s interval, because
   Textual awaits the timer callback before scheduling the next. Dispatch it as a
   worker — the idiom this file already uses for its two render paths (1488-1493,
   1639-1644) — but see **correction 14**: it must not be `exclusive=True`.

7. **`_reconcile_shadow_state` already resolves every agent's shadow** in its
   scroll-prune loop (1837-1848: `for followed in list(self._snapshots): s =
   get_shadow_snapshot(followed)`). That is the "resolve once per agent per tick"
   loop the t1216_2 sibling note asks us to reuse — publish its result as
   `self._tick_shadow_snaps` rather than re-walking.

8. **The test runner no longer seeds `PYTHONPATH`.** t1236 (`442dbc42c`) made
   `run_all_python_tests.sh` **unset and scrub** it, precisely so a wrong
   bootstrap fails in tests instead of only at runtime. The plan's "seeds
   `PYTHONPATH` with only `board` and `lib`" is now false — the new test file
   must do its own three `sys.path.insert`s from `__file__`
   (`test_monitor_shadow_zone.py:33-36`).

9. **`monitor_app.py` has no `async def action_*` today** — every action is a
   plain `def` dispatching via `call_later` / `run_worker`. Textual supports async
   actions and minimonitor's `action_pick_concerns` is one, so mirroring it is
   right; note it is the **first** in this file. See **correction 15** for the
   re-entrancy guard it needs.

10. **"press 'e' to launch one" is premature.** `e`/`E` is **t1216_4**, not yet
    in `MonitorApp.BINDINGS` (458-477). Promising a key that does nothing is a
    worse failure than a plain message. Use *"No shadow agent bound to this
    agent"*; t1216_4 re-adds the hint when it adds the key.

11. ~~The toast deliberately diverges from minimonitor's.~~ **Withdrawn by
    correction 16.** The first verified draft kept a countless toast because the
    cheap trigger has no parse. Correction 16 introduces one authoritative
    capture per *newly-seen* block, so the real counts are available and the
    monitor uses minimonitor's exact wording.

12. **A concurrent session holds uncommitted edits to `minimonitor_app.py`**
    (task-info dialog, `I` binding — no overlap with the concern code). Correction
    2 needs a two-line edit there, so the Step-8 commit must stage **paths
    explicitly** and verify staged *content*, never `git add -A`.

13. **The `__new__` test harness would conceal a missing `__init__` field.**
    Step 2 does specify all seven new attributes in `MonitorApp.__init__`, but
    every test modelled on `test_minimonitor_concern_action.py:92-110` sets them
    by hand on a `__new__`-constructed app — so a forgotten initializer would
    pass the whole new suite and raise `AttributeError` only in live use. The
    suite therefore needs at least one **constructed-app** path
    (`MonitorApp(session=…, project_root=…)`, per
    `test_monitor_shadow_zone.py:124-142`) that drives a real `_refresh_data`
    and a real `action_pick_concerns` with **no** hand-set concern state.

14. **`exclusive=True` would leak a capture subprocess.** Verified at
    `monitor_core.py:441-450`: `capture_shadow_text` wraps `proc.communicate()`
    in `asyncio.wait_for` and kills the child **only** in `except
    asyncio.TimeoutError`. When `run_worker(exclusive=True)` cancels the pass,
    `wait_for` cancels the inner future and re-raises `CancelledError` — the
    `proc.kill()` / `await proc.wait()` block never runs and the
    `aitask_shadow_capture.sh` child is orphaned, which is worst exactly when
    tmux is stalled (the case the 3 s timeout exists for) and undermines the
    bounded-cost claim. **Fix: never cancel an in-flight capture.** Dispatch
    non-exclusively and guard with an `_offer_busy` latch, so a slow pass is
    simply *not restarted* rather than killed mid-flight. (Adding a
    `CancelledError` branch to `capture_shadow_text` was considered and rejected
    for this task: it edits a t1216_1 seam that minimonitor also depends on, to
    fix a hazard this task can avoid structurally. Recorded as an upstream
    robustness note.)

15. **The `c` re-entrancy guard must outlive the capture.** `push_screen` is
    non-blocking, so clearing `_concern_pick_busy` in a `finally` immediately
    after it releases the guard **while the modal is still open**. Textual
    resolves bindings up the focus chain to the App, and `ConcernPickerModal`
    binds only `escape` / `enter` / `a` / `A` (`monitor_shared.py:700-705`) — so
    a second `c` reaches `action_pick_concerns` and stacks a second picker. (The
    modal early-return at `on_key` 2043-2045 does **not** cover this: it guards
    the `on_key` handler, not binding dispatch.) **Fix: transfer ownership of the
    latch to `_on_concerns_picked`**, which Textual always invokes on dismissal,
    including `None` on Esc. Every pre-push return path still releases it.

16. **`concern_block_signature` signs blocks that yield no forwardable
    concerns.** It uses `_last_block_region(..., require_close=True)` — a
    complete *fence* — but, unlike `has_concern_block` (:433), it does **not**
    require ≥1 parsed concern. So an all-malformed block (exactly the case t1274
    exists for) signs, badges, and would toast *"Shadow raised concerns"*, after
    which `c` reports nothing forwardable — and, because that path deliberately
    leaves `_concern_sig_offered` untouched, the badge sticks **forever** for a
    block that can never become parseable. Two fixes:
    - **Verify before toasting.** On a *newly-seen* signature for the **selected**
      agent, take one authoritative `-J` capture and toast only if
      `parse_concerns` yields ≥1. Cost is **one subprocess per (selected agent,
      new block)** — not per tick, and never scaling with N. This is a stated
      deviation from the parent plan's *"the authoritative `-J` capture runs only
      when the user presses `c`, or via the narrow-pane fallback"*, bought
      deliberately: it also restores minimonitor's count-bearing toast
      (withdrawing correction 11).
    - **Clear the badge on a definitive negative.** When the `c` capture contains
      a complete block that yields nothing forwardable, the user has just been
      told exactly that and the block will never parse — record it as offered.
      Keep the marker untouched when the capture *failed* or showed **no**
      complete block (truncated / scrolled off), where we learned nothing. This
      amends one PINNED row whose rationale ("clearing would hide a block the
      user never saw") predates t1274's definitive message; Step 0 records it.

17. **A raw signature and a `-J` signature of the SAME block can differ — so a
    single stored signature breaks both dedup maps.** `concern_block_signature`
    documents its one residual: whitespace runs normalise to a single space, so a
    wrap landing **mid-word** injects a space that was not in the source. The
    trigger reads the raw tick capture (`-p -e`, hard newlines at every wrap)
    while every marker is written from the `-J` capture (wraps joined), so the
    two digests differ **systematically** whenever the block wraps mid-word — not
    merely when the pane is resized. Consequences, both real:
    - `_concern_sig_examined` never matches the next tick's raw signature, so
      correction 16's "check each signature once" degenerates into a
      **subprocess every tick** — the exact cost this design exists to avoid.
    - `_concern_sig_offered` never matches either, so after a **successful pick**
      the badge is **permanently stuck on**. p1216_1 bounded this residual to "at
      most one spurious re-offer", but that framing assumed both sides come from
      the same capture path; across two paths it never converges.

    **Fix: both maps store the (trigger, captured) signature *pair*.** Every
    marker write records the raw signature that was on screen *and* the digest of
    the text actually captured, and every read is a membership test. Bounded at
    two entries per agent (a new block replaces the pair), and a genuine resize
    still costs at most one spurious re-check — the documented residual, restored
    to its intended bound.

18. **The toast must re-check focus after its awaits.** `_offer_concerns` pins
    `pane_id` before `capture_shadow_text` (≤3 s) and `compute_shadow_staleness`
    (≤2 s), then notifies without re-reading it — so moving the selection during
    the capture toasts for an agent that is no longer selected, breaking the
    "at most one popup, for the selected agent" policy the whole badge design
    rests on. Re-check `self._focused_pane_id` **and** that the shadow is still
    bound to the pane we captured, immediately before `notify`. On a mismatch,
    still record the signature as examined (the check genuinely ran; re-running it
    would spend another subprocess) and skip only the toast — nothing is lost,
    because the **badge** is the durable signal and is untouched.

    Note the deliberate asymmetry with `action_pick_concerns`, which keeps its
    pinned `pane_id` across the same awaits: `c` is an explicit user action
    targeting the agent that was selected when they pressed it, whereas the toast
    is an unsolicited interruption that must describe what is on screen *now*.

19. **The marker writer must not read the trigger from ambient state after an
    await.** As first drafted, `_mark_concern_sig` resolved
    `self._concern_sig_latest[pane_id]` at *write* time — after
    `capture_shadow_text` returned. `_scan_concern_signatures` runs on every 3 s
    tick, so a newer block **B** can replace signature **A** during that window;
    the capture then returns A's text and the marker is written as `{B, A}`.
    B is thereby recorded as examined (never verified — no toast) or offered
    (never presented — badge cleared), and a genuinely new concern block is
    **silently lost**. That is a miss, not a spurious re-offer: the worst failure
    class for this feature, and invisible.

    **Fix: snapshot the trigger signature before each await and pass it
    explicitly.** `_mark_concern_sig(store, pane_id, trigger_sig, captured_sig)`
    takes no ambient state, so a marker can only ever describe the block the
    capture was actually launched for. For the same reason the `seen` sets are
    **re-read after** the await rather than reused from before it — a concurrent
    `c` (its guard is independent of `_offer_busy`) may have offered the block
    while the offer pass was suspended, and toasting for a block the user just
    picked would be the mirror-image bug.

Confirmed unchanged: `c` is free in `MonitorApp.BINDINGS`; `check_action`
(1984-1988) disables every non-`switch_zone` binding in `PREVIEW`/`SHADOW`, so
`c` is reachable **only** from `PANE_LIST` with no change needed;
`tests/test_tui_clipboard_seam.sh` scans every `*.py` under `.aitask-scripts/`
for `\.copy_to_clipboard\(`, so `monitor_app.py` is in scope;
`RowRenderTests` (`test_monitor_shadow_status.py:439-463`) asserts non-shadowed
rows are **byte-identical** between a populated and an empty shadow map.

---

## Step 0 — reconcile the task's PINNED lifecycle table

Corrections 4 and 16 change user-visible policy, so the **task file** is amended
before implementation rather than left contradicting the code (no silent AC
deviation). In `aitasks/t1216/t1216_3_monitor_concern_picker.md`, under
`## PINNED: badge lifecycle`:

- replace the row *"Followed pane loses its shadow entirely | entry evicted |
  off"* with two rows — *"Shadow dies / respawns for the same agent | **retained**
  | off, and off again on respawn"* and *"Followed **agent pane** leaves the
  snapshot map | entry **evicted** | row gone"* — plus one line recording the
  decision and its reason (respawn must not re-offer; blip vs death is
  indistinguishable);
- split the row *"`c` pressed → capture ok but parse yields 0 concerns … |
  unchanged | stays on"* into the **definitive** case (complete block, nothing
  forwardable → **offered set**, badge off) and the **indeterminate** cases
  (capture failed, or still head-truncated after the deep retry → unchanged,
  badge stays on), noting that t1274's `unparsed_concerns_msg` is what makes the
  first case definitive.

Commit with `./ait git` as a task-metadata change, separate from the code commit.

## Step 1 — shared formatters (`monitor_shared.py`)

Two edits, both keeping existing call sites working untouched.

```python
SHADOW_GLYPH = "◆"          # :88 (existing)
SHADOW_CONCERN_GLYPH = "!"  # NEW — single column, appended to the glyph


def format_shadow_glyph(
    shadow_snap: PaneSnapshot | None, *, has_concerns: bool = False
) -> str:
    if shadow_snap is None:
        return ""                       # unchanged — no placeholder
    body = SHADOW_GLYPH + (SHADOW_CONCERN_GLYPH if has_concerns else "")
    return f"[{_state_color(shadow_snap)}]{body}[/]"
```

`has_concerns` is **keyword-only** so no positional caller can break, and it
defaults to `False` so minimonitor's `_agent_card_text` and `FormatterTests`
(`test_monitor_shadow_status.py:396-419`) are untouched. The marker shares the
state colour, so the markup stays a **single span** — the existing
`[bold magenta]◆[/]` assertion still matches exactly when there are no fresh
concerns.

**Non-shadowed rows stay byte-identical**: the `None` branch returns `""`
regardless of `has_concerns`, so `RowRenderTests`' equivalence assertion holds by
construction.

Second edit — lift the t1274 message (correction 2), beside `format_stale_duration`
(:100):

```python
def unparsed_concerns_msg(count: int) -> str:
    """Warning for a block whose marker lines yielded no concern (t1274)."""
    return (
        f"Shadow emitted a concern block but {count} line(s) could not be "
        "parsed — none are forwardable"
    )
```

In `minimonitor_app.py`: delete `_unparsed_msg` (96-105), import
`unparsed_concerns_msg` from `monitor_shared`, and keep the private name alive as
a one-line alias (`_unparsed_msg = unparsed_concerns_msg`) so the existing suite
binds unchanged.

## Step 2 — imports and state (`monitor_app.py`)

Add to the existing `monitor.tmux_monitor` import (26-31) — the shim re-exports
all four (`tmux_monitor.py:47-55`):

```python
capture_shadow_text, compute_shadow_staleness,
_SHADOW_DEEP_RETRY_LINES, _SHADOW_TRUNCATED_MSG,
```

Add `ConcernPickerModal` and `unparsed_concerns_msg` to the `monitor_shared`
import (33-38), and two new import statements:

```python
from monitor.concern_parser import (  # noqa: E402
    _SENTINEL_SAFE_COLS, block_head_truncated, build_clipboard_payload,
    concern_block_signature, needs_addressing, parse_concerns,
    unrecovered_markers,
)
from tui_clipboard import copy_to_system_clipboard  # noqa: E402
```

`lib/` is already on `sys.path` (bootstrap at 22-24), which is how
`agent_launch_utils` / `shortcuts_mixin` resolve today.

**All seven fields are initialized in `__init__` (479-566)**, beside the t1216_2
shadow block at 529-550. This is load-bearing, not incidental: the `__new__`
harness sets them by hand and would mask an omission (correction 13), which is
why Verification requires a constructed-app path.

```python
self._concern_sig_latest: dict[str, str] = {}              # pane -> THIS tick's raw sig
self._concern_sig_offered: dict[str, frozenset[str]] = {}  # pane -> sigs already picked
self._concern_sig_examined: dict[str, frozenset[str]] = {} # pane -> sigs already -J-checked
self._tick_shadow_snaps: dict[str, PaneSnapshot] = {}      # published by the tick
self._concern_tick: int = 0                      # narrow-probe throttle
self._offer_busy: bool = False                   # one offer pass at a time
self._concern_pick_busy: bool = False            # `c` guard, held while the modal is open
```

Three signature maps, each load-bearing:
`_latest` is the derived truth (absent ⇒ no complete block ⇒ no badge);
`_offered` is what the user has been shown the picker for, and drives the badge;
`_examined` records that the **authoritative** capture already ran, so a block
that verifies to *nothing forwardable* is checked **once** rather than
re-captured every tick.

The two marker maps hold a **`frozenset` pair, not a single string**
(correction 17). One shared writer keeps that invariant in one place:

```python
@staticmethod
def _mark_concern_sig(
    store: dict[str, frozenset[str]],
    pane_id: str,
    trigger_sig: str | None,
    captured_sig: str,
) -> None:
    """Record BOTH the raw trigger signature and the -J captured one.

    They are digests of the same block taken through different capture paths
    (`-p -e` vs `-J`), and `concern_block_signature`'s documented mid-word-wrap
    residual makes them differ systematically whenever the block wraps mid-word.
    Storing only one leaves the next tick's raw signature unmatched — which
    re-captures every tick for `_examined`, and never clears the badge for
    `_offered`. Bounded at two entries: a new block replaces the pair.

    `trigger_sig` is a PARAMETER, never read from ``_concern_sig_latest`` here
    (correction 19): callers snapshot it before their capture await, and the 3s
    tick can replace it with a NEWER block's signature meanwhile. Reading it at
    write time would mark that newer block as already examined/offered and lose
    it silently. Static for the same reason — there is no instance state to
    reach for.
    """
    store[pane_id] = frozenset(
        s for s in (trigger_sig, captured_sig) if s is not None
    )
```

## Step 3 — the per-tick trigger (sync, zero subprocesses)

In `_reconcile_shadow_state` (1785-1850), the prune loop at 1837-1848 already
walks every agent and resolves its shadow. Publish that resolution instead of
discarding it:

```python
live_shadow_ids: set[str] = set()
tick_shadows: dict[str, PaneSnapshot] = {}
for followed in list(self._snapshots):
    s = self._monitor.get_shadow_snapshot(followed)
    if s is not None:
        live_shadow_ids.add(s.pane.pane_id)
        tick_shadows[followed] = s
self._tick_shadow_snaps = tick_shadows
# … existing _shadow_scroll_state prune, unchanged …
```

The method stays **sync** and keeps returning `Zone` (correction 5).

New sibling method, called from `_refresh_data` **between 943 and 945** so the
badge is correct when `_rebuild_pane_list` renders:

```python
def _scan_concern_signatures(self) -> None:
    """Refresh the per-agent concern signatures from data the tick already has.

    Zero tmux traffic: ``shadow_snap.content`` came from the same async gather
    that captured the agents. This is a TRIGGER, never a parse — the picker
    re-captures with -J (concern_parser's third strictness tier).
    """
    prev = self._concern_sig_latest
    latest: dict[str, str] = {}
    for followed, snap in self._tick_shadow_snaps.items():
        sig = concern_block_signature(snap.content)
        if sig is None and snap.pane.width < _SENTINEL_SAFE_COLS:
            # Below _SENTINEL_SAFE_COLS the fences themselves can wrap, so
            # "no signature" is uninformative, not evidence of absence. Carry
            # forward whatever the Step-5 probe last established — rebuilding
            # wholesale here would clear the probe's value every tick and make
            # a narrow-pane badge flicker on and off. For a WIDE pane absence
            # IS evidence, so it drops (the "block scrolls out" row).
            sig = prev.get(followed)
        if sig is not None:
            latest[followed] = sig
    self._concern_sig_latest = latest
    # Evict ONLY when the agent itself is gone (correction 4, confirmed with the
    # user): a shadow that died and one that blipped are indistinguishable here,
    # and evicting on that would re-offer an identical block on respawn.
    for pid in list(self._concern_sig_offered):
        if pid not in self._snapshots:
            del self._concern_sig_offered[pid]
            self._concern_sig_examined.pop(pid, None)
```

## Step 4 — the badge (derived, never latched)

```python
def _has_fresh_concerns(self, followed_pane_id: str) -> bool:
    sig = self._concern_sig_latest.get(followed_pane_id)
    if sig is None:
        return False
    return sig not in self._concern_sig_offered.get(followed_pane_id, frozenset())
```

```python
def _seen_concern_sigs(self, followed_pane_id: str) -> frozenset[str]:
    """Signatures already picked OR already authoritatively checked."""
    return self._concern_sig_offered.get(
        followed_pane_id, frozenset()
    ) | self._concern_sig_examined.get(followed_pane_id, frozenset())
```

Membership, not equality (correction 17) — the raw signature on screen and the
`-J` signature stored at pick time are digests of the same block through
different capture paths, so an equality test would leave the badge stuck on
forever after a successful pick.

`_format_agent_card_text` — change **only line 1270**:

```python
shadow = format_shadow_glyph(
    shadow_snap, has_concerns=self._has_fresh_concerns(snap.pane.pane_id)
)
```

This is what makes the N-agent case work: **every** agent with a fresh block is
marked at zero cost, so nothing is missed across N agents, while only one popup
ever fires.

### Badge lifecycle (PINNED — one test per row; mirrors the amended task table)

| Event | `_concern_sig_offered` | Badge |
|---|---|---|
| New block, signature differs from the stored one | unchanged | **on** (+ toast if selected **and** it verifies) |
| `c` → `-J` capture returns `None` (failure/timeout) | **unchanged** | stays **on** |
| `c` → capture shows **no complete block** (truncated after the deep retry) | **unchanged** | stays **on** |
| `c` → capture shows a **complete block yielding nothing forwardable** | set to the **captured** sig (correction 16) | off |
| `c` → modal actually pushed with ≥1 concern | set to the **captured** sig | off |
| Picker cancelled (Esc / Cancel) | already set at push | stays off — the user saw them |
| Shadow re-issues a *different* block | differs again | **on** again |
| Block scrolls out of the capture window (`sig is None`) | **retained** | off |
| That same block scrolls back in | matches retained | stays off (no re-toast) |
| Shadow dies / respawns for the same agent | **retained** (correction 4) | off, then off again on respawn |
| Followed **agent pane** leaves `_snapshots` | entry **evicted** | row gone |

Three decisions that are easy to get wrong:

1. **Set the marker only once the outcome is definitive** — never on the
   keypress. Clearing at keypress would hide a block the user never saw exactly
   when the capture fails or times out.
2. **Set it at push, not on confirm.** A user who opens the list and forwards
   nothing has seen the block; re-toasting would be noise.
3. **Store the signature of the text the picker actually captured**, recomputed
   from the `-J` capture — not the tick signature that raised the badge. The
   shadow may have emitted more between badge and keypress, and storing the older
   signature would leave the newer block permanently un-offered.

## Step 5 — verify-then-toast (worker, never cancelled)

Dispatched from the end of `_refresh_data`, after the
`call_after_refresh(_restore_focus, …)` at 952-954:

```python
self.run_worker(
    self._offer_concerns(), group="concerns", exit_on_error=False
)
```

**Deliberately not `exclusive=True`** (correction 14): cancelling the pass would
orphan the `aitask_shadow_capture.sh` child, because `capture_shadow_text` only
kills it on `TimeoutError`. Its own `group` also keeps it clear of the `preview`
/ `shadow-preview` render groups. Re-entrancy is handled by `_offer_busy`, so a
slow pass is *not restarted* rather than killed.

```python
async def _offer_concerns(self) -> None:
    """Toast the SELECTED agent once per verified block. Never per-tick I/O.

    Cost: at most ONE `-J` capture per (selected agent, newly-seen signature),
    plus the narrow-pane probe every other tick when a sub-sentinel-width shadow
    shows nothing. Never scales with N — the badge, which does, is free.
    """
    if self._monitor is None or self._offer_busy:
        return
    self._offer_busy = True
    try:
        self._concern_tick += 1
        pane_id = self._focused_pane_id       # re-read: focus may have moved
        shadow_snap = self._tick_shadow_snaps.get(pane_id) if pane_id else None
        if shadow_snap is None:
            return
        seen = self._seen_concern_sigs(pane_id)
        sig = self._concern_sig_latest.get(pane_id)   # the TRIGGER — snapshot it
        if sig is None:
            # Nothing detected. Only a sub-sentinel-width pane can HIDE a block
            # from the cheap detector (_SENTINEL_SAFE_COLS = 24: the fences are
            # 21 and 18 chars), so anything wider genuinely has none.
            if shadow_snap.pane.width >= _SENTINEL_SAFE_COLS:
                return
            if self._concern_tick % 2 == 0:
                return                        # probe every other tick
        elif sig in seen:
            return                            # already picked, or already checked

        shadow_pane = shadow_snap.pane.pane_id
        text = await capture_shadow_text(shadow_pane)
        if text is None:
            return                            # learned nothing; retry next tick
        captured_sig = concern_block_signature(text)
        if captured_sig is None:
            return                            # no complete block in the -J window
        # Narrow-pane path: this is where the badge's signature comes from.
        if sig is None:
            self._concern_sig_latest[pane_id] = captured_sig
        # Re-read AFTER the await (correction 19): a concurrent `c` may have
        # offered this block while we were suspended.
        if captured_sig in self._seen_concern_sigs(pane_id):
            return
        # Record BOTH digests (correction 17), with the trigger passed EXPLICITLY
        # from the snapshot above (correction 19) — re-reading it here could
        # store a NEWER block's signature and lose it.
        self._mark_concern_sig(
            self._concern_sig_examined, pane_id, sig, captured_sig
        )
        concerns = parse_concerns(text)
        if not concerns:
            return      # malformed / empty block: no misleading toast. The badge
                        # stands, and `c` gives the user the precise reason.
        eps = max(2.0, float(getattr(self, "_refresh_seconds", 3)))
        stale, _ = await compute_shadow_staleness(
            self._monitor, shadow_pane, pane_id, eps
        )
        # Re-check AFTER the awaits (correction 18): the toast is an unsolicited
        # interruption and must describe what is on screen now. The signature
        # stays marked examined — the check really did run — and the badge is
        # untouched, so nothing is lost when we skip the popup.
        if self._focused_pane_id != pane_id:
            return
        still = self._monitor.get_shadow_snapshot(pane_id)
        if still is None or still.pane.pane_id != shadow_pane:
            return                            # shadow died or was rebound
        actionable = sum(1 for c in concerns if needs_addressing(c))
        info = len(concerns) - actionable
        info_suffix = f" (+{info} informational)" if info else ""
        stale_suffix = " (⚠ STALE — agent moved on)" if stale else ""
        self.notify(
            f"Shadow raised {actionable} concern(s){info_suffix} — press 'c' to pick"
            + stale_suffix
        )
    finally:
        self._offer_busy = False
```

`_concern_sig_examined` is set **before** the parse, so a block that verifies to
nothing is captured once and never re-probed — without it, correction 16's
verify step would become a per-tick subprocess for every malformed block.

The toast now matches minimonitor's wording exactly (`minimonitor_app.py:1458-1462`),
which is what withdrawing correction 11 buys.

`compute_shadow_staleness` is tri-state (`True | False | None`, where `None`
means *indeterminate — preserve*); `if stale` treats both `False` and `None` as
"no warning", the right read for a one-shot toast with no prior state to
preserve.

The narrow-pane signature lands **after** `_rebuild_pane_list` has run, so on the
sub-24-column path the badge appears one tick (~3 s) after the toast. Accepted:
rebuilding the list out of band would disturb the focus restoration
`_refresh_data` has just scheduled.

## Step 6 — `c` → `action_pick_concerns`

```python
BINDINGS = [ …, Binding("c", "pick_concerns", "Concerns"), … ]
```

`check_action` (1984-1988) already returns `action == "switch_zone"` while
`PREVIEW`/`SHADOW` is focused, so `c` is live **only** in `PANE_LIST`. **No
`check_action` change.**

```python
async def action_pick_concerns(self) -> None:
    if self._concern_pick_busy:
        return                                  # correction 15
    pane_id = self._focused_pane_id
    if not pane_id or pane_id not in self._snapshots:
        self.notify("Focus an agent pane first", severity="warning")
        return
    shadow_pane = self._current_shadow_pane_id()
    if not shadow_pane:
        self.notify("No shadow agent bound to this agent", severity="warning")
        return                                  # correction 10
    self._concern_pick_busy = True
    modal_owns_guard = False
    # Snapshot the trigger BEFORE any await (correction 19): the 3s tick can
    # replace it with a newer block's signature while we capture, and marking
    # that newer signature as offered would clear its badge unpresented.
    trigger_sig = self._concern_sig_latest.get(pane_id)
    try:
        text = await capture_shadow_text(shadow_pane)          # -J, --deep
        if text is None:
            self.notify("Could not read the shadow pane", severity="warning")
            return                              # indeterminate: marker UNTOUCHED
        concerns = parse_concerns(text)
        if not concerns and block_head_truncated(text):
            deeper = await capture_shadow_text(
                shadow_pane, lines=_SHADOW_DEEP_RETRY_LINES
            )
            if deeper is not None:
                text = deeper
                concerns = parse_concerns(text)
            if not concerns:
                self.notify(_SHADOW_TRUNCATED_MSG, severity="warning")
                return                          # indeterminate: UNTOUCHED
        if not concerns:
            lost = len(unrecovered_markers(text))               # correction 2
            if lost:
                self.notify(unparsed_concerns_msg(lost), severity="warning")
            else:
                self.notify("No concerns detected on the shadow pane")
            # Definitive only when the capture DOES contain a complete block:
            # the user has just been told precisely what is in it, and it will
            # never become parseable — so clear the badge (correction 16). If
            # there is no complete block here, we learned nothing about the
            # badged one: leave the marker alone.
            done_sig = concern_block_signature(text)
            if done_sig is not None:
                self._mark_concern_sig(
                    self._concern_sig_offered, pane_id, trigger_sig, done_sig
                )
            return
        eps = max(2.0, float(getattr(self, "_refresh_seconds", 3)))
        stale, _ = await compute_shadow_staleness(
            self._monitor, shadow_pane, pane_id, eps
        )                                        # correction 3: on demand
        self._mark_concern_sig(
            self._concern_sig_offered, pane_id, trigger_sig,
            concern_block_signature(text),
        )
        self.push_screen(
            ConcernPickerModal(
                concerns,
                narrow=False,                    # monitor is full-width
                stale=bool(stale),
                unrecovered=len(unrecovered_markers(text)),
            ),
            callback=self._on_concerns_picked,
        )
        modal_owns_guard = True                  # released by the callback
    finally:
        if not modal_owns_guard:
            self._concern_pick_busy = False


def _on_concerns_picked(self, selected: list | None) -> None:
    self._concern_pick_busy = False              # correction 15
    if not selected:
        return                                   # cancel writes nothing
    copy_to_system_clipboard(self, build_clipboard_payload(selected))
    self.notify("Concerns copied to clipboard.")
```

The guard is **held across the modal's lifetime** and handed to
`_on_concerns_picked`, which Textual always invokes on dismissal (including
`None` on Esc) — without that, `c` pressed over the open picker stacks a second
one, because App bindings resolve up the focus chain and the modal does not bind
`c` (correction 15).

`concern_block_signature` is fed the `-J` text here rather than a tick capture —
deliberate, and the reason the digest normalises whitespace runs: a `-J`-joined
and a soft-wrapped rendering of the same block agree at word boundaries. Storing
the tick sig instead would leave a newer block permanently un-offered.

`pane_id` stays **pinned** across the awaits here, unlike the toast path
(correction 18): `c` is an explicit action against the agent that was selected
when the key was pressed, so its modal and its marker belong to that agent even
if the selection drifts mid-capture.

Shadow resolution uses `_current_shadow_pane_id()` (a pure `get_shadow_snapshot`
dict read, per t1216_2's sibling note) rather than minimonitor's live
`find_shadow_pane_async`. Consequence, stated: a shadow spawned since the last
3 s tick is not yet visible to `c`. That is the price of zero-tmux resolution and
self-heals within one tick.

**`copy_to_system_clipboard`, never `app.copy_to_clipboard`** —
`tests/test_tui_clipboard_seam.sh` greps `\.copy_to_clipboard\(` across every
`*.py` under `.aitask-scripts/` and `monitor_app.py` is in scope. A bare OSC 52
from a non-visible tmux window silently never reaches the system clipboard.

The modal is pure UI: it builds no payload and touches no clipboard. Nothing
reaches the clipboard until the user confirms, and the monitor never types the
payload into the agent — the user pastes it.

## Step 7 — docs

- `website/content/docs/tuis/monitor/reference.md` — add a `c` row to the
  **Pane Interaction** table (24-34). *(Correction: the "Each card shows:"
  description the plan expected here does not exist in reference.md.)*
- `website/content/docs/tuis/monitor/how-to.md` —
  - extend the **"Each card shows:"** bullet list at **38-42** with the shadow
    glyph and its concern marker (neither is documented today, even though
    t1133 shipped the glyph);
  - add `### How to Pick Shadow Concerns` after **141** (*Cycle the Preview
    Size*), mirroring `minimonitor/how-to.md:119-137` — intro, numbered steps,
    the disposition split (`a` / `A`), the degradation cases, and an
    **Auto-offer** blockquote. Say that the badge marks **every** agent with a
    fresh block while the toast fires only for the selected one — that difference
    from minimonitor is the point of the N-agent design — and that a block whose
    markers cannot be parsed badges without toasting, with `c` giving the reason.

## Verification

New `tests/test_monitor_concern_action.py`. It must do its **own**
`sys.path.insert` ×3 from `__file__` (`.aitask-scripts`, `.../lib`,
`.../board`) — the runner scrubs `PYTHONPATH` (correction 8) — and the
module-level `os.environ.pop("TMUX"/"TMUX_PANE", None)`.

Harness: `test_minimonitor_concern_action.py:92-110` — `MonitorApp.__new__`,
hand-set `_monitor` / `_snapshots` / `_concern_sig_*`, and **`spy_`-prefixed**
lambdas replacing `notify` / `push_screen` / `copy_to_clipboard` (the prefix
avoids colliding with read-only Textual `App` properties). Spy
`copy_to_clipboard`, not `copy_to_system_clipboard`, so the **real** seam runs
and is observed through it. `_async_return(value)` for coroutine stubs;
monkeypatch the module-level `capture_shadow_text` / `compute_shadow_staleness`
on `monitor_app`.

- **Constructed-app path (correction 13)** — a `MonitorApp(session=…,
  project_root=REPO_ROOT)` built normally (per `test_monitor_shadow_zone.py:124-142`,
  mounted via `run_test`), with **no** hand-set concern state: run a full
  `_refresh_data` over a shadowed agent whose content carries a block, assert the
  badge renders, then drive `action_pick_concerns` to a pushed modal. Omitting
  any `__init__` field must make this fail — the `__new__` tests cannot.
- Modal pushed with the parsed concerns, `narrow=False`; **nothing on the
  clipboard before confirm**; the callback with a selection writes exactly
  `build_clipboard_payload(selected)`; cancel (`None`) and empty write nothing.
- Deep retry on head-truncation (captures == `[None, _SHADOW_DEEP_RETRY_LINES]`);
  `_SHADOW_TRUNCATED_MSG` when still truncated; **negative control** that a
  genuine absence of a block yields the plain message and **no** re-capture.
- t1274 parity: all-markers-malformed yields `unparsed_concerns_msg`, and the
  modal receives `unrecovered=` matching `len(unrecovered_markers(text))`.
- **Verify-before-toast (correction 16)** — an all-malformed block badges but
  produces **no** toast; a well-formed block toasts with the real
  `{actionable} concern(s)` count and the `(+N informational)` suffix; the
  malformed block is authoritatively captured **once**, not once per tick
  (assert the capture count across several ticks).
- **Definitive-negative badge clear (correction 16)** — `c` over a complete but
  unforwardable block **sets** `_concern_sig_offered` (badge off); `c` over a
  capture that fails, or one showing no complete block, leaves it **untouched**
  (badge stays on). These two must be separate tests: a single "badge clears"
  assertion would pass under either policy.
- Toast fires **once per signature** and **only for the selected agent**; a
  second tick with the same sig does not re-toast; the `⚠ STALE` suffix appears
  when `compute_shadow_staleness` returns `True` and is absent for both `False`
  and `None`.
- **Mid-word-wrap dedup (correction 17)** — the discriminating test for the
  signature *pair*. Fixture: raw tick content whose block wraps **mid-word** and
  `-J` text of the same block, so `concern_block_signature` returns two different
  digests (assert that precondition explicitly — otherwise the test proves
  nothing). Then:
  - several ticks perform **exactly one** `capture_shadow_text` call, not one per
    tick;
  - after a successful pick, `_has_fresh_concerns` is `False` and **stays**
    `False` across further ticks — the stuck-badge case.
  **Negative control:** store only the captured signature (the pre-fix
  behaviour) and confirm both assertions fail, so the pair — not the fixture — is
  what makes them pass.
- **A newer block arrives during the capture (correction 19)** — the miss case,
  run for **both** writers. Trigger signature **A** is on screen; script
  `capture_shadow_text` to run a refresh that replaces `_concern_sig_latest` with
  a newer block **B** before returning **A**'s text. Assert the marker holds
  exactly `{A, captured_A}` and **not** `B`; that `_has_fresh_concerns` is still
  `True`; and that the next tick verifies/offers B normally. Repeat via
  `action_pick_concerns` (B must not be silently marked offered).
  **Negative control:** have `_mark_concern_sig` re-read `_concern_sig_latest`
  instead of taking the parameter and confirm both cases fail — a marker that
  swallows B is otherwise invisible.
- **Focus moves during the capture (correction 18)** — script
  `capture_shadow_text` to change `_focused_pane_id` to another agent before
  returning: assert **no** toast fires, that the signature is still recorded in
  `_concern_sig_examined` (so the next tick does not re-capture), and that the
  badge is unchanged. Second case: the shadow is **rebound** to a different pane
  during the await → also no toast. Paired positive control: with focus
  unchanged, the same fixture **does** toast — otherwise a broken offer path
  would pass the negative test vacuously.
- Badge appears for a **non-selected** agent with fresh concerns — the N-agent
  case minimonitor structurally cannot cover — asserted through
  `_format_agent_card_text`, paired with the byte-identity control that a
  **non-shadowed** row is unchanged (the `RowRenderTests` invariant).
- **The per-tick path spawns no subprocess**: monkeypatch
  `asyncio.create_subprocess_exec` with a recorder; with several wide-shadow
  agents and no new block, assert **zero** calls across several ticks, and with a
  new block assert **exactly one** regardless of N.
- **One test per row of the badge-lifecycle table**, in particular: the two
  indeterminate capture-failure controls asserting `_concern_sig_offered` is
  untouched and `_has_fresh_concerns` still `True`; scroll-out → scroll-back with
  no re-toast; **shadow death then respawn retains** the marker (the
  user-confirmed correction 4 semantics) **and** its counterpart, eviction when
  the agent leaves `_snapshots`; and a shadow that emitted a *newer* block
  between badge and keypress storing the **captured** signature.
- Narrow-pane probe: fires for the selected agent only, throttled to every other
  tick, with **negative controls** that a shadow pane at exactly
  `_SENTINEL_SAFE_COLS` never triggers it and that a non-selected narrow agent
  never triggers it.
- **Narrow-pane badge does not flicker** — after the probe establishes a
  signature, run several further ticks whose raw content still yields `None` and
  assert `_has_fresh_concerns` stays `True` throughout. Paired negative control:
  a **wide** pane whose block scrolls out **does** drop to `False` on the next
  tick, proving the carry-forward is scoped to sub-sentinel widths and is not
  just "never forget".
- **Re-entrancy across the modal's lifetime (correction 15)** — a second
  `action_pick_concerns` while the capture is in flight is a no-op; a second one
  **while the modal is open** is also a no-op (exactly one `push_screen`); after
  `_on_concerns_picked` runs, a third succeeds. A test that only covers the
  capture window would pass under the buggy `finally`-release.
- **No cancellation of an in-flight capture (correction 14)** — two consecutive
  `_offer_concerns()` calls while the first is suspended mid-capture: the second
  returns immediately and the first completes uncancelled. Plus a structural
  assertion on the `run_worker` kwargs (`group="concerns"`, **no**
  `exclusive=True`), so re-adding `exclusive` fails the suite.
- No-shadow and no-focused-agent negative controls.

**Prove the harness can fail.** Invert each guard in turn — the
`_concern_sig_offered` write moved to the keypress; the badge compared against
`_examined` instead of `_offered`; eviction on shadow loss; the
`< _SENTINEL_SAFE_COLS` bound; the `% 2` throttle; `has_concerns` hard-wired
`True`; the `finally` releasing `_concern_pick_busy` before dismissal; the toast
emitted before `parse_concerns`; the marker maps storing a single string instead
of the pair; the post-await focus re-check removed — and confirm the suite exits **non-zero** each
time. A passing test pins nothing until its failure path is demonstrated, and a
negative control that *passes* means some other guard did the rejecting.

```bash
bash tests/run_all_python_tests.sh   # ~12 min; read ONLY the last line
bash tests/test_tui_clipboard_seam.sh
bash tests/test_no_raw_tmux.sh
```

Manual, **from a shell outside the main aitasks tmux session** (`aidocs/framework/tui_conventions.md`
"Tmux-stress tasks"): run two agents, spawn a shadow on the **non-selected** one
from minimonitor, have it emit a concern block, and confirm the badge appears on
that agent's card with **no** toast; select it and confirm the toast carries the
right count; press `c`, tick a subset, and confirm the payload pastes correctly
into the agent.

## Commit note — concurrent session

`minimonitor_app.py` carries another session's uncommitted work (correction 12).
Stage **explicit paths** and verify staged *content* (`git diff --cached`) before
committing; never `git add -A`. If the file's foreign hunks cannot be separated,
fall back to the hunk-extraction procedure recorded in `p1216_1`.

## Post-Review Changes

### Change Request 1 (2026-07-30 00:20)

- **Requested by user:** Review of the implementation raised two defects.
  1. *(blocking)* `_scan_concern_signatures` swept only `_concern_sig_offered`
     when evicting a departed agent, so an `_examined`-only entry was never
     reclaimed — violating the stated agent-exit contract.
  2. *(follow-up)* `_offer_concerns` re-checked focus and shadow-pane identity
     after its awaits but **not signature freshness**, so the same pane
     advancing from the verified block A to a newer B still toasted A's count —
     disagreeing with the badge (tracking B) and with the picker moments later.

- **Verified:** both CONFIRMED against the source.
  1. The offer pass returns *before* marking a block offered when it yields
     nothing forwardable, so a malformed-only block populates `_examined`
     **only**; a loop over `_offered` cannot see it. The pre-existing eviction
     test hid this because it reaches the agent through `c`, which populates
     both maps.
  2. Identity is not freshness: nothing between the staleness await and the
     `notify` compared the live signature against the one just verified.

- **Changes made:**
  1. The eviction sweep now iterates `set(_concern_sig_offered) |
     set(_concern_sig_examined)` and pops from both.
  2. `_offer_concerns` builds the verified `(trigger, captured)` pair locally
     and, as its last post-await guard, returns unless
     `_concern_sig_latest[pane_id]` is still in it. The newer block is
     deliberately left un-examined so the next pass announces it on its own
     terms.

- **Tests added:** `test_agent_exit_evicts_an_examined_only_entry` (asserts the
  `_offered`-empty precondition explicitly, so it cannot pass for the same
  reason the old test did) and
  `test_same_pane_advancing_to_a_new_block_suppresses_the_toast` (advances the
  signature from inside the scripted staleness call, with the pane and focus
  held constant so only freshness can decide). Both paired with mutation
  controls: restoring the offered-only sweep and stubbing out the freshness
  check each make the suite exit non-zero.

- **Files affected:** `.aitask-scripts/monitor/monitor_app.py`,
  `tests/test_monitor_concern_action.py`.

## Notes for sibling tasks

- `_concern_sig_offered` is keyed by **followed** pane id (minimonitor keys
  `_last_concern_block_payload` by *shadow* pane id). The monitor's identity for
  a row is the agent, and it survives a shadow respawn — which is what makes the
  retention rule (correction 4) the right one.
- `_tick_shadow_snaps` is the single per-tick shadow resolution. Any further
  per-agent shadow read must consume it, not re-walk `get_shadow_snapshot`.
- **Never compare a raw-capture signature against a stored `-J` one by
  equality.** They are digests of the same block through different capture
  paths and differ whenever it wraps mid-word. Write markers through
  `_mark_concern_sig` (which stores both) and read them with `in`.
- **Snapshot before the await; never read mutable tick state at write time.**
  `_mark_concern_sig` takes `trigger_sig` as a parameter precisely so it cannot
  reach for `_concern_sig_latest`, which the 3 s tick may have advanced to a
  newer block — marking that block seen would lose it silently. Any new writer on
  this path must follow the same rule.
- **Re-check `_focused_pane_id` after any await** before showing something the
  user did not ask for. Anything unsolicited must describe the current screen;
  only an explicit action (like `c`) may keep a pinned target.
- **Never dispatch shadow-capture work with `exclusive=True`.**
  `capture_shadow_text` kills its child only on `TimeoutError`
  (`monitor_core.py:441-450`), so a cancelled worker orphans the subprocess.
  Guard with a busy latch instead.
- **t1216_4** should restore the *"press 'e' to launch one"* wording in
  `action_pick_concerns` when it adds the `e` binding (correction 10), and reuse
  `_current_shadow_pane_id()` / the sync `find_shadow_pane` for its duplicate
  guard.
- `unparsed_concerns_msg` now lives in `monitor_shared`; the
  `minimonitor_app._unparsed_msg` alias is transitional and belongs in the
  `shadow_seam_wrapper_removal` follow-up (**t1289**).

## Risk

### Code-health risk: medium

- `_format_agent_card_text` (1255-1288) and `_reconcile_shadow_state`
  (1785-1850) are per-tick hot paths shared by the pane-list render; the badge
  reads state the same tick writes, so an ordering slip renders a stale badge
  with no visible error · severity: medium · → mitigation: the sync
  `_scan_concern_signatures` is placed between 943 and 945 by construction, and
  the one-test-per-lifecycle-row net plus the `RowRenderTests` byte-identity
  control pin both ends
- Three signature maps keyed by followed-pane-id (`_latest` / `_offered` /
  `_examined`) can drift — an eviction touching two of three, or a badge compared
  against `_examined` instead of `_offered`, gives either a permanently silent
  badge or one that never clears. This is the single most likely defect ·
  severity: medium · → mitigation: a single eviction site, dedicated
  retention-vs-eviction and check-once tests, and an explicit inverted-guard
  control for the `_offered`/`_examined` mix-up (a consolidating refactor was
  proposed and **declined** as premature)
- **Two digests of one block.** The trigger reads `-p -e` and every marker is
  written from `-J`, so the same block can hash two ways
  (`concern_block_signature`'s mid-word-wrap residual). Review found this
  silently defeated *both* dedup maps — per-tick subprocesses and a permanently
  stuck badge — and neither failure is loud. Any future comparison of a raw
  signature against a stored one is exposed to the same trap · severity: medium ·
  → mitigation: a single `_mark_concern_sig` writer storing the (trigger,
  captured) pair, membership tests at every read, and a mid-word-wrap test whose
  precondition (the two digests actually differ) is asserted, with a
  single-string negative control
- **Post-await staleness of pinned identity.** `_offer_concerns` holds a pane id
  across up to 5 s of awaits; review found the toast fired for a
  no-longer-selected agent. The same class of bug reaches any future async work
  added to this path · severity: medium · → mitigation: an explicit re-check of
  both focus and the shadow binding immediately before the notify, with a
  focus-change-during-capture test and a positive control; `action_pick_concerns`
  pins deliberately and that asymmetry is documented at both sites
- **Ambient reads across an await can LOSE a concern block.** Three review
  passes each found a different instance of one root cause — state read at write
  time instead of snapshotted at launch time — and the last (correction 19) was a
  *silent miss*: a newer block marked examined/offered without ever being
  verified or shown. That is the only failure mode here that costs the user
  information rather than merely annoying them, and nothing surfaces it ·
  severity: **high** · → mitigation: `_mark_concern_sig` is a `@staticmethod`
  taking `trigger_sig` explicitly so it *cannot* reach for ambient state; both
  callers snapshot before their first await; `seen` is re-read after it; and the
  newer-block-during-capture test carries a negative control that restores the
  ambient read and must fail
- Two lifecycle guards are correct only because of *where* they release:
  `_concern_pick_busy` (must survive until modal dismissal) and `_offer_busy`
  (must wrap the whole pass). Both failure modes are silent — a stacked modal, or
  an offer path that dies permanently after one exception · severity: medium ·
  → mitigation: the modal-open re-entrancy test, the `finally`-wrapped body, and
  the inverted-guard control that a `finally`-released pick guard fails the suite
- The `minimonitor_app.py` two-line lift (correction 2) lands in a file another
  session is actively editing; a careless `git add` would commit foreign work
  under this task's id or lose that session's edits · severity: medium ·
  → mitigation: explicit path staging + staged-content verification, with
  p1216_1's hunk-extraction procedure as the recorded fallback
- `format_shadow_glyph` is a shared formatter consumed by both apps and pinned by
  a byte-identity assertion · severity: low · → mitigation: keyword-only
  parameter defaulting to `False`, so every existing call site is unchanged by
  construction
- **Upstream, not fixed here:** `capture_shadow_text` has no `CancelledError`
  cleanup (`monitor_core.py:441-450`), so any *future* caller that cancels it
  orphans a subprocess. This task avoids the hazard structurally rather than
  editing a t1216_1 seam minimonitor also depends on · severity: low ·
  → mitigation: recorded in "Notes for sibling tasks" and as an upstream defect
  at Step 8

### Goal-achievement risk: medium

- The monitor is the **first production consumer** of
  `concern_block_signature`. Its reflow stability is a property claim over
  arbitrary tmux wrapping that t1216_1's tests could only sample; if real-world
  wrapping defeats it, badges silently never appear — an invisible failure ·
  severity: medium · → mitigation: concern_signature_reflow_soak (plus, in-task,
  the explicit throttled `-J` probe for the sub-24-column blind spot rather than
  silent absence)
- The badge is one extra column on a card row already carrying a state dot, the
  shadow glyph, a compare-mode glyph, window name, status and a gate summary.
  *Rendered* is not *readable*: at narrow widths the marker may be the first
  thing lost, and the badge is the entire N-agent story — without it the feature
  degrades to "works for the selected agent only" · severity: medium ·
  → mitigation: t1216_5's live walkthrough at real terminal widths with several
  agents; the marker is adjacent to an already-established glyph so it moves with
  it (a dedicated width-budget audit was proposed and **declined** as overlapping
  t1216_5)
- Correction 16 adds one authoritative capture per newly-seen block, a stated
  deviation from the parent plan's "`-J` only on `c` or the narrow fallback". If
  blocks turn out to appear far more often than assumed, per-tick cost rises
  toward minimonitor's · severity: low · → mitigation: `_concern_sig_examined`
  bounds it to once per signature, `_offer_busy` to one in flight, and the
  selected-agent scope keeps it independent of N; the "exactly one capture
  regardless of N" test pins the bound
- Corrections 4 and 16 both amend the parent's PINNED lifecycle table. Both were
  raised in review and 4 was confirmed with the user, but a PINNED table is meant
  to be hard to move · severity: low · → mitigation: Step 0 records both
  amendments in the task file with their reasons, and each amended row has its
  own test, so reverting either is a one-line change
- Everything else (the picker modal, the clipboard seam, the parser, the shadow
  lookup) is reuse of code already proven in production · severity: low ·
  → mitigation: none needed

### Planned mitigations
- timing: after | name: concern_signature_reflow_soak | type: test | priority: medium | effort: medium | addresses: goal-achievement (the monitor is the first production consumer of `concern_block_signature`; a reflow failure hides badges silently) | desc: Soak/property verification that `concern_block_signature` stays stable and discriminating for a real concern block re-rendered across many LIVE tmux pane widths, and that the monitor's badge actually fires — the automated counterpart to t1216_1's in-process sampled widths and to t1216_5's human walkthrough. Should depend on t1216_3.

## Final Implementation Notes

- **Actual work done:** All seven plan steps landed. Step 0 amended the task's
  PINNED badge-lifecycle table (the eviction rule and the definitive-negative
  split) so the task and the code agree. `monitor_shared.py` gained
  `SHADOW_CONCERN_GLYPH`, a keyword-only `has_concerns` on
  `format_shadow_glyph`, and the lifted `unparsed_concerns_msg`;
  `minimonitor_app.py` keeps `_unparsed_msg` as a one-line alias (two lines
  total). `monitor_app.py` gained the imports, seven `__init__` fields,
  `_mark_concern_sig` / `_seen_concern_sigs` / `_scan_concern_signatures` /
  `_has_fresh_concerns`, the card badge, the `_offer_concerns` worker,
  `action_pick_concerns` / `_on_concerns_picked`, and the `c` binding;
  `_reconcile_shadow_state` now publishes `_tick_shadow_snaps` from the walk it
  already did. Docs: a `c` row in `reference.md`, a shadow/concern-marker bullet
  and a new "How to Pick Shadow Concerns" section in `how-to.md`. New
  `tests/test_monitor_concern_action.py` (61 tests).

- **Deviations from plan:** none in design — the nineteen corrections were all
  settled during verification, before any code was written. Two mechanical
  notes:
  1. `main` advanced **eight commits mid-session**, touching every file this
     plan modifies. Re-verified before implementing; only line numbers moved
     (recorded in "Anchor refresh at implementation time"). No correction
     changed, and the t1322 `format_shadow_glyph` docstring ("deliberately
     single-argument") was checked to be about `completed`, which stays
     un-passable — orthogonal to `has_concerns`.
  2. Two defects found in review and fixed under Post-Review Changes 1 (the
     `_examined`-only eviction leak and the missing signature-freshness
     re-check).

- **Issues encountered:**
  - **Two test-harness bugs of my own.** Reading a `@staticmethod` off the class
    yields the plain function, so restoring it after a monkeypatch rebound it as
    an instance method and corrupted 16 later tests — the cleanup must re-wrap
    with `staticmethod(...)`. And the disposition trailer is prose
    (`Disposition: informational.`), not a bracketed tag.
  - **Mutation testing found two real coverage holes.** Ten inverted guards, of
    which eight failed the suite immediately. The two that *passed* were genuine
    gaps: the `_SENTINEL_SAFE_COLS` **carry-forward** boundary in
    `_scan_concern_signatures` (a different site from the probe bound I had
    tested in `_offer_concerns`), and any render-level assertion that a shadowed
    row *without* fresh concerns lacks the marker. Both closed; all ten now fail.
  - **A passing test that proved nothing.** The original agent-exit eviction test
    reached the agent through `c`, which populates both marker maps, so it could
    never see the `_examined`-only leak review found. Its replacement asserts the
    `_offered`-empty precondition explicitly.
  - The runner has no pytest here, so it falls back to unittest; `-p <file>.py`
    discovery is the way to run one file (a `-k` filter silently runs nothing).

- **Key decisions:**
  - **Verify before toasting.** `concern_block_signature` requires a complete
    fence but *not* a parsed concern, so the cheap trigger alone would announce
    "Shadow raised concerns" for an all-malformed block. One authoritative `-J`
    capture per *newly-seen* signature for the *selected* agent buys both honesty
    and minimonitor's real counts, bounded by `_concern_sig_examined` to once per
    signature and by `_offer_busy` to one in flight. The badge — the part that
    scales with N — stays free.
  - **Marker maps store a `frozenset` pair, not a string.** The trigger digests
    the raw `-p -e` capture and every marker is written from `-J`; the documented
    mid-word-wrap residual makes those differ *systematically*, which would both
    re-capture every tick and leave the badge stuck on after a successful pick.
  - **Snapshot before the await, pass it explicitly.** `_mark_concern_sig` is a
    `@staticmethod` taking `trigger_sig` so it cannot reach for
    `_concern_sig_latest`, which the 3s tick may have advanced to a newer block —
    marking that seen would lose a concern block silently.
  - **Four independent post-await re-checks** guard the toast: focus, shadow-pane
    identity, shadow liveness, and signature freshness. Identity is not
    freshness — the same pane can advance to a different block.
  - **A busy latch, never `exclusive=True`.** `capture_shadow_text` kills its
    child only on its own timeout, so a cancelled worker orphans the subprocess.
  - **The pick guard is handed to the modal callback**, because Textual resolves
    app bindings up the focus chain and `ConcernPickerModal` does not bind `c`.

- **Upstream defects identified:**
  - `tests/test_board_work_report.py:483 — WorkReportFullColumnUnderSearchTests::test_hidden_cards_still_listed asserts sl.option_count == len(col_tasks) against the LIVE aitasks/ tree, so any concurrent task-file change during the ~12-minute suite makes it fail (observed 145 != 146). Nondeterministic by construction; unrelated to this task (importing aitask_board loads none of the modules changed here).`

- **Build verification:** the full Python suite ran **2788 tests with this one
  failure**, established as independent of this change rather than assumed: the
  board imports none of `monitor_app` / `monitor_shared` / `minimonitor_app`, and
  the failing assertion compares a live-tree snapshot against a list rebuilt
  later while this very workflow was committing task-status and gate-ledger
  changes. Proceeded per the workflow's unrelated-failure rule.

- **Notes for sibling tasks:**
  - `_tick_shadow_snaps` is the single per-tick shadow resolution; consume it
    rather than re-walking `get_shadow_snapshot`.
  - Never compare a raw-capture signature against a stored `-J` one by equality;
    write markers through `_mark_concern_sig` and read them with `in`.
  - Never dispatch shadow-capture work with `exclusive=True`.
  - Anything unsolicited shown after an await must re-check identity **and**
    freshness; only an explicit user action may keep a pinned target.
  - **t1216_4** should restore the "press 'e' to launch one" wording in
    `action_pick_concerns` when it adds the `e` binding, and reuse
    `_current_shadow_pane_id()` / the sync `find_shadow_pane` for its duplicate
    guard.
  - `unparsed_concerns_msg` now lives in `monitor_shared`; the
    `minimonitor_app._unparsed_msg` alias is transitional and belongs in
    **t1289** (`shadow_seam_wrapper_removal`).
  - The live tmux walkthrough (two agents, shadow on the non-selected one, badge
    without toast → select → toast → `c` → paste) was **not** performed in-task;
    it needs an interactive terminal and belongs to **t1216_5**.
