---
Task: t1647_1_promote_trail_discovery_seams_to_lib.md
Parent Task: aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Sibling Tasks: aitasks/t1647/t1647_2_trail_schema_merged_from_provenance.md, aitasks/t1647/t1647_3_trail_merge_preflight_helper.md, aitasks/t1647/t1647_4_merge_trails_skill_and_codeagent_op.md, aitasks/t1647/t1647_5_board_bytrail_fold_trails_command.md, aitasks/t1647/t1647_6_merge_trails_docs_website_and_rfc.md, aitasks/t1647/t1647_7_manual_verification_merge_trails.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-02 12:09
---

# Plan: t1647_1 — Promote trail discovery seams to `lib/trail_discovery.py`

**Verify-path re-plan.** The existing plan `aiplans/p1647/p1647_1_*.md` was
re-checked against the live tree. Its anchors are accurate, but three of its
claims are wrong and one is unsafe. This plan supersedes it.

## Context

The trail-merge feature (t1647) needs trail discovery, dedup, overlap
computation and blob loading **outside** the board: the preflight helper
(t1647_3) and, transitively, the `/aitask-merge-trails` skill consume them.
Today they are board-internal functions in
`.aitask-scripts/board/aitask_board.py`. Promote them into a shared lib module
that the board then imports and re-exports, so the skill duplicates nothing and
both surfaces read one definition.

Pure refactor: **zero behavior change**. The board suite is the regression guard.

## Verification findings (what changed vs. the existing plan)

**1. Anchors confirmed.** All 11 named symbols exist, within 1–11 lines of the
plan's estimates (`TRAIL_ARTIFACT_KIND`:1092, `TrailInfo`:1120,
`trail_entry_refs`:1259, `compute_trail_overlaps`:1295, `_trail_owner_rank`:1317,
`dedupe_trail_records`:1330, `_iter_active_task_frontmatter`:1345,
`_iter_trail_frontmatter_records`:1402, `_trail_versions`:1439,
`load_trail_blob`:1454, `discover_trails`:1491).

**2. The move is not contiguous.** Board-only code is interleaved inside the
range and must stay: `TRAIL_WATCH_INTERVAL` / `TRAIL_WATCH_MAX_TICKS` /
`TRAIL_GATHER_SCRIPT` / `TRAIL_CLASSIFICATION_GLYPHS` / `_TRAIL_GHOST_LABELS`
(1094–1117), `TrailEntryView` (1135), `trail_summary_text` (1270). Extract by
symbol, never by line range.

**3. ❌ "Existing `test_board_bytrail_view.py` must pass UNCHANGED" is false —
at THREE seams, not one.** A `patch.object(ab, "<name>", …)` rebinds only the
**board's** name. Every moved function resolves its collaborators in
`trail_discovery`'s namespace, so a board-level patch of any moved symbol stops
intercepting the moment its consumer is also a moved symbol. Three sites qualify
(full sweep in Step 4):

- **`:3380`** `TrailDiscoveryPilotTests.test_s_lists_a_trail_created_while_the_board_was_running`
  (the **t1365 AC1 guard**) patches `ab.load_trail_blob`, then runs the **real**
  `discover_trails` — its comment says so: *"Real discovery this time; only the
  blob subprocess is stubbed."*
- **`:2944`** `TrailDiscoveryFreshnessTests._discover()` centralizes the identical
  `patch.object(self.ab, "load_trail_blob", …)` + real `discover_trails()` pattern
  and is called from **six** tests (`:2958, 2988, 3011, 3029, 3043, 3057`). Worse
  than a slow subprocess: `:2966` asserts `found[0].load_error == ""`, and the
  real `aitask_artifact.sh get` cannot resolve the handle in a synthetic fixture
  tree — so all six **fail outright**. The test's own comment at `:2963` names
  exactly this trap.
