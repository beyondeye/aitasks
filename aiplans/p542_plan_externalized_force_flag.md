---
Task: t542_plan_externalized_force_flag.md
Base branch: main
---

# t542: Add `--force` flag to `aitask_plan_externalize.sh`

## Context

`aitask_plan_externalize.sh` copies Claude Code's internal plan file
(`~/.claude/plans/<random>.md`) to the external `aiplans/` location. When
the target plan file already exists it short-circuits with:

```
PLAN_EXISTS:<path>
```

and exits 0 without writing anything (script lines 147–152). This is the
desired behavior for the **Step 8 safety fallback** (idempotent) but breaks
the following flows where the external plan file needs to be refreshed with
the newer internal plan:

- **Step 6 "Verify plan" path** (`planning.md` §6.0, plan_preference=verify):
  an existing plan file is present, Claude re-enters plan mode and may
  revise the plan. On `ExitPlanMode`, re-externalizing is a silent no-op
  and the revisions never reach `aiplans/`.
- **Child task workflow** when `plan_preference_child: verify`
  (active in the `fast` profile, used by default for `pick`): same pattern.
- Any manual re-run of `aitask_plan_externalize.sh` after an in-plan-mode
  revision.

The symptom from the task description is a session log showing the script
being called with an explicit `--internal` path on a child task, producing
`PLAN_EXISTS` instead of updating the plan file.

The fix: add a `--force` flag that bypasses the PLAN_EXISTS short-circuit
and overwrites the existing external plan file. Step 6 callers use
`--force`; Step 8 safety fallback keeps the current idempotent behavior.

## Files to modify

1. `.aitask-scripts/aitask_plan_externalize.sh` — add the flag and overwrite logic.
2. `.claude/skills/task-workflow/plan-externalization.md` — document the flag,
   the new output token, and which caller uses which mode.
3. `tests/test_plan_externalize.sh` — cover the new paths.

Note: `planning.md` delegates to `plan-externalization.md` via the
"Plan Externalization Procedure" reference, so updating the procedure file
is sufficient for Step 6 to pick up the new flag. `SKILL.md` Step 8 also
references the same procedure file but will continue to call without
`--force` (safety fallback is idempotent by design).

## Implementation

### 1. `.aitask-scripts/aitask_plan_externalize.sh`

**Header docs update (lines 11–33):**

- Update the `Usage:` line to include `[--force]`.
- Add the new flag to the `Arguments:` block:
  ```
  --force              Overwrite an existing external plan file
                       (default: no-op, emits PLAN_EXISTS)
  ```
- Add the new output token to the "Output lines (exit 0)" block:
  ```
  OVERWRITTEN:<external_path>:<source>
  ```

**`usage()` function (lines 52–68):** Mirror the header-docs changes
(same Arguments line and same Output token).

**Arg parser (lines 70–95):** Add a new case alongside `--internal`.

```bash
TASK_ID=""
INTERNAL_OVERRIDE=""
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --internal)
            [[ $# -ge 2 ]] || die "--internal requires a path argument"
            INTERNAL_OVERRIDE="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            die "Unknown flag: $1"
            ;;
        *)
            [[ -n "$TASK_ID" ]] && die "Unexpected extra argument: $1"
            TASK_ID="$1"
            shift
            ;;
    esac
done
```

**No-op block (lines 147–152) — bypass when `--force`, remember
`EXISTED_BEFORE` for the output token:**

```bash
# --- No-op if already externalized (unless --force) ---

EXISTED_BEFORE=false
if [[ -f "$EXTERNAL_PLAN" ]]; then
    if [[ "$FORCE" != true ]]; then
        echo "PLAN_EXISTS:$EXTERNAL_PLAN"
        exit 0
    fi
    EXISTED_BEFORE=true
fi
```

**Final output line (line 310):** Emit `OVERWRITTEN` when the file was
replaced, otherwise `EXTERNALIZED` (same as today).

```bash
mv "$tmp_target" "$EXTERNAL_PLAN"

if [[ "$EXISTED_BEFORE" == true ]]; then
    echo "OVERWRITTEN:${EXTERNAL_PLAN}:${SOURCE}"
else
    echo "EXTERNALIZED:${EXTERNAL_PLAN}:${SOURCE}"
fi
```

**Notes on behavior preserved:**

- `--force` only bypasses the PLAN_EXISTS short-circuit. It does **not**
  affect source resolution — `MULTIPLE_CANDIDATES`, `NOT_FOUND:no_internal_*`,
  and `NOT_FOUND:source_not_file` still apply. If `--force` is combined with
  an empty `~/.claude/plans/` the script emits `NOT_FOUND:no_internal_files`
  and the existing external file is left untouched (no destructive overwrite
  with empty content).
