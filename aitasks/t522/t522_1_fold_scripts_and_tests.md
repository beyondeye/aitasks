---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [aitask_fold, task_workflow]
created_at: 2026-04-12 09:53
updated_at: 2026-04-12 09:53
---

## Context

Parent task t522 aims to reduce prose-procedure complexity in fold-related workflows by encapsulating their logic into bash scripts. This child task delivers the three new helper scripts plus shared helper refactor plus tests. It ships a usable script API but does **not** touch any SKILL.md callers — t522_2 owns that migration. The existing `task-fold-content.md` / `task-fold-marking.md` prose procedures remain in place so existing callers keep working throughout this child.

Decision log (from parent planning in aiplans/p522_encapsulate_fold_logic_in_scripts.md):
- Three scripts, not one combined script. Keeps validate / content / mark composable for "merge into existing" callers (aitask-fold, planning ad-hoc, contribution-review) and "create new primary" callers (aitask-explore, aitask-pr-import) which compose them differently.
- `handle_folded_tasks()` in `aitask_archive.sh` is NOT refactored. It runs during archival, covers already-archived edge cases, and has independent test coverage in `tests/test_archive_folded.sh`. The ~5-line `--remove-child` duplication stays.
- `--exclude-children` flag is NOT needed on `aitask_fold_validate.sh`. Both `/aitask-fold` (SKILL.md:162) and planning ad-hoc fold accept child task IDs as fold sources.

## Key Files to Modify

**Create:**
- `.aitask-scripts/aitask_fold_validate.sh` — see interface below
- `.aitask-scripts/aitask_fold_content.sh` — see interface below
- `.aitask-scripts/aitask_fold_mark.sh` — see interface below
- `tests/test_fold_validate.sh`
- `tests/test_fold_content.sh`
- `tests/test_fold_mark.sh`

**Edit:**
- `.aitask-scripts/lib/task_utils.sh` — add `read_yaml_field()` and `read_task_status()` functions (copy from `.aitask-scripts/aitask_archive.sh:170-200`). Guard against double-definition via existing `_AIT_TASK_UTILS_LOADED` sentinel.
- `.aitask-scripts/aitask_archive.sh` — delete local definitions of `read_yaml_field` and `read_task_status` at lines 170-200 (file already sources `lib/task_utils.sh` so the shared versions take over automatically).

## Reference Files for Patterns

- **Script scaffolding / shell conventions:** `.aitask-scripts/aitask_update.sh` — shows `set -euo pipefail`, argument parsing with `--batch` mode, how to source `lib/task_utils.sh` and `lib/terminal_compat.sh`.
- **Output format (`KEY:value` lines):** `.aitask-scripts/aitask_query_files.sh` — consistent structured output style to mirror.
- **Frontmatter reading:** `.aitask-scripts/aitask_archive.sh:170-200` (`read_yaml_field`, `read_task_status`) — the functions being moved.
- **Parent / child file resolution via glob:** `.aitask-scripts/aitask_archive.sh:302-308` — shows the `^([0-9]+)_([0-9]+)$` regex pattern and the `ls "$TASK_DIR"/t"${fp}"/t"${fp}"_"${fc}"_*.md` glob pattern. Reuse for `aitask_fold_validate.sh` and `aitask_fold_mark.sh`.
- **Test scaffolding:** `tests/test_archive_folded.sh` — canonical pattern for fold-related tests: bare remote + clone setup, assert helpers (`assert_eq`, `assert_contains`, `assert_file_exists`), `CLEANUP_DIRS` array, PASS/FAIL counters, final summary with exit code.
- **macOS portability:** `.aitask-scripts/lib/terminal_compat.sh` — `sed_inplace()`, `die()`, `warn()`, `info()`. Use `sed_inplace` not `sed -i`. For `wc -l` comparisons as strings, pipe through `| tr -d ' '` per CLAUDE.md.
- **`task_git` and `task_push`:** `.aitask-scripts/lib/task_utils.sh:43-80` — use `task_git` instead of raw `git` in `aitask_fold_mark.sh` so branch-mode task-data worktrees work.
- **Calling aitask_update.sh from another script:** `.aitask-scripts/aitask_archive.sh:349-354` — `"$SCRIPT_DIR/aitask_update.sh" --batch "$fold_parent" --remove-child "t${folded_id}" --silent 2>/dev/null || true`. Mirror this pattern.

