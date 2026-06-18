#!/usr/bin/env bash
# task_utils.sh - Shared task/plan resolution and extraction utilities
# Source this file from aitask scripts; do not execute directly.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_TASK_UTILS_LOADED:-}" ]] && return 0
_AIT_TASK_UTILS_LOADED=1

# Ensure terminal_compat.sh is loaded (for die/warn helpers)
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
# shellcheck source=archive_utils.sh
source "${SCRIPT_DIR}/lib/archive_utils.sh"
# shellcheck source=yaml_utils.sh
source "${SCRIPT_DIR}/lib/yaml_utils.sh"
# shellcheck source=python_resolve.sh
source "${SCRIPT_DIR}/lib/python_resolve.sh"

# --- Default directory variables (override before sourcing if needed) ---
TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"
PLAN_DIR="${PLAN_DIR:-aiplans}"
ARCHIVED_PLAN_DIR="${ARCHIVED_PLAN_DIR:-aiplans/archived}"

# --- Task Data Worktree Detection ---
# Detects if task data lives in a separate worktree (.aitask-data/)
# or on the current branch (legacy mode). All scripts use task_git()
# for git operations on task/plan files.

_AIT_DATA_WORKTREE=""

# Detect whether task data lives in a separate worktree
# Sets _AIT_DATA_WORKTREE to ".aitask-data" (branch mode) or "." (legacy mode)
_ait_detect_data_worktree() {
    if [[ -n "$_AIT_DATA_WORKTREE" ]]; then return; fi
    if [[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]; then
        _AIT_DATA_WORKTREE=".aitask-data"
    else
        _AIT_DATA_WORKTREE="."
    fi
}

# Resolve the data worktree's git-dir. Empty when in legacy mode or when the
# expected worktree git-dir is missing.
_ait_data_gitdir() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
        printf ''
        return
    fi
    local gd=".git/worktrees/-aitask-data"
    [[ -d "$gd" ]] && printf '%s' "$gd"
}

# Read-only git subcommands — the guard treats them as safe.
_ait_git_subcmd_is_readonly() {
    case "${1:-}" in
        status|log|show|diff|rev-parse|ls-files|blame|grep|reflog) return 0 ;;
        branch)
            local a
            for a in "${@:2}"; do
                case "$a" in -d|-D|-m|-M|--delete|--move) return 1 ;; esac
            done
            return 0 ;;
        tag)
            local a
            for a in "${@:2}"; do
                case "$a" in -l|--list) return 0 ;; esac
            done
            return 1 ;;
        stash)
            [[ "${2:-}" == "list" || "${2:-}" == "show" ]] && return 0 || return 1 ;;
    esac
    return 1
}

# Recovery subcommands — must be allowed through even when the worktree is wedged.
_ait_git_subcmd_is_recovery() {
    case "${1:-}" in
        rebase|merge|cherry-pick|revert)
            local a
            for a in "${@:2}"; do
                case "$a" in --abort|--continue|--skip|--edit-todo|--quit) return 0 ;; esac
            done
            return 1 ;;
        bisect)
            [[ "${2:-}" == "reset" ]] && return 0 || return 1 ;;
    esac
    return 1
}

# Pre-flight: reject mutating ops while the data worktree is mid-rebase/merge/etc.
# No-op in legacy mode and when the data worktree git-dir is missing.
assert_data_worktree_clean() {
    [[ "${AIT_GIT_SKIP_STATE_CHECK:-}" == "1" ]] && return 0
    _ait_git_subcmd_is_recovery "$@" && return 0
    _ait_git_subcmd_is_readonly "$@" && return 0

    local gitdir
    gitdir="$(_ait_data_gitdir)"
    [[ -z "$gitdir" ]] && return 0

    local state hit=""
    for state in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
        if [[ -e "$gitdir/$state" ]]; then hit="$state"; break; fi
    done
    [[ -z "$hit" ]] && return 0

    die "$(cat <<EOF
Data worktree (.aitask-data) is stuck mid-${hit}.
Recover with one of:
  ./ait git rebase --abort        (discard the in-progress rebase)
  ./ait git rebase --continue     (resume if you were editing)
  ./ait git merge --abort
  ./ait git cherry-pick --abort
  ./ait git revert --abort
  ./ait git bisect reset
Set AIT_GIT_SKIP_STATE_CHECK=1 to bypass this check.
Run './ait git-health' for a full diagnostic.
EOF
)"
}

