#!/usr/bin/env bash
# aitask_archive.sh - Archive completed tasks and their plan files
#
# Handles all non-interactive post-implementation archival:
#   - Task metadata updates (status, timestamps)
#   - File moves to archived directories
#   - Parent children_to_implement updates
#   - Lock releases
#   - Folded task cleanup
#   - Git staging and commit
#
# Outputs structured lines for the calling skill to handle interactive parts
# (issue updates, folded task warnings).
#
# Usage:
#   ./.aitask-scripts/aitask_archive.sh <task_num>              # Archive parent
#   ./.aitask-scripts/aitask_archive.sh <parent>_<child>        # Archive child
#   ./.aitask-scripts/aitask_archive.sh --dry-run <task_num>    # Preview
#   ./.aitask-scripts/aitask_archive.sh --no-commit <task_num>  # Stage only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# read_yaml_field and read_yaml_list come from lib/yaml_utils.sh, which
# task_utils.sh sources transitively.

# --- Configuration ---
DRY_RUN=false
NO_COMMIT=false
SUPERSEDED=false
OBSOLETE=false
# The run's archived_reason ("" | superseded | obsolete), derived once from the
# two flags above, which nothing but parse_args reads. It names the task the
# flag targets and ONLY that task: a parent the child flow auto-archives in the
# same run gets its own reason from parent_archive_decision (t2254).
ARCHIVE_REASON=""
WITH_DEFERRED_CARRYOVER=false
IGNORE_GATES=false
TASK_NUM=""

# Paths whose DELETION handle_folded_tasks staged. They must reach the archival
# commit's pathspec: `task_git rm` stages the removal, but a path-scoped commit
# only commits the paths it names, so omitting these leaves the deletion staged
# in the shared index for an unrelated session's commit to sweep up — the exact
# defect t1599_4 exists to close. Accumulated, never reset per call: the child
# flow calls handle_folded_tasks for the child and again for the parent, and both
# precede the single commit (t1599_4).
FOLDED_DELETED_PATHS=()

# Ids this run archived as completed work (the task, plus a parent the child flow
# auto-archived). Read by fire_landed_triggers after the archival, never before.
LANDED_IDS=()

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_archive.sh [options] <task_num>

Archive a completed task and its plan file.

Arguments:
  task_num        Task number: 166 or t166 (parent), 16_2 or t16_2 (child)

Options:
  --dry-run                    Preview actions without executing
  --no-commit                  Stage changes but don't commit
  --superseded                 Mark task as superseded (adds archived_reason: superseded)
  --obsolete                   Mark task as obsolete (adds archived_reason: obsolete);
                               used by `ait obsolete review`. Exclusive with --superseded
                               The reason goes on the named task only; a parent the
                               child flow auto-archives takes it only when none of
                               its children landed
  --with-deferred-carryover    For manual_verification tasks: archive even when
                               deferred items remain, creating a new
                               manual_verification task seeded with just those
                               deferred items
  --ignore-gates               Archive even when the task declares gates that
                               are not all `pass` (escape hatch — bypasses the
                               gate-guard added in t635_4)
  --help, -h                   Show this help

Output format (structured lines for skill parsing):
  ARCHIVED_TASK:<path>              Archived task file
  ARCHIVED_PLAN:<path>              Archived plan file
  ISSUE:<task_num>:<issue_url>      Task has linked issue needing user action
  PR:<task_num>:<pr_url>            Task has linked PR needing user action
  PARENT_ARCHIVED:<path>            Parent task also archived (all children done)
  PARENT_ISSUE:<task_num>:<url>     Parent has linked issue needing user action
  PARENT_PR:<task_num>:<url>        Parent has linked PR needing user action
  FOLDED_DELETED:<task_num>:<path>  Folded task was deleted
  FOLDED_ISSUE:<task_num>:<url>     Deleted folded task had linked issue
  FOLDED_PR:<task_num>:<url>        Deleted folded task had linked PR
  FOLDED_WARNING:<task_num>:<status> Folded task skipped (active status)
  COMMITTED:<hash>                  Git commit hash
  CARRYOVER_CREATED:<task_id>:<path> Carry-over manual_verification task
                                    created for deferred items
  GATE_PENDING:<csv>                Declared gates not all `pass` (gate-guard)

Exit codes:
  0  Success
  1  Generic error (invalid arguments, missing task, etc.)
  2  A pre-archive gate blocked archival. Either:
       - manual_verification items pending/deferred (VERIFICATION_PENDING /
         VERIFICATION_DEFERRED on stdout), or
       - declared gates not all `pass` (GATE_PENDING:<csv> + GATE_BLOCKED on
         stdout; override with --ignore-gates)

Examples:
  ./.aitask-scripts/aitask_archive.sh 166          # Archive parent task t166
  ./.aitask-scripts/aitask_archive.sh 16_2         # Archive child task t16_2
  ./.aitask-scripts/aitask_archive.sh --dry-run 42 # Preview archival of t42
EOF
}

# --- Argument Parsing ---
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --no-commit)
                NO_COMMIT=true
                shift
                ;;
            --superseded)
                SUPERSEDED=true
                shift
                ;;
            --obsolete)
                OBSOLETE=true
                shift
                ;;
            --with-deferred-carryover)
                WITH_DEFERRED_CARRYOVER=true
                shift
                ;;
            --ignore-gates)
                IGNORE_GATES=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            -*)
                die "Unknown option: $1. Use --help for usage."
                ;;
            *)
                if [[ "$1" =~ ^t?[0-9]+(_[0-9]+)?$ ]]; then
                    TASK_NUM="${1#t}"
                    shift
                else
                    die "Invalid task number: $1 (expected format: 166, t166, 16_2, or t16_2)"
                fi
                ;;
        esac
    done

    if [[ -z "$TASK_NUM" ]]; then
        die "Task number is required. Use --help for usage."
    fi
    if [[ "$SUPERSEDED" == true && "$OBSOLETE" == true ]]; then
        die "--superseded and --obsolete are mutually exclusive"
    fi
    if [[ "$SUPERSEDED" == true ]]; then
        ARCHIVE_REASON="superseded"
    elif [[ "$OBSOLETE" == true ]]; then
        ARCHIVE_REASON="obsolete"
    fi
}

