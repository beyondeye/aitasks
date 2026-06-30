---
Task: t1045_applink_efficient_roster_focused_content.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1045 — Applink: roster status for all panes, binary content only for focused/subscribed

## Context

After t1044, an empty/absent `subscribe.panes` expands to **all** discovered panes
(`router._discover_pane_ids`), and the push scheduler streams full binary content
(keyframe + deltas/appends) for **every** subscribed pane. That is correct but wasteful
on cellular: the user is only *viewing* one pane's live content at a time. The roster
(badges / idle / awaiting-input) needs every pane, but the heavy binary frames only need
the focused/explicitly-chosen pane(s).

This task implements the **server side** of a refined, bandwidth-frugal contract that
`content_transport.md:174` already names as a "planned follow-up requiring coordinated
server + mobile changes":

- Push `pane_status` (the JSON roster heartbeat) for **all** discovered panes.
- Stream **binary content** only for the panes the client marks as *content* panes
  (the focused or explicitly-subscribed one(s)).

The mobile-side adoption is the separately-tracked, reverse-dependent task
**aitasks_mobile#19** — the server contract lands first, then the client adopts it. The
wire change must be **additive/versioned** (`protocol.md §Versioning`) so older clients
keep working unchanged.

## Design — the server contract

Split the `Subscription`'s single pane set into two derived roles:

- **status pane set** = `Subscription.panes` (unchanged meaning; empty/absent ⇒ all
  discovered). Drives `pane_status` for the whole roster.
- **content pane set** ⊆ status set. Drives the binary frames (keyframe/delta/append/dim).

Selection of the content set, additive and backward-compatible:

- **New optional `subscribe.content_panes` field** (list of `%N` ids):
  - **Absent** ⇒ *legacy* behavior: every status pane is also a content pane
    (`content_all = True`). Older clients that never send the field are byte-for-byte
    unchanged.
  - **Present** (list, possibly empty) ⇒ only the listed panes stream content; the rest
    are status-only. `[]` means "no content panes yet — I'll pick one via `focus`."
- **`focus` verb** additionally promotes the focused pane into the content set (the pane
  the user is viewing always streams). This is the convenience path for `monitor_control`+
  clients. **Read-only clients cannot reach `focus`** (it is gated `monitor_control`+ in
  `router.py`), so for them the explicit `content_panes` field is the *required* path —
  re-subscribe with the new content pane when the user switches. The plan supports both.

Effective content predicate (single source of truth, on the model):
`streams_content(pane) = pane ∈ panes AND (content_all OR pane ∈ content_panes OR pane == focused_pane)`.

**Blast-radius / "edited-unaware" safety:** the split is fully encapsulated behind one
model method (`streams_content`); `pusher._push_pane` calls it instead of open-coding the
rule. The default (`content_all = True`) means any caller/profile that does not opt in
behaves exactly as today. `MAX_SUBSCRIBED_PANES` still bounds `panes`; `content_panes` is
intersected with `panes`, so it can only shrink the streamed set.

## Implementation

### 1. `content.py` — `Subscription` model

- Add fields in `__init__`: `self.content_all: bool = True`, `self.content_panes: set[str] = set()`.
- `apply_subscribe(payload)` — after the existing `panes` resolution + `MAX_SUBSCRIBED_PANES`
  cap, parse the new field:
  ```python
  cp = payload.get("content_panes")
  if cp is None:
      self.content_all = True
      self.content_panes = set()
  else:
      self.content_all = False
      self.content_panes = (
          {p for p in cp if isinstance(p, str) and p} & self.panes
          if isinstance(cp, list) else set()
      )
  ```
  Keep `self.force |= set(self.panes)` as-is — it seeds a first-tick `pane_status` for the
  whole roster (status-only panes discard their force seed in the pusher after that first
  status send; see step 2). Re-subscribing rebuilds `content_panes` from scratch each call
  (idempotent), so a narrowed re-subscribe correctly drops panes from the content set.
- Add the predicate:
  ```python
  def streams_content(self, pane_id: str) -> bool:
      if pane_id not in self.panes:
          return False
      return (self.content_all
              or pane_id in self.content_panes
              or pane_id == self.focused_pane)
  ```
- `set_focus(pane_id)` — when the split is active and this pane is not already a content
  pane, force an immediate keyframe so it starts streaming at once:
  ```python
  def set_focus(self, pane_id: str) -> None:
      if (pane_id in self.panes and not self.content_all
              and pane_id not in self.content_panes):
          self.force.add(pane_id)
      self.focused_pane = pane_id
  ```
  (In legacy `content_all` mode this adds no force — the pane already streams — so existing
  behavior is unchanged.)

