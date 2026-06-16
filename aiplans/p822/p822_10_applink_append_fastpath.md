---
Task: t822_10_applink_append_fastpath.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_11_applink_modal_handshakes.md, aitasks/t822/t822_12_applink_permissions_doc_sync.md, aitasks/t822/t822_13_applink_headless_monitor_flag.md, aitasks/t822/t822_14_applink_push_scheduler_resilience.md
Archived Sibling Plans: aiplans/archived/p822/p822_6_extract_monitor_core.md, aiplans/archived/p822/p822_7_applink_websocket_listener.md, aiplans/archived/p822/p822_8_applink_snapshot_push_loop.md, aiplans/archived/p822/p822_9_applink_delta_engine.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t822_10 — applink append fast path (data plane Stage 3)

## Context

Parent **t822** builds `ait applink`, streaming desktop tmux panes to a mobile
companion over a paired LAN WebSocket. The data plane has shipped in stages:
**t822_8** = Stage 1 (`keyframe`/`cursor`/`dim` full-grid push), **t822_9** =
Stage 2 (`delta` — changed rows only against a per-connection `row_sigs`
baseline). This task adds **Stage 3: the `append` fast path (0x03)** for
log-streaming panes (`tail -f`, agent logs, build output): when a pane scrolls up
by *k* rows with *k* brand-new rows at the bottom, emit a tiny `append` frame
carrying only the new bottom rows instead of a near-full `delta`.

The t822_9 plan explicitly reserved the hooks: `FRAME_APPEND = 0x03` is already
defined in `content.py`; the per-connection `PaneState.row_sigs` baseline and the
deltifier sit right where the append detector belongs; and its Final Notes say
"`append` (0x03) slots in *before* the delta path on bottom-growth detection".

Wire format (`content_transport.md` §append, **fixed** — this task consumes it):

```
[0x03, pane_id, frame_id, [row, row, ...]]
```

No `prev_frame_id`, **no `osc8` sidecar**. Client appends the rows at the bottom
and drops the topmost rows to keep the row count from the latest keyframe.

### Key design decision — correctness comes from *exact shift detection*

`append` is convergence-safe **iff** the new snapshot equals the baseline
scrolled up by *k* with *k* brand-new bottom rows. The client applies an append
by: drop *k* top rows, shift the rest up, append the *k* received rows at the
bottom. The reconstructed buffer `C` is then `C[i] = prev[i+k]` for
`i ∈ [0, H-1-k]` and `C[H-k+j] = received[j]`. For `C == new` we need:

