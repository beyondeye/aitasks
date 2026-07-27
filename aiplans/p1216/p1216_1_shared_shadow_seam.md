---
Task: t1216_1_shared_shadow_seam.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Sibling Tasks: aitasks/t1216/t1216_2_monitor_shadow_zone.md, aitasks/t1216/t1216_3_monitor_concern_picker.md, aitasks/t1216/t1216_4_monitor_shadow_spawn.md
Base branch: main
Output branch: main
---

# p1216_1 — Shared shadow seam (headless)

## Goal

Lift every minimonitor shadow helper that is pure or depends only on
`TmuxMonitor` into `monitor_core.py` / `monitor_shared.py`, rewire minimonitor
onto the lifted code with **identical behaviour**, and add the one new piece the
monitor needs: a cheap, reflow-stable concern-block freshness trigger.

`monitor_app.py` is **not touched** in this child. The proof of correctness is
that the whole existing minimonitor/shadow suite passes unmodified (except
import paths) against the lifted implementations.

## Step 1 — `strip_ansi` becomes public

`monitor_core.py:149` defines `_strip_ansi(s)` over `_ANSI_CSI_RE` (L145).
Rename to `strip_ansi`, keep `_strip_ansi = strip_ansi` if the internal call
sites are numerous enough that renaming them adds noise. `concern_parser` will
import it for the signature normalisation in Step 6.

## Step 2 — `match_shadow_pane` moves, `_pane_id_sort_key` dies

Move `match_shadow_pane` (`minimonitor_app.py:116-142`) into `monitor_core.py`
verbatim, next to `is_shadow_target` (L284). It is pure: splits each
`list-panes` line on `\t`, skips `len(parts) < 2`, skips falsy targets via
`is_shadow_target`, and returns `max(matches, key=...)` so the newest `%N` wins.

Delete `minimonitor_app._pane_id_sort_key` (L104-113) and pass the existing
`monitor_core._pane_id_num` (L294) as the key — an identical body whose
docstring already says it "mirrors `match_shadow_pane`'s defense in
minimonitor". Re-export `match_shadow_pane` through `monitor/tmux_monitor.py`
(minimonitor imports everything monitor-core-ish through that shim, L27-35) and
keep a module-level `match_shadow_pane` name importable from
`minimonitor_app` — `tests/test_minimonitor_concern_action.py::MatchShadowPaneTests`
calls `mm.match_shadow_pane` at module scope.

## Step 3 — shadow pane lookup on `TmuxMonitor`

Move, keeping the shared args builder so sync and async cannot drift:

```python
def _shadow_query_args(self) -> list[str]:
    return ["list-panes", "-a", "-F", f"#{{pane_id}}\t#{{{SHADOW_TARGET_OPTION}}}"]

def find_shadow_pane(self, followed_pane_id: str) -> str | None:        # sync
    rc, out = self.tmux_run(self._shadow_query_args(), timeout=2)
    return None if rc != 0 else match_shadow_pane(out, followed_pane_id)

async def find_shadow_pane_async(self, followed_pane_id: str) -> str | None:
    rc, out = await self.tmux_run_async(self._shadow_query_args(),
                                        timeout=_SHADOW_CAPTURE_TIMEOUT)
    return None if rc != 0 else match_shadow_pane(out, followed_pane_id)
```

The **sync** variant is what the spawn duplicate-guards use (t1216_4) — it must
stay sync so the guard can run before a dialog opens without an await trap.

## Step 4 — `capture_shadow_text` on `TmuxMonitor`

Move `_capture_shadow_text` (`minimonitor_app.py:1309-1354`) verbatim. It is the
only real shell-out and it deliberately does **not** use the tmux gateway:

- `script = _SCRIPT_DIR / "aitask_shadow_capture.sh"`, invoked
  `asyncio.create_subprocess_exec(str(script), "--deep", shadow_pane, ...)`.
- `env = dict(os.environ, SHADOW_PLAN_CAPTURE_LINES=str(lines))` when `lines` is
  given, else `None`.
- `OSError` on spawn → `None`; `asyncio.wait_for(..., timeout=3.0)` with
  `proc.kill()` + `await proc.wait()` (both suppressed) on timeout → `None`;
  non-zero `returncode` → `None`; else
  `stdout.decode("utf-8", errors="replace")`.

`--deep` is **always** passed: what it reads is plan-review output, and at the
narrow width a shadow pane runs at, the 200-line default can start inside the
block and clip the opening fence (t1187).

**Do not reroute this through the tick capture.** `_capture_args`
(monitor_core.py:1452) is `capture-pane -p -e` with **no `-J`**;
`concern_parser` requires wrap-joined, ANSI-free text, which
`aitask_shadow_capture.sh:115` provides with `-p -J`.

