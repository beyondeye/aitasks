---
Task: t2175_3_sitrep_deterministic_refresh_of_todo_part1.md
Parent Task: aitasks/t2175_sitrep_repo_todo_list_steward.md
Sibling Tasks: aitasks/t2175/t2175_4_*.md, aitasks/t2175/t2175_5_*.md, aitasks/t2175/t2175_6_*.md
Archived Sibling Plans: aiplans/archived/p2175/p2175_*_*.md
Base branch: main
Output branch: main
---

# t2175_3 — Sitrep: deterministic refresh of Part 1

## Context

Sitrep (t2175) keeps one persisted todo list per repo (`.aitask-sitrep/todo.md`)
so finished agent windows can be closed. t2175_1 built the only writer
(`.aitask-scripts/aitask_sitrep_todo.sh` + `lib/sitrep_todo.py`, CAS by
store-wide `rev`, contract fixture `tests/fixtures/sitrep/`). t2175_2 fills the
store from finished agents (`aitask_sitrep_harvest.sh` + `lib/sitrep_harvest.py`).
Today an item's state is whatever harvest wrote. Nothing re-checks it, so
"t2181 open" stays open after t2181 is archived. This task adds the
**deterministic refresh**. It re-checks every open/unknown item it knows how to
verify against the real state and writes the results back through
`set-state --batch` (Part 1 only, CAS on the observed rev). It runs on the
monitor maintenance tick and on demand.

Decisions settled with the user (2026-11-03):
- **Push items get a structured ref** `push:<branch>@<sha>` (writer grammar
  extension, todo `format=2`, and `format=1` files stay readable). The sitrep
  skill (t2175_4) creates them; refresh checks them with git, without fetching.
- **The monitor wiring lives here**: a refresh job in the monitor's trailing
  maintenance. t2175_5 later adds harvest `all` beside it.
- **A picked task stays open**: a task item is `open` while its task is
  Ready/Editing/Implementing/Postponed (the outcome shows the live status). It
  becomes `done` only on Done/archived or Folded. Done items are never re-checked.

Plan review round 1 (four concerns, all verified in the code and addressed below):
- **Trail completion**: the board counts an entry as landed only when its status
  is `Done` (`board/board_trail_view.py:316,324`), and `trail_gather` reports
  folding as `task_folded` drift (`lib/trail_gather.py:1370-1377`). So a folded
  trail entry is landed only when the task it was merged into is Done. The task
  item's own reminder still closes on Folded (settled).
- **Context concurrency**: `op_upsert_context` (`lib/sitrep_todo.py:1094`)
  replaces a context without a new rev, so a refresh verdict computed from the
  old trail source would pass CAS. A changed context now takes a fresh item rev.
- **Push evidence**: `@{upstream}` can be local (`branch.<b>.remote=.`).
  Completion now requires the push destination to be a remote-tracking ref of a
  configured remote with a URL.
- **Refresh deadlines**: one shared deadline covers the checks and the write,
  and the remaining time is propagated into every subprocess. The caller timeout
  is derived from the same budget.

Plan review round 2 (three concerns, all verified and addressed below):
- **Push destination identity**: `refs/remotes/<r>/*` records the fetch
  endpoint, and `remote.<r>.pushurl` can name a different one, so the
  ancestry check could pass against a repo the push never reaches. Done now
  requires the push URL set to be exactly the single fetch URL (after
  `insteadOf`/`pushInsteadOf` expansion); anything else → `unknown`.
- **Deadline bypasses**: `archive_iter._iter_single_archive` runs `zstd`
  through `Popen` with an unbounded `wait()` (`lib/archive_iter.py:375,403`),
  and `sitrep_harvest._git` / `resolve_project` use fixed 20 s timeouts. All
  slow work therefore moves into a **killable worker process group**. The
  parent alone owns the deadline and kills the whole group, using the
  `agent_freeze.py:1576-1584` `start_new_session` + `killpg` pattern. Reused
  helpers run unchanged inside the worker and are bounded by the kill.
- **Budget starvation**: targets are checked oldest-`checked_at`-first, and the
  one target interrupted by the deadline is stamped `unknown`, so every run
  makes progress and an expensive item rotates to the back.

Plan review round 3 (verified, addressed): the parent had no CAS token for a
target interrupted between `START:` and `VERDICT:`. Now `START:` carries the
snapshot rev and reporting fields, and a test interrupts before the first
VERDICT with concurrent item and context edits.

Advisory notes consumed (t2175_2 → this task, acknowledged): harvested task
items are `derived=script`, `checked_at` = harvest time, `state=unknown` when
the file was not found (cross-repo titles say "(cross-repo, unverified)").
Triage items (`kind=question`) are NOT refresh targets. Trail items are
`kind=watch`, with a `trail: art:trail-<id>` context source and no ref.

## Design

### Targets (exhaustive; everything else is left byte-identical, not stamped)
Only items with `state ∈ {open, unknown}` (done and dismissed are never
re-checked or written):

| item | check |
|---|---|
| `kind=task`, ref `t<N>[_<M>]` | local task lookup in the canonical root |
| `kind=task`, ref `<proj>#<N>[_<M>]` | `aitask_projects.sh resolve <proj>` → same lookup in that root; unresolved → `unknown` |
| `kind=action`, ref `push:<branch>@<sha>` | git, in the canonical root |
| `kind=watch` with exactly one `trail: art:trail-…` context source | trail check |