- **`:2002`** `test_missing_artifact_script_is_a_clean_retry` patches the
  **constant** `ab.ARTIFACT_SCRIPT` to a nonexistent path to prove the watch
  retries cleanly, then runs the real worker and the real subprocess. Once
  `_trail_versions` moves it reads `trail_discovery.ARTIFACT_SCRIPT`, the patch is
  inert, and the real binary runs. This one is the most dangerous of the three: if
  the real script happens to return an empty listing, `assertEqual(landed[0], [])`
  still **passes — vacuously** — and the missing-binary guard is silently gone.

> **Confirmed by the user:** re-point the patch to the lib module, preserving each
> guard's intent while moving only the seam address. That decision applies to all
> three sites (it was taken on `:3380`; `:2944` and `:2002` are the same defect
> found by a wider sweep). This is a deliberate, assented narrowing of the task's
> "must pass UNCHANGED" criterion to **"every guard must still hold, and still be
> able to fail"** — record it in the Final Implementation Notes.

**4. ❌ `TASKS_DIR` must be resolved lazily — a module-level constant is unsafe.**
The board binds `TASKS_DIR = task_dir()` at import (`:92`), and `task_dir()` reads
`$TASK_DIR` **at call time** (`lib/config_utils.py:83`). `tests/lib/board_fixture.py`
loads the board under a **fresh synthetic module name per fixture tree**
(`aitask_board_fixture_<tag>_<id>`) with `TASK_DIR` set only during `exec_module`.
A canonical `trail_discovery` would be imported **once** for the whole
single-process suite and freeze `TASKS_DIR` to the first tree — silently scanning
the wrong tree in every later test, and defeating this plan's own synthetic-cwd
test. Both lib precedents resolve lazily: `trail_gather._local_dirs()`
(`lib/trail_gather.py:249`) reads env per call, and `archive_iter` takes
`archived_dir` as a parameter.

**5. ⚠️ Dependency source misstated.** `parse_frontmatter` comes from `task_yaml`
(board `:54` block), but `parse_task_filename` comes from **`topic_semantics`**
(board `:941`) — not the `task_yaml` block as the plan says.

**6. ℹ️ `_iter_active_task_frontmatter` has exactly one real caller** (`:1426`).
The `:792` hit is a **comment** inside `Task.save`, not a call; it must be
re-pointed at the new module.

**7. ℹ️ Sequencing constraint satisfied.** The parent pinned "sequence the board
children after t1603_4 lands" — t1603_4 is archived
(`aitasks/archived/t1603/t1603_4_*.md`).

**8. ⚠️ `aitask_board.py` has uncommitted changes from a concurrent session**
(+12 lines: an import at `~:31`, a method at `~:12429`). Disjoint from the trail
region, but it means **never** `git restore`/`stash`/`checkout` this file, and
commit by explicit path only.

## Steps

### 1. Create `.aitask-scripts/lib/trail_discovery.py`

Move these, **docstrings and comments intact** (they carry load-bearing history —
the t1365 re-read-from-disk rationale, the RFC §12 fail-closed contract):

`TRAIL_ARTIFACT_KIND`, `ARTIFACT_SCRIPT`, `TrailInfo`, `trail_entry_refs`,
`compute_trail_overlaps`, `_trail_owner_rank`, `dedupe_trail_records`,
`_iter_active_task_frontmatter`, `_iter_trail_frontmatter_records`,
`_trail_versions`, `load_trail_blob`, `discover_trails`.

Module docstring records: cwd = repo root (the `trail_gather.py` convention), and
the read-only contract (only `artifact get` / `artifact versions` are spawned).

Imports: `from task_yaml import parse_frontmatter`,
`from topic_semantics import parse_task_filename` (per finding 5),
`from archive_iter import iter_archived_frontmatter`, `import trail_schema`,
`from config_utils import task_dir`.

**Resolve the task dir lazily** (finding 4) — a `_tasks_dir()` helper calling
`task_dir()` per call, mirroring `trail_gather._local_dirs()`. Replace the two
uses: `TASKS_DIR.glob(pattern)` in `_iter_active_task_frontmatter` (`:1389`) and
`TASKS_DIR / "archived"` in `_iter_trail_frontmatter_records` (`:1434`). Do **not**
bind a module-level `TASKS_DIR`.

