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
# RECORDS MEAN "STEP 6 REACHED A TERMINAL SUCCESS" (t1661). Steps 3-5b mutate
# the task files, but Step 6 can still roll the whole transaction back (a failed
# commit, or an amend the guard refuses). So the four per-mutation records above
# are BUFFERED as they happen and flushed only on one of Step 6's three terminal
# SUCCESS outcomes -- in emission order, immediately before the terminal record:
#
#   COMMITTED:<hash>  this fold's own commit was created
#   AMENDED           the fold was folded into the preceding commit
#   NO_COMMIT         no commit was created, and that is still a SUCCESS --
#                     either --commit-mode none (the caller commits the
#                     mutations itself) or a verified no-op (git reports these
#                     paths unchanged). Nothing was rolled back either way.
#
# So NO_COMMIT is a valid flush outcome, not a failure, and a record does NOT
# imply durable git history -- it means that mutation SURVIVED Step 6 and is on
# disk, committed or handed to the caller to commit. Every Step 6 rollback path
# dies without flushing, so a consumer never sees progress for a transaction
# that was undone. Add a new record via _fold_emit, never a bare `echo`.
#
# WHAT THIS DOES NOT BUY: silence is not proof that nothing changed. An abort
# BEFORE Step 6 -- a folded id with no task file, say, whose aitask_update.sh
# exits non-zero under `set -e` -- leaves the mutations made so far on disk,
# uncommitted and NOT rolled back (rollback_paths is not even built until after
# Step 5b), and emits nothing. THE EXIT STATUS IS AUTHORITATIVE: on a non-zero
# exit, reconcile the task files rather than trusting an empty record set.
# Making that path transactional is a separate concern from this output
# contract -- it needs the rollback set assembled before Step 3.
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

# --- Structured-record buffer (t1661) ----------------------------------------
# Holds the Steps 3-5b records until Step 6 reaches a terminal success.
# See the "RECORDS MEAN ..." note in the header above.
# Deliberately defined here, ABOVE Step 6: tests/test_fold_mark.sh's
# install_prefix_commit_block excises Step 6 to rebuild t1599_2's pre-fix
# commit block, and that rebuild must not take the buffer with it.
_fold_records=()
_fold_emit() { _fold_records+=( "$1" ); }
_fold_flush_records() {
    local r
    for r in ${_fold_records[@]+"${_fold_records[@]}"}; do printf '%s\n' "$r"; done
    _fold_records=()
}
# --- end structured-record buffer --------------------------------------------

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
#
# The derived active_gates* tuple (t635_33) is deliberately NOT unioned — it is
# profile-filtered enforcement state, recomputed at the next claim; unioning
# would corrupt it. The aitask_update.sh write below preserves the primary's
# tuple as-is; when this union changes `gates:`, the tuple's gates-half digest
# stops matching and every reader falls back to the raw field (fail-closed)
# until re-materialization.
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

# boardgroup (t1243_8) is a scalar board-group slug and follows the same rule:
# NOT unioned/merged on fold. The primary keeps its own group membership. There
# is nothing to union — group identity is (column, slug), so adopting a folded
# task's slug could silently move the primary into a different group, and the
# folded file is deleted at archival anyway.

# followup_kind (t1468_1) is a scalar carrying instance-specific provenance and
# follows the same rule: NOT unioned/merged on fold. It answers "how was THIS
# task spawned", so adopting a folded task's kind would attribute the primary's
# origin to a task it merely absorbed — and the primary keeps its own. The
# folded file is deleted at archival anyway.

# plan_approved_at (t1595) is a scalar recording that THIS task's own plan was
# approved and deliberately deferred, so it follows the same rule: NOT
# unioned/merged on fold. Adopting a folded task's marker would claim the
# primary's plan is implementation-ready on the strength of a different task's
# approval; the primary keeps its own, and the folded file is deleted at
# archival anyway.

