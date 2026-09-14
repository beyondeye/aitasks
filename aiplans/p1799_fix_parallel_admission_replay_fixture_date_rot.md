---
Task: t1799_fix_parallel_admission_replay_fixture_date_rot.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1799 — Remaining parallel-admission clock work after upstream t1763 (+ shortcut_scopes docstring)

## Context

The 4 `test_parallel_admission_collect.py` failures this task was spawned for
(replay fixtures locked at `2026-08-30 08:00`, judged at the wall clock, aged
past `MAX_CLAIM_AGE_S` on 2026-09-13) are **already fixed on `origin/main`** by
`44f92f5fa` (t1763). That commit pins `col.time = _FrozenClock(self.NOW)` in
`_ReplayScaffold` and `ExcludeNoPlanPredicateTests`. I checked this read-only:
the upstream test file, run in memory against this tree's (unchanged) collector,
passes **101/101**. The checkout is **ahead 12 / behind 2** of `origin/main`, so
the plan first reconciles, then does only the work that remains:

1. **The task's requested guard test** was not added upstream (t1763 only pins
   the clock). It is added here as behavioral coverage on top of `_FrozenClock`.
   No second clock mechanism, and no repo-wide structural rule.
2. **`tests/test_parallel_admission_preflight.sh:73,87`** hard-codes
   `updated_at: 2026-09-02 09:00` on real-CLI fixtures (unchanged upstream). By
   `pa.tier()` the CONFLICT/UNCHECKABLE assertions flip after **2026-09-16
   09:00**. That comes from reading the code; a red proof confirms it before
   commit.
3. **`roadmap_run.run(now=…)`** (`roadmap_run.py:280/336`) drops its `now`:
   `collect_population` takes no `now`, so admission ages read the wall clock
   while the roadmap's generation/freshness use `now`. Fixed, with a
   **caller-level** test.
4. **`shortcut_scopes._ensure_import_paths` docstring** (`:80-81`, unchanged
   upstream) says the TUI dirs have no colliding basenames, but `applink/` and
   `chatlink/` both ship `paths.py` and `audit.py`.

## Implementation steps

### 0. Merge `origin/main` into `main` (user decision: merge, no rebase), then confirm the upstream fix
The user chose a **merge**: no existing SHA is rewritten, so nothing that cites
the 12 local commits (t1794_1, t1522, t1747_3, t1770, t1789, …) goes stale.
**Do not use `git pull`**: the repo sets `pull.rebase=true`, so a bare pull
would rebase.
- `git fetch origin main`, so the trial and the real merge see the same tip.
- **Precondition:** `git status --porcelain` is empty (the checkout is shared
  with concurrent sessions). If it is dirty, stop and ask; never stash.
- **Trial merge in a throwaway worktree:**
  `git worktree add --detach <scratchpad>/merge-probe HEAD`, then
  `git -C <probe> merge --no-edit origin/main`. It must complete with no
  conflicts. Two files changed on both sides, with disjoint hunks:
  `monitor/monitor_core.py` (local 186–283 vs upstream 439) and
  `tests/test_prompt_detection.py` (nearest hunks 7 lines apart). Then
  `git worktree remove --force <probe>`. This moves no branch ref. If the trial
  conflicts, stop and ask before touching `main`.
- **Real:** re-check the clean-tree precondition, then run
  `git merge -m "ait: Merge origin/main into main" origin/main`. It uses the
  administrative `ait:` prefix with no `(t1799)` tag, so the merge is not
  attributed to this task's code. If git refuses because a concurrent session
  has uncommitted edits to an incoming file, that is the safe failure: stop and
  ask.
- **Verify:** `git rev-list --left-right --count HEAD...origin/main` → `13 0`
  (the 12 local commits plus the merge). The original tip is still an ancestor:
  `git merge-base --is-ancestor c52534f14 HEAD`. Nothing is pushed; pushing
  `main` stays the user's call. Once pushed it is a plain fast-forward, because
  `main` now descends from `origin/main`.
- **Confirm the upstream fix in the tree:** `pytest -q tests/test_parallel_admission_collect.py`
  → 101 passed. Also `python3 tests/test_prompt_detection.py` passes (the
  merged file from both sides).
- The planning Checkpoint's Remote Drift Check will report `AHEAD:2` with an
  overlap on `tests/test_parallel_admission_collect.py`. That is expected;
  answer "Continue anyway", because this step is the integration.
- After the rebase, re-read every target file before editing (line anchors below
  are post-reconcile).

### 1. Forward the roadmap's `now` — caller-level
- **Test first** (`tests/test_roadmap_run.py`): `NowForwardingTests(_RunHarness)`.
  Rebind `rr.col.collect_population` (restored via `addCleanup`) to a recorder
  that appends its `now` kwarg and raises a private `_StopAtAdmission`. Then
  call `rr.run(self.tmp, _narrative(self.tmp), "owner",
  os.path.join(self.tmp, "out.json"), now=NOW)` under
  `assertRaises(_StopAtAdmission)` and assert the recorded list is `[NOW]`. The
  default `_Seam` drives `run()` through `enumerate_candidates` → `snapshot` →
  `origin_facts` (all via `_RUN`) to the `collect_population` call.
  **Red proof:** run it before the next two edits. It must fail with `[None]`.
