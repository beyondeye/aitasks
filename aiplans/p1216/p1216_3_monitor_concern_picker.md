---
Task: t1216_3_monitor_concern_picker.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Sibling Tasks: aitasks/t1216/t1216_1_shared_shadow_seam.md, aitasks/t1216/t1216_2_monitor_shadow_zone.md, aitasks/t1216/t1216_4_monitor_shadow_spawn.md
Base branch: main
Output branch: main
---

# p1216_3 — Concerns in the full monitor (badge + toast + picker)

Depends on **t1216_1** (`concern_block_signature`, `_SENTINEL_SAFE_COLS`,
`capture_shadow_text`, `compute_shadow_staleness`) and **t1216_2**
(`_current_shadow_pane_id`, the per-tick shadow resolution).

## Goal

From `ait monitor`, shadow concerns can be parsed and picked through the
existing `ConcernPickerModal`, with the same clipboard payload semantics as
minimonitor. Fresh concerns are surfaced across N agents without polling cost.

`ConcernPickerModal` already lives in `monitor_shared.py:593` and its docstring
already claims *"Shared by the full monitor and minimonitor (both push it)"* —
`monitor_app.py` just never pushes it. Make that true; write no second modal.

## Step 1 — the per-tick trigger (no subprocess)

Minimonitor's `_maybe_offer_concerns` (L1494) runs the expensive `-J` subprocess
capture **every tick**. With N agents that is N spawns per tick and would
violate the parent's per-tick-cost acceptance criterion.

In `_refresh_data` (`monitor_app.py:702-781`), after `commit_snapshots`, for
each agent snapshot that has a bound shadow (`get_shadow_snapshot(pane_id)` —
already resolved once per agent per tick by t1216_2 and by
`_format_agent_card_text` at L1028; resolve it **once** and share):

```python
sig = concern_block_signature(shadow_snap.content)   # already-captured content
```

Zero extra tmux traffic — `shadow_snap.content` came from the same async gather
that captures the agents (`capture_all_classified_async`, L1657-1665).

State: `self._concern_sig_offered: dict[str, str] = {}` keyed by **followed**
pane id.

### Narrow-pane fallback

`_SENTINEL_SAFE_COLS` is 24 because the block sentinels are 21
(`===AITASK-CONCERNS===`) and 18 (`===END-CONCERNS===`) chars — a narrower pane
wraps them and hides the block from the cheap detector entirely.

When `shadow_snap.pane.width < _SENTINEL_SAFE_COLS` **and** `sig is None`, fall
back to the authoritative `capture_shadow_text` **for the selected agent only**
(`pane_id == self._focused_pane_id`), throttled to every other tick (reuse the
`_shadow_freshness_tick % 2` cadence minimonitor uses at L1522-1526). That
bounds the cost to at most one subprocess per tick — the same as minimonitor
today — and never scales with N. Compute the signature from that capture so the
lifecycle below is unchanged.

## Step 2 — badge lifecycle (PINNED)

The badge is **derived, never a latched flag**:

```python
def _has_fresh_concerns(self, followed_pane_id: str, sig: str | None) -> bool:
    return sig is not None and sig != self._concern_sig_offered.get(followed_pane_id)
```

| Event | `_concern_sig_offered` | Badge |
|---|---|---|
| New block, signature differs from the stored one | unchanged | **on** (+ toast if selected) |
| `c` pressed → `-J` capture returns `None` (failure/timeout) | **unchanged** | stays **on** |
| `c` pressed → capture ok but 0 concerns parsed, or still head-truncated after the deep retry | **unchanged** | stays **on** |
| `c` pressed → modal actually pushed with ≥1 concern | set to the signature of the **captured** text | off |
| Picker cancelled (Esc / Cancel) | already set at push | stays off — the user saw them |
| Shadow re-issues a *different* block | differs again | **on** again |
| Block scrolls out of the capture window (`sig is None`) | **retained** | off |
| That same block scrolls back in | matches retained | stays off (no re-toast) |
| Followed pane loses its shadow entirely | entry **evicted** | off |

Three decisions that are easy to get wrong and are therefore spelled out:

1. **Set the marker only once `ConcernPickerModal` has actually been pushed with
   ≥1 concern** — not on the keypress. Clearing at keypress would hide a block
   the user never saw whenever the capture fails, times out, or parses nothing,
   which is exactly when the badge matters most.
