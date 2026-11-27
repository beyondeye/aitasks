---
Task: t2379_fix_dep_scan_invalid_utf8_and_stale_trail_skill_contract.md
Base branch: main
Output branch: main
---

# t2379 — dep scan dies on invalid UTF-8; stale trail skill-contract test

## Context

Two upstream defects found during t2335_3 review:

1. `.aitask-scripts/lib/dep_resolution.py` — `LocalDepResolver._read_facts`
   (~604) and the per-file read in `scan()` (~705) catch `OSError` only. A
   task file that is not valid UTF-8 raises `UnicodeDecodeError` (a
   `ValueError`). Through `facts()`/`classify()` it escapes into callers; in
   the blocking scan it kills the process before `SCAN_OK`, so `ait ls` marks
   **every** dependent `Blocked [unverified]`. `lookup()` (t2335_3) already
   catches `(OSError, UnicodeDecodeError)`.
2. `tests/test_trail_skill_contract.sh` fails 6 assertions (2 phrases × 3
   goldens). Verified: **the test is stale, the skill lost no rule.** t1989
   (`af9f27ae7`) rewrote the prose — (g) "an explicit owner choice is REQUIRED
   before any create" now line-wraps between "explicit" and "owner"; (j)
   "Always pass `--owner <id>`" became the stricter
   "**Always pass `--owner <owner> --allow-archived-owner`**".

### Review concerns (verified, both valid — addressed below)

- **Fail-open through `ait ls`.** `scan()`'s per-file skip writes nothing for
  the skipped task, then `SCAN_OK`. `aitask_ls.sh` reads the same file with
  bash `read` (byte-tolerant), sees `status: Ready` + a `depends:` key, finds
  no scan row (`lookup_dep_blocking`, ~440) and lists it **Ready**. `ait ls`
  is the only consumer of the scan output (grep: `aitask_ls.sh:339`). The same
  hole already exists for the `OSError` skip; widening the catch would add a
  common new route into it.
- **Catch scope.** The `scan()` try block covers `prime()` and
  `classify_text()` too, which run the gate evaluator (`gate_ledger`
  witness / registry / git work). A broad decode catch there would drop a
  healthy dependent's whole row (even a second, missing dep) under `SCAN_OK`,
  and blame the wrong file. The decode recovery must cover **only the task
  file read**.
- **Key-gated UNVERIFIED (round 2).** `ait ls` sets `depends_key_present`
  only on a bash `case` match of the literal key `depends` (~548). A bad byte
  inside the key leaves it 0, so an UNVERIFIED row gated on it is ignored and
  the task lists Ready. The UNVERIFIED row is therefore honoured on its own.
- **Command help (round 2).** `aitask_gate.sh` help for `deps-blocking-scan`
  (~1700) describes only blocking rows + `SCAN_OK`; it is updated in this
  change (a few lines, not worth a separate task).

## Implementation

1. **`dep_resolution.py` `_read_facts`** — `except OSError:` →
   `except (OSError, UnicodeDecodeError):` → `None` → `UNRESOLVABLE`
   (blocking, `(UNRESOLVED)`), the outcome an `OSError` already gets. The try
   there already covers only the read (`_facts_from_text` is outside it).
2. **`dep_resolution.py` `scan`** — split the loop body into two blocks:
   - read: `try: open/read` / `except (OSError, UnicodeDecodeError) as exc:`
     → stderr `deps-blocking-scan: <path>: <exc>`, write
     `UNVERIFIED\t<path>`, `continue`.
   - prime + classify: unchanged `except OSError` boundary (pre-existing
     behaviour), which now also writes the `UNVERIFIED\t<path>` row instead
     of silently costing the task its verdict. A `UnicodeDecodeError` (or
     anything else) raised during evaluation is **not** caught: the scan
     dies without `SCAN_OK`, the existing failed-scan behaviour.
   - new module constant `_UNVERIFIED = "UNVERIFIED"` beside `_TERMINAL`;
     update the `scan()` docstring with the row grammar. A real path can
     never equal `UNVERIFIED` (rows are `os.path.join(tasks_dir, …)`).
3. **`aitask_gate.sh`** — document the second row kind
   `UNVERIFIED<TAB><path>` (this task file could not be read or evaluated;
   its dependency state is unknown, and absence from the blocking rows must
   not be read as "not blocked") in **both** places: the implementation
   comment (~877) and the `deps-blocking-scan` command help (~1700).