# Print human-readable health of the .aitask-data worktree. Informational only.
task_git_health() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
        info "Mode: legacy (no separate .aitask-data worktree) — nothing to check."
        return 0
    fi

    local gitdir branch head_ref state
    local hits=()
    gitdir="$(_ait_data_gitdir)"
    branch="$(git -C .aitask-data rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    head_ref="$(git -C .aitask-data rev-parse --short HEAD 2>/dev/null || echo '?')"

    info "Mode: branch (.aitask-data worktree present)"
    info "Worktree path: .aitask-data"
    info "Git-dir: ${gitdir:-<missing>}"
    info "Branch (rev-parse --abbrev-ref HEAD): $branch"
    info "HEAD commit: $head_ref"

    if [[ -z "$gitdir" || ! -d "$gitdir" ]]; then
        warn "Git-dir not found at expected path — worktree may be misregistered."
        return 0
    fi

    for state in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
        [[ -e "$gitdir/$state" ]] && hits+=("$state")
    done

    if [[ "$branch" == "HEAD" ]]; then
        warn "Detached HEAD."
    fi
    if (( ${#hits[@]} > 0 )); then
        warn "In-progress operations: ${hits[*]}"
        info "Recover with: ./ait git <rebase|merge|cherry-pick|revert> --abort  (or --continue)"
    elif [[ "$branch" != "HEAD" ]]; then
        success "Clean — no in-progress rebase/merge/cherry-pick/revert/bisect."
    fi
}

# Run git commands targeting the task data worktree
# In branch mode: git -C .aitask-data <args>
# In legacy mode: git <args>
task_git() {
    _ait_detect_data_worktree
    assert_data_worktree_clean "$@"
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" "$@"
    else
        git "$@"
    fi
}

# Sync task data from remote (independent of code sync in branch mode)
# Uses --rebase instead of --ff-only so sync succeeds even when local has
# unpushed commits (e.g. from a previous failed push cycle).
task_sync() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --rebase --quiet 2>/dev/null || true
    else
        git pull --rebase --quiet 2>/dev/null || true
    fi
}

# Push task data to remote with automatic pull-rebase on conflict.
# Retries up to 3 times. Failures are non-fatal (best-effort push).
task_push() {
    assert_data_worktree_clean push
    local max_attempts=3
    local attempt
    for (( attempt=1; attempt<=max_attempts; attempt++ )); do
        if _task_push_once 2>/dev/null; then
            return 0
        fi
        # Pull with rebase to incorporate remote changes, then retry
        if [[ $attempt -lt $max_attempts ]]; then
            _task_pull_rebase 2>/dev/null || true
        fi
    done
    # All attempts exhausted — best-effort, don't fail the workflow
    return 0
}

# Internal: single push attempt
_task_push_once() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" push --quiet
    else
        git push --quiet
    fi
}

# Internal: pull with rebase to catch up with remote
_task_pull_rebase() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" pull --rebase --quiet
    else
        git pull --rebase --quiet
    fi
}

# --- YAML List Parsing ---

# Parse a YAML inline list value to comma-separated string.
# Strips brackets, quotes, and spaces: "['38', t85_2]" -> "38,t85_2"
parse_yaml_list() {
    local value="$1"
    echo "$value" | tr -d "[]'\"" | tr -d ' '
}

# --- YAML List Formatting ---

# Format a comma-separated string as a YAML inline list.
# "1,3,5" -> "[1, 3, 5]"; empty input -> "[]".
# Inverse of parse_yaml_list.
format_yaml_list() {
    local input="$1"
    if [[ -z "$input" ]]; then
        echo "[]"
    else
        echo "[$(echo "$input" | sed 's/,/, /g')]"
    fi
}

# join_yaml_flow_lists and read_yaml_field are defined in yaml_utils.sh
# (sourced above) — a shared lib so agentcrew_utils.sh can reuse the same
# canonical readers without a copy of its own.