- `new[i] == prev[i+k]` for all `i ∈ [0, H-1-k]` — **the shift condition we
  verify** (the design doc's "cheap prefix comparison").
- `received[j] == new[H-k+j]` — guaranteed because we *send* exactly the new
  snapshot's bottom *k* rows.

So if the shift condition holds for the *k* we detect, and we send the new
bottom *k* rows, convergence is automatic. This is the same independent-ground-
truth discipline t822_9 used: an `append` produces on the client exactly what a
fresh keyframe of the new content would. The spec's looser wording ("no rows
above the bottom changed") is interpreted as this exact full-viewport scroll —
pinned in the docs (Step 1) so mobile and server agree.

Consequences of this interpretation (all conservative — never incorrect, only
"fewer appends"):

- **Cursor must be unchanged AND at the bottom row.** `append` carries **no
  cursor payload** ("no cursor change implied"), and the pusher does not send
  standalone `cursor` (0x04) frames — so an append leaves the client's cursor
  exactly as the previous frame set it. Gating only on the cursor *row* would let
  an append fire while the cursor *column / visibility / style* changed (e.g. an
  in-place progress bar redrawing the bottom line), stranding the client with a
  stale cursor. We therefore require the **full cursor tuple to be identical to
  the last sent frame's** (`cursor == st.last_cursor`) *and* at the bottom row
  (`cursor[0] == rows-1`). For continuous log output the cursor sits unchanged at
  the bottom-left, so appends fire; any cursor motion (col/visibility/style) or a
  mid-screen TUI falls back to `delta` (which *does* carry the cursor). This is
  the correctness gate for cursor-state convergence — distinct from the
  shift condition, which is the correctness gate for row-content convergence.
- **Alt-screen / scroll-region is NOT explicitly checked** — `PaneSnapshot`
  exposes no alt-screen flag. This is a **deliberate conservative choice, not a
  satisfaction of the spec's "no scroll-region/alt-screen" signal**: we do not
  detect alt-screen; we rely on exact-shift detection, under which a vim/htop
  redraw simply fails the shift check and falls back to `delta`. If an alt-screen
  frame *coincidentally* were an exact full-viewport shift it would be sent as an
  append — and that is still **correct** (the client converges to the same grid a
  keyframe would produce), but we are honest that the original "no alt-screen"
  condition is replaced by "exact shift + unchanged cursor", not literally
  implemented. Pinned as such in the docs (Step 1).
- **Blank trailing cursor line phase.** A streaming pane alternates between a
  "bottom row has the newest line" snapshot (clean shift → append) and a "bottom
  row is the blank cursor line" snapshot (rows above the blank shifted, blank
  stayed → not a full-viewport shift → `delta`). So output streams as
  *predominantly* appends interleaved with small deltas — matching the task's
  "predominantly `append` frames" acceptance criterion.
- **Underfilled viewport / bottom-fill-without-scroll** → no shift → `delta`
  (cheap, the one new row is a 1-row delta). Append targets the full-screen
  scrolling steady state where bandwidth matters.
- **Hyperlinks.** `append` carries no `osc8` sidecar in the fixed wire format.
  If any appended row contains an OSC8 hyperlink we **fall back to `delta`**
  (which does carry `osc8`) rather than silently dropping the URL. Log output
  rarely contains hyperlinks, so this costs little. (Not a wire change — the
  fixed format is respected.)

## Implementation

> **Ordering:** docs/contract pin (Step 1) first, then code (Steps 2–3), then
> tests (Steps 4–5) — same discipline as t822_9, so tests encode the pinned
> conventions rather than an un-pinned guess.

### Step 1 — Pin the append detection + row-id conventions (do first)

**1a. `aidocs/applink/content_transport.md` §append** — add two clarifying
sentences (the schema itself is unchanged):

- The server emits `append` only on an **exact full-viewport scroll**: the new
  grid equals the previous grid shifted up by *k* (`1 ≤ k < rows`) with *k*
  brand-new rows at the bottom, **and the cursor is unchanged and at the bottom
  row**. (The server does not detect alt-screen explicitly — see the conservative
  choice noted in §Append fast-path detection.) The appended rows carry their
  **new absolute `row_id`s** (`rows-k … rows-1`); after the client drops *k* top
  rows and shifts, the appended rows land at exactly those positions (consistent
  with `keyframe`/`delta` row-id = viewport position).
- `append` carries **no cursor**: the client keeps the cursor from the previous
  frame (the server only emits an append when the cursor did not change).
- The client **adopts the append's `frame_id` as its current frame_id** even
  though the append has no `prev_frame_id`; a subsequent `delta`'s `prev_frame_id`
  then equals the append's `frame_id` and the linear gap-check still works. A run
  of appends cannot self-detect a *lost* append (no `prev_frame_id` chain);
  recovery rests on two existing guarantees: the WebSocket transport is **ordered
  and reliable** (a dropped frame breaks the connection → reconnect → fresh
  keyframe), and the **keyframe interval** forces a periodic full keyframe that
  re-syncs any accumulated drift. This is the same recovery model deltas rely on.
- `append` has no `osc8` sidecar, so the server sends a `delta` (which does)
  whenever an appended row carries a hyperlink. Mobile may therefore assume
  `append` rows never set the OSC8 attr bit.