"$SCRIPT_DIR/aitask_update.sh" --batch "$primary_id" \
    --folded-tasks "$full_csv" \
    ${file_ref_args[@]+"${file_ref_args[@]}"} \
    ${verifies_args[@]+"${verifies_args[@]}"} \
    ${gates_args[@]+"${gates_args[@]}"} \
    ${abd_args[@]+"${abd_args[@]}"} \
    --silent >/dev/null
_fold_emit "PRIMARY_UPDATED:${primary_id}"

# Step 4: mark each new folded task. Clear its risk_mitigation_tasks: the list
# is instance-specific (see note above) and a folded task no longer drives its
# own mitigation flow once merged into the primary.
for fid in "${folded_ids[@]}"; do
    fid="${fid#t}"
    "$SCRIPT_DIR/aitask_update.sh" --batch "$fid" --status Folded --folded-into "$primary_id" --risk-mitigation-tasks "" --silent >/dev/null
    _fold_emit "FOLDED:${fid}"

    # Step 4b: child task parent cleanup
    if [[ "$fid" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        fp="${BASH_REMATCH[1]}"
        fc="${BASH_REMATCH[2]}"
        "$SCRIPT_DIR/aitask_update.sh" --batch "$fp" --remove-child "t${fid}" --silent >/dev/null 2>&1 || true
        _fold_emit "CHILD_REMOVED:${fp}:${fc}"
    fi
done

# Step 5: transitive tasks point at primary
for tid in "${transitive_ids[@]}"; do
    tid="${tid#t}"
    [[ -z "$tid" ]] && continue
    "$SCRIPT_DIR/aitask_update.sh" --batch "$tid" --folded-into "$primary_id" --silent >/dev/null 2>&1 || true
    _fold_emit "TRANSITIVE:${tid}"
done

# Step 5b (t1030_3, extended t1076_2): transfer folded tasks' attachments AND
# artifacts to the primary. For attachments: re-bind the refcount (so blobs
# survive the folded files' deletion at archival) AND merge the folded
# frontmatter entries into the primary (so they stay accessible via
# `ait attach ls/get <primary>` and are decref-discoverable). For artifacts:
# merge only the handle-only `artifacts:` frontmatter entries (dedupe by
# handle) — manifests are handle-keyed with no ownership field, so there is no
# ledger to re-bind. Processes direct + transitive folded tasks; both have
# their files deleted at archival. All under ONE global attach lock. Skipped
# entirely when no folded task carries an attachment or artifact (the common
# case) so a plain fold never touches the attach lock or creates the
# attachments/ tree.

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

# _fold_transfer_artifacts <primary_file> <folded_file...> -- merge each folded
# file's `artifacts:` frontmatter entries into the primary, deduping by handle
# (t1076_2). Handles are the identity — one entry per handle per task, minted
# once by `ait artifact create` — so a handle the primary already lists is
# simply skipped. Names are advisory (get/rm are handle-addressed), so no name
# uniquing is needed. No ledger work: artifact manifests are handle-keyed with
# no ownership field.
_fold_transfer_artifacts() {
    local primary_file="$1"; shift
    local py; py="$(require_python)"
    declare -A seen_handles=()
    local f recs ln k v ah ak an have

    # Seed the seen set from the primary's current artifacts (no append).
    recs="$(read_yaml_mappings "$primary_file" artifacts)" || true
    ah=""; have=false
    while IFS= read -r ln; do
        if [[ -z "$ln" ]]; then
            $have && [[ -n "$ah" ]] && seen_handles["$ah"]=1
            ah=""; have=false; continue
        fi
        have=true; k="${ln%%=*}"; v="${ln#*=}"
        [[ "$k" == "handle" ]] && ah="$v"
    done <<< "$recs"
    $have && [[ -n "$ah" ]] && seen_handles["$ah"]=1

    for f in "$@"; do
        [[ -f "$f" ]] || continue
        recs="$(read_yaml_mappings "$f" artifacts)" || true
        [[ -z "$recs" ]] && continue
        ah=""; ak=""; an=""; have=false
        while IFS= read -r ln; do
            if [[ -z "$ln" ]]; then
                $have && _fold_merge_one_artifact
                ah=""; ak=""; an=""; have=false; continue
            fi
            have=true; k="${ln%%=*}"; v="${ln#*=}"
            case "$k" in
                handle) ah="$v" ;; kind) ak="$v" ;; name) an="$v" ;;
            esac
        done <<< "$recs"
        $have && _fold_merge_one_artifact
    done
}