# --- Task level enum (single source of truth) ---

# Canonical task level enum (high/medium/low), shared by priority, effort, and
# the two risk fields (risk_code_health, risk_goal_achievement). Single bash
# source of truth — Python mirror: .aitask-scripts/lib/task_levels.py.
TASK_LEVELS="high medium low"   # canonical, severity-descending

# Return 0 if $1 is a valid task level, non-zero otherwise (empty => invalid).
is_valid_task_level() {
    local val="$1" level
    for level in $TASK_LEVELS; do
        [[ "$val" == "$level" ]] && return 0
    done
    return 1
}

# Emit the levels one-per-line for interactive pickers (e.g. fzf).
task_levels_lines()     { printf '%s\n' high medium low; }   # canonical (desc)
task_levels_lines_asc() { printf '%s\n' low medium high; }   # ascending

# --- Helper: read status of a folded task ---
read_task_status() {
    local file_path="$1"
    read_yaml_field "$file_path" "status"
}

# --- Cross-repo dependency field readers ---

# Read the xdeps list as a normalized comma-separated string (e.g. "1,t42_3").
# Empty when the field is absent.
read_xdeps() {
    local file_path="$1"
    local raw
    raw=$(read_yaml_field "$file_path" "xdeps")
    [[ -z "$raw" ]] && return 0
    local parsed
    parsed=$(parse_yaml_list "$raw")
    normalize_task_ids "$parsed"
}

# Read the xdeprepo scalar (cross-repo project name). Empty when absent.
read_xdeprepo() {
    local file_path="$1"
    read_yaml_field "$file_path" "xdeprepo"
}

# Validate the cross-repo dep pair.
#
# As of t832_10:
#   - Neither set                 → no-op (most tasks).
#   - Both set                    → BATCH_XDEPREPO must resolve cleanly;
#                                   every id in BATCH_XDEPS must exist in
#                                   the cross-repo project.
#   - BATCH_XDEPREPO alone        → OK (intent-only; the new task declares
#                                   cross-repo coordination without any
#                                   concrete deps yet). The xdeprepo
#                                   registry resolution still runs.
#   - BATCH_XDEPS alone           → die (xdeps cannot exist without a
#                                   project context to resolve them in).
#
# Reads globals: BATCH_XDEPS, BATCH_XDEPREPO, SCRIPT_DIR. Callers
# (create.sh, update.sh) populate these before invoking.
validate_xdeps_pair() {
    if [[ -z "${BATCH_XDEPS:-}" && -z "${BATCH_XDEPREPO:-}" ]]; then
        return 0
    fi
    if [[ -n "${BATCH_XDEPS:-}" && -z "${BATCH_XDEPREPO:-}" ]]; then
        die "--xdeps requires --xdeprepo (xdeps without a project context cannot be resolved)."
    fi

    local resolved
    resolved=$("$SCRIPT_DIR/aitask_project_resolve.sh" "$BATCH_XDEPREPO" 2>/dev/null || true)
    case "$resolved" in
        RESOLVED:*) ;;
        STALE:*)
            die "Project '$BATCH_XDEPREPO' is registered but its path is stale: ${resolved#STALE:}"
            ;;
        NOT_FOUND:*|"")
            die "Project '$BATCH_XDEPREPO' is not registered. Run \`cd /path/to/$BATCH_XDEPREPO && ait projects add\`."
            ;;
        *)
            die "Project resolver returned unexpected output for '$BATCH_XDEPREPO': $resolved"
            ;;
    esac

    local IFS=','
    local id
    for id in $BATCH_XDEPS; do
        id="${id#t}"
        [[ -z "$id" ]] && continue
        local result
        result=$("$SCRIPT_DIR/aitask_query_files.sh" --project "$BATCH_XDEPREPO" task-status "$id" 2>/dev/null || true)
        case "$result" in
            STATUS:NOT_FOUND|"")
                die "--xdeps id $id not found in cross-repo project '$BATCH_XDEPREPO'."
                ;;
            STATUS:*) ;;
            *)
                die "Unexpected task-status output for xdeps id $id in '$BATCH_XDEPREPO': $result"
                ;;
        esac
    done
}

