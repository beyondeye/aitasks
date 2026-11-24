---
Task: t2350_sitrep_tui_source_agent_still_frozen_hint.md
Base branch: main
Output branch: main
---

# t2350 — Sitrep TUI: say when a triage item's source agent is still frozen

## Context

t2337 put each frozen agent's sitrep state on the monitor side (the `drop ok`
badge in `ait monitor` / `ait minimonitor`). This task covers the other
direction. A wrap-up triage question or an unparsed-output review case can come
from a frozen agent whose record still exists. When it does, that item's
details in the sitrep TUI should say so and say how to drop the agent. This is
display only. The sitrep TUI never drops, kills or types into a pane, and it
never probes panes.

The receipt (`<capture.txt>.harvested`) is the only record→item link:
`links=1`, then `triage=c<N>` / `review=c<N>`. The reverse lookup (item → frozen
records) scans the frozen records and reuses `FrozenSitrepTracker` from t2337
completely: the certified read, `parse_links`, `receipt_certifies`, the
version-keyed cache, the publish gate and fail-closed `unknown`. Its verdict
needs one extra value, the receipt's `store=`, so the reverse map keeps only
records harvested into **this** TUI's store.

## Review findings addressed (user review, verified against the code)

1. **Registry invalidation (blocking).** `agent_sessions.SessionsView._stat_stamp`
   is `(st_mtime_ns, st_size, st_ino)`, and `chmod 000` changes none of them. A
   warm view therefore keeps serving the cached registry. The tracker's cache
   hit and its publish gate both go through that view, so it would keep
   returning `triage_open`. **Fix:** add `st_ctime_ns` to the stamp (the same
   reason `frozen_sitrep._version` already carries ctime). The next refresh then
   re-reads, `load_safe` returns an empty registry on `OSError`, and no frozen
   records means no hint. The change only adds re-reads. The other users
   (monitor_shared, minimonitor, frozenagent) see a re-read only on a ctime
   change, and every real write also moves mtime and the inode, so they behave
   the same. Update the `SessionsView` docstring.
2. **Drop guidance when the monitor card is missing (blocking).** After a tmux
   restart, a settled record can outlive its stand-in pane, and the monitor's
   `h` needs a selectable pane. The hint keeps the monitor route and adds the
   pane-independent fallback. `ait frozenagent` with no arguments is list mode,
   a cross-project list of every frozen record. In that mode Enter opens the
   record in-process and deliberately does not stamp the pane
   (`frozenagent_app._open_selected`), and `k` (Drop) runs the guarded drop.
   The hint does **not** suggest `ait frozenagent --record <id>`, because that
   mode stamps its own pane as the record's stand-in (rule 1 in
   `frozenagent_app`'s docstring). No pane probe is added to the sitrep TUI.
3. **Label width (blocking).** `_field` pads the label to `_LABEL_W` = 12 and
   appends the value directly, and "Frozen agent" is 12 characters long. **Fix:**
   use the label `Frozen`. The render test asserts the exact
   `"Frozen      agent-…"` separator.
4. **Idle scan cost.** Scan only while it can be shown. The rescan interval is
   a no-op unless the active screen is a details screen for a question item.
   Opening such an item kicks a scan at once, and a scan sequence number
   stops a freshly opened screen from showing a map scanned before it opened.
   Store generations (`_apply`) do not kick scans.
5. **Late scan callback (blocking, second review).** A scan started for a
   question item can land after the user has closed it and opened a task item.
   The new screen has `set_frozen_sources` but `frozen_min_seq=None`, so
   `seq < None` would raise `TypeError` before the dirty rerun. **Fix:**
   - delivery is gated on `wants_frozen_sources`;
   - `frozen_sources_for` treats a `None` threshold as "nothing";
   - the callback clears `_frozen_busy` first, delivers inside
     `try/except`, and runs the dirty rerun in a `finally`, so one bad delivery
     can never wedge the scan loop.