# --- Helper: update task metadata for archival ---
# Sets status=Done, updates updated_at, adds completed_at, and adds
# archived_reason when <reason> is given. The reason is an explicit argument,
# never read from the run's flags: the caller decides it per file (t2254).
archive_metadata_update() {
    local file_path="$1"
    local reason="${2:-}"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M')

    if [[ "$DRY_RUN" == true ]]; then
        if [[ -n "$reason" ]]; then
            info "[dry-run] Would update metadata in $file_path (status=Done, timestamps, archived_reason=$reason)"
        else
            info "[dry-run] Would update metadata in $file_path (status=Done, timestamps)"
        fi
        return
    fi

    sed_inplace "s/^status: .*/status: Done/" "$file_path"
    sed_inplace "s/^updated_at: .*/updated_at: $timestamp/" "$file_path"
    # Add completed_at after updated_at (only if not already present)
    if ! grep -q "^completed_at:" "$file_path"; then
        awk -v ts="$timestamp" '/^updated_at:/{print; print "completed_at: " ts; next}1' "$file_path" > "$file_path.tmp" && mv "$file_path.tmp" "$file_path"
    fi
    # Add archived_reason for superseded / obsolete tasks
    if [[ -n "$reason" ]]; then
        if ! grep -q "^archived_reason:" "$file_path"; then
            awk -v r="$reason" '/^status:/{print; print "archived_reason: " r; next}1' "$file_path" > "$file_path.tmp" && mv "$file_path.tmp" "$file_path"
        fi
    fi
}

# --- Helper: move file to archive directory ---
archive_move() {
    local src="$1"
    local dest_dir="$2"

    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would move $src -> $dest_dir/"
        return
    fi

    mkdir -p "$dest_dir"
    mv "$src" "$dest_dir/"
}

# --- Helper: release lock (best-effort, idempotent) ---
release_lock() {
    local task_num="$1"

    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would release lock for t$task_num"
        return
    fi

    "$SCRIPT_DIR/aitask_lock.sh" --unlock "$task_num" 2>/dev/null || true
}

# --- Helper: prune shadow rejection store (best-effort, idempotent) ---
# A rejection is scoped to the task under review and is meaningless once the
# task archives, so the archival seam is where the store self-cleans. Archival
# never blocks on it: a LOCK_BUSY prune (a TUI mid-write) leaves the store in
# place for any later prune of the same id to finish.
prune_shadow_rejections() {
    local task_id="$1"

    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would prune shadow rejection store for t$task_id"
        return
    fi

    "$SCRIPT_DIR/aitask_shadow_rejected.sh" prune "$task_id" >/dev/null 2>&1 || true
}

# --- Helper: prune scratchpad notes store (best-effort, idempotent) ---
# Scratchpad notes are scoped to the task and dropped when it archives. Every
# call site runs after the task file has left aitasks/, and the store's lifecycle
# lock makes a racing open/save either finish before that move (so this prune
# removes its store) or refuse after it. A LOCK_BUSY prune leaves the store for
# any later prune of the same id.
prune_scratchpad() {
    local task_id="$1"

    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would prune scratchpad for t$task_id"
        return
    fi

    "$SCRIPT_DIR/aitask_scratchpad_store.sh" prune "$task_id" >/dev/null 2>&1 || true
}

# --- "Landed": one definition for an archived task file ---
# Completed work, as relations_consume.end_state reads it (task_relations.md
# D8): status Done and no archived_reason. A folded_into record also excludes
# it, as the landed trigger always required. Shared by the landed trigger and
# by the auto-archived parent's reason, so the two cannot drift apart.
archived_file_landed() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        return 1
    fi
    if [[ "$(read_yaml_field "$file" status 2>/dev/null || true)" != "Done" ]]; then
        return 1
    fi
    if [[ -n "$(read_yaml_field "$file" archived_reason 2>/dev/null || true)" ]]; then
        return 1
    fi
    if [[ -n "$(read_yaml_field "$file" folded_into 2>/dev/null || true)" ]]; then
        return 1
    fi
    return 0
}

# --- The reason for a parent the child flow auto-archives (t2254) ---
# parent_archive_decision <parent_num> <child_id> <child_reason>
#
# A --superseded / --obsolete flag names ONE task, the child. The parent it
# auto-archives is completed work when ANY of its children landed; it takes the
# child's reason only when every other child record was READ and none landed.
# Prints exactly one line and always returns 0 (it runs inside `$( )`):
#
#   LANDED|t<id>            a child landed: this one (archived without a reason)
#                           or an archived sibling, loose or bundled
#   NONE_LANDED|<n>         all <n> other child records were read, none landed,
#                           and the record set did not change across the scan
#   UNVERIFIED|<failure>    no record landed, but "none landed" is unproven: a
#                           record could not be read, or the records kept
#                           changing while they were scanned
#
# Positive landed evidence wins even when another record could not be read.
# Bundled records are read, not inferred from the bundle's existence: the
# candidates are the bundles _search_numbered_then_legacy and
# aitask_zip_old.sh cmd_unpack search (numbered, its .tar.gz twin, then the
# legacy old.tar.*), and each matching entry is extracted with
# _extract_from_archive into a tagged temp dir that the owning shell's EXIT
# sweep removes. An orphaned parent that later regains children is how bundled
# siblings arise.
#
# The negative verdict also needs a STABLE view. A record can move between the
# two locations while they are scanned one after the other: cmd_unpack copies a
# record loose before it drops it from the bundle, and zip_old writes the bundle
# before it deletes the loose file. Either handoff can land between the loose
# scan and the bundle scan, so whichever order they run in, the record is seen
# in neither. The scan therefore runs between two fingerprints of every evidence
# source (loose records and candidate bundles, by content checksum), and
# NONE_LANDED is certified only when they match. A changed view re-runs the
# scan, up to PARENT_SCAN_ATTEMPTS times, then reports UNVERIFIED. Residual: a
# change undone within one scan (two complete bundle operations inside it) is
# not seen.
#
# Test-only seam: AIT_ARCHIVE_PARENT_SCAN_HOOK=<cmd> runs between the loose and
# the bundle scan of every attempt, with AIT_ARCHIVE_SCAN_ATTEMPT exported; its
# output goes to stderr and its status is ignored.
PARENT_SCAN_ATTEMPTS=3

