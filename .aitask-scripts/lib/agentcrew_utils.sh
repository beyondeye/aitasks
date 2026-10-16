#!/usr/bin/env bash
# agentcrew_utils.sh - Shared utility functions for the AgentCrew infrastructure.
# Provides constants, validation, crew resolution, YAML helpers, and DAG cycle detection.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_AGENTCREW_UTILS_LOADED:-}" ]] && return 0
_AIT_AGENTCREW_UTILS_LOADED=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Captured separately: callers reassign SCRIPT_DIR after sourcing.
_AIT_AGENTCREW_LIB_DIR="$SCRIPT_DIR"
# shellcheck source=terminal_compat.sh
source "$SCRIPT_DIR/terminal_compat.sh"
# shellcheck source=yaml_utils.sh
source "$SCRIPT_DIR/yaml_utils.sh"

# --- Constants ---
AGENTCREW_BRANCH_PREFIX="crew-"
AGENTCREW_DIR=".aitask-crews"

# --- Status constants (used by downstream scripts: crew_status, crew_runner) ---
# shellcheck disable=SC2034
{
AGENT_STATUS_WAITING="Waiting"
AGENT_STATUS_RUNNING="Running"
AGENT_STATUS_COMPLETED="Completed"
AGENT_STATUS_ABORTED="Aborted"
AGENT_STATUS_READY="Ready"
AGENT_STATUS_ERROR="Error"
AGENT_STATUS_PAUSED="Paused"

CREW_STATUS_INITIALIZING="Initializing"
CREW_STATUS_RUNNING="Running"
CREW_STATUS_COMPLETED="Completed"
CREW_STATUS_KILLING="Killing"
CREW_STATUS_PAUSED="Paused"
CREW_STATUS_ERROR="Error"
CREW_STATUS_ABORTED="Aborted"
}

# crew_branch_name <crew_id>
# Returns the git branch name for an agentcrew.
crew_branch_name() {
    local crew_id="$1"
    echo "${AGENTCREW_BRANCH_PREFIX}${crew_id}"
}

