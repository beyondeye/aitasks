---
Task: t2304_change_surface_no_renames_for_rename_old_path.md
Base branch: main
Output branch: main
---

# t2304 — change surface: report both halves of a rename (`--no-renames`)

## Context

`aitask_change_surface.sh` is the testmap selector's change-surface intake
(n014 `assumption_change_surface_is_intake`). The engine (aitasks_go#t61_1)
escalates a listed path that is missing from the working tree to a full run,
because a deleted imported file drops every relationship the scanner derived
from it. Git's default rename detection prints only the **new** path of a
rename, in both reads the script makes:

- `current_dirty_set()` — `git diff --name-only HEAD` (line 132). It feeds
  `capture`/`baseline` (`DIRTY_AT_CLAIM`) and `list` pass B.
- `cmd_list` pass A — `git show --name-only --format= <sha>` (line 278).

So the old path of a renamed file never reaches the intake. Dependents that
still reference it are never selected, and nothing escalates. The advisory note
from aitasks_go#t61_1 reproduced this with the real script and found that
emulating `diff.renames=false` gives the intended shape with no new prefixes.

## Implementation

### 1. `.aitask-scripts/aitask_change_surface.sh`

- Line 132: `git diff --no-renames --name-only HEAD -- . …`
- Line 278: `git show --no-renames --name-only --format= "$sha"`
- Add a comment block above `current_dirty_set()` (and point to it from pass A)
  that says:
  - why the flag is there: a rename's old path must reach the intake, because
    the selector escalates absent paths;
  - that both reads must carry it, so `baseline` and `list` agree;
  - that `--no-renames` also overrides a user's `diff.renames=copies` config.
- Help text: one sentence under the `list` output section: "A rename is
  reported as two ordinary path lines, its old path and its new path, each
  classified on its own." No new prefixes and no classification changes.
  `read_plan_scope` already keeps a dirty token that no longer exists on disk,
  so an old path the plan names classifies as `TASK`.

`ls-files --others` is unaffected: untracked files are never rename-paired.

### 2. `tests/test_change_surface.sh` — new section 10, all through the real script

The repo's git config is pinned with `git -c diff.renames=true` in each
fixture-validity control. Without that pin, a user's global config could make
the control vacuous.

- **10a. Staged rename (`git mv`)**, one fixture covering all three classes
  for the old half:
  - Commit `ra.sh`, `na.sh` and `pa.sh` on top of `new_repo` (10b's
    `ua.sh`/`uo.sh`/`un.sh` go in their own fixture). Each file gets distinct
    content, so git cannot pair the wrong files.
  - Plan p20 names `ra.sh` and `rb.sh`.
  - Before capture, run `git mv pa.sh pb.sh` (baseline-only). Then
    `capture 20`, `git mv ra.sh rb.sh` (plan-named) and `git mv na.sh nb.sh`
    (neither).
  - **Fixture-validity control:** `git -c diff.renames=true diff --name-only
    HEAD` lists `rb.sh` but not `ra.sh`. This proves git really rename-pairs in
    this fixture, so the positive checks are not vacuous.
  - Expected lines (positive `assert_line` checks):

    | Old half | New half |
    |---|---|
    | `TASK:ra.sh` | `TASK:rb.sh` |
    | `OTHER:pa.sh` | `OTHER:pb.sh` |
    | `UNKNOWN:na.sh` | `UNKNOWN:nb.sh` |

  - Negative `assert_no_line` checks, applied **only** to paths with no
    plan-named claim. The old half of a rename the plan does not own must never
    be attributed: `TASK:pa.sh` (baseline-only) and `TASK:na.sh` (owned by
    nobody) must be absent. `ra.sh` gets **no** negative, because
    `TASK:ra.sh` is the required positive.

- **10b. Unstaged rename (`mv`, new file untracked)**: the same three-class
  layout, with its own names written out:
  - Plan p22 names `ua.sh` and `ub.sh`.
  - Before capture, run `mv uo.sh up.sh` (baseline-only). Then `capture 22`,
    `mv ua.sh ub.sh` (plan-named) and `mv un.sh um.sh` (neither).
  - Positives: `TASK:ua.sh`, `TASK:ub.sh`, `OTHER:uo.sh`, `OTHER:up.sh`,
    `UNKNOWN:un.sh`, `UNKNOWN:um.sh`.
  - Negatives: `TASK:uo.sh` and `TASK:un.sh` absent. `ua.sh` gets none.
- **10c. Committed rename**: `git mv ca.sh cb.sh && git commit -m "refactor:
  rename (t21)"`.
  - Control: `git -c diff.renames=true show --name-only --format= HEAD` lists
    only `cb.sh`.
  - Expect `COMMITTED:ca.sh` and `COMMITTED:cb.sh`.
- **10d. Plain deletion** (regression guard): `git rm -q dd.sh` with no plan
  naming it → `UNKNOWN:dd.sh`. An unstaged `rm de.sh` → `UNKNOWN:de.sh`.
- **10e. `baseline` agrees with `list` on the same tree**:
  - Make the staged and unstaged pre-claim renames, `capture`, then without
    further work compare the sorted path set from `baseline` (`DIRTY_AT_CLAIM:`
    stripped) with the sorted path set from `list` (class prefix stripped).
    They must be equal and include both halves of each rename.
  - Also assert `CAPTURED:4`.

Update the file's header "Covers:" list with the rename cases. The file runs
everything at top level (no `( … )` assert subshells), so the file-backed
counters are not needed.

## Consumer review (one more path per rename): outcomes to record

| Consumer | How it reads the surface | Effect |
|---|---|---|
| shadow scope (`lib/shadow_scope.py::claim_baseline`) | `baseline` → `DIRTY_AT_CLAIM:` set | gains the old half of a pre-claim rename, which is correct: it really was dirty at claim. Note: `dirty_channels()` makes its own porcelain `git diff [--cached] --name-only -z` reads with renames on by default, the same blind spot outside this script → follow-up (below) |
| plan-paths seam (`tests/test_plan_paths_seam.sh`) | pins the script's own `tokens="$(grep -oE` grammar line | unaffected (no grammar change) |
| docs_updated gate skill (`aitask-gate-docs-updated`) | `list` classes | an unplanned rename now shows two `UNKNOWN:` rows instead of one. This is intended: the old path is real change surface and the gate asks rather than guesses |
| parallel admission (`aitask_parallel_admission.sh`, `lib/parallel_admission*.py`) | does not call this script (grep) | none |
| revert analyze (`aitask_revert_analyze.sh`) | does not call this script; already uses `--no-renames` itself | none; the two are now consistent |
| `_DIGEST_EXCLUDES` drift guard (test §8) | `EXCLUDES=` array text | unchanged |
| `aitask_pick_own.sh` capture | stdout discarded | none |

## Out of scope → follow-up tasks (offered at Step 8)

From the t61_1 note, item 3:
1. git C-quotes non-ASCII and special paths (`core.quotePath`), so such a path
   never matches a plan token or a baseline line. The fix is `-z` reads or
   `-c core.quotePath=false`, plus decoding.
2. The plan-token regex has no `|` in its class, so `docs/a|b.md` splits and is
   never attributed.

From the consumer review:
3. `shadow_scope.dirty_channels` loses rename old paths in the same way.

These are separate defects with their own blast radius, so they are not folded
into this low-effort fix.

## Post-implementation

- Step 9: archival via the normal workflow. Commit `bug: … (t2304)`.
- After landing:
  - Re-sync the script copy into aitasks_go by the normal framework sync.
  - Send `ait note --project aitasks_go` to t61_1 and t61_5 with the landing
    commit and the real `list` output of fixture 10a and 10c, so
    `producer_norenames.txt` can be replaced. The fixture lives in aitasks_go,
    so it is its owner's to edit.

## Verification

- `bash tests/test_change_surface.sh`: all existing cases plus section 10 pass.
- Pre-fix control: run section 10 against the unpatched script. The old-half
  assertions (`TASK:ra.sh`, `OTHER:pa.sh`, `UNKNOWN:na.sh`, `COMMITTED:ca.sh`,
  the 10e set equality) fail, and 10b/10d pass both before and after (they are
  regression guards). Do this in an isolated copy, never by stashing or
  restoring the shared tree.
- `bash tests/test_plan_paths_seam.sh`, `bash tests/test_shadow_scope.sh`.
- `shellcheck .aitask-scripts/aitask_change_surface.sh`.

## Risk

### Code-health risk: low
None identified. The change is two flags on two reads in one script, with no
grammar or classification change. The consumer review above found no consumer
that parses rename-specific output.

### Goal-achievement risk: low
None identified. The engine's own emulation already showed the shape this
change produces, and every acceptance case runs through the real script with a
fixture-validity control.

## Post-Review Changes

### Change Request 1 (2026-11-15 22:45)
- **Requested by user:** the section-10 rename controls pinned `diff.renames=true`
  only on their own comparison command, while `capture`/`list` ran the producer
  under inherited git config. Under a user's `diff.renames=false` the unpatched
  producer never hides an old half, so removing both `--no-renames` flags could
  escape every assertion. Pin rename detection for the producer too, and keep the
  unpatched-producer failure check.
- **Changes made:** `tests/test_change_surface.sh` §10 now routes the controls
  and every producer call through one environment (`RENAMES_ON`:
  `GIT_CONFIG_COUNT` → `diff.renames=true`, `-u GIT_CONFIG_PARAMETERS`) via
  `rn_cs` / `rn_git`. A passing control therefore vouches for exactly the config
  the producer saw.
- **Files affected:** `tests/test_change_surface.sh`
- **Verification matrix** (82 assertions):

  | producer | inherited cfg | `GIT_CONFIG_GLOBAL` renames=false | `GIT_CONFIG_PARAMETERS` renames=false |
  |---|---|---|---|
  | patched | 82/82 | 82/82 | 82/82 |
  | unpatched | 76/82 (6 fail) | 76/82 (6 fail) | 76/82 (6 fail) |

  Escape reproduced with the pin removed (`RENAMES_ON=(env)`): unpatched under
  global renames=false → 80/82; only the 2 fixture-validity controls fail, and
  every producer assertion passes.

## Final Implementation Notes
- **Actual work done:** `--no-renames` on both git reads in
  `.aitask-scripts/aitask_change_surface.sh`: `current_dirty_set()` (the dirty set
  behind capture/baseline and list pass B) and pass A's `git show`. Added a
  comment block explaining why both reads must carry it, and one help line saying
  a rename is two ordinary path lines. `tests/test_change_surface.sh` §10 has 24
  new assertions, all through the real script: staged (10a) and unstaged (10b)
  renames with the old half plan-named / baseline-only / unowned; a committed
  `(t21)` rename (10c); staged and unstaged plain deletions (10d); and
  baseline ≡ list path-set consistency with `CAPTURED:4` (10e).
- **Deviations from plan:** (1) The planning review found contradictory 10a
  negatives (a `TASK:ra.sh` negative against the required positive). The
  negatives now cover only the unclaimed halves (`pa`/`na`, `uo`/`un`).
  (2) The code review found the controls were pinned but the producer was not.
  Fixed with the shared `RENAMES_ON` environment, see Post-Review Change 1.
- **Issues encountered:** Before the fix, 10e's `baseline == list` set equality
  passed: both were consistently incomplete. The exact-set assertion
  (`ea eb ec ed`) and `CAPTURED:4` are what catch the defect there.
- **Key decisions:** No new prefixes and no classification change. Each half is
  classified by the existing rules. `read_plan_scope` already keeps a token that
  is dirty but absent on disk, so a plan-named old path is `TASK` with no
  further change. Pre-fix control: exactly 6 assertions fail against the
  unpatched producer (TASK:ra.sh, OTHER:pa.sh, UNKNOWN:na.sh, COMMITTED:ca.sh,
  CAPTURED:4, exact set) under inherited, global-false and `-c false` configs;
  10b/10d pass before and after (regression guards).
- **Consumer review outcome:** as tabled in the plan. No consumer parses
  rename-specific output. The docs_updated gate shows one more `UNKNOWN:` row
  for an unplanned rename's old half, as intended. shadow_scope consumes only
  `baseline` and correctly gains the old half of a pre-claim rename.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/shadow_scope.py:224-225` — `dirty_channels()` reads staged/unstaged with porcelain `git diff [--cached] --name-only -z` (rename detection on by default), so a staged rename's old path is missing from the shadow's own dirty channels; same blind spot as t2304, outside this script.
  - `.aitask-scripts/aitask_change_surface.sh:132,295` — git C-quotes non-ASCII/special paths under the default `core.quotePath`, so such a path can never equal a plan token or a baseline line and is never attributed `TASK` (reported by aitasks_go#t61_1's note).
  - `.aitask-scripts/aitask_change_surface.sh:249` — the plan-token class `[A-Za-z0-9_./-]` excludes `|` (and other legal path bytes), so a plan naming `docs/a|b.md` splits it and the path stays `UNKNOWN` (reported by aitasks_go#t61_1's note).
