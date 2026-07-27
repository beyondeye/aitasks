---
Task: t1216_1_shared_shadow_seam.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Sibling Tasks: aitasks/t1216/t1216_2_monitor_shadow_zone.md, aitasks/t1216/t1216_3_monitor_concern_picker.md, aitasks/t1216/t1216_4_monitor_shadow_spawn.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-28 00:06
---

# p1216_1 — Shared shadow seam (headless)

## Context

`ait monitor` is the best TUI for switching between sessions, but it is not
shadow-aware: the shadow companion is reachable only from `ait minimonitor`, so
a shadow-heavy workflow is forced to give up multi-session switching (t1216).

Every shadow helper the full monitor needs lives today inside
`minimonitor_app.py`, shaped around minimonitor's "there is exactly one followed
agent" assumption. t1216's acceptance criteria require the ported logic to be
**shared** — lifted into `monitor_core.py` / `monitor_shared.py` and imported by
both apps — with **no second implementation** of concern parsing, shadow lookup,
or the picker modal.

This first child does the lift and **nothing in `monitor_app.py` changes**
(verified: `monitor_app.py` contains zero references to any lifted symbol). Its
proof of correctness is that the entire existing minimonitor/shadow test suite
still passes against the lifted implementations. It also adds the one genuinely
new piece the monitor needs: a cheap, reflow-stable concern-block **freshness
trigger**, so badging N agents per tick costs zero extra tmux traffic.

Parent plan: `aiplans/p1216_monitor_shadow_pane_view_and_concern_picker.md` —
its "Shadow snapshot concurrency contract" and "The perf problem the badge
policy creates" sections are binding.

## Plan verification (2026-07-27)

Re-verified against current `main` before implementation. Sources last changed
2026-07-24 (`979b88968`), so anchors held: all monitor_core / minimonitor
anchors are exact or within ±3 lines, `_last_block_region(text, *,
require_close: bool)` exists as assumed (concern_parser.py:101), the `pane=`
kwarg on `capture_pane_content_async` does bypass `_pane_cache`
(monitor_core.py:1552-1553), `_next_generation()` is reserved before the await
(monitor_core.py:1572-1573), `_shadow_snapshots` is rebuilt wholesale
(monitor_core.py:1730/1743), and `tests/run_all_python_tests.sh` auto-discovers
a new `test_*.py` with a propagating exit code.

Nine corrections were folded into the steps below. The first five came from
verifying the plan against the source; items 6-9 came from a second review pass
and all concern the Step 5 concurrency design.

1. **`strip_ansi` placement.** The original plan had `concern_parser` import it
   from `monitor_core`, which would falsify the parser's documented purity and
   make `tests/test_concern_parser.py` (flat-imports with only
   `.aitask-scripts/monitor` on `sys.path`) order-dependent. → new pure
   `monitor/ansi_utils.py`.
2. **Lift shape.** The original plan put `find_shadow_pane` /
   `capture_shadow_text` on `TmuxMonitor` as methods. The existing tests use a
   `_FakeMon` exposing **only** `tmux_run` / `tmux_run_async`
   (test_minimonitor_concern_action.py:64-79, test_minimonitor_shadow_pick.py:41-50),
   so methods would break three test files and forfeit the characterization net
   that is this child's proof. → module-level functions taking a duck-typed
   `monitor` first arg, plus one-line delegating seams left on
   `MiniMonitorApp`. Only `refresh_shadow_snapshot` (which needs real internals
   and has no legacy tests) becomes a `TmuxMonitor` method.
3. **Regression net was incomplete.** `tests/test_minimonitor_concern_smoke.py`
   (live-tmux, drives the REAL capture through `app._capture_shadow_text`) was
   missing, as were `CaptureArgvTests` (pins the `--deep` argv) and
   `LaunchShadowGuardTests` (pins the *sync* lookup) inside
   `test_minimonitor_concern_action.py`.
4. **No docstring "strictness table" exists.** concern_parser.py:42-51 is
   *prose* ("Two consumers, two strictnesses"), not a table. The new tier is
   added as a table replacing that prose.
5. **Two doc lists are already stale** and are corrected while in the file:
   `concern-format.md` "Where it lives" omits `contains_any_concern_block` and
   `block_head_truncated`; `aidocs/framework/shadow_agent.md:146` says the
   staleness compare lives "in minimonitor", which the lift makes untrue.

A second review pass (shadow agent, 2026-07-27) raised four concerns against the
Step 5 concurrency design. All four were verified valid against the source and
are addressed by rules 1-5 in Step 5, each with a dedicated test:

6. **Stamp origin was undefined** — the draft used a *separate* shadow counter
   while leaving `commit_snapshots`' stamp source unstated. A commit-time stamp
   lets a full refresh that captured earlier but committed later overwrite newer
   shadow content; two counters make stamps incomparable. → one shared
   `_shadow_write_seq`, reserved by both writers.
7. **Presence ≠ identity** — the draft merged whenever the followed-pane key was
   still present, so a shadow replaced mid-await (`%8` dies, `%12` spawns for the
   same agent) would be clobbered by the dead pane's content. → the merge must
   also match the pane id it actually captured.
8. **Bookkeeping ran ahead of the guards** — `_apply_bookkeeping` (L1394) is the
   sole writer of `_last_content` / `_last_change_time` and its docstring
   requires the caller to check its reserved generation *before* calling it. A
   rejected late refresh would still have reset the shadow's idle clock. → checks
   strictly precede bookkeeping.