- When `--force` is passed but the file does not exist, behavior is identical
  to the non-force path: `EXTERNALIZED:<path>:<source>`. Callers can pass
  `--force` unconditionally in the Step 6 proactive call without needing to
  first check whether the file exists.
- Frontmatter-prepending logic (`build_header` / `has_frontmatter`) is
  unchanged. When `--force` overwrites an existing external file, the
  replacement file is rebuilt from the internal plan's content just as it
  would be for a fresh externalize. Any post-implementation edits that the
  caller made directly to the external plan (e.g., "Post-Review Changes"
  history) will be lost — this is the deliberate contract of `--force`
  and matches the user's request for "update the plan with the same script".

### 2. `.claude/skills/task-workflow/plan-externalization.md`

Update the "Procedure" and output-parsing sections:

- Add `[--force]` to the usage examples. The canonical Step 6 invocation
  becomes:
  ```bash
  ./.aitask-scripts/aitask_plan_externalize.sh <task_id> --force
  ```
  with or without `--internal <path>`.
- Add a new bullet to the output-parsing list (after `EXTERNALIZED`):
  ```
  - `OVERWRITTEN:<external>:<source>` — external plan replaced with the
    current internal plan (only possible when `--force` is passed).
    Treat identically to `EXTERNALIZED` — proceed to commit.
  ```
- Add a "When to use `--force`" note explaining the two call sites:
  - **Step 6 (proactive, from `planning.md`):** always call with `--force`.
    Step 6 runs after `ExitPlanMode`, so the internal plan is the new
    source of truth. This is what fixes verify-plan and child-task flows.
  - **Step 8 (safety fallback, from `SKILL.md`):** never call with
    `--force`. Step 8 is purely reactive — if the plan was already
    externalized in Step 6, leave it alone.
- Update the "Commit the externalized plan (Step 6 only)" section so the
  commit message reflects both cases: keep `ait: Add plan for t<N>` for
  fresh externalizes and use `ait: Update plan for t<N>` after an
  `OVERWRITTEN` result.

### 3. `tests/test_plan_externalize.sh`

Append three tests after Test 9 (before the "Results" section):

- **Test 10: `--force` overwrites existing external plan → `OVERWRITTEN`.**
  Setup: create sandbox, externalize once (produces existing file), then
  write a *new* internal plan with different content, re-run with `--force`,
  assert output starts with `OVERWRITTEN:aiplans/p999_sandbox_task.md:`,
  assert the external file body contains the new content (grep a unique
  marker from the second plan).
- **Test 11: `--force` with no existing external plan → `EXTERNALIZED`.**
  Verifies backward-compatible behavior when the file doesn't yet exist.
  Setup mirrors Test 1 but adds `--force`; expect `EXTERNALIZED:` (not
  `OVERWRITTEN`).
- **Test 12: `--force` with empty internal dir and existing external plan
  → `NOT_FOUND:no_internal_files` and external file preserved.**
  Verifies `--force` does not wipe the existing plan when there is nothing
  to copy. Setup: run once to externalize, delete the internal source,
  re-run with `--force`, assert `NOT_FOUND:no_internal_files`, assert the
  external file still exists and is unchanged (compare via `md5sum`/`cmp`
  or re-grep a marker).

Each test uses the existing `new_sandbox`/`make_fresh_internal`/
`run_externalize` helpers and follows the same PASS/FAIL pattern
(`assert_contains`, `assert_file_exists`, `assert_eq`).

## Verification

After implementation (in Step 7/8 of task-workflow):

1. **Run the test suite:**
   ```bash
   bash tests/test_plan_externalize.sh
   ```
   All 9 existing tests + 3 new tests must pass.

2. **Lint the script:**
   ```bash
   shellcheck .aitask-scripts/aitask_plan_externalize.sh
   ```
   No new warnings.

3. **Smoke test the `PLAN_EXISTS` path is unchanged** (no `--force`):
   Inside a scratch sandbox (or the real repo on a dummy task), run
   externalize twice without `--force` and confirm the second call still
   emits `PLAN_EXISTS`. This is already covered by existing Test 2 but is
   worth a final manual spot-check.

4. **Manual walkthrough of the Step 6 "Verify plan" flow** (optional but
   useful) to confirm the procedure file update wires correctly: pick a
   task that already has a plan file via `/aitask-pick` with `fast` profile,
   let the verify-plan branch trigger, make a trivial plan edit in plan
   mode, exit, and verify the external plan file now contains the edit
   (previously it would have been stale).

## Step 9 — Post-Implementation

Follow `task-workflow/SKILL.md` Step 9: commit code changes (script +
procedure doc + test file) as a `feature: ...` commit with `(t542)` suffix,
commit the consolidated plan file via `./ait git`, then archive via
`./.aitask-scripts/aitask_archive.sh 542` and push with `./ait git push`.