_child_bundle_candidates() {  # <parent_num> -> sets _CHILD_BUNDLES
    local numbered
    numbered=$(archive_path_for_id "$1" "$ARCHIVED_DIR")
    _CHILD_BUNDLES=("$numbered" "${numbered%.tar.zst}.tar.gz" \
                    "$ARCHIVED_DIR/old.tar.zst" "$ARCHIVED_DIR/old.tar.gz")
}

# One line per evidence source that exists now: path and content checksum.
# Reads _CHILD_BUNDLES; always returns 0.
_child_evidence_fingerprint() {  # <parent_num>
    local f sum
    for f in "$ARCHIVED_DIR/t$1/t$1_"*_*.md ${_CHILD_BUNDLES[@]+"${_CHILD_BUNDLES[@]}"}; do
        if [[ -z "$f" || ! -e "$f" ]]; then
            continue
        fi
        sum=$(cksum < "$f" 2>/dev/null) || sum="unreadable"
        printf '%s\t%s\n' "$f" "$sum"
    done
    return 0
}

parent_archive_decision() {
    local parent_num="$1" child_id="$2" child_reason="$3"
    if [[ -z "$child_reason" ]]; then
        echo "LANDED|t${child_id}"
        return 0
    fi

    local id_re="^t(${parent_num}_[0-9]+)_"
    local entry_re="(^|/)t${parent_num}/t(${parent_num}_[0-9]+)_[^/]*\.md$"
    local attempt failure n_read before after stable=false
    local f base sid b listing rc entry
    _child_bundle_candidates "$parent_num"

    for (( attempt = 1; attempt <= PARENT_SCAN_ATTEMPTS; attempt++ )); do
        failure=""
        n_read=0
        before=$(_child_evidence_fingerprint "$parent_num")

        # Loose records: aitasks/archived/t<P>/t<P>_<n>_*.md
        for f in "$ARCHIVED_DIR/t${parent_num}/t${parent_num}_"*_*.md; do
            if [[ ! -e "$f" ]]; then
                continue
            fi
            base=$(basename "$f")
            if [[ ! "$base" =~ $id_re ]]; then
                continue
            fi
            sid="${BASH_REMATCH[1]}"
            if [[ "$sid" == "$child_id" ]]; then
                continue    # this child: its in-memory reason is authoritative
            fi
            if [[ ! -r "$f" ]]; then
                if [[ -z "$failure" ]]; then
                    failure="unreadable $f"
                fi
                continue
            fi
            n_read=$((n_read + 1))
            if archived_file_landed "$f"; then
                echo "LANDED|t${sid}"
                return 0
            fi
        done

        if [[ -n "${AIT_ARCHIVE_PARENT_SCAN_HOOK:-}" ]]; then
            AIT_ARCHIVE_SCAN_ATTEMPT="$attempt" \
                bash -c "$AIT_ARCHIVE_PARENT_SCAN_HOOK" >&2 </dev/null || true
        fi

        # Bundled records
        for b in ${_CHILD_BUNDLES[@]+"${_CHILD_BUNDLES[@]}"}; do
            if [[ -z "$b" || ! -f "$b" ]]; then
                continue
            fi
            rc=0
            listing=$(_archive_list "$b") || rc=$?
            if [[ "$rc" -ne 0 ]]; then
                if [[ -z "$failure" ]]; then
                    failure="unlistable bundle $b"
                fi
                continue
            fi
            while IFS= read -r entry; do
                if [[ ! "$entry" =~ $entry_re ]]; then
                    continue
                fi
                sid="${BASH_REMATCH[2]}"
                if [[ "$sid" == "$child_id" ]]; then
                    continue
                fi
                if ! _extract_from_archive "$b" "$entry"; then
                    if [[ -z "$failure" ]]; then
                        failure="unextractable $entry in $b"
                    fi
                    continue
                fi
                n_read=$((n_read + 1))
                if archived_file_landed "$_AIT_EXTRACT_RESULT"; then
                    echo "LANDED|t${sid}"
                    return 0
                fi
            done <<< "$listing"
        done

        after=$(_child_evidence_fingerprint "$parent_num")
        if [[ "$before" == "$after" ]]; then
            stable=true
            break
        fi
    done

    if [[ "$stable" != true ]]; then
        echo "UNVERIFIED|child records kept changing during the scan (${PARENT_SCAN_ATTEMPTS} attempts)"
    elif [[ -n "$failure" ]]; then
        echo "UNVERIFIED|$failure"
    else
        echo "NONE_LANDED|$n_read"
    fi
    return 0
}

