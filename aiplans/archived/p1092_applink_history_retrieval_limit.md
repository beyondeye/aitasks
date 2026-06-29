---
Task: t1092_applink_history_retrieval_limit.md
Base branch: main
plan_verified: []
---

# t1092 — applink history retrieval limit

## Context

The applink "history" RPC lets the mobile companion pull terminal scrollback
(`pane_id, before_line, count` → a keyframe of negative-row_id lines merged
above row 0). It works, but retrievable history is bounded and the user wants
to know *why* and whether the bound can be safely raised — treating the whole
constraint chain, not one constant, as the subject.

## Investigation findings (AC1 — authoritative reason for each constraint)

Constraint chain, from request inward:

1. **Request cap — `_MAX_HISTORY_ROWS = 1000`** (`.aitask-scripts/applink/router.py:43`,
   enforced `router.py:378-379`: `count<1 or count>1000` → `BAD_PAYLOAD`).
   Single hardcoded constant; not negotiated or versioned. Caps the `count`
   field only. **Non-binding today** — capture retains far fewer lines than
   1000, so this cap never actually limits the user. Cited in: `router.py`,
   `tests/test_applink_router.sh` (uses `count: 10**9`, so robust to any value
   change — does *not* pin the exact boundary).

2. **Capture depth — `capture_lines = 200` ← THE REAL LIMITER.**
   The applink server reads `config["capture_lines"]` (`server.py:90`), which is
   the **monitor's shared** `tmux.monitor.capture_lines` (default 200 at
   `monitor/monitor_core.py:1460`; set in `aitasks/metadata/project_config.yaml:16`).
   The capture is `tmux capture-pane -p -e -t <pane> -S -<capture_lines>`
   (`monitor_core.py:1178-1182`). `content.history_rows()` (`content.py:409-449`)
   reads negative rows from *this* captured buffer; running off the top yields an
   **empty** keyframe (`content.py:444-445`, `break`). Effective scrollback
   available to history ≈ `capture_lines − viewport_height` ≈ 200 − ~50 = **~150
   lines**. Raising `_MAX_HISTORY_ROWS` alone changes nothing.
   - The knob is *already* user-configurable via `project_config.yaml`, **but it
     is shared with the monitor/minimonitor**, which capture every pane on every
     refresh tick (default 3s) and scan the captured text for idle detection.
     Raising the shared value taxes a hot per-tick path for a benefit only the
     occasional on-demand history pull needs. **This coupling is the design smell.**

3. **tmux server `history-limit` (implicit 4th ceiling).** `-S -N` can only
   retrieve what the tmux server itself retains. The framework never sets
   `history-limit`, so the tmux default (**2000 lines**) is a hard ceiling above
   `capture_lines`. Raising capture depth past ~2000 retrieves nothing more
   unless `history-limit` is also raised.

4. **Frame-size ceiling — `MAX_PUSH_FRAME_BYTES = 2 MiB`** (`pusher.py:57`).
   History keyframe is msgpack `encode_keyframe` (`content.py:459-466`):
   `[pane_id, frame_id, cols, rows, cursor, row_list, osc8?]`, each row
   `[row_id, [spans]]`, each span `[text, fg, bg, attrs, width]`
   (`content.py:191-254`). An oversize history frame is **dropped + audited, not
   sent** (`pusher._drain_history` :187-191, off the live `frame_id` chain → no
   corruption; best-effort by design, `content_transport.md:212`,
   `security.md:100-104`).

   **Size estimate (AC2):**
   - Realistic scrollback (text, 1–3 spans/row, 80–200 chars): ~100–300 B/row →
     **1000 rows ≈ 0.1–0.3 MiB**. Comfortably under 2 MiB.
   - Pathological per-cell styling (200-wide, every cell a distinct span):
     ~15–17 B/span × 200 ≈ ~3 KB/row → 1000 rows ≈ ~3 MiB > 2 MiB — **but already
     safely dropped+audited**, no live-state corruption.
   - ⇒ **`MAX_PUSH_FRAME_BYTES` needs no change.** Even a max-count pull stays
     well under it for real content; the adversarial case is already handled.

**Conclusion: the binding limiter is constraint 2 (`capture_lines = 200`), not
the `_MAX_HISTORY_ROWS = 1000` request cap.** Any meaningful relaxation must
deepen capture; raising the request cap alone is theatre.