6. **Resume freshness (blocking, second review).** Polling pauses while the
   details screen is covered, so a record can be dropped meanwhile. The
   open-time threshold would then accept a map that predates the cover.
   **Fix:** the open and resume paths share one rule,
   `app.request_frozen_sources()`:
   - it returns a new threshold, `_frozen_seq + 1`, and kicks a scan;
   - a resume withholds the line by clearing it and re-rendering, takes that
     new threshold, and shows the line again only when a scan started after
     the resume lands.
7. **One request path (third review).** Textual 8.2.7's `push_screen` also
   posts `ScreenResume` on the initial push (`textual/app.py` ~2955, checked).
   A separate request in `open_item` would therefore queue a second scan and
   raise the threshold past the first result. **Fix:** `on_screen_resume` is
   the **only** request path, for the first activation and for every return.
   `open_item` passes only `frozen_wanted=True`, for a question item when the
   seam is set, and requests nothing itself.

## Design

### 1. `lib/agent_sessions.py`: ctime in the `SessionsView` stamp
- `_stat_stamp` returns `(st_mtime_ns, st_size, st_ino, st_ctime_ns)`. Update
  the type hint and the docstring to say ctime is there so that a permission
  change alone invalidates the view (t2350).

### 2. `lib/frozen_sitrep.py`: store on the verdict, plus a reverse index
- `FrozenSitrepState` gets the field `store: str = ""`, set by `derive()` on
  the linked branch to the value `_receipt_store(lines)` returned. Because it
  defaults, every existing constructor and the monitor badge are unchanged.
- `LINKED_STATES = frozenset({TRIAGE_OPEN, TRIAGED, CLOSED, REVIEW_PENDING})`.
  These are the only states that carry linked cids from a certified receipt,
  and all of them are in `SAFE_STATES`.
- `FrozenSitrepTracker.frozen_records()` returns `self._view.frozen()`.
- New frozen dataclass `FrozenSource` with `record_id`, `window`, `task_id`,
  `frozen_at`, `link` (`"triage"` | `"review"`) and `state` (the verdict).
- New class `FrozenSourceIndex(sessions_path=None)`. It owns one tracker, so
  the cache persists across scans.
  - `scan(store_dir) -> dict[int, tuple[FrozenSource, ...]]`:
    1. Set `want = os.path.realpath(store_dir)` and
       `recs = tracker.frozen_records()`.
    2. Call `verdicts = tracker.states([r.id for r in recs])`, which is the
       publish-gated, cached derivation.
    3. Keep a record only when all of these hold:
       - its state is in `LINKED_STATES`;
       - `os.path.realpath(v.store) == want`;
       - `v.instance == instance_of(rec)`.

       Anything else is skipped. That covers `unknown`, `unharvested`,
       `unlinked`, `nothing`, another store, and an instance mismatch. Skipping
       is the fail-closed direction: the hint stays absent.
    4. Map each `cN` in `v.triage` (with link `triage`) and in `v.review`
       (with link `review`) to `N`. Sort the sources for each item by
       `(frozen_at, record_id)`.
  - `scan` never raises. Any exception gives `{}`.
- New `describe_source(src) -> str`, plain text that names both routes. For
  example: `agent-pick-7 (t2337, frozen 2026-11-22 10:00) is still frozen —
  harvested, safe to drop. Drop it with  h  (Harvest) on its card in ait
  monitor / minimonitor; if the card is missing (e.g. after a tmux restart),
  run  ait frozenagent , open it (Enter) and press  k  (Drop).`
  A `review_pending` state adds `(raw output kept)`. The keys named are the
  defaults of those TUIs. Window and task are record text and go out as a
  plain value.
- Add a short "REVERSE INDEX (t2350)" paragraph to the module docstring.

### 3. Sitrep TUI: a scan only while it is shown