Move `_SHADOW_CAPTURE_TIMEOUT` (3.0), `_SHADOW_DEEP_RETRY_LINES` (1500) and
`_SHADOW_TRUNCATED_MSG` alongside, re-exported so minimonitor's existing
references keep resolving.

Note the stamping asymmetry and **verify it is unchanged**:
`aitask_shadow_capture.sh` stamps `@aitask_shadow_analyzed_at` only when running
*inside* a shadow pane (`shadow_stamp_analyzed_at`, L137-149). Minimonitor's and
the monitor's captures run from a non-shadow pane and never stamp. Adding a
second caller must not change that — assert it in the test.

## Step 5 — `refresh_shadow_snapshot` and the concurrency contract

New on `TmuxMonitor`. This is the sharpest part of the child.

**Why care:** `_shadow_snapshots` is rebuilt **wholesale** by `commit_snapshots`
(L1743), and `capture_pane_classified_async` reserves a new **global**
generation before its await (L1572) — which is why today's 0.3 s
`_fast_preview_refresh` can already supersede an in-flight
`capture_all_classified_async`. A naive per-shadow refresh would widen that
starvation window and clobber every other agent's shadow entry.

Three binding rules:

1. **Separate generation.** `refresh_shadow_snapshot` never calls
   `_next_generation()`. Add `self._shadow_capture_generation: int = 0` and a
   `_next_shadow_generation()`, reserved before the await. The agent-facing
   `_pane_cache` / snapshot path is untouched by it, so it cannot invalidate a
   full refresh.
2. **Stamped per-key merge.** Store shadow entries with the shadow generation
   they were fetched at (a parallel `dict[str, int]` keyed the same way, or a
   small record — do not change `PaneSnapshot`, which is shared). A write lands
   only if its stamp is **newer** than the entry it replaces. Amend
   `commit_snapshots` (L1729-1743) to stamp the entries it rebuilds and, for
   keys present in both, keep the newer-stamped one.
3. **Only the full refresh deletes.** `commit_snapshots` still drops keys absent
   from its own discovery (that is what makes a dead shadow disappear). A
   single-shadow merge is **dropped** when its key is no longer present — it can
   never resurrect a shadow the full refresh just removed. Fail-closed.

Body sketch:

```python
async def refresh_shadow_snapshot(self, followed_pane_id: str) -> PaneSnapshot | None:
    prev = self._shadow_snapshots.get(followed_pane_id)
    if prev is None:
        return None                      # rule 3: never resurrect
    gen = self._next_shadow_generation()
    raw = await self.capture_pane_content_async(prev.pane.pane_id, pane=prev.pane)
    if raw is None:
        return None
    pane, content = raw
    result = await self._run_offloaded(
        lambda: _classify_one(content, self.get_compare_mode(pane.pane_id),
                              self.prompt_patterns, pane.category))
    return self._merge_shadow_snapshot(followed_pane_id, gen, pane, content, result)
```

`pane=` is the t1133 kwarg (L1533-1550) that bypasses `_pane_cache` — shadows
must stay out of it. `capture_pane_content_async` is non-finalizing, so it never
touches `_last_content` / `_last_change_time`; that is correct here.

`_merge_shadow_snapshot` performs rules 2 and 3 on the loop.

## Step 6 — `concern_block_signature`

New in `concern_parser.py`, as a **third strictness tier** documented in the
module docstring's existing trigger-vs-action table:

| Entry point | Input shape | Purpose |
|---|---|---|
| `parse_concerns` | wrap-joined, ANSI-free (`-J`) | explicit picker action |
| `has_concern_block` | wrap-joined, ANSI-free (`-J`) | strict auto-offer trigger |
| `concern_block_signature` | **raw tick capture** (`-p -e`, no `-J`) | **cheap freshness trigger only** |

```python
def concern_block_signature(raw_text: str) -> str | None:
    """Cheap freshness trigger over a NON-wrap-joined, ANSI-bearing tick
    capture. Returns a REFLOW-STABLE digest of the last block region, or None
    when no complete block is present. Trigger only — never parse its input
    into forwardable concerns; the picker re-captures with -J."""
```

Implementation: `strip_ansi` → reuse `_last_block_region(text, require_close=True)`
so the block boundaries come from the **existing** grammar (no second
implementation) → `re.sub(r"\s+", " ", region).strip()` → `hashlib.sha256(...)`
hexdigest (truncated is fine; it is an equality token, not a security artifact).

**Normalisation rationale — record it in the docstring:**

- Collapsing whitespace to *nothing* is fully reflow-proof but erases token
  boundaries, so `"needs review"` and `"needsreview"` collide and a genuinely
  changed concern is silently missed. **Rejected.**
- Normalising to one space is exact for trailing row padding and for wraps at a
  word boundary. A wrap landing **mid-word** injects a space that was not in the
  source, so the same block re-rendered at a different pane width can re-hash.
  Accepted, and it fails in the safe direction: at most **one spurious
  re-offer** (a badge and one toast; nothing lost or forwarded), never a missed
  real change.