# --- Anchor field helper ---

# Normalize and validate an anchor task id (intra-repo, archived-inclusive).
#
# Accepts a raw id with an optional single leading "t" (e.g. t42, 42, t42_1,
# 42_1), strips it, asserts the id shape (N or N_M), and verifies the task
# exists (any status, including Done/archived, is valid — anchoring to a
# completed topic root is allowed). Echoes the BARE id so callers store/resolve
# the canonical form (so `--anchor t42` and `--anchor 42` are identical, and the
# stored `anchor:` value equals a root's bare own-id group key).
#
# Dies on a malformed id or a non-existent target. Mirrors the local
# strip_prefix in aitask_query_files.sh, but t-only and shared.
#
# Reads global: SCRIPT_DIR.
normalize_anchor_id() {
    local raw="$1"
    local id="${raw#t}"
    if [[ ! "$id" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
        die "anchor target '$raw' is not a valid task id (expected N or N_M)."
    fi
    local status
    status=$("$SCRIPT_DIR/aitask_query_files.sh" task-status "$id" 2>/dev/null || true)
    case "$status" in
        STATUS:NOT_FOUND|"")
            die "anchor target '$id' not found."
            ;;
        STATUS:*)
            echo "$id"
            ;;
        *)
            die "anchor target '$id': unexpected status result '$status'."
            ;;
    esac
}

# Normalize child task IDs: ensure entries with underscore have 't' prefix.
# e.g. "85_2,t85_3,16" -> "t85_2,t85_3,16"
normalize_task_ids() {
    local input="$1"
    [[ -z "$input" ]] && return
    local result=""
    IFS=',' read -ra ids <<< "$input"
    for id in "${ids[@]}"; do
        if [[ "$id" =~ ^[0-9]+_[0-9]+$ ]]; then
            id="t${id}"
        fi
        [[ -n "$result" ]] && result="${result},"
        result="${result}${id}"
    done
    echo "$result"
}

# --- Per-user Config ---

# Read the current user's email from the local (gitignored) userconfig.yaml
# Output: email string, or empty if file missing / field not found
get_user_email() {
    local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
    if [[ -f "$config" ]]; then
        grep '^email:' "$config" | sed 's/^email: *//'
    fi
}

# Read the last-used labels list from userconfig.yaml (per-user).
# Output: CSV string (e.g. "ui,backend"), empty when field or file is absent.
# Delegates to the yaml-aware userconfig_persist.py so both flow- and
# block-style values are read correctly; falls back to a flow-only grep read
# when no Python interpreter is available (read-only, never corrupts).
get_last_used_labels() {
    local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
    [[ -f "$config" ]] || return 0

    local py out
    py="$(resolve_python 2>/dev/null || true)"
    if [[ -n "$py" ]]; then
        if out="$(TASK_DIR="${TASK_DIR:-aitasks}" "$py" \
            "${SCRIPT_DIR}/lib/userconfig_persist.py" get-labels 2>/dev/null)"; then
            printf '%s' "$out"
            return 0
        fi
    fi

    # Fallback (no Python): flow-style single-line read only.
    local line
    line=$(grep '^last_used_labels:' "$config" 2>/dev/null) || true
    [[ -z "$line" ]] && return 0
    echo "$line" | sed -e 's/^last_used_labels:[[:space:]]*//' \
                       -e 's/^\[//' \
                       -e 's/\][[:space:]]*$//' \
                       -e 's/[[:space:]]//g'
}

# Write the last-used labels list to userconfig.yaml (per-user).
# Input: CSV string (e.g. "ui,backend") — empty is valid and writes "[]".
# Delegates to the yaml-aware userconfig_persist.py, which round-trips the whole
# file safely so it can never orphan a prior block-style value into invalid
# YAML. Falls back to a block-safe bash writer when no Python is available.
set_last_used_labels() {
    local csv="${1:-}"
    local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
    mkdir -p "$(dirname "$config")"

    local py
    py="$(resolve_python 2>/dev/null || true)"
    if [[ -n "$py" ]]; then
        if TASK_DIR="${TASK_DIR:-aitasks}" "$py" \
            "${SCRIPT_DIR}/lib/userconfig_persist.py" set-labels "$csv" 2>/dev/null; then
            return 0
        fi
    fi

    _set_last_used_labels_fallback "$csv" "$config"
}

