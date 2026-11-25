---
Task: t2335_2_refresh_direction_freshness.md
Parent Task: aitasks/t2335_sitrep_work_directions.md
Sibling Tasks: aitasks/t2335/t2335_3_trails_highlight_and_critical_path_overlay.md, aitasks/t2335/t2335_4_skill_directions_code.md, aitasks/t2335/t2335_5_tui_directions_tab.md, aitasks/t2335/t2335_6_manual_verification_work_directions.md
Archived Sibling Plans: aiplans/archived/p2335/p2335_1_store_direction_records_format_4.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2335_2: refresh, deterministic direction freshness

## Context

t2335_1 gave the sitrep store direction records (format 4): a summary saved with the digest of a baseline snapshot, plus `freshness`, `checked_at` and `drift` fields that only `direction-freshness --batch` may write. Nothing computes those fields yet, so every direction stays `unknown`. This child adds the deterministic computation to the refresh (`lib/sitrep_refresh.py`): it rebuilds each direction's snapshot, compares it line by line with the retained baseline, and writes `current` / `stale` / `unknown` with named reasons. It also adds the two reads the skill child (t2335_4) needs to save a proposal: build-and-retain a snapshot, and recheck a proposal before the first write.

Contract: `aidocs/framework/sitrep.md`, "Directions". Context files: parent `aitasks/t2335_sitrep_work_directions.md`; archived sibling plan `aiplans/archived/p2335/p2335_1_store_direction_records_format_4.md`; pending siblings `aitasks/t2335/t2335_{3,4,5,6}_*.md`.

Measured on the live store (2026-11-25): the item pass checks 55 targets in 3 s of the 60 s budget, so directions run in the time the item pass leaves and no budget share is reserved for them.

## Review concerns (all seven verified against the code and the plan, all addressed)

| Concern | Verified how | Addressed in |
|---|---|---|
| A trail's hash and its drift verdict can come from two different versions | `load_trail_blob` runs `artifact get`; `aitask_trail_gather.sh drift --trail art:<handle>` runs a second `artifact get` (its lines 46 to 53). A repoint between the two pairs version A's hash with version B's verdict | decision 4, "Reading a trail", Test 19, mutant list |
| A `next` item outside the direction can close with no guard noticing | `op_direction_set` accepts any existing `c<N>` as `next`; `direction_stamp` hashes the members only; closing a non-member item changes neither the block's rev nor the stamp | decision 10, step 1b, Test 21 |
| A recheck cut by the deadline could read as "same" | The first plan defined the changed and failed outputs, not what a prefix of matching results means | "Completeness (both verbs)", Test 22, mutant list |
| The parity check asked for byte-identical stdout although a count line is now added | The scratch store of the mitigation has no direction, and decision 3 prints `REFRESH_UNASSIGNED` there | post-phase live_item_output_parity |
| Rebuilding `run_drift` on a `(verdict, first code)` pair loses item output | `run_drift` (`sitrep_refresh.py:770`) counts every `DRIFT:` line for `drift STALE (N)` and tells `drift unavailable` (failed call, empty output) from `drift error` (a helper-reported first line); the pair carries neither | step 2 (`_drift_output`), the `run_drift` unit tests, post-phase live_item_output_parity |
| The unassigned count is missing exactly when nothing is assigned | The first plan printed `REFRESH_UNASSIGNED` only for a store with a known direction | decision 3, wire contract, Test 17 |
| A record with no digest reads `stale` over an unreadable input, and a bad baseline hides the unreadable inputs | The first verdict table was first-match: `never_summarized` came before the unreadable check, and `baseline_unreadable` returned alone | "Verdict", Test 19 |

## Design decisions

1. **Two phases in one run.** The parent runs the item worker and its `set-state --batch` write as today, then a second killable worker (`dworker`) that loads a NEW store snapshot, then `direction-freshness --batch`. The stamp and the member lines therefore come from a snapshot taken after the item write (the t2335_1 note). The parent still does no scan itself.
2. **Dedicated wire lines**, `REFRESH_DIRECTION:` and `REFRESH_DIRECTIONS:`. `REFRESH_ITEM` and the final `REFRESHED:` line keep their exact shape, so every existing consumer and test string is unchanged.
3. **The unassigned count does not depend on directions.** Phase 2 runs whenever the store was read and the item phase did not fail, and always prints `REFRESH_UNASSIGNED:<n>` (also `0`, also before `REFRESH_NONE:no_targets`), counted from the snapshot taken after the item write. The item worker also announces `DIRECTIONS:<n>` (known directions), so a run with no check time left can say how many directions it did not reach. The item lines and every final line keep their format; the one exact-output assertion that now sees an extra line (`tests/test_sitrep_refresh.sh:221`) is changed to check the last line.
4. **A trail's version is its content hash, and the hash and the drift verdict come from the same bytes.** One `artifact get` per handle: the fetched bytes give the hash (first 12 hex of `blob_hash`) and are written to a private temp file that the drift helper reads as a path, so it never resolves the handle again. The manifest has no ordinal, and a repoint to an older version would keep a count unchanged. Trail value: `<12 hex>:current` or `<12 hex>:stale`.
5. **An unreadable input has a value, `unreadable`, in a snapshot**, so a proposal can still be saved when a trail or a cross-repo task cannot be read. Safety comes from the verdict order: any input unreadable NOW is `unknown`, whatever the digests say; when it becomes readable the line differs from `unreadable` and the verdict is `stale`. It never reads `current`.
6. **The deadline's interrupted direction is written `unknown` with `check_incomplete`** (the item rule), using the rev and stamp its `DSTART` line carried. Directions not started stay untouched and are reported not reached.
7. **`checked_at` means "verdict last changed"** (the recovery-item rule). An unchanged `(freshness, drift)` sends no batch line and is reported `unchanged`. Rotation under a tight budget uses the existing attempt ledger with a new `directions` map (slug to last attempt), so a slow trail cannot starve the other directions.
8. **Proposal verbs are subcommands of `aitask_sitrep_refresh.sh`** (`snapshot`, `recheck`), not a new helper script: they share the worker, the deadline and the readers, and no new whitelist entry is needed.
9. Two codes are added to the task's vocabulary: `task_unreadable` (an unreadable task or `next` task, `unknown`) and `check_incomplete` (decision 6, `unknown`).
10. **The stamp covers every store-side input of the verdict.** The block's rev covers the record (trails, the `next` key, the digest); the stamp covers the members. The one input neither covers is the item a `next: c<N>` points at, which need not be a member. `st.direction_stamp` therefore also hashes `next:c<N>@<item rev>` when the record's `next` is an item id. A stamp for a direction whose `next` is empty or a task ref is unchanged, so the saved fixtures keep their stamps. Inputs outside the store (task files, trail artifacts) stay outside the lock, as the contract already says.

## Snapshot values (the refresh owns them)

| Line | Key | Value |
|---|---|---|
| `member` | `c<N>` (pending members only) | `<state>\|<ref>` (store grammar) |
| `task` | canonical ref of each pending member whose ref is a task ref (`t<N>[_<M>]` or `<project>#<N>[_<M>]`), any item kind, once per ref | active: the status (`Ready` … `Done`, `Folded`); archived: `archived:<status>`; found only in another task's `folded_tasks`: `folded:t<N>`; `missing`; `unreadable` (lookup error, unresolved project) |
| `trail` | each handle of the record's `trails` (or the proposed ones) | `<12 hex>:current`, `<12 hex>:stale`, `unreadable` (blob or drift not readable) |
| `next` | the record's `next` (or the proposed one) | `valid` (a pending item `c<N>`; an active task in Ready / Editing / Implementing / Postponed), `closed`, `missing`, `unreadable` |