### 2. `_task_id_sort_key` → `topic_semantics` (user-confirmed)

Board-local at `:620`, used by `_trail_owner_rank` (`:1327`, moving) **and** by
board code at `:2411` (not moving). It is generic task-id parsing, and
`topic_semantics` already owns `parse_task_filename` / `task_anchor_id` /
`task_own_id` — so this costs **zero new import edges** and avoids duplicating it.
Add it there; the board picks it up via its existing `:941` import block (both
remaining uses are after `:941`), and `trail_discovery` imports it alongside
`parse_task_filename`.

### 3. Board adoption (re-export is mandatory)

Delete the moved definitions and add, next to the existing lib imports
(`import trail_schema`, `:33`):

```python
import trail_discovery          # module handle: the :3380 patch seam
from trail_discovery import (
    TRAIL_ARTIFACT_KIND, ARTIFACT_SCRIPT, TrailInfo, trail_entry_refs,
    compute_trail_overlaps, _trail_owner_rank, dedupe_trail_records,
    _iter_active_task_frontmatter, _iter_trail_frontmatter_records,
    _trail_versions, load_trail_blob, discover_trails,
)
```

Re-export is required: the tests read these as `ab.<name>` and the board itself
calls them from outside the region (`discover_trails`:11925, `load_trail_blob`:12055,
`_trail_versions`:9089/12097/12129/12144/12264/12281, `TrailInfo`:4417/4444,
`trail_entry_refs`:4583, `compute_trail_overlaps`:11980). Keep
`trail_summary_text`, `run_trail_drift`, `TrailEntryView`, lane building and
glyphs in the board. Re-point the `:792` comment (finding 6).

Add the import **without disturbing** the concurrent session's `:31` edit
(finding 8).

### 4. Audit every board-namespace patch against the internal call edges

**Sweep method — all three axes, or the audit misses seams:**

1. Every moved symbol, **constants included** (`ARTIFACT_SCRIPT`,
   `TRAIL_ARTIFACT_KIND`) — not just the functions. A patched constant is read
   through the *defining* module exactly as a function is.
2. Both receiver spellings — `patch.object(ab, …)` **and**
   `patch.object(self.ab, …)`, plus any local alias. Matching only `ab,` is what
   hid `:2944`.
3. The whole `tests/` tree, not just `test_board_bytrail_view.py`.

```bash
command grep -rn 'patch.object([A-Za-z_.]*, "\(TRAIL_ARTIFACT_KIND\|ARTIFACT_SCRIPT\|TrailInfo\|trail_entry_refs\|compute_trail_overlaps\|_trail_owner_rank\|dedupe_trail_records\|_iter_active_task_frontmatter\|_iter_trail_frontmatter_records\|_trail_versions\|load_trail_blob\|discover_trails\|_task_id_sort_key\)"' tests/
```

Internal edges: `discover_trails` → {`dedupe_trail_records`,
`_iter_trail_frontmatter_records`, `load_trail_blob`}; `load_trail_blob` →
{`_trail_versions`, `ARTIFACT_SCRIPT`, `trail_schema`}; `_trail_versions` →
`ARTIFACT_SCRIPT`; `dedupe_trail_records` → `_trail_owner_rank`;
`_iter_trail_frontmatter_records` → {`_iter_active_task_frontmatter`, `TrailInfo`,
`TRAIL_ARTIFACT_KIND`}.

A site breaks **iff** the patched symbol moved **and** its consumer on that code
path is also a moved symbol. Patches consumed by *board* code are unaffected.

**Must be re-pointed to the lib module (3 sites):**

| Site | Patched | Consumer | Effect if left |
|---|---|---|---|
| `:2002` | `ARTIFACT_SCRIPT` (const) | real `_trail_versions` | real binary runs; may pass **vacuously** |
| `:2944` | `load_trail_blob` (`self.ab`) | real `discover_trails` ×6 tests | `load_error != ""` → **6 failures** |
| `:3380` | `load_trail_blob` | real `discover_trails` | real `artifact get` subprocess |