# crew_is_terminal <worktree>
# True iff the crew has finished, derived from member agent status files (so a
# stale persisted _crew_status.yaml never blocks cleanup). With >=1 member: every
# member must be in a terminal agent state. With NO members: fall back to the
# persisted crew status. Mirrors the Python all-terminal rule in
# agentcrew_utils.compute_crew_status / effective_crew_rollup (no-members branch)
# — keep the terminal set {Completed, Aborted, Error} in sync across the two.
crew_is_terminal() {
    local wt="$1" sf st found=false
    for sf in "$wt"/*_status.yaml; do
        [[ -f "$sf" ]] || continue
        [[ "$(basename "$sf")" == _* ]] && continue   # skip _crew_status.yaml etc.
        found=true
        st="$(read_yaml_field "$sf" "status")"
        case "$st" in
            "$AGENT_STATUS_COMPLETED"|"$AGENT_STATUS_ABORTED"|"$AGENT_STATUS_ERROR") ;;
            *) return 1 ;;
        esac
    done
    if $found; then
        return 0
    fi
    # No member agents — fall back to the persisted crew status (preserves the
    # existing empty-crew cleanup behaviour, e.g. a Completed crew with no agents).
    st="$(read_yaml_field "$wt/_crew_status.yaml" "status" 2>/dev/null || true)"
    case "$st" in
        "$CREW_STATUS_COMPLETED"|"$AGENT_STATUS_ERROR"|"$AGENT_STATUS_ABORTED") return 0 ;;
        *) return 1 ;;
    esac
}

# agentcrew_worktree_path <crew_id>
# Returns the worktree filesystem path for an agentcrew.
agentcrew_worktree_path() {
    local crew_id="$1"
    echo "${AGENTCREW_DIR}/crew-${crew_id}"
}

# --- Bounded crew git network operations (t2024) ---
# Every crew fetch/push to origin runs through _crew_git_bounded, so an origin
# that is routable but never answers (a TCP connect waiting out the kernel's SYN
# retries) cannot stall crew init, agent registration or a launch-mode change.
# The bound is AIT_CREW_GIT_TIMEOUT seconds; agentcrew_utils.py's
# crew_git_timeout() reads the same knob for the runner and `ait crew status`.
_AIT_CREW_GIT_TIMEOUT_DEFAULT=10

# crew_git_timeout — print the per-operation bound in whole seconds. Unset,
# empty, zero, negative, non-numeric or absurdly long values fall back to the
# default. `10#` keeps a leading zero from being read as octal.
crew_git_timeout() {
    local t="${AIT_CREW_GIT_TIMEOUT:-}"
    if [[ "$t" =~ ^[0-9]{1,6}$ ]] && (( 10#$t > 0 )); then
        printf '%s\n' "$(( 10#$t ))"
    else
        printf '%s\n' "$_AIT_CREW_GIT_TIMEOUT_DEFAULT"
    fi
}

# _crew_git_bounded <worktree> <output-file> <git-args...>
# Run `git -C <worktree> <git-args>` through lib/bounded_run.py with stdout and
# stderr in <output-file>. Returns git's status, or 124 when the bound expired
# and the operation's whole process tree was killed. bounded_run.py runs git in
# a new session with noninteractive_env(): no controlling terminal, no askpass
# program and no display, so ssh, plink or a configured transport cannot prompt
# (a `set -m` job would keep the terminal). Only network operations go through
# here: killing a local step that writes the worktree (a commit, a rebase)
# could leave it half-done.
_crew_git_bounded() {
    local wt="$1" out="$2"
    shift 2
    "${_AIT_RESOLVED_PYTHON:-python3}" "$_AIT_AGENTCREW_LIB_DIR/bounded_run.py" \
        --timeout "$(crew_git_timeout)" --noninteractive -- \
        git -C "$wt" "$@" >"$out" 2>&1
}

# crew_push <worktree>
# Publish the crew branch checked out in <worktree> to origin (best-effort).
# Always `push -u origin HEAD` (t2016): crew init creates the branch with no
# upstream, so a bare `git push` dies with "has no upstream branch" unless the
# user sets push.autoSetupRemote; -u gives it one on the first push that
# succeeds, so an offline init heals later. Naming the destination also keeps
# a push.default=matching from publishing the repository's other branches.
# A push that timed out leaves the branch exactly as a failed one does: git
# sets the upstream only after a push succeeds (or finds the remote already up
# to date), so the next successful push sets it.
# No origin remote -> nothing to publish to: returns 0 silently. On failure
# warns with git's own stderr and returns 1. Never writes to stdout — callers
# print machine-parsed CREATED:/ADDED:/UPDATED: lines there, and git prints
# "branch ... set up to track ..." on stdout unless --quiet.
crew_push() {
    local wt="$1" out rc=0
    git -C "$wt" remote get-url origin >/dev/null 2>&1 || return 0
    if ! out="$(mktemp "${TMPDIR:-/tmp}/ait_crew_push_XXXXXX")"; then
        warn "git push of the crew branch to origin skipped: mktemp failed"
        return 1
    fi
    _crew_git_bounded "$wt" "$out" push --quiet -u origin HEAD || rc=$?
    if [[ "$rc" -eq 124 ]]; then
        warn "git push of the crew branch to origin timed out after $(crew_git_timeout)s (origin did not answer in time; AIT_CREW_GIT_TIMEOUT sets the bound)"
    elif [[ "$rc" -ne 0 ]]; then
        warn "git push of the crew branch to origin failed:"
        # Raw, not through warn(): warn() is echo -e and would interpret
        # backslashes in git's message.
        cat "$out" >&2
    fi
    rm -f "$out"
    [[ "$rc" -eq 0 ]] || return 1
}

# crew_pull_rebase <worktree>
# Rebase the crew branch onto its freshly fetched upstream (best-effort, quiet).
# What `git pull --rebase --no-autostash` did, split in two so that only the
# network step is bounded: the fetch of the tracked branch runs through
# _crew_git_bounded, and the local rebase runs only after a fetch that
# succeeded — exactly when `pull --rebase` would have rebased — and is never
# killed half-way. --no-autostash (t2008): the crew worktree holds other live
# agents' uncommitted heartbeats, status and command files, and a user's
# rebase.autoStash would stash and re-apply them; without it the rebase refuses
# on a dirty worktree, as under git's default. The upstream is read like
# agentcrew_utils.py's _upstream_source (t2018). Returns 1, quietly, when there
# is no upstream (the old pull died with "no tracking information"), or when
# the fetch or the rebase failed.
crew_pull_rebase() {
    local wt="$1" branch remote merge_ref out rc=0
    branch="$(git -C "$wt" symbolic-ref -q HEAD 2>/dev/null)" || return 1
    remote="$(git -C "$wt" for-each-ref --format='%(upstream:remotename)' "$branch" 2>/dev/null)" || return 1
    merge_ref="$(git -C "$wt" for-each-ref --format='%(upstream:remoteref)' "$branch" 2>/dev/null)" || return 1
    [[ -n "$remote" && -n "$merge_ref" ]] || return 1
    out="$(mktemp "${TMPDIR:-/tmp}/ait_crew_fetch_XXXXXX")" || return 1
    _crew_git_bounded "$wt" "$out" fetch --quiet -- "$remote" "$merge_ref" || rc=$?
    rm -f "$out"
    [[ "$rc" -eq 0 ]] || return 1
    git -C "$wt" rebase --no-autostash --quiet >/dev/null 2>&1
}

# validate_crew_id <id>
# Validates that a crew ID matches [a-z0-9_-]+. Dies on failure.
validate_crew_id() {
    local id="$1"
    if [[ -z "$id" ]]; then
        die "Crew ID cannot be empty"
    fi
    if ! [[ "$id" =~ ^[a-z0-9_-]+$ ]]; then
        die "Invalid crew ID '$id': must match [a-z0-9_-]+"
    fi
}

# validate_agent_name <name>
# Validates that an agent name matches [a-z0-9_]+. Dies on failure.
validate_agent_name() {
    local name="$1"
    if [[ -z "$name" ]]; then
        die "Agent name cannot be empty"
    fi
    if ! [[ "$name" =~ ^[a-z0-9_]+$ ]]; then
        die "Invalid agent name '$name': must match [a-z0-9_]+"
    fi
}

# resolve_crew <crew_id>
# Verifies the agentcrew worktree exists and echoes its path. Dies if not found.
resolve_crew() {
    local crew_id="$1"
    local wt_path
    wt_path="$(agentcrew_worktree_path "$crew_id")"
    if [[ ! -d "$wt_path" ]]; then
        die "Crew '$crew_id' not found: worktree '$wt_path' does not exist"
    fi
    echo "$wt_path"
}

# read_yaml_field and read_yaml_list are defined in yaml_utils.sh (sourced
# above). They were once a second, independent copy here, colliding with
# task_utils.sh's read_yaml_field when both libs were sourced — now canonical
# in one shared place (t815).

# write_yaml_file <file> <content>
# Writes YAML content to a file via heredoc (content passed as string).
write_yaml_file() {
    local file="$1"
    local content="$2"
    printf '%s\n' "$content" > "$file"
}

# resolve_template_includes <base_dir> [base_dir2 ...]
# Reads template content from stdin, writes resolved content to stdout.
# Resolves <!-- include: filename --> directives by searching each base_dir
# in order; the first existing match wins. One-level only (included files
# are not scanned for further includes). Missing includes emit a warning
# and preserve the directive line as-is.
resolve_template_includes() {
    local base_dirs=("$@")
    if [[ ${#base_dirs[@]} -eq 0 ]]; then
        die "resolve_template_includes: requires at least one base_dir"
    fi
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ \<\!--[[:space:]]+include:[[:space:]]+([^[:space:]]+)[[:space:]]+--\> ]]; then
            local inc_name="${BASH_REMATCH[1]}"
            local found=""
            local d
            for d in "${base_dirs[@]}"; do
                if [[ -f "$d/$inc_name" ]]; then
                    found="$d/$inc_name"
                    break
                fi
            done
            if [[ -n "$found" ]]; then
                cat "$found"
            else
                warn "Template include not found in any base_dir: $inc_name"
                printf '%s\n' "$line"
            fi
        else
            printf '%s\n' "$line"
        fi
    done
}

# append_yaml_list_item <file> <field> <value>
# Appends a value to a YAML inline list field [a, b] -> [a, b, c].
# If the field has an empty list [], sets it to [value].
append_yaml_list_item() {
    local file="$1"
    local field="$2"
    local value="$3"

    local current
    current=$({ grep "^${field}:" "$file" 2>/dev/null || true; } | head -n 1)

    if [[ -z "$current" ]]; then
        # Field doesn't exist, append it
        echo "${field}: [${value}]" >> "$file"
        return 0
    fi

    local list_content
    list_content=$(echo "$current" | sed "s/^${field}:[[:space:]]*//" | tr -d "[]'\"" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')

    local new_line
    if [[ -z "$list_content" ]]; then
        new_line="${field}: [${value}]"
    else
        new_line="${field}: [${list_content}, ${value}]"
    fi

    # Replace the line in-place
    local tmpfile
    tmpfile=$(mktemp "${TMPDIR:-/tmp}/ait_yaml_XXXXXX")
    while IFS= read -r line; do
        if [[ "$line" == "${field}:"* ]]; then
            echo "$new_line"
        else
            echo "$line"
        fi
    done < "$file" > "$tmpfile"
    mv "$tmpfile" "$file"
}