## Decision (AC2 / AC3) — chosen: decouple history capture

- **`_MAX_HISTORY_ROWS = 1000` — KEEP (no change).** It is a protocol-level DoS
  bound on `count` (scan/keyframe size), not the real limiter. The keyframe size
  is bounded by `count` (≤1000 rows ⇒ ~0.1–0.3 MiB realistic, safe under 2 MiB),
  independent of capture depth. → `tests/test_applink_router.sh` count-cap
  assertion is **unchanged** (we are not moving the cap).
- **`MAX_PUSH_FRAME_BYTES = 2 MiB` — KEEP (no change).** Bounded by `count`
  (above); the adversarial per-cell case is already dropped+audited safely (off
  the live chain).
- **Capture depth — DECOUPLE, via a precise per-request depth.** Give the applink
  history RPC its **own** on-demand capture, separate from the monitor's live
  `capture_lines` (**stays 200**).
  - **Precise semantics (concern: depth ≠ retrievable scrollback).** A tmux
    capture of N lines = viewport (`pane.height` rows) **+** N−height scrollback
    rows; `history_rows()` only serves the scrollback *above* the viewport. So
    retrievable ≈ `depth − pane.height`, NOT `depth`. We therefore **compute the
    depth per request** from what is actually asked:
    `depth = min(history_capture_lines, pane.height + count + max(0, -before_line))`.
    The drain already knows `pane.height` (from `_pane_cache`), `count`, and
    `before_line`, so this serves the full requested `count` (up to buffer
    availability) regardless of viewport height — never over-captures.
  - **`history_capture_lines` is a CEILING (clamp), default 2000** — the max
    single-history capture depth, aligned with tmux's own default server
    `history-limit` (~2000, the real hard ceiling). It is **not** a fixed depth.
- **AC4 (out-of-scope follow-up):** per-session / negotiated history-depth
  override (client requests a depth; server clamps) is **not** implemented here
  — file as a follow-up. Likewise raising tmux server `history-limit` (default
  2000) is out of scope. At the **default `history_capture_lines = 2000`** the
  config ceiling coincides with tmux's default `history-limit` (2000), so they
  are consistent out of the box; raising the config past ~2000 (up to the 10000
  load clamp) yields no further scrollback unless tmux's own `history-limit` is
  also raised. Note both explicitly.

## Implementation

### 1. Monitor: NON-MUTATING raw deep capture (concern 1 — the critical fix)
`.aitask-scripts/monitor/monitor_core.py`
- `_capture_args(self, pane_id, capture_lines=None)` — `n = self.capture_lines
  if capture_lines is None else capture_lines`; use `-S -{n}` (line 1178-1182).
  Backward-compatible: default `None` = today's `-S -200`.
- **Add a new raw capture that does NOT call `_finalize_capture`:**
  ```python
  async def capture_pane_content_async(self, pane_id, capture_lines=None):
      """Raw one-shot capture for consumers (history RPC) that must NOT perturb
      idle/awaiting-input state. Returns (pane, content) or None. Unlike
      capture_pane_async it does NOT touch _last_content / _last_change_time."""
      pane = self._pane_cache.get(pane_id)
      if pane is None:
          return None
      rc, content = await self._tmux_async(self._capture_args(pane_id, capture_lines))
      if rc != 0:
          return None
      return pane, content
  ```
- **Why this matters:** `_finalize_capture` (lines 1145-1148) writes
  `_last_content`/`_last_change_time` for idle + prompt detection. Reusing the
  finalizing `capture_pane_async` for a *different-depth* history capture would
  reset the pane's idle state (then the next 200-line live capture resets it
  again), corrupting the applink server's **own** idle/awaiting-input detection
  — the `pane_status` heartbeat that drives mobile badges. The raw method keeps
  idle state driven **solely** by the live `capture_all_async` path. The
  existing `capture_pane`/`capture_pane_async` finalizing methods get the
  optional `capture_lines` arg too (consistency), but the history drain uses the
  **non-finalizing** one.

