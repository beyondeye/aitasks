---
priority: high
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [aitask_monitor, shadow, tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1111
created_at: 2026-07-27 22:20
updated_at: 2026-07-27 22:37
---

## Context

First child of **t1216** (make `ait monitor` shadow-aware). Every shadow helper
the full monitor needs currently lives inside `minimonitor_app.py`, shaped
around minimonitor's "there is exactly one followed agent" assumption. t1216's
acceptance criteria require the ported logic to be **shared** — lifted into
`monitor_core.py` / `monitor_shared.py` and imported by both apps — with **no
second implementation** of concern parsing, shadow lookup, or the picker modal.

This child does the lift and **nothing in `monitor_app.py` changes**. Its proof
is that the entire existing minimonitor/shadow test suite still passes against
the lifted implementations. It also adds the one genuinely new piece the
monitor needs: a cheap, reflow-stable concern-block **freshness trigger**, so
badging N agents per tick costs zero extra tmux traffic.

Parent plan: `aiplans/p1216_monitor_shadow_pane_view_and_concern_picker.md`
(read its "Shadow snapshot concurrency contract" and "The perf problem the badge
policy creates" sections — they are binding).

## Key files to modify

- `.aitask-scripts/monitor/monitor_core.py` — receives the tmux-touching shadow
  seams. Already owns `SHADOW_TARGET_OPTION` (L274), `SHADOW_ANALYZED_AT_OPTION`
  (L281), `is_shadow_target` (L284), `_pane_id_num` (L294), `_strip_ansi`
  (L149), `get_shadow_snapshot` (L1483), `get_pane_option` (L1046),
  `get_last_change_wall` (L1062), `commit_snapshots` (L1687).
- `.aitask-scripts/monitor/monitor_shared.py` — receives `format_stale_duration`.
- `.aitask-scripts/monitor/concern_parser.py` — receives `concern_block_signature`.
- `.aitask-scripts/monitor/minimonitor_app.py` — loses the moved bodies, imports
  the shared ones. Behaviour must be identical.
- `.claude/skills/aitask-shadow/concern-format.md` — add the new trigger tier to
  its "Trigger vs. action contract" table.

## What moves where

**To `monitor_core.py`:**

- `_strip_ansi` (L149) → public `strip_ansi` (keep a private alias if internal
  call sites are numerous).
- `match_shadow_pane` (minimonitor L116-142) — pure, parses
  `list-panes -F '#{pane_id}\t#{@aitask_shadow_target}'`, newest-`%N`-wins.
  **Delete** minimonitor's `_pane_id_sort_key` (L104-113) and use the existing
  `_pane_id_num` (L294) — an already-flagged duplication.
- `TmuxMonitor.find_shadow_pane(followed_pane_id)` /
  `find_shadow_pane_async(...)` — from `_shadow_query_args` (L1275),
  `_find_shadow_pane_for_sync` (L1283), `_find_shadow_pane_for` (L1298). Keep
  the single shared args builder so sync and async cannot drift.
- `TmuxMonitor.capture_shadow_text(shadow_pane, *, lines=None)` — from
  `_capture_shadow_text` (L1309). Keep **verbatim**: the `--deep` flag, the
  `_SHADOW_CAPTURE_TIMEOUT = 3.0` ceiling, the `SHADOW_PLAN_CAPTURE_LINES` env
  override, and the `OSError` / timeout-kill / non-zero-rc guards. It shells out
  to `.aitask-scripts/aitask_shadow_capture.sh`, whose `-J` wrap-join is the
  parser's contract — do NOT reroute it through the tick capture
  (`_capture_args`, L1452, is `-p -e` with no `-J`).
- `TmuxMonitor.refresh_shadow_snapshot(followed_pane_id)` — NEW. Re-capture one
  bound shadow and merge it into `_shadow_snapshots`. See the concurrency
  contract below.
- `compute_shadow_staleness(monitor, shadow_pane, followed_pane, eps)` — from
  `_update_shadow_freshness` (L1368-1418). Returns the tri-state
  (`True` stale / `False` current / `None` unknown) plus the analyzed-at epoch.
  Its failure-safe semantics are load-bearing and must survive intact:
  unreadable stamp, malformed float, and not-yet-observed followed pane all
  **preserve** the prior state and never clear a standing warning; an empty
  stamp means "not analyzed yet" → `False` + clear.

**To `monitor_shared.py`:** `format_stale_duration` (minimonitor's
`@staticmethod` at L1420) — pure; output shapes `"{s}s"` / `"{m}m{s:02d}s"` /
`"{h}h{m:02d}m"`.

**Stays in `minimonitor_app.py`:** `_find_own_agent_snapshot` (L525) — it
resolves the followed agent from minimonitor's *own* window index and is
intrinsically minimonitor-shaped. Every lifted API must take an explicit
`followed_pane_id` instead. `_set_shadow_stale_banner` (L1356) also stays (it is
hard-wired to `#mini-shadow-stale`) but takes its text from the shared formatter.

## PINNED: shadow snapshot concurrency contract

`_shadow_snapshots` is rebuilt **wholesale** by `commit_snapshots`
(monitor_core.py:1743), and `capture_pane_classified_async` reserves a new
**global** generation before its await (L1572). A naive per-shadow refresh would
therefore both starve the 3 s full refresh and clobber every other agent's
shadow entry. Three binding rules:

1. `refresh_shadow_snapshot` **never calls `_next_generation()`**. It reserves
   from a separate monotonic `_shadow_capture_generation`. It therefore cannot
   invalidate a full refresh — the agent-facing `_pane_cache` / snapshot path is
   untouched by it.
2. `_shadow_snapshots` entries are **stamped** with the shadow generation they
   were fetched at, and written **per key**. A write lands only if its stamp is
   newer than the entry it would replace. `commit_snapshots` is amended to stamp
   the entries it rebuilds and to keep a newer-stamped existing entry for keys
   present in both. The two paths are then order-independent in either
   interleaving.
3. **Only the full refresh may delete.** Discovery is authoritative for
   existence: `commit_snapshots` drops keys absent from its own discovery, and a
   single-shadow merge is **dropped** when its key is no longer present — it can
   never resurrect a shadow the full refresh just removed. Fail-closed.

Pass `pane=` to `capture_pane_content_async` (the t1133 kwarg at L1533-1550) so
the shadow bypasses `_pane_cache` — shadows must stay out of it.

## PINNED: `concern_block_signature`

```python
def concern_block_signature(raw_text: str) -> str | None:
    """Cheap freshness trigger over a NON-wrap-joined, ANSI-bearing tick
    capture. Returns a REFLOW-STABLE digest of the last block region, or None
    when no complete block is present. Trigger only — never parse its input
    into forwardable concerns; the picker re-captures with -J."""
```

Lives in `concern_parser.py` as a **third strictness tier** alongside
`parse_concerns` (forgiving) and `has_concern_block` (strict), documented in the
module docstring's existing strictness table. It exists so the monitor can badge
N agents from `shadow_snap.content` — data the tick already captured — at zero
extra tmux traffic.

**Normalisation:** strip ANSI, then `re.sub(r"\s+", " ", region).strip()`, then
digest.

- Collapsing whitespace to *nothing* was considered and **rejected**: fully
  reflow-proof but it erases token boundaries, so `"needs review"` and
  `"needsreview"` collide and a genuinely changed concern is silently missed.
- Normalising to one space is exact for trailing row padding and for wraps at a
  word boundary. A wrap landing **mid-word** injects a space that was not in the
  source, so the same block re-rendered at a different pane width can re-hash.
  This residual is deliberate and fails in the safe direction: **at most one
  spurious re-offer** (a badge, and one toast if selected — nothing lost or
  forwarded), never a missed real change. Pin it with a test so nobody later
  "fixes" it back into a collision.

**Narrow panes:** the sentinels are 21 (`===AITASK-CONCERNS===`) and 18
(`===END-CONCERNS===`) chars, so a pane narrower than
`_SENTINEL_SAFE_COLS = 24` can wrap them and hide a block entirely. Export the
constant; t1216_3 owns the authoritative-capture fallback that consumes it.

## Verification

New `tests/test_shadow_seam.py`, following the `_FakeMon` idiom from
`tests/test_minimonitor_concern_action.py` (L64-104) and the scripted-coroutine
`_make_monitor` fixture from `tests/test_monitor_shadow_status.py` (L78-110) —
real `TmuxMonitor`, `_run_offloaded` overridden to run synchronously, no tmux,
no sleeps. Cover:

- `match_shadow_pane` — bind, miss, whitespace-only target ignored, newest wins.
- `find_shadow_pane` sync + async; `capture_shadow_text` argv (`--deep`, script
  path) and the `SHADOW_PLAN_CAPTURE_LINES` env override.
- `compute_shadow_staleness` — stale / current / within-eps / no-stamp, and each
  preserve-on-failure case.
- `concern_block_signature` — **stable** (same block with trailing padding, ANSI
  colour runs, and word-boundary wraps at several widths → identical digest);
  **discriminating** (`"needs review"` vs `"needsreview"` → different, as does
  any changed priority / region / body); **residual pinned** (mid-word wrap →
  different digest, asserted as known behaviour with the consequence named in
  the docstring); **narrow pane** (`< _SENTINEL_SAFE_COLS`, sentinel wraps →
  `None`).
- **Concurrency** — a shadow refresh interleaved inside a full refresh in *both*
  orders leaves the newer content for the refreshed key and every other key
  intact; a merge is dropped after its shadow is removed by a full refresh; and
  a negative control proving the shadow path never bumps `capture_generation`.

Regression net (must pass **unmodified** except for import-path updates — this
is the whole point of the child):

```bash
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_tui_clipboard_seam.sh
```

specifically `tests/test_minimonitor_concern_action.py`,
`tests/test_minimonitor_shadow_pick.py`, `tests/test_concern_parser.py`,
`tests/test_monitor_shadow_status.py`.