# Block-safe bash writer, used only when no Python interpreter is available.
# Writes flow style ([a, b]) and, when replacing an existing value, also removes
# any block-style continuation lines ("- item") that followed the header — so a
# value previously written in block style cannot orphan list items into invalid
# YAML. Deletion stops at the first non-list line, so a following block such as
# "shortcuts:" is never touched.
_set_last_used_labels_fallback() {
    local csv="$1" config="$2"
    local yaml_list
    if [[ -z "$csv" ]]; then
        yaml_list="[]"
    else
        yaml_list="[$(echo "$csv" | sed 's/,/, /g')]"
    fi

    if [[ ! -f "$config" ]]; then
        {
            echo "# Local user configuration (gitignored, not shared)"
            echo "last_used_labels: $yaml_list"
        } > "$config"
        return 0
    fi

    if grep -q '^last_used_labels:' "$config" 2>/dev/null; then
        local tmp
        tmp="$(mktemp)"
        awk -v repl="last_used_labels: ${yaml_list}" '
            drop && /^[[:space:]]*-[[:space:]]/ { next }
            drop { drop=0 }
            /^last_used_labels:/ { print repl; drop=1; next }
            { print }
        ' "$config" > "$tmp" && mv "$tmp" "$config"
    else
        echo "last_used_labels: $yaml_list" >> "$config"
    fi
}

# --- Platform Detection ---

# Detect git remote platform from origin URL
# Output: "github", "gitlab", "bitbucket", or "" (unknown)
detect_platform() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$remote_url" == *"gitlab"* ]]; then
        echo "gitlab"
    elif [[ "$remote_url" == *"bitbucket"* ]]; then
        echo "bitbucket"
    elif [[ "$remote_url" == *"github"* ]]; then
        echo "github"
    else
        echo ""
    fi
}

# Detect platform from an issue/web URL
# Input: URL string
# Output: "github", "gitlab", "bitbucket", or "" (unknown)
detect_platform_from_url() {
    local url="$1"
    if [[ "$url" == *"gitlab"* ]]; then
        echo "gitlab"
    elif [[ "$url" == *"bitbucket"* ]]; then
        echo "bitbucket"
    elif [[ "$url" == *"github"* ]]; then
        echo "github"
    else
        echo ""
    fi
}

# --- Task and Plan Resolution ---
# Archive search/extract primitives provided by archive_utils.sh:
#   _search_archive(), _extract_from_archive(), _find_archive_for_task()
# Temp directory cleanup handled by _AIT_ARCHIVE_TMPDIR in archive_utils.sh

# Resolve task number to file path, checking both active and archived directories
# Input: task_id (e.g., "53" or "53_6")
# Output: file path
resolve_task_file() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Check active directory first
        files=$(ls "$TASK_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Check archived directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$parent_num" "$ARCHIVED_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_DIR/old.tar.zst" "$ARCHIVED_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for t${parent_num}_${child_num} (checked active, archived, and numbered archives)"
        fi
    else
        # Parent task
        files=$(ls "$TASK_DIR"/t${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$task_id" "$ARCHIVED_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)t${task_id}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_DIR/old.tar.zst" "$ARCHIVED_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)t${task_id}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for task number $task_id (checked active, archived, and numbered archives)"
        fi
    fi

    local count
    count=$(echo "$files" | wc -l)

    if [[ "$count" -gt 1 ]]; then
        die "Multiple task files found for task $task_id"
    fi

    echo "$files"
}