# _fold_merge_one_artifact -- append the current folded artifact entry
# (dynamic-scope locals ah/ak/an from _fold_transfer_artifacts) into the
# primary, updating the seen set. Skips on missing handle or a handle already
# on the primary.
_fold_merge_one_artifact() {
    [[ -n "$ah" ]] || return 0
    [[ -n "${seen_handles[$ah]:-}" ]] && return 0   # dup handle: already owned
    "$py" "$SCRIPT_DIR/lib/frontmatter_patch.py" append "$primary_file" artifacts \
        "handle=$ah" ${ak:+"kind=$ak"} ${an:+"name=$an"}
    seen_handles["$ah"]=1
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

# _fold_attach_txn -- rebind + merge (attachments and artifacts), run as one
# transaction under the attach lock.
_fold_attach_txn() {
    _fold_rebind_refs "$primary_id" \
        "${folded_ids[@]}" ${transitive_ids[@]+"${transitive_ids[@]}"}
    _fold_transfer_attachments "$primary_file" \
        ${folded_files[@]+"${folded_files[@]}"} \
        ${transitive_files[@]+"${transitive_files[@]}"}
    _fold_transfer_artifacts "$primary_file" \
        ${folded_files[@]+"${folded_files[@]}"} \
        ${transitive_files[@]+"${transitive_files[@]}"}
}

# Only enter the attach transaction if a folded/transitive task actually carries
# an attachment or an artifact — keeps the common bare fold off the attach lock
# and free of the attachment libs (detection uses read_yaml_mappings, already
# available; the libs are sourced lazily only when needed). Artifacts need no
# ledger rebind (manifests are handle-keyed) — only the frontmatter merge — but
# they share the same transaction and lock.
_fold_any_attach_or_artifacts=false
for _ff in ${folded_files[@]+"${folded_files[@]}"} ${transitive_files[@]+"${transitive_files[@]}"}; do
    [[ -f "$_ff" ]] || continue
    if read_yaml_mappings "$_ff" attachments 2>/dev/null | grep -q '^hash='; then
        _fold_any_attach_or_artifacts=true; break
    fi
    if read_yaml_mappings "$_ff" artifacts 2>/dev/null | grep -q '^handle='; then
        _fold_any_attach_or_artifacts=true; break
    fi
done
if [[ "$_fold_any_attach_or_artifacts" == true ]]; then
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

# _fold_task_id_of_path -- task/plan id owning a repo path, empty when the path
# is not a task/plan file.
#
# Only the CANONICAL direct locations count -- `<TASK_DIR>/t<N>_*.md` and
# `<TASK_DIR>/t<P>/t<P>_<C>_*.md` (same for `<PLAN_DIR>`/`p`). Matching on the
# basename alone was too loose: `aitasks/metadata/t10_unrelated.md` and
# `aitasks/archived/t10_old.md` both parsed as task 10 and would have been
# ACCEPTED by the guard when folding into t10 -- exactly the unknown-metadata
# class default-deny exists to refuse. A child's filename id must also agree
# with its enclosing directory, so `aitasks/t99/t10_2_x.md` is not task 10_2.
# Anything outside these shapes returns empty and falls to the deny branch.
_fold_task_id_of_path() {
    local p="$1" root pfx rest dir base pnum
    case "$p" in
        "$TASK_DIR"/*) root="$TASK_DIR"; pfx=t ;;
        "$PLAN_DIR"/*) root="$PLAN_DIR"; pfx=p ;;
        *) return 0 ;;
    esac
    rest="${p#"$root"/}"
    # Deeper than <dir>/<file> is never a canonical task/plan location.
    case "$rest" in */*/*) return 0 ;; esac
    if [[ "$rest" == */* ]]; then
        dir="${rest%%/*}"
        base="${rest#*/}"
        [[ "$dir" =~ ^${pfx}([0-9]+)$ ]] || return 0
        pnum="${BASH_REMATCH[1]}"
        [[ "$base" =~ ^${pfx}${pnum}_([0-9]+)_.*\.md$ ]] || return 0
        printf '%s_%s' "$pnum" "${BASH_REMATCH[1]}"
        return 0
    fi
    [[ "$rest" =~ ^${pfx}([0-9]+)_.*\.md$ ]] && printf '%s' "${BASH_REMATCH[1]}"
    return 0
}