## Implementation Plan

### Step 1: Refactor shared helpers into lib/task_utils.sh

1. Open `.aitask-scripts/lib/task_utils.sh`.
2. After `parse_yaml_list()` (around line 109), add `read_yaml_field()` and `read_task_status()` functions copied verbatim from `.aitask-scripts/aitask_archive.sh:170-200`.
3. Verify no other script in `.aitask-scripts/` already defines either function (grep: `grep -rn 'read_yaml_field\|read_task_status' .aitask-scripts/`). Only `aitask_archive.sh` should match.
4. Delete the local definitions from `.aitask-scripts/aitask_archive.sh:170-200` (including the `# --- Helper: read a YAML field from frontmatter ---` and `# --- Helper: read status of a folded task ---` section headers).
5. Run `bash tests/test_archive_folded.sh` — must still pass (regression check on the move).

### Step 2: Implement `aitask_fold_validate.sh`

Skeleton:
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"

usage() { echo "Usage: $0 [--exclude-self <id>] <id1> [<id2> ...]"; exit 1; }

exclude_self=""
ids=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --exclude-self) exclude_self="$2"; shift 2 ;;
        --help|-h) usage ;;
        --) shift; ids+=("$@"); break ;;
        -*) die "unknown flag: $1" ;;
        *) ids+=("$1"); shift ;;
    esac
