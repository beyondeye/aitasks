#!/usr/bin/env bash
# aitask_fold_mark.sh - Mark fold relationships in task frontmatter
#
# Mirrors task-fold-marking.md:
#   1. Read primary's existing folded_tasks
#   2. Collect transitive folded_tasks from each new folded task (unless --no-transitive)
#   3. Write the full deduped list to primary via aitask_update.sh --batch --folded-tasks
#   4. For each new folded task: set status=Folded, folded_into=<primary>
#   4b. For each new folded task that is a child (e.g. 16_2): remove from its
#       original parent's children_to_implement
#   5. For each transitive task: set folded_into=<primary>
#   6. Commit via task_git (respects branch-mode task-data worktree)
#
# Structured stdout (one per line):
#   PRIMARY_UPDATED:<primary_id>
#   FOLDED:<id>
#   CHILD_REMOVED:<parent>:<child>
#   TRANSITIVE:<id>
#   COMMITTED:<short_hash>  |  AMENDED  |  NO_COMMIT
#
# Usage:
#   aitask_fold_mark.sh [--no-transitive] [--commit-mode fresh|amend|none] \
#                      <primary_id> <folded_id1> [<folded_id2> ...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

usage() {
    cat <<EOF
Usage: $0 [--no-transitive] [--commit-mode fresh|amend|none] <primary_id> <folded_id1> [...]

Marks each <folded_id> as folded into <primary_id>, updates the primary's
folded_tasks list, handles transitive folds, and optionally commits.

Options:
  --no-transitive       Do not chase each folded task's own folded_tasks field
  --commit-mode MODE    fresh (default), amend, or none
EOF
    exit 1
}