`kind=question`, agent action/watch items without one of these anchors, and
items with no ref are not targets. "Unverifiable ⇒ unknown" applies to a
**target whose check could not complete**, never to items refresh has no rule
for. That rule is what keeps agent-derived "deploy dev" items untouched.

### Evidence rules (positive evidence only; `done` is irreversible)
**Task lookup** follows the fail-closed shape of `trail_links.lookup_task_meta`
(.aitask-scripts/lib/trail_links.py:165), rooted at an explicit root. The active
file wins over the archived one, and any listing or bundle error means absence
is not proven. It reuses `archive_iter.checked_glob`,
`archive_iter.find_archived_markdown_by_id` (loose, numbered `_bN/oldM.tar.zst`
and legacy bundles) and `task_yaml.parse_frontmatter`.
- active, status Ready/Editing/Implementing/Postponed (any other non-terminal
  status) → `open`, outcome `status: <S>`
- active, status `Done` → `done`, `status: Done (not yet archived)`
- active or archived, status `Folded` → `done`, `folded into t<folded_into>` (or `folded`)
- archived, status `Done` → `done`, `archived (completed <completed_at date>)`
- archived with any other status → `unknown`, `archived with status <S>`
- unparseable frontmatter / read error / lookup error → `unknown`, `lookup failed: <first error>`
- not found anywhere → one lazy **fold scan** per run (active frontmatter +
  `archive_iter.iter_archived_frontmatter` over every bundle) for a task whose
  `folded_tasks` lists the id → `done`, `folded into t<N>`. A scan error →
  `unknown`. Otherwise `unknown`, `task file not found`.
- cross-repo outcomes are prefixed `<proj>: `. An unresolved project gives
  `unknown`, `cross-repo: project <proj> not resolved`.
