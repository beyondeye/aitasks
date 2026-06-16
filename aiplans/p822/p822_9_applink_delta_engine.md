---
Task: t822_9_applink_delta_engine.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_10_applink_append_fastpath.md, aitasks/t822/t822_11_applink_modal_handshakes.md, aitasks/t822/t822_12_applink_permissions_doc_sync.md, aitasks/t822/t822_13_applink_headless_monitor_flag.md, aitasks/t822/t822_14_applink_push_scheduler_resilience.md
Archived Sibling Plans: aiplans/archived/p822/p822_6_extract_monitor_core.md, aiplans/archived/p822/p822_7_applink_websocket_listener.md, aiplans/archived/p822/p822_8_applink_snapshot_push_loop.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t822_9 — applink delta engine (data plane Stage 2)

## Context

Parent **t822** builds `ait applink`, streaming desktop tmux panes to a mobile
companion over a paired LAN WebSocket. **t822_8** shipped data-plane **Stage 1**:
per-pane `keyframe` (0x01) push + `dim` (0x05) on resize, via a per-connection
`PushScheduler`. Stage 1 sends a *full grid* on every change — fine on LAN, too
heavy for cellular/relay.

This task adds **Stage 2: delta encoding** — hash each row, collect only the rows
that changed since the client's last frame, emit `delta` (0x02) against
`prev_frame_id`. Most workloads drop to <100 B/update. The wire layout is fixed:
`[0x02, pane_id, frame_id, prev_frame_id, cursor, [changed rows…], osc8?]`
(`content_transport.md` §delta) — this task *consumes* it.

### Confirmed architectural decision: per-connection deltifier (NOT a shared cache)