9. **Failure policy was asymmetric by accident** — the full refresh hides a
   shadow on transient capture failure, while the fast path would silently retain
   it. → made explicit: the fast path never hides; staleness is bounded by one
   full-refresh interval.

A third review pass raised one further concern, also verified valid:

10. **The reservation point was still too early** — item 6's fix put the full
    batch's reservation next to `gen = self._next_generation()` (L1653), but
    `capture_all_classified_async` **awaits discovery** (L1654) before reading any
    shadow pane (L1661). A fast refresh completing entirely inside that discovery
    window would take a higher seq than a full refresh that reads the same pane
    later, losing the newer content. → the full batch reserves **after** discovery
    and immediately before the raw-capture `gather`, making the seq a proxy for
    *read* order on both paths; the residual sub-window is stated in rule 1 and
    the fix is pinned by a discovery-window test with a negative control.

Confirmed non-issues: `tests/test_no_raw_tmux.sh` cannot trip on the
`aitask_shadow_capture.sh` shell-out (its Python pattern needs a `"tmux"` argv
head, and `monitor_core.py` is allowlisted anyway); `_strip_ansi` has only two
real call sites (monitor_core.py:189,193), so no compatibility alias is needed.

---

## Step 1 — New pure `monitor/ansi_utils.py`

Create `.aitask-scripts/monitor/ansi_utils.py`, pure (imports `re` only),
mirroring the pure-sibling precedent of `monitor/prompt_patterns.py`:

```python
"""ANSI escape stripping — the single implementation, shared by the tmux core
and the pure concern grammar.

Kept in its own dependency-free module so `concern_parser` (pure: no tmux, no
Textual, no I/O) can normalise an ANSI-bearing capture without importing
`monitor_core` and its asyncio / subprocess / gateway graph.
"""
from __future__ import annotations

import re

ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(s: str) -> str:
    return ANSI_CSI_RE.sub("", s)
```

Then:

- `monitor_core.py` — delete `_ANSI_CSI_RE` (L145) and `_strip_ansi` (L149-150);
  add `from monitor.ansi_utils import strip_ansi` to the `monitor.`-package
  import group; update the two call sites (L189, L193) to `strip_ansi`.
- `tmux_monitor.py` — the shim re-exports `_strip_ansi` (L30). Change that entry
  to `strip_ansi`. Nothing imports the old private name, so no alias is kept.
- `tests/test_concern_parser.py` — import-path update only: change the
  `sys.path.insert` from `.aitask-scripts/monitor` to `.aitask-scripts` and the
  import from `from concern_parser import (...)` to
  `from monitor.concern_parser import (...)`, matching the style already used by
  `test_minimonitor_concern_action.py:29-34`.

## Step 2 — `match_shadow_pane` moves, `_pane_id_sort_key` dies

Move `match_shadow_pane` (`minimonitor_app.py:116-142`) into `monitor_core.py`
verbatim, next to `is_shadow_target` (L284). It is pure: splits each `list-panes`
line on `\t`, skips `len(parts) < 2`, skips falsy targets via `is_shadow_target`,
and returns `max(matches, key=...)` so the newest `%N` wins.

Delete `minimonitor_app._pane_id_sort_key` (L104-113) and pass the existing
`monitor_core._pane_id_num` (L294) as the key — an identical body whose docstring
already says it "mirrors `match_shadow_pane`'s defense in minimonitor".

Re-export `match_shadow_pane` through `monitor/tmux_monitor.py` (add it to the
flat `from monitor.monitor_core import (...)` list at L18-38 — the shim has no
`__all__` and no `import *`, so an omitted name is simply unreachable), and keep
a module-level `match_shadow_pane` name importable from `minimonitor_app`:
`tests/test_minimonitor_concern_action.py` calls `mm.match_shadow_pane` at
module scope (L109, 113, 117, 121). Re-importing it into `minimonitor_app`'s
namespace satisfies that without a wrapper.

## Step 3 — shadow pane lookup, module-level and duck-typed

Add to `monitor_core.py`, keeping the shared args builder so sync and async
cannot drift:

```python
def shadow_query_args() -> list[str]:
    return ["list-panes", "-a", "-F", f"#{{pane_id}}\t#{{{SHADOW_TARGET_OPTION}}}"]


def find_shadow_pane(monitor, followed_pane_id: str) -> str | None:        # sync
    if monitor is None:
        return None
    rc, out = monitor.tmux_run(shadow_query_args(), timeout=2)
    return None if rc != 0 else match_shadow_pane(out, followed_pane_id)


async def find_shadow_pane_async(monitor, followed_pane_id: str) -> str | None:
    if monitor is None:
        return None
    rc, out = await monitor.tmux_run_async(
        shadow_query_args(), timeout=_SHADOW_CAPTURE_TIMEOUT
    )
    return None if rc != 0 else match_shadow_pane(out, followed_pane_id)
```

`monitor` is **duck-typed on the gateway surface** (`tmux_run` /
`tmux_run_async` → `(rc, stdout)`) — exactly what `_FakeMon` documents itself as
("Stub TmuxMonitor exposing only the gateway entries the lookups use"). The
`monitor is None` guard preserves minimonitor's current early return.

The **sync** variant is what the spawn duplicate-guards use (t1216_4) and what
`LaunchShadowGuardTests` asserts (`mon.sync_calls` non-empty, no async query) —
it must stay sync so the guard can run before a dialog opens without an await
trap.

## Step 4 — `capture_shadow_text`, module-level

Move `_capture_shadow_text` (`minimonitor_app.py:1309-1354`) to `monitor_core.py`
as a **module-level** `async def capture_shadow_text(shadow_pane, *, lines=None)`.
It uses no instance state — only `_SCRIPT_DIR`, `os`, `asyncio` — so it needs no
`self` and no monitor. Keep the body verbatim:

- `script = _SCRIPT_DIR / "aitask_shadow_capture.sh"`, invoked
  `asyncio.create_subprocess_exec(str(script), "--deep", shadow_pane, ...)`.
- `env = dict(os.environ, SHADOW_PLAN_CAPTURE_LINES=str(lines))` when `lines` is
  given, else `None` (inherit — `CaptureArgvTests` asserts `env is None` in the
  default case and `"PATH" in env` in the override case).
- `OSError` on spawn → `None`; `asyncio.wait_for(..., timeout=3.0)` with
  `proc.kill()` + `await proc.wait()` (both suppressed) on timeout → `None`;
  non-zero `returncode` → `None`; else `stdout.decode("utf-8", errors="replace")`.

`--deep` is **always** passed: what it reads is plan-review output, and at the
narrow width a shadow pane runs at, the 200-line default (`SHADOW_CAPTURE_LINES`,
`aitask_shadow_capture.sh:47`) can start inside the block and clip the opening
fence (t1187); `--deep` selects the 400-line `SHADOW_PLAN_CAPTURE_LINES` (L61).

**Do not reroute this through the tick capture.** `_capture_args`
(monitor_core.py:1452-1459) is `capture-pane -p -e` with **no `-J`**;
`concern_parser` requires wrap-joined, ANSI-free text, which
`aitask_shadow_capture.sh:115` provides with `-p -J`.

Note `monitor_core.py` already spawns subprocesses (L252, L435), and the shell-out
carries no `"tmux"` argv literal, so `tests/test_no_raw_tmux.sh` is unaffected.

Move `_SHADOW_CAPTURE_TIMEOUT` (3.0), `_SHADOW_DEEP_RETRY_LINES` (1500) and
`_SHADOW_TRUNCATED_MSG` (`minimonitor_app.py:86-101`) alongside, and re-import
them into `minimonitor_app`'s namespace so `mm._SHADOW_DEEP_RETRY_LINES`
(test_minimonitor_concern_action.py:270,276) and `mm._SHADOW_TRUNCATED_MSG`
(test_minimonitor_concern_smoke.py:185) keep resolving.

**Stamping asymmetry — verify it is unchanged.** `aitask_shadow_capture.sh`
stamps `@aitask_shadow_analyzed_at` only when running *inside* a shadow pane
(`shadow_stamp_analyzed_at`, L137-151: requires `$TMUX_PANE` set, that pane to
carry `@aitask_shadow_target`, and that target to equal the captured pane).
Minimonitor's and the monitor's captures run from a non-shadow pane and never
stamp. Adding a second caller must not change that — assert it in the test.

## Step 5 — `refresh_shadow_snapshot` and the concurrency contract

New **method** on `TmuxMonitor` (it needs `_shadow_snapshots` and the generation
counter). This is the sharpest part of the child.

**Why care:** `_shadow_snapshots` is rebuilt **wholesale** by `commit_snapshots`
(a fresh dict is assigned at monitor_core.py:1743), and
`capture_pane_classified_async` reserves a new **global** generation before its
await (L1572-1573) — which is why today's 0.3 s `_fast_preview_refresh` can
already supersede an in-flight `capture_all_classified_async`. A naive per-shadow
refresh would widen that starvation window and clobber every other agent's shadow
entry.

Five binding rules. (Rules 1-3 were tightened during plan review — the original
three left the stamp source, the pane-identity check, and the bookkeeping
ordering under-specified; each gap is a real corruption path, spelled out below.)

