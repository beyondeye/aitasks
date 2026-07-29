---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t1216_2]
issue_type: feature
status: Implementing
labels: [aitask_monitor, shadow, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus5
created_at: 2026-07-27 22:22
updated_at: 2026-07-29 22:09
---

## Pick-time safety guard — SAFE from your normal working tmux

**Risk to running code agents: LOW.** This child's entire tmux surface is
**read-only**, so it can be picked and implemented from inside the same tmux
session where your code agents are running.

What it touches:
- `capture-pane -p -J` via `aitask_shadow_capture.sh` (gateway-routed). That
  script never kills, splits, resizes or closes anything; its only mutation is
  `set-option -p @aitask_shadow_analyzed_at` on **its own** `$TMUX_PANE`, behind
  a double guard, and it never runs from a monitor-side capture.
- Clipboard via `tui_clipboard.copy_to_system_clipboard`.
- No pane creation, no `kill-*`, no hook or `remain-on-exit` registration.

Two conditions to preserve:
- **Any live-tmux test must isolate itself.** Use
  `require_isolated_tmux()` from `tests/lib/tmux_isolation.sh` (unsets `TMUX` /
  `TMUX_PANE`, pins `TMUX_TMPDIR`, sets `AITASKS_TMUX_SOCKET=""`), or follow
  `tests/test_minimonitor_concern_smoke.py`, which pins its own socket
  (`ait_t1187_smoke`) and session name and only ever `kill-session`s that.
- **Do not call `attach_shadow_cleanup_hook` from this child.** It belongs to
  t1216_4 and is the one genuinely destructive seam in the shadow family (see
  that task's guard).

## Context

Third child of **t1216** (make `ait monitor` shadow-aware). Depends on
**t1216_1** (shared shadow seam, incl. `concern_block_signature`) and
**t1216_2** (the `SHADOW` zone).

Delivers the parent's third acceptance criterion: from `ait monitor`, shadow
concerns can be parsed and picked through the existing `ConcernPickerModal`,
with the same clipboard payload semantics as minimonitor
(`build_clipboard_payload` + `DEFAULT_PREAMBLE`).

`ConcernPickerModal` already lives in `monitor_shared.py` (L593) and its
docstring already claims *"Shared by the full monitor and minimonitor (both push
it)"* — but `monitor_app.py` never pushes it. This child makes that true.

**Auto-offer policy decided with the user:** *card badge + toast for the
selected agent only.* Every agent whose shadow has a fresh concern block gets a
marker on its pane-list card, so nothing is missed across N agents; the toast
fires only for the currently selected agent, so there is at most one popup.

Parent plan: `aiplans/p1216_monitor_shadow_pane_view_and_concern_picker.md`.

## Key files to modify

- `.aitask-scripts/monitor/monitor_app.py` — the tick hook, the badge, the
  toast, `action_pick_concerns`, the `c` binding.
- `.aitask-scripts/monitor/monitor_shared.py` — extend `format_shadow_glyph`
  (L86) or add a sibling formatter for the concern marker.
- `website/content/docs/tuis/monitor/reference.md` — keybinding table.
- `website/content/docs/tuis/monitor/how-to.md` — a "Picking shadow concerns"
  section mirroring `website/content/docs/tuis/minimonitor/how-to.md` (L119-135).

## PINNED: the per-tick path must spawn no subprocess

Minimonitor runs the expensive `-J` subprocess capture **every tick** in
`_maybe_offer_concerns` (L1494). With N agents that is N spawns per tick, which
would violate the parent's acceptance criterion on per-tick cost.

Instead, per tick, for each agent with a bound shadow run
`concern_block_signature` (from t1216_1) over `shadow_snap.content` — data the
tick already captured, **zero extra tmux traffic**. Keep
`_concern_sig_offered: dict[followed_pane_id, str]`.

The authoritative `-J` capture (`TmuxMonitor.capture_shadow_text`) runs **only**
when the user presses `c`, or via the narrow-pane fallback below.

**Narrow-pane fallback.** A shadow pane narrower than `_SENTINEL_SAFE_COLS`
(24, exported by t1216_1) can wrap the block sentinels and hide a block from the
cheap detector. When `shadow_snap.pane.width < _SENTINEL_SAFE_COLS` **and** the
cheap detector reports no block, fall back to the authoritative capture **for
the selected agent only**, throttled to the shadow-freshness cadence (every
other tick). That bounds the cost to at most one subprocess per tick — the same
as minimonitor today — and never scales with N.

## PINNED: badge lifecycle

The badge is **derived, never a latched flag**:

```
badge_on(pane) == sig is not None and sig not in _concern_sig_offered.get(pane, frozenset())
```

Membership, not equality: the on-screen signature comes from the raw tick
capture (`-p -e`) while the stored one is recomputed from the `-J` capture, and
`concern_block_signature`'s documented mid-word-wrap residual makes those two
digests differ systematically for the same block. Each marker therefore records
**both** digests (see `p1216_3` correction 17).

| Event | `_concern_sig_offered` | Badge |
|---|---|---|
| New block, signature differs from the stored one | unchanged | **on** (+ toast if selected **and** it verifies) |
| `c` pressed → `-J` capture returns `None` (failure/timeout) | **unchanged** | stays **on** |
| `c` pressed → capture shows **no complete block** (still head-truncated after the deep retry) | **unchanged** | stays **on** |
| `c` pressed → capture shows a **complete block yielding nothing forwardable** | set to the **captured** sig pair | off |
| `c` pressed → modal actually pushed with ≥1 concern | set to the **captured** sig pair | off |
| Picker cancelled (Esc / Cancel) | already set at push | stays off — the user saw them |
| Shadow re-issues a *different* block | differs again | **on** again |
| Block scrolls out of the capture window (`sig is None`) | **retained** | off |
| That same block scrolls back in | matches retained | stays off (no re-toast) |
| Shadow dies / respawns for the same agent | **retained** | off, and off again on respawn |
| Followed **agent pane** leaves the snapshot map | entry **evicted** | row gone |

**Two rows amended during plan verification (2026-07-29), both decided
deliberately rather than drifted into:**

1. *Shadow loss no longer evicts.* The original row ("followed pane loses its
   shadow entirely → evicted") contradicted this task's own "Notes for sibling
   tasks", which requires that a respawned shadow **not** silently re-offer an
   identical block — eviction produces exactly that re-offer. It is also not
   cleanly implementable: `get_shadow_snapshot()` returns `None` both for a dead
   shadow and for a one-tick capture blip (t1133's `LifecycleTests` establish
   blips are normal), so literal eviction needs a per-agent grace counter or it
   re-offers on every blip. **Confirmed with the user:** retain across shadow
   loss; evict only when the agent pane itself leaves the snapshot map. The badge
   still goes off meanwhile, because it derives from the *current* signature.
2. *A definitive negative now clears the badge.* The original row lumped "parse
   yields 0 concerns" together with capture failure. Since t1274, a complete
   block that yields nothing forwardable produces a **specific** message
   (`unparsed_concerns_msg`) — the user has been told exactly what is in it and
   it will never become parseable, so leaving the badge lit strands it forever.
   The indeterminate cases (capture failed, or no complete block in the window)
   still leave the marker untouched, because there we learned nothing.

The marker is set only once the outcome is **definitive** — never on the
keypress. Clearing at keypress would hide a block the user never saw whenever
the capture fails or times out, which is exactly when the badge matters most.
Setting it at push rather than on confirm is still deliberate: a user who opens
the list and forwards nothing has seen the block, so re-toasting would be noise.

Store the signature **of the text the picker actually captured** (recomputed
from the `-J` capture) alongside the tick signature that raised the badge — the
former because the shadow may have emitted more between badge and keypress, and
storing only the older one would leave the newer block permanently un-offered;
the latter because the two capture paths hash the same block differently.

The trigger signature is **snapshotted before the capture await and passed
explicitly** to the marker writer. Re-reading it afterwards would let the 3s
refresh substitute a *newer* block's signature, marking a block as offered that
was never presented — a silent miss (`p1216_3` correction 19).

Retaining the entry on `sig is None` rather than clearing it is what stops a
block flickering in and out of the capture window from re-firing forever, and it
matches minimonitor, which never clears `_last_concern_block_payload` on absence.

## Implementation

- **Badge:** a fresh signature marks the agent's card in
  `_format_agent_card_text` (monitor_app L1022-1054, which already calls
  `get_shadow_snapshot` at L1028 and `format_shadow_glyph` at L1037). Extend the
  shared formatter so the `◆` gains a concern marker. **Non-shadowed rows must
  stay byte-identical**, as t1133 established and
  `tests/test_monitor_shadow_status.py::RowRenderTests` asserts.
- **Toast:** only when the fresh agent is `self._focused_pane_id` —
  `"Shadow raised concerns — press 'c' to pick"`, once per signature, with the
  `" (⚠ STALE — agent moved on)"` suffix when `compute_shadow_staleness` (from
  t1216_1) reports stale.
- **`c` → `action_pick_concerns`:** resolve the selected agent's shadow via the
  shared lookup, run `capture_shadow_text` (`-J`, `--deep`), `parse_concerns`,
  then the `block_head_truncated` → `_SHADOW_DEEP_RETRY_LINES` deep retry, then
  `push_screen(ConcernPickerModal(concerns, narrow=False, stale=...))`.
  `narrow=False` because the monitor is full-width, unlike minimonitor.
- **On confirm:** `build_clipboard_payload(selected)` →
  **`tui_clipboard.copy_to_system_clipboard(self, payload)`**. Never
  `app.copy_to_clipboard` — `tests/test_tui_clipboard_seam.sh` enforces this,
  and `monitor_app.py` has no clipboard usage today so the import is new. The
  modal is pure-UI: it builds no payload and touches no clipboard; the caller
  owns both. Nothing is written to the clipboard until the user confirms, and
  the monitor never types the payload into the agent — the user pastes it.
- **Binding:** `c` is free in the monitor. It is only active in `PANE_LIST` — in
  `PREVIEW` / `SHADOW`, keys are forwarded to tmux, which is correct.

## Verification

New `tests/test_monitor_concern_action.py`, following
`tests/test_minimonitor_concern_action.py`'s harness: `MonitorApp.__new__`
(bypassing `App.__init__`), hand-set `_monitor` / state, and `spy_`-prefixed
lambdas replacing `notify` / `push_screen` / `copy_to_clipboard` (the `spy_`
prefix avoids colliding with read-only Textual `App` properties). Cover:

- Modal pushed with the parsed concerns; **nothing on the clipboard before
  confirm**; confirm writes `build_clipboard_payload(selected)`; cancel writes
  nothing.
- Deep retry on head-truncation; the `_SHADOW_TRUNCATED_MSG` warning when still
  truncated.
- Toast fires once per signature and **only for the selected agent**.
- Badge appears for a **non-selected** agent that has fresh concerns — the
  N-agent case minimonitor cannot cover.
- A test asserting the per-tick path spawns **no** subprocess.
- **One test per row of the badge-lifecycle table**, in particular the three
  capture-failure negative controls (capture `None`; zero concerns parsed; still
  head-truncated after the deep retry) each asserting `_concern_sig_offered` is
  **untouched** and the badge still renders; the scroll-out / scroll-back
  no-re-toast case; eviction on shadow loss; and a shadow that emitted a *newer*
  block between badge and keypress storing the **captured** signature.
- Narrow-pane fallback firing for the selected agent only, throttled, with a
  negative control that a wide shadow pane never triggers it.
- No-shadow and no-block negative controls.

```bash
bash tests/run_all_python_tests.sh
bash tests/test_tui_clipboard_seam.sh
bash tests/test_no_raw_tmux.sh
```

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-29T19:09:49Z status=pass attempt=1 type=human