2. **Set it at push, not on confirm.** A user who opens the list and forwards
   nothing has seen the block; re-toasting them would be noise.
3. **Store the signature of the text the picker actually captured**, recomputed
   from the `-J` capture — not the tick signature that raised the badge. The
   shadow may have emitted more between badge and keypress, and storing the
   older signature would leave the newer block permanently un-offered.

Retaining the entry when `sig is None` (rather than clearing it) is what stops a
block flickering in and out of the capture window from re-firing forever; it
matches minimonitor, which never clears `_last_concern_block_payload` on
absence. Evict the entry only when the followed pane loses its shadow, in the
same `_refresh_data` prune that already drops stale `_preview_scroll_state`
entries (L734-745).

## Step 3 — the card badge

`_format_agent_card_text` (`monitor_app.py:1022-1054`) already calls
`get_shadow_snapshot` (L1028) and `format_shadow_glyph` (L1037). Extend the
shared formatter in `monitor_shared.py` (L86-92) rather than inlining markup:

```python
SHADOW_CONCERN_GLYPH = "!"   # or similar; single column

def format_shadow_glyph(shadow_snap, *, has_concerns: bool = False) -> str:
    if shadow_snap is None:
        return ""
    body = SHADOW_GLYPH + (SHADOW_CONCERN_GLYPH if has_concerns else "")
    return f"[{_state_color(shadow_snap)}]{body}[/]"
```

The default `has_concerns=False` keeps minimonitor's call site (`_agent_card_text`)
working untouched.

**Non-shadowed rows must stay byte-identical** — the `None` branch still returns
`""` with no placeholder, as t1133 established and
`tests/test_monitor_shadow_status.py::RowRenderTests` asserts by comparing
against a `{}`-map render.

## Step 4 — the toast

Only when the fresh agent **is** the selected one
(`pane_id == self._focused_pane_id`), so at most one popup regardless of N:

```
Shadow raised concerns — press 'c' to pick
```

with the suffix `" (⚠ STALE — agent moved on)"` when `compute_shadow_staleness`
(t1216_1) reports `True` for that pane. Fire once per signature — the
`_concern_sig_offered` comparison already gives that, but the toast must not
re-fire on every tick while the badge is on, so track the last **toasted**
signature separately from the last **offered** one (a block stays badged until
picked, but is toasted only when it first appears).

## Step 5 — `c` → `action_pick_concerns`

```python
async def action_pick_concerns(self) -> None:
```

1. Resolve the selected agent (`self._focused_pane_id` → `self._snapshots`);
   warn `"Focus an agent pane first"` if absent.
2. Resolve its shadow via `_current_shadow_pane_id()` (t1216_2); warn
   `"No shadow agent running — press 'e' to launch one"` if absent.
3. `text = await self._monitor.capture_shadow_text(shadow_pane)` (`-J`,
   `--deep`); on `None` warn `"Could not read the shadow pane"` (severity
   `warning`) and **return without touching `_concern_sig_offered`**.
4. `concerns = parse_concerns(text)`.
5. If empty and `block_head_truncated(text)`: re-capture once with
   `lines=_SHADOW_DEEP_RETRY_LINES`; if still empty, notify
   `_SHADOW_TRUNCATED_MSG` (severity `warning`) and **return without touching
   `_concern_sig_offered`**.
6. If still empty: notify `"No concerns detected on the shadow pane"` and
   **return without touching `_concern_sig_offered`**.
7. `stale = compute_shadow_staleness(...)` — reuse the tick-computed value
   rather than spending a second live read, as minimonitor does at L1475.
8. `self._concern_sig_offered[pane_id] = concern_block_signature(text)` — set
   **here**, immediately before the push, per Step 2 decision 3. Note the
   signature is computed from the `-J` text; the function normalises whitespace
   so a `-J`-joined and a soft-wrapped rendering of the same block agree at word
   boundaries.
9. `self.push_screen(ConcernPickerModal(concerns, narrow=False, stale=stale), callback=self._on_concerns_picked)`

   `narrow=False` — the monitor is full-width, unlike minimonitor's 40-column
   sidebar.