# --- Archive a parent task ---
archive_parent() {
    local task_num="$1"

    # Resolve files
    local task_file
    task_file=$(resolve_task_file "$task_num")
    local task_basename
    task_basename=$(basename "$task_file")

    local plan_file
    plan_file=$(resolve_plan_file "$task_num")

    info "Archiving parent task: $task_basename"

    # Check for linked issue before archival (output for skill)
    local issue_url
    issue_url=$(extract_issue_url "$task_file")
    if [[ -n "$issue_url" ]]; then
        echo "ISSUE:$task_num:$issue_url"
    fi

    # Check for related issues before archival (output for skill)
    local related_url
    while IFS= read -r related_url; do
        [[ -n "$related_url" ]] && echo "RELATED_ISSUE:$task_num:$related_url"
    done < <(extract_related_issues "$task_file")

    # Check for linked PR before archival (output for skill)
    local pr_url
    pr_url=$(extract_pr_url "$task_file")
    if [[ -n "$pr_url" ]]; then
        echo "PR:$task_num:$pr_url"
    fi

    # Handle folded tasks (before moving, so we can read from original path)
    handle_folded_tasks "$task_num" "$task_file"

    # Update metadata (the run's reason names this task)
    archive_metadata_update "$task_file" "$ARCHIVE_REASON"

    # Move task file to archive
    archive_move "$task_file" "$ARCHIVED_DIR"
    echo "ARCHIVED_TASK:$ARCHIVED_DIR/$task_basename"

    # Move plan file to archive (if exists)
    if [[ -n "$plan_file" && -f "$plan_file" ]]; then
        local plan_basename
        plan_basename=$(basename "$plan_file")
        archive_move "$plan_file" "$ARCHIVED_PLAN_DIR"
        echo "ARCHIVED_PLAN:$ARCHIVED_PLAN_DIR/$plan_basename"
    fi

    # Release lock
    release_lock "$task_num"
    prune_shadow_rejections "$task_num"
    prune_scratchpad "$task_num"

    # Git staging and commit
    if [[ "$DRY_RUN" != true ]]; then
        # The staging below is already narrow; the pathspec on the commit is what
        # stops a concurrent session's *staged* file riding along (t1599_4).
        local -a commit_paths=( "$ARCHIVED_DIR/$task_basename" "$task_file" )
        # Folded-task deletions were staged by handle_folded_tasks; name them or
        # the removals stay in the shared index (t1599_4).
        commit_paths+=( ${FOLDED_DELETED_PATHS[@]+"${FOLDED_DELETED_PATHS[@]}"} )
        task_git add "$ARCHIVED_DIR/$task_basename"
        if [[ -n "$plan_file" ]]; then
            local plan_basename
            plan_basename=$(basename "$plan_file")
            task_git add "$ARCHIVED_PLAN_DIR/$plan_basename" 2>/dev/null || true
            commit_paths+=( "$ARCHIVED_PLAN_DIR/$plan_basename" "$plan_file" )
        fi
        # Stage deletion of original task/plan paths (files already moved by archive_move).
        # Narrow to specific paths so we don't sweep in unrelated in-progress edits by sibling agents.
        task_git add -u "$task_file" 2>/dev/null || true
        if [[ -n "$plan_file" ]]; then
            task_git add -u "$plan_file" 2>/dev/null || true
        fi

        if [[ "$NO_COMMIT" != true ]]; then
            # --no-stage: the `add -u` above is deliberate (it stages the deletion of
            # the moved-from paths without adding anything else); letting the helper
            # re-stage would be a no-op at best and widen the set at worst.
            local crc=0
            task_git_commit_scoped --no-stage \
                "ait: Archive completed t${task_num} task and plan files" \
                "${commit_paths[@]}" || crc=$?
            if [[ "$crc" -eq 0 ]]; then
                local commit_hash
                commit_hash=$(task_git rev-parse --short HEAD)
                echo "COMMITTED:$commit_hash"
                # The landed trigger fires after the archive COMMIT only: never for
                # --no-commit (stage only) or a verified nothing-to-commit, and
                # only for completed work (no reason).
                if [[ -z "$ARCHIVE_REASON" ]]; then
                    LANDED_IDS+=("$task_num")
                fi
            elif [[ "$crc" -eq 2 ]]; then
                # Verified nothing to commit. Say so: the pre-t1599_4 code aborted
                # here under `set -e`, so silence would be a new failure mode.
                warn "nothing to commit for t${task_num} archival — no commit made"
            else
                die "archive commit failed for t${task_num}"
            fi
        fi
    fi
}