done
[[ ${#ids[@]} -eq 0 ]] && usage

for id in "${ids[@]}"; do
    id="${id#t}"  # strip leading 't' if any
    if [[ -n "$exclude_self" && "$id" == "$exclude_self" ]]; then
        echo "INVALID:$id:is_self"
        continue
    fi
    # Resolve file
    if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        parent="${BASH_REMATCH[1]}"
        child="${BASH_REMATCH[2]}"
        file=$(ls "$TASK_DIR"/t"${parent}"/t"${parent}"_"${child}"_*.md 2>/dev/null | head -1 || true)
    else
        file=$(ls "$TASK_DIR"/t"${id}"_*.md 2>/dev/null | head -1 || true)
    fi
    if [[ -z "$file" ]]; then
        echo "INVALID:$id:not_found"
        continue
    fi
    status=$(read_task_status "$file")
    if [[ "$status" != "Ready" && "$status" != "Editing" ]]; then
        echo "INVALID:$id:status_${status}"
        continue
    fi
    # For parent IDs only, check for pending children
    if [[ "$id" =~ ^[0-9]+$ ]]; then
        child_count=$(ls "$TASK_DIR"/t"${id}"/*.md 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$child_count" -gt 0 ]]; then
            echo "INVALID:$id:has_children"
            continue
        fi
    fi
    echo "VALID:$id:$file"
done
```

Notes: use `tr -d ' '` when comparing `wc -l` output as a string (per CLAUDE.md shell conventions). Always exit 0; callers parse the lines. Run `chmod +x` via the creation process (`aitask_create.sh` doesn't do this; `chmod +x .aitask-scripts/aitask_fold_*.sh` after creation).

### Step 3: Implement `aitask_fold_content.sh`

Skeleton:
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# task_utils.sh not strictly needed but fine to source

use_stdin=false
primary_file=""
folded=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --primary-stdin) use_stdin=true; shift ;;
        --help|-h) echo "Usage: $0 <primary_task_file> <folded1> [...]"; exit 1 ;;
        -*) die "unknown flag: $1" ;;
        *) if [[ -z "$primary_file" && "$use_stdin" == false ]]; then
               primary_file="$1"
           else
               folded+=("$1")
           fi
           shift ;;
    esac
done
[[ ${#folded[@]} -eq 0 ]] && die "need at least one folded file"

# Extract primary body
extract_body() {
    awk 'BEGIN{in_fm=0; seen_open=0} {
        if ($0 == "---") {
            if (seen_open==0) { seen_open=1; in_fm=1; next }
            else if (in_fm==1) { in_fm=0; next }
        }
        if (in_fm==0 && seen_open==1) print
    }' "$1"
}

if [[ "$use_stdin" == true ]]; then
    primary_body=$(cat)
else
    primary_body=$(extract_body "$primary_file")
fi

# Build merged output
printf '%s\n' "$primary_body"

folded_refs=()
for f in "${folded[@]}"; do
    base=$(basename "$f")
    # Strip 't' and '.md'; split into N and name
    stem="${base#t}"
    stem="${stem%.md}"
    # stem like "12_fix_login" or "16_2_add_login"
    if [[ "$stem" =~ ^([0-9]+)_([0-9]+)_(.+)$ ]]; then
        n="${BASH_REMATCH[1]}_${BASH_REMATCH[2]}"
        name="${BASH_REMATCH[3]}"
    elif [[ "$stem" =~ ^([0-9]+)_(.+)$ ]]; then
        n="${BASH_REMATCH[1]}"
        name="${BASH_REMATCH[2]}"
    else
        die "cannot parse filename: $base"
    fi
    display_name="${name//_/ }"
    printf '\n## Merged from t%s: %s\n\n' "$n" "$display_name"
    extract_body "$f"
    folded_refs+=("- **t${n}** (\`${base}\`)")
done

printf '\n## Folded Tasks\n\nThe following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.\n\n'
for ref in "${folded_refs[@]}"; do
    printf '%s\n' "$ref"
done
```

### Step 4: Implement `aitask_fold_mark.sh`

Skeleton (key logic):
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/task_utils.sh"

handle_transitive=true
commit_mode="fresh"
primary_id=""
folded_ids=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-transitive) handle_transitive=false; shift ;;
        --commit-mode) commit_mode="$2"; shift 2 ;;
        --help|-h) echo "Usage: $0 [--no-transitive] [--commit-mode fresh|amend|none] <primary_id> <folded_id1> [...]"; exit 1 ;;
        -*) die "unknown flag: $1" ;;
        *) if [[ -z "$primary_id" ]]; then primary_id="$1"; else folded_ids+=("$1"); fi; shift ;;
    esac
done
[[ -z "$primary_id" || ${#folded_ids[@]} -eq 0 ]] && die "need primary id and at least one folded id"
primary_id="${primary_id#t}"

# Step 1: existing folded_tasks on primary
resolve_file_by_id() {
    local id="$1" file=""
    if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local p="${BASH_REMATCH[1]}" c="${BASH_REMATCH[2]}"
        file=$(ls "$TASK_DIR"/t"${p}"/t"${p}"_"${c}"_*.md 2>/dev/null | head -1 || true)
    else
        file=$(ls "$TASK_DIR"/t"${id}"_*.md 2>/dev/null | head -1 || true)
    fi
    echo "$file"
}

primary_file=$(resolve_file_by_id "$primary_id")
[[ -z "$primary_file" ]] && die "primary task not found: $primary_id"
existing=$(parse_yaml_list "$(read_yaml_field "$primary_file" folded_tasks)")

# Step 2: transitive
transitive_ids=()
if [[ "$handle_transitive" == true ]]; then
    for fid in "${folded_ids[@]}"; do
        fid="${fid#t}"
        f=$(resolve_file_by_id "$fid")
        [[ -z "$f" ]] && continue
        t_raw=$(parse_yaml_list "$(read_yaml_field "$f" folded_tasks)")
        [[ -n "$t_raw" ]] && IFS=',' read -ra t_arr <<< "$t_raw" && transitive_ids+=("${t_arr[@]}")
    done
fi

# Step 3: build full list (existing + new + transitive, deduped)
declare -A seen=()
all_list=()
for raw in $(echo "$existing" | tr ',' ' ') "${folded_ids[@]}" "${transitive_ids[@]}"; do
    raw="${raw#t}"
    [[ -z "$raw" || -n "${seen[$raw]:-}" ]] && continue
    seen[$raw]=1
    all_list+=("$raw")
done
full_csv=$(IFS=','; echo "${all_list[*]}")

"$SCRIPT_DIR/aitask_update.sh" --batch "$primary_id" --folded-tasks "$full_csv" --silent >/dev/null
echo "PRIMARY_UPDATED:$primary_id"

# Step 4: update each new folded task
for fid in "${folded_ids[@]}"; do
    fid="${fid#t}"
    "$SCRIPT_DIR/aitask_update.sh" --batch "$fid" --status Folded --folded-into "$primary_id" --silent >/dev/null
    echo "FOLDED:$fid"
    # Step 4b: child task parent cleanup
    if [[ "$fid" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        fp="${BASH_REMATCH[1]}"
        "$SCRIPT_DIR/aitask_update.sh" --batch "$fp" --remove-child "t${fid}" --silent >/dev/null 2>&1 || true
        echo "CHILD_REMOVED:${fp}:${BASH_REMATCH[2]}"
    fi
done

# Step 5: transitive tasks
for tid in "${transitive_ids[@]}"; do
    tid="${tid#t}"
    [[ -z "$tid" ]] && continue
    "$SCRIPT_DIR/aitask_update.sh" --batch "$tid" --folded-into "$primary_id" --silent >/dev/null 2>&1 || true
    echo "TRANSITIVE:$tid"
done

# Step 6: commit
case "$commit_mode" in
    fresh)
        task_git add aitasks/ 2>/dev/null || true
        joined=$(printf 't%s, ' "${folded_ids[@]}"); joined="${joined%, }"
        task_git commit -m "ait: Fold tasks into t${primary_id}: merge ${joined}" --quiet 2>/dev/null || true
        hash=$(task_git rev-parse --short HEAD 2>/dev/null || echo "")
        echo "COMMITTED:${hash}"
        ;;
    amend)
        task_git add aitasks/ 2>/dev/null || true
        task_git commit --amend --no-edit --quiet 2>/dev/null || true
        echo "AMENDED"
        ;;
    none)
        echo "NO_COMMIT"
        ;;
    *) die "invalid --commit-mode: $commit_mode" ;;
esac
```

### Step 5: Write tests

Use `tests/test_archive_folded.sh` as the scaffolding template. Each test file should:
- Define `assert_eq`, `assert_contains`, `assert_file_exists` (copy from test_archive_folded.sh)
- Use `CLEANUP_DIRS` and a `teardown_all()` at the end
- Set up a bare remote + working clone, mkdir the needed structure, copy the new scripts, set up a minimal `aitasks/metadata/` if needed (e.g., `task_types.txt`, `labels.txt`)
- Create fake task files with YAML frontmatter directly via heredoc writes
- Invoke the script under test and assert against its output or resulting file state

See full test case list in parent plan file (`/home/ddt/.claude/plans/squishy-drifting-cray.md` Child t522_1 section — or the committed `aiplans/p522_encapsulate_fold_logic_in_scripts.md`).

### Step 6: Make scripts executable and commit

```bash
chmod +x .aitask-scripts/aitask_fold_validate.sh .aitask-scripts/aitask_fold_content.sh .aitask-scripts/aitask_fold_mark.sh
```

Commit code files with `git` (not `./ait git`):
```bash
git add .aitask-scripts/aitask_fold_validate.sh .aitask-scripts/aitask_fold_content.sh .aitask-scripts/aitask_fold_mark.sh .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_archive.sh tests/test_fold_validate.sh tests/test_fold_content.sh tests/test_fold_mark.sh
git commit -m "chore: Add fold helper scripts with shared read_yaml_field (t522_1)"
```

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_fold_*.sh` — lint clean.
2. `bash tests/test_fold_validate.sh` — all PASS.
3. `bash tests/test_fold_content.sh` — all PASS.
4. `bash tests/test_fold_mark.sh` — all PASS.
5. `bash tests/test_archive_folded.sh` — still passes (regression check on `read_yaml_field` move).
6. Manual smoke: create two scratch task files in `/tmp`, run each of the three new scripts against them, verify output format matches the spec.

## Notes for Sibling Tasks (t522_2, t522_3)

- Script interfaces are locked once this child ships. If t522_2 discovers an interface gap (e.g., the callers need an extra flag), that's a signal to either split it into a t522_1_1 follow-up or bundle it into t522_2 with a script edit.
- `read_yaml_field` / `read_task_status` now live in `lib/task_utils.sh` — safe to use from any new script or shell code.
- `handle_folded_tasks()` in `aitask_archive.sh` was intentionally left alone. Do not refactor it in t522_2 or t522_3.