`sitrep_tui/sitrep_tui_actions.py` (it owns `_init_actions` /
`_start_actions` and the trails worker):
- `_init_actions(..., frozen_scan=None)` takes a sync
  `(store_dir) -> dict[int, tuple]`. `None` means off, which is the test
  default and shows nothing.
- State:
  - `_frozen_scan`;
  - `_frozen_map = None` with `_frozen_map_seq = 0`;
  - `_frozen_seq = 0`, the sequence of the last scan started;
  - `_frozen_busy` and `_frozen_dirty`.
- `_kick_frozen_scan()` coalesces the same way `_kick_trails_scan` does. When
  it starts a worker it increments `_frozen_seq` and passes the value to the
  worker.
- `@work(thread=True, group="sitrep-frozen", exit_on_error=False)
  _frozen_worker(seq)` calls the seam on `self.store_dir` off the loop. An
  exception gives `{}`. It then calls
  `call_from_thread(self._on_frozen_scanned, seq, result)`.
- `_on_frozen_scanned(seq, result)`:
  1. Set `_frozen_busy = False`, then store the map and its seq.
  2. Inside `try`, deliver only when the top screen is active **and**
     `getattr(top, "wants_frozen_sources", False)` is true:
     `top.set_frozen_sources(self.frozen_sources_for(top.item_num, top.frozen_min_seq))`.
     An exception is logged and swallowed, because the line is decoration.
  3. In `finally`, run `_kick_frozen_scan()` when the dirty flag is set.
- `frozen_sources_for(num, min_seq) -> tuple` returns `()` in each of these
  cases:
  - the scan is off;
  - `min_seq` is `None`;
  - no map exists yet;
  - `_frozen_map_seq < min_seq`;
  - the item is not mapped.
- `request_frozen_sources() -> int | None` is the one freshness rule, used by
  both the open path and the resume path. It returns `None` when the seam is
  off. Otherwise it computes `min_seq = self._frozen_seq + 1`, which is the
  next scan to start, whether this kick starts it now or a busy scan's dirty
  rerun starts it. It calls `_kick_frozen_scan()` and returns `min_seq`.
- `_frozen_tick()` is the interval callback. It kicks a scan only when
  `_top_screen()` is active and its `wants_frozen_sources` is true.
- `_start_actions`, when the seam is set, adds
  `set_interval(FROZEN_RESCAN_INTERVAL, self._frozen_tick)` with
  `FROZEN_RESCAN_INTERVAL = 5.0`. Visible staleness after a drop is then
  bounded by about 5 s.

`sitrep_tui/sitrep_tui_app.py`:
- `SitrepTuiApp.__init__(..., frozen_scan=None)` forwards the seam to
  `_init_actions`.
- `open_item` passes `frozen_wanted=(self._frozen_scan is not None and
  item.kind == "question")` and requests nothing itself. Activation (below) does
  the request.
- `ItemDetailScreen`:
  - gets the constructor argument `frozen_wanted: bool = False` and the
    attributes `self._frozen = ()` and `self.frozen_min_seq = None`. The
    threshold stays `None` until the first activation, so no result can be
    delivered before it;
  - `wants_frozen_sources` is a property that returns `frozen_wanted`;
  - `body_content` adds `_field("Frozen", frozen_sitrep.describe_source(src))`
    for each source after the `About` line, and nothing when there is none;
  - `set_frozen_sources(sources)` updates the body only on a change (as
    `set_trails` does). There are no link rows;
  - `on_screen_resume` is the **sole** request path. It runs on the initial
    push, because Textual posts `ScreenResume` then, and on every return. It
    acts only when `wants_frozen_sources` is true. It withholds any old hint
    (`self._frozen = ()`, re-render only if it was non-empty), then sets
    `self.frozen_min_seq = self.app.request_frozen_sources()`. The hint shows
    only from a scan started at or after this activation.