The deltifier lives in **`applink/content.py`**, and per-row hash state is
**per-connection** on `Subscription.PaneState.row_sigs` — *intentionally*, not as
an accident of co-location. The design doc originally placed it in `monitor_core`
for a client-agnostic shared cache ("one diff per tick regardless of attached
clients"). That sharing **cannot work as imagined**, and per-connection is the
*correct* shape:

- A delta is computed **against the specific frame that client last received**.
  Two clients on pane `%1` generally sit at different `frame_id`s (subscribed at
  different times, one recovered via `request_keyframe`), so their diff
  *baselines differ*. The "prev" side of the diff is irreducibly per-client.
- A shared cache could only memoize the **current-capture** row hashes (the "new"
  side) — computed once per `capture_all_async` tick anyway, and shared across
  clients only saves recomputing a handful of `hash()` calls. The expensive part
  (the tmux capture) is *already* shared via `monitor_core.capture_all_async`
  (t822_8). So the shared cache buys ~nothing at the realistic ~1 client and would
  couple the shared TUI core to applink's subscription lifecycle.

Per-connection state is therefore both simpler *and* required for correct
per-client recovery. **This shape is inherited by t822_10 (append)**, whose
fast-path detection also keys off the client's last-sent rows. The doc and the
task AC are corrected to state this rationale (steps 1a/1c), not just swap a noun.

## Implementation

> **Ordering:** do the **contract pins (Step 1) first**, then code (Steps 2–3),
> then tests (Steps 4–5). Steps 4–5 encode the `delta` conventions (osc8 offset
> basis, empty-spans-clears-row) that Step 1 fixes in the spec — writing tests
> first would risk green tests against an un-pinned convention (finding #7).

### Step 1 — Pin the wire contract and sync docs (do first)

**1a. `aidocs/applink/content_transport.md` §delta — pin two conventions** the
mobile decoder must match (today's spec leaves both implicit):
- The optional `osc8` sidecar's flat span-offsets are **row-major over the
  delta's own `rows` array** (changed rows only), exactly as keyframe `osc8` is
  row-major over its rows.
- **A row whose spans array is empty (`[row_id, []]`) clears that row** to blank.
  (Plain "unlisted rows retain prior content" can't express content→blank within
  fixed dims; this is the convergence guard — see Step 3.)

**1b. `aidocs/applink/monitor_port_design.md` §Deltification responsibility +
§Append fast-path** — rewrite the "runs in `monitor_core` … row-hash cache exists
once per pane regardless of clients" claim to the implemented reality **with the
rationale from the Context section**: deltifier in `applink/content.py`; per-row
hash state per-connection on `Subscription.PaneState`; the capture pipeline is the
shared resource (`capture_all_async`), and a shared row-hash cache is unnecessary
because the diff baseline is per-client. Give §Append fast-path the same
`content.py` pointer so t822_10 inherits it.

**1c. `aitasks/t822/t822_9_applink_delta_engine.md` — AC correction** (no silent
deviation): change "Key Files to Modify" / "Implementation Plan" to name
`applink/content.py` as the deltifier home, with the one-line per-connection
rationale. Commit via `./ait git`.

**1d. Cross-repo coordination (flag, don't assume):** the osc8-offset-basis and
empty-row-clear conventions are **new contract** for the mobile decoder in
`../aitasks_mobile`. The server is authoritative (design goal 5), but mobile may
have begun parsing osc8 under a different assumption. Record the mobile decoder
contract in this plan's **Final Notes "Mobile note"** (the channel t822_8
established) AND add a one-line pointer in **t822_12** (applink_permissions_doc_sync,
the mobile-facing sibling) via `./ait git` so the contract is tracked cross-repo,
not discovered at integration. This is the residual goal-achievement risk made
explicit, not eliminated.

### Step 2 — `applink/content.py`: encoder + deltifier (pure, unit-testable)

**`encode_delta`** (next to `encode_keyframe`, lazy msgpack via `_packb`; tag
`FRAME_DELTA = 0x02` already defined):
```python
def encode_delta(pane_id, frame_id, prev_frame_id, cursor, row_list, osc8=None) -> bytes:
    arr = [pane_id, frame_id, prev_frame_id, cursor, row_list]
    if osc8:
        arr.append(osc8)
    return bytes([FRAME_DELTA]) + _packb(arr)
```

**Parser refactor** so delta osc8 can be built over a row *subset* (today's
`snapshot_to_rows` discards per-span urls):
```python
def parse_snapshot(content):
    """-> list of (row_id, spans, urls). Same line-split / trailing-blank-drop as today."""
    out = []
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    for row_id, line in enumerate(lines):
        spans, urls = parse_sgr_line(line)
        out.append((row_id, spans, urls))
    return out

def build_osc8(parsed):
    """Flat row-major span-offset -> url over the given (row_id, spans, urls) list."""
    osc8, idx = {}, 0
    for _rid, spans, urls in parsed:
        for u in urls:
            if u:
                osc8[idx] = u
            idx += 1
    return osc8

def row_signature(spans):
    """In-process-stable hash of one row's spans (change detection)."""
    return hash(tuple((s[0], s[1], s[2], s[3], s[4]) for s in spans))

def snapshot_to_rows(content):                 # unchanged PUBLIC behavior
    parsed = parse_snapshot(content)
    return [[rid, spans] for rid, spans, _u in parsed], build_osc8(parsed)
```
`build_osc8(parse_snapshot(c))` reproduces today's global offsets byte-for-byte,
preserving keyframe behavior + the existing osc8 test. Sole `snapshot_to_rows`
consumer is `pusher.py:133` (rewritten) plus one test; a regression test guards
the refactor (Step 4).

**The diff** — with an explicit `None`-baseline guard (finding #8):
```python
def deltify(prev_sigs, parsed):
    """Collect rows that changed vs the client's last-sent baseline.
    Returns (changed_wire, removed_ids, new_sigs, changed_subset).
    REQUIRES a prior keyframe baseline — prev_sigs must not be None (the caller
    routes the first frame / forced frame through the keyframe path)."""
    assert prev_sigs is not None, "deltify requires a prior keyframe baseline"
    new_sigs, changed_subset = {}, []
    for rid, spans, urls in parsed:
        sig = row_signature(spans)
        new_sigs[rid] = sig
        if prev_sigs.get(rid) != sig:
            changed_subset.append((rid, spans, urls))
    removed = [rid for rid in prev_sigs if rid not in new_sigs]   # client holds it, gone now
    changed_wire = [[rid, spans] for rid, spans, _u in changed_subset]
    return changed_wire, removed, new_sigs, changed_subset
```
**`removed` → `[row_id, []]` is the convergence guard:** delta semantics retain
unlisted rows, so a row the client holds that is now absent (content shrank within
fixed dims, dropping a trailing line) must be explicitly cleared, or the client
diverges from a fresh keyframe.

**Per-pane state** — add one field to `PaneState`:
```python
row_sigs: Optional[dict] = None   # {row_id: sig} the client currently holds; None => must keyframe
```
`None` (a fresh `PaneState`) forces a keyframe. **Recovery correctness (finding
#4):** `Subscription.apply_subscribe` already does `self.force |= set(self.panes)`
(content.py:346), so **every (re)subscribe force-seeds a keyframe** for each pane →
the keyframe path resets `row_sigs`. A *reconnecting* client gets a brand-new
`ConnState`/`Subscription` (empty `_pane`) → `row_sigs is None` → keyframe. So a
client never receives a delta against a baseline it lacks; the guarantee is the
force-seed, not the stale-state drop.

### Step 3 — `applink/pusher.py`: keyframe-vs-delta selection

Rewrite **only** the keyframe-emit tail of `_push_pane` (current lines 125–142).
The `pane_status`, `dim`-on-resize, and the
`(changed or forced or interval_due) and (due or forced)` gate above stay as-is.

```python
cursor = await self._monitor.capture_cursor_async(pane_id)
cursor = list(cursor) if cursor is not None else [0, 0, False, 0]
parsed = content.parse_snapshot(snap.content)
new_sigs = {rid: content.row_signature(spans) for rid, spans, _u in parsed}

emit_keyframe = forced or interval_due or st.row_sigs is None
sent_keyframe = False
if not emit_keyframe:
    changed_wire, removed, _ns, changed_subset = content.deltify(st.row_sigs, parsed)
    if not changed_wire and not removed:
        st.last_hash = content_hash      # whole-pane hash moved but no visible row
        return                           # changed (e.g. a trailing blank) -> send nothing
    # Cost proxy (finding #5): a delta covering >= every row is never smaller than a
    # keyframe, so fall back without a second full encode. Bounded by pane width, so
    # row-count is a sound proxy for "delta cost >= keyframe cost". SINGLE encode/tick.
    # Known trade-off: this errs CONSERVATIVELY — on a dense terminal where many short
    # rows change it may pick a keyframe even though a delta would have been smaller in
    # bytes. Never incorrect (only more keyframes), and the documented escape hatch if
    # keyframe frequency ever bites is a byte-accurate compare (encode both, send smaller).
    if len(changed_wire) + len(removed) >= len(parsed):
        emit_keyframe = True
    else:
        delta_wire = changed_wire + [[rid, []] for rid in removed]
        prev_frame_id = st.frame_id
        frame_id = sub.next_frame_id(pane_id)               # = prev_frame_id + 1
        await self._send(content.encode_delta(
            pane_id, frame_id, prev_frame_id, cursor, delta_wire,
            content.build_osc8(changed_subset) or None))

if emit_keyframe:
    full_rows = [[rid, spans] for rid, spans, _u in parsed]
    frame_id = sub.next_frame_id(pane_id)
    await self._send(content.encode_keyframe(
        pane_id, frame_id, dims[0], dims[1], cursor, full_rows,
        content.build_osc8(parsed) or None))
    sent_keyframe = True

st.row_sigs = new_sigs
st.last_hash = content_hash
st.last_dims = dims
if sent_keyframe:
    st.last_keyframe_t = now             # any keyframe (forced/interval/cost-fallback) resets drift
st.last_send_t = now
sub.force.discard(pane_id)
```
- **Chain:** every data frame bumps `frame_id` via `next_frame_id`; a delta's
  `prev_frame_id` is the previously-sent `frame_id`. Linear chain per spec.
- **`request_keyframe` recovery:** `force` → `emit_keyframe` → fresh keyframe + full
  `row_sigs` reset within one tick. Only recovery path (no replay buffer).
- **Resize:** the existing `dim_changed` branch already sets `forced=True` →
  keyframe path rebuilds `row_sigs`, so resize invalidates stale hashes for free.
- **Single encode per tick** in all cases (count proxy, not double-encode).

### Step 4 — `tests/test_applink_content.sh` (extend, pure)

Reuse the skip-if-no-msgpack harness. Add: `encode_delta` (leading `0x02`;
`unpackb(rest)` == `[pane_id, frame_id, prev_frame_id, cursor, rows]` + osc8 only
with hyperlinks); `parse_snapshot` shape; **`snapshot_to_rows` output unchanged**
(refactor regression guard); `deltify` (1-of-N changed → 1 row, empty removed;
unchanged → both empty; dropped trailing line → its id in `removed`; `None`
baseline → AssertionError); `build_osc8` over a 2-row subset → subset-relative
offsets; `row_signature` equal/!= by field.

### Step 5 — `tests/test_applink_pusher.sh` (extend, async) — INDEPENDENT convergence

Reuse `FakeWS`/`FakeMonitor`/`FakePane`/`FakeSnap` + injected clock. **The
convergence check must not compare two pusher-produced artifacts** (finding #2) —
a systematic bug would corrupt both sides identically. Instead, decode the **actual
wire bytes** with an independent in-test client applier and compare to a direct
parse of the pane content:

```python
client = {}                                  # row_id -> spans, built ONLY from wire bytes
def apply(frame: bytes):
    tag, body = frame[0], msgpack.unpackb(frame[1:], raw=False, strict_map_key=False)
    if tag == C.FRAME_KEYFRAME:              # [pane,fid,cols,rows,cursor,rowlist,osc8?]
        client.clear()
        for rid, spans in body[5]:
            if spans: client[rid] = spans
    elif tag == C.FRAME_DELTA:              # [pane,fid,prev,cursor,rowlist,osc8?]
        for rid, spans in body[4]:
            client[rid] = spans if spans else None
        client_clean = {k: v for k, v in client.items() if v}   # drop cleared rows
        client.clear(); client.update(client_clean)

def truth(content):                          # independent ground truth: a direct full parse
    return {rid: spans for rid, spans in C.snapshot_to_rows(content)[0] if spans}
```

Cases:
- **delta after keyframe:** force pass (keyframe@f1); change 1 line; advance past
  cadence; `_run_once` → a `0x02` frame; assert `prev_frame_id == f1` and only the
  changed row present.
- **convergence (headline):** apply the captured keyframe + delta(s) via `apply()`;
  assert `client == truth(snap.content)` — ground truth is the *direct parse of the
  current content*, NOT a fresh keyframe, breaking the self-referential loop.
- **explicit chain assertion:** across a keyframe→delta→delta sequence, each delta's
  `prev_frame_id` equals the prior frame's `frame_id` (a row_id-keyed apply ignores
  ordering/frame_id, so assert the chain directly).
- **single-row change is small:** `len(delta_frame) < ` a forced-keyframe frame.
- **recovery:** after deltas, `request_keyframe` → next pass is `0x01`; `apply()` of
  the recovery keyframe alone still equals `truth`.
- **cost fallback:** change every row → a `0x01` keyframe is emitted (not a delta).
- **removed row → blank:** shrink `snap.content` by a non-blank line at fixed dims →
  delta carries `[row_id, []]`; `client` after `apply()` still equals `truth`.

## Risk

### Code-health risk: medium
- Rewrites `_push_pane`'s emit tail (load-bearing in t822_8); a delta bug causes
  **silent client divergence**. · severity: medium · → mitigation: pure diff in
  `content.py`; an **independent-decoder convergence test** (wire bytes →
  reconstructed buffer vs a direct content parse, finding #2) + explicit chain
  assertion; blast radius confined to the applink package; behavior-preserving
  `snapshot_to_rows` refactor with a regression test.
- `row_sigs` drift if invalidation is missed. · severity: low · → mitigation:
  resize forces a keyframe; every (re)subscribe force-seeds a keyframe
  (content.py:346); reconnect gets a fresh `Subscription`; `None` sigs force a
  keyframe; `deltify` asserts a non-None baseline.

### Goal-achievement risk: medium
- **No real mobile client** (cross-repo, unavailable): convergence/recovery exercised
  only against synthetic wire decoding; schema drift possible. · severity: medium ·
  → mitigation: strict `content_transport.md` adherence; the delta osc8 basis +
  empty-row-clear conventions are **pinned in the spec** (Step 1a) and **flagged to
  the mobile sibling t822_12** (Step 1d), not left to inference; live-path
  verification via the Step 8c manual-verification follow-up.
- Delta-frame resource limits (size cap, decode-bomb). · severity: low · →
  mitigation: owned by **t1007** (created by t822_8) with t985.

_No `### Planned mitigations` — confirmed "No mitigations" (live verification via
Step 8c; resource limits via t1007; spec ambiguity resolved in-plan + flagged to
t822_12)._

## Verification

1. `bash tests/test_applink_content.sh` → PASS (encode_delta, parse_snapshot,
   deltify incl. None-guard, build_osc8, row_signature; existing cases green).
2. `bash tests/test_applink_pusher.sh` → PASS (independent-decoder convergence,
   chain, delta-after-keyframe, single-row-small, recovery, cost-fallback,
   removed-row-blank; existing emit/idle/resize/teardown green).
3. `bash tests/test_applink_router.sh && bash tests/test_applink_smoke.sh && bash
   tests/test_applink_devices.sh` → PASS (no regressions).
4. `python -c "import applink.content, applink.pusher"` (venv) → clean; msgpack lazy.
5. **Live (manual — real mobile client unavailable):** `./ait applink`, scripted
   `python websockets` client, `subscribe` → keyframe; type one line → a `delta`
   well under the keyframe size; drop a delta + `request_keyframe` → fresh keyframe
   within one tick. → Step 8c manual-verification follow-up.

## Step 9 (Post-Implementation)

Profile `fast`, current branch (no worktree). Code (`content.py`, `pusher.py`,
tests) via `git`; task AC + plan + the two `aidocs/applink/*.md` edits + the
t822_12 pointer via `./ait git`. Push via `./ait git push`. Archive via
`./.aitask-scripts/aitask_archive.sh 822_9` — parent t822 keeps t822_10..t822_14
pending. **Final Notes / Mobile note:** `delta` =
`[0x02, pane_id, frame_id, prev_frame_id, cursor, [rows], osc8?]`; unlisted rows
retain prior content; `[row_id, []]` clears a row; `osc8` offsets are row-major
over the delta's own rows array; on `prev_frame_id` mismatch send `request_keyframe`.
**Sibling note (t822_10 append):** extends the same `_push_pane` selection branch —
`append` (0x03) slots in *before* the delta path on bottom-growth detection; the
per-connection `row_sigs` / `changed_subset` / `removed` machinery is reusable.

## Final Implementation Notes

- **Actual work done:** Implemented Stage 2 of the applink data plane as planned, in
  the confirmed per-connection `content.py` shape.
  - `applink/content.py`: `encode_delta` (0x02 = 1 raw type byte + msgpack
    `[pane_id, frame_id, prev_frame_id, cursor, row_list, osc8?]`); parser split
    into `parse_snapshot` (retains per-span urls), `build_osc8` (row-major offsets
    over *any* row list — full grid or a delta subset), `row_signature`
    (in-process-stable per-row hash); `deltify` (changed-row collection + `removed`
    ids, with an `assert prev_sigs is not None` baseline guard); `snapshot_to_rows`
    kept byte-for-byte identical (thin wrapper); `PaneState.row_sigs` per-connection
    baseline.
  - `applink/pusher.py`: `_push_pane` selects delta-vs-keyframe — keyframe on
    first/forced/keyframe-interval, else a delta; `prev_frame_id = st.frame_id`
    before the bump (linear chain); a single-encode **row-count cost proxy**
    (`changed + removed >= total_rows → keyframe`) avoids a double encode per tick;
    `removed` rows emitted as `[row_id, []]`; `request_keyframe` recovery + resize
    both route through the keyframe path, resetting `row_sigs`.
  - Docs: pinned the delta `osc8` offset basis (subset-relative) + the
    empty-spans-clears-row convention in `content_transport.md` §delta; corrected
    `monitor_port_design.md` §Deltification + §Append to the per-connection
    `content.py` placement *with rationale*; corrected the t822_9 AC and added a
    cross-repo contract note to t822_12.
- **Deviations from plan:** None of substance. Original task wording named
  `monitor_core` / a "single shared hash cache"; the confirmed decision (and AC
  correction) is per-connection state in `content.py` (the diff baseline is
  irreducibly per-client). Cost comparison is a row-count proxy, not a byte-accurate
  double encode — deliberate and conservative (never a delta when a keyframe is
  smaller; may over-keyframe on dense terminals; documented escape hatch is a
  byte-accurate compare).
- **Issues encountered:** None. Existing tests passed unchanged after the
  `snapshot_to_rows` refactor (regression-guarded); `msgpack` stays lazily imported.
- **Key decisions:** Per-connection deltifier in `content.py`; the convergence test
  reconstructs the client buffer **from decoded wire bytes** and compares to a
  *direct parse of the content* (not a second pusher-produced keyframe), so a
  systematic encode/threading/order bug cannot pass by corrupting both sides
  identically; standalone `cursor` (0x04) frames remain folded into
  keyframes/deltas (carried-forward t822_8 limitation).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t822_10 (append):** emit `append` (0x03) *before* the delta path when the
    change is pure bottom-growth (cursor at bottom before+after, no upper rows
    changed, no alt-screen). The per-connection `PaneState.row_sigs` baseline plus
    `deltify`'s `changed_subset` / `removed` are reusable for the bottom-growth test;
    `FRAME_APPEND = 0x03` is reserved in `content.py`; `append` carries no
    `prev_frame_id`.
  - **Mobile (`aitasks_mobile`):** `delta` decode =
    `[0x02][msgpack([pane_id, frame_id, prev_frame_id, cursor, rows, osc8?])]`;
    unlisted rows retain prior content; `[row_id, []]` clears a row; `osc8` offsets
    are row-major over the delta's **own** rows array (allow int map keys); on
    `prev_frame_id` mismatch send `request_keyframe`. Both conventions are now pinned
    in `content_transport.md` §delta and flagged in t822_12.
