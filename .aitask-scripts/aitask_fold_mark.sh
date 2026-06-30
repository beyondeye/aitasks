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
# The per-blob attachment ledger libs (attachment_lock.sh + attachment_meta.sh)
# are sourced LAZILY in Step 5b — only when a folded task actually carries an
# attachment — so a plain fold needs neither lib present (keeps the common path
# and minimal test fixtures dependency-free).

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

# Step 3b: union verifies lists from primary + directly folded tasks.
# No transitive walk: verifies entries are feature-task references, not fold
# chains, so deep traversal would pull in unrelated references.
declare -A seen_verifies=()
verifies_list=()

add_to_verifies() {
    local raw="$1"
    raw="${raw#t}"
    [[ -z "$raw" ]] && return 0
    if [[ -z "${seen_verifies[$raw]:-}" ]]; then
        seen_verifies[$raw]=1
        verifies_list+=("$raw")
    fi
}

primary_verifies_csv=$(parse_yaml_list "$(read_yaml_field "$primary_file" "verifies")")
if [[ -n "$primary_verifies_csv" ]]; then
    IFS=',' read -ra primary_verifies_parts <<< "$primary_verifies_csv"
    for v in "${primary_verifies_parts[@]}"; do
        add_to_verifies "$v"
    done
fi
for ff in ${folded_files[@]+"${folded_files[@]}"}; do
    fv_csv=$(parse_yaml_list "$(read_yaml_field "$ff" "verifies")")
    [[ -z "$fv_csv" ]] && continue
    IFS=',' read -ra fv_parts <<< "$fv_csv"
    for v in "${fv_parts[@]}"; do
        add_to_verifies "$v"
    done
done