- The Folded outcomes name the receiving task's live state when it resolves
  (`folded into t30 (t30: Ready)`). The reminder is `done` either way (settled:
  the folded task's own item closes).

The lookup returns a structured `TaskFacts(found=active|archived|fold_scan|missing|error,
status, folded_into, receiver, detail)`. Two verdict functions read it:
`reminder_verdict` (task items, the rules above) and `landed_state` (trail
entries, below). They never share a "done" shortcut.

**Push** (`push:<branch>@<sha>`): no fetch, no network. All git goes through
one helper with a 20 s timeout and `GIT_TERMINAL_PROMPT=0`, run in the
canonical root.
- not a git work tree → `unknown`, `not a git repository`
- `rev-parse --verify --quiet <sha>^{commit}` fails → `unknown`, `commit <sha7> not in this repository`
- **Destination = where `git push` from `<branch>` would land**:
  `rev-parse --symbolic-full-name <branch>@{push}`. It must be
  `refs/remotes/<r>/<x>` where `<r>` is a configured remote
  (`git remote` lists it, `<r>` is not `.`) with a non-empty
  `remote.<r>.url` (or `pushurl`). Everything else → `unknown`, `no remote push
  destination for <branch>`. That covers: no upstream, a local upstream
  (`branch.<b>.remote=.` resolves to `refs/heads/…`), a remote name without a
  URL, or a `@{push}` that does not resolve.
- **The cached ref must describe the endpoint the push goes to.**
  `git remote get-url --all <r>` (fetch URLs, `insteadOf` applied) must
  give exactly one URL, and `git remote get-url --push --all <r>` (push URLs,
  `pushInsteadOf`/`pushurl` applied) must give exactly that same single URL.
  Several fetch or push URLs, or a push URL that differs →
  `unknown`, `push URL differs from fetch URL (<r>); not verifiable without network`.
  Without a network round-trip, a remote-tracking ref is evidence only for
  the fetch endpoint.
- `merge-base --is-ancestor <sha> <dest>` rc 0 → `done`,
  `pushed: <sha7> is on <r>/<x>`; rc 1 → `open`,
  `not pushed: <branch> <a> ahead / <b> behind <r>/<x> (fetched <date|never>)`
  from `rev-list --left-right --count <branch>...<dest>` and the
  `FETCH_HEAD` mtime under `--git-common-dir`; any other rc → `unknown`.
- The branch value is used only after `git check-ref-format --branch` accepts
  it, and always as an argv element, never through a shell.

**Trail** (`art:trail-<id>` handle; cwd = canonical root, as the artifact CLI
requires):
- blob: `trail_discovery.load_trail_blob(handle)` (fail-closed, read-only),
  reused unchanged inside the worker; the group kill bounds its fixed 15 s
  timeouts. The artifact CLI it spawns is
  `trail_discovery.ARTIFACT_SCRIPT`, which the e2e test overrides through the
  seam `AITASK_SITREP_REFRESH_ARTIFACT_SH` (the worker rebinds the module
  attribute). An error → `unknown`, `trail unreadable: <error>`.
- each entry `<proj>#<id>`: local project (`trail_gather.local_project_name()`)
  → task lookup above; another project → resolve + lookup. `landed_state`,
  matching the board (landed ⇔ the work is Done):
  - status `Done` (active or archived) → landed
  - Folded (active file, or deleted and found by the fold scan) → follow the
    receiver: `folded_into`, or for a scan hit the task listing it in
    `folded_tasks`. Up to 5 hops, with cycle detection. The entry is landed
    only when the final receiver is Done. A receiver in
    Ready/Editing/Implementing/Postponed → open, shown as
    `t12→t30`. A missing, cyclic, too-deep or unreadable receiver → unverifiable.
  - any other active status → open; missing / error → unverifiable
- next wave = the lowest-ordinal wave with any entry that has not landed.
  State: every entry landed → `done` (`all <W> waves landed`); any entry
  open → `open`; otherwise `unknown`.
- outcome (only reported facts, nothing guessed):
  `next wave <k>/<W> <title> (<n> open: t12,t13,…) · drift <CURRENT|STALE (<r>)|error|unavailable> · generated <YYYY-MM-DD> · owner t<id> <status>`.
  Drift comes from the read-only `aitask_trail_gather.sh drift --trail <handle>`
  (15 s, the board's `run_trail_drift` parse). Drift never decides state.
- More than one trail source on one item → `unknown`, `several trail sources`.

**Outcome hygiene:** every outcome is one line, `|` → `/`, control characters
removed, and it is truncated to `sitrep_todo.MAX_OUTCOME` (200) at a field
boundary, with list members dropped first and a trailing `…`. Pure function,
unit-tested.

### Concurrency, budget, failure
- Read: `sitrep_todo.load_todo_for_read(store)` (no lock; the atomic rename
  gives a whole snapshot) → items with rev plus contexts (for trail pointers).
- Compute every check, then ONE writer call: `set-state --batch` lines
  `c<N>|<observed rev>|<state>|<run ts>|<outcome>`. `STALE:` (agent changed
  the item) and `KEPT:` (dismissed meanwhile) are counted and never retried; the
  next tick re-reads. Two concurrent refreshes are safe by the same CAS. No
  refresh mutex.
- **The observed rev covers every input a verdict reads**: kind and ref
  (`update` already takes a fresh rev), state (`set-state` / `dismiss`), and the
  context's `trail:` sources. For the context, `upsert-context` now takes a
  fresh item rev whenever it creates or replaces an entry (an `unchanged`
  result takes none). So a trail source swapped while refresh is computing
  makes the batch line `STALE:`.
- `checked_at` = one run timestamp taken before the first check
  (`sitrep_todo.now_ts()`, so `AITASK_SITREP_NOW` pins it). Every target line
  is stamped every run (so every refresh with targets is one write and one
  backup roll).
- **Two processes: the parent owns the deadline, the worker does the slow work.**
  `--budget <s>` (default 60; fallback env `AITASK_SITREP_REFRESH_BUDGET`) sets
  one deadline covering everything. The checks must finish by
  `budget − reserve`, with `reserve = min(15, budget/4)` kept for the writer.
  - The **parent** (`sitrep_refresh.py run`) does no filesystem scan, git or
    helper call itself. It spawns the **worker** (`sitrep_refresh.py worker`)
    with `start_new_session=True`, stdin/stdout pipes and stderr to a temp
    file. It reads the worker's line stream with `selectors` until EOF or the
    check deadline. At the deadline it sends `os.killpg(pgid, SIGKILL)` (the
    `agent_freeze.py:1576-1584` pattern), reaps, and closes the pipes.
    Every grandchild (zstd, git, artifact CLI, project resolver) is in that
    group, so no reused helper can overrun.
  - The **worker** does everything slow, in order: `canonical_root`, the store
    check, the snapshot, target selection and the checks. It reuses
    `sitrep_harvest.canonical_root` / `resolve_project`, `archive_iter`,
    `trail_discovery` and `trail_gather` unchanged (their own fixed caps
    remain as caps). It streams one line per event, each flushed:
    `ROOT:<root>` (whole remainder), `NONE:no_store|no_targets`,
    `TARGETS:<n>`,
    `START:c<N>|<snapshot rev>|<kind>|<old state>|<old outcome>` (old outcome
    LAST; the writer forbids `|` in outcomes), then
    `VERDICT:c<N>|<new state>|<outcome>` (outcome LAST), or `FAILED:<reason>`.
    **START carries everything the parent needs to write the line**, which is
    the snapshot rev (the CAS token) plus the reporting fields. So an item
    interrupted before its VERDICT is written with the rev the worker observed
    in its snapshot, never a re-read one. The parent accepts a `VERDICT` only
    for the currently open `START` id, and a `START` only when no other is open.
    Anything else is a protocol error → `REFRESH_FAILED:worker_protocol`,
    nothing written.
  - A worker killed before `ROOT:` → `REFRESH_FAILED:deadline` (nothing
    written). Verdicts received before the kill are kept.
  - **Interrupted target**: the target with a `START:` but no `VERDICT:` at the
    kill is written `unknown`, `check did not finish within the <b>s budget`.
    It could not complete, so it is unverifiable, and stamping it rotates it
    to the back (see Ordering). Targets never started are left unwritten
    (`REFRESH_WARN:budget_exhausted|<n> not reached`).
  - A check stopped by its **own cap** (inside the worker) → `unknown`,
    `timed out`.
  - The writer (`set-state --batch`) runs from the parent with
    `timeout = time left until the run deadline` and
    `AITASK_SITREP_LOCK_TIMEOUT = clamp(time left − 3, 1, 10)`, so the lock wait
    leaves time for the write itself. Lock busy → `REFRESH_FAILED:lock_busy`
    before the deadline.
- **Ordering (progress across runs).** The worker checks targets in ascending
  `checked_at` (`never` first, then the oldest ISO stamp), ties by id. Every
  reached target, finished or interrupted, gets the run stamp. So the next run
  starts with the targets this one did not reach, and k-per-run progress means
  every target is checked within ⌈targets / k⌉ runs. An item that is always
  expensive is re-checked once per rotation and shows `unknown` with the
  budget reason, instead of blocking everything behind it. A `STALE:` line is
  not stamped, so the item stays early and is retried next tick.
  - A run killed before the batch writes nothing. The writer is crash-safe by
    design (old or new generation; a dead-PID lock is stolen next time).
  - **Caller contract:** a caller's hard timeout must be at least
    `budget + 15` (interpreter start and exit). The monitor derives both from one
    constant (step 5).
- No store (`store.init` absent, or `todo.md` missing in a never-initialized
  store) → `REFRESH_NONE:no_store`, and nothing is created: the writer's
  first-mutation init must never run from refresh. No targets →
  `REFRESH_NONE:no_targets`, no write. Store damaged (writer exit 4) →
  `REFRESH_FAILED:store_unusable`, exit 1; exit 3 → `REFRESH_FAILED:lock_busy`.
- Root: `--root <path>` (default cwd) → `sitrep_harvest.canonical_root` (one
  store per repository; a linked worktree maps to the main root). `..` is refused
  before any filesystem access (exit 2).

### Wire contract (`aitask_sitrep_refresh.sh`)
```
aitask_sitrep_refresh.sh [--root <path>] [--dry-run]
REFRESH_ITEM:c<N>|<kind>|<old>-><new>|applied|stale|kept|not_found|dry_run|<outcome>   (outcome LAST)
REFRESH_WARN:<reason>|<detail>
REFRESHED:checked=<n>|changed=<c>|stale=<s>|kept=<k>|unknown=<u>      (final, exit 0)
REFRESH_NONE:no_store|no_targets                                    (final, exit 0)
REFRESH_FAILED:<reason>                                             (final, exit 1)
exit 2: usage / `..` root, nothing read or written
```
`changed` counts lines whose state or outcome differ (the stamp alone is not a
change). Test seams: `AITASK_SITREP_REFRESH_PAUSE_FIFO` with point
`refresh:before_write` (the same pattern as `AITASK_SITREP_PAUSE_FIFO`), and
`AITASK_SITREP_REFRESH_ARTIFACT_SH` (the artifact CLI used for the trail fetch,
default `.aitask-scripts/aitask_artifact.sh`), and
`AITASK_SITREP_REFRESH_BATCH_LOG` (a file that receives a copy of the exact
batch stdin sent to the writer).

## Implementation steps

1. **Writer: the `push:` ref and todo format 2** (`.aitask-scripts/lib/sitrep_todo.py`, header of `aitask_sitrep_todo.sh`).
   - `PUSH_REF_RE = ^push:(<branch>)@([0-9a-f]{7,40})\Z`, with branch
     `[A-Za-z0-9._][A-Za-z0-9._/-]*`, no `..`, no `//`, no trailing `/` or
     `.lock`. `normalize_ref` accepts it verbatim (lowercased sha) and the error
     message names the third form.
   - Split `FORMAT_VERSION` into `TODO_FORMAT_VERSION = 2` and
     `QA_FORMAT_VERSION = 1` (qa.md is unchanged). `TodoStore.format` is
     parsed from line 2 (accepted `{1, 2}`; anything else stays a FormatError).
     `render_todo` emits `store.format`, so render∘parse stays the identity on
     a v1 file. A v1 file containing a `push:` ref is a FormatError
     ("push refs need format=2"). Every op that commits a CHANGED todo sets
     `store.format = TODO_FORMAT_VERSION` (upgrade on write; a no-op write
     leaves a v1 file byte-identical). `empty_text` renders v2. Check every
     `FORMAT_VERSION` / `TODO_HEADER` user (`grep -rn` across `.aitask-scripts`
     and `tests`, including `sitrep_harvest.py`).
   - **`op_upsert_context` takes a fresh item rev** on `created` / `replaced`
     (`revs = Revs(args.store)`; `item.rev = revs.take()`;
     `_commit_todo(args, store, revs)` so `@NEXT_REV` is emitted). `unchanged`
     takes none. The result line shape is unchanged (`CONTEXT:c<N>|…`). Check the
     harvest's upsert-context callers and any test pinning a rev after an
     upsert (`tests/test_sitrep_todo.sh`, `tests/test_sitrep_harvest.sh`), and
     update the pins while keeping the assertions. The header's CONCURRENCY
     paragraph says "every change to an item OR its context entry gives the item
     a fresh rev".
   - Header comments in both files: the ref grammar, the format=2 change
     (read v1, write v2), and that push refs are created by the skill.
2. **Fixture** (`tests/fixtures/sitrep/`): per the contract, a format change
   edits the fixture. Move the current golden store to
   `tests/fixtures/sitrep/store_v1/` (unchanged bytes). Regenerate
   `store/` as format=2 through the writer, with `AITASK_SITREP_NOW` pinned. It
   is the same content plus one item `c6` (`kind=action`,
   `ref=push:main@<sha>`, `derived=agent`) and its context. Update
   `expected_list.txt`. `expected_context_c1.txt` and `expected_check_sources.txt`
   stay unchanged unless regeneration changes them, and any diff is reviewed.
   `tests/test_sitrep_todo.sh` Test 16 keeps its assertions on `store/`. Add
   Test 16b on `store_v1/`: `read` is byte-identical, `list` matches a pinned
   `expected_list_v1.txt`, a no-op update leaves it byte-identical, and a real
   update rewrites line 2 to `format=2` with every other line unchanged except
   the touched item. Add 16c: `add --ref push:…` accepted, plus each invalid
   push form → exit 2 with nothing written, and `EXISTS:` on a second add of the
   same push ref. `tests/test_sitrep_todo_format.py:108`'s "format=2 refused"
   case becomes format=3, and new cases cover v1 parse with a push ref → error
   at the item line, qa format=2 refused, and render emits the parsed version.
3. **`.aitask-scripts/lib/sitrep_refresh.py`** (stdlib plus `sitrep_todo`,
   `sitrep_harvest` (for `canonical_root` and `resolve_project`), `archive_iter`,
   `task_yaml`, `trail_discovery`, `trail_gather`; the last two imported lazily
   inside the trail check, so a repo with no trail items never pays their import).
   - pure layer: `Verdict(state, outcome)`, `select_targets(store) -> [Target]`,
     `lookup_task(root, tid, fold_index) -> TaskFacts`,
     `reminder_verdict(facts) -> Verdict`, `landed_state(facts, follow) ->
     landed|open|unverifiable` (receiver chain, ≤5 hops, cycle guard),
     `push_verdict(root, branch, sha)` (URL-identity rule included),
     `trail_verdict(doc, entry_state, drift) -> Verdict`,
     `order_targets(targets)` (checked_at ascending, `never` first, then id),
     `clean_outcome(parts) -> str`, and `Deadline(budget)` (`check_left()`,
     `run_left()`, `reserve`).
   - worker: `cmd_worker(args)` does the slow sequence and emits the line
     protocol (Design). Each target is wrapped, so an exception becomes
     `VERDICT …|unknown|check error: <Type>`.
   - parent: `cmd_run(args)` holds the `Deadline`, spawns and supervises the
     worker (selector loop, group kill, reap), turns the stream into the batch
     (interrupted target → `unknown` budget reason), calls the writer, and
     prints the wire contract. `REFRESH_FAILED:worker:<rc>` if the worker
     exits non-zero without a `FAILED:` or `NONE:` line.
   - e2e seams: `AITASK_SITREP_REFRESH_PAUSE_FIFO` is read by the parent
     (`refresh:before_write`, parked after the worker's EOF and before the
     writer call, outside the check deadline so a paused test is not killed);
     `AITASK_SITREP_REFRESH_ARTIFACT_SH` is read by the worker.
   - The writer call is one
     subprocess with absolute `AITASK_SITREP_DIR`, `cwd=root`, and the timeout
     and lock-timeout taken from the shared deadline (Design), with exit codes
     mapped as above, like `sitrep_harvest.Store.run`. A project
     resolution cache and a fold-scan cache are kept per run.
   - module docstring: targets, evidence rules, the "unknown only for targets"
     rule, the CAS/no-retry rule, the no-fetch push rule, budgets, and that it
     never creates a store.
4. **`.aitask-scripts/aitask_sitrep_refresh.sh`**: thin bash entry
   (`#!/usr/bin/env bash`, `set -euo pipefail`, header documenting the wire
   contract, exit codes, seams, and callers: the monitor tick, the sitrep skill
   (t2175_4), and on-demand use). It validates args, refuses `..` in `--root`
   (exit 2) before any FS access, resolves python via `lib/python_resolve.sh`
   (`require_ait_python`), and execs `lib/sitrep_refresh.py`. It does not
   source `task_utils.sh` (the t2175_1 EXIT-trap reason). No `ait` dispatcher
   entry (the t2175_1 decision). The permission touchpoints are owed by
   t2175_4, the first SKILL.md caller (`aidocs/framework/aitasks_extension_points.md`).
5. **Monitor tick** (`.aitask-scripts/monitor/monitor_shared.py`).
   - Add `_SITREP_REFRESH_SH = _SCRIPT_DIR / "aitask_sitrep_refresh.sh"`,
     `_SITREP_REFRESH_BUDGET = 60.0` (passed as `--budget`, covering checks
     plus write) and `_SITREP_REFRESH_TIMEOUT = _SITREP_REFRESH_BUDGET + 15.0`
     (the script's caller contract). Both come from one constant, so they cannot
     drift apart. Add class-level
     floors `_sitrep_refresh_inflight = False`, `_sitrep_refresh_due_at = 0.0`.
     Init them in `_init_agent_marks` with `_MARKS_PURGE_STARTUP_GRACE` and
     `_MARKS_PURGE_INTERVAL` cadence, independent of the other jobs.
   - `async def _maybe_refresh_sitrep(self)`: due/inflight guards. Roots =
     `sorted({r for s in self._session_root_map if (r := self._root_for_session(s))})`.
     For each root where `<root>/.aitask-sitrep/store.init` is a file,
     `await self._run_marks_cmd(["--root", root, "--budget",
     str(int(_SITREP_REFRESH_BUDGET))], script=_SITREP_REFRESH_SH,
     timeout=_SITREP_REFRESH_TIMEOUT)`. A root without a store spawns nothing.
     Wrap in try/except/finally like `_maybe_purge_sessions` (the inflight
     flag is cleared in `finally`; the due time is set after the pass).
   - Call it in `_dispatch_refresh_maintenance._maintenance()` after
     `_maybe_purge_sessions()`. Comment: harvest `all` (t2175_5) belongs
     before it, so newly harvested items get refreshed in the same pass.
6. **Tests**.
   - `tests/test_sitrep_refresh.py` (unittest, scratch dirs, no real
     `~/.config`): task lookup and verdicts for every row above (loose active /
     child, archived loose, archived inside a `.tar.gz` numbered bundle (the
     fallback path, so no zstd binary is needed), Folded with and without
     `folded_into`, fold scan hit/miss/error, an unreadable dir → `unknown`);
     push against a scratch repo with a bare `origin` (pushed → done, ahead
     → open with counts, unknown sha / non-git → unknown, a branch name with
     a shell metacharacter refused) **and every non-remote destination →
     unknown, never done**: no upstream; a local upstream
     (`git config branch.main.remote .` + `branch.main.merge
     refs/heads/integration`, with the sha on `integration`); a remote name
     whose URL was removed; a repo with no remotes at all; **the two-endpoint
     case**: `origin.url` = bare A (holds the sha, fetched into
     `refs/remotes/origin/main`) and `origin.pushurl` = empty bare B, with
     `main@{push}` = `refs/remotes/origin/main` and the ancestry true →
     `unknown` (push URL differs); likewise two `pushurl` entries, two `url`
     entries, and a `pushInsteadOf` rewrite that changes only the push URL.
     Controls: `pushurl` equal to `url` → done, no `pushurl` → done.
     **Trail landing**, over a schema-valid doc built the way
     `tests/test_trail_gather.py` builds them (next wave, all Done → done, one
     unresolvable entry with the rest Done → unknown, drift labels), with these
     fold cases: (a) an existing Folded entry file whose `folded_into` primary
     is Ready, then Implementing → entry open (`t12→t30`), wave not advanced,
     trail not done; the same primary archived Done → landed; (b) a **deleted**
     folded file found by the fold scan in a Ready primary's `folded_tasks` →
     open, and Done → landed; (c) a receiver chain t12→t30→t31 with t31 Done →
     landed; a cycle or more than 5 hops → unverifiable. In the same fixtures
     the task items (reminders) for t12 are `done` (`folded into t30 (t30:
     Ready)`), so the settled reminder rule is pinned beside the trail rule.
     **Deadline and ordering**: `Deadline` arithmetic (reserve = min(15, budget/4));
     `order_targets` (`never` first, oldest stamp next, id ties);
     stream-to-batch conversion (an interrupted `START:` → `unknown` budget
     line carrying the START's snapshot rev, not-started → unwritten, a `ROOT:`
     with `|` taken whole, a VERDICT for a non-open id / two open STARTs →
     protocol error, nothing written).
     Target selection (question, done, dismissed, agent action without a push
     ref, no ref → not targets); `clean_outcome` (≤200, no `|`, no control
     characters, deterministic truncation).
   - `tests/test_sitrep_refresh.sh` (bash, `tests/lib/asserts.sh`, file-backed
     counters if any body runs in a subshell, scratch git roots, scratch
     `HOME` with `AIT_PYTHON` pinned first (the t2175_2 gotcha), scratch
     projects registry):
     1. **follow-up lands**: Ready → `open|status: Ready`, then Implementing →
        open, then archived Done → `done|archived (completed …)`. A further run
        leaves that line byte-identical (not re-checked).
     2. **archival / harvest-unknown**: an `unknown` item whose task now exists → `open`.
     3. **fold**: Folded with `folded_into` → done. Then the folded file is
        deleted and the primary archived with `folded_tasks` → done via the
        fold scan.
     4. **push**: scratch repo plus bare origin, `push:main@<sha>` → open
        `1 ahead`. After `git push` (no refresh-side fetch) → done.
     5. **unreachable repo → unknown**: cross-repo ref with the project absent
        from the registry, and a registry entry pointing at a deleted dir,
        both → `unknown`. A push item in a non-git root → `unknown`. None of
        these ever become `done`.
     6. **concurrent refresh vs agent write**: refresh parked at
        `refresh:before_write`; meanwhile `dismiss c1` and `update c2 --title`
        → resume → `kept` for c1 and `stale` for c2; c1 stays dismissed and c2
        keeps its new title. The other targets are applied. Two concurrent
        refreshes both exit 0, the store parses, and every item is present.
     6b. **context swap during a paused refresh**: watch item c3 points at
        stubbed trail A (all landed, so refresh computes `done`). While paused,
        `upsert-context c3` swaps the source to unfinished trail B → resume →
        `stale` for c3, which stays `open`. The next refresh reads B → `open`
        with B's next wave. The trail fetch is stubbed by the test seam
        `AITASK_SITREP_REFRESH_ARTIFACT_SH`, which points at a script serving
        fixture JSON per handle. Drift then reports `error`/`unavailable`,
        which never decides state. An `unchanged` upsert during the pause → the
        line still applies.
     7. non-targets (question, done, dismissed, agent action) keep
        byte-identical lines; `--dry-run` writes nothing.
     8. no store → `REFRESH_NONE:no_store` and no `.aitask-sitrep/` created;
        a damaged `todo.md` → `REFRESH_FAILED:store_unusable`, exit 1,
        nothing changed; `..` root → exit 2.
     9. budget: `--budget 0` → `REFRESH_FAILED:deadline` (the worker never
        reported `ROOT:`), nothing written.
     10. **slow check + slow writer within the caller contract**: `--budget 12`
        (reserve 3), two push items, and a PATH-first `git` shim that sleeps 2 s
        per call for push-check subcommands (`merge-base`, `rev-list`,
        `remote`) and then execs the real git. Meanwhile a writer is parked on
        the store lock via `AITASK_SITREP_PAUSE_FIFO` at `write:after_backup`
        and released after 4 s. The run goes under `timeout 27` (budget + 15,
        the monitor's rule) and must exit 0 with `REFRESHED:` before the timeout.
        Finished targets are written, the interrupted one is `unknown` with the
        budget reason, the rest are unwritten, and elapsed < 27 s. Then the lock
        is held past the refresh's lock timeout → `REFRESH_FAILED:lock_busy`,
        exit 1, nothing written, still before the outer timeout.
     11. **real archive path stalls**: the archived task bundle is a real
        numbered `.tar.zst`, and a PATH-first `zstd` shim sleeps 600 s before
        exec'ing the real one. A missing-id task item triggers the fold scan
        through the real `archive_iter` `Popen` path, which hangs. With
        `--budget 10` under `timeout 25`: exit 0 before 25 s, targets before the
        stall are written, the stalled one is `unknown` (budget reason), the
        rest are unwritten, and afterwards no `zstd`/`sleep` process of the
        test's process group survives (`pgrep -f` on the shim's unique
        marker). Skip with a SKIP line if `zstd` is not installed.
        The same with a `git` shim stalling `worktree list` (inside the reused
        `canonical_root`) → `REFRESH_FAILED:deadline` before the outer timeout,
        nothing written, no survivor.
     12. **progress across bounded runs**: six targets with `checked_at=never`,
        where c1–c3 are push items made expensive by the git shim (one takes
        ≈ the whole check budget) and stay open, and c4–c6 are cheap local
        task items. Run the refresh repeatedly under a budget that fits one
        expensive check. After at most 4 runs, c4–c6 have been checked
        (non-`never` `checked_at`, correct `open` status), while c1–c3 remain
        open/unknown, and no run lasted past budget + 15. A control that
        orders by id instead (the mutant below) never reaches c4–c6.
     13. **interrupted before the first VERDICT, with concurrent edits**:
        the git shim stalls the first target (push item c1) until the kill.
        (a) No edit → c1 is written `unknown` with the budget reason, using its
        snapshot rev (`REFRESH_ITEM:c1|…|applied`), and the other targets are
        unwritten. (b) While the worker is stalled, `update c1 --title X` →
        after the kill the c1 line is `stale`, c1 keeps title X and its pre-run
        state, and nothing else is written for it. (c) The same with
        `upsert-context c1` (a changed entry) → `stale`, and the new context is
        preserved. Each case asserts the batch the parent sent (a seam:
        `AITASK_SITREP_REFRESH_BATCH_LOG` copies the exact stdin given to the
        writer) carries the START's rev, not the current one.
   - `tests/test_monitor_sitrep_refresh.py` mirroring
     `tests/test_monitor_sessions_purge.py`'s `_Host` / `IsolatedAsyncioTestCase`
     pattern: runs only for roots with `store.init`, one call per distinct root
     with `--root` and `--budget 60`, the timeout passed is ≥ budget + 15
     (pinned from the two constants), startup grace and cadence,
     never stacked, the flag is cleared when the command raises, independent of
     the sessions purge, and the maintenance worker awaits it (the
     `MaintenanceDispatchTests` source check).
7. **Regression and lint**: `bash tests/test_sitrep_todo.sh`,
   `python3 -m unittest tests.test_sitrep_todo_format tests.test_sitrep_harvest
   tests.test_sitrep_refresh tests.test_monitor_sitrep_refresh
   tests.test_monitor_sessions_purge`, `bash tests/test_sitrep_harvest.sh`,
   `bash tests/test_sitrep_refresh.sh`, the full Python suite (read only the last
   line), and `shellcheck` on the new and changed `.sh` files.
8. **Notes** (`./ait note`, after the commit, citing its SHA):
   - **t2175_4**: create push items with
     `add --kind action --ref push:<branch>@<sha> --derived agent`. Run
     `aitask_sitrep_refresh.sh` on start (after harvest `all`). The outcome texts
     are the live state shown in Part 1, so the skill reads them and never
     restates task content. It owes the 5 permission touchpoints for
     `aitask_sitrep_refresh.sh`. Unknown means unverified, never done.
   - **t2175_5**: the maintenance tick already runs refresh
     (`_maybe_refresh_sitrep`). Put harvest `all` before it in `_maintenance()`.
     `REFRESH_*` lines are available if the monitor shows an indicator.

### Post-phase (risk mitigations)

1. [refresh_guard_mutants] One mutant per guard, each in a fresh `mktemp -d`
   copy of the tree (never `rm -rf "$VAR"`; the t2175_1 lesson). Each must turn
   its named test red, and an unmutated control copy must be green on the same
   commands. Evidence (mutant → red test) goes in the Final Implementation
   Notes:
   - an `Implementing` status maps to `done` (follow-up-lands e2e case 1 + verdict unit tests)
   - task-lookup `errors` ignored, so a failed listing reads as missing (the unreadable-dir unit test)
   - not found maps to `done` (case 5 / fold-scan-miss unit test)
   - push without `merge-base --is-ancestor` (open is reported as done in case 4's pre-push step)
   - the batch carries a re-read rev instead of the observed one (case 6 turns from `stale` to applied)
   - `render_todo` always emits v2 (Test 16b's no-op byte-identity)
   - a v1 parse accepts a `push:` ref (the format unit test)
   - a Folded trail entry is landed regardless of its receiver (fold cases a and b)
   - `upsert-context` keeps the item rev (e2e 6b turns from `stale` to applied)
   - `@{push}` accepted without the `refs/remotes/<configured remote with URL>`
     check (the local-upstream unit case turns `done`)
   - writer timeout and lock timeout not derived from the deadline (fixed 60 s / 10 s; e2e 10 runs past `timeout 27`)
   - the push URL-identity check removed (two-endpoint unit case turns `done`)
   - checks run in the parent without the worker/group kill (e2e 11 overruns `timeout 25` or leaves a survivor)
   - `kill(pid)` instead of `killpg` (e2e 11: the zstd shim survives)
   - targets ordered by id instead of `checked_at` (e2e 12: c4–c6 never checked)
   - the interrupted target left unstamped (e2e 12: starvation recurs)
   - the parent re-reads the current rev for an interrupted target instead of using START's (e2e 13b/13c: the edit's rev passes CAS and the line applies)
2. [live_store_smoke] Against a COPY of this repo's real `.aitask-sitrep/`
   (`cp -a` into the scratchpad, absolute `AITASK_SITREP_DIR`; the real store
   is never written):
   - `aitask_sitrep_refresh.sh --root <copy root> --dry-run`: every item is
     reported with a verdict that matches the real task state (t2181/t2182
     open with their status, triage items untouched).
   - one real run on the copy: line 2 becomes `format=2`, and
     `aitask_sitrep_todo.sh list` and `aitask_sitrep_harvest.sh record`-style
     reads (`sitrep_todo.load_todo_for_read`) still parse it.
   - the trail check, read-only, on `art:trail-gates-framework-landing` (or
     another real handle from `grep -h "handle: art:trail" -r aitasks/`): a
     next-wave outcome of at most 200 characters with a drift label.
   Record the observed lines in the Final Implementation Notes.

## Verification
- `bash tests/test_sitrep_refresh.sh`, `bash tests/test_sitrep_todo.sh`,
  `bash tests/test_sitrep_harvest.sh`
- `python3 -m unittest tests.test_sitrep_refresh tests.test_sitrep_todo_format tests.test_sitrep_harvest tests.test_monitor_sitrep_refresh tests.test_monitor_sessions_purge`
- `bash tests/run_all_python_tests.sh`: last line verdict only
- `shellcheck .aitask-scripts/aitask_sitrep_refresh.sh .aitask-scripts/aitask_sitrep_todo.sh`

## Post-implementation
Step 9 of the task workflow: commit, archive t2175_3, push via `./ait git`.

## Risk

### Code-health risk: medium
- The todo format bump (`format=2`, push refs) changes the one writer that harvest and every store depend on; this repo's live store is v1, and a wrong upgrade path would make stores exit 4 · severity: low (residual — addressed by inline post-phase refresh_guard_mutants and live_store_smoke, plus the v1 fixture tests) · → mitigation: inline post-phase live_store_smoke
- The monitor's trailing maintenance gains a third job; a hang or raise could wedge maintenance · severity: low · → mitigation: none (same total `_run_marks_cmd` with a timeout, inflight flag cleared in `finally`, tests mirror SessionsPurgeTests)
- The task lookup mirrors `trail_links.lookup_task_meta`'s fail-closed logic instead of sharing it (that helper is xdeps-specific and cwd-rooted) · severity: low · → mitigation: none (small, cited, unit-tested)
- Blast radius: the writer core, its fixture, the monitor mixin, two new scripts · severity: low · → mitigation: none

### Goal-achievement risk: low
- The positive-evidence rules (Done-unarchived, fold scan, archived non-Done) are judgement calls, and a wrong rule makes an item `done`, which is irreversible because done items are not re-checked · severity: low (residual — addressed by inline post-phase refresh_guard_mutants) · → mitigation: inline post-phase refresh_guard_mutants
- Trail and push checks are only unit-tested against stubs and scratch repos; the real artifact path and the real store are unexercised · severity: low (residual — addressed by inline post-phase live_store_smoke) · → mitigation: inline post-phase live_store_smoke
- Push evidence uses the remote-tracking ref without fetching: a stale ref keeps an item open (never a wrong done); a later force-push that drops the sha is not detected · severity: low · → mitigation: none (documented; the outcome names the fetch date)
- (review round 1) A folded trail entry, a context swap during a refresh, or a local upstream could each have produced a wrong, irreversible `done`; a slow run could have been killed by its caller before the single write · severity: low (residual — the landed/receiver rule, the context rev bump, the remote-destination check and the shared deadline are each pinned by a test and a mutant in inline post-phase refresh_guard_mutants) · → mitigation: inline post-phase refresh_guard_mutants
- The fold receiver chain and the `folded_tasks` scan read every archive bundle; on a large archive this is the slowest check · severity: low · → mitigation: none (lazy, once per run, only for not-found ids, bounded by the group kill, rotated by the ordering rule)
- (review round 2) A distinct push URL, a reused helper with an unbounded wait, or an always-expensive early target could still have closed a push wrongly, overrun the caller, or starved later items · severity: low (residual — URL identity, the worker group kill and checked_at ordering are each pinned by an e2e/unit case and a mutant) · → mitigation: inline post-phase refresh_guard_mutants
- The parent/worker split adds a line protocol and process supervision · severity: low · → mitigation: none (the pattern exists in agent_freeze; supervision paths are covered by e2e 9–12)
- Push items have no producer until t2175_4 · severity: low · → mitigation: none (note to t2175_4 with the exact `add` line)

### Planned mitigations
- timing: post-phase | name: refresh_guard_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — irreversible wrong `done`; code-health — format upgrade | desc: one mutant per guard (Implementing→done, lookup errors ignored, missing→done, push without ancestor check, re-read rev in batch, always-v2 render, v1 accepting push refs, folded entry landed without a Done receiver, upsert-context without a rev bump, @{push} without the remote check, deadline-free writer timeouts, push URL identity removed, checks without the worker group kill, kill instead of killpg, id ordering, interrupted target unstamped, re-read rev for the interrupted target) must turn its test red
- timing: post-phase | name: live_store_smoke | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — real paths unexercised; code-health — upgrade of real v1 stores | desc: dry-run and one write on a copy of this repo's real store, plus a read-only trail check on a real art:trail handle