### 2. Pusher: per-request deep capture for the history drain
`.aitask-scripts/applink/pusher.py`
- Add module const `DEFAULT_HISTORY_CAPTURE_LINES = 2000` (ceiling; comment:
  applink-only, decoupled from the monitor's live `capture_lines`, aligned with
  tmux's default `history-limit`).
- `PushScheduler.__init__(..., history_capture_lines=DEFAULT_HISTORY_CAPTURE_LINES)`
  → store `self._history_capture_lines`.
- `_drain_history(self, sub)` — **drop the `snaps` param**; per pending pull:
  ```python
  for pane_id, before_line, count, _token in sub.take_pending_history():
      if self._stopped: return
      cached = self._monitor.get_pane(pane_id)          # read pane cache ONCE
      # only capture what THIS request can use (viewport + count + scroll), clamped
      depth = self._history_capture_lines
      if cached is not None:
          depth = min(depth, cached.height + count + max(0, -before_line))
      cap = await self._monitor.capture_pane_content_async(pane_id, depth)
      if cap is None: continue
      pane, text = cap
      cols, rows_h = pane.width, pane.height
      rows, osc8 = content.history_rows(text, rows_h, before_line, count)
      ...   # frame_id read, encode_keyframe, best-effort _send — unchanged
  ```
  (`get_pane` at monitor_core.py:1193 is a no-subprocess `_pane_cache` accessor,
  already used by the router — reuse it to read `pane.height` for the depth calc.)
- Update call site `_run_once` (line 161): `await self._drain_history(sub)`.
- Update the docstring: history takes a **fresh, request-sized, non-finalizing**
  capture at drain time — not this tick's live `snaps`; still best-effort, off
  the live `frame_id` chain, exact for idle panes.

### 3. Server: load + thread the applink config (with clamp)
`.aitask-scripts/applink/server.py`
- Add a small `load_applink_config(project_root)` helper (mirrors
  `load_monitor_config`'s yaml read) that reads
  `tmux.applink.history_capture_lines` and **clamps it to a sane range at load
  time** (runtime bound, not a comment — concern 3). Must be **fault-tolerant**
  (missing file / missing `tmux` or `applink` key / non-dict / non-int / negative
  / null → fall back to the default, never raise):
  ```python
  DEFAULT_HISTORY_CAPTURE_LINES = 2000
  HARD_MAX_HISTORY_CAPTURE_LINES = 10000
  def load_applink_config(project_root):
      lines = DEFAULT_HISTORY_CAPTURE_LINES
      try:
          import yaml
          data = yaml.safe_load((project_root/"aitasks"/"metadata"/"project_config.yaml").read_text()) or {}
          raw = (data.get("tmux") or {}).get("applink", {}).get("history_capture_lines")
          if raw is not None:
              lines = max(1, min(int(raw), HARD_MAX_HISTORY_CAPTURE_LINES))
      except Exception:
          pass   # any malformed config → safe default
      return {"history_capture_lines": lines}
  ```
  Kept in the applink package (not in `load_monitor_config`) to keep monitor vs
  applink config domains separate.
- In `__init__`, read it and pass through `_ensure_pusher` (lines 243-248):
  `PushScheduler(conn, ws, self._monitor, audit=self._audit,
  history_capture_lines=self._history_capture_lines)`.
- **DoS is now runtime-bounded** twofold: the loader clamps the *config* to
  ≤10000, and each request captures only `min(ceiling, height + count + scroll)`
  with `count ≤ _MAX_HISTORY_ROWS (1000)` — so a single tmux capture is bounded
  regardless of config, and the keyframe is bounded by `count`.

### 4. Config (shipped + seed)
- `aitasks/metadata/project_config.yaml` — add under `tmux:` a new
  `applink:\n    history_capture_lines: 2000` block, commented: it is the
  **ceiling** on a single on-demand history capture (per-request depth is sized
  to `viewport + count`), distinct from `monitor.capture_lines`, clamped to
  ≤10000 at load, and itself bounded by tmux's server `history-limit` (~2000).
- `seed/project_config.yaml` — mirror the same block for fresh installs.

### 5. Docs (AC1/AC2 truth-sync)
- `aidocs/applink/content_transport.md` — §Scrollback (line ~220) and the
  "anchored to the drain-time capture / same snapshot as that tick's live frame"
  bullet: history now reads a **dedicated request-sized capture** (depth sized to
  `viewport + count`, ceiling `history_capture_lines`, default 2000), not the
  monitor's ~200-line live buffer; replace the "~200 lines" / "same snapshot as
  that tick's live frame" wording accordingly (keep the best-effort +
  contiguous-from-`-1` + empty-past-buffer semantics).
- `aidocs/applink/security.md` — note the deeper history capture is still
  DoS-bounded by the `_MAX_HISTORY_ROWS` count cap and the 2 MiB frame drop
  (deeper scan, but count- and frame-size-bounded).
- `aidocs/applink/protocol.md` — if the history verb section cites ~200, update;
  add the per-session-override as a noted future extension (AC4).

### 6. Tests
`tests/test_applink_pusher.sh`
- `FakeMonitor`: add `get_pane(self, pane_id)` (returns the pane so the drain can
  read `height`) and `async def capture_pane_content_async(self, pane_id,
  capture_lines=None)` that **records** the requested `capture_lines` and returns
  **depth-aware content** — shallow (e.g. last ~200 lines) when `capture_lines`
  is small, the full deep buffer only when the override is large. This defeats
  the false-confidence trap (concern 4): the old snaps-based code could not have
  returned the deep rows, because the fake now gates depth on the arg.
- Update the existing history tests that call `_drain_history(sub, snaps)`
  (~lines 577, 613, 792) to the new `_drain_history(sub)` signature.
- **Decouple assertions:**
  1. After a pull, assert the recorded `capture_lines` ==
     `min(history_capture_lines, height + count + max(0,-before_line))`
     (the per-request sizing), proving history no longer rides the 200-line live
     capture and is sized to the request.
  2. Behavioral: a deep fake buffer + a `before_line` past the old ~200 bound
     returns rows the shallow capture could not — and returns the full `count`.
- **Concern-1 guard (most important, real `TmuxMonitor`, not the fake):** a
  small unit that captures a pane via `capture_pane_content_async(pane_id, 1500)`
  and asserts `_last_content` / `_last_change_time` are **unchanged** (idle state
  untouched), versus `capture_pane_async` which *does* mutate them. Also assert
  `_capture_args(pane_id, 1500)` contains `-S -1500` and `_capture_args(pane_id)`
  still contains `-S -200`. (1500 is an arbitrary depth chosen distinct from both
  200 and the 1000 count cap to avoid conflation.) (Add to `tests/test_applink_pusher.sh` or the nearest
  monitor_core test harness, whichever already constructs a `TmuxMonitor`.)
- Run `bash tests/test_applink_pusher.sh` and `bash tests/test_applink_router.sh`
  (router unchanged — must still pass green).

### 7. Config + threading tests (concern: silent default fallback)
`tests/test_applink_server_limits.sh` (already imports `server as SV` /
`AppLinkServer` and builds via `AppLinkServer.__new__`).
- **`load_applink_config` matrix** — write a temp `project_config.yaml` into a
  tmpdir `aitasks/metadata/` and call `SV.load_applink_config(tmp_root)`; assert:
  - no `tmux.applink` key (or missing file) → **2000** (default)
  - `tmux.applink.history_capture_lines: 3000` → **3000**
  - over-ceiling `999999` → **clamped to 10000**
  - malformed (`"abc"` / `-5` / `null`) → **2000** (graceful fallback, no raise)
  This pins the exact YAML path (`tmux.applink.history_capture_lines`) and the
  clamp, so a nesting/path typo fails the test instead of silently defaulting.
- **Threading** — assert the value actually reaches the scheduler:
  `PushScheduler(conn, ws, mon, history_capture_lines=4242)._history_capture_lines
  == 4242`, and the default-construction case `== DEFAULT_HISTORY_CAPTURE_LINES`.
  (Lightweight constructor check; `_ensure_pusher` passes the server-loaded value
  through verbatim.)

## Verification

1. `shellcheck` N/A (Python). Run the affected bash test harnesses:
   `bash tests/test_applink_pusher.sh`, `bash tests/test_applink_router.sh`, and
   `bash tests/test_applink_server_limits.sh` — all PASS.
2. Sanity-import the Python modules (no syntax/wiring breakage):
   `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/applink'); import pusher, server, content"`.
3. Confirm the monitor's live path is untouched: grep that
   `capture_all_async` / minimonitor / shadow callers pass **no** depth arg.
4. **Live (coordinate with t1088, do NOT duplicate):** the end-to-end check that
   a real mobile client can now scroll back >~150 lines is the manual
   history-coordinate verification already owned by **t1088**. Flag there that
   the server now serves up to the requested `count` (≤1000) of scrollback,
   capped by the `history_capture_lines` ceiling (default 2000) and tmux's
   `history-limit`; the mobile loading-indicator follow-up
   (aitasks_mobile#25) must still treat an empty deep keyframe as "no more
   history", not a hang.

## Risk

### Code-health risk: low
- Touches the load-bearing `monitor_core.py` capture path: a backward-compatible
  optional `capture_lines` arg (default `None` = today's behavior) **plus** a new
  **non-finalizing** `capture_pane_content_async`. The non-finalizing method is
  the deliberate guard against the idle-state-corruption failure mode — history
  captures never write `_last_content`/`_last_change_time`, so idle/awaiting
  detection stays driven solely by the live path · severity: low · → mitigation:
  None (pinned by the concern-1 non-mutation unit test + existing tests green)
- `_drain_history` changes its capture source (this-tick `snaps` → fresh
  request-sized capture) and signature, within already-documented best-effort /
  non-anchored history semantics; off the live `frame_id` chain so no live-state
  regression · severity: low · → mitigation: None (drain path unit-tested; new
  tests pin per-request depth + deep-row behavior)

### Goal-achievement risk: low
- Effectiveness of a large `history_capture_lines` ceiling is silently bounded by
  tmux's own server `history-limit` (default ~2000); at the chosen default 2000
  the two coincide, but a user raising the config past ~2000 (up to the 10000
  load clamp) sees no further gain unless tmux's `history-limit` is also raised ·
  severity: low · → mitigation: documented explicitly in config comment + docs
  (AC4 note)

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned (decouple history capture).
  - `monitor_core.py`: added optional `capture_lines` override to `_capture_args`,
    `capture_pane`, `capture_pane_async`; added the non-finalizing
    `capture_pane_content_async` returning `(pane, content)`.
  - `pusher.py`: `DEFAULT_HISTORY_CAPTURE_LINES = 2000`; `PushScheduler`
    `history_capture_lines` kwarg; `_drain_history(sub)` now takes a fresh,
    request-sized (`min(ceiling, height + count + max(0, -before_line))`),
    non-finalizing capture per pull; `_run_once` call site updated.
  - `server.py`: `load_applink_config()` (fault-tolerant; clamps to
    `[1, 10000]`, sub-1 → default) + `HARD_MAX_HISTORY_CAPTURE_LINES = 10000`;
    threaded into `_ensure_pusher` via `getattr` (tolerates `__new__` test build).
  - Config: documented `tmux.applink.history_capture_lines` in `seed/` (commented)
    and the active `aitasks/metadata/project_config.yaml` (value 2000).
  - Docs: `content_transport.md` §Scrollback truth-synced (dedicated request-sized
    non-finalizing capture, not the live ~200 buffer) + AC4 out-of-scope note;
    `security.md` DoS-bounding paragraph.
  - Tests: `test_applink_pusher.sh` (+ per-request depth assertion, deep-scrollback
    behavioral discriminator, concern-1 real-`TmuxMonitor` non-mutation guard);
    `test_applink_server_limits.sh` (load_applink_config matrix: default / missing
    file / configured / over-ceiling clamp / malformed→default, + scheduler
    threading).
- **Deviations from plan:** One refinement during review-driven implementation:
  the loader treats a sub-1 value (`-5`, `0`) as malformed → default 2000 rather
  than clamping to 1 (the approved pseudocode showed `max(1, min(...))`); this
  better matches "malformed → safe default" and is pinned by the config matrix.
- **Issues encountered:** None. The per-request depth formula is self-consistent
  with `history_rows()` (`base = total − viewport_height` shifts with the trimmed
  capture), so capturing exactly `viewport + count` yields the same rows as a
  full-buffer capture — verified by the existing drain tests staying green.
- **Key decisions:** Non-finalizing capture is the load-bearing choice — reusing
  the finalizing `capture_pane_async` at a deeper depth would have corrupted the
  applink server's own idle/awaiting-input detection (the `pane_status` mobile
  badge heartbeat). `_MAX_HISTORY_ROWS` (1000) and `MAX_PUSH_FRAME_BYTES` (2 MiB)
  were deliberately left unchanged (count-bounded keyframe stays safe).
- **Upstream defects identified:** None.
- **Coordination:** Live end-to-end scrollback verification is owned by t1088
  (history coordinate-verify); paired mobile follow-up is aitasks_mobile#25
  (loading indicator must treat an empty deep keyframe as "no more history").
  AC4 follow-up (client-negotiated/per-session history depth) noted out-of-scope
  in `content_transport.md`.