- `main()` passes `frozen_scan=frozen_sitrep.FrozenSourceIndex().scan`. It is
  built once, so the tracker cache persists. `sessions_path=None` resolves
  `$AITASKS_AGENT_SESSIONS_FILE` first and then the default, the same lookup
  the monitor uses.

### 4. Docs
- `website/content/docs/tuis/sitrep/reference.md`, section "Item details",
  gets a **Frozen** bullet. It covers:
  - when it shows: a wrap-up triage question or review case whose source
    agent is still frozen and was harvested into this store;
  - the two drop routes, `h` in the monitor and `ait frozenagent` → Enter →
    `k`;
  - that it is display only and checked while the details are open (about
    every 5 s);
  - that nothing is shown for an unreadable, in-flight or pre-link record
    until `harvest all --backfill-links` records its links.

  Then run `python3 check_links.py --build` in `website/`.
- `aidocs/framework/sitrep.md`, after the "Frozen-agent badge (t2337)" block:
  add a "Reverse index (t2350)" paragraph covering the filters, the
  `sitrep-frozen` worker with its visible-only scan and seq gate, the
  ctime-stamped registry, and why the fallback is list mode and never
  `--record`.

## Steps
1. `lib/agent_sessions.py`: add ctime to the stamp and update the docstring.
2. `lib/frozen_sitrep.py`: add the `store` field, `LINKED_STATES`,
   `frozen_records`, `FrozenSource`, `FrozenSourceIndex`, `describe_source`
   and the docstring paragraph.
3. `sitrep_tui/sitrep_tui_actions.py`: add the seam, seq, worker, callback,
   `frozen_sources_for`, `_frozen_tick` and the interval.
4. `sitrep_tui/sitrep_tui_app.py`: wire the constructor and `open_item`, then
   the `ItemDetailScreen` line, `set_frozen_sources`, resume, and `main()`.
5. Tests (below).
6. Docs, then the link check.
7. Step 9 (Post-Implementation): commit, archive and merge per the workflow.

## Verification
- `tests/test_frozen_sitrep.py`:
  - a new `ReverseIndexTests(_TrackerCase)` covering:
    - a triage link maps to `{3: (src,)}` with link `triage`, and a review
      link with `review`;
    - another store's receipt gives `{}`;
    - a stale (uncertified) receipt, an unlinked receipt, a malformed link line
      (`unknown`) and an unsettled record (lease held) each give `{}`;
    - two records linking one item give two sorted sources;
    - a tracker that raises gives `{}`;
    - `describe_source` names `h`, `ait frozenagent` and `k`, and does not
      contain `--record`;
    - **warmed-scan permission loss:** scan once and get the hint, then
      `chmod 000` the registry and scan again with the same index, which gives
      `{}`. Restore the mode in cleanup. Skip when `os.geteuid() == 0`, since
      root bypasses permissions.
  - a `SessionsView` test: a warm view re-reads after a chmod-only change.
    Check this with `refresh()` returning `True`, and `records()` returning
    `[]` while the file is unreadable.
- `tests/test_sitrep_tui_frozen_source.py` (new; on the fixture and `_Case`
  from `test_sitrep_tui_actions`, as the trails tests are; stub `frozen_scan`
  seam with an optional Event gate):
  - a linked triage item's details show the line, and the assertion pins the
    separator `"Frozen      agent-pick-7"`;
  - an unlinked question item shows no line;
  - a non-question item never kicks a scan;
  - without a seam there is no line and no worker;
  - a scan landing while the details are open updates the active screen only,
    never a covered or closed one;
  - a result from a scan started **before** the open is not shown (seq gate);
  - **one request on first open:** with the interval set far beyond the
    test, opening a question item calls the seam **exactly once**, and its
    result is shown. That checks there is no double request between
    `open_item` and the initial `ScreenResume`;
  - **late callback:** a gated scan starts for a question item. The test
    closes that item, opens a task item, then releases the gate. There is no
    exception, the task details show no line, and a dirty rerun queued meanwhile
    still runs, so `_frozen_busy` ends up `False`;
  - **resume freshness:** with the hint shown, push a covering screen, change
    the seam's result to "record dropped" (`{}`), then pop the screen before
    any interval tick. The line disappears immediately on resume and stays
    gone after the fresh scan lands. The opposite case, where the record is
    still frozen, shows the line again once that scan lands;
  - the interval tick does not scan while only the main list is shown;
  - a raising seam shows nothing;
  - the set of key bindings is unchanged.