verifies_args=()
if [[ ${#verifies_list[@]} -gt 0 ]]; then
    verifies_csv=$(IFS=','; echo "${verifies_list[*]}")
    verifies_args=(--verifies "$verifies_csv")
fi

# Step 3c: union gates (declared gate set) from primary + directly folded tasks.
# Gate names are plain strings (no task-id normalization). Mirrors the verifies
# union: a merged task should carry the union of every folded task's gates so a
# declared checkpoint is never lost on fold (t635_1).
declare -A seen_gates=()
gates_list=()

add_to_gates() {
    local raw="$1"
    [[ -z "$raw" ]] && return 0
    if [[ -z "${seen_gates[$raw]:-}" ]]; then
        seen_gates[$raw]=1
        gates_list+=("$raw")
    fi
}

primary_gates_csv=$(parse_yaml_list "$(read_yaml_field "$primary_file" "gates")")
if [[ -n "$primary_gates_csv" ]]; then
    IFS=',' read -ra primary_gates_parts <<< "$primary_gates_csv"
    for g in "${primary_gates_parts[@]}"; do
        add_to_gates "$g"
    done
fi
for ff in ${folded_files[@]+"${folded_files[@]}"}; do
    fg_csv=$(parse_yaml_list "$(read_yaml_field "$ff" "gates")")
    [[ -z "$fg_csv" ]] && continue
    IFS=',' read -ra fg_parts <<< "$fg_csv"
    for g in "${fg_parts[@]}"; do
        add_to_gates "$g"
    done
done

gates_args=()
if [[ ${#gates_list[@]} -gt 0 ]]; then
    gates_csv=$(IFS=','; echo "${gates_list[*]}")
    gates_args=(--gates "$gates_csv")
fi

# Step 3d: union also_blocks_dependents (per-task extra unblock gates) the same
# way as gates above — a per-task unblock requirement must not be lost on fold
# (t635_3).
declare -A seen_abd=()
abd_list=()

add_to_abd() {
    local raw="$1"
    [[ -z "$raw" ]] && return 0
    if [[ -z "${seen_abd[$raw]:-}" ]]; then
        seen_abd[$raw]=1
        abd_list+=("$raw")
    fi
}

primary_abd_csv=$(parse_yaml_list "$(read_yaml_field "$primary_file" "also_blocks_dependents")")
if [[ -n "$primary_abd_csv" ]]; then
    IFS=',' read -ra primary_abd_parts <<< "$primary_abd_csv"
    for g in "${primary_abd_parts[@]}"; do
        add_to_abd "$g"
    done
fi
for ff in ${folded_files[@]+"${folded_files[@]}"}; do
    fa_csv=$(parse_yaml_list "$(read_yaml_field "$ff" "also_blocks_dependents")")
    [[ -z "$fa_csv" ]] && continue
    IFS=',' read -ra fa_parts <<< "$fa_csv"
    for g in "${fa_parts[@]}"; do
        add_to_abd "$g"
    done
done

abd_args=()
if [[ ${#abd_list[@]} -gt 0 ]]; then
    abd_csv=$(IFS=','; echo "${abd_list[*]}")
    abd_args=(--also-blocks-dependents "$abd_csv")
fi

# risk_mitigation_tasks is deliberately NOT unioned into the primary (unlike
# verifies above). Each task's mitigation list is instance-specific to its own
# risk evaluation — merging folded tasks' lists into the primary would attribute
# mitigations to a plan that never evaluated them. The folded tasks' lists are
# instead cleared below (Step 4) and the primary keeps only its own.

# anchor (t1016) is a scalar topic group key and is likewise NOT unioned/merged
# on fold — the primary keeps its own anchor; the folded task's file is deleted
# during archival, so its anchor simply disappears.

"$SCRIPT_DIR/aitask_update.sh" --batch "$primary_id" \
    --folded-tasks "$full_csv" \
    ${file_ref_args[@]+"${file_ref_args[@]}"} \
    ${verifies_args[@]+"${verifies_args[@]}"} \
    ${gates_args[@]+"${gates_args[@]}"} \
    ${abd_args[@]+"${abd_args[@]}"} \
    --silent >/dev/null
echo "PRIMARY_UPDATED:${primary_id}"

# Step 4: mark each new folded task. Clear its risk_mitigation_tasks: the list
# is instance-specific (see note above) and a folded task no longer drives its
# own mitigation flow once merged into the primary.
for fid in "${folded_ids[@]}"; do
    fid="${fid#t}"
    "$SCRIPT_DIR/aitask_update.sh" --batch "$fid" --status Folded --folded-into "$primary_id" --risk-mitigation-tasks "" --silent >/dev/null
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

# Step 5b (t1030_3): transfer folded tasks' attachments to the primary.
# Re-bind the refcount (so blobs survive the folded files' deletion at archival)
# AND merge the folded frontmatter entries into the primary (so they stay
# accessible via `ait attach ls/get <primary>` and are decref-discoverable).
# Processes direct + transitive folded tasks; both have their files deleted at
# archival. All under ONE global attach lock. Skipped entirely when no folded
# task carries an attachment (the common case) so a plain fold never touches the
# attach lock or creates the attachments/ tree.

# Data-root-relative meta paths touched by rebind, for staging + rollback.
fold_meta_relpaths=()

# _fold_unique_name <base_name> <hash> -> a name not already in seen_names.
# Deterministic: <stem>~<first8hex><ext>, lengthening the hex suffix (8->16->32
# ->64) until unique, then a numeric counter on the (astronomically unlikely)
# full-hash collision. Reads/uses the caller's seen_names assoc (dynamic scope).
_fold_unique_name() {
    local base="$1" hexall="${2#sha256:}" stem ext len cand i
    if [[ "$base" == *.* ]]; then ext=".${base##*.}"; stem="${base%.*}"; else ext=""; stem="$base"; fi
    for len in 8 16 32 64; do
        cand="${stem}~${hexall:0:$len}${ext}"
        [[ -z "${seen_names[$cand]:-}" ]] && { printf '%s' "$cand"; return 0; }
    done
    i=2
    while [[ -n "${seen_names[${stem}~${hexall}-${i}${ext}]:-}" ]]; do i=$((i + 1)); done
    printf '%s' "${stem}~${hexall}-${i}${ext}"
}

# _fold_transfer_attachments <primary_file> <folded_file...> -- merge each folded
# file's attachment frontmatter entries into the primary, skipping duplicate
# hashes and disambiguating same-name/different-hash entries.
_fold_transfer_attachments() {
    local primary_file="$1"; shift
    local py; py="$(require_python)"
    declare -A seen_hashes=() seen_names=()
    local f recs ln k v h n mime size added backend have

    # Seed seen sets from the primary's current attachments (no append).
    recs="$(read_yaml_mappings "$primary_file" attachments)" || true
    h=""; n=""; have=false
    while IFS= read -r ln; do
        if [[ -z "$ln" ]]; then
            $have && { [[ -n "$h" ]] && seen_hashes["$h"]=1; [[ -n "$n" ]] && seen_names["$n"]=1; }
            h=""; n=""; have=false; continue
        fi
        have=true; k="${ln%%=*}"; v="${ln#*=}"
        case "$k" in hash) h="$v" ;; name) n="$v" ;; esac
    done <<< "$recs"
    $have && { [[ -n "$h" ]] && seen_hashes["$h"]=1; [[ -n "$n" ]] && seen_names["$n"]=1; }

    for f in "$@"; do
        [[ -f "$f" ]] || continue
        recs="$(read_yaml_mappings "$f" attachments)" || true
        [[ -z "$recs" ]] && continue
        h=""; n=""; mime=""; size=""; added=""; backend=""; have=false
        while IFS= read -r ln; do
            if [[ -z "$ln" ]]; then
                $have && _fold_merge_one
                h=""; n=""; mime=""; size=""; added=""; backend=""; have=false; continue
            fi
            have=true; k="${ln%%=*}"; v="${ln#*=}"
            case "$k" in
                hash) h="$v" ;; name) n="$v" ;; mime) mime="$v" ;;
                size) size="$v" ;; added_at) added="$v" ;; backend) backend="$v" ;;
            esac
        done <<< "$recs"
        $have && _fold_merge_one
    done
}

# _fold_merge_one -- append the current folded attachment (dynamic-scope locals
# h/n/mime/size/added/backend from _fold_transfer_attachments) into the primary,
# updating the seen sets. Skips on missing hash or a hash already on the primary.
_fold_merge_one() {
    [[ -n "$h" ]] || return 0
    [[ -n "${seen_hashes[$h]:-}" ]] && return 0   # dup hash: rebind drops folded id
    local name="${n:-$h}"
    [[ -n "${seen_names[$name]:-}" ]] && name="$(_fold_unique_name "$name" "$h")"
    "$py" "$SCRIPT_DIR/lib/frontmatter_patch.py" append "$primary_file" attachments \
        "hash=$h" "name=$name" \
        ${mime:+"mime=$mime"} ${size:+"size=$size"} \
        ${added:+"added_at=$added"} ${backend:+"backend=$backend"}
    seen_hashes["$h"]=1
    seen_names["$name"]=1
}

# _fold_rebind_refs <primary_id> <folded_id...> -- rebind each folded id's refs
# to the primary; collect each changed blob's meta relpath for staging/rollback.
_fold_rebind_refs() {
    local primary_id="$1"; shift
    local fid changed
    for fid in "$@"; do
        fid="${fid#t}"
        [[ -z "$fid" ]] && continue
        while IFS= read -r changed; do
            [[ -n "$changed" ]] && fold_meta_relpaths+=( "$(attach_meta_relpath "$changed")" )
        done < <(attach_meta rebind "$fid" "$primary_id")
    done
}

# _fold_attach_txn -- rebind + merge, run as one transaction under the attach lock.
_fold_attach_txn() {
    _fold_rebind_refs "$primary_id" \
        "${folded_ids[@]}" ${transitive_ids[@]+"${transitive_ids[@]}"}
    _fold_transfer_attachments "$primary_file" \
        ${folded_files[@]+"${folded_files[@]}"} \
        ${transitive_files[@]+"${transitive_files[@]}"}
}

# Only enter the attach transaction if a folded/transitive task actually carries
# an attachment — keeps the common no-attachment fold off the attach lock and
# free of the attachment libs (detection uses read_yaml_mappings, already
# available; the libs are sourced lazily only when needed).
_fold_any_attachments=false
for _ff in ${folded_files[@]+"${folded_files[@]}"} ${transitive_files[@]+"${transitive_files[@]}"}; do
    [[ -f "$_ff" ]] || continue
    if read_yaml_mappings "$_ff" attachments 2>/dev/null | grep -q '^hash='; then
        _fold_any_attachments=true; break
    fi
done
if [[ "$_fold_any_attachments" == true ]]; then
    # shellcheck source=lib/attachment_lock.sh
    source "$SCRIPT_DIR/lib/attachment_lock.sh"
    # shellcheck source=lib/attachment_meta.sh
    source "$SCRIPT_DIR/lib/attachment_meta.sh"
    with_attach_lock _fold_attach_txn
fi

# Full rollback path set for a failed fold commit (review concern 6): every task
# file the fold mutated in place (deletion happens later, at archival) plus the
# rebound meta files — all HEAD-restorable. Paths are data-root-relative (the
# task_git contract), matching primary_file / folded_files entries.
rollback_paths=( "$primary_file" )
for _f in ${folded_files[@]+"${folded_files[@]}"} ${transitive_files[@]+"${transitive_files[@]}"}; do
    rollback_paths+=( "$_f" )
done
for _fid in "${folded_ids[@]}"; do
    _fid="${_fid#t}"
    if [[ "$_fid" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        _pf="$(resolve_file_by_id "${BASH_REMATCH[1]}")"
        [[ -n "$_pf" ]] && rollback_paths+=( "$_pf" )
    fi
done
for _m in ${fold_meta_relpaths[@]+"${fold_meta_relpaths[@]}"}; do
    rollback_paths+=( "$_m" )
done

# _fold_rollback -- restore the whole fold transaction from HEAD (on commit fail).
_fold_rollback() {
    task_git reset -q -- "${rollback_paths[@]}" >/dev/null 2>&1 || true
    task_git checkout -- "${rollback_paths[@]}" >/dev/null 2>&1 || true
}

# Step 6: commit
case "$commit_mode" in
    fresh)
        task_git add aitasks/ >/dev/null 2>&1 || true
        if (( ${#fold_meta_relpaths[@]} > 0 )); then
            task_git add -- "${fold_meta_relpaths[@]}" >/dev/null 2>&1 || true
        fi
        joined=""
        for fid in "${folded_ids[@]}"; do
            fid="${fid#t}"
            if [[ -n "$joined" ]]; then
                joined="${joined}, t${fid}"
            else
                joined="t${fid}"
            fi
        done
        if task_git commit -m "ait: Fold tasks into t${primary_id}: merge ${joined}" --quiet >/dev/null 2>&1; then
            hash=$(task_git rev-parse --short HEAD 2>/dev/null || echo "")
            echo "COMMITTED:${hash}"
        elif task_git diff --cached --quiet >/dev/null 2>&1; then
            # Nothing was staged (no real change) — benign no-op, not a failure.
            echo "NO_COMMIT"
        else
            _fold_rollback
            die "fold commit failed — rolled back the whole fold transaction"
        fi
        ;;
    amend)
        task_git add aitasks/ >/dev/null 2>&1 || true
        if (( ${#fold_meta_relpaths[@]} > 0 )); then
            task_git add -- "${fold_meta_relpaths[@]}" >/dev/null 2>&1 || true
        fi
        if task_git commit --amend --no-edit --quiet >/dev/null 2>&1; then
            echo "AMENDED"
        else
            _fold_rollback
            die "fold amend-commit failed — rolled back the whole fold transaction"
        fi
        ;;
    none)
        echo "NO_COMMIT"
        ;;
    *)
        die "invalid --commit-mode: $commit_mode"
        ;;
esac
