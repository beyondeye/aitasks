---
Task: t2337_frozen_agent_sitrep_harvest_triage_badge.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2337 — Show a frozen agent's sitrep state (harvested / triaged)

## Context

A frozen row in `ait monitor` / `ait minimonitor` shows only `<mark>F … frozen`.
The user cannot tell whether the agent can be dropped without pressing `h`.
Drop safety is decided by the harvest receipt `<capture.txt>.harvested`
(`agent_sessions.capture_harvested`: current-capture `sha256=` + `cert=2`).
Triage state is a second, advisory signal.

**Design decision (user-confirmed):** the link from a frozen record to its
triage and review items is **recorded in the receipt by the harvest itself**,
not derived from a store scan. The task's proposed `record=` passage-key scan
misses the common case. The workflow-end pipe (`workflow-end.md`) creates the
triage item with no passage key. The later record harvest then matches it by
run/complete key (`Harvest.wrapup`, `matched` branch) and retains no passage key
for the record. The harvest already knows the triage ids (`wrapup`) and the
review id (`record_case`) when it writes the receipt, so it records them there.
This covers every match path. The sitrep TUI part (task scope 3) is deferred to
a follow-up task.

**Review corrections folded in (user, plan review):**

1. **Legacy receipts keep their fast path.** `receipt_valid` stays
   certification-only, so `drop_record`'s pre-kill harvest
   (`agent_freeze.py:1701`, non-`--force` `record <id>`) still short-circuits on
   a certified legacy receipt and never needs the writer lock. Links are
   backfilled **only** by the maintenance `all` pass (best-effort, new
   `--backfill-links`).
2. **One receipt snapshot, verified on every path.** Safety and links are
   derived from **one** read of the capture and one read of the receipt,
   through a certification rule shared with `capture_harvested`. **Every**
   verdict is published only after a post-read check that the versions of
   every consumed input still equal the versions the verdict was derived from.
   The inputs are the record, the capture, the receipt and todo.md. This
   covers the fresh read, the cache hit and the empty-capture path alike, so a
   concurrent restore or re-freeze never publishes, or caches, a positive
   verdict. `agent_freeze._write_private` rewrites `capture.txt` in place
   (`O_TRUNC`, same inode). An empty capture is therefore positive only for a
   settled frozen record (state `frozen`, no operation lease) whose versions
   held across the read. The badge is advisory; the destructive Drop guard
   stays its own separate check.
3. **Honest triage wording.** `triaged` means every linked triage question is
   `done`. A dismissed triage question, or a closed parser-review item with no
   triage question, reads as the neutral `closed`.

## Implementation

### Pre-phase (risk mitigations)

1. [pin_receipt_gate_compat] Before touching any receipt code, add
   characterization tests and run them green against the **current** code:
   - `tests/test_frozen_sitrep.py` (new): `agent_sessions.capture_harvested` →
     True for the legacy base receipt (`sha256= / store= / cert=2`), True for
     that receipt plus trailing `links=1` / `triage=c3` / `review=c4` lines,
     False for a sha mismatch, False with no `cert=` line, False with no
     receipt.
   - `tests/test_sitrep_harvest.sh`, new section: **the real Drop command with
     a certified legacy receipt while the writer lock is unavailable.** A
     record is harvested, then its receipt is rewritten to the legacy base
     lines. `aitask_frozen.sh drop <id>` (or the `agent_freeze` drop CLI the
     existing sections use) runs under `AITASK_SITREP_LOCK_TIMEOUT=1` while the
     lock is held (the section-11 seam). The test asserts the Drop CLI's own
     success line, `DROPPED:<id>`; Drop captures the harvest output internally,
     so the CLI contract is not extended. A control asserts that a
     **non**-certified (cert-less) receipt under the same held lock is refused
     (`DROP_REFUSED:<id>|harvest:…`). The `already_harvested` short-circuit is
     asserted separately, by a direct `record <id>` harvest call against the
     legacy receipt (Verification).

   Both must still pass after steps 1–6.

### 1. Receipt records the links — `.aitask-scripts/lib/sitrep_harvest.py` + wrapper