Fixing `:2944` fixes all six of its callers at once — patch the helper, not the
tests. Each edit changes only the receiver
(`ab` → `ab.trail_discovery`), which is why Step 3 must also
`import trail_discovery` so the attribute is reachable.

**Verified unaffected (no edit):**

- `ab.load_trail_blob` at `:1934` and `:2431` — consumer is the board's
  `_reload_active_trail` (`:12055`), a board-namespace call. For `:2431` also
  confirm `_enter_live_bytrail`'s `_set_base_filter("bytrail")` does not reach
  real discovery (`_trail_infos` is pre-set to `[]`).
- All seven `ab._trail_versions` patches (`:1463/1506/1913/1965/2105/2324/2630`) —
  consumers are board watch/baseline methods. Confirm at implementation that none
  drives a **real** `load_trail_blob`, whose internal `_trail_versions` call is
  lib-resolved.
- All eight `ab.discover_trails` patches (`:585/3098/3118/3151/3218/3277/3309/3360`)
  — consumer is board code at `:11925`.
- `ReadOnlyNegativeControlTests` — **global** `patch("subprocess.run", …)` is
  cross-module, so the read-only guard keeps working untouched.

**Recurrence guard.** Add a comment at the board's re-export block: these names
are re-exports, and the lib functions call each other in *their own* namespace —
so a test must patch them at `trail_discovery`, never at the board. Without it the
next such test fails the same way, and (as `:2002` shows) may do so silently.

**Prove each re-pointed guard can still fail.** For all three, temporarily break
the production path and confirm the test goes red — a patch pointed at the wrong
module and a patch pointed at the right one look identical while the code is
correct. `:2002` in particular passed vacuously *because* nothing forced it to
discriminate.

### 5. New `tests/test_trail_discovery.py`

Imports the lib module directly — no board, no Textual:

- `_trail_owner_rank` dedup precedence: active > active-folded > archived; tie →
  lowest id (synthetic `TrailInfo` records).
- `compute_trail_overlaps` on divergent membership (shared + unshared refs; entry
  key is `task`).
- `trail_entry_refs` shape.
- `discover_trails` against a synthetic project dir (tmp cwd with `aitasks/` +
  `aitasks/archived/`, owners carrying `artifacts:` entries): handle dedup across
  owners, archived-owner flag, and `unreadable` reporting — pin **both** failure
  shapes (`parse_frontmatter` raising, and returning `None`).
- `load_trail_blob` fail-closed with `subprocess.run` mocked: `doc=None`,
  non-empty `error`, versions fallback attempted.
- **A negative control for finding 4:** run discovery under two different tmp
  trees in one process and assert the second sees the second tree. This fails
  against a module-level `TASKS_DIR` and passes against the lazy resolver — it is
  the only thing that can catch the contamination bug.

### 6. Run the guards

```bash
bash tests/run_all_python_tests.sh --test-dir tests
```

Verdict = **last stderr line** only (`PYTHON SUITE: PASSED|FAILED`). Piping
discards the status — use `set -o pipefail` or `${PIPESTATUS[0]}`.

## Verification

- `tests/test_trail_discovery.py` green, including the two-tree negative control.
- `tests/test_board_bytrail_view.py` green — `ReadOnlyNegativeControlTests`, the
  boot-phase spawn control, the t1365 AC1 discovery test (`:3380`), all six
  `TrailDiscoveryFreshnessTests` cases, and `test_missing_artifact_script_is_a_clean_retry`
  (`:2002`) in particular. For the three re-pointed seams, confirm each still
  **fails** when its production path is broken.
- Full python suite green.
- `ait board` boots and `z` (By-Trail) renders the live trails as before (spot
  check; the t1647_7 MV sibling re-verifies).

## Risk

### Code-health risk: **medium**

- Extracting from a 14k-line load-bearing TUI while **another session holds
  uncommitted edits** in the same file · severity: medium · → mitigation: inline
  pre-phase *snapshot-board*
