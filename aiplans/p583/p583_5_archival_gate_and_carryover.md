---
Task: t583_5_archival_gate_and_carryover.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_4_manual_verification_workflow_procedure.md, aitasks/t583/t583_7_plan_time_generation_integration.md, aitasks/t583/t583_8_documentation_website_and_skill.md, aitasks/t583/t583_9_meta_dogfood_aggregate_verification.md
Archived Sibling Plans: aiplans/archived/p583/p583_1_verification_parser_python_helper.md, aiplans/archived/p583/p583_2_verifies_frontmatter_field_three_layer.md, aiplans/archived/p583/p583_3_verification_followup_helper_script.md, aiplans/archived/p583/p583_6_issue_type_manual_verification_and_unit_tests.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 15:34
---

# Plan: t583_5 — Archival Gate + Carry-over

## Context

Fifth child of t583 (manual-verification module for `/aitask-pick`). Prevents
`aitask_archive.sh` from archiving a `manual_verification` task while any
verification items are still unchecked. Also adds a `--with-deferred-carryover`
flag that creates a new manual-verification task containing just the deferred
items, letting the user archive the current one and pick the carry-over later.

Depends on t583_1 (uses `aitask_verification_parse.sh terminal_only` as the
gate primitive). All primitives used below are already present on `main`:
- `aitask_verification_parse.sh terminal_only|parse|seed` (t583_1, archived).
- `aitask_create.sh --batch --commit --silent --type manual_verification
  --verifies …` (t583_2, archived; `--verifies` is serialized via
  `format_yaml_list`).
- `task_types.txt` already contains `manual_verification` (line 9).
- No `aitask_create_manual_verification.sh` seeder exists yet (that is t583_7).
  This plan uses the raw create + seed fallback that t583_7 will refactor.

## Verification refresh notes

Two function-name corrections vs the task-file plan:
- `resolve_task_id_to_file` → **`resolve_task_file`** (`task_utils.sh:275`).
- `read_frontmatter_field` → **`read_yaml_field`** (`task_utils.sh:126`).

Structural points confirmed:
- `aitask_archive.sh` `parse_args()` at line 79, `main()` at line 530,
  dispatch to `archive_parent()` / `archive_child()` at lines 533–539.