### 2. `pusher.py` — `_push_pane` content gate

Currently `_push_pane` (a) sends a `pane_status` heartbeat, then (b) emits binary frames.
Gate (b) on the content predicate. After the existing `pane_status` block
(`if forced or (now - st.last_status_t) >= idle_s: ... st.last_status_t = now`), insert:

```python
# Roster-vs-content split (t1045): a status-only pane gets the pane_status
# heartbeat above but NO binary frames. Clear its force seed and return before
# the per-pane cursor capture / parse / binary encode below.
if not sub.streams_content(pane_id):
    sub.force.discard(pane_id)
    return
```

Everything below (dim-on-resize, `content_hash`, keyframe/delta/append, the oversize
re-anchor, `st`/`force` bookkeeping) stays exactly as-is and now runs only for content
panes — so a status-only pane costs **zero** per-pane `capture_cursor_async` calls and zero
binary bytes (the roster snapshot from `_run_once`'s single shared `capture_all_async()`
is taken regardless, for everyone's `pane_status`). The forced first-tick `pane_status`
still fires for every roster pane because `forced` is read above the gate.

### 3. `router.py` — `subscribe` and `request_keyframe` handlers

**`subscribe`:**

- Validate **and bound** the new field, mirroring the existing `panes` checks (a non-list
  `panes` is `BAD_PAYLOAD`, and `len(panes) > _MAX_PANES` is rejected). `content_panes` gets
  the *same* treatment so a hostile/malformed payload cannot force router/model iteration
  over a huge array before the intersection shrinks it. Right after the `panes` non-list
  check:
  ```python
  cp = payload.get("content_panes")
  if cp is not None and (not isinstance(cp, list) or len(cp) > _MAX_PANES):
      return self._bad_field(msg_id, verb, "content_panes")
  ```
  Per-entry `%N` regex is unnecessary in the router: the model intersects entries with the
  already-validated `panes` (no shell sink — `content_panes` never reaches a command line),
  and the length is now bounded here. `content_panes` flows to `apply_subscribe` via the
  copied `payload`.
- Echo the accepted content set in the `res` so the client can confirm acceptance, only
  when the split is active (keeps the legacy `res` unchanged):
  ```python
  reply = {"ok": True, "panes": sorted(accepted)}
  if not conn.subscription.content_all:
      reply["content_panes"] = sorted(conn.subscription.content_panes)
  return self._res(msg_id, verb, reply)
  ```

**`request_keyframe` (contract decision):** today the handler adds *any* pane to `force`
unconditionally (it does not even require the pane to be subscribed). Under the split that
becomes a **silent no-op** for a status-only pane — force is seeded, then the pusher sends
`pane_status`, discards force at the content gate, and never sends a keyframe. Rather than
leave that silent, **reject `request_keyframe` for panes that are not effective content
panes**, mirroring the existing `history` precedent (which rejects panes outside the
active subscription with `reason: not_subscribed`). A keyframe is a content-recovery frame;
it only means something for a pane the client is streaming.
  ```python
  if conn.subscription is None or not conn.subscription.streams_content(pane_id):
      return self._err(msg_id, verb, ERR_BAD_PAYLOAD,
                       f"pane '{pane_id}' is not a content pane",
                       detail={"reason": "not_content_pane"})
  conn.subscription.request_keyframe(pane_id)
  ```
  This also tightens the prior lenient behavior for *unsubscribed* panes (previously a
  benign no-op that left a phantom id in `force`) — both cases now get one coherent rule:
  you can only request a keyframe for a pane you are actually streaming. The flow for a
  roster client is `subscribe(content_panes=[])` → `focus(%n)` (or re-subscribe with the
  pane in `content_panes`) → `request_keyframe(%n)`.

### 4. Docs

- **`content_transport.md` §subscribe** — add `content_panes` to the payload example and a
  bullet defining it (absent ⇒ legacy all-content; present ⇒ status-only for the rest).
  Replace the "Bandwidth note (planned follow-up)" paragraph (line 174) with the
  now-implemented contract: `pane_status` for the whole roster, binary content only for
  the content set; note `focus` promotes a pane to content and that read-only clients use
  `content_panes` (focus is `monitor_control`+). Update the "Server responds … a keyframe
  per subscribed pane" line to "a keyframe per *content* pane; `pane_status` for the whole
  roster." Note additivity per §Versioning.
- **`content_transport.md` §request_keyframe / recovery** — document that
  `request_keyframe` is valid only for an **effective content pane** (focused or in
  `content_panes`, or any pane in legacy all-content mode) and returns `BAD_PAYLOAD`
  `reason: not_content_pane` otherwise — same shape as `history`'s `not_subscribed`.
- **`protocol.md` §Subscription** (line ~160) — note the status-vs-content split, the
  optional `content_panes` field, that `focus` selects the content pane, and that
  `request_keyframe` applies to content panes only.

### 5. Tests

- **`tests/test_applink_pusher.sh`** — new cases against the existing fakes. Add a
  `cursor_calls` list to `FakeMonitor.capture_cursor_async` (append `pane_id`) so the
  "no work for status-only panes" claim is asserted directly, not just by frame count:
  - roster subscribe with `content_panes: []` over two panes ⇒ both emit `pane_status`,
    **zero** binary frames; **no** `capture_cursor_async` call for either pane; and each
    pane's `PaneState` is untouched (`sub.state_for(p).frame_id == 0`, `row_sigs is None`,
    `last_hash is None`). This proves the gate returns *before* capture/encode, not that it
    merely discards the result.
  - then `set_focus(%1)` ⇒ `%1` emits a keyframe (and now appears in `cursor_calls`), `%2`
    stays status-only (still no cursor call, state still pristine).
  - `content_panes: ["%2"]` ⇒ `%2` streams, `%1` is status-only (pane_status only, no
    cursor call, pristine state).
  - regression: no `content_panes` ⇒ both panes stream (legacy path intact — explicit
    two-pane assertion).