# --- Handle folded tasks cleanup ---
handle_folded_tasks() {
    local task_num="$1"
    local archived_task_file="$2"

    local folded_raw
    folded_raw=$(parse_yaml_list "$(read_yaml_field "$archived_task_file" "folded_tasks")")

    if [[ -z "$folded_raw" ]]; then
        return
    fi

    IFS=',' read -ra folded_ids <<< "$folded_raw"
    for folded_id in "${folded_ids[@]}"; do
        # Strip leading 't' if present
        folded_id="${folded_id#t}"
        if [[ -z "$folded_id" ]]; then
            continue
        fi

        # Extract numeric part for lock release
        local folded_num="$folded_id"

        # Resolve the folded task file (handles both parent and child task IDs)
        local folded_file
        if [[ "$folded_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
            local fp="${BASH_REMATCH[1]}"
            local fc="${BASH_REMATCH[2]}"
            folded_file=$(ls "$TASK_DIR"/t"${fp}"/t"${fp}"_"${fc}"_*.md 2>/dev/null | head -1 || true)
        else
            folded_file=$(ls "$TASK_DIR"/t"${folded_id}"_*.md 2>/dev/null | head -1 || true)
        fi

        if [[ -z "$folded_file" ]]; then
            # Already deleted or archived — skip silently
            continue
        fi

        # Check status
        local folded_status
        folded_status=$(read_task_status "$folded_file")

        if [[ "$folded_status" == "Implementing" || "$folded_status" == "Done" ]]; then
            echo "FOLDED_WARNING:$folded_id:$folded_status"
            continue
        fi

        # Check for linked issue before deletion
        local folded_issue
        folded_issue=$(extract_issue_url "$folded_file")
        if [[ -n "$folded_issue" ]]; then
            echo "FOLDED_ISSUE:$folded_id:$folded_issue"
        fi

        # Check for related issues on folded task before deletion
        local folded_related
        while IFS= read -r folded_related; do
            [[ -n "$folded_related" ]] && echo "FOLDED_RELATED_ISSUE:$folded_id:$folded_related"
        done < <(extract_related_issues "$folded_file")

        # Check for linked PR before deletion
        local folded_pr_url
        folded_pr_url=$(extract_pr_url "$folded_file")
        if [[ -n "$folded_pr_url" ]]; then
            echo "FOLDED_PR:$folded_id:$folded_pr_url"
        fi

        if [[ "$DRY_RUN" == true ]]; then
            info "[dry-run] Would delete folded task: $folded_file"
            prune_scratchpad "$folded_id"
            continue
        fi

        # If folded task is a child, remove from its parent's children_to_implement
        # (safety-net — normally handled at fold time by Task Fold Marking Procedure)
        if [[ "$folded_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
            local fold_parent="${BASH_REMATCH[1]}"
            "$SCRIPT_DIR/aitask_update.sh" --batch "$fold_parent" --remove-child "t${folded_id}" --silent 2>/dev/null || true
        fi

        # Delete folded task file and plan. Every removed path is recorded so the
        # archival commit's pathspec can name it (see FOLDED_DELETED_PATHS).
        task_git rm "$folded_file" --quiet
        FOLDED_DELETED_PATHS+=( "$folded_file" )
        # Delete plan file (handles both parent and child task IDs). Iterate the
        # glob rather than passing it straight to `task_git rm`, so each removed
        # path is known individually; `-e` also filters the unexpanded glob.
        local _folded_plan
        if [[ "$folded_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
            local fp="${BASH_REMATCH[1]}"
            local fc="${BASH_REMATCH[2]}"
            for _folded_plan in "$PLAN_DIR"/p"${fp}"/p"${fp}"_"${fc}"_*.md; do
                [[ -e "$_folded_plan" ]] || continue
                task_git rm "$_folded_plan" --quiet 2>/dev/null || continue
                FOLDED_DELETED_PATHS+=( "$_folded_plan" )
            done
        else
            for _folded_plan in "$PLAN_DIR"/p"${folded_id}"_*.md; do
                [[ -e "$_folded_plan" ]] || continue
                task_git rm "$_folded_plan" --quiet 2>/dev/null || continue
                FOLDED_DELETED_PATHS+=( "$_folded_plan" )
            done
        fi
        echo "FOLDED_DELETED:$folded_id:$folded_file"
        # The folded task file is deleted above, so its scratchpad goes with it.
        # (Shadow rejection stores are not pruned for folded tasks.)
        prune_scratchpad "$folded_id"

        # Release lock for folded task
        release_lock "$folded_num"
    done
}

# --- Archive a child task ---
archive_child() {
    local parent_num="$1"
    local child_num="$2"
    local task_id="${parent_num}_${child_num}"

    # Resolve child files
    local child_task_file
    child_task_file=$(resolve_task_file "$task_id")
    local child_task_basename
    child_task_basename=$(basename "$child_task_file")

    local child_plan_file
    child_plan_file=$(resolve_plan_file "$task_id")

    # Resolve parent files (needed for potential parent archival)
    local parent_task_file
    parent_task_file=$(resolve_task_file "$parent_num")
    local parent_task_basename
    parent_task_basename=$(basename "$parent_task_file")

    # This run also archives the parent when no other child is left to
    # implement (the `remaining_children` test below, decided here before
    # anything is written): the parent's approvals are then checked as well,
    # while refusing still leaves the child and the parent untouched (t2281).
    local sibling other_children=""
    while IFS= read -r sibling; do
        sibling="${sibling#t}"
        [[ -z "$sibling" || "$sibling" == "$task_id" ]] || other_children+="$sibling "
    done < <(read_yaml_list "$parent_task_file" "children_to_implement" | tr ',' '\n')
    [[ -n "$other_children" ]] || approval_guard "$parent_num"

    # Function-scoped parent plan paths, populated later if the parent gets auto-archived.
    # Declared here so the commit section can see the original (pre-move) path for staging.
    local parent_plan_file=""
    local parent_plan_basename=""
    # The auto-archived parent's own reason ("" = completed work), decided by
    # parent_archive_decision; the commit section reads it for the landed list.
    local parent_reason=""

    info "Archiving child task: $child_task_basename (parent: $parent_task_basename)"

    # Cache parent issue/PR/related_issues BEFORE --remove-child rewrites the file
    # (aitask_update.sh may strip fields it doesn't know about)
    local cached_parent_issue
    cached_parent_issue=$(extract_issue_url "$parent_task_file")
    local cached_parent_related
    cached_parent_related=$(extract_related_issues "$parent_task_file")
    local cached_parent_pr
    cached_parent_pr=$(extract_pr_url "$parent_task_file")

    # Check for linked issue on child
    local child_issue
    child_issue=$(extract_issue_url "$child_task_file")
    if [[ -n "$child_issue" ]]; then
        echo "ISSUE:$task_id:$child_issue"
    fi

    # Check for related issues on child
    local child_related
    while IFS= read -r child_related; do
        [[ -n "$child_related" ]] && echo "RELATED_ISSUE:$task_id:$child_related"
    done < <(extract_related_issues "$child_task_file")

    # Check for linked PR on child
    local child_pr
    child_pr=$(extract_pr_url "$child_task_file")
    if [[ -n "$child_pr" ]]; then
        echo "PR:$task_id:$child_pr"
    fi

    # Update parent's children_to_implement
    if [[ "$DRY_RUN" == true ]]; then
        info "[dry-run] Would remove t${task_id} from parent's children_to_implement"
    else
        "$SCRIPT_DIR/aitask_update.sh" --batch "$parent_num" --remove-child "t${task_id}" --silent
    fi

    # Handle folded tasks for child (if any) — must be before archive_move
    handle_folded_tasks "$task_id" "$child_task_file"

    # Update child metadata (the run's reason names this child)
    archive_metadata_update "$child_task_file" "$ARCHIVE_REASON"

    # Move child task to archive
    local child_archive_dir="$ARCHIVED_DIR/t${parent_num}"
    archive_move "$child_task_file" "$child_archive_dir"
    echo "ARCHIVED_TASK:$child_archive_dir/$child_task_basename"

    # Move child plan to archive (if exists)
    if [[ -n "$child_plan_file" && -f "$child_plan_file" ]]; then
        local child_plan_basename
        child_plan_basename=$(basename "$child_plan_file")
        local child_plan_archive_dir="$ARCHIVED_PLAN_DIR/p${parent_num}"
        archive_move "$child_plan_file" "$child_plan_archive_dir"
        echo "ARCHIVED_PLAN:$child_plan_archive_dir/$child_plan_basename"
    fi

    # Release child lock
    release_lock "$task_id"
    prune_shadow_rejections "$task_id"
    prune_scratchpad "$task_id"

    # Check if all children are complete
    local remaining_children
    remaining_children=$(read_yaml_list "$parent_task_file" "children_to_implement")

    local parent_archived=false
    if [[ -z "$remaining_children" ]]; then
        info "All child tasks complete — archiving parent task as well."

        # Emit cached parent issue/related/PR (read before --remove-child)
        if [[ -n "$cached_parent_issue" ]]; then
            echo "PARENT_ISSUE:$parent_num:$cached_parent_issue"
        fi

        local parent_related
        while IFS= read -r parent_related; do
            [[ -n "$parent_related" ]] && echo "PARENT_RELATED_ISSUE:$parent_num:$parent_related"
        done <<< "$cached_parent_related"

        if [[ -n "$cached_parent_pr" ]]; then
            echo "PARENT_PR:$parent_num:$cached_parent_pr"
        fi

        # Remove empty child directories
        if [[ "$DRY_RUN" != true ]]; then
            rmdir "$TASK_DIR/t${parent_num}/" 2>/dev/null || true
            rmdir "$PLAN_DIR/p${parent_num}/" 2>/dev/null || true
        else
            info "[dry-run] Would remove empty child dirs"
        fi

        # Handle folded tasks for parent (if any)
        handle_folded_tasks "$parent_num" "$parent_task_file"

        # The parent's own reason (t2254): the run's flag names the child only.
        # `|| decision=""` routes a failed helper into the unverified branch
        # below instead of letting errexit abort a half-done archival.
        local decision verdict detail
        decision=$(parent_archive_decision "$parent_num" "$task_id" "$ARCHIVE_REASON") || decision=""
        verdict="${decision%%|*}"
        detail="${decision#*|}"
        case "$verdict" in
            NONE_LANDED)
                parent_reason="$ARCHIVE_REASON"
                info "Parent t${parent_num}: no child landed (${detail} other archived child record(s) read) — archiving the parent as ${parent_reason} too."
                ;;
            LANDED)
                parent_reason=""
                if [[ -n "$ARCHIVE_REASON" ]]; then
                    info "Parent t${parent_num}: ${detail} landed — archiving the parent as completed work."
                fi
                ;;
            *)
                parent_reason=""
                if [[ "$verdict" != "UNVERIFIED" || -z "$detail" ]]; then
                    detail="decision helper failed"
                fi
                warn "Parent t${parent_num}: could not read every child record (${detail}) — no proof that none landed, so the parent is archived as completed work."
                ;;
        esac

        # Archive parent task
        archive_metadata_update "$parent_task_file" "$parent_reason"
        archive_move "$parent_task_file" "$ARCHIVED_DIR"
        echo "PARENT_ARCHIVED:$ARCHIVED_DIR/$parent_task_basename"

        # Archive parent plan (if exists). Assigns the function-scoped parent_plan_file
        # and parent_plan_basename so the commit section can reference the original path.
        parent_plan_file=$(resolve_plan_file "$parent_num")
        if [[ -n "$parent_plan_file" && -f "$parent_plan_file" ]]; then
            parent_plan_basename=$(basename "$parent_plan_file")
            archive_move "$parent_plan_file" "$ARCHIVED_PLAN_DIR"
            echo "ARCHIVED_PLAN:$ARCHIVED_PLAN_DIR/$parent_plan_basename"
        else
            parent_plan_file=""
        fi

        # Release parent lock
        release_lock "$parent_num"
        prune_shadow_rejections "$parent_num"
        prune_scratchpad "$parent_num"
        parent_archived=true
    fi

    # Git staging and commit
    if [[ "$DRY_RUN" != true ]]; then
        # Every staged path is also collected into commit_paths: the pathspec on the
        # commit is what stops a concurrent session's *staged* file riding along,
        # which the narrow staging alone cannot do (t1599_4).
        local -a commit_paths=( "$child_archive_dir/$child_task_basename" \
                                "$child_task_file" "$parent_task_file" )
        # As above: staged folded-task deletions must be in the pathspec.
        commit_paths+=( ${FOLDED_DELETED_PATHS[@]+"${FOLDED_DELETED_PATHS[@]}"} )

        # Stage archived child files
        task_git add "$child_archive_dir/$child_task_basename"
        if [[ -n "${child_plan_file:-}" ]]; then
            local child_plan_basename
            child_plan_basename=$(basename "$child_plan_file")
            task_git add "$ARCHIVED_PLAN_DIR/p${parent_num}/$child_plan_basename" 2>/dev/null || true
            commit_paths+=( "$ARCHIVED_PLAN_DIR/p${parent_num}/$child_plan_basename" \
                            "$child_plan_file" )
        fi

        # Stage deletion of original child task/plan paths (files already moved by archive_move).
        # Narrowed to specific paths so we don't sweep in unrelated in-progress edits by sibling agents.
        task_git add -u "$child_task_file" 2>/dev/null || true
        if [[ -n "${child_plan_file:-}" ]]; then
            task_git add -u "$child_plan_file" 2>/dev/null || true
        fi
        # Stage parent task file: in-place modification from --remove-child,
        # or deletion if parent was also archived (both cases handled by a single add -u on the original path).
        task_git add -u "$parent_task_file" 2>/dev/null || true

        # Stage parent archival if applicable
        if [[ "$parent_archived" == true ]]; then
            task_git add "$ARCHIVED_DIR/$parent_task_basename" 2>/dev/null || true
            commit_paths+=( "$ARCHIVED_DIR/$parent_task_basename" )
            if [[ -n "$parent_plan_basename" ]]; then
                task_git add "$ARCHIVED_PLAN_DIR/$parent_plan_basename" 2>/dev/null || true
                task_git add -u "$parent_plan_file" 2>/dev/null || true
                commit_paths+=( "$ARCHIVED_PLAN_DIR/$parent_plan_basename" "$parent_plan_file" )
            fi
        fi

        if [[ "$NO_COMMIT" != true ]]; then
            local commit_msg="ait: Archive completed t${task_id} task and plan files"
            if [[ "$parent_archived" == true ]]; then
                commit_msg="ait: Archive completed t${task_id} and parent t${parent_num} task and plan files"
            fi
            # --no-stage: the `add -u` calls above deliberately stage the moved-from
            # deletions and the parent's in-place edit; re-staging would widen the set.
            local crc=0
            task_git_commit_scoped --no-stage "$commit_msg" "${commit_paths[@]}" || crc=$?
            if [[ "$crc" -eq 0 ]]; then
                local commit_hash
                commit_hash=$(task_git rev-parse --short HEAD)
                echo "COMMITTED:$commit_hash"
                # The landed trigger fires after the archive COMMIT only (see
                # archive_parent), and per id for completed work only: the child
                # when the run carries no reason, the auto-archived parent (same
                # commit) when its own decided reason is empty (t2254).
                if [[ -z "$ARCHIVE_REASON" ]]; then
                    LANDED_IDS+=("$task_id")
                fi
                if [[ "$parent_archived" == true && -z "$parent_reason" ]]; then
                    LANDED_IDS+=("$parent_num")
                fi
            elif [[ "$crc" -eq 2 ]]; then
                warn "nothing to commit for t${task_id} archival — no commit made"
            else
                die "archive commit failed for t${task_id}"
            fi
        fi
    fi
}

# --- Helper: build a carry-over manual_verification task from deferred items ---
# Prints CARRYOVER_CREATED:<task_id>:<path> on stdout on success.
create_carryover_task() {
    local orig_file="$1"

    local items_tmp
    items_tmp=$(mktemp_suffixed "${TMPDIR:-/tmp}/ait_verify_defer_XXXXXX.txt")

    ./.aitask-scripts/aitask_verification_parse.sh parse "$orig_file" \
        | awk -F: '$3 == "defer" { sub(/^ITEM:[0-9]+:defer:[0-9]+:/, ""); print }' \
        > "$items_tmp"

    if [[ ! -s "$items_tmp" ]]; then
        rm -f "$items_tmp"
        return 0
    fi

    local orig_basename orig_name
    orig_basename=$(basename "$orig_file" .md)
    orig_name=$(echo "$orig_basename" | sed -E 's/^t[0-9]+(_[0-9]+)?_//')
    local carryover_name="${orig_name}_carryover"

    local orig_verifies_raw orig_verifies
    orig_verifies_raw=$(read_yaml_field "$orig_file" "verifies")
    orig_verifies=$(parse_yaml_list "$orig_verifies_raw")

    local orig_id
    orig_id=$(echo "$orig_basename" | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*/\1/')
    local carryover_desc="Carry-over of deferred manual-verification items from t${orig_id}. Re-pick this task to continue the remaining checklist."
    # followup_kind is carry_over, NOT manual_verification: the kind records how
    # the task came to exist, --type records how it is worked. The MV
    # cross-field invariant is one-directional (kind manual_verification
    # requires type manual_verification, not the converse), so this pairing is
    # legal (t1468_2).
    local create_args=(--batch --commit --silent
        --name "$carryover_name"
        --desc "$carryover_desc"
        --type manual_verification
        --priority medium --effort low
        --followup-kind carry_over
        --followup-of "$orig_id")
    if [[ -n "$orig_verifies" ]]; then
        create_args+=(--verifies "$orig_verifies")
    fi

    # Inherit premise_baseline (t1663_3) -- the same t1555 rule as
    # verification_baseline below: the carried premise is as old as its source,
    # so it is never re-stamped to HEAD. It travels through the CREATION call,
    # not a later aitask_update.sh, for two reasons. --verifies above would
    # otherwise seed HEAD at creation, so the creation commit would briefly
    # carry the wrong value. And the update writer's commit-existence check
    # would abort archival for an origin whose baseline names a commit a history
    # rewrite removed (the reader reports that state as history_rewritten, and
    # the carry-over should inherit it). The flag is ALWAYS passed: "" is what
    # keeps an origin without a baseline from producing a carry-over with one.
    #
    # Read through YAML (read_premise_seed_fields), never read_yaml_field: that
    # keeps a quoted scalar's quotes, so a valid '"<oid> @ <ts>"' would fail the
    # grammar and silently drop the inheritance.
    local orig_premise="" premise_out="" premise_rc=0 premise_line
    premise_out="$(read_premise_seed_fields "$orig_file")" || premise_rc=$?
    if [[ $premise_rc -ne 0 ]]; then
        warn "carry-over: origin premise_baseline unreadable (status $premise_rc); not inherited"
    else
        premise_line="$(printf '%s\n' "$premise_out" | head -n1)"
        case "$premise_line" in
            BASELINE:?*)
                if ! orig_premise="$(premise_baseline_canonical "${premise_line#BASELINE:}")"; then
                    orig_premise=""
                    warn "carry-over: origin premise_baseline is malformed; not inherited"
                fi
                ;;
            BASELINE_INVALID|INVALID:frontmatter)
                warn "carry-over: origin premise_baseline is malformed; not inherited"
                ;;
        esac
    fi
    create_args+=(--premise-baseline "$orig_premise")

    local new_file
    new_file=$(./.aitask-scripts/aitask_create.sh "${create_args[@]}")
    if [[ -z "$new_file" || ! -f "$new_file" ]]; then
        rm -f "$items_tmp"
        die "Carry-over task creation failed"
    fi

    ./.aitask-scripts/aitask_verification_parse.sh seed "$new_file" --items "$items_tmp"

    local new_id
    new_id=$(basename "$new_file" .md | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*/\1/')

    # Inherit verification_baseline (t1555_1). The carry-over re-seeds the
    # original's deferred item text verbatim into a task with a FRESH
    # created_at, so resetting the baseline would make the staleness pre-check
    # measure from the wrong commit -- which is precisely why the field exists
    # instead of reusing created_at. Written before the commit below so it
    # lands in the same seed commit.
    local orig_baseline
    orig_baseline=$(read_yaml_field "$orig_file" "verification_baseline")
    if [[ -n "$orig_baseline" ]]; then
        ./.aitask-scripts/aitask_update.sh --batch "$new_id" \
            --verification-baseline "$orig_baseline" --silent >/dev/null
    fi

    if [[ "$NO_COMMIT" != true ]]; then
        # Scoped: the seed edit is this task's own file and nothing else (t1599_4).
        local crc=0
        task_git_commit_scoped "ait: Seed carry-over checklist on t${new_id}" \
            "$new_file" || crc=$?
        if [[ "$crc" -eq 2 ]]; then
            warn "nothing to commit for the t${new_id} carry-over seed"
        elif [[ "$crc" -ne 0 ]]; then
            rm -f "$items_tmp"
            die "carry-over seed commit failed for t${new_id}"
        fi
    fi

    rm -f "$items_tmp"

    echo "CARRYOVER_CREATED:${new_id}:${new_file}"
}

# --- Helper: pre-archive gate for manual_verification tasks ---
# For non-manual_verification tasks, this is a no-op.
# For manual_verification tasks:
#   - Exits 2 with VERIFICATION_PENDING on stdout if any item is pending.
#   - Exits 2 with VERIFICATION_DEFERRED on stdout if any item is deferred
#     and --with-deferred-carryover was not passed.
#   - When --with-deferred-carryover is passed and only deferred items remain,
#     creates the carry-over task before archival proceeds.
verification_gate_and_carryover() {
    local task_num="$1"
    local task_file
    task_file=$(resolve_task_file "$task_num") || die "Task not found: $task_num"

    local issue_type
    issue_type=$(read_yaml_field "$task_file" "issue_type")
    [[ "$issue_type" == "manual_verification" ]] || return 0

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

    if [[ "$WITH_DEFERRED_CARRYOVER" == "true" ]] && echo "$gate_out" | grep -q '^DEFERRED:'; then
        if [[ "$DRY_RUN" == true ]]; then
            info "[dry-run] Would create carry-over task for deferred items in $task_file"
        else
            create_carryover_task "$task_file"
        fi
    fi
}

# --- Helper: gate-guard for declared gates (t635_4) ---
# Gate-guarded archival (decision D5): a task that declares gates (gates:
# frontmatter) may only archive once every declared gate is `pass`. Self-gating:
# a task with no declared gates is a no-op, so behavior is unchanged until
# t635_14 populates gates: (the mechanism is dormant today).
#
#   - NO_GATES / ALL_PASS -> return (archival proceeds).
#   - BLOCKED:<csv> and --ignore-gates NOT set -> emit GATE_PENDING:<csv> +
#     GATE_BLOCKED and exit 2 (mirrors verification_gate_and_carryover).
#   - --ignore-gates -> log an override notice and proceed (escape hatch).
gate_guard() {
    local task_num="$1"

    local decision
    decision=$("$SCRIPT_DIR/aitask_gate.sh" archive-ready "$task_num" 2>/dev/null || echo "NO_GATES")

    case "$decision" in
        BLOCKED:*)
            local pending="${decision#BLOCKED:}"
            if [[ "$IGNORE_GATES" == true ]]; then
                info "Ignoring gate-guard (--ignore-gates): archiving t${task_num} with pending gate(s): ${pending}"
                return 0
            fi
            echo "GATE_PENDING:${pending}"
            echo "GATE_BLOCKED: cannot archive until all declared gates pass (use --ignore-gates to override)"
            exit 2
            ;;
        *)  # NO_GATES, ALL_PASS, or any unexpected value -> do not block.
            return 0
            ;;
    esac
}

# --- Helper: approval guard for attended Codex (t2281) ---
# In a Codex tool shell, a task is not archived while one of its approval
# questions (plan, review, merge) is unanswered, declined, voided, answered
# without approving, approved but never recorded, or no longer standing.
# Outside a Codex tool shell nothing here runs. --ignore-gates does NOT cover
# it: that flag overrides declared gates, not a pending answer from the user.
# Called for every task a run archives: the named one (main) and a parent the
# child flow archives with its last child (archive_child), each before the
# run writes anything.
approval_guard() {
    local task_num="$1"
    [[ -n "${CODEX_THREAD_ID:-}" ]] || return 0
    local decision
    decision=$("$SCRIPT_DIR/aitask_gate.sh" approvals-settled "$task_num" 2>/dev/null) \
        || decision="${decision:-APPROVALS:blocked|approval state could not be read}"
    case "$decision" in
        APPROVALS:unguarded|APPROVALS:settled*) return 0 ;;
        *)
            echo "APPROVAL_PENDING:${decision#APPROVALS:blocked|}"
            echo "APPROVAL_BLOCKED: cannot archive while an approval question of t${task_num} is open or no longer stands - ask it again and act on the answer first"
            exit 2
            ;;
    esac
}