# Resolve plan file from task number, checking both active and archived
# Plan naming convention:
#   Parent task t53_name.md -> plan p53_name.md
#   Child task t53/t53_1_name.md -> plan p53/p53_1_name.md
# Input: task_id (e.g., "53" or "53_6")
# Output: file path or empty string if not found
resolve_plan_file() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Check active plan directory
        files=$(ls "$PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Check archived plan directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$parent_num" "$ARCHIVED_PLAN_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_PLAN_DIR/old.tar.zst" "$ARCHIVED_PLAN_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    else
        # Parent plan
        files=$(ls "$PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$task_id" "$ARCHIVED_PLAN_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)p${task_id}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_PLAN_DIR/old.tar.zst" "$ARCHIVED_PLAN_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)p${task_id}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    fi

    if [[ -z "$files" ]]; then
        echo ""
        return
    fi

    local count
    count=$(echo "$files" | wc -l)
    if [[ "$count" -gt 1 ]]; then
        echo "$files" | head -1
    else
        echo "$files"
    fi
}

# Extract the issue URL from a task file's YAML frontmatter
# Input: task file path
# Output: issue URL or empty string
extract_issue_url() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^issue:[[:space:]]*(.*) ]]; then
            local url="${BASH_REMATCH[1]}"
            url=$(echo "$url" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$url"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract the pull request URL from a task file's YAML frontmatter
# Input: task file path
# Output: pull request URL or empty string
extract_pr_url() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^pull_request:[[:space:]]*(.*) ]]; then
            local url="${BASH_REMATCH[1]}"
            url=$(echo "$url" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$url"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract file_references entries from a task file's YAML frontmatter
# Input: task file path
# Output: one entry per line (newline-separated), empty if missing/empty
# Each entry is returned verbatim: "path", "path:N", "path:N-M",
# or compact multi-range "path:N-M^N-M^...".
get_file_references() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break
            else in_yaml=true; continue; fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^file_references:[[:space:]]*(.*) ]]; then
            local raw="${BASH_REMATCH[1]}"
            raw="${raw#\[}" ; raw="${raw%\]}"
            if [[ -z "$raw" ]]; then return; fi
            while IFS=',' read -ra items; do
                for item in "${items[@]}"; do
                    item=$(echo "$item" | sed 's/^[[:space:]"]*//;s/[[:space:]"]*$//')
                    [[ -n "$item" ]] && echo "$item"
                done
            done <<< "$raw"
            return
        fi
    done < "$file_path"
}

# Validate a single file_reference entry string.
# Accepted: "path" | "path:N" | "path:N-M" | "path:N-M^N-M^..."
# Line numbers are 1-indexed. Die with a clear error on malformed input.
validate_file_ref() {
    local ref="$1"
    if [[ -z "$ref" ]]; then
        die "Empty file reference"
    fi
    if [[ ! "$ref" =~ ^[^:]+(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)?$ ]]; then
        die "Invalid file reference: '$ref' (expected PATH[:N[-M][^N[-M]]...])"
    fi
}