- Run the two files with `~/.aitask/venv/bin/python -m pytest -q`, plus
  `tests/test_monitor_frozen_sitrep_badge.py`,
  `tests/test_sitrep_tui_trails_actions.py`,
  `tests/test_sitrep_tui_app.py` and the agent_sessions / frozenagent tests
  that use `SessionsView` as regression checks.

## Risk

### Code-health risk: low
- The `SessionsView` stamp change reaches every user of that view: monitor,
  minimonitor and frozenagent. It only adds re-reads on a ctime-only change,
  and real writes also change mtime and the inode, so behaviour is unchanged
  except that a permission loss now reads as an empty registry, the cold-read
  behaviour. · severity: low · → mitigation: covered by the regression runs in
  Verification.

### Goal-achievement risk: low
None identified. The plan covers the task's requirements and the four review
findings: display only, a receipt-link reverse lookup through the t2337
tracker, fail-closed and off the event loop, nothing shown for pre-link
records, and a drop route that works without a monitor card.

## Final Implementation Notes

- **Actual work done:** all of Design 1–4 as planned.
  - `lib/agent_sessions.py`: `SessionsView` stamp gains `st_ctime_ns`.
  - `lib/frozen_sitrep.py`:
    - `FrozenSitrepState.store` (set by `derive` on the linked branch);
    - `LINKED_STATES`;
    - `FrozenSitrepTracker.frozen_records()`;
    - `FrozenSource`;
    - `FrozenSourceIndex.scan` (store-realpath and instance filters, never
      raises);
    - `describe_source`.
  - `sitrep_tui_actions.py`:
    - the `frozen_scan` seam;
    - `frozen_sources_for` / `request_frozen_sources` / `_kick_frozen_scan` /
      `_frozen_tick`;
    - the `sitrep-frozen` thread worker;
    - `_on_frozen_scanned` (busy cleared first, opt-in-gated delivery in
      `try`, dirty rerun in `finally`);
    - `FROZEN_RESCAN_INTERVAL = 5.0`.
  - `sitrep_tui_app.py`:
    - `frozen_wanted` for question items;
    - `ItemDetailScreen` `Frozen` field, `set_frozen_sources`, and
      `on_screen_resume` as the sole request path (withhold, then re-arm the
      threshold);
    - `main()` builds one `FrozenSourceIndex`.
- **Deviations from plan:** the reference doc names the user-facing route to
  record a pre-link agent's links, harvest + refresh (`r` or the startup run,
  which runs `aitask_sitrep_harvest.sh all` → `--backfill-links`). There is no
  `ait sitrep harvest` verb, so the plan's `harvest all --backfill-links`
  wording would have named a command users cannot type.
- **Issues encountered:** none.
- **Upstream defects identified:**
  - `.aitask-scripts/sitrep_tui/sitrep_tui_model.py:800` (`ORIGIN_LABELS`) with `.aitask-scripts/sitrep_tui/sitrep_tui_app.py` `_field`: the writer accepts the origin key `incarnation` (`lib/sitrep_todo.py:148` `ORIGIN_KEYS`), which has no label entry. Its details row renders as `"  incarnation"`, 13 characters, wider than the 12-column pad, so the value runs into the label (`  incarnation<value>`).
- **Key decisions:** the fallback drop route is `ait frozenagent` LIST mode,
  never `--record` (that mode stamps its own pane as the stand-in).