- **`tests/test_applink_router.sh`** — subscribe with `content_panes` splits the set and
  the `res` echoes `content_panes`; a non-list `content_panes` ⇒ `BAD_PAYLOAD`; an
  over-long `content_panes` (> `_MAX_PANES`) ⇒ `BAD_PAYLOAD`; an entry not in the roster is
  dropped. `request_keyframe` for a content pane ⇒ ok + in `force`; for a status-only or
  unsubscribed pane ⇒ `BAD_PAYLOAD` `reason: not_content_pane` (update the existing
  line-336 `%3` case, which currently relies on the dropped lenient behavior, to use a
  content pane for the ok assertion and add the rejection case).
- **`tests/test_applink_content.sh`** — unit-level: `apply_subscribe` sets
  `content_all`/`content_panes`; `streams_content` truth table (status-only vs content vs
  focused); `set_focus` adds to `force` in split mode but not in legacy mode.

Run: `bash tests/test_applink_content.sh && bash tests/test_applink_pusher.sh && bash tests/test_applink_router.sh`,
plus `shellcheck` is N/A (Python edits); the pusher/content tests SKIP cleanly if `msgpack`
is absent.

## Out of scope

- **Mobile client** (`aitasks_mobile#19`) — sending/honoring `content_panes` + driving the
  content pane on focus. Reverse cross-repo dependency already recorded on that task.
- **History (`history` verb)** stays keyed on roster membership (`pane_id in panes`) — a
  scrollback pull is an explicit client action; not narrowing it to the content set keeps
  blast radius minimal. Noted, not changed.

## Risk

### Code-health risk: medium
- The change touches the load-bearing per-connection push loop (`pusher._push_pane`). · severity: medium · → mitigation: in-task tests (regression + new split cases) — covered, no separate task.
- Force-set / first-keyframe interaction is the subtle part: status-only panes must discard their force seed, and a newly-focused pane must force a keyframe. · severity: medium · → mitigation: dedicated pusher tests for both transitions — covered in-task.
- `request_keyframe` is tightened from lenient (any pane) to content-panes-only, a small behavior change beyond the core split; the only client is the coordinated mobile app. · severity: low · → mitigation: documented contract + router tests; client adopts via aitasks_mobile#19.

### Goal-achievement risk: low
- The deliverable's full value depends on the paired mobile change, which is out of this task's scope. · severity: low · → mitigation: already tracked as aitasks_mobile#19 (reverse dependency recorded) — no new task.
- The chosen contract shape (additive `content_panes` field + `focus` promotion) could differ from what the mobile side prefers. · severity: low · → mitigation: contract is additive/versioned and read-only-safe; mobile adopts against this documented contract — no before-task needed.

The identified risks are all mitigated within this task (tests) or by the already-tracked
paired mobile task; no standalone before/after mitigation tasks are warranted.

## Post-implementation
Follow the shared workflow Step 8 (review) → Step 9 (no branch to merge — current-branch
profile; run the `risk_evaluated` gate at archival). Commit code with
`performance: ... (t1045)`; commit docs/tests appropriately.