4. **`aitask_ls.sh`** —
   - `build_dep_blocking_map`: in the parse loop, `k == UNVERIFIED` → append
     `v` to a new `dep_scan_unverified=()` array (bash-3.2 safe, same
     indexed-array shape) and `continue`.
   - new `is_dep_unverified <path>` (array scan like `lookup_dep_blocking`).
   - `calculate_blocked_status`, `dep_scan_state == ok` branch: check
     `is_dep_unverified "$current_task_file"` **first and independently of
     `depends_key_present`** — the scanner is the authority on that path,
     and a corrupt byte inside the key itself (`dep\xffends:`) makes this
     script's own key detection miss it. Hit → `blocked=1;
     blocked_unverified=1; blocking_info` = `d_text` when it parsed to
     something, else `depends:` — the rendering of the scan-failed branch,
     factored into one helper both use. Miss → the existing
     `depends_key_present`-gated scan-hit lookup, unchanged.
   - Consequence, intended (fail-closed): an unreadable task file with no
     dependencies at all also lists `Blocked (by depends:) [unverified]` —
     its dependency state really is unknown. Comment says so.
5. **`tests/test_local_dep_parity.py`** — new `InvalidUtf8Tests(_TreeCase)`:
   - fixture, both placements of the invalid byte (`b"\xff"`):
     `t410_x.md` = valid frontmatter `status: Ready`, `depends: [999]`, the
     byte in the **body**; `t412_x.md` = `status: Ready` with the byte
     **inside the key** (`dep\xffends: [999]`), so bash sees no `depends:`
     key; `t411` = `write_task(..., "411", "Ready", depends=["410"])`.
   - core: `facts("410")` is `None`; `classify(["410"])` → one blocking
     `UNRESOLVABLE` verdict `410 (UNRESOLVED)`; `lookup("410")` is
     `UNREADABLE`.
   - scan (stderr captured): last line `SCAN_OK`; `UNVERIFIED\t<path>` for
     both t410 and t412; t411 row is `410 (UNRESOLVED)`; the fixture's t203
     row `999 (UNRESOLVED)` still present; stderr names both paths.
   - **real `ait ls`** (`LS -v -s all --all-levels 999`): the t410 line
     carries `Blocked (by 999) [unverified]`; the t412 line carries
     `Blocked (by depends:) [unverified]` (no `Status: Ready`); the t411 line
     carries `Blocked (by 410 (UNRESOLVED))` and **not** `[unverified]`; t203
     is still plainly blocked, not `[unverified]` (the scan did not fail as a
     whole).
   - scope: patch `LocalDepResolver.classify_text` to raise
     `UnicodeDecodeError` for one dependent → `scan()` raises (no `SCAN_OK`
     written). Patch it to raise `OSError` for one dependent → that path gets
     an `UNVERIFIED` row, the other rows are kept, `SCAN_OK` last.
   - Controls, run by hand and recorded in Final Implementation Notes:
     (a) new tests vs the unmodified code → fail (scan raises; `ait ls`
     reports t411 `[unverified]` because the whole scan failed);
     (b) after steps 1-2 with the `UNVERIFIED` row write left out → the
     `ait ls` assertion fails with t410 listed `Ready` (the reviewer's
     scenario, reproduced); (c) the broad catch the first plan proposed → the
     scope test fails; (d) the `ait ls` UNVERIFIED check gated on
     `depends_key_present` → the t412 assertion fails (t412 listed `Ready`)
     while t410 still passes.
6. **`tests/test_trail_skill_contract.sh`** — update the two stale pins,
   keeping assertion names: (g) `"owner choice is REQUIRED before any create"`;
   (j) ``'Always pass `--owner <owner> --allow-archived-owner`'`` (and its
   comment). No skill template / golden changes.

Out of scope (noted in Final Implementation Notes, not changed): the board
and minimonitor read dependent task files themselves; how they treat a
non-UTF-8 *dependent* file is not this task's scan path.

## Verification

- `python3 -m unittest tests.test_local_dep_parity -v` — all pass.
- `bash tests/test_trail_skill_contract.sh` — `0 failed`.
- `bash tests/test_xdeps_blocking.sh`, and any `tests/test_*ls*.sh` touching
  `aitask_ls.sh` blocking output — pass.
- `shellcheck .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_gate.sh`.

## Step 9

Commit code + tests (`bug: … (t2379)`) naming paths explicitly (shared dirty
worktree); plan via `aitask_task_commit.sh`; archive per Step 9.

## Risk

### Code-health risk: low
- New scan row kind is a protocol change; a consumer that does not know it
  would treat `UNVERIFIED` as a path key and never match it (harmless). Only
  `ait ls` consumes the scan (grep-verified) and is updated in the same
  change · severity: low · → mitigation: none

### Goal-achievement risk: low
None identified.

## Post-Review Changes

### Change Request 1 (2026-11-27 11:25)
- **Requested by user:** (1) the (g) OWNER:none pin had dropped "explicit" to
  dodge the template's line wrap, so replacing "explicit" with "automatic" in
  all three goldens left 303/303 green; keep the full phrase and normalize the
  line break. (2) The `deps-blocking-scan` help and implementation comment did
  not say where the evaluation boundary is (only `OSError` is isolated; other
  evaluation exceptions propagate).
- **Changes made:** (1) `tests/test_trail_skill_contract.sh` (g) now asserts
  "an explicit owner choice is REQUIRED before any create" against the golden
  with every whitespace run folded to one space (`tr -s '[:space:]' ' '`).
  Negative control: the real test file, run from a scratch copy of `tests/`
  with "an explicit" → "an automatic" in all three goldens → 3 failures (the
  three owner-handoff assertions), 300 passed; unmutated copy 303/0.
  (2) `aitask_gate.sh` comment and command help now say: unreadable file (I/O
  error or not UTF-8) or an `OSError` during evaluation → `UNVERIFIED` row;
  any other exception while evaluating a readable file (e.g. a gate-witness
  decode error) ends the scan without `SCAN_OK`.
- **Files affected:** tests/test_trail_skill_contract.sh, .aitask-scripts/aitask_gate.sh
- **Concern resolutions:** no item touched a documentation page (the website
  claim names only unreadable files, which stays accurate).

### Change Request 2 (2026-11-27 11:50)
- **Requested by user:** (a) `git commit -- <paths>` takes the whole worktree
  file, so t2369's four uncommitted hunks in `aitask_gate.sh` would ride along;
  commit only t2379's changes, built and verified in isolation, keeping the
  doc guard. (b) A CAS on `main` followed by a blind `git reset -- <paths>`
  can unstage a concurrent session's `git add` of the same paths.
- **Changes made (integration procedure only, no source change):**
  `aitask_gate.sh` for the commit = HEAD + only t2379's two regions (verified:
  HEAD→mine = those 2 hunks; mine→live = exactly t2369's 4 hunks). Isolated
  worktree at 799b584a with only the six t2379 files: parity 44/44, trail
  contract 303/0, ls / xdeps / deps-unblock / witness-parity suites green. The
  commit is made in that worktree behind the doc guard, then integrated by a
  script that holds git's `index.lock` (O_EXCL) for the whole step: refuse if
  any of the six index entries is no longer its base blob, CAS
  `update-ref main <new> <base>`, write only those six entries into a copy of
  the locked index and rename it over `index`. Scratch-repo tests: clean case
  integrates and leaves the other session's hunk unstaged; concurrent `git add`
  → `REFUSED:index_entry_changed`, staged entry and `main` untouched; held lock
  → `REFUSED:index_locked`; moved branch → `REFUSED:branch_moved`, index
  untouched, lock released.
- **Files affected:** none (commit procedure).

### Change Request 3 (2026-11-27 12:05)
- **Requested by user:** (a) the integration helper compared only blob ids, so
  a staged mode-only change (same blob) was accepted and overwritten; compare
  the full stage-0 entry. (b) It advanced `main` before writing the prepared
  index, so a failed copy left `main` advanced and the index at base.
- **Changes made (integration procedure only):** each path must have exactly
  one `git ls-files -s` line identical to `<mode> <blob> 0<TAB><path>` from the
  base tree (multiple stages, missing entry, mode or blob change → refuse).
  The prepared index is copied INTO the held `index.lock` before `update-ref`;
  after the CAS only the rename remains, and a failed rename reports
  `PARTIAL:` (exit 4) keeping the prepared lock as the recovery
  (`mv -f index.lock index`). Scratch tests: pure mode-only stage
  (100644→100755, same blob) refused and preserved; content stage refused and
  preserved; held lock refused; moved branch refused, index untouched;
  injected prepare failure → nothing changed, lock released; injected rename
  failure → `PARTIAL:`, recovery `mv` yields the clean end state.
- **Files affected:** none (commit procedure).

### Change Request 4 (2026-11-27 12:15)
- **Requested by user:** `main` advanced to 251595ebb (t2369 landed), so the
  isolated worktree's base 799b584a3 is stale and the CAS would refuse;
  refresh the commit procedure — a standard guarded, path-scoped commit from
  current `main` is sufficient after a final diff check.
- **Verified:** HEAD→live of `aitask_gate.sh` is exactly the two reviewed
  hunks (hunk text identical to the isolated worktree's); 251595ebb touched
  none of the other five t2379 files, whose live content is byte-identical to
  the reviewed versions; nothing is staged on the six paths. Re-run in an
  isolated worktree at 251595ebb + the six live files: parity OK, trail
  contract, ls display, xdeps, boardcol, deps-unblock, witness parity green.
- **Changes made:** the commit uses the standard guarded
  `git commit -F - -- <six paths>` from `main`; the temp-worktree /
  index-lock integration helper is dropped (no longer needed). Scratch
  worktree removed.
- **Files affected:** none (commit procedure).

## Final Implementation Notes
- **Actual work done:** `dep_resolution.py` — `_read_facts` treats
  `UnicodeDecodeError` like `OSError` (→ `None` → `<id> (UNRESOLVED)`);
  `scan()` split into a read block (`OSError` / `UnicodeDecodeError` →
  stderr + `UNVERIFIED\t<path>`) and a prime/classify block (`OSError` only →
  same; any other evaluation exception propagates, no `SCAN_OK`); new
  `_UNVERIFIED` constant + docstring. `aitask_ls.sh` — collects `UNVERIFIED`
  rows into `dep_scan_unverified`, `is_dep_unverified` lookup checked first and
  independently of `depends_key_present`, `mark_deps_unverified` shared with
  the scan-failed branch. `aitask_gate.sh` — row kind and the `OSError`
  boundary documented in the implementation comment and the
  `deps-blocking-scan` help. `test_local_dep_parity.py` — `InvalidUtf8Tests`
  (4 tests: core, scan, real `ait ls` with the bad byte in the body and inside
  the `depends` key, catch-scope). `test_trail_skill_contract.sh` — (g) pins
  the full "an explicit owner choice is REQUIRED before any create" on a
  whitespace-folded golden; (j) pins
  "Always pass `--owner <owner> --allow-archived-owner`".
  `website/content/docs/commands/task-management.md` — Details paragraph
  covers an unreadable dependency and an unreadable task.
- **Deviations from plan:** added the website doc sentence (the page already
  documented the `[unverified]` / `(UNRESOLVED)` states this change extends);
  the scope test patches `classify_text` keyed on the one readable task text
  that declares `[999]` instead of tracking opened paths.
- **Issues encountered:** controls, all run by hand on the real code:
  (a) unmodified code → 3 errors (`UnicodeDecodeError`) + 1 failure (t412
  listed Ready even pre-fix: the whole-scan failure only marks tasks whose
  `depends:` key bash can read); (b) scanner fixed but `ait ls` not yet
  reading `UNVERIFIED` → t410 listed `Ready` (the review's fail-open,
  reproduced); (c) broad decode catch around prime/classify → scope test fails
  ("UnicodeDecodeError not raised"); (d) `UNVERIFIED` gated on
  `depends_key_present` → t412 listed `Ready`. Trail (g): the real test file run
  from a scratch copy with "an explicit" → "an automatic" in all three goldens
  fails the 3 owner-handoff assertions. Commit isolation: `aitask_gate.sh`
  carried t2369's uncommitted hunks during review; resolved when t2369 landed
  (251595ebb) — HEAD→live is then exactly the reviewed hunks, verified in an
  isolated worktree before the standard path-scoped commit.
- **Key decisions:** an unreadable task file lists as
  `Blocked (by depends:) [unverified]` even when it declares no dependencies
  (its dependency state is unknown; fail-closed). `facts()` / `classify()`
  keep their two-state contract (unreadable dependency = `UNRESOLVED`).
  The trail skill lost no rule — t1989 (`af9f27ae7`) reworded it; the test was
  stale.
- **Documentation review:** `website/content/docs/commands/task-management.md`
  — level=ok, prose=ok, reader=not-run(not-beginner), claims=ok (basis:
  `lib/dep_resolution.py`, `aitask_ls.sh`), 0 unresolved. Three `aidocs/`
  pages of the concurrent t2369 session excluded by the user.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_core.py:7111 — TaskInfoCache._resolve reads the task file with Path.read_text() and does not catch UnicodeDecodeError, so get_task_info() (minimonitor task picker) raises on a task file that is not valid UTF-8 (probed: t410 with a 0xff byte raises; its dependent t411 resolves 410 as UNRESOLVABLE correctly)`