- Silent cross-test tree contamination if `TASKS_DIR` is bound at module import
  · severity: high · → mitigation: inline post-phase *two-tree-control* (Step 5)
- A moved-symbol patch seam silently stops intercepting — **confirmed at 3 sites**,
  one of which (`:2002`, a patched *constant*) would then pass **vacuously** and
  retire a real guard with no failure to notice · severity: high · → mitigation:
  inline phase *patch-audit* (Step 4), whose three-axis sweep and
  can-it-still-fail check are what make the seam visible

### Goal-achievement risk: **low**

The goal — one shared module that t1647_3 and `/aitask-merge-trails` can import —
is delivered directly by the move, and every symbol and dependency has been
verified against the live tree. No goal-achievement risk identified beyond the
assented test-contract deviation in finding 3 (3 seam re-points), which is
mechanical and does not change what the module delivers.

### Pre-phase (risk mitigations)

- **snapshot-board** — before editing, copy `aitask_board.py` to the scratchpad as
  a baseline. Never `git restore` / `stash` / `checkout` it: that would destroy the
  concurrent session's uncommitted work.

### Post-phase (risk mitigations)

- **two-tree-control** — the second half of Step 5's negative control.
- Commit by **explicit path** only, and verify `git commit --stat` lists exactly
  the intended files.

## Pinned (from the parent plan — not re-decided)