- `show_help()` at line 42; flag docs listed at lines 51–55.
- `archive_parent()` at line 170, `archive_child()` at line 347 — neither is
  re-entered via `main()`, so placing the gate in `main()` before dispatch is
  sufficient for the explicit-archive path. Implicit parent-archival (fired
  from inside `archive_child()` when it's the last child) does NOT re-check
  the parent. This is acceptable scope: parents almost never carry a
  `## Verification Checklist`; t583_9 (meta-dogfood) covers that edge case.

## Files to modify

- `.aitask-scripts/aitask_archive.sh` — add gate, flag, carry-over, help text.

## Files to create

- `tests/test_archive_verification_gate.sh` — integration tests for the gate
  and carry-over paths (patterned after `tests/test_archive_folded.sh`).

## Changes to `aitask_archive.sh`

### 1. New config variable (near line 39)

```bash
WITH_DEFERRED_CARRYOVER=false
```

### 2. New flag in `parse_args()` (inside the `case "$1"` at lines 81–107)

Add after the `--superseded` case:

```bash
--with-deferred-carryover)
    WITH_DEFERRED_CARRYOVER=true
    shift
    ;;
```

### 3. New helper `verification_gate_and_carryover` (before `main()`)

Encapsulates the gate + carry-over so `main()` stays small:

```bash
# --- Helper: pre-archive gate for manual_verification tasks ---
# Exits 2 on blocked verification; prints CARRYOVER_CREATED on success-with-flag.
# No-op for non-manual_verification tasks.
verification_gate_and_carryover() {
    local task_num="$1"
    local task_file
    task_file=$(resolve_task_file "$task_num") || die "Task not found: $task_num"

    local issue_type
    issue_type=$(read_yaml_field "$task_file" "issue_type")
    [[ "$issue_type" == "manual_verification" ]] || return 0

    # Run the gate primitive. stdout is PENDING:/DEFERRED: lines; exit 2 = blocked.
    local gate_out gate_rc=0
    gate_out=$(./.aitask-scripts/aitask_verification_parse.sh terminal_only "$task_file") || gate_rc=$?

    if [[ "$gate_rc" -ne 0 ]]; then
        if echo "$gate_out" | grep -q '^PENDING:'; then
            echo "$gate_out"
            echo "VERIFICATION_PENDING: cannot archive until all items are terminal (pass/fail/skip)"
            exit 2
        fi
        if echo "$gate_out" | grep -q '^DEFERRED:' && [[ "$WITH_DEFERRED_CARRYOVER" != "true" ]]; then
            echo "$gate_out"
            echo "VERIFICATION_DEFERRED: use --with-deferred-carryover to archive with carry-over task"
            exit 2
        fi
    fi

    # Only reachable in two cases: all terminal, OR deferred+flag. Only the latter triggers carry-over.
    if [[ "$WITH_DEFERRED_CARRYOVER" == "true" ]] && echo "$gate_out" | grep -q '^DEFERRED:'; then
        create_carryover_task "$task_file"
    fi
}
```

### 4. New helper `create_carryover_task` (before `main()`)

Builds a fresh manual-verification task seeded with the deferred items only.
Mirrors the existing fallback-path the task file sketches — t583_7 later
refactors this into `aitask_create_manual_verification.sh`.

```bash
# --- Helper: build carry-over task from deferred items of the task being archived ---
# Prints CARRYOVER_CREATED:<new_id>:<path> on stdout.
create_carryover_task() {
    local orig_file="$1"

    # 1. Extract deferred item texts from the original via `parse`.
    local items_tmp
    items_tmp=$(mktemp "${TMPDIR:-/tmp}/t583_5_defer_XXXXXX.txt")
    ./.aitask-scripts/aitask_verification_parse.sh parse "$orig_file" \
        | awk -F: '$3 == "defer" { sub(/^ITEM:[0-9]+:defer:[0-9]+:/, ""); print }' \
        > "$items_tmp"

    if [[ ! -s "$items_tmp" ]]; then
        rm -f "$items_tmp"
        return 0  # nothing to carry over (defensive; gate already checked DEFERRED:)
    fi

    # 2. Compute carry-over task name from the original filename stem.
    local orig_basename orig_name
    orig_basename=$(basename "$orig_file" .md)
    # Strip leading "t<digits>_" or "t<parent>_<child>_" prefix.
    orig_name=$(echo "$orig_basename" | sed -E 's/^t[0-9]+(_[0-9]+)?_//')
    local carryover_name="${orig_name}_deferred_carryover"

    # 3. Read `verifies:` from original (may be empty).
    local orig_verifies_raw orig_verifies
    orig_verifies_raw=$(read_yaml_field "$orig_file" "verifies")
    orig_verifies=$(parse_yaml_list "$orig_verifies_raw")

    # 4. Create the new task (commits internally).
    local create_args=(--batch --commit --silent
        --name "$carryover_name"
        --type manual_verification
        --priority medium --effort low)
    [[ -n "$orig_verifies" ]] && create_args+=(--verifies "$orig_verifies")

    local new_file
    new_file=$(./.aitask-scripts/aitask_create.sh "${create_args[@]}")
    if [[ -z "$new_file" || ! -f "$new_file" ]]; then
        rm -f "$items_tmp"
        die "Carry-over task creation failed"
    fi

    # 5. Seed the checklist with deferred items.
    ./.aitask-scripts/aitask_verification_parse.sh seed "$new_file" --items "$items_tmp"

    # 6. Commit the seeded change (separate from aitask_create's commit).
    local new_id
    new_id=$(basename "$new_file" .md | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*/\1/')
    ./ait git add "$new_file"
    ./ait git commit -m "ait: Seed carry-over checklist on t${new_id}" --quiet

    rm -f "$items_tmp"

    echo "CARRYOVER_CREATED:${new_id}:${new_file}"
}
```

### 5. Hook the gate into `main()` (line 530)

```bash
main() {
    parse_args "$@"

    verification_gate_and_carryover "$TASK_NUM"

    if [[ "$TASK_NUM" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"
        archive_child "$parent_num" "$child_num"
    else
        archive_parent "$TASK_NUM"
    fi
}
```

### 6. Update `show_help()` (line 42)

- Add `--with-deferred-carryover` under `Options:` (after `--superseded`).
- Add two new structured output lines under `Output format`:
  `CARRYOVER_CREATED:<task_id>:<path>` and a note about exit code 2.
- Add `Exit codes:` block documenting:
  `0` = success, `1` = generic error, `2` = verification gate blocked archival.

## Tests (`tests/test_archive_verification_gate.sh`)

Follow `tests/test_archive_folded.sh` patterns: `assert_eq`/`assert_contains`,
`setup_archive_project()` helper, `CLEANUP_DIRS` trap.

**Fixtures per test** — use `aitask_create.sh --batch --commit --type
manual_verification --name …` inside the isolated repo, then
`aitask_verification_parse.sh seed` + `set` to drive items into the desired
state. (Avoids hard-coding exact frontmatter bytes.)

Test cases:

1. **pending blocks archival** — task with `[ ]` + `[x]` → expect exit 2,
   stdout contains `PENDING:1` and `VERIFICATION_PENDING:`, task file still
   exists in `aitasks/`, no `COMMITTED:` line.
2. **deferred blocks without flag** — task with `[defer]` + `[x]` → exit 2,
   stdout contains `DEFERRED:1` and `VERIFICATION_DEFERRED:`.
3. **deferred + flag succeeds** — same task + `--with-deferred-carryover` →
   exit 0, stdout has `CARRYOVER_CREATED:<id>:<path>` AND standard
   `ARCHIVED_TASK:` / `COMMITTED:`. Original file moved under
   `aitasks/archived/`. New carry-over file exists with a
   `## Verification Checklist` section holding exactly the deferred item.
   Carry-over's `verifies:` frontmatter matches the original's.
4. **all-terminal archives normally** — `[x]` + `[fail]` + `[skip]` → exit 0,
   no gate output lines, normal archival.
5. **non-manual_verification is no-op** — `issue_type: feature` task with a
   dummy `## Verification Checklist` → exit 0, no gate output, normal
   archival.
6. **no checklist section is no-op** — `issue_type: manual_verification` but
   no `## Verification Checklist` → exit 0 (parser treats empty checklist as
   vacuously terminal).
7. **child task gate** — repeat test 1 for a child task ID (e.g. `42_1`) to
   confirm the gate fires for the child-archive path too.

## Verification steps

1. Run the new test file:
   `bash tests/test_archive_verification_gate.sh` → all pass.
2. Run adjacent existing tests to confirm no regression:
   `bash tests/test_archive_folded.sh` and
   `bash tests/test_archive_related_issues.sh`.
3. Shellcheck:
   `shellcheck .aitask-scripts/aitask_archive.sh`.
4. Manual smoke in a scratch fixture repo: create a manual_verification task,
   seed 2 items, mark one `defer` via
   `aitask_verification_parse.sh set <file> 1 defer`, run
   `aitask_archive.sh <id>` → expect exit 2; rerun with
   `--with-deferred-carryover` → expect success + `CARRYOVER_CREATED` line +
   new task present.

## Step 9 reminder

Per `.claude/skills/task-workflow/SKILL.md`. Commit message:
`feature: Add archival gate and carry-over for manual-verification (t583_5)`.
Plan file commits use the `ait:` prefix.