# --- The `landed` trigger (task relations D4/D9) ---
# Fires only for COMPLETED work whose archive commit succeeded: never for
# --dry-run or --no-commit, and per archived id, only for a file that
# archived_file_landed accepts (status Done, no archived_reason, no
# folded_into). The task a --superseded / --obsolete flag names therefore fires
# nothing, while a parent the child flow auto-archived in that run fires when
# its own decided reason is empty (t2254). The enqueue helper
# never writes to stdout, always exits 0 and does its work detached (the store
# read and the fan-out to the related pending tasks run there), so this can
# neither block nor fail the archive.
archived_file_for() {
    local id="$1"
    if [[ "$id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        ls "$ARCHIVED_DIR/t${BASH_REMATCH[1]}/t${id}_"*.md 2>/dev/null | head -1 || true
    else
        ls "$ARCHIVED_DIR/t${id}_"*.md 2>/dev/null | head -1 || true
    fi
}

fire_landed_triggers() {
    [[ "$DRY_RUN" == true || "$NO_COMMIT" == true ]] && return 0
    local id file
    for id in ${LANDED_IDS[@]+"${LANDED_IDS[@]}"}; do
        file=$(archived_file_for "$id")
        archived_file_landed "$file" || continue
        "$SCRIPT_DIR/aitask_relations_enqueue.sh" obsolescence landed "$id" >/dev/null 2>&1 || true
    done
    return 0
}

# --- Main ---
main() {
    parse_args "$@"

    # Guarded here rather than deeper: verification_gate_and_carryover below can
    # already create AND commit a carry-over task, so it is the first task-data
    # mutation reachable from this entry (t1725_2).
    #
    # --dry-run is exempt on purpose: archive_metadata_update and archive_move
    # both short-circuit under it, making the whole invocation read-only, and a
    # reporting mode must keep working while the worktree is wedged.
    [[ "$DRY_RUN" == true ]] || assert_task_data_writable

    verification_gate_and_carryover "$TASK_NUM"
    gate_guard "$TASK_NUM"
    approval_guard "$TASK_NUM"

    if [[ "$TASK_NUM" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"
        archive_child "$parent_num" "$child_num"
    else
        archive_parent "$TASK_NUM"
    fi

    fire_landed_triggers || true
}

main "$@"