1. **One total order over shadow writes, keyed by the moment the shadow pane is
   READ.** Add `self._shadow_write_seq: int = 0` beside `_shadow_snapshots`
   (L950) and `_next_shadow_write_seq()`. **Both** writers reserve from this
   **single** counter, and each reserves it in the last statement before it
   issues its own shadow `capture-pane`:
   - `capture_all_classified_async` reserves it **after** the discovery await
     (L1654) and **immediately before** the raw-capture `asyncio.gather` (L1661) —
     *not* next to `gen = self._next_generation()` at L1653:

     ```python
     all_panes = panes + shadows
     if gen == self._capture_generation:        # skip if already superseded
         self._full_shadow_seq = (gen, self._next_shadow_write_seq())
     raw_results = await asyncio.gather(...)
     ```
   - `refresh_shadow_snapshot` reserves it in the statement immediately before
     its `capture_pane_content_async` await.

   `commit_snapshots` then stamps with the seq its *own* capture reserved:
   `g, seq = self._full_shadow_seq; stamp = seq if g == gen else
   self._next_shadow_write_seq()` (the fallback covers a hand-built call with no
   matching capture and reproduces today's wholesale-overwrite semantics). A
   single slot suffices because the `gen == self._capture_generation` guard stops
   a superseded cycle from clobbering the live cycle's slot, and a superseded
   refresh returns at the `gen != self._capture_generation` guard (L1712) *before*
   stamping.

   **Why the read moment, not the cycle start:** `capture_all_classified_async`
   begins with an **awaited discovery** (L1654) before it reads any shadow pane.
   Reserving at L1653 would let a fast refresh that both reserves *and reads*
   entirely inside that discovery window take a **higher** seq than a full refresh
   which reads the same pane **later** — so the full refresh's newer content would
   lose. Moving the reservation past discovery makes the seq a faithful proxy for
   read order on both paths. Stamping at *commit* time is wrong for the mirror
   reason: a full refresh that read **before** a shadow refresh but commits
   **after** it would overwrite newer content with older. Two independent counters
   would make the two paths' stamps incomparable at all.

   **Stated residual:** the full batch reads all shadows in one concurrent
   `gather` under a single seq, so within the sub-window between that reservation
   and an individual pane's read, a fast refresh reserving just after it can still
   win with marginally older data. Both reads are effectively simultaneous, so
   either outcome is defensible, and the loser is superseded by the next full
   refresh within ~3 s. This is accepted rather than plumbed away: per-pane
   stamping would mean wrapping every coroutine in the `gather` and threading a
   fourth element through the `classified` tuples that `commit_snapshots` and the
   existing `test_monitor_shadow_status.py` batch tests consume — changing a shape
   the characterization net depends on, to close a window orders of magnitude
   smaller than the discovery gap this rule fixes.

   `refresh_shadow_snapshot` still **never** calls `_next_generation()` (L998), so
   it cannot supersede a full refresh; the agent-facing `_pane_cache` / snapshot
   path is untouched by it. (Negative control in the tests.)

2. **Stamped per-key merge.** Store each entry's seq in a parallel
   `self._shadow_snapshot_seq: dict[str, int]` keyed the same way — do **not**
   change `PaneSnapshot`, which is shared. A write lands only if its seq is
   **strictly greater** than the seq of the entry it would replace. Both the
   full rebuild and the single-shadow merge obey this, so the two are
   order-independent in either interleaving. `commit_snapshots` keeps a
   newer-stamped existing entry for keys present in both, and prunes
   `_shadow_snapshot_seq` to exactly the keys it retains.

3. **Existence is not identity — the merge must match the pane it captured.**
   `commit_snapshots` remains the only deleter (discovery is authoritative for
   existence), but a "key still present" check is **not sufficient**: the old
   shadow `%8` can die and a replacement `%12` be discovered for the *same*
   followed-pane key while a refresh of `%8` is in flight. The key is present, so
   a presence-only merge would overwrite the live `%12` with dead `%8` content.
   Therefore merge only when the current entry is present **and**
   `cur.pane.pane_id == the pane id actually captured`. Fail-closed: a missing
   key (never resurrect) or a rebind (never overwrite the replacement) both drop
   the merge.

4. **Bookkeeping runs only after the merge is accepted.** `_apply_bookkeeping`
   (L1394) is the **only** writer of `_last_content` / `_last_change_time`, and
   its docstring makes the contract explicit: *"Generation ownership is the
   caller's job … the async commits checked their reserved gen before calling
   here."* A rejected late refresh that had already called it would write stale
   content into `_last_content` and reset `_last_change_time` to now — resetting
   the shadow's idle clock and making the *next* full refresh see a spurious
   change. So `_merge_shadow_snapshot` performs the rule-2 and rule-3 checks
   **first**, and only then calls `_apply_bookkeeping`. Both checks and the write
   run on the loop after the await, so they are atomic with respect to other
   coroutines.

5. **A fast-refresh failure is "no update", never a hide.** The two paths differ
   deliberately and this asymmetry is now explicit rather than incidental:
   - *Full refresh:* a shadow whose raw fetch fails produces no entry this tick,
     so the glyph is hidden for that tick (existing, documented behaviour —
     `commit_snapshots` docstring L1704-1708).
   - *Fast refresh:* `refresh_shadow_snapshot` returning `None` (capture failure,
     stale seq, or rebind) **retains** the previous snapshot and its idle state.

   Rationale: the fast path is an optimisation layered on the 3 s full refresh,
   which remains the sole authority for hiding. Mirroring the hide at a 0.3 s
   cadence would make the glyph flicker on any transient hiccup. The staleness is
   therefore **bounded by one full-refresh interval** (~3 s), after which the full
   refresh hides or replaces the entry. Because of rule 4, a retained entry keeps
   its idle bookkeeping untouched — the same treatment a normal pane gets when it
   fails a single tick. This is a stated approximation, not an oversight, and is
   pinned by a test.

Body sketch:

```python
async def refresh_shadow_snapshot(self, followed_pane_id: str) -> PaneSnapshot | None:
    prev = self._shadow_snapshots.get(followed_pane_id)
    if prev is None:
        return None                      # rule 3: never resurrect
    captured_pane_id = prev.pane.pane_id
    seq = self._next_shadow_write_seq()  # rule 1: reserved in the statement
                                         # immediately before the READ below
    raw = await self.capture_pane_content_async(captured_pane_id, pane=prev.pane)
    if raw is None:
        return None                      # rule 5: no update; never a hide
    pane, content = raw
    result = await self._run_offloaded(
        lambda: _classify_one(content, self.get_compare_mode(pane.pane_id),
                              self.prompt_patterns, pane.category))
    return self._merge_shadow_snapshot(
        followed_pane_id, captured_pane_id, seq, pane, content, result)


def _merge_shadow_snapshot(self, key, captured_pane_id, seq, pane, content, result):
    cur = self._shadow_snapshots.get(key)
    if cur is None or cur.pane.pane_id != captured_pane_id:
        return None                      # rule 3: removed, or rebound to a new shadow
    if seq <= self._shadow_snapshot_seq.get(key, -1):
        return None                      # rule 2: a newer write already landed
    snap = self._apply_bookkeeping(pane, content, result, time.monotonic())  # rule 4
    self._shadow_snapshots[key] = snap
    self._shadow_snapshot_seq[key] = seq
    return snap
```

`pane=` is the t1133 kwarg (L1533-1536, applied at L1552-1553) that bypasses
`_pane_cache` — shadows must stay out of it. `capture_pane_content_async` is
non-finalizing, so it never touches `_last_content` / `_last_change_time`; that
is correct here — the single mutation point stays `_apply_bookkeeping`, now
strictly downstream of both guards.

## Step 6 — `concern_block_signature`

New in `concern_parser.py`, as a **third strictness tier**. concern_parser.py:42-51
currently documents the two existing tiers as *prose* ("Two consumers, two
strictnesses…") — replace that paragraph with a three-row table:

| Entry point | Input shape | Purpose |
|---|---|---|
| `parse_concerns` | wrap-joined, ANSI-free (`-J`) | forgiving — explicit picker action |
| `has_concern_block` | wrap-joined, ANSI-free (`-J`) | strict auto-offer trigger |
| `concern_block_signature` | **raw tick capture** (`-p -e`, no `-J`) | **cheap freshness trigger only** |

```python
def concern_block_signature(raw_text: str) -> str | None:
    """Cheap freshness trigger over a NON-wrap-joined, ANSI-bearing tick
    capture. Returns a REFLOW-STABLE digest of the last block region, or None
    when no complete block is present. Trigger only — never parse its input
    into forwardable concerns; the picker re-captures with -J."""
```

Implementation: `strip_ansi` (from `monitor.ansi_utils`) → reuse
`_last_block_region(text, require_close=True)` (L101) so the block boundaries come
from the **existing** grammar (no second implementation) → `re.sub(r"\s+", " ",
region).strip()` → `hashlib.sha256(...)` hexdigest (truncated is fine; it is an
equality token, not a security artifact).

**Normalisation rationale — record it in the docstring:**

- Collapsing whitespace to *nothing* is fully reflow-proof but erases token
  boundaries, so `"needs review"` and `"needsreview"` collide and a genuinely
  changed concern is silently missed. **Rejected.**
- Normalising to one space is exact for trailing row padding and for wraps at a
  word boundary. A wrap landing **mid-word** injects a space that was not in the
  source, so the same block re-rendered at a different pane width can re-hash.
  Accepted, and it fails in the safe direction: at most **one spurious re-offer**
  (a badge and one toast; nothing lost or forwarded), never a missed real change.

Also export `_SENTINEL_SAFE_COLS = 24`: the sentinels are 21
(`===AITASK-CONCERNS===`) and 18 (`===END-CONCERNS===`) chars, so a narrower pane
can wrap them and hide a block from this detector entirely. t1216_3 owns the
authoritative-capture fallback that consumes it (`TmuxPaneInfo.width` exists,
monitor_core.py:334, so the consumer is viable).

## Step 7 — staleness

Move the body of `_update_shadow_freshness` (`minimonitor_app.py:1368-1418`) to a
module-level `async def compute_shadow_staleness(monitor, shadow_pane,
followed_pane, eps)` in `monitor_core.py`, returning `(stale: bool | None,
analyzed_at: float | None)`. `get_pane_option` is async (monitor_core.py:1048), so
this is async too. Its failure-safe semantics are load-bearing — preserve each
branch exactly, **including the `hasattr` guards** (the tests attach
`get_pane_option` / `get_last_change_wall` onto a bare `_FakeMon`) and the
**ordering** (a missing stamp must return before the `get_last_change_wall`
lookup — `test_no_stamp_skips_last_change_lookup` asserts that cost gate):

| Condition | Result |
|---|---|
| `monitor` is None / no `get_pane_option` | return `(None, None)` — **preserve** prior state |
| `get_pane_option` raises | `(None, None)` — preserve |
| stamp empty (never analyzed) | `(False, None)` — clear any banner |
| `float(stamp)` raises `ValueError` | `(None, None)` — preserve |
| `get_last_change_wall(followed)` is `None` (unobserved) | `(None, None)` — preserve |
| `last_change > analyzed_at + eps` | `(True, analyzed_at)` |
| otherwise | `(False, analyzed_at)` |

The caller keeps computing `eps = max(2.0, float(getattr(self,
"_refresh_seconds", 3)))`.

Move `_format_stale_duration` (the `@staticmethod` at `minimonitor_app.py:1420`)
to `monitor_shared.format_stale_duration` — pure, shapes `"{s}s"` /
`"{m}m{s:02d}s"` / `"{h}h{m:02d}m"`. It sits naturally beside the other pure
formatters (`format_shadow_glyph`, L86; `format_pane_status`, L95).

`_set_shadow_stale_banner` (L1356) **stays** in minimonitor: it is hard-wired to
`#mini-shadow-stale` and sets the `_shadow_stale_banner_text` test seam (which,
note, is never initialized in `__init__` — it is created lazily at L1364 and the
tests set it directly). It now composes its text from the shared formatter.

## Step 8 — rewire minimonitor (bodies out, seams stay)

Delete the moved **bodies**; import the lifted names (through
`monitor/tmux_monitor.py` where that shim already re-exports, matching the file's
existing import style at L27-35). Keep a **one-line delegating seam** for each
private name the existing suite binds to, so the characterization net passes
byte-unmodified:

```python
async def _capture_shadow_text(self, shadow_pane, *, lines=None):
    return await capture_shadow_text(shadow_pane, lines=lines)

def _find_shadow_pane_for_sync(self, followed_pane_id):
    return find_shadow_pane(self._monitor, followed_pane_id)

async def _find_shadow_pane_for(self, followed_pane_id):
    return await find_shadow_pane_async(self._monitor, followed_pane_id)

_format_stale_duration = staticmethod(format_stale_duration)
```

`_update_shadow_freshness` keeps its signature and becomes: compute `eps`, call
`compute_shadow_staleness(...)`, then apply the banner policy (on `None`, return
without touching `_shadow_feedback_stale` or the banner — that is the
preserve-on-failure contract).

These seams are deliberate, documented as "delegating seam — the shared
implementation lives in `monitor_core`", and are removed by the follow-up once
t1216_2/_3 land (see `### Planned mitigations`).

Keep `_find_own_agent_snapshot` (L525) **local** — it resolves the followed agent
from minimonitor's own window index and is intrinsically minimonitor-shaped. The
lifted APIs all take an explicit `followed_pane_id` instead. Its ten call sites
(714, 736, 822, 891, 923, 964, 1100, 1145, 1441, 1508) are unchanged.

## Step 9 — docs

1. `.claude/skills/aitask-shadow/concern-format.md` — add the
   `concern_block_signature` row to the "Trigger vs. action contract" table
   (L132-135), stating the trigger-only contract and its non-wrap-joined input.
   While in the file, fix the already-stale "Where it lives" list (L139-152),
   which omits the existing `contains_any_concern_block` and
   `block_head_truncated`.
   **Constraint:** this file is read at runtime by the shadow, and
   `tests/test_concern_parser.py::TestShadowDocsNotParserLive` globs
   `.claude/skills/aitask-shadow/*.md` asserting no doc trips `has_concern_block`
   / `contains_any_concern_block` — so do **not** write a contiguous fenced
   example.
2. `aidocs/framework/shadow_agent.md` — the "Compare (in minimonitor)" bullet
   (L146-157) becomes untrue once the compare lives in `monitor_core`. Reword to
   name `monitor_core.compute_shadow_staleness` as the shared implementation with
   minimonitor owning the banner.

## Verification

New `tests/test_shadow_seam.py`. It must do its own
`sys.path.insert(0, REPO_ROOT / ".aitask-scripts")` — the runner puts only
`board` and `lib` on `PYTHONPATH`. Harness: the `_FakeMon` idiom from
`tests/test_minimonitor_concern_action.py:64-99` for the lookup/capture tests,
and the scripted-coroutine `_make_monitor` fixture from
`tests/test_monitor_shadow_status.py:80-111` (real `TmuxMonitor`,
`_run_offloaded` overridden to run synchronously, no tmux, no sleeps) for the
concurrency tests.

- `match_shadow_pane`: bind, miss, whitespace-only target ignored, multiple →
  newest.
- `find_shadow_pane` sync and async against a `_FakeMon`; `capture_shadow_text`
  argv (`--deep`, script path) and the `SHADOW_PLAN_CAPTURE_LINES` env override
  with inherited `PATH`; the no-stamp-from-a-non-shadow-caller assertion.
- `compute_shadow_staleness`: one test per row of the table in Step 7, including
  the cost gate (no `get_last_change_wall` call when the stamp is empty).
- `concern_block_signature`:
  - **stable** — same block with trailing row padding, ANSI colour runs, and
    word-boundary wraps at several widths → identical digest;
  - **discriminating** — `"needs review"` vs `"needsreview"` → different, plus
    changed priority / region / body;
  - **residual, pinned deliberately** — a mid-word wrap of the same block yields
    a different digest, asserted as *known* behaviour with the
    spurious-re-offer consequence named in the test docstring, so nobody later
    "fixes" it back into a collision;
  - **narrow pane** — below `_SENTINEL_SAFE_COLS` the sentinel itself wraps and
    the detector returns `None`.
- **Concurrency** — one test per binding rule, all with the scripted-coroutine
  fixture (deterministic, no sleeps):
  - *late-full* (rule 1) — full refresh reads the shadow **first**, a shadow
    refresh reads and merges **second**, the full refresh commits **last**: the
    shadow's newer content survives for the refreshed key, and every other key
    still gets the full refresh's content. This is the interleaving a
    commit-time stamp would get wrong.
  - *discovery-window interleaving* (rule 1) — the discriminating test for the
    reservation **point**. Script `discover_panes_with_shadows_async` to suspend,
    run a complete fast refresh (reserve + read + merge) while it is suspended,
    then let discovery finish and the full refresh read **newer** shadow content
    and commit. The full refresh's newer content must win. Pin it with a
    negative control that reserves at L1653 instead and fails, so the test is
    shown to discriminate the reservation point rather than merely pass.
  - *late-shadow* (rules 1+2) — shadow refresh captures first, full refresh
    captures and commits, then the shadow merge runs last: the merge is
    **rejected** and the full refresh's content stands.
  - *rebind during await* (rule 3) — while a refresh of `%8` is in flight, a full
    refresh replaces the key's shadow with `%12`; the late `%8` merge is dropped
    and `%12` survives. Plus the existing removal case (key gone → never
    resurrected). A **negative control** with no rebind proves the identity check
    (not the fixture) is what blocked it.
  - *bookkeeping isolation* (rule 4) — after a **rejected** late refresh, assert
    both the displayed snapshot **and** `_last_content` / `_last_change_time` for
    the shadow pane are unchanged (an accepted refresh, as the positive control,
    does update them).
  - *failure policy* (rule 5) — a fast refresh whose capture returns `None`
    leaves the previous snapshot and its idle state in place and returns `None`;
    a subsequent full refresh that no longer discovers the shadow does remove it.
  - *negative control* — `refresh_shadow_snapshot` never bumps
    `capture_generation` (so `test_monitor_shadow_status.py::SupersessionTests`
    stays green), asserted across accepted, rejected and failed refreshes.

**Prove the harness can fail:** before relying on the new file, confirm the suite
exits non-zero when one of the new guards is inverted — a passing test pins
nothing until its failure path is demonstrated.

Regression net — must pass with **only** the one import-path edit named in
Step 1:

```bash
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_tui_clipboard_seam.sh
```

specifically `tests/test_minimonitor_concern_action.py` (all **six** classes —
`MatchShadowPaneTests`, `ActionPickConcernsTests`, `CaptureArgvTests`,
`LaunchShadowGuardTests`, `AutoOfferTests`, `ShadowFreshnessTests`),
`tests/test_minimonitor_concern_smoke.py` (live-tmux; drives the real capture
through `app._capture_shadow_text`), `tests/test_minimonitor_shadow_pick.py`,
`tests/test_concern_parser.py`, `tests/test_monitor_shadow_status.py`.

## Notes for sibling tasks

- `refresh_shadow_snapshot` returns `None` for **four** distinct reasons — key
  absent, shadow rebound to a different pane, stale write seq, or capture failure
  — and in every case the meaning is the same: **"no update this tick"**, never
  "shadow gone". t1216_2's fast tick must not hide or clear anything on `None`;
  the 3 s full refresh owns deletion, which bounds fast-path staleness to one
  full-refresh interval (Step 5, rule 5).
- Any future writer of `_shadow_snapshots` must reserve from
  `_next_shadow_write_seq()` in the statement **immediately before it issues its
  own shadow capture** — never at commit time, never at the top of a coroutine
  that awaits something else first, and never from a second counter. Each of
  those breaks the read-order total ordering the merge depends on. Route the
  write through `_merge_shadow_snapshot`.
- `_SENTINEL_SAFE_COLS` and `_SHADOW_DEEP_RETRY_LINES` are exported for t1216_3.
- The **sync** `find_shadow_pane(monitor, ...)` is what t1216_4's duplicate guard
  needs.
- All lifted lookups/staleness take a **duck-typed** `monitor` first arg, not a
  `TmuxMonitor` — `monitor_app.py` can call them with its own monitor unchanged.
- The `MiniMonitorApp._*` delegating seams are transitional; `monitor_app.py`
  must call the shared functions directly and never grow parallel seams.

## Risk

### Code-health risk: medium
- The `commit_snapshots` amendment (stamping + newer-wins merge) edits a
  per-tick hot path shared by monitor and minimonitor; a stamping error could
  silently drop shadow entries, resurrect a removed one, or corrupt the shadow's
  idle clock, with no user-visible signal until a glyph goes wrong · severity:
  medium · → mitigation: shadow_refresh_concurrency_soak
- Plan review found four genuine correctness gaps in the first draft of this
  merge (undefined stamp origin, presence-vs-identity, bookkeeping ahead of the
  guards, unspecified failure policy) — evidence that this seam is easy to get
  subtly wrong and that a later edit could reintroduce any of them. The five
  binding rules and their one-test-per-rule net are the standing control ·
  severity: medium · → mitigation: shadow_refresh_concurrency_soak
- The transitional delegating seams left on `MiniMonitorApp` mean two names for
  one implementation until t1216_2/_3 land — structure debt that will quietly
  become permanent if nobody removes it · severity: low · → mitigation: shadow_seam_wrapper_removal
- Blast radius is wide but mechanical: 6 source files (one new), 2 docs, 1 new
  test file, 1 test import-path edit · severity: low · → mitigation: none needed
  (the unmodified characterization net is the in-task control)

### Goal-achievement risk: medium
- `refresh_shadow_snapshot` ships with **no production consumer** in this child
  (t1216_2's fast tick is the first). Its concurrency contract is proven only by
  scripted-coroutine unit tests, which cannot reproduce real event-loop
  interleaving, so a subtle ordering flaw could survive to t1216_2 · severity:
  medium · → mitigation: shadow_refresh_concurrency_soak
- `concern_block_signature`'s reflow stability is a *property* claim over
  arbitrary tmux wrapping; the tests sample several widths but cannot enumerate
  them. The residual is bounded and fails safe (at most one spurious re-offer)
  · severity: low · → mitigation: none needed (pinned by the stable /
  discriminating / residual / narrow-pane test quartet in this task)

### Planned mitigations
- timing: after | name: shadow_refresh_concurrency_soak | type: test | priority: medium | effort: medium | addresses: code-health (commit_snapshots hot-path amendment) + goal-achievement (refresh_shadow_snapshot ships with no production consumer) | desc: Live/soak verification of the stamped per-key merge contract under real event-loop interleaving once t1216_2 wires the 0.3s fast tick — should depend on t1216_2; distinct from t1216_5 (human manual verification of the whole feature).
- timing: after | name: shadow_seam_wrapper_removal | type: refactor | priority: medium | effort: low | addresses: code-health (transitional delegating seams on MiniMonitorApp) | desc: Once t1216_2/t1216_3 have landed and the shared seams have a second real consumer, remove the one-line MiniMonitorApp delegators and migrate the four minimonitor/shadow test files onto the shared monitor_core functions.

## Final Implementation Notes

- **Actual work done:** All nine plan steps landed as designed. New pure
  `monitor/ansi_utils.py` owns the single `strip_ansi`; `match_shadow_pane`,
  `shadow_query_args`, `find_shadow_pane(_async)`, `capture_shadow_text` and
  `compute_shadow_staleness` are module-level in `monitor_core.py` taking a
  duck-typed `monitor`; `TmuxMonitor.refresh_shadow_snapshot` /
  `_merge_shadow_snapshot` / `_next_shadow_write_seq` / `_clear_shadow_snapshots`
  implement the five-rule merge; `commit_snapshots` stamps and merges per key;
  `concern_block_signature` + `_SENTINEL_SAFE_COLS` are the new third tier in
  `concern_parser.py`; `format_stale_duration` moved to `monitor_shared.py`;
  minimonitor keeps one-line delegating seams and lost `_pane_id_sort_key`.
  `monitor_app.py` was not touched (verified: it references no lifted symbol).
  New `tests/test_shadow_seam.py` (53 tests). Docs updated in
  `concern-format.md` and `aidocs/framework/shadow_agent.md`.

- **Deviations from plan:**
  1. **No test file needed editing at all.** The plan's Step 1 called for an
     import-path update in `tests/test_concern_parser.py`. `monitor_core.py`
     already uses a dual `try: from .X / except ImportError: from X` idiom for
     sibling imports, which resolves under BOTH the package and flat import
     styles; reusing it in `concern_parser.py` means the flat-import test needs
     no change. The characterization net is therefore **byte-unmodified** —
     strictly stronger than the plan's own stated proof.
  2. **Two extra correctness fixes found while implementing** (both beyond the
     reviewed design, both with negative controls):
     - `capture_all` (sync path) cleared `_shadow_snapshots` without the new
       `_shadow_snapshot_seq`, desyncing two halves of one value and risking a
       `KeyError` / a stale seq vetoing a later legitimate write. Fixed by
       `_clear_shadow_snapshots()` clearing both as a unit.
     - **Commit-side half of the rebind race.** Rule 3 guarded the merge
       direction only. A fast refresh of the OLD shadow can land with a seq
       *newer* than the full batch's, and seq-only arbitration would keep that
       dead pane and discard the replacement discovery had just found. Fixed by
       comparing seqs only when the pane identity matches: discovery owns
       identity, the seq owns recency between reads of the same pane.
  3. Four now-dead imports were removed from `minimonitor_app.py`
     (`asyncio`, `SHADOW_ANALYZED_AT_OPTION`, `is_shadow_target`,
     `_SHADOW_CAPTURE_TIMEOUT`); `_SHADOW_DEEP_RETRY_LINES` /
     `_SHADOW_TRUNCATED_MSG` / `SHADOW_TARGET_OPTION` are still referenced and
     stayed. The plan had assumed all constants needed re-export.
  4. Two stale doc statements adjacent to the edits were corrected while in the
     files: `concern-format.md`'s "Where it lives" list (missing
     `contains_any_concern_block` / `block_head_truncated`) and its claim that
     staleness uses a "content-signature mechanism" — it uses timestamps, and
     that wording became actively misleading once a real content-signature
     function existed in the same file.

- **Issues encountered:**
  - The first version of the rebind test **passed for the wrong reason**: the
    stale merge was being rejected by the seq guard, so the identity check was
    never exercised. The negative control (replacing the identity check with a
    presence-only check) exposed it by *passing* when it should have failed. The
    test was rebuilt to suspend the full refresh mid-capture so the late merge
    carries a genuinely newer seq, and only then does identity decide. Lesson
    applied to every other guard: each is now paired with a control proving it,
    not the fixture, is what blocks the bad write.
  - The initial baseline appeared to show `FAILED (failures=1)`; that is nested
    output from an existing guard test that runs a sub-suite as a subprocess.
    The top-level runner exits 0. Verified before making any change.
  - `_SENTINEL_SAFE_COLS` assertion in the narrow-pane test was written with the
    inequality inverted (24 is the *safe* width, above the 21-char fence, not
    below it); caught on first run.

- **Key decisions:**
  - Lifted helpers take a **duck-typed `monitor`** (gateway surface only), not a
    `TmuxMonitor`. This is what keeps the existing `_FakeMon` stubs valid and is
    the reason zero test edits were needed; `monitor_app.py` can pass its own
    monitor unchanged.
  - `capture_shadow_text` is module-level and monitor-free — it touches no
    instance state, and keeping it off `TmuxMonitor` is what lets the live-tmux
    smoke test keep driving the real capture through `app._capture_shadow_text`.
  - Shadow write ordering uses ONE counter reserved at the READ site on both
    paths. All six binding behaviours have discriminating negative controls
    (reservation point, no-generation-bump, seq guard, merge identity, commit
    identity, bookkeeping ordering, failure policy).

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - `refresh_shadow_snapshot` returns `None` for five reasons now (key absent,
    rebound pane, stale seq, capture failure — and it never creates an entry).
    All mean **"no update this tick"**, never "shadow gone". t1216_2's fast tick
    must not hide or clear on `None`; the full refresh owns deletion, bounding
    fast-path staleness to one refresh interval.
  - Any future writer of `_shadow_snapshots` must reserve via
    `_next_shadow_write_seq()` in the statement immediately before its own
    capture, and write through `_merge_shadow_snapshot`. Reserving at commit
    time, at the top of a coroutine that awaits something else first, or from a
    second counter each breaks the read-order total ordering.
  - `_SENTINEL_SAFE_COLS` (24) and `_SHADOW_DEEP_RETRY_LINES` (1500) are
    exported for t1216_3. `TmuxPaneInfo.width` exists, so the narrow-pane
    fallback consumer is viable.
  - The sync `find_shadow_pane(monitor, ...)` is what t1216_4's duplicate guard
    needs — it must stay sync (no await trap before a dialog opens).
  - The `MiniMonitorApp._*` delegating seams are transitional. `monitor_app.py`
    must call the shared functions directly and never grow parallel seams;
    removing the seams is the `shadow_seam_wrapper_removal` follow-up.