# detect_circular_deps <worktree_path> [new_agent_name] [new_agent_deps_csv]
# DFS cycle detection across all *_status.yaml files in the worktree.
# If new_agent_name and new_agent_deps_csv are provided, includes them
# as a proposed (not yet created) agent for pre-validation.
# Returns 0 if no cycle, exits with die() if cycle found.
detect_circular_deps() {
    local wt_path="$1"
    local new_name="${2:-}"
    local new_deps_csv="${3:-}"

    # Build adjacency list: agent -> deps (space-separated)
    # Using associative array (bash 4+)
    declare -A adj
    declare -A all_agents

    # Read existing agents from status files (skip _crew_status.yaml)
    local status_file agent_name
    for status_file in "$wt_path"/*_status.yaml; do
        [[ -f "$status_file" ]] || continue
        # Skip crew-level status file
        [[ "$(basename "$status_file")" == "_crew_status.yaml" ]] && continue
        agent_name=$(read_yaml_field "$status_file" "agent_name")
        [[ -z "$agent_name" ]] && continue
        all_agents["$agent_name"]=1

        local deps_str
        deps_str=$(read_yaml_list "$status_file" "depends_on" | tr '\n' ' ')
        adj["$agent_name"]="${deps_str:-}"
    done

    # Add proposed new agent if provided
    if [[ -n "$new_name" ]]; then
        all_agents["$new_name"]=1
        if [[ -n "$new_deps_csv" ]]; then
            adj["$new_name"]=$(echo "$new_deps_csv" | tr ',' ' ')
        else
            adj["$new_name"]=""
        fi
    fi

    # DFS cycle detection
    # States: 0=unvisited, 1=in-progress, 2=done
    declare -A state
    local agent
    for agent in "${!all_agents[@]}"; do
        state["$agent"]=0
    done

    # Recursive DFS via stack (to avoid bash recursion limits)
    _dfs_check_cycle() {
        local start="$1"
        local -a stack=("$start")
        local -a path=()
        local -A on_path

        while [[ ${#stack[@]} -gt 0 ]]; do
            local current="${stack[-1]}"
            unset 'stack[-1]'
            stack=("${stack[@]}")

            if [[ "${state[$current]:-0}" -eq 2 ]]; then
                continue
            fi

            if [[ "${on_path[$current]:-0}" -eq 1 ]]; then
                # Backtrack: mark done and remove from path
                state["$current"]=2
                on_path["$current"]=0
                if [[ ${#path[@]} -gt 0 ]]; then
                    unset 'path[-1]'
                    path=("${path[@]}")
                fi
                continue
            fi

            state["$current"]=1
            on_path["$current"]=1
            path+=("$current")

            # Push backtrack marker
            stack+=("$current")

            # Push dependencies
            local dep
            for dep in ${adj[$current]:-}; do
                if [[ "${on_path[$dep]:-0}" -eq 1 ]]; then
                    die "Circular dependency detected: ${path[*]} -> $dep"
                fi
                if [[ "${state[$dep]:-0}" -eq 0 ]]; then
                    stack+=("$dep")
                fi
            done
        done
    }

    for agent in "${!all_agents[@]}"; do
        if [[ "${state[$agent]}" -eq 0 ]]; then
            _dfs_check_cycle "$agent"
        fi
    done

    return 0
}