- Add `RECEIPT_LINKS = 1` beside `HARVEST_CERT` (mirrored as
  `agent_sessions.HARVEST_RECEIPT_LINKS`, equality tested like suffix and cert).
- `Harvest.__init__`: `self.triage_ids = []`. In `wrapup()`, after `triage` is
  resolved (both the `matched` and the new-item branch), append it once
  (dedupe, keep order).
- `receipt_text(data, store_dir, triage=(), review=())`: the unchanged base lines
  first (`sha256= / store= / cert=2`), then `links=1`, then one `triage=c<N>`
  per id and one `review=c<N>` line when present. `write_receipt` gains the two
  keyword arguments.
- `receipt_valid(path, data, store_dir)`: **certification only.** It returns
  True when the receipt's first three lines equal the base lines, whatever
  follows. This keeps today's behaviour for legacy receipts, so `record <id>`
  without `--force` (the Drop path, and `h`'s callers that do not force)
  short-circuits with `already_harvested` and takes no lock.
- New `receipt_linked(path, data, store_dir)`: valid, and a
  `links=<RECEIPT_LINKS>` line is present.
- `cmd_plan` record source with the new `--backfill-links` flag: when
  `receipt_valid` holds but `receipt_linked` does not, the record proceeds to
  apply (`WORK:`) instead of short-circuiting. Without the flag the short-circuit
  is unchanged. Re-harvest is a store no-op (every key already matches) and
  rewrites the receipt with links.
- `cmd_apply` (record source): pass `h.triage_ids` and the `record_case` review
  number to `write_receipt`. The `sitrep_agent` / `nothing_found` early
  receipts get `links=1` with no ids.
- `aitask_sitrep_harvest.sh`: `cmd_record` accepts `--backfill-links` and
  forwards it to both phases (the parser gets the flag on the `record`
  subparser). `cmd_all` passes `--backfill-links` to every `RECORD:`. A backfill
  failure prints its `HARVEST_FAILED` line and makes `all` exit 1, as any
  failed record does today. The monitor's maintenance tick already swallows
  that. `h` (`--force`) and Drop never pass the flag. Update the header and the
  module docstring (receipt lines, backfill).

### 2. Shared certification rule — `.aitask-scripts/lib/agent_sessions.py`

- Extract `receipt_certifies(receipt_lines: list[str], data: bytes) -> bool`
  (the `sha256=<current>` + `cert=HARVEST_RECEIPT_CERT` membership check), and
  `capture_harvested` calls it. Behaviour is unchanged; the pre-phase tests pin
  it. `frozen_sitrep` uses the same function, so the two can never disagree.

### 3. Derivation helper — new `.aitask-scripts/lib/frozen_sitrep.py`

Stdlib only; imports `agent_sessions` and `sitrep_todo`, with no
monitor/Textual import. It reports evidence and does not decide for the user.

- States: `unharvested`, `nothing`, `triage_open`, `triaged`, `closed`,
  `review_pending`, `unlinked` (certified legacy receipt with no `links=`), and
  `unknown`. `SAFE_STATES` is every state except `unharvested` and `unknown`.
- `@dataclass(frozen=True) FrozenSitrepState(state, triage=(), review=(),
  reason="", instance=None)`. `triage` and `review` are `((cid, item_state),
  …)`. `instance = (record_id, pane_id, standin_pid)` is taken from the
  `record_ver` the verdict was settled against, and is `None` when no record
  was read. Property `safe`.
- **Versions.** `Versions = (record_ver, capture_ver, receipt_ver, todo_ver)`.
  - `record_ver = (state, op_nonce, capture_txt, pane_id, standin_pid,
    frozen_at)` read from the SessionsView record. `freeze_commit` and
    `standin_respawned` rewrite `pane_id` / `standin_pid` (and `frozen_at`) while
    the record id stays the same, so these fields are what tell one frozen
    instance of a record from the next.
  - The file versions are `(st_ino, st_size, st_mtime_ns)`, or `None` when the
    file is absent. `todo_ver` is `None` when no store is consulted.
  - The size is part of every file version: an in-place `O_TRUNC` rewrite keeps
    the inode and changes the size, and the mtime too.
- **Settled record precondition.** The record must be in state `frozen` with an
  empty `op_nonce` (no freeze / restore / drop lease in flight), before and
  after the reads. Otherwise → `unknown("operation_in_flight")`. This is what
  makes an empty capture trustworthy: no writer is mid-rewrite under a settled
  record.
- **One snapshot read** — `read_evidence(rec) -> Evidence`:
  1. If `capture_txt` is empty → `Evidence(no_text=True)`.
  2. Open the capture and `os.fstat` the fd (`ENOENT` → no_text). Read all
     bytes. `len(data)` must equal the fstat size, else changed.
  3. Open the receipt (`ENOENT` → no receipt), `fstat` it, and read it whole.
  4. Evidence carries `data`, the receipt text and the fstat-derived
     `capture_ver` / `receipt_ver`. An empty capture is **not** an early
     return: it flows through the same verification as any other.
- **Publish rule — the one gate every path goes through** (`_settle`):
  1. `pre` = the record version + the evidence's file versions (fresh read), or
     the record version + `os.stat` of both paths (cache probe).
  2. Compute the candidate. On a cache probe, if `pre` matches the cached
     `Versions` and the todo.md sha still matches, the candidate is the cached
     state. Otherwise run `read_evidence` + `derive`, which reads todo.md
     (stat, read, sha, stat again inside the reader).
  3. `post` = re-read the record (`SessionsView.refresh`) + `os.stat` the
     capture, the receipt and the todo.md the candidate consumed.
  4. Publish only if `post == pre` (including the todo.md version the reader
     saw) and the settled-record precondition still holds. Cache only then.
  5. Otherwise retry once from step 1; on a second mismatch →
     `unknown("changed_during_read")`, never cached.

  This gate applies to a cache hit, a fresh read and the empty-capture path
  identically. No branch returns a state before step 4.
- `derive(rec, evidence, todo_reader) -> FrozenSitrepState`, from that single
  Evidence:
  1. `rec is None` → `unknown("no_record")`. A changed evidence →
     `unknown("changed_during_read")`.
  2. no_text → `nothing` (the candidate; published only through the gate),
     which mirrors `capture_harvested`'s "nothing to lose".
  3. `not receipt_certifies(lines, data)` → `unharvested`.
  4. Parse links from the **same** lines. A malformed `triage=` / `review=` /
     `links=` value → `unknown("receipt_malformed")`. No `links=` →
     `unlinked`. Linked with no ids → `nothing`.
  5. Ids present: `store=` must be absolute with basename `.aitask-sitrep`,
     else `unknown`. `todo_reader(store)` returns `{num: state}` or raises. A
     missing or unparsable file, or a cid absent from it → `unknown`.
  6. Classification. Open means item state `open` or `unknown`.
     - any open review → `review_pending`;
     - else any open triage → `triage_open`;
     - else ≥1 triage question and **all** triage questions `done` → `triaged`
       (a closed review alongside does not change it);
     - else (a dismissed triage question, or a closed review with no triage
       question) → `closed`.
- `class FrozenSitrepTracker`: owns one `agent_sessions.SessionsView`.
  `states(record_ids) -> {id: FrozenSitrepState}`. The cache maps record id →
  `(Versions, todo sha, state)`, written only by a successful `_settle`.
  - A cache hit costs two or three `stat`s plus the todo.md read (sha) and the
    post-check, with no capture read.
  - todo.md is parsed only when its sha changes (the `SitrepNowCounter`
    pattern).
  - An exception for one record → `unknown(<ExcName>)`, never cached; the
    others are unaffected.
  - Test seams: an optional `between_reads` hook (called after the candidate is
    computed, before `post`) and counters `derives` / `parses`.
- `describe(state) -> str`, the long wording for the `h` dialog:
  - unharvested: "not harvested yet — Drop harvests first and keeps the agent if that fails"
  - nothing: "harvested — safe to drop; nothing to triage"
  - triage_open: "harvested — safe to drop; follow-ups still to triage (c12)"
  - triaged: "harvested — safe to drop; follow-ups triaged (c12)"
  - closed: "harvested — safe to drop; linked sitrep items closed (c12 dismissed, c20 review done)"
  - review_pending: "harvested — safe to drop (raw output kept); review pending (c20)"
  - unlinked: "harvested — safe to drop; triage link not recorded yet (the next maintenance harvest records it)"
  - unknown: "sitrep state unknown (<reason>)" (never says safe)
- `describe_record(record_id) -> str`: a one-shot fresh tracker → `describe`,
  best effort → `""`.

The Drop wording is checked against `agent_freeze.drop_record` when it is
written.

### 4. Shared badge formatter — `.aitask-scripts/monitor/monitor_shared.py`

Beside `format_frozen_prefix`, ASCII only (no font-coverage risk):

- `FROZEN_SITREP_BADGES = {state: ((text, style), …)}`:
  - unharvested → `unharvested` (yellow)
  - nothing → `drop ok` (green)
  - triage_open → `drop ok` (green) + `, triage` (yellow)
  - triaged → `drop ok` (green) + `, triaged` (dim)
  - closed → `drop ok` (green) + `, closed` (dim)
  - review_pending → `drop ok` (green) + `, review` (yellow)
  - unlinked → `drop ok` (green) + `, ?` (dim)
  - unknown → `sitrep ?` (dim)
- `format_frozen_sitrep_badge(state: str | None) -> str` returns markup with a
  leading space, or `""` for `None`. `frozen_sitrep_badge_width(state)` returns
  the plain cell width. An unknown key raises (the `format_mark_glyph` guard).
- `AgentMarksMixin` — **one coalesced background worker, never awaited by the
  refresh.**
  - Class-level floors: `_frozen_sitrep_results = {}` (record id →
    `FrozenSitrepState`, the latest **validated** verdicts),
    `_frozen_sitrep_tracker = None`, `_frozen_sitrep_inflight = False`,
    `_frozen_sitrep_pending = None`.
  - `_kick_frozen_sitrep(self) -> None` is **synchronous** and called by the
    refresh with no await. It collects `frozen_record_id` from frozen snaps only
    (frozen-first). If no pass is in flight, it starts one through
    `_dispatch_frozen_sitrep(ids)`, the single seam that calls `run_worker(…,
    name="frozen_sitrep", group="frozen-sitrep", exclusive=False,
    exit_on_error=False)`. If a pass is in flight, it only stores the latest
    ids in `_frozen_sitrep_pending` (coalesced: at most one pass running and
    one queued, and the queued one always uses the newest ids).
  - `async def _frozen_sitrep_pass(self, ids)`: `await
    asyncio.to_thread(tracker.states, ids)`.
    - On success, it replaces `_frozen_sitrep_results` with the result,
      restricted to `ids`, so records gone since then drop out. On exception it
      sets `{}`: no badge, never a stale safe one.
    - `finally`: clear `_frozen_sitrep_inflight`; if `_frozen_sitrep_pending`
      is set, take it and dispatch one more pass.
    - It triggers **no repaint of its own**. The next ordinary refresh tick
      renders the new results.
  - `_frozen_sitrep_state(snap) -> str | None`: the latest result for this
    snap, **bound to its frozen instance**, purely in memory. The result is
    used only when `result.instance == (snap.frozen_record_id,
    snap.pane.pane_id, snap.pane.pane_pid)`. The snapshot's `pane_pid` is the
    stand-in's process: `freeze_commit` records exactly that pid as
    `standin_pid`, and every re-freeze or stand-in respawn replaces it.
    - A restore + re-freeze that reuses the record id therefore withholds the
      old badge (→ `None`) until a pass settles against the new instance.
    - No result, a non-frozen snap, or an instance mismatch → `None` (no
      badge, never a stale `drop ok`).

### 5. Monitor + minimonitor wiring

- `monitor_app.py` `_refresh_data`: `self._kick_frozen_sitrep()` (sync, no
  await) right after `self._snapshots` is set. The frozen branch of
  `_format_agent_card_text` renders `[dim]frozen[/]` + the badge of
  `_frozen_sitrep_state(snap)`.
- `minimonitor_app.py` `_refresh_data`: the same sync kick after
  `self._snapshots = …`.
  - Frozen list row: the badge is appended, and the name budget is
    `_row_name(snap, prefix, cell_len("frozen") +
    frozen_sitrep_badge_width(state))`.
  - Own panel: `_update_own_card` reads `_frozen_sitrep_state(snap)` and passes
    it to `_own_card_text` (new `sitrep_state` kwarg, appended to the
    `frozen<stamp>` line). It is added to the repaint compare as
    `_own_sitrep_state`.
- Both renderers only **read** `_frozen_sitrep_results`, so a held badge read
  never delays the refresh.

### 6. `h` dialog wording — `.aitask-scripts/monitor/sitrep_close.py`

In `_harvest_close` with `state == "frozen"`: after the harvest, `line = await
asyncio.to_thread(frozen_sitrep.describe_record, record_id)`. Pass it to
`HarvestResultDialog(…, sitrep_line=line)`, which renders it as a plain-Content
`Sitrep: …` line under the verdict. The line is advisory: buttons depend only
on `report.ok`.

### 7. Docs

- `aidocs/framework/sitrep.md`: the receipt lines (`links=` / `triage=` /
  `review=`), certification-only `receipt_valid`, the `--backfill-links`
  maintenance backfill (and why Drop never backfills). Under "The monitor
  surface": the badge states, the single-snapshot derivation, the fail-closed
  `unknown`, and the cache keys. Add the new test file to the tests table.
- `website/content/docs/workflows/sitrep.md` step 7, and
  `website/content/docs/workflows/freeze-and-restore-agents.md` (drop step):
  the badge and what each word means.
- `cd website && python3 check_links.py --build`.

### 8. Follow-up task (Step 8)

Create a task for the deferred sitrep-TUI part. On a triage item whose source
record is still frozen, show a "source agent still frozen: drop it with `h` in
the monitor" line. It needs the reverse lookup over receipts and is display
only.

## Verification

- `tests/test_frozen_sitrep.py`:
  - one case per state, including **closed via a dismissed triage question**
    and **closed via a done review with no triage question**, and `triaged`
    only when all triage questions are done;
  - a malformed receipt, a bad `store=` and a cid missing from todo → unknown;
  - review precedence;
  - **one replacement that settles** (fresh read): the capture starts
    certified (`drop ok`). On the first attempt only, the `between_reads` seam
    replaces it with new text whose receipt is now stale. The retry derives
    from the replacement evidence, so the published verdict is `unharvested`.
    The old `drop ok` is discarded, and the cache holds the new verdict, not the
    old one;
  - **a change on both attempts**: the seam mutates the capture on every call →
    `unknown("changed_during_read")`, and nothing is cached. The next call with
    the seam removed derives fresh (`derives` increments);
  - **replacement during a cache-hit store read**: the cache is warmed with
    `drop ok`; the seam fires during the todo.md read and rewrites the capture
    in place (`O_TRUNC` + new text). The result is not a safe state;
  - **empty capture observed during a rewrite**: the capture is truncated to
    empty in place (the `_write_private` shape), and the seam then writes the
    new text before the post-check → not `nothing`. Stable empty capture under
    a settled frozen record → `nothing`;
  - **record not settled** (state `freezing`, or a non-empty `op_nonce`) with an
    empty or certified capture → `unknown("operation_in_flight")`;
  - a cache hit does not re-read the capture (`derives` unchanged);
  - a receipt rewrite or a todo.md change invalidates the cache;
  - one record's exception leaves the others intact;
  - `capture_harvested` and `derive` agree on every receipt shape (same
    `receipt_certifies`);
  - `RECEIPT_LINKS` equality across the two modules.
- `tests/test_sitrep_harvest.sh`:
  - the receipt carries `links=1` + `triage=c<N>`;
  - **piped-then-record**: a banner is piped (run marker), then the capture
    showing it is harvested, and the receipt names the piped triage item;
  - a legacy receipt plus a direct `record <id>` (no flag) →
    `HARVEST_NONE:<id>|already_harvested`, with the receipt unchanged, also
    while the writer lock is held;
  - a legacy receipt plus `all` → todo.md byte-identical and the receipt gains
    `links=1`;
  - the pre-phase Drop-under-held-lock section.
- Update `tests/test_sitrep_corpus.py` (`receipt_valid` cases) and
  `tests/test_agent_freeze.py` `_harvest_receipt_text` only where they assert
  the exact receipt text.
- Monitor tests (`tests/test_monitor_agent_marks.py` /
  `tests/test_monitor_sitrep_harvest_close.py`):
  - the formatter is total over the states;
  - the frozen row carries the badge, and the minimonitor name budget subtracts
    its width;
  - **refresh never waits on a badge read, in both TUIs**: the tracker's
    `states` is stubbed to block on a `threading.Event`. Under `App.run_test`,
    `_refresh_data()` completes within a short `asyncio.wait_for` bound while
    the read is held. A second refresh starts **no** second pass (one in
    flight, `_frozen_sitrep_pending` holds the newest ids). After the event is
    released, the queued pass runs once, and the next refresh renders the
    badge. Worker teardown follows `testing_conventions.md` (the event is
    released before the `run_test` block exits);
  - a failing pass leaves `{}` (no badge), and a result for a record id that
    is no longer on a frozen snap is not rendered;
  - **reused record id, new stand-in, delayed read**: the results hold a
    `drop ok` for `(id, %3, 100)`. The snapshot now shows the same record id on
    `%3` with `pane_pid=200` (a re-freeze), and the new pass is held on the
    event. Both TUIs render **no** badge for that row, and the minimonitor own
    panel shows none either. After release, the pass settles against instance
    `(id, %3, 200)`, and the next refresh renders that verdict. A control with
    a matching instance renders the badge;
  - `HarvestResultDialog` shows the `Sitrep:` line, and its buttons are
    unchanged by it.
- Run the touched Python modules through `bash tests/run_all_python_tests.sh
  --test-dir` or directly, plus `bash tests/test_sitrep_harvest.sh`,
  `bash tests/test_sitrep_corpus.sh` and
  `bash tests/test_monitor_harvest_close_live.sh`, and
  `shellcheck .aitask-scripts/aitask_sitrep_harvest.sh`.
- Step 9 (Post-Implementation): archival and merge per the workflow.

## Risk

### Code-health risk: low
- Changing the receipt format and the harvest's cache check touches the drop/purge safety path. A slip could make Drop refuse a certified legacy record (a writer-lock dependency), make `capture_harvested` reject new receipts, or make the gate accept a stale one · severity: low (residual — addressed by inline pre-phase pin_receipt_gate_compat; `receipt_valid` stays certification-only and the backfill is maintenance-only) · → mitigation: inline pre-phase pin_receipt_gate_compat
- The backfill re-harvests every legacy receipt once, on the next `all` pass, inside its 300 s budget. Frozen records are few, the store writes are no-ops, and failures are swallowed by the maintenance tick · severity: low · → mitigation: none
- A concurrent restore, re-freeze or in-place capture rewrite races the derivation. It is handled by one publish gate for every path: the cache hit, the fresh read and the empty capture. The gate re-checks the record, capture, receipt and todo.md versions after all reads and requires a settled frozen record. The replacement, cache-hit and empty-rewrite tests cover it · severity: low · → mitigation: none

### Goal-achievement risk: low
- Agents frozen before this change show `drop ok, ?` until the next maintenance pass (about 10 min) or an `h` records their links · severity: low · → mitigation: none
- The badge is longer than `frozen`, so window names get a shorter budget on the 40-column minimonitor · severity: low · → mitigation: none
- The badge lags the store by up to one refresh tick plus one pass, because the coalesced worker publishes and the next tick renders. This is acceptable for an advisory badge; Drop's own guard is unaffected. A stale verdict for a reused record id is withheld by the instance binding (record id, pane id, stand-in pid) · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: pin_receipt_gate_compat | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: receipt format change on the drop/purge safety path | desc: characterization tests pinning capture_harvested across receipt shapes and the real Drop command with a certified legacy receipt under a held writer lock, before the format changes

## Final Implementation Notes

- **Actual work done:** all plan steps 1–7 implemented as designed (step 8,
  the sitrep-TUI follow-up task, is created at Step 8 review):
  - `lib/sitrep_harvest.py` + `aitask_sitrep_harvest.sh`: the receipt carries
    `links=1` / `triage=c<N>` / `review=c<N>` after the unchanged certification
    base. `receipt_valid` is certification-only (first three lines).
    `receipt_linked` and `record --backfill-links` exist, and only `all` passes
    the flag.
  - `lib/agent_sessions.py`: `receipt_certifies` (the one certification rule,
    shared by `capture_harvested` and the badge) and `HARVEST_RECEIPT_LINKS`.
  - New `lib/frozen_sitrep.py`: the states, `read_evidence` (one fstat'd read
    per file), `derive`, and `FrozenSitrepTracker` with the single publish gate
    (record / capture / receipt / todo.md versions rechecked after all reads,
    settled-record precondition, one retry, uncached `unknown`). Also
    `describe` and `describe_record`.
  - `monitor/monitor_shared.py`: `FROZEN_SITREP_BADGES`,
    `format_frozen_sitrep_badge`, `frozen_sitrep_badge_width`, and the mixin's
    coalesced, never-awaited pass (`_kick_frozen_sitrep` /
    `_dispatch_frozen_sitrep` / `_frozen_sitrep_pass`) with instance-bound
    `_frozen_sitrep_state`.
  - `monitor_app.py` / `minimonitor_app.py`: the kick after the snapshots land;
    the badge on frozen rows and on the minimonitor own panel (repaint compare
    included); the name budget pays for the badge.
  - `monitor/sitrep_close.py`: a `Sitrep: …` line in `HarvestResultDialog` for
    frozen agents. It is advisory, and the buttons are unchanged.
  - Docs: `aidocs/framework/sitrep.md` (receipt link lines, badge section,
    tests table), `website/.../workflows/sitrep.md` step 7, and
    `website/.../workflows/freeze-and-restore-agents.md` step 6.
- **Deviations from plan:** the pre-phase "real Drop under a held harvest lock"
  test went into `tests/test_agent_freeze.py` (`DropLegacyReceiptRealHarvestTests`)
  instead of a `tests/test_sitrep_harvest.sh` section. The real `drop_record`
  needs tmux for its survivor scan and kill, and that suite already provides a
  fake tmux. The real `aitask_sitrep_harvest.sh` still runs as a subprocess
  against a scratch session-store file, and the lock is held by a separate bash
  process through `registry_lock_acquire`. The shell suite still asserts the
  direct `record` short-circuit under a held lock (section 21).
- **Issues encountered:**
  - The first Drop control passed vacuously: a bannerless capture takes the
    lock-free `nothing_found` path. Both tests now use a fixture with a
    wrap-up banner.
  - `test_one_record_failure_leaves_the_others` first had a dead stub. It now
    injects a real `read_evidence` failure.
- **Verification evidence (negative controls):**
  - Removing the publish gate fails all four race tests.
  - Making `settled()` always true fails both settled-record tests.
  - A minimonitor subclass that reads the badge inline in the refresh fails
    `RefreshNeverWaitsTests` ("MUTANT CAUGHT").
  - Every pre-phase pin passed against the pre-change code first.
- **Not run:** `tests/test_frozen_agents_acceptance.sh`. It is a live-tmux
  test that refuses to run inside a tmux session.
- **Key decisions:**
  - The record → item link is recorded by the harvest in the receipt, not
    derived by a store scan (user-confirmed at planning).
  - `receipt_valid` stays certification-only, so Drop never needs the harvest
    mutex; the backfill is maintenance-only.
  - The badge is advisory and computed off the refresh, with instance binding;
    `unknown` is never cached or shown as safe.
  - The `h` dialog body is bounded with `45vh` instead of a fixed 20 rows.
    This also fixes the pre-existing overflow at 12 or more items on a 40x24
    screen, found while verifying the new line.
- **Upstream defects identified:** None
- **Full-suite note:** the one failure in the full Python run,
  `tests/test_control_routed_explicit_targets.py`, flags
  `monitor/monitor_core.py` `_sitrep_launch_client`. That is another
  session's uncommitted change, not touched by this task.

## Post-Review Changes

### Change Request 1 (2026-11-22 19:40)
- **Requested by user:** three review findings:
  1. a failed todo.md read cached an `unknown` verdict forever;
  2. the unbounded Sitrep line pushed the `h` dialog's buttons off a 40x24
     screen;
  3. `describe_record` was awaited with no deadline, even after a failed
     harvest.
- **Changes made:**
  - `FrozenSitrepTracker` never caches an `unknown` verdict. Tests check that
    a store that becomes readable, and an item that appears later, both recover
    in the same tracker; the old-caching mutant fails the store test.
  - The Sitrep line moved inside the scrolling body, and `describe` names at
    most three ids (`+N more`).
  - The body's `max-height: 20` became `45vh`. That also fixes a pre-existing
    overflow: 12 or more item rows alone already pushed the buttons off at
    40x24.
  - The Sitrep line is skipped on a failed report and bounded by
    `SITREP_LINE_TIMEOUT` (3 s) on success. Tests cover a failed report and a
    slow read.
- **Files affected:** `.aitask-scripts/lib/frozen_sitrep.py`,
  `.aitask-scripts/monitor/sitrep_close.py`, `aidocs/framework/sitrep.md`,
  `tests/test_frozen_sitrep.py`, `tests/test_monitor_sitrep_harvest_close.py`.

### Change Request 2 (2026-11-22 19:55)
- **Requested by user:** three low-severity findings:
  1. an undecodable receipt read as `unharvested` instead of `unknown`;
  2. a missing capture recorded no receipt version, so a leftover receipt
     failed the post-check on every attempt;
  3. the backfill check read the receipt and hashed the capture twice.
- **Changes made:**
  - `Evidence.receipt_unreadable` → `unknown(receipt_unreadable)`, still unsafe.
  - The no-capture path records the receipt's version, so the publish gate
    compares like with like.
  - `sitrep_harvest.receipt_state` returns `(valid, linked)` from one read and
    one hash; `receipt_valid` and `receipt_linked` delegate to it, and
    `cmd_plan` calls it once.
  - Tests cover the undecodable receipt and the stable missing-capture case.
- **Files affected:** `.aitask-scripts/lib/frozen_sitrep.py`,
  `.aitask-scripts/lib/sitrep_harvest.py`, `tests/test_frozen_sitrep.py`.

### Change Request 3 (2026-11-23 08:00)
- **Requested by user:**
  1. an OS-level receipt read failure (e.g. mode 000) produced an `unknown`
     with no instance, so the row lost its badge instead of showing `sitrep ?`;
  2. `--force` still ran the receipt check, and `receipt_linked` was left
     with no callers.
- **Changes made:**
  - `FrozenSitrepTracker.states` binds an exception verdict to the record's
    instance when the record resolves; it stays unsafe and uncached. A
    mode-000 receipt test checks the bound `unknown` and its recovery on the
    same tracker, and both TUIs render `sitrep ?`.
  - `cmd_plan` computes `receipt_state` only on the non-forced path.
    `receipt_linked` is removed; `receipt_valid` stays.
- **Files affected:** `.aitask-scripts/lib/frozen_sitrep.py`,
  `.aitask-scripts/lib/sitrep_harvest.py`, `aidocs/framework/sitrep.md`,
  `tests/test_frozen_sitrep.py`, `tests/test_monitor_frozen_sitrep_badge.py`.

### Change Request 4 (2026-11-23 08:15)
- **Requested by user:** a warmed `drop ok` survived a chmod 000 of the
  receipt, because inode, size and mtime are unchanged by chmod.
- **Changes made:** the file version now includes `st_ctime_ns`, so a
  permission change alone invalidates the cache. A regression test warms the
  tracker, revokes the read permission (`unknown`, unsafe), then restores it
  (`nothing`). The ctime-less mutant fails it.
- **Files affected:** `.aitask-scripts/lib/frozen_sitrep.py`,
  `aidocs/framework/sitrep.md`, `tests/test_frozen_sitrep.py`.