# Refusal reason set by _fold_amend_guard; read by the amend arm.
_fold_amend_refusal=""

# _fold_amend_guard -- decide whether HEAD is this fold's commit to rewrite.
# 0 = safe to amend, 1 = refuse (reason in _fold_amend_refusal).
#
# DEFAULT-DENY. Every path in HEAD must match one of three accept branches;
# anything else refuses. There is deliberately no "warn and proceed" bucket: a
# warn-only branch would wave through the foreign `aitasks/metadata/gates.yaml`
# that commit 21219b0b4 actually swallowed, which is the failure this exists to
# stop.
#
# It never die()s. Steps 3-5b have already written every fold mutation to disk
# by the time Step 6 runs, so a bare die() here would leave the primary and
# folded task files dirty -- and a dirty task-file set is exactly what the next
# unscoped commit sweeps up, re-creating this task's own defect. The caller
# runs _fold_rollback first, matching the other two failure exits in this block.
_fold_amend_guard() {
    local ups="" head_short="" p pid
    local -A owned_ids=()
    local -a foreign=()

    # Ids whose task/plan files this fold legitimately touches.
    local _oid
    for _oid in "$primary_id" ${folded_ids[@]+"${folded_ids[@]}"} \
                ${transitive_ids[@]+"${transitive_ids[@]}"}; do
        _oid="${_oid#t}"
        owned_ids["$_oid"]=1
        # A child id also legitimises its parent: aitask_create.sh co-commits
        # the parent file when it creates a child (:861-862), and fold marking
        # edits it via --remove-child.
        [[ "$_oid" =~ ^([0-9]+)_[0-9]+$ ]] && owned_ids["${BASH_REMATCH[1]}"]=1
    done

    # The fold's own file set, including the attachment-meta rebinds, which are
    # not .md paths and would otherwise fall through to the deny branch.
    local -A own_paths=()
    for p in "${rollback_paths[@]}"; do own_paths["$p"]=1; done

    local labels_path
    labels_path="$(labels_file_path)"

    while IFS= read -r p; do
        [[ -n "$p" ]] || continue
        [[ -n "${own_paths[$p]:-}" ]] && continue
        pid="$(_fold_task_id_of_path "$p")"
        if [[ -n "$pid" ]]; then
            [[ -n "${owned_ids[$pid]:-}" ]] && continue
        elif [[ "$p" == "$labels_path" ]]; then
            # The one non-task path an amend-preceding step legitimately
            # co-commits: aitask_create.sh stages the label vocabulary at every
            # commit site. Refusing it would break the fold step of
            # aitask-explore / aitask-pr-import on their normal path.
            warn "amend will also carry ${p} (co-committed label vocabulary)"
            continue
        fi
        foreign+=( "$p" )
    done < <(task_git show --name-only --format='' HEAD 2>/dev/null || true)

    head_short="$(task_git rev-parse --short HEAD 2>/dev/null || echo "HEAD")"

    if (( ${#foreign[@]} > 0 )); then
        _fold_amend_refusal="refusing --commit-mode amend: HEAD (${head_short}) carries paths outside this fold:
$(printf '  %s\n' "${foreign[@]}")
Re-run with --commit-mode fresh."
        return 1
    fi

    # Rewriting a published commit changes its SHA under everyone who has it,
    # and aitask_sync.sh pushes non-force, so the next sync fails outright.
    #
    # ACCEPTED RESIDUAL: this reads the LOCAL remote-tracking ref and
    # deliberately does not fetch (a fold has no business doing network I/O).
    # A push made elsewhere since the last fetch is therefore missed. It can
    # under-detect a published commit; it can never wrongly refuse an
    # unpublished one.
    ups="$(task_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
    if [[ -n "$ups" ]] && task_git merge-base --is-ancestor HEAD "$ups" 2>/dev/null; then
        _fold_amend_refusal="refusing --commit-mode amend: HEAD (${head_short}) is already published on ${ups}; amending would rewrite pushed history and break the next sync.
Re-run with --commit-mode fresh."
        return 1
    fi

    return 0
}

# Step 6: commit
case "$commit_mode" in
    fresh)
        joined=""
        for fid in "${folded_ids[@]}"; do
            fid="${fid#t}"
            if [[ -n "$joined" ]]; then
                joined="${joined}, t${fid}"
            else
                joined="t${fid}"
            fi
        done
        # task_git_commit_scoped (lib/task_utils.sh) is the canonical scoped
        # commit: it stages only these paths, treats a failed `git status` as
        # unverified rather than clean, guards the empty pathspec, and passes
        # `-o` so an empty one is fatal instead of silently committing the whole
        # index. rollback_paths is already exactly this fold's file set, so no
        # separate derivation -- or separate fold_meta_relpaths add -- is needed.
        crc=0
        task_git_commit_scoped \
            "ait: Fold tasks into t${primary_id}: merge ${joined}" \
            "${rollback_paths[@]}" || crc=$?
        case "$crc" in
            0)
                hash=$(task_git rev-parse --short HEAD 2>/dev/null || echo "")
                _fold_flush_records
                echo "COMMITTED:${hash}"
                ;;
            2)
                # Verified nothing to commit for these paths -- benign no-op.
                # A terminal SUCCESS: nothing was rolled back and the
                # mutations stand, so the records are honest -- flush them.
                _fold_flush_records
                echo "NO_COMMIT"
                ;;
            *)
                _fold_rollback
                die "fold commit failed — rolled back the whole fold transaction"
                ;;
        esac
        ;;
    amend)
        # Guard BEFORE staging, and roll back on refusal: the fold's on-disk
        # mutations are already written, and leaving them dirty hands the next
        # unscoped commit exactly the bystander this task removes.
        if ! _fold_amend_guard; then
            _fold_rollback
            die "$_fold_amend_refusal"
        fi
        (( ${#rollback_paths[@]} )) || die "internal: empty fold path set"
        # `add` only so an untracked path can be named by the pathspec.
        task_git add -- "${rollback_paths[@]}" >/dev/null 2>&1 || true
        if task_git commit --amend --no-edit -o --quiet -- "${rollback_paths[@]}" >/dev/null 2>&1; then
            _fold_flush_records
            echo "AMENDED"
        else
            _fold_rollback
            die "fold amend-commit failed — rolled back the whole fold transaction"
        fi
        ;;
    none)
        # The caller stages and commits; the mutations stand on disk either
        # way, so this is a terminal success and the records are flushed.
        _fold_flush_records
        echo "NO_COMMIT"
        ;;
    *)
        # Validated only here, after Steps 3-5b already wrote every mutation,
        # so this exit owes the same rollback as the other three -- otherwise it
        # leaves the task files dirty for the next unscoped commit to sweep.
        _fold_rollback
        die "invalid --commit-mode: $commit_mode"
        ;;
esac