**1b. `aidocs/applink/monitor_port_design.md` §Append fast-path detection** —
replace the one-line placeholder with the implemented reality: detector
`detect_append` lives in `applink/content.py` next to `deltify`, keyed off the
same per-connection `PaneState.row_sigs`; it's a prefix comparison of row
signatures (full-viewport shift); the `append` emit slots into `pusher._push_pane`
*before* the delta path; the cursor gate requires the full cursor tuple unchanged
and at the bottom row (a new `PaneState.last_cursor`), since `append` carries no
cursor. Note explicitly that alt-screen is **not** detected (no snapshot signal);
exact-shift + unchanged-cursor is the deliberate conservative substitute, and a
coincidental alt-screen shift is still convergence-correct.

**1c. Cross-repo coordination (flag, don't assume).** The append row-id basis
and the "hyperlink → delta fallback" are **new contract** for the mobile decoder
in `../aitasks_mobile`. Record them in this plan's Final Notes "Mobile note" and
add a one-line pointer in **t822_12** (`applink_permissions_doc_sync`, the
mobile-facing sibling) via `./ait git` — exactly as t822_9 did for its delta
conventions. (AC note: the task file does not currently mention t822_12; this is
a bidirectional-coordination link, not a scope change.)

### Step 2 — `applink/content.py`: `encode_append` + `detect_append` (pure)

**`encode_append`** (next to `encode_delta`, lazy msgpack via `_packb`;
`FRAME_APPEND = 0x03` already defined):

```python
def encode_append(pane_id, frame_id, row_list) -> bytes:
    """`append` (0x03): rows appended at the bottom of the client buffer; the
    client drops the topmost rows to keep the row count from the latest
    keyframe. Carries NO prev_frame_id (each append stacks on the latest visible
    state) and NO osc8 sidecar (content_transport.md §append) — the caller emits
    a `delta` instead when an appended row carries a hyperlink. Wire array:
    [pane_id, frame_id, row_list]."""
    return bytes([FRAME_APPEND]) + _packb([pane_id, frame_id, row_list])
```

**`detect_append`** (next to `deltify`):

```python
def detect_append(prev_sigs, new_sigs):
    """Detect a pure bottom-growth scroll: the new grid is the baseline scrolled
    up by k rows (1 <= k < H) with k brand-new rows at the bottom. Returns k, or
    None when it is not such an append (caller falls back to delta).

    prev_sigs / new_sigs are {row_id: sig} over a full snapshot each (contiguous
    0..H-1, as parse_snapshot produces). Requires equal row counts H (a clean
    scroll keeps the viewport height). The check is the cheap prefix comparison
    the design doc calls for: new[i] == prev[i+k] for all i in [0, H-1-k]. The
    smallest matching k is returned (and is the correct one — the shift condition
    is fully verified for it, so client convergence is guaranteed)."""
    if prev_sigs is None:
        return None
    H = len(new_sigs)
    if H == 0 or len(prev_sigs) != H:
        return None
    for k in range(1, H):
        if all(new_sigs.get(i) == prev_sigs.get(i + k) for i in range(H - k)):
            return k
    return None
```

Also extend the module docstring's Stage-3 sentence to name `detect_append` /
`encode_append`.

### Step 3 — `applink/pusher.py`: try `append` before the delta path

Add one field to `PaneState` in `content.py` (the full before-cursor state —
`append` carries no cursor, so we must confirm the cursor did not change):

```python
last_cursor: Optional[list] = None   # [row, col, visible, style] at the last sent frame
```

In `_push_pane`, the change/cadence gate, the cursor capture, and `new_sigs`
computation (lines 128–137) stay as-is. Rewrite the emit selection (current
lines 143–185) to try `append` first:

```python
emit_keyframe = forced or interval_due or st.row_sigs is None
sent_keyframe = False
sent_append = False
bottom_row = dims[1] - 1

if not emit_keyframe:
    # Stage 3 (t822_10): append fast path — the new grid is the baseline scrolled
    # up by k with k brand-new bottom rows, with the cursor UNCHANGED and at the
    # bottom row (append carries no cursor, so the client keeps the prior one).
    # Tried before the delta path; falls back to a delta when it does not apply.
    # `append` carries no osc8 either, so a hyperlink in the new rows also forces
    # the delta path (which does carry the sidecar).
    k = content.detect_append(st.row_sigs, new_sigs)
    if (k is not None
            and cursor[0] == bottom_row
            and st.last_cursor == cursor):           # full tuple unchanged since last frame
        appended = parsed[len(parsed) - k:]                 # (row_id, spans, urls)
        if not any(urls for _r, _s, urls in appended):      # no OSC8 -> append ok
            append_wire = [[row_id, spans] for row_id, spans, _u in appended]
            frame_id = sub.next_frame_id(pane_id)           # bump the monotonic chain
            await self._send(content.encode_append(pane_id, frame_id, append_wire))
            sent_append = True

    if not sent_append:
        changed_wire, removed, _ns, changed_subset = content.deltify(st.row_sigs, parsed)
        if not changed_wire and not removed:
            st.last_hash = content_hash
            return
        if len(changed_wire) + len(removed) >= len(parsed):
            emit_keyframe = True
        else:
            delta_wire = changed_wire + [[row_id, []] for row_id in removed]
            prev_frame_id = st.frame_id
            frame_id = sub.next_frame_id(pane_id)
            await self._send(content.encode_delta(
                pane_id, frame_id, prev_frame_id, cursor, delta_wire,
                content.build_osc8(changed_subset) or None,
            ))

if emit_keyframe:
    full_rows = [[row_id, spans] for row_id, spans, _u in parsed]
    frame_id = sub.next_frame_id(pane_id)
    await self._send(content.encode_keyframe(
        pane_id, frame_id, dims[0], dims[1], cursor, full_rows,
        content.build_osc8(parsed) or None,
    ))
    sent_keyframe = True

st.row_sigs = new_sigs
st.last_hash = content_hash
st.last_dims = dims
st.last_cursor = list(cursor)           # NEW: full before-cursor for the next tick
if sent_keyframe:
    st.last_keyframe_t = now
st.last_send_t = now
sub.force.discard(pane_id)
```

Key points:
- **`append` bumps `frame_id`** via `next_frame_id` and the common tail stores
  `new_sigs` as the new baseline, so a subsequent `delta`'s `prev_frame_id`
  (`= st.frame_id`) correctly points at the append's frame_id — the monotonic
  chain stays linear even though the append itself carries no `prev_frame_id`.
- **`last_keyframe_t` is *not* touched by an append**, so the keyframe-interval
  drift bound still forces a periodic full keyframe through a long append run
  (defends against accumulated divergence; matches the spec recovery model).
- `last_cursor` (the full `[row, col, visible, style]`) is updated on every sent
  frame (keyframe/delta/append), so the next tick's "before" check reflects the
  cursor state the client actually holds — and an append fires only when that
  cursor is unchanged, keeping the client's (uncarried) cursor correct.
- Also update the `pusher.py` module docstring's Stage banner to mention Stage 3.

### Step 4 — `tests/test_applink_content.sh` (extend, pure)

Add, in the existing skip-if-no-msgpack harness:
- `encode_append`: leading `0x03`; `unpackb(rest) == [pane_id, frame_id, rows]`;
  exactly 3 elements (never an osc8 sidecar).
- `detect_append`:
  - clean scroll-by-1 (`prev=[A,B,C]`, `new=[B,C,D]`) → `1`.
  - clean scroll-by-2 (`prev=[A,B,C,D]`, `new=[C,D,E,F]`) → `2`.
  - repeated-line scroll (`prev=[A,A,A]`, `new=[A,A,B]`) → `1` (convergence-safe).
  - mid-screen edit (only row 1 changed) → `None`.
  - full replacement (no shared row) → `None`.
  - differing row counts → `None`.
  - `None` baseline → `None`.

  Build signature dicts the same way the pusher does:
  `{rid: C.row_signature(spans) for rid, spans, _u in C.parse_snapshot(text)}`.

### Step 5 — `tests/test_applink_pusher.sh` (extend, async) — INDEPENDENT convergence

Add an append block after the delta block, reusing `FakeWS`/`FakeMonitor`/
`FakePane`/`FakeSnap` + the injected clock. Use a **positional** in-test client
(a list of rows by viewport position) decoded **only from wire bytes** and
compared to a direct parse of the content — never to another pusher artifact (the
t822_9 independent-decoder discipline, adapted to append's shift semantics):

```python
def apply_kf_list(frame):
    body = msgpack.unpackb(frame[1:], raw=False, strict_map_key=False)
    return [spans for _rid, spans in body[5]]        # full grid in order
def apply_append_list(client, frame):
    body = msgpack.unpackb(frame[1:], raw=False, strict_map_key=False)
    newrows = [spans for _rid, spans in body[2]]     # append rowlist
    k = len(newrows)
    return client[k:] + newrows                      # drop k top, append k bottom
def truth_list(text):
    rows = dict(C.snapshot_to_rows(text)[0])
    return [rows[i] for i in range(len(rows))]
```

**Explicit fixture (do not rely on defaults):** the pane MUST be created with a
height matching the parsed row count, or `cursor[0] == bottom_row` can never hold
(`detect_append` uses `len(new_sigs)` while the cursor gate uses `dims[1] - 1`).
Use a 3-row pane and 3-line content throughout the append block:

```python
paneA = C.FakePane("%1", width=80, height=3)   # bottom_row = 2
monA  = FakeMonitor(); monA.cursor = (2, 0, True, 0)   # at bottom, col 0
monA.snaps["%1"] = FakeSnap(paneA, "a\nb\nc\n")        # parses to exactly 3 rows
```

Cases:
- **keyframe seed** → positional client == `truth_list("a\nb\nc\n")`.
- **scroll-by-1** (`"a\nb\nc\n"` → `"b\nc\nd\n"`, cursor still `(2,0,True,0)`) →
  exactly one `0x03` append frame carrying one row;
  `apply_append_list` → client == `truth_list("b\nc\nd\n")`.
- **chain + convergence** (`→ "c\nd\ne\n"`) → another append; convergence holds.
- **append frame_id == previous frame_id + 1** (monotonic chain across appends).
- **append carries no cursor / no osc8 / no prev** → decoded body has exactly 3
  elements (`[pane_id, frame_id, rows]`).
- **delta-after-append chains (concern: gap detection)** — after the appends, a
  mid-screen edit (`"c\nd\ne\n"` → `"c\nX\ne\n"`) → a `0x02` delta whose
  `prev_frame_id` equals the **last append's frame_id** (proves the client can
  adopt the append's frame_id and still gap-check the following delta).
- **cursor moved but still at bottom (concern: cursor drift)** — from a clean
  scroll state, change `monA.cursor` to `(2, 5, True, 0)` (same row, different
  column) and feed a scroll snapshot → frame is **not** `0x03`; a `0x02` delta is
  emitted instead (which carries the new cursor). Asserts the full-tuple gate.
- **cursor not at bottom** (separate scheduler, `mon.cursor = (0, 0, True, 0)`,
  then a scroll) → frame is **not** `0x03` (append suppressed by the row gate).
- **hyperlink in the appended row** → scroll where the new bottom row contains an
  OSC8 span → a `0x02` delta (osc8-bearing), **not** an append.

## Risk

### Code-health risk: low
- Edits the `_push_pane` emit selection (load-bearing since t822_8/t822_9); a
  detection bug could cause silent client divergence. · severity: low · →
  mitigation: `detect_append` is a pure, unit-tested function; the emit path
  only *adds* a branch tried before the existing delta path and is fully
  convergence-guarded (shift condition verified before emit); the
  independent-decoder positional convergence test reconstructs the client buffer
  from wire bytes and compares to a direct parse, so a systematic bug cannot pass
  by corrupting both sides; blast radius confined to the applink package
  (`content.py` + `pusher.py` + two test files + two doc clarifications).
- New `PaneState.last_cursor_row` field. · severity: low · → mitigation: defaults
  to `None` (append never fires until a frame sets it); updated uniformly in the
  common send tail.

### Goal-achievement risk: low
- **No real mobile client** (cross-repo, unavailable): append application /
  convergence exercised only against synthetic wire decoding; mobile-decoder
  schema drift possible. · severity: low · → mitigation: append's wire schema is
  already fixed and decoded by mobile from Stage 1; the only new conventions
  (row-id basis, hyperlink→delta) are **pinned in the spec** (Step 1a) and
  **flagged to t822_12** (Step 1c); live verification via the Step 8c
  manual-verification follow-up.
- Spec wording "no rows above the bottom changed" is looser than the implemented
  exact-shift detection. · severity: low · → mitigation: the gap is resolved
  conservatively (fewer appends, never incorrect) and the precise convention is
  pinned in `content_transport.md` so mobile and server agree.

_No `### Planned mitigations` — confirmed "No mitigations": live verification via
the Step 8c follow-up; spec ambiguity resolved in-plan + flagged to t822_12._

## Verification

1. `bash tests/test_applink_content.sh` → PASS (new `encode_append` +
   `detect_append` cases; all existing cases green).
2. `bash tests/test_applink_pusher.sh` → PASS (new append block:
   independent-decoder convergence, chain, monotonic frame_id, mid-screen→delta,
   cursor-gate, hyperlink→delta; existing emit/idle/resize/delta/teardown green).
3. `bash tests/test_applink_router.sh && bash tests/test_applink_smoke.sh && bash
   tests/test_applink_devices.sh` → PASS (no regressions).
4. `python -c "import applink.content, applink.pusher"` (venv) → clean; msgpack
   stays lazily imported.
5. **Live (manual — real mobile client unavailable):** `./ait applink`, scripted
   `python websockets` client, `subscribe` → keyframe; stream `seq 1 1000` in a
   subscribed pane → predominantly `0x03` append frames; open vim and edit
   mid-screen → `delta`/`keyframe`, never `append`. → Step 8c
   manual-verification follow-up.

   **Eyes-open limitation:** the unit tests (1–2) prove *server-side* append
   emission and convergence against an independent decoder, but the append's
   drop-top/shift/append *rendering* and uncarried-cursor handling actually live
   in the mobile client, which is unavailable here. This task does **not** prove
   real client behavior; that is what the Step 8c manual-verification follow-up
   and eventual mobile integration cover. Approval is with that caveat.

## Step 9 (Post-Implementation)

Profile `fast`, current branch (no worktree). Code (`content.py`, `pusher.py`,
tests) via `git`; the two `aidocs/applink/*.md` clarifications + the t822_12
pointer via `./ait git`. Push via `./ait git push`. Archive via
`./.aitask-scripts/aitask_archive.sh 822_10` — parent t822 keeps
t822_11..t822_14 pending.

**Final Notes / Mobile note (append, 0x03):** `[0x03, pane_id, frame_id, [rows]]`
— no `prev_frame_id`, no `osc8`, **no cursor**. Client drops the top `len(rows)`
rows, shifts up, appends `rows` at the bottom; appended rows carry their new
absolute row_ids (`H-k … H-1`). The client **keeps its existing cursor** (the
server only appends when the cursor is unchanged) and **adopts the append's
`frame_id` as current** so a following `delta`'s `prev_frame_id` chains. The
server emits `append` only on an exact full-viewport scroll with the cursor
unchanged and at the bottom row; it sends a `delta` instead whenever the cursor
changed or an appended row carries a hyperlink (so append rows never set the OSC8
attr bit). Gap recovery for a lost append relies on ordered/reliable WS transport
+ the periodic keyframe interval — there is no per-append `prev_frame_id` chain.

## Final Implementation Notes

- **Actual work done:** Implemented Stage 3 of the applink data plane as planned.
  - `applink/content.py`: `encode_append` (0x03 = 1 raw tag byte + msgpack
    `[pane_id, frame_id, row_list]`, no cursor/prev/osc8); `detect_append`
    (pure `{row_id: sig}` prefix comparison — returns the smallest `k` for which
    the new grid equals the baseline scrolled up by `k`, else `None`);
    `PaneState.last_cursor` per-connection full-cursor baseline.
  - `applink/pusher.py`: `_push_pane` tries the append path *before* the delta
    path — gated on `detect_append` + cursor at the bottom row + the full cursor
    tuple unchanged (`st.last_cursor == cursor`) + no hyperlink in the appended
    rows; bumps `frame_id` so a later delta chains; updates `st.last_cursor` in
    the common send tail. Falls back to the existing delta/keyframe selection
    otherwise.
  - Docs: pinned the append detection / row-id / no-cursor / no-osc8 /
    frame_id-adoption / gap-recovery conventions in `content_transport.md`
    §append and `monitor_port_design.md` §Append fast-path detection (with the
    explicit "alt-screen not detected — conservative exact-shift substitute"
    note); added a t822_10 cross-repo contract note to t822_12.
  - Tests: +10 `test_applink_content.sh` checks (`encode_append` shape +
    `detect_append` scroll-by-1/2, repeated-line, mid-screen, full-replacement,
    differing-counts, None-baseline); +15 `test_applink_pusher.sh` checks (an
    independent **positional** wire-decoder: keyframe seed → append → chain →
    convergence vs a direct content parse, append frame_id monotonic, no
    cursor/prev/osc8, delta-after-append chains on the append's frame_id,
    cursor-moved-col → not append, cursor-not-at-bottom → not append, hyperlink →
    not append).
- **Deviations from plan:**
  - The hyperlink guard is `any(u for _r, _s, urls in appended for u in urls)`
    (flatten to url *strings*), not `any(urls for ...)` as first drafted — `urls`
    is a per-span list (`['']` for a non-hyperlink span), so the list-level check
    was always truthy and suppressed every append. Caught by the failing
    scroll-by-1 test before commit.
  - Step 9 said the two `aidocs/applink/*.md` edits commit "via `./ait git`", but
    `aidocs/` is a real directory on the **code** branch (not symlinked to
    `aitask-data`), so they were committed with the code via plain `git`. Only
    the t822_12 task-file pointer used `./ait git`.
- **Issues encountered:** the hyperlink-guard list-vs-string bug above; no others.
  All pre-existing applink tests stayed green.
- **Key decisions:** correctness rests on **exact full-viewport shift detection**
  (the client converges to the same grid a keyframe would produce), with the
  cursor-unchanged gate protecting the uncarried cursor and the in-order-transport
  + periodic-keyframe model covering lost-append recovery. Alt-screen is not
  detected explicitly (no snapshot signal) — a deliberate conservative substitute.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **Mobile (`aitasks_mobile`):** `append` decode = `[0x03][msgpack([pane_id,
    frame_id, row_list])]`; no cursor (keep the prior one), no `prev_frame_id`, no
    `osc8`; drop the top `len(row_list)` rows, shift up, append `row_list` at the
    bottom (rows carry their new absolute row_ids `H-k … H-1`); adopt the append's
    `frame_id` as current so the next `delta`'s `prev_frame_id` chains. Pinned in
    `content_transport.md` §append and flagged in t822_12.
  - The unrelated working-tree changes under `.aitask-scripts/brainstorm/` present
    during this task were **not** part of t822_10 and were excluded from the commit.
