---
Task: t2060_fix_stale_test_guards_boardgroup_and_unscoped_commit.md
Base branch: main
Output branch: main
---

# t2060 — Fix stale test guards (boardgroup driver guard; unscoped-commit scope)

## Context

t1739's regression sweep found two test failures unrelated to its change:

1. `tests/test_aitask_merge_boardgroup.sh` Test 3 greps `aitask_sync.sh` for
   `"$_MERGE_PYTHON" "$_MERGE_SCRIPT"` driver invocations. t1727 (66da94134)
   moved the merge-driver call into `lib/task_automerge.sh`, renamed the
   variables to `_AIT_AUTOMERGE_PYTHON` / `_AIT_AUTOMERGE_SCRIPT`, and split the
   call over backslash continuations, so `base_args` is on a different physical
   line from the invocation. The guard now finds 0 invocations and fails its
   own "not vacuous" floor. Reproduced: `17 passed, 1 failed`.
2. `tests/test_no_unscoped_task_commit.sh` "canonical teaching skill is in
   scope" — **already fixed on main** by t2053 (b6d1e4118: `md_has` was
   `printf | grep -q`, which SIGPIPEs under `pipefail` and returns 141 for a
   present name). `.claude/skills/ait-git/SKILL.md` exists and is enumerated;
   current run: `103 passed, 0 failed`. No change needed — record this in the
   Final Implementation Notes.

## Change — `tests/test_aitask_merge_boardgroup.sh` Test 3 only

Replace the hardcoded-file, single-line grep with a call-site discovery that
survives both relocation and line continuation:

- `logical_lines <file>` — awk that joins backslash-continued lines, so an
  invocation whose flags sit on a continuation line is matched whole.
- `driver_invocations <file>` — discovers the variables that file assigns to
  `…/aitask_merge.py` (`grep -oE '<ident>="[^"]*aitask_merge\.py"'`), then
  prints each logical line containing `"$<…PYTHON…>" "$<that var>"`.
  (Discovery keys on the driver's real path, not on a variable name, so a
  rename cannot make it vacuous again.)
- `count_driver_sites <files…>` — echoes `<invocations> <with_base>`, where an
  invocation counts as with-base if the logical line contains `base_args` or
  `--base-file` (same predicate as the old guard).

Assertions:

1. **Planted control first** (proves the matcher discriminates and joins
   continuations): a temp `.sh` with `_X_SCRIPT=".../aitask_merge.py"`, one
   split invocation passing `${base_args[@]…}` on the continuation line, and
   one split invocation without it → expect `2 1`.
2. Real tree: scan every `*.sh` under `.aitask-scripts/` (find, recursive).
   - at least one invocation (not vacuous);
   - `lib/task_automerge.sh` is among the sites (scope assertion in the other
     direction — the canonical call site must not silently drop out);
   - every invocation passes a base (`invocations == with_base`).

Update the Test 3 echo header to "every recognized merge-driver invocation
passes a base". The file uses top-level asserts (no subshells), so no counter
opt-in is needed.

**Coverage boundary — documented, not widened (review finding).** Discovery is
per-file and shape-specific, so it does NOT see:
- a caller that uses a driver-path variable assigned in a *different* file
  (e.g. sourcing `lib/task_automerge.sh` and reusing `_AIT_AUTOMERGE_SCRIPT`);
- an invocation whose interpreter variable name lacks `PYTHON`, or that calls
  the script by literal path / through an array.

In those cases the floor and the canonical-site assertion still pass. So:
- a comment block above the helpers states the **supported invocation shape**
  (`"$<…PYTHON…>" "$<var>"` where `<var>` is assigned `…/aitask_merge.py` in the
  same file, flags possibly on continuation lines) and the omissions above;
- assertion labels say "every *recognized* invocation", never "every
  invocation";
- the planted control is described as proving the matcher on the supported
  shape only.

Exhaustive discovery (cross-file variable set, or a tripwire that fails on
any `aitask_merge.py` reference the guard cannot classify) is **separate
work**: recorded below as an `after` risk mitigation, which Step 8d creates as
a standalone follow-up task carrying the two omission classes above as its
acceptance cases.

Dry-run of the discovery on the current tree (read-only) found exactly one
site: `lib/task_automerge.sh` with `base_args` on the joined line.

## Verification

- `bash tests/test_aitask_merge_boardgroup.sh` → all pass (18+ assertions).
- Mutant check (scratch copy, not the shared tree): drop the
  `${base_args[@]+…}` from a copy of `task_automerge.sh` and run the
  `count_driver_sites` against it → `with_base` < `invocations`.
- `shellcheck tests/test_aitask_merge_boardgroup.sh` (no new warnings).
- `bash tests/test_no_unscoped_task_commit.sh` → still `ALL TESTS PASSED`.

## Step 9

Current-branch mode: commit code (`bug: … (t2060)`) and plan separately, then
archive via `aitask_archive.sh 2060`.

## Risk

### Code-health risk: low
- Guard coverage is shape-limited (per-file variable discovery, `PYTHON`-named interpreter); an unrecognized future call site would be silently omitted · severity: low (boundary documented + assertion labels qualified in this plan) · → mitigation: t2069

### Goal-achievement risk: low
None identified.

### Planned mitigations
- timing: after | name: exhaustive_merge_driver_guard_discovery | type: test | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: guard coverage is shape-limited (code-health) | desc: Make the boardgroup merge-driver guard exhaustive: discover driver-path variables across sourced files and fail on any aitask_merge.py reference the guard cannot classify (non-PYTHON interpreter var, literal path, array call) | created: t2069

## Final Implementation Notes
- **Actual work done:** Rewrote Test 3 of `tests/test_aitask_merge_boardgroup.sh`. It now discovers merge-driver call sites in every `*.sh` under `.aitask-scripts/` by keying on variables assigned `.../aitask_merge.py`. Backslash continuations are joined before matching (`logical_lines` / `driver_invocations` / `count_driver_sites`). Added a planted control (2 split invocations, 1 with a base → `2 1`), a not-vacuous floor, a canonical-site assertion for `lib/task_automerge.sh`, and the every-recognized-invocation-has-a-base check. The supported invocation shape and coverage boundary are documented in a comment above the helpers. Result: 20/20 pass (was 17/18).
- **Deviations from plan:** None. The review finding about discovery coverage was folded into the plan before approval (documented boundary, "recognized" wording, and an `after` mitigation for exhaustive discovery).
- **Issues encountered:** Defect 2 (`test_no_unscoped_task_commit.sh`, "canonical teaching skill is in scope") was already fixed on main by t2053 (b6d1e4118). `md_has` used `printf | grep -q`, which hit SIGPIPE under `pipefail` and returned 141 for a name that was present. Re-run: 103/103 pass. No change made.
- **Key decisions:** Discovery keys on the driver's path rather than on a variable name, so the call site can move or be renamed without the guard going vacuous. Mutant check on a scratch copy of `task_automerge.sh` with `base_args` removed gives `1 0` (caught), against `1 1` for the real file.
- **Upstream defects identified:** None