`recover:` and `push:` refs get no task line. Task lookups reuse `sitrep_refresh.TaskIndex` and `Projects`.

### Reading a trail

`Reader.trail_value(handle)`, once per handle and direction:

1. `trail_discovery.load_trail_blob(handle)`: one `artifact get`. No document, no `blob_hash` or no `blob_raw` is `unreadable`.
2. The bytes go to a file in the worker's private temp directory.
3. `drift_facts(root, <that path>)` runs `aitask_trail_gather.sh drift --trail <path>`. The wrapper resolves only `art:` arguments, so a path reaches `trail_gather.py` as it is and no second fetch happens. `CURRENT` or `STALE` with its first `DRIFT:` code; anything else is `unreadable`.
4. Value: `<first 12 hex of blob_hash>:<verdict>`.

The item refresh's own `check_trail` keeps its text-only `run_drift` call: its outcome line carries no hash to pair.

## Verdict

The evidence is collected first, each part on its own, and combined after. No part hides another.

| Evidence | When | Reasons |
|---|---|---|
| N, never summarised | the record has no digest | `never_summarized` |
| U, could not be read | the current snapshot is above `st.MAX_BASELINE_BYTES` | `baseline_too_large` |
| | the record has a digest and `st.load_baseline` is not `ok` | `baseline_unreadable` |
| | a current value is `unreadable` | `trail_unreadable` / `task_unreadable`, one cause per key |
| C, classified differences | the baseline is `ok` and the snapshot was built | the reasons of the list below |

| Freshness | Condition | Reasons written |
|---|---|---|
| `unknown` | U is not empty | N, then U, then C: everything that was established |
| `stale` | U is empty and N holds | `never_summarized` |
| `current` | U and N are empty and the snapshot's digest equals the record's | none |
| `stale` | otherwise | C, or `inputs_changed` when C is empty |

So a record with no digest and an unreadable trail is `unknown` with `never_summarized` and `trail_unreadable`, and a damaged baseline with an unreadable task is `unknown` with `baseline_unreadable` and `task_unreadable`. Reasons are fed to `st.aggregate_drift` in vocabulary order.

Classification, baseline line against current line (pure, in vocabulary order):