# union_file_references <primary_file> [<folded_file> ...]
# Reads file_references from primary first, then each folded file in
# argument order. Dedupes by first-occurrence exact-string match.
# Prints the unioned list as CSV on stdout (empty if nothing to emit).
union_file_references() {
    local primary_file="$1"
    shift
    local -a merged=()
    declare -A seen=()
    local entry f

    if [[ -n "$primary_file" && -f "$primary_file" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            if [[ -z "${seen[$entry]:-}" ]]; then
                seen[$entry]=1
                merged+=("$entry")
            fi
        done < <(get_file_references "$primary_file")
    fi

    for f in "$@"; do
        [[ -z "$f" || ! -f "$f" ]] && continue
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            if [[ -z "${seen[$entry]:-}" ]]; then
                seen[$entry]=1
                merged+=("$entry")
            fi
        done < <(get_file_references "$f")
    done

    if [[ ${#merged[@]} -eq 0 ]]; then
        return 0
    fi
    local IFS=','
    echo "${merged[*]}"
}

# Extract related issue URLs from a task file's YAML frontmatter
# Input: task file path
# Output: one URL per line (newline-separated), empty if missing/empty
extract_related_issues() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break
            else in_yaml=true; continue; fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^related_issues:[[:space:]]*(.*) ]]; then
            local raw="${BASH_REMATCH[1]}"
            # Strip brackets, split on comma, trim quotes/spaces
            raw="${raw#\[}" ; raw="${raw%\]}"
            if [[ -z "$raw" ]]; then return; fi
            while IFS=',' read -ra items; do
                for item in "${items[@]}"; do
                    item=$(echo "$item" | sed 's/^[[:space:]"]*//;s/[[:space:]"]*$//')
                    [[ -n "$item" ]] && echo "$item"
                done
            done <<< "$raw"
            return
        fi
    done < "$file_path"
}

# Extract the contributor username from a task file's YAML frontmatter
# Input: task file path
# Output: contributor username or empty string
extract_contributor() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^contributor:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract the contributor email from a task file's YAML frontmatter
# Input: task file path
# Output: contributor email or empty string
extract_contributor_email() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^contributor_email:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract the implemented_with agent string from a task file's YAML frontmatter
# Input: task file path
# Output: implemented_with value or empty string
extract_implemented_with() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^implemented_with:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract "Final Implementation Notes" section from a plan file
# Input: plan file path
# Output: the section content
extract_final_implementation_notes() {
    local plan_path="$1"
    local in_section=false
    local content=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^##[[:space:]]+Final[[:space:]]+Implementation[[:space:]]+Notes ]]; then
            in_section=true
            continue
        fi

        if [[ "$in_section" == true ]]; then
            # Stop at next level-2 heading
            if [[ "$line" =~ ^##[[:space:]] ]]; then
                break
            fi
            if [[ -n "$content" ]]; then
                content="${content}"$'\n'"${line}"
            else
                content="$line"
            fi
        fi
    done < "$plan_path"

    # Trim leading/trailing blank lines (awk for portability — BSD sed can't handle grouped multi-line commands)
    echo "$content" | sed '/./,$!d' | awk '{lines[NR]=$0} /[^[:space:]]/{last=NR} END{for(i=1;i<=last;i++) print lines[i]}'
}

# --- Contribute Metadata Parsing ---

# Parse aitask-contribute metadata from issue body HTML comment
# Sets global: CONTRIBUTE_CONTRIBUTOR, CONTRIBUTE_EMAIL, CONTRIBUTE_FINGERPRINT_VERSION,
#              CONTRIBUTE_AREAS, CONTRIBUTE_FILE_PATHS, CONTRIBUTE_FILE_DIRS,
#              CONTRIBUTE_CHANGE_TYPE, CONTRIBUTE_AUTO_LABELS
parse_contribute_metadata() {
    local body="$1"
    CONTRIBUTE_CONTRIBUTOR=""
    CONTRIBUTE_EMAIL=""
    CONTRIBUTE_FINGERPRINT_VERSION=""
    CONTRIBUTE_AREAS=""
    CONTRIBUTE_FILE_PATHS=""
    CONTRIBUTE_FILE_DIRS=""
    CONTRIBUTE_CHANGE_TYPE=""
    CONTRIBUTE_AUTO_LABELS=""

    local in_block=false
    while IFS= read -r line; do
        if [[ "$line" == *"<!-- aitask-contribute-metadata"* ]]; then
            in_block=true
            continue
        fi
        if [[ "$in_block" == true ]]; then
            if [[ "$line" == *"-->"* ]]; then
                break
            fi
            case "$line" in
                *contributor_email:*)
                    CONTRIBUTE_EMAIL=$(echo "$line" | sed 's/.*contributor_email:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *contributor:*)
                    CONTRIBUTE_CONTRIBUTOR=$(echo "$line" | sed 's/.*contributor:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *fingerprint_version:*)
                    CONTRIBUTE_FINGERPRINT_VERSION=$(echo "$line" | sed 's/.*fingerprint_version:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *file_paths:*)
                    CONTRIBUTE_FILE_PATHS=$(echo "$line" | sed 's/.*file_paths:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *file_dirs:*)
                    CONTRIBUTE_FILE_DIRS=$(echo "$line" | sed 's/.*file_dirs:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *change_type:*)
                    CONTRIBUTE_CHANGE_TYPE=$(echo "$line" | sed 's/.*change_type:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *auto_labels:*)
                    CONTRIBUTE_AUTO_LABELS=$(echo "$line" | sed 's/.*auto_labels:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *areas:*)
                    CONTRIBUTE_AREAS=$(echo "$line" | sed 's/.*areas:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
            esac
        fi
    done <<< "$body"
}