- No `.sh` entry point in this child; t1647_3 owns the whitelisted wrapper.
- The board keeps behavioral ownership of rendering; the lib owns
  discovery / dedup / overlap / load only.

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/lib/trail_discovery.py` (291 lines)
  holding the 12 promoted symbols; `_task_id_sort_key` went to
  `lib/topic_semantics.py` instead. `aitask_board.py` lost 253 lines and gained
  an `import trail_discovery` + re-export block. Re-pointed 3 patch seams in
  `tests/test_board_bytrail_view.py` and added `tests/test_trail_discovery.py`
  (26 tests). Extraction and deletion were done programmatically via `ast` rather
  than by hand, and verified two ways: the moved bodies are **byte-identical** to
  the pre-change file (modulo the two intended `TASKS_DIR` → `_tasks_dir()`
  rewrites), and the board's top-level symbol set lost **exactly** those 13 names
  and nothing else.

- **Deviations from plan:** Three, all corrections of plan claims that turned out
  to be wrong when tested:
  1. **The planned two-tree negative control was vacuous.** Proven by mutation:
     freezing `_tasks_dir()` did NOT fail it. `task_dir()` returns the *relative*
     `Path("aitasks")` by default, so a frozen value keeps resolving correctly
     after a `chdir` — cwd is not a discriminating axis. The real vector is the
     `TASK_DIR` **value**, which five board test modules
     (`test_board_archived_relation_lookup`, `test_board_refresh_degrade`,
     `test_board_decref_doomed_attachments`, `test_board_columns_seam`,
     `test_board_movement`) set to **absolute** temp-tree paths. The control now
     varies `TASK_DIR` per tree; both tests in `TaskDirResolutionTests` fail
     against the frozen mutant and pass against the per-call resolver. Finding 4's
     *mechanism* (stated as "the fixture freezes to the first tree via cwd") was
     therefore wrong even though its *conclusion* — resolve lazily — was right.
  2. **The seam severities were overstated in both directions** (measured by
     reverting each receiver and running the tests):
     - `:2944` — **1 of 7** tests fails, not "all six". Only
       `test_discovery_sees_frontmatter_written_after_the_manager_was_built`
       asserts `load_error == ""`; the other five assert on handles, which still
       arrive, so they silently lose their stub instead of failing.
     - `:3380` — passes under the revert; it spawns real subprocesses rather than
       failing. A silent loss of isolation, not a breakage.
     - `:2002` — passes under the revert, but NOT for the reason the plan gave.
       `tests/lib/board_fixture.py:78` **deliberately** omits `.aitask-scripts`
       from fixture trees, so `ARTIFACT_SCRIPT` points at a missing file with or
       without the patch. The patch was never what made the binary missing, so
       this seam was never the "most dangerous" one — its discriminating power
       came from the fixture all along.
     All three re-points are still correct (each restores the seam the test says
     it is using), but only `:2944` was a real failure.
  3. `_task_id_sort_key` landed in `topic_semantics` rather than
     `trail_discovery` (user-confirmed at planning): it is generic task-id
     parsing, `topic_semantics` already owns `parse_task_filename`, and
     `trail_discovery` imports from there anyway — so it costs zero new import
     edges and avoids putting a general helper in a trail-specific module.

- **Issues encountered:**
  - A first mutation probe appeared to show the `:2002` guard surviving a broken
    production path. The mutation had not actually landed: `FileNotFoundError` is
    a **subclass of `OSError`**, so removing it from
    `except (TimeoutExpired, FileNotFoundError, OSError)` changed nothing. Re-run
    with `except subprocess.TimeoutExpired` only, and the propagation was verified
    directly before trusting either result.
  - A `cd` inside one Bash step persisted into later steps and made relative paths
    resolve from `.aitask-scripts/lib/`, briefly making `topic_semantics.py` look
    deleted. Nothing was lost; absolute paths used afterwards.
  - `main` advanced to v0.34.0 mid-task and a concurrent session committed its
    board edits as `7ed466df6` (t1599_3). The board file was snapshotted to the
    scratchpad before editing and never `git restore`/`stash`-ed, so that
    session's uncommitted work was preserved; the symbol-set check above confirms
    the extraction did not disturb it.

- **Key decisions:**
  - `_tasks_dir()` is a function, not a module constant — matching
    `trail_gather._local_dirs()` and `archive_iter`'s parameterised
    `archived_dir`. `TASKS_DIR` is deliberately absent from the module, and
    `ReExportContractTests.test_no_module_level_task_dir_constant` pins that.
  - The board's re-export block carries a comment stating that these names are
    re-exports and that tests must patch them on `trail_discovery` — the seam is
    invisible otherwise, and (per `:2002`) a wrongly-aimed patch can pass.
  - Deletion and extraction were driven by `ast` line ranges rather than manual
    edits, because the file was being concurrently modified and hand-editing a
    14k-line file across 13 disjoint ranges is where transcription errors live.

- **Upstream defects identified:** None

- **Notes for sibling tasks:**
  - **t1647_3 / the `/aitask-merge-trails` skill:** import
    `discover_trails`, `load_trail_blob`, `dedupe_trail_records`,
    `compute_trail_overlaps`, `trail_entry_refs`, `TrailInfo` and
    `TRAIL_ARTIFACT_KIND` from `trail_discovery`. cwd must be the repo root.
    `discover_trails()` returns `(infos, unreadable)` — **do not treat a
    non-empty `unreadable` as "no trails"**; it is a retryable partial scan
    (t1365). `load_trail_blob` is fail-closed: `doc=None` with a non-empty error,
    never a partial document.
  - **Patching rule for every sibling that writes tests:** these functions call
    each other inside `trail_discovery`. Patch them on `trail_discovery`, never
    on the board — and confirm the patch can still fail, because a wrongly-aimed
    one is indistinguishable from a correct one while the code works.
  - **Do not add a module-level `TASKS_DIR`** (or any cached dir constant) to
    this module; the suite is single-process and `TASK_DIR` genuinely varies.
  - Board-side rendering (`trail_summary_text`, `run_trail_drift`,
    `TrailEntryView`, lanes, glyphs, `TRAIL_WATCH_*`, `TRAIL_GATHER_SCRIPT`,
    `TRAIL_CLASSIFICATION_GLYPHS`) deliberately stayed in the board — t1647_5's
    By-Trail command works against those, not against this module.
  - **Acceptance-criterion narrowing (user-assented):** the task's "existing
    tests pass UNCHANGED" was narrowed to "every guard must still hold, and still
    be able to fail". 3 receivers changed; no test intent was altered.