handle_transitive=true
commit_mode="fresh"
primary_id=""
folded_ids=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-transitive)
            handle_transitive=false
            shift
            ;;
        --commit-mode)
            [[ $# -ge 2 ]] || die "--commit-mode requires an argument"
            commit_mode="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        -*)
            die "unknown flag: $1"
            ;;
        *)
            if [[ -z "$primary_id" ]]; then
                primary_id="$1"
            else
                folded_ids+=("$1")
            fi
            shift
            ;;
    esac
done

[[ -z "$primary_id" ]] && usage
[[ ${#folded_ids[@]} -eq 0 ]] && die "need at least one folded id"

primary_id="${primary_id#t}"

resolve_file_by_id() {
    local id="$1" file=""
    if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local p="${BASH_REMATCH[1]}" c="${BASH_REMATCH[2]}"
        file=$(ls "$TASK_DIR"/t"${p}"/t"${p}"_"${c}"_*.md 2>/dev/null | head -1 || true)
    elif [[ "$id" =~ ^[0-9]+$ ]]; then
        file=$(ls "$TASK_DIR"/t"${id}"_*.md 2>/dev/null | head -1 || true)
    fi
    echo "$file"
}

primary_file=$(resolve_file_by_id "$primary_id")
[[ -z "$primary_file" ]] && die "primary task file not found for id: $primary_id"

# Step 1: existing folded_tasks on the primary
existing_csv=$(parse_yaml_list "$(read_yaml_field "$primary_file" "folded_tasks")")

# Step 2: transitive ids from each new folded task
transitive_ids=()
if [[ "$handle_transitive" == true ]]; then
    for fid in "${folded_ids[@]}"; do
        fid="${fid#t}"
        f=$(resolve_file_by_id "$fid")
        [[ -z "$f" ]] && continue
        t_csv=$(parse_yaml_list "$(read_yaml_field "$f" "folded_tasks")")
        if [[ -n "$t_csv" ]]; then
            IFS=',' read -ra parts <<< "$t_csv"
            for p in "${parts[@]}"; do
                [[ -n "$p" ]] && transitive_ids+=("$p")
            done
        fi
    done
fi

# Step 3: build deduped full list = existing + new + transitive
declare -A seen=()
all_list=()

add_to_list() {
    local raw="$1"
    raw="${raw#t}"
    [[ -z "$raw" ]] && return 0
    if [[ -z "${seen[$raw]:-}" ]]; then
        seen[$raw]=1
        all_list+=("$raw")
    fi
}

if [[ -n "$existing_csv" ]]; then
    IFS=',' read -ra existing_parts <<< "$existing_csv"
    for e in "${existing_parts[@]}"; do
        add_to_list "$e"
    done
fi
for nid in "${folded_ids[@]}"; do
    add_to_list "$nid"
done
for tid in "${transitive_ids[@]}"; do
    add_to_list "$tid"
done

full_csv=""
if [[ ${#all_list[@]} -gt 0 ]]; then
    full_csv=$(IFS=','; echo "${all_list[*]}")
fi

# Collect file paths for direct folded tasks
folded_files=()
for fid in "${folded_ids[@]}"; do
    fid="${fid#t}"
    f=$(resolve_file_by_id "$fid")
    [[ -n "$f" ]] && folded_files+=("$f")
done

# Collect file paths for transitive folded tasks
transitive_files=()
for tid in "${transitive_ids[@]}"; do
    tid="${tid#t}"
    [[ -z "$tid" ]] && continue
    f=$(resolve_file_by_id "$tid")
    [[ -n "$f" ]] && transitive_files+=("$f")
done

# Compute deduped union of file_references across primary + folded + transitive.
# Passing primary first preserves its existing entries and order; folded entries
# are appended in fold-argument order via process_file_references_operations'
# exact-string dedup in aitask_update.sh.
union_csv=$(union_file_references "$primary_file" \
    ${folded_files[@]+"${folded_files[@]}"} \
    ${transitive_files[@]+"${transitive_files[@]}"})

file_ref_args=()
if [[ -n "$union_csv" ]]; then
    IFS=',' read -ra union_entries <<< "$union_csv"
    for entry in "${union_entries[@]}"; do
        [[ -z "$entry" ]] && continue
        file_ref_args+=(--file-ref "$entry")
    done
fi

"$SCRIPT_DIR/aitask_update.sh" --batch "$primary_id" \
    --folded-tasks "$full_csv" \
    ${file_ref_args[@]+"${file_ref_args[@]}"} \
    --silent >/dev/null
echo "PRIMARY_UPDATED:${primary_id}"

# Step 4: mark each new folded task
for fid in "${folded_ids[@]}"; do
    fid="${fid#t}"
    "$SCRIPT_DIR/aitask_update.sh" --batch "$fid" --status Folded --folded-into "$primary_id" --silent >/dev/null
    echo "FOLDED:${fid}"

    # Step 4b: child task parent cleanup
    if [[ "$fid" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        fp="${BASH_REMATCH[1]}"
        fc="${BASH_REMATCH[2]}"
        "$SCRIPT_DIR/aitask_update.sh" --batch "$fp" --remove-child "t${fid}" --silent >/dev/null 2>&1 || true
        echo "CHILD_REMOVED:${fp}:${fc}"
    fi
done

# Step 5: transitive tasks point at primary
for tid in "${transitive_ids[@]}"; do
    tid="${tid#t}"
    [[ -z "$tid" ]] && continue
    "$SCRIPT_DIR/aitask_update.sh" --batch "$tid" --folded-into "$primary_id" --silent >/dev/null 2>&1 || true
    echo "TRANSITIVE:${tid}"
done

# Step 6: commit
case "$commit_mode" in
    fresh)
        task_git add aitasks/ >/dev/null 2>&1 || true
        joined=""
        for fid in "${folded_ids[@]}"; do
            fid="${fid#t}"
            if [[ -n "$joined" ]]; then
                joined="${joined}, t${fid}"
            else
                joined="t${fid}"
            fi
        done
        task_git commit -m "ait: Fold tasks into t${primary_id}: merge ${joined}" --quiet >/dev/null 2>&1 || true
        hash=$(task_git rev-parse --short HEAD 2>/dev/null || echo "")
        echo "COMMITTED:${hash}"
        ;;
    amend)
        task_git add aitasks/ >/dev/null 2>&1 || true
        task_git commit --amend --no-edit --quiet >/dev/null 2>&1 || true
        echo "AMENDED"
        ;;
    none)
        echo "NO_COMMIT"
        ;;
    *)
        die "invalid --commit-mode: $commit_mode"
        ;;
esac