```python
def _on_concerns_picked(self, selected: list | None) -> None:
    if not selected:
        return
    copy_to_system_clipboard(self, build_clipboard_payload(selected))
    self.notify("Concerns copied to clipboard.")
```

**`tui_clipboard.copy_to_system_clipboard`, never `app.copy_to_clipboard`** —
`tests/test_tui_clipboard_seam.sh` enforces this, and a bare OSC 52 from a
non-visible tmux window silently never reaches the system clipboard.
`monitor_app.py` has no clipboard usage today, so this import is new.

The modal is pure UI: it builds no payload and touches no clipboard (its dismiss
contract is `list[Concern]` on Enter/OK, all concerns on `A`, `None` on Esc /
Cancel). The monitor never types the payload into the agent — the user pastes
it. Nothing reaches the clipboard until the user confirms.

Binding: `Binding("c", "pick_concerns", "Concerns")` — `c` is free in the
monitor's `BINDINGS` (L391-410) and matches minimonitor's key. It is active only
in `PANE_LIST`; in `PREVIEW` / `SHADOW`, `check_action` disables it and `on_key`
forwards the keystroke to tmux, which is correct.

## Step 6 — docs

- `website/content/docs/tuis/monitor/reference.md` — add `c` to the keybinding
  table and the badge to the card-contents description.
- `website/content/docs/tuis/monitor/how-to.md` — a "Picking shadow concerns"
  section mirroring `website/content/docs/tuis/minimonitor/how-to.md:119-135`,
  including the auto-offer note and the two configuration pointers.

## Verification

New `tests/test_monitor_concern_action.py`, following
`tests/test_minimonitor_concern_action.py`'s harness: `MonitorApp.__new__`
(bypassing `App.__init__`), hand-set `_monitor` / `_snapshots` /
`_concern_sig_offered`, and **`spy_`-prefixed** lambdas replacing `notify` /
`push_screen` / `copy_to_clipboard` (the prefix avoids colliding with read-only
Textual `App` properties such as `clipboard`). `_async_return(value)` (L58) for
the coroutine stubs.

- Modal pushed with the parsed concerns; **nothing on the clipboard before
  confirm**; invoking the callback with a selection writes exactly
  `build_clipboard_payload(selected)`; cancel writes nothing.
- Deep retry on head-truncation (`captures == [None, _SHADOW_DEEP_RETRY_LINES]`);
  `_SHADOW_TRUNCATED_MSG` when still truncated; a **negative control** that a
  genuine absence of concerns yields the plain informational message and no
  re-capture.
- Toast fires once per signature and **only for the selected agent**.
- Badge appears for a **non-selected** agent with fresh concerns — the N-agent
  case minimonitor structurally cannot cover.
- A test asserting the per-tick path spawns **no** subprocess (monkeypatch
  `asyncio.create_subprocess_exec` with a recorder and assert zero calls across
  several ticks with several shadowed agents).
- **One test per row of the Step 2 table.** In particular the three
  capture-failure negative controls (capture `None`; zero concerns parsed; still
  head-truncated after the deep retry) each asserting `_concern_sig_offered` is
  **untouched** and the badge still renders; the scroll-out / scroll-back
  no-re-toast case; eviction on shadow loss; and the case where the shadow
  emitted a *newer* block between badge and keypress, asserting the **captured**
  signature is stored (so the newer block is not left permanently un-offered).
- Narrow-pane fallback: fires for the selected agent only, throttled to every
  other tick, with a **negative control** that a wide shadow pane never triggers
  it.
- No-shadow and no-block negative controls.

```bash
bash tests/run_all_python_tests.sh
bash tests/test_tui_clipboard_seam.sh
bash tests/test_no_raw_tmux.sh
```

Manual, **from a shell outside the main aitasks tmux session**: run two agents,
spawn a shadow on the non-selected one, have it emit a concern block, and
confirm the badge appears on that agent's card with no toast; select it and
confirm the toast; press `c`, tick a subset, and confirm the clipboard payload
pastes correctly into the agent.

## Notes for sibling tasks

- `_concern_sig_offered` is keyed by **followed** pane id, not shadow pane id
  (minimonitor keys `_last_concern_block_payload` by shadow pane id) — the
  monitor's identity for an agent row is the followed pane, and a respawned
  shadow for the same agent should not silently re-offer an identical block.