- `member_added`: a current member line with no baseline line.
- `member_closed`: a baseline member that is still a member and now `done` / `dismissed`. `member_removed`: a baseline member that no longer names the direction.
- `task_completed`: a task value that became `Done`. `task_archived`: became `archived:*`. `task_deleted`: became `missing`. A task line that left with its closed member is not a reason of its own.
- `trail_new_version`: the hash part changed. `trail_stale`: the verdict part became `stale`; the key is `<handle>=<the trail's first DRIFT code>` when that fits 132 characters, else the handle.
- `next_invalid`: the same `next` key, a value that changed to something other than `valid`.
- Any other difference (a member's state or ref, Ready to Implementing, a `folded:` value, a changed trail or `next` key) is not classified: it yields `inputs_changed` only when no reason above was found.
- Reasons go through `st.aggregate_drift`.

## Wire contract (header of `aitask_sitrep_refresh.sh`)

```
REFRESH_DIRECTION:<slug>|<old>-><new>|<result>|<drift>
    result: applied | unchanged | stale | kept:<why> | not_found | no_record | unversioned | dry_run
REFRESH_UNASSIGNED:<n>                       pending items in no direction (every run that read the store)
REFRESH_DIRECTIONS:checked=<n>|changed=<c>|unknown=<u>|refused=<r>
REFRESH_WARN:direction_unknown|<n> unknown
REFRESH_WARN:directions_not_reached|<n> not reached
REFRESH_WARN:directions_failed|<reason>      phase 2 failed; the item results stand
```

- `stale` is the batch's `STALE:` (the rev or the membership moved; recomputed next run, never retried), `kept:<why>` its `KEPT:` answer, `not_found` its `NOT_FOUND:`. `no_record` is a known direction with no block (nothing can hold a verdict; reported `stale` with `never_summarized`, no batch line). `unversioned` is a block with rev 0 on a store not yet upgraded.
- `REFRESH_UNASSIGNED:<n>` prints on every run whose phase 2 read the store, with or without directions, before the final line. It is absent only when nothing was read after the item phase: `REFRESH_NONE:no_store`, `REFRESH_FAILED:`, or no check time left. On `--dry-run` it counts the store as it is, without the unwritten item results.
- The `REFRESH_DIRECTION` lines, `REFRESH_DIRECTIONS:` and the direction warnings print only when the store has a known direction. With directions and no item target the run ends `REFRESHED:checked=0|…`; with neither it still ends `REFRESH_NONE:no_targets`.
- A phase-1 failure still ends `REFRESH_FAILED:` and skips phase 2.

Proposal verbs (stdin: one line per direction; `=` is "as stored", `-` is none):

```
aitask_sitrep_refresh.sh snapshot [--root R] [--budget S]     <slug>|<members csv>|<trails csv>|<next>
  SNAPSHOT:<slug>|<digest>|baselines/<digest>.txt|<pending>|<unreadable count>
  SNAPSHOT_UNREADABLE:<slug>|<kind>|<key>
  SNAPSHOT_TOO_LARGE:<slug>|<bytes>|<limit>          nothing retained for it
  SNAPSHOTS:<retained>|<refused>                     final, exit 0;  SNAPSHOT_FAILED:<reason> exit 1
aitask_sitrep_refresh.sh recheck [--root R] [--budget S]      <slug>|<members csv>|<trails csv>|<next>|<digest>
  RECHECK_SAME:<slug>|<digest>
  RECHECK_CHANGED:<slug>|<saved digest>|<digest now>
  RECHECK_REASON:<slug>|<code>|<count>|<sample>      from the retained baseline, when it loads
  RECHECK_INCOMPLETE:<slug>                          requested, no result (see Completeness)
  RECHECK:same exit 0 | RECHECK:changed|<n> exit 1 | RECHECK_FAILED:<reason> exit 1
```

`snapshot` retains through the writer's `retain-baseline` (the parent does it; the worker writes snapshot text only into a private temp directory). `recheck` is read-only. An unknown item id, a bad slug, a slug named twice or a bad field is exit 2. `recheck` exits non-zero on any difference, so the skill cannot save over moved evidence.

**Completeness (both verbs).** The worker is deadline-bound and can be cut after some directions. A prefix of results is never a success:

- The parent parses stdin itself, so it knows the requested slugs. The run is complete only when the worker exited 0, was not interrupted by the deadline, left no `DSTART` open, and returned exactly one result for every requested slug and for no other.
- `RECHECK:same` (exit 0) is printed only for a complete run in which every result is `RECHECK_SAME`. Any other complete run is `RECHECK:changed|<n>` (exit 1).
- An incomplete run prints the results it has, then `RECHECK_INCOMPLETE:<slug>` for each requested direction with no result, then `RECHECK_FAILED:incomplete|<done> of <requested>` (exit 1). `RECHECK_FAILED:` is also the final line for a worker failure, a protocol error and an unusable store.
- `snapshot` follows the same rule: an incomplete run ends `SNAPSHOT_INCOMPLETE:<slug>` lines and `SNAPSHOT_FAILED:incomplete|<done> of <requested>` (exit 1). Baselines it already retained stay: they are content-addressed and name nothing until a `direction-set` uses them.
- Unlike these verbs, the refresh run itself may stop early: its unreached directions keep their stored verdict and are reported not reached.

## Implementation steps

1. **New `lib/sitrep_direction.py`** (pure logic plus the readers; imports `sitrep_refresh` for `TaskIndex`, `Projects`, `clean_text`; `sitrep_refresh` imports it lazily, as it does `sitrep_crash`).
   - `VOCABULARY` (ordered codes), `UNKNOWN_CODES`.
   - `class Reader(root, checker, tmp_dir)`: `task_value(ref)`, `trail_value(handle) -> (value, first_code)`, `next_value(store, key)`. `trail_value` follows "Reading a trail": one `load_trail_blob` (honouring `AITASK_SITREP_REFRESH_ARTIFACT_SH`), then `sitrep_refresh.drift_facts(root, <path of the fetched bytes>)` (step 2). Results are cached per handle for the run, so two directions sharing a trail read it once.
   - `build_snapshot(slug, members, tasks, trails, next) -> (text, unreadable)`: renders in the store grammar (kinds in order, keys sorted, final newline) and is checked with `st.parse_baseline` whenever it is within the size limit.
   - `snapshot_for(store, slug, reader, members=None, trails=None, next=None)`: the stored inputs, or a proposed set.
   - `classify(baseline, current, store, slug) -> [(code, key)]`, `evidence(record, store_dir, slug, text, unreadable, current, trail_codes)` returning the three parts N, U and C separately, and `verdict(evidence) -> (freshness, drift)` combining them as in "Verdict".
   - `parse_proposal(text, with_digest)`: the stdin grammar, `st.RequestError` on a bad line.

   1b. **`lib/sitrep_todo.py`, the stamp** (decision 10). `direction_stamp(store, slug, members=None)` appends the line `next:c<N>@<item rev>` when `store.directions[slug].next` is an item id. Its docstring, the module docstring line on the stamp, the `direction-freshness` paragraph in the header of `aitask_sitrep_todo.sh` and "Freshness and the membership stamp" in `aidocs/framework/sitrep.md` say what the stamp covers. `op_direction_freshness_batch` and `op_directions` already call the helper, so they need no other change.
2. **`lib/sitrep_refresh.py`**
   - The drift helper call is split from its two readers, and nothing the item formatter reads is dropped:
     - `_drift_output(root, trail) -> (rc, lines)`: the subprocess call that `run_drift` makes today (same argv shape, same `DRIFT_CAP`, same cwd), on a handle or a file path. `rc` is `None` for a timeout or an `OSError`; `lines` are the non-empty stripped stdout lines, ALL of them. The helper path comes from `AITASK_SITREP_REFRESH_TRAIL_GATHER_SH` (test-only), else `TRAIL_GATHER_SH`.
     - `run_drift(root, handle) -> str` keeps its four texts, decided by the same conditions in the same order over `(rc, lines)`: `drift unavailable` (no result, a non-zero exit, or no line), `drift CURRENT`, `drift STALE (<number of DRIFT: lines>)`, `drift error` (any other first line, such as the helper's `ERROR:`). Its body changes only in where the output comes from.
     - `drift_facts(root, path) -> (verdict, first_code)` for directions reads the same `(rc, lines)`: `("current", "")`, `("stale", <code of the first DRIFT: line>)`, and `("", "")` for both error kinds, which a direction reads as `unreadable`.
   - `cmd_worker`: emit `DIRECTIONS:<len(st.known_directions(snapshot))>` after `ROOT:` and before `NONE:` / `TARGETS:`. `Stream.feed` accepts it.
   - `cmd_dworker` (`dworker --mode refresh|proposal --root --parent [--spec FILE] [--out DIR]`), with the parent watchdog. Lines: `ROOT:`, `NONE:no_store`, `FAILED:`, `ATTEMPTS:<path>`, `UNASSIGNED:<n>`, `DTARGETS:<n>`, `DSTART:<slug>|<rev or ->|<stamp>|<old freshness>|<old drift>`, `DVERDICT:<slug>|<freshness or no_record>|<drift>`; in proposal mode `DSNAP:<slug>|<digest>|<bytes>|<file>|<pending>|<unreadable keys>` and `DCHECK:<slug>|<saved>|<now>|<drift>`. One direction's exception is `unknown` / `check_incomplete`, never the end of the run. Order: `order_directions` by the ledger's `directions` stamps (`never` first, then slug).
   - `DirectionStream` (pure, unit-tested like `Stream`): `feed`, `close(interrupted)` giving the interrupted `DSTART` as `unknown` / `check_incomplete`.
   - `supervise(cmd, deadline, stream=None)`: takes the stream object, so both workers share the kill-the-group loop.
   - `run_writer(root, verb_args, batch, deadline, restart)`: generalised from the fixed `set-state --batch`.
   - `cmd_run`: after the item results (also after `NONE:no_targets`): with no check time left, print `directions_not_reached|<n>` when `stream.directions > 0` and nothing else; otherwise run `dworker`, print `REFRESH_UNASSIGNED:<n>` from its `UNASSIGNED:` line, and, when it reports directions, drop unchanged and no-record lines, build `<slug>|<rev>|<stamp>|<freshness>|<ts>|<drift>` lines, pause seam `AITASK_SITREP_REFRESH_DIRECTION_PAUSE_FIFO` (point `refresh:before_direction_write`), write, map `FRESHNESS:` / `STALE:` / `KEPT:` / `NOT_FOUND:`, print the lines of the wire contract, stamp the ledger. The whole phase sits in one `try`: any `WorkerFailure` becomes `REFRESH_WARN:directions_failed|…` and the item output and exit status are untouched. `NONE:no_targets` with directions takes the same path with zero item counts.
   - Ledger: `read_attempts` / `merge_attempts` / `write_attempts` carry a second map `directions` (same version 1; a reader that does not know it ignores it; a lost map only makes directions look older).
   - `cmd_snapshot`, `cmd_recheck` (parent side of the proposal verbs) and their parser entries. Both end through one helper, `proposal_complete(requested, stream, interrupted, rc)`, which implements the Completeness rule; the success line is reachable only through it. Module docstring: targets, the verdict table, the `checked_at` rule, the new worker lines.
3. **`aitask_sitrep_refresh.sh`**: header (wire contract above, the two new seams, the `checked_at` rule), `usage`, and the optional first word `snapshot` / `recheck` (stdin passed through; same `--root` / `--budget` checks). Default with no word is `run`, unchanged. Read `aidocs/framework/shell_conventions.md` first.
4. **TUI report** (`sitrep_tui/sitrep_tui_model.py`, `sitrep_tui_actions.py`): `parse_refresh_output` collects `REFRESH_DIRECTION` payloads and the `REFRESH_DIRECTIONS` counts; `RefreshReport.partial` also counts `direction_unknown`, `directions_not_reached` and `directions_failed`; `verdict()` appends `; directions: N checked, M changed[, K unknown][, R not reached]` when directions were checked; `refresh_lines` lists them. The monitor tick only runs the script and needs no change.
5. **Tests**
   - New `tests/test_sitrep_direction.py`: `build_snapshot` round-trips through `st.parse_baseline`; one `classify` case per reason; `inputs_changed` for Ready to Implementing; every combination of the verdict's evidence parts, incl. the negative controls (an unreadable trail with EQUAL digests is `unknown`, never `current`; an unusable baseline per `load_baseline` status; an oversized snapshot) and the overlaps (no digest plus an unreadable trail is `unknown` with both reasons; a damaged baseline plus an unreadable task is `unknown` with both; an oversized snapshot plus no digest); a partial read keeps its classified reasons; `Reader.trail_value` with a loader stub that answers version A then version B: one load per handle, the value's hash and verdict both belong to A, and the drift helper was given a path, never the handle; 20 closures plus two other causes give three reasons with `member_closed:20:…`; the composite `trail_stale` key and its fallback to the handle; `parse_proposal` refusals.
   - `tests/test_sitrep_refresh.py`: `run_drift` through a stub helper, pinning each text: `drift CURRENT`; `drift STALE (3)` for three `DRIFT:` lines and `drift STALE (0)` for none; `drift unavailable` for a non-zero exit, for empty output and for a helper that cannot be run; `drift error` for an `ERROR:` first line with exit 0. `drift_facts` over the same stub outputs. These are written and run against the UNCHANGED `run_drift` first (only the seam lookup added), then again after the split.
   - `tests/test_sitrep_refresh.py`: `DirectionStream` (order violations, the interrupted `DSTART`), `Stream` accepts `DIRECTIONS:`, the ledger's `directions` map (read, merge, prune, an old-shape file), `order_directions`.
   - `tests/test_sitrep_refresh.sh`, new Tests 17 to 22 on stores built through the real writer, with a fake artifact CLI and a stub drift helper:
     - 17: `never_summarized`; `snapshot` then `direction-set` then refresh gives `current`; a second run writes nothing (file byte-identical, rev unchanged, result `unchanged`); title, rank, trails, next, summary and digest byte-identical around every freshness write. The unassigned count: a store that holds only pending items in no direction prints `REFRESH_UNASSIGNED:<n>` with the right count and no `REFRESH_DIRECTION` line; after its last item closes it prints `REFRESH_UNASSIGNED:0` and its last line is still exactly `REFRESH_NONE:no_targets`; an item closed by this very run is not counted; `REFRESH_NONE:no_store` prints no count.
     - 18: each drift reason end to end (member added, closed, removed; task completed, archived, deleted; trail stale, new version; `next` invalid), and `REFRESH_UNASSIGNED` next to directions.
     - 19: `unknown`: an unreadable trail (never `current`, with the equal-digest control), a damaged baseline (`baseline_unreadable`), an oversized snapshot (`baseline_too_large`), and the `direction_unknown` warning. The overlaps: a record with no digest and an unreadable trail is `unknown` with `never_summarized` and `trail_unreadable`; a damaged baseline with an unreadable task is `unknown` with both reasons. **A handle that changes between reads**: the baseline is saved over version A, which is stale; the fake artifact CLI serves A on the first `get` of a run and B (current) on every later one, and logs each `get`. The refresh must read `stale` hash-A evidence consistently: the verdict is never `current`, the log shows exactly one `get` for the handle, and the drift stub's log shows a file path.
     - 20: budget: an item check that eats the budget leaves the directions not reached (their stored `current` is not rewritten and the warning names the count); a stalled trail read is killed, that direction is `unknown` / `check_incomplete`, and the next run starts with the other directions (ledger), with a delete-the-ledger control.
     - 21: the race: paused at `refresh:before_direction_write`, each of these gives result `stale` with `todo.md` byte-identical: a member's `set-state`, an item moved in, a member moved out, and **the closure of a `next` item that is not a member** (the direction's rev and its member list are both unchanged; a `current` line is waiting). The control with no change applies. The next run then reads `stale` with `next_invalid`.
   - `tests/test_sitrep_todo_format.py` and `tests/test_sitrep_todo.sh` (the stamp, step 1b): the stamp moves when a non-member `next` item changes state, and when `next` is re-pointed to another item; it is unchanged for an empty `next` and for a task-ref `next` (the fixture's `expected_directions.txt` stays byte-identical); `direction-freshness --batch` answers `STALE:` to a line computed before a non-member `next` item closed, with the file byte-identical, and applies the control.
     - 22: proposal: `recheck` is `RECHECK:same` and exit 0 with no change; a task closed during the confirmation gives `RECHECK_CHANGED` with `task_completed`, exit 1, and the script's guarded `direction-set` is not run (store byte-identical); a task closed after the save reads `stale` on the next refresh; `SNAPSHOT_TOO_LARGE`; a proposed member set that differs from the stored one. **A recheck cut short**: a proposal of two directions whose first matches and whose second stalls on its trail read, under a small `--budget`: the output has `RECHECK_SAME` for the first, `RECHECK_INCOMPLETE` for the second, the last line is `RECHECK_FAILED:incomplete|1 of 2`, the exit status is non-zero, `RECHECK:same` is absent, and the script's guarded `direction-set` calls are not run (store byte-identical). The control with no stall is `RECHECK:same`. The same pair for `snapshot` ends `SNAPSHOT_FAILED:incomplete|1 of 2`.
   - `tests/test_sitrep_refresh.py`: `proposal_complete` over a missing slug, an extra slug, a repeated result, an open `DSTART`, an interrupted run and a non-zero worker exit; each is incomplete, and only the full set is complete.
   - `tests/test_sitrep_tui_actions.py`: parse, `verdict()` and `partial` with direction lines; an output without them reads exactly as before.
   - Existing suites listed under Verification must pass unchanged.
6. **Docs** (read `aidocs/framework/documentation_conventions.md` first)
   - `aidocs/framework/sitrep.md`: "Directions" gains "The freshness verdict" (digest inputs and values, the verdict table, the reason vocabulary with one line each, the `checked_at` rule, what is not reached, the proposal verbs); the baseline example uses real values; the Components row, the TUI "Harvest + refresh" bullet and the tests row are updated.
   - `website/content/docs/tuis/sitrep/reference.md:358`: the re-check verdict line gains the directions part. Then `python3 check_links.py --build` in `website/`.
   - `lib/sitrep_refresh.py` and `aitask_sitrep_refresh.sh` headers (steps 2 and 3).

### Post-phase (risk mitigations)

1. [live_item_output_parity] The item refresh must behave as before.
   - Before the first edit: `./.aitask-scripts/aitask_sitrep_refresh.sh --dry-run` on the live store, output saved in the scratchpad; and `git archive HEAD .aitask-scripts` extracted there as the old code.
   - After step 2: the same dry run again. The legacy lines (every line except `REFRESH_UNASSIGNED:` and the `REFRESH_DIRECTION*` lines) are compared with the saved output; a line that differs is explained by a real change of its item (its task or lock moved in between) or it is a defect.
   - One scratch store with task, push, trail and recovery targets and no direction, copied twice: the old and the new refresh each run on one copy with `AITASK_SITREP_NOW` pinned. The trail targets cover every drift text: one trail whose drift is current, one stale with several `DRIFT:` lines (the count must match), one whose helper call fails (non-zero exit), one whose helper prints nothing, and one whose helper reports `ERROR:` with exit 0. The old code has no seam for the helper, so both scratch copies of `.aitask-scripts/` (the old one from `git archive`, the new one copied from the working tree) get the SAME stub in place of `aitask_trail_gather.sh`, answering by handle. Two separate checks, so a regression cannot hide behind the intended addition:
     - legacy output: the new stdout with its `REFRESH_UNASSIGNED:` line removed is byte-identical to the old stdout, same lines in the same order, and the two `todo.md` files are byte-identical;
     - the addition: the new stdout has exactly one line the old one lacks, it is `REFRESH_UNASSIGNED:<n>` with `n` equal to the store's pending items (counted independently with `directions`' `UNASSIGNED:` line), and it comes before the final line.
   - Record the commands and their output in the Final Implementation Notes.
2. [verdict_guard_mutants] Each guard is proven to be tested. In a scratch copy of `.aitask-scripts/` (never in the working tree), remove one guard at a time and run the named tests against the copy; each mutant must fail at least one assertion that names the guard, and the unmutated copy must pass:
   - an unreadable input makes the verdict `unknown`;
   - the baseline status makes it `unknown`;
   - the size limit makes it `unknown`;
   - `unknown` keeps `never_summarized` and the classified reasons beside the unreadable ones;
   - the drift helper reads the fetched bytes (mutant: pass it the handle again; the changing-handle case of Test 19 must fail);
   - the `next` item in the stamp (mutant: members only; the non-member closure of Test 21 must fail);
   - the unchanged-verdict skip (the second run must write nothing);
   - the stamp of the batch line taken from the post-write snapshot (Test 21);
   - the interrupted direction written `unknown` (Test 20);
   - the Completeness rule (mutant: `RECHECK:same` when every returned result matches; the cut-short case of Test 22 must fail).
   - Record the mutant, the failing assertion and the control run in the Final Implementation Notes.

## Order of work and the live store

The monitor's maintenance tick runs this checkout's refresh against the live `.aitask-sitrep/` every ten minutes (t2335_1 saw uncommitted code upgrade the live store this way). So:

- Step 1 (the new module) and its unit tests land first; nothing calls it yet.
- In step 2 the phase-2 call in `cmd_run` is the LAST edit, after `DirectionStream`, the worker and the writer mapping pass their unit tests.
- The live store has one known direction (`crashed-agents`, no block), so until someone saves a record phase 2 sends no batch line there: it reports `no_record` and writes nothing.

Another session has uncommitted edits in `.claude/skills/task-workflow-remote-/`, `.opencode/skills/task-workflow-remote-/`, `.codex/config.toml` and `CLAUDE.md`. None is a file of this plan. Re-check `git status` on `aidocs/framework/sitrep.md` and the website page before their first edit; commits name their paths.

## Notes to send after implementation (workflow Step 8e)

- t2335_4: the `snapshot` and `recheck` verbs and their lines; the `unreadable` value; `aitask_sitrep_refresh.sh` needs the code-agent permission touchpoints when the skill first calls it.
- t2335_5: the snapshot value forms, the reason vocabulary, the `checked_at` meaning, the `RefreshReport` additions, and that an `unknown` verdict can carry several reasons (`never_summarized` beside an unreadable one).
- Both: the stamp now also covers a `next` item.

## Verification

- Before editing: run `bash tests/test_sitrep_refresh.sh`, `python3 tests/test_sitrep_refresh.py`, `python3 tests/test_sitrep_tui_actions.py` once for a baseline.
- `python3 tests/test_sitrep_direction.py`; `python3 tests/test_sitrep_refresh.py`; `bash tests/test_sitrep_refresh.sh`.
- Consumers: `tests/test_sitrep_todo.sh`, `test_sitrep_todo_format.py`, `test_sitrep_tui_actions.py`, `test_sitrep_tui_app.py`, `test_monitor_sitrep_refresh.py`, `test_sitrep_crash.{sh,py}`, `test_sitrep_skill_contract.sh`.
- `shellcheck .aitask-scripts/aitask_sitrep_refresh.sh`; `python3 check_links.py --build` in `website/`.
- Then workflow Step 9 (post-implementation: review, commit, archival).

## Risk

### Code-health risk: medium
- `cmd_run`, `supervise` and `run_writer` are reworked to carry a second phase. The item refresh is a load-bearing path: the monitor runs it on the live store every ten minutes and the TUI on every `r` · severity: medium (residual: low, phase 2 is isolated in one `try` and the item output is compared before and after by inline post-phase live_item_output_parity) · → mitigation: inline post-phase live_item_output_parity
- Uncommitted code reaches the live store through the monitor tick while this task is being implemented · severity: low · → mitigation: none (the order of work: the phase-2 call is the last edit, and the live store has no direction record to write)
- `sitrep_refresh.py` gets a second worker, a second stream and a second write, and grows by a few hundred lines · severity: low · → mitigation: none (the direction logic is its own module with pure, injected functions)
- `st.direction_stamp` changes for directions whose `next` is an item id. The stamp is t2335_1's store contract, read by `directions` and by the batch write. An older checkout's writer computes the old stamp, so its `direction-freshness` lines for such a direction answer `STALE:` · severity: low · → mitigation: none (no other code writes freshness; a refused line is the safe direction; stamps for other directions are byte-identical and the fixture pins that)
- Phase 2 now runs on every refresh, also for a store with no direction, to print the unassigned count: one more short-lived process and one more store read per run · severity: low · → mitigation: none (measured item pass 3 s; the phase is skipped when no check time is left, and its failure is a warning)
- The attempt ledger gains a `directions` map that an older checkout's refresh drops when it rewrites the file · severity: low · → mitigation: none (the ledger is a scheduling hint; a lost stamp only makes a direction look older)

### Goal-achievement risk: medium
- "Never `current` over an unreadable or changed input" rests on the evidence being combined correctly, on one fetch per trail and on the batch stamp covering every store-side input. A guard that no test exercises could be lost unnoticed · severity: medium (residual: low, each guard is removed in turn by inline post-phase verdict_guard_mutants) · → mitigation: inline post-phase verdict_guard_mutants
- The plan settles points the task text leaves open or states differently: a trail's version is its content hash, a snapshot may hold the value `unreadable`, two codes are added (`task_unreadable`, `check_incomplete`), a direction with no block is reported and not written · severity: medium · → mitigation: none (decided at plan approval; documented in the "Directions" section)
- The `snapshot` / `recheck` contract is fixed before t2335_4 is planned and may not fit it · severity: medium · → mitigation: none (Test 22 plays the skill's sequence; a note goes to t2335_4)
- Directions run in the time the item pass leaves. If item checks ever fill the whole budget on every run, no direction is reached · severity: low · → mitigation: none (measured 3 s of 60 s on the live store; the run warns `directions_not_reached` and the TUI shows it as partial)
- A direction that stays `unknown` (an oversized `crashed-agents`, an unregistered cross-repo project) makes every refresh partial, so the TUI's startup toast is a warning each time · severity: low · → mitigation: none (the task text asks for it; t2335_5 can decide how to show it)

### Planned mitigations
- timing: post-phase | name: live_item_output_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the rework of the run path regressing the item refresh | desc: compare the item refresh's output and written store before and after the change, on the live store (dry run) and on a scratch store
- timing: post-phase | name: verdict_guard_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a wrong current verdict slipping through an untested guard | desc: remove each verdict and write guard in a scratch copy and confirm a test naming it fails

## Post-Review Changes

### Change Request 1 (2026-11-25 16:10)
- **Requested by user:** five review concerns, each confirmed against the code. (1) `recheck` returned `RECHECK:same` on an equal digest without loading the retained baseline; with a corrupted baseline the assignments went through and `direction-set` then refused `hash_mismatch`. (2) A proposal naming a `next` item that does not exist passed both verbs, while `direction-set` refuses it. (3) With no item target, a failed or skipped direction pass ended `REFRESH_NONE:no_targets` and the TUI verdict read "Nothing to refresh", hiding the warning. (4) A fetch killed at the deadline left `trail_discovery`'s `ait_trail_*` temp file behind. (5) The direction worker rebuilt the membership map for every direction.
- **Changes made:**
  - `sitrep_direction.differences` loads the retained baseline first; a baseline that is not `ok` is `baseline_unreadable` whatever the digests say. The worker always calls it, and the parent prints `RECHECK_SAME` only for an equal digest with no reason.
  - The proposal worker refuses a `next: c<N>` that names no item (`BADREQ`, exit 2), before any snapshot is built or retained.
  - `RefreshReport.verdict()` appends the direction part on the `REFRESH_NONE` line too (`_directions_text`).
  - Both workers write their temp files under a directory the parent owns and removes: the direction worker sets `tempfile.tempdir` and `TMPDIR` to its `--out`; the item worker runs with `TMPDIR` set to a run directory created by `cmd_run`.
  - `_dworker_refresh` passes the member ids it already has to `snapshot_for`.
  - Tests: `Verdicts.test_an_equal_digest_does_not_authorize_a_save_over_an_unusable_baseline`; Test 22 (a damaged baseline with equal digests, a `next` item that does not exist, with its control); Tests 20 and 22 run their stalled fetch under a private `TMPDIR` and assert it is empty; `test_no_item_target_still_shows_what_happened_to_the_directions`.
  - Three more mutants, all killed: the baseline check moved behind the digest comparison, the `next` existence check removed, the worker's temp directory lines removed (leaves `ait_trail_<x>.json`).
  - The header of `aitask_sitrep_refresh.sh` and "Saving a proposal" in `aidocs/framework/sitrep.md` state the rules.
- **Files affected:** `.aitask-scripts/lib/sitrep_direction.py`, `.aitask-scripts/lib/sitrep_refresh.py`, `.aitask-scripts/sitrep_tui/sitrep_tui_model.py`, `.aitask-scripts/aitask_sitrep_refresh.sh`, `aidocs/framework/sitrep.md`, `tests/test_sitrep_direction.py`, `tests/test_sitrep_refresh.sh`, `tests/test_sitrep_tui_actions.py`

### Change Request 2 (2026-11-25 16:40)
- **Requested by user:** the parent-owned temp directory is removed in the parent's `finally`, which does not run when an external caller kills the parent itself; the run directory and the nested artifact file then stay. Confirmed.
- **Changes made:** run directories are named `ait_sitrep_tmp_<parent pid>_<random>` (`make_run_dir`), and every run and proposal verb first calls `reclaim_run_dirs`, which removes a directory only when its name matches, it is a real directory owned by this user, and its owner pid names no process, or it is older than `TMP_MAX_AGE` (the largest budget plus an hour). A live owner's directory, a symlink and any other name are never touched. Tests: `RunDirectories` (three unit cases), and Test 20 (c): the parent is killed with SIGKILL during a stalled fetch, the directory stays (control), and the next run leaves `TMPDIR` empty.
- **Files affected:** `.aitask-scripts/lib/sitrep_refresh.py`, `.aitask-scripts/aitask_sitrep_refresh.sh`, `tests/test_sitrep_refresh.py`, `tests/test_sitrep_refresh.sh`

### Change Request 3 (2026-11-25 17:05)
- **Requested by user:** two concerns on the reclaim of Change Request 2, both confirmed. (1) The age clause removed a directory whose recorded pid was still alive; a timestamp cannot prove an owner stopped, and the unit test expected that deletion. (2) The sweep ran before the `--dry-run` check and in `recheck`, so two read-only commands deleted a pre-existing directory.
- **Changes made:** `reclaim_run_dirs` removes a directory only when its owner pid provably names no process (`TMP_MAX_AGE` and the age clause are gone; a pid that cannot be signalled is not "gone"). It is called only by a refresh run without `--dry-run` and by `snapshot`. Tests: the unit case now keeps a ten-year-old directory with a live owner, with its file; Test 20 (c) shows `--dry-run` and a passing `recheck` leaving the abandoned directory in place, a writing run removing it while keeping an aged directory whose owner is alive, and `snapshot` removing that one once its owner is gone.
- **Files affected:** `.aitask-scripts/lib/sitrep_refresh.py`, `.aitask-scripts/aitask_sitrep_refresh.sh`, `tests/test_sitrep_refresh.py`, `tests/test_sitrep_refresh.sh`

### Change Request 4 (2026-11-25 17:35)
- **Requested by user:** two concerns on the reclaim, both confirmed. (1) `kill(pid, 0)` answering "no such process" is no proof of death: with two pid namespaces sharing one temp directory, one deleted the other's live run directory. (2) A name carrying a ten-digit pid above the platform's range raised an uncaught `OverflowError` and ended a normal refresh before any result line.
- **Changes made:** ownership is proven by a lock. `make_run_dir` creates `ait_sitrep_tmp_<random>` (no pid in the name), creates the lock file under another name, takes an exclusive `flock` on it and only then renames it to `.owner.lock`, so a visible lock file is always already held; the parent keeps the fd until `remove_run_dir`. `reclaim_run_dirs` removes a directory only when it can take that lock itself, and removes the tree while holding it. A held lock, a missing lock file, a lock that is not a regular file, a symlink and any error keep the directory; each entry is handled in its own `try`, so one bad entry cannot stop the sweep or the run. No pid and no age is consulted. Tests: `RunDirectories` (a directory held by another process is kept, also when ten years old, and is reclaimed once that process is killed; no lock file, a lock that is a directory or a symlink, and `ait_sitrep_tmp_9999999999_fixture` are kept); Test 20 (c) with a lock-holding process and the out-of-range name, asserting that the run still exits 0 and prints its result. Mutant: the sweep without the `flock` call removes the live holder's directory and `RunDirectories` fails.
- **Files affected:** `.aitask-scripts/lib/sitrep_refresh.py`, `.aitask-scripts/aitask_sitrep_refresh.sh`, `tests/test_sitrep_refresh.py`, `tests/test_sitrep_refresh.sh`

## Final Implementation Notes

- **Actual work done:** All six plan steps and both post-phase checks, plus four review rounds (see "Post-Review Changes").
  - New `lib/sitrep_direction.py`: the snapshot values, `Reader` (one fetch per trail: hash and drift verdict from the same bytes), `build_snapshot` / `snapshot_for`, `classify`, `evidence` + `verdict` (three evidence parts collected separately, then combined), `differences` for the recheck, `parse_proposal`.
  - `lib/sitrep_refresh.py`: `_drift_output` with its two readers (`run_drift` unchanged in output, `drift_facts`), `load_trail`, the direction worker (`dworker`, modes refresh / snapshot / recheck), `DirectionStream`, `proposal_complete`, `direction_phase` (phase 2 of every run), `cmd_proposal`, the ledger's `directions` map, run directories with an owner lock.
  - `lib/sitrep_todo.py`: `direction_stamp` also hashes the item a `next: c<N>` points at.
  - `aitask_sitrep_refresh.sh`: the `snapshot` / `recheck` words and the wire contract in the header.
  - TUI: `RefreshReport` reads the direction lines; `partial` and `verdict()` include them, also on the `REFRESH_NONE` line.
  - Docs: "The freshness verdict" and the proposal verbs in `aidocs/framework/sitrep.md`; the re-check line in the website's sitrep reference.
  - Tests: new `tests/test_sitrep_direction.py` (35 tests); `tests/test_sitrep_refresh.py` 102 to 117 tests; `tests/test_sitrep_refresh.sh` 197 to 389 assertions (Tests 17 to 22); `tests/test_sitrep_todo.sh` 675 to 684; `tests/test_sitrep_todo_format.py` 83 to 84; `tests/test_sitrep_tui_actions.py` 78 to 81.
- **Deviations from plan:**
  - Phase 2 was wired into `cmd_run` before the `DirectionStream` unit tests were written, not after as "Order of work" said. It was checked at once with a `--dry-run` on the live store, and the unit tests followed in the next step. The live store has no direction record, so nothing could be written.
  - `evidence` takes the snapshot (which carries `all_members` and `trail_codes`) instead of separate arguments.
  - `drift_facts` returns an empty code when the helper's first `DRIFT:` code is not in the store's code grammar; the `trail_stale` key is then the handle.
  - The proposal worker reports a per-direction exception as `DERROR:` (no result, so the run is incomplete) and a bad request as `BADREQ:` (exit 2).
  - The direction batch log seam writes to `<AITASK_SITREP_REFRESH_BATCH_LOG>.directions`.
  - Test 19 (d) saves the baseline while version A is current and then makes A stale, which is the case the review concern describes; the plan sentence said "saved over version A, which is stale".
  - The oversized store of Test 19 (e) is rendered by the store's own model and installed whole (1100 items through the writer one by one would take minutes). It is verified with `verify todo` before use.
  - Run directories and their reclaim (Change Requests 1 to 4) were not in the plan.
- **Issues encountered:**
  - `tests/test_sitrep_tui_actions.py` had one error (`RestoreTests.test_pre_fix_control_the_unconditional_verb_rolls_it_back`, `NoMatches '#rd-close'`) in the baseline run taken BEFORE any edit, while five suites ran one after another under load from the background jobs. It passes when run alone, before and after the change (81 tests OK). Not caused by this task.
  - Under the test suite's scratch `HOME`, plain `python3` resolves to a wrapper that needs the real venv; the in-test Python calls use `$AIT_PYTHON`.
  - The first version of the mutant harness read the last output line for `OK`; `tests/test_sitrep_refresh.py` prints a line after it. The checker now looks for an `OK` line anywhere. The first `stamp_from_the_snapshot` mutant was itself broken (a doubled backslash put a literal `\n` in the batch) and failed the control case; it was corrected and re-run.
- **Key decisions:**
  - A trail's version is the first 12 hex of its content hash; the value is `<hash>:current|stale`.
  - `unreadable` is a snapshot value, never a gap; `unknown` is decided from the inputs as they are now, whatever the digests say.
  - `checked_at` of a direction means "verdict last changed"; an equal verdict sends no batch line.
  - The recheck authorizes a save only when the digest is equal AND the retained baseline loads as `ok`.
  - Ownership of a run directory is proven by a held `flock`, never by a pid or an age; only writing commands sweep.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t2335_4: draft with `aitask_sitrep_refresh.sh snapshot` (stdin `<slug>|<members>|<trails>|<next>`, `=` as stored, `-` none), read the retained `baselines/<digest>.txt`, and run `recheck` (the same lines plus `|<digest>`) before the first write; write only after exit 0. `SNAPSHOT_UNREADABLE:` lines name inputs whose value is `unreadable`: the summary can be saved, and the direction reads `unknown` until they can be read. A proposed `next: c<N>` must exist. The skill's permission touchpoints for `aitask_sitrep_refresh.sh` are owed when it first calls the script.
  - t2335_5: `RefreshReport.directions` holds `<slug>|<old>-><new>|<result>|<drift>`, `.direction_counts` the `REFRESH_DIRECTIONS` pairs, `.unassigned` the count. An `unknown` verdict can carry several reasons. A direction with no block is reported `no_record` by the refresh and has nothing stored; derive its row from `st.known_directions`.
  - The stamp (`st.direction_stamp`) now also covers the `next` item.
  - Test helpers worth reusing (`tests/test_sitrep_refresh.sh`, above Test 17): `dart.sh` (fake artifact CLI with a repoint and a stall switch), `dgather.sh` (a drift stub that resolves `art:` handles as the real wrapper does), `save_summary`, `assign`, `qitem`.

### Post-phase evidence: live_item_output_parity

```
before the first edit:  ./.aitask-scripts/aitask_sitrep_refresh.sh --dry-run > live_dry_before.txt   (54 lines)
                        git archive HEAD .aitask-scripts | tar -x -C <scratch>/old                    (HEAD 95d0169d8)
after step 2:           the same dry run; legacy lines (all but REFRESH_UNASSIGNED / REFRESH_DIRECTION*) diffed
  < REFRESH_ITEM:c194|task|open->done|dry_run|archived (completed 2026-11-25)
  < REFRESHED:checked=53|changed=1|stale=0|kept=0|unknown=3
  > REFRESHED:checked=52|changed=0|stale=0|kept=0|unknown=3
  explained: the monitor's own refresh closed c194 at 2026-11-25T13:45:25Z, so it is no longer a target
  (list --machine: ITEM:c194|...|task|done|...|archived (completed 2026-11-25)). Every other line is identical.

scratch store A (13 targets, no direction; old writer; both .aitask-scripts copies carry the SAME drift stub):
  targets: tasks Ready / Implementing / Done / archived / missing / unresolved cross-repo, one push,
           trails with drift CURRENT, STALE with three DRIFT lines, a non-zero exit, empty output, ERROR: with exit 0, an unreadable trail
  old stdout: ... drift CURRENT ... drift STALE (3) ... drift unavailable ... drift unavailable ... drift error ...
              REFRESHED:checked=13|changed=13|stale=0|kept=0|unknown=9
  check 1  grep -v '^REFRESH_UNASSIGNED:' out_new | cmp - out_old   -> LEGACY_STDOUT: byte-identical
           cmp root_old/.aitask-sitrep/todo.md root_new/...          -> TODO_MD: byte-identical
  check 2  diff out_old out_new                                      -> 13a14 > REFRESH_UNASSIGNED:13
           directions (new store): UNASSIGNED:13; the line sits directly before the final line

scratch store B (two recovery items made by the old detector; t51's lock removed and its task set Ready in both copies):
  old stdout: REFRESH_ITEM:c1|recovery|open->open|unchanged|crashed ...
              REFRESH_ITEM:c2|recovery|open->done|applied|recovered · recovered: Ready
              REFRESHED:checked=2|changed=1|stale=0|kept=0|unknown=0
  new adds:   REFRESH_UNASSIGNED:0
              REFRESH_DIRECTION:crashed-agents|unknown->stale|no_record|never_summarized:1
              REFRESH_DIRECTIONS:checked=1|changed=0|unknown=0|refused=0
  legacy stdout byte-identical; todo.md byte-identical
```

### Post-phase evidence: verdict_guard_mutants

Each mutant is one edit in a scratch copy of `.aitask-scripts/` with the tests copied beside it; the working tree is never touched. Control (no edit): the unit files pass and `ONLY="17 19 20 21 22"` gives 127 passed, 0 failed.

| Mutant (the guard removed) | A failing assertion that names it |
|---|---|
| an unreadable input is `unknown` | Test 19: "equal digests over an unreadable trail are unknown, never current" (got `unknown->current`) |
| the baseline status is `unknown` | Test 19: "a damaged baseline is unknown with baseline_unreadable" (got `current`) |
| the size limit is `unknown` | `Verdicts.test_oversized_snapshot_is_unknown`; Test 19: "with baseline_too_large, beside the other reasons" |
| `unknown` keeps every reason | Test 19: "no digest and an unreadable trail: unknown with both reasons" |
| the drift helper reads the fetched bytes | Test 19: "a handle repointed between reads" (got `current`), "exactly one fetch" (got 2) |
| the `next` item in the stamp | Test 21: "the closure of a next item that is not a member -> the line is refused as stale" (got `applied`) |
| the unchanged-verdict skip | Test 17: "a second run reports it unchanged" (got `applied`), "keeps the rev" |
| the batch stamp is the snapshot's (mutant: re-read at write time) | Test 21: "a member's set-state -> the line is refused as stale" (got `applied`); the control case still passes |
| the interrupted direction is written `unknown` | Test 20: "the interrupted direction is written unknown" |
| the completeness rule | Test 22: "a recheck cut short", "never 'same'" (got `RECHECK:same`, exit 0) |
| the recheck loads the baseline before comparing digests (CR 1) | Test 22: "a damaged baseline fails the recheck although the digests are equal" (got exit 0) |
| a proposed `next` item must exist (CR 1) | Test 22: "snapshot with a next item that does not exist -> exit 2" (got 0) |
| the worker's temp files under the parent's directory (CR 1) | Test 20: "the killed fetch leaves no temp file behind" (got `ait_trail_rtzh3j5e.json`) |
| the sweep takes the owner lock (CR 4) | `RunDirectories.test_only_a_directory_whose_lock_can_be_taken_goes` |

The harness, verbatim as finally run (`bash mutants.sh <repo root> <scratch dir>`; the last three mutants were run after Change Request 1; the lock mutant of Change Request 4 removed the one `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` line of `reclaim_run_dirs` in a copy and ran `tests/test_sitrep_refresh.py RunDirectories`):

```bash
#!/usr/bin/env bash
# verdict_guard_mutants (t2335_2): remove one guard at a time in a SCRATCH COPY
# of the tree and run the tests that name it. Never touches the working tree.
# Usage: mutants.sh <repo root> <scratch dir>
set -uo pipefail
REPO="$1"
WORK="$2"
rm -rf "$WORK"
mkdir -p "$WORK/base/aidocs" "$WORK/base/tests"
cp -a "$REPO/.aitask-scripts" "$WORK/base/.aitask-scripts"
cp -a "$REPO/aidocs/implementation_trail_examples" "$WORK/base/aidocs/"
cp -a "$REPO/tests/lib" "$REPO/tests/fixtures" "$WORK/base/tests/"
cp "$REPO/tests/test_sitrep_refresh.sh" "$REPO/tests/test_sitrep_refresh.py" \
   "$REPO/tests/test_sitrep_direction.py" "$REPO/tests/test_sitrep_todo_format.py" \
   "$WORK/base/tests/"
find "$WORK/base" -name __pycache__ -type d -prune -exec rm -rf {} +

# run_tests <tree> <label> <only> <py spec...>: prints the failing lines.
run_tests() {
    local tree="$1" label="$2" only="$3" spec fails=0 out
    shift 3
    for spec in "$@"; do
        out="$(cd "$tree" && python3 tests/${spec%% *} ${spec#* } 2>&1)"
        if ! printf '%s\n' "$out" | grep -q '^OK'; then
            fails=$((fails + 1))
            printf '%s\n' "$out" | grep -E '^(FAIL|ERROR): ' | sed "s/^/    [$label] py  /" | head -4
        fi
    done
    if [[ -n "$only" ]]; then
        out="$(cd "$tree" && ONLY="$only" bash tests/test_sitrep_refresh.sh 2>&1)"
        if ! printf '%s\n' "$out" | grep -q '^ALL TESTS PASSED'; then
            fails=$((fails + 1))
            printf '%s\n' "$out" | grep '^FAIL' | cut -c1-230 | sed "s/^/    [$label] sh  /" | head -4
        fi
        printf '%s\n' "$out" | grep '^Results:' | sed "s/^/    [$label] sh  /"
    fi
    return "$fails"
}

echo "=== CONTROL (no mutation): every named test passes ==="
run_tests "$WORK/base" control "17 19 20 21 22" \
    "test_sitrep_direction.py -q" "test_sitrep_refresh.py -q" "test_sitrep_todo_format.py -q"
echo "    control failing groups: $?"

# mutant <name> <only> <py specs (;-separated)> <python patch expr>
mutant() {
    local name="$1" only="$2" specs="$3" patch="$4" tree="$WORK/$1" rc
    rm -rf "$tree"
    cp -a "$WORK/base" "$tree"
    if ! python3 - "$tree" <<PYEOF
import sys
tree = sys.argv[1]
def sub(rel, old, new):
    p = tree + "/.aitask-scripts/" + rel
    s = open(p, encoding="utf-8").read()
    assert s.count(old) == 1, (rel, s.count(old), old[:60])
    open(p, "w", encoding="utf-8").write(s.replace(old, new))
$patch
PYEOF
    then echo "=== MUTANT $name: PATCH DID NOT APPLY ==="; return; fi
    echo "=== MUTANT $name ==="
    local IFS=';'
    # shellcheck disable=SC2086
    set -- $specs
    unset IFS
    run_tests "$tree" "$name" "$only" "$@"
    rc=$?
    if [[ $rc -gt 0 ]]; then echo "    -> KILLED ($rc failing group(s))"; else echo "    -> SURVIVED"; fi
    rm -rf "$tree"
}

mutant unreadable_is_unknown "19" "test_sitrep_direction.py -q Verdicts" '
sub("lib/sitrep_direction.py",
    """    for kind, key in snap.unreadable:
        ev.unread.append(("trail_unreadable" if kind == "trail" else "task_unreadable", key))
""", "")'

mutant baseline_status_is_unknown "19" "test_sitrep_direction.py -q Verdicts" '
sub("lib/sitrep_direction.py",
    """            baseline = None
            ev.unread.append(("baseline_unreadable", ""))
""", """            baseline = None
""")'

mutant size_limit_is_unknown "19" "test_sitrep_direction.py -q Verdicts" '
sub("lib/sitrep_direction.py",
    """    if snap.too_large:
        ev.unread.append(("baseline_too_large", ""))
""", "")'

mutant unknown_keeps_all_reasons "19" "test_sitrep_direction.py -q Verdicts" '
sub("lib/sitrep_direction.py",
    """        pairs = ([("never_summarized", "")] if ev.never else []) + ev.unread + ev.classified
""", """        pairs = ev.unread
""")'

mutant drift_reads_fetched_bytes "19" "test_sitrep_direction.py -q TrailValues" '
sub("lib/sitrep_direction.py",
    """        state, code = self._drift_facts(self.checker.root, path)
""", """        state, code = self._drift_facts(self.checker.root, handle)
""")'

mutant next_item_in_stamp "21" "test_sitrep_todo_format.py -q DirectionMembership" '
sub("lib/sitrep_todo.py",
    """    if m:
        item = store.items.get(int(m.group(1)))
        lines.append(f"next:c{m.group(1)}@{item.rev if item is not None else \x27-\x27}")
""", "")'

mutant unchanged_verdict_skip "17" "" '
sub("lib/sitrep_refresh.py",
    """            elif (ln.state, ln.drift) == (ln.old_fresh, ln.old_drift):
""", """            elif False:
""")'

mutant stamp_from_the_snapshot "21" "" '
sub("lib/sitrep_refresh.py",
    """            _pause("refresh:before_direction_write", var)
""", """            _pause("refresh:before_direction_write", var)
            _now = st.load_todo_for_read(os.path.join(root, STORE_NAME))
            batch = "".join(
                f"{ln.slug}|{_now.directions[ln.slug].rev}|"
                f"{st.direction_stamp(_now, ln.slug)}|{ln.state}|{ts}|{ln.drift}" + chr(10)
                for ln in written)
""")'

mutant interrupted_is_unknown "20" "test_sitrep_refresh.py -q DirectionStreamTests" '
sub("lib/sitrep_refresh.py",
    """            ln.interrupted = True
            out.append(ln)
        return out


def proposal_complete""", """            ln.interrupted = True
        return out


def proposal_complete""")'

mutant completeness_rule "22" "test_sitrep_refresh.py -q ProposalCompleteness" '
sub("lib/sitrep_refresh.py",
    """    complete = (rc == 0 and not interrupted and stream.open is None
                and not stream.failed and not stream.none
                and sorted(got) == sorted(requested))
""", """    complete = True
""")'
mutant recheck_validates_the_baseline "22" "test_sitrep_direction.py -q Verdicts" '
sub("lib/sitrep_direction.py",
    """    status, baseline = load(store_dir, digest, slug)
    if status != "ok":
        return reasons([("baseline_unreadable", "")])
    if snap.digest == digest:
        return []
""", """    if snap.digest == digest:
        return []
    status, baseline = load(store_dir, digest, slug)
    if status != "ok":
        return reasons([("baseline_unreadable", "")])
""")'

mutant proposed_next_item_exists "22" "" '
sub("lib/sitrep_refresh.py",
    """            if m and int(m.group(1)) not in store.items:
                raise st.RequestError(f"direction {p.slug}: next {p.next} names no item")
""", "")'

mutant worker_temp_files_owned_by_parent "20" "" '
sub("lib/sitrep_refresh.py",
    """    tempfile.tempdir = args.out
    os.environ["TMPDIR"] = args.out
""", "")'
echo "=== done ==="
```