Also export `_SENTINEL_SAFE_COLS = 24`: the sentinels are 21
(`===AITASK-CONCERNS===`) and 18 (`===END-CONCERNS===`) chars, so a narrower
pane can wrap them and hide a block from this detector entirely. t1216_3 owns
the fallback that consumes the constant.

## Step 7 — staleness

Move the body of `_update_shadow_freshness` (`minimonitor_app.py:1368-1418`) to
`monitor_core.compute_shadow_staleness(monitor, shadow_pane, followed_pane, eps)`,
returning `(stale: bool | None, analyzed_at: float | None)`. Its failure-safe
semantics are load-bearing — preserve each branch exactly:

| Condition | Result |
|---|---|
| `get_pane_option` raises | return `(None, None)` — **preserve** prior state |
| stamp empty (never analyzed) | `(False, None)` — clear any banner |
| `float(stamp)` raises `ValueError` | `(None, None)` — preserve |
| `get_last_change_wall(followed)` is `None` (unobserved) | `(None, None)` — preserve |
| `last_change > analyzed_at + eps` | `(True, analyzed_at)` |
| otherwise | `(False, analyzed_at)` |

The caller keeps computing `eps = max(2.0, refresh_seconds)`.

Move `_format_stale_duration` (the `@staticmethod` at L1420) to
`monitor_shared.format_stale_duration` — pure, shapes `"{s}s"` /
`"{m}m{s:02d}s"` / `"{h}h{m:02d}m"`.

`_set_shadow_stale_banner` (L1356) **stays** in minimonitor: it is hard-wired to
`#mini-shadow-stale` and sets the `_shadow_stale_banner_text` test seam. It now
composes its text from the shared formatter.

## Step 8 — rewire minimonitor

Delete the moved bodies; import the lifted names (through
`monitor/tmux_monitor.py` where that shim already re-exports, to match the
file's existing import style at L27-35). Keep `_find_own_agent_snapshot` (L525)
**local** — it resolves the followed agent from minimonitor's own window index
and is intrinsically minimonitor-shaped. The lifted APIs all take an explicit
`followed_pane_id` instead.

The ten call sites of `_find_own_agent_snapshot` (714, 736, 822, 891, 923, 964,
1100, 1146, 1441, 1508) are unchanged.

## Step 9 — docs

Add the `concern_block_signature` row to the "Trigger vs. action contract" table
in `.claude/skills/aitask-shadow/concern-format.md` (L126-138), stating the
trigger-only contract and its non-wrap-joined input. Note the file is read at
runtime by the shadow, and `tests/test_concern_parser.py::TestShadowDocsNotParserLive`
asserts no doc trips `has_concern_block` / `contains_any_concern_block` — so do
**not** write a contiguous fenced example.

## Verification

New `tests/test_shadow_seam.py`. Harness: the `_FakeMon` idiom from
`tests/test_minimonitor_concern_action.py:64-104` for the lookup/capture tests,
and the scripted-coroutine `_make_monitor` fixture from
`tests/test_monitor_shadow_status.py:78-110` (real `TmuxMonitor`,
`_run_offloaded` overridden to run synchronously, no tmux, no sleeps) for the
concurrency tests.

- `match_shadow_pane`: bind, miss, whitespace-only target ignored, multiple →
  newest.
- `find_shadow_pane` sync and async; `capture_shadow_text` argv (`--deep`,
  script path) and the `SHADOW_PLAN_CAPTURE_LINES` env override with inherited
  `PATH`; the no-stamp-from-a-non-shadow-caller assertion.
- `compute_shadow_staleness`: one test per row of the table in Step 7.
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
- **Concurrency** — a shadow refresh interleaved *inside* a full refresh in both
  orders leaves the newer content for the refreshed key and every other key
  intact; a merge is dropped after its shadow is removed by a full refresh; and
  a **negative control** proving `refresh_shadow_snapshot` never bumps
  `capture_generation` (so `test_monitor_shadow_status.py::SupersessionTests`
  stays green).

Regression net — must pass with **only** import-path edits:

```bash
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_tui_clipboard_seam.sh
```

especially `tests/test_minimonitor_concern_action.py`,
`tests/test_minimonitor_shadow_pick.py`, `tests/test_concern_parser.py`,
`tests/test_monitor_shadow_status.py`.

## Notes for sibling tasks

- `refresh_shadow_snapshot` returns `None` for an unknown followed pane by
  design (rule 3). t1216_2's fast tick must treat that as "no update this tick",
  not as "shadow gone" — the full refresh owns deletion.
- `_SENTINEL_SAFE_COLS` and `_SHADOW_DEEP_RETRY_LINES` are exported for t1216_3.
- The **sync** `find_shadow_pane` is what t1216_4's duplicate guard needs.