- **Verification:**
  - New `tests/test_sitrep_tui_frozen_source.py` (16): three mutants, each
    caught.
    - The original plan's callback (no opt-in gate, no None guard, no
      try/finally) fails the late-callback test.
    - Resume without withhold/re-arm fails both resume tests.
    - A double request from `open_item` fails five tests.
  - `tests/test_frozen_sitrep.py`: +14 tests (reverse index,
    `SessionsViewCtimeTests`). Dropping ctime from the stamp fails both chmod
    tests.
  - Regression: 935 passed and 4 skipped across agent_sessions / frozenagent /
    frozen_* / sitrep_tui* / monitor badge + harvest-close; +204 for the
    monitor frozen capture/filter and agent_frozen_ops tests;
    `test_agent_sessions_stamp.sh` 26/26.
  - `website/check_links.py --build` passed.

## Post-Review Changes

### Change Request 1 (2026-11-24 19:05)
- **Requested by user:** three review findings, each verified.
  1. A record listed before the sequential states pass could be published
     stale: a lease or a lost registry seen while a later record was derived
     did not drop it.
  2. The first-open test did not disable the production 5 s rescan timer.
  3. A hint update rebuilt the body, which re-read case records
     (`review_line`) on the UI thread.
- **Changes made:**
  1. `FrozenSourceIndex._scan` publishes from one final registry snapshot
     (`FrozenSitrepTracker.current_records()`). It keeps a kept record only if
     it is still settled at the exact `record_version` it was listed with.
     New tests change the first record while the second is derived, through
     the tracker's `candidate` seam: one takes a lease (first record dropped,
     second kept), one makes the registry unreadable (`{}`). Both fail without
     the recheck.
  2. `_FrozenCase.setUp` patches `actions.FROZEN_RESCAN_INTERVAL` to 3600 s.
     The explicit `_frozen_tick` tests stay.
  3. `ItemDetailScreen` resolves the review-case line once per screen
     (`_review_line`). It depends on the snapshot's context alone, and this
     also takes those reads off the existing age-tick rebuild. New test:
     exactly 1 `review_case` call across open, an age tick and a hint
     update. Without the memo it is 4.
- **Files affected:** `.aitask-scripts/lib/frozen_sitrep.py`,
  `.aitask-scripts/sitrep_tui/sitrep_tui_app.py`, `tests/test_frozen_sitrep.py`,
  `tests/test_sitrep_tui_frozen_source.py`.
- **Concurrent-session note:** `aidocs/framework/sitrep.md` also carries another
  session's uncommitted t2354 hunk (the badge "in place of" the word, around
  line 680). Only my "Reverse index (t2350)" hunk belongs to this task, so that
  file is committed after t2354's hunk has landed. It is never hunk-filtered
  into this commit.

### Change Request 2 (2026-11-24 19:20)
- **Requested by user:** the CR1 per-screen review-line cache kept an empty
  line, read while the analysis file was unavailable, for the screen's whole
  lifetime. The ordinary age redraw used to re-read it, so the guidance never
  recovered without reopening the item, even with no frozen scanner. Verified.
- **Changes made:** `body_content(now, reuse_review=False)`. Every ordinary
  rebuild (open, age tick, trails update) re-reads the review-case line as
  before t2350. Only `set_frozen_sources` passes `reuse_review=True`, so a scan
  landing adds no case-record reads.
  - New test: the line recovers on the age tick without reopening, with and
    without a scanner. It fails against the CR1 cache.
  - Updated test: a hint redraw adds 0 `review_case` calls. It fails when the
    reuse is ignored.
  - Tests now read what the widget shows (`Static.content`), never a fresh
    rebuild.
- **Files affected:** `.aitask-scripts/sitrep_tui/sitrep_tui_app.py`,
  `tests/test_sitrep_tui_frozen_source.py`.