- `.aitask-scripts/lib/parallel_admission_collect.py` `collect_population`
  (`:1051`): add `now=None`, pass `now=now` to its `collect(...)` call
  (`:1091`), and add one docstring line.
- `.aitask-scripts/lib/roadmap_run.py:336-337`: add `now=now` to the call. The
  test goes green. In production nothing changes, because `now` already
  defaults to `int(time.time())` at the top of `run`.

### 2. Behavioral clock guard — `tests/test_parallel_admission_collect.py`
Build on upstream's `_FrozenClock` (`:474`), the scaffold `NOW` (`:507`,
`:859`) and the `"time"` entry already in both `_saved` tuples:
- `FixtureClockTests(_ReplayScaffold)` (a concrete subclass; the scaffold stays
  test-free):
  1. `test_the_fixture_lock_is_fresh_at_the_scaffold_clock`: read the installed
     fixture (`col._LOCK_PROBE(self.root)[1]["9"]["locked_at"]`) and assert
     `0 <= self.NOW - col.parse_ts(it)[0] < pa.MAX_CLAIM_AGE_S`, with a message
     that names the aging hazard.
  2. `test_replay_judges_at_the_scaffold_clock`: replay with `--thresholds 10`
     and assert a line starting `"SNAPSHOT:%d|" % self.NOW`. `base.now` is the
     value `tier()` ages claims against, so this proves the code under test
     reads the pinned clock.
  3. `test_an_unpinned_clock_reproduces_the_rot` (negative control): set
     `col.time = time` (the real module; the scaffold's `_restore` re-pins it)
     and assert that SNAPSHOT is **not** `self.NOW` and that
     `VERDICT_FOR:11|CONFLICT` is absent. This reproduces the original failure
     on demand, which proves tests 1–2 are not vacuous and that the pin is
     load-bearing.
- `ExcludeNoPlanPredicateTests`: add one test asserting
  `self._base().now == self.NOW` and that `LIVE["locked_at"]` is fresh against
  it.
- No AST or structural rule: `CollectIntegrationTests` keeps its explicit
  `now=`, which is a different, equally valid fixture style.

### 3. Preflight real-CLI fixtures — `tests/test_parallel_admission_preflight.sh:73,87`
This is a subprocess CLI, so there is no clock to pin. Define
`NOW_TS="$(date '+%Y-%m-%d %H:%M')"` once near `TMPROOT`, using the repo idiom
(`tests/test_plan_verified.sh:34`). Add a comment giving the t1799 reason, and
interpolate it into both `printf` frontmatters (`updated_at: %s` + arg).
`parse_ts` parses naive local time and `date` prints local time, so they agree.

### 4. Docstring — `.aitask-scripts/lib/shortcut_scopes.py:80-81`
Replace the false sentence with the actual invariant:
> Basenames DO collide across these dirs: `applink/` and `chatlink/` both ship
> `paths.py` and `audit.py`. It is safe only because chatlink imports its own
> modules package-qualified (`chatlink.paths`), so it never binds the bare
> `sys.modules["paths"]` / `["audit"]`, and `applink_app` inserts its own
> directory at `sys.path[0]` before its flat `from paths import …`.
> `tests/test_board_package_contract.py` pins the set (`KNOWN_COLLISIONS`) so it
> cannot grow unnoticed.

Also update the `KNOWN_COLLISIONS` comment in
`tests/test_board_package_contract.py:62-66` so it points at that docstring as
the documented, accepted latent state. The pin itself stays.

**Decision: document, don't rename.** Renaming either side is a wide change for
a collision that loads cleanly: chatlink's `paths` is imported by `chatlink_app`
plus 5 test scripts, and applink imports both flat across 7 modules.

## Verification
- After Step 0: collect test 101 passed, and `test_prompt_detection.py` passes.
  That is the baseline. There is no "was 4 failed" claim, since upstream owns
  that fix.
- Step 1 red proof: the caller-level test fails (`[None]`) before the forwarding
  edits and passes after.
- Step 2: `FixtureClockTests` 1–3 pass. Test 3 *is* the red proof: it shows the
  unpinned clock produces the original rot.
- Step 3 red proof: run a scratch copy of the preflight script with `updated_at`
  set more than 14 d back. Expect the CONFLICT/UNCHECKABLE asserts to fail. Then
  run the real file: all pass. No `git stash`/`git restore` anywhere.
- `pytest -q tests/test_parallel_admission_collect.py tests/test_roadmap_run.py tests/test_parallel_admission_purity.py tests/test_board_package_contract.py tests/test_shortcut_scopes.py`;
  `bash tests/test_parallel_admission_preflight.sh`;
  `bash tests/test_parallel_admission_cli.sh`;
  `bash -n tests/test_parallel_admission_preflight.sh`.
- Full suite: `bash tests/run_all_python_tests.sh` (read the last-line verdict).

## Post-implementation
Step 9 of the task workflow: current-branch mode (fast profile), so no merge.
Build verification/gates, then archival via `aitask_archive.sh 1799`.

## Risk

### Code-health risk: low
- Step 0 adds a merge commit to the shared `main` and changes working-tree files that concurrent sessions read · severity: low · → mitigation: none (addressed in Step 0: user-chosen merge rewrites no SHA, clean-tree precondition checked twice, conflict-free trial merge in a throwaway worktree, git refuses rather than clobbers uncommitted foreign edits, no push)
- `collect_population` gains a kwarg used by `replay` and the roadmap · severity: low · → mitigation: none (the default is unchanged; no test stubs its signature)

### Goal-achievement risk: low
- The preflight 2026-09-16 rot comes from reading `tier()`, not from an observed failure · severity: low · → mitigation: none (the Step 3 red proof confirms it before commit)

## Post-Review Changes

### Change Request 1 (2026-09-14 17:40)
- **Requested by user:** (1) the inner `collect_population` → `collect(now=now)` handoff had no test: the roadmap test stubs `collect_population`, so dropping the inner forward would pass every test; (2) the negative control restored the real clock and assumed the machine date is after the 2026 fixture, so it fails on a historical or time-faked runner.
- **Changes made:** added `FixtureClockTests.test_collect_population_forwards_now_to_the_snapshot`, which pins `now=NOW+60`, deliberately different from the scaffold's frozen clock so a dropped `now` cannot pass by fallback. Replaced `test_an_unpinned_clock_reproduces_the_rot` with `test_a_clock_past_max_claim_age_reproduces_the_rot`, which uses `_FrozenClock(NOW + MAX_CLAIM_AGE_S + 3600)` and asserts that SNAPSHOT equals that instant and that the verdict is exactly `VERDICT_FOR:11|CLEAR_CAVEATED`. Verified: an in-process mutant that drops the inner `now` fails the new test, and `FixtureClockTests` passes with `time.time` patched to 2020-01-01.
- **Files affected:** `tests/test_parallel_admission_collect.py`

## Final Implementation Notes
- **Actual work done:** Step 0 merged `origin/main` into `main` as `c90ae55e8` (`ait: Merge origin/main into main`). No local SHA was rewritten and nothing was pushed. The merge brought in upstream's `_FrozenClock` fix for the 4 original failures (`44f92f5fa`, t1763); the collect test was then 101/101 on the merged tree. After that:
  - `collect_population` gained `now=None` and forwards it to `collect`, and `roadmap_run.run` forwards its own `now`. A caller-level `NowForwardingTests` in `tests/test_roadmap_run.py` covers the outer handoff, and `FixtureClockTests.test_collect_population_forwards_now_to_the_snapshot` covers the inner one.
  - Added behavioral clock guards in `tests/test_parallel_admission_collect.py`: `FixtureClockTests` (fixture freshness at the scaffold clock, SNAPSHOT equals the scaffold `NOW`, and a deterministic aged-clock negative control), plus a freshness test in `ExcludeNoPlanPredicateTests`.
  - `tests/test_parallel_admission_preflight.sh` stamps its fixtures with the current time via `NOW_TS`.
  - Corrected the `shortcut_scopes._ensure_import_paths` docstring, and pointed the `KNOWN_COLLISIONS` comment at it. The pin stays.
- **Deviations from plan:**
  - The merge brought in 5 upstream commits, not 2: t1783, t1784 and t1802 landed during the session. The trial merge was re-run against the new tip before merging.
  - The first merge attempt was blocked because the shared tree had 23 uncommitted paths from concurrent sessions (t1794_2, t1797), `monitor_core.py` among them. I waited until they committed, re-checked, and merged into a clean tree.
  - The plan said the scaffold's `_restore` "re-pins" the clock. It actually restores the real `time` module. After review, the negative control was changed to a frozen aged clock anyway (Change Request 1).
- **Issues encountered:** The original red proofs held: the caller-level test failed with `[None]` before the forwarding edit, and the preflight script with a 44-day-old `updated_at` failed 5 asserts (CONFLICT → CLEAR_CAVEATED, UNCHECKABLE → CLEAR). That confirms the predicted 2026-09-16 09:00 breakage. After review, an in-process mutant that drops the inner `now` fails the new forwarding test, and `FixtureClockTests` passes with `time.time` patched to 2020-01-01. The full Python suite PASSED (runner=pytest) before Change Request 1. CR1 changed only `test_parallel_admission_collect.py`, which re-ran green (128 targeted tests).
- **Key decisions:**
  - Integrated by merge, per the user, rather than by rebase, which would have rewritten 12 unpushed local SHAs.
  - Built on upstream's `_FrozenClock` instead of adding a second clock seam. No AST or structural rule.
  - Documented the applink/chatlink basename collision rather than renaming modules; the blast radius was too wide for a latent issue.
- **Upstream defects identified:** None
