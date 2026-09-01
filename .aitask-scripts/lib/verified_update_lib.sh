#!/usr/bin/env bash
# Shared helpers for aitask_verified_update.sh and aitask_usage_update.sh.
# Caller scripts must source terminal_compat.sh and task_utils.sh first, and
# must set the following globals before invoking commit_metadata_update:
#   _AIT_UPDATE_MODEL_FILE_FN  — name of the caller's update_model_file function
#   _AIT_COMMIT_PREFIX         — commit message prefix (e.g. "ait: Update verified score")
# The caller's update_model_file callback is invoked with positional args:
#   <models_file> <model_name> <skill_name> <extra>
# The verified caller consumes <extra> as raw_score; the usage caller ignores it.

[[ -n "${_AIT_VERIFIED_UPDATE_LIB_LOADED:-}" ]] && return 0
_AIT_VERIFIED_UPDATE_LIB_LOADED=1

MAX_REMOTE_RETRIES=5

# --- Out-param interface (the chain does NOT return values via stdout) ---
#
# A global assigned inside `$( )` does not cross back to the caller
# (`FLAG=1; inner() { FLAG=0; echo 80; }; v="$(inner)"` leaves FLAG=1), so the
# convergence verdict cannot ride back alongside the value. Both are out-params;
# control flow stays on the exit code.
#
# ONLY THE REMOTE PATH PRODUCES A VALUE. main() tests has_remote_tracking
# itself and, on the local path, already holds the value from update_model_file
# BEFORE calling commit_metadata_update_local — so that helper must never touch
# AIT_METADATA_VALUE, including on its early "nothing staged" return.
AIT_METADATA_VALUE=""            # the new count / score (remote path only)
AIT_METADATA_LOCAL_CONVERGED=""  # 1 = local branch has the commit, 0 = origin only

run_git_quiet() {
    if [[ "${SILENT:-false}" == "true" ]]; then
        "$@" >/dev/null 2>&1
    else
        "$@"
    fi
}

log_info() {
    if [[ "${SILENT:-false}" == "false" ]]; then
        info "$@"
    fi
}

previous_calendar_month() {
    local current_month="$1"  # YYYY-MM
    if date --version >/dev/null 2>&1; then
        date -d "${current_month}-01 -1 month" "+%Y-%m"
    else
        date -j -v-1m -f "%Y-%m-%d" "${current_month}-01" "+%Y-%m"
    fi
}

has_remote_tracking() {
    ./ait git remote get-url origin >/dev/null 2>&1 || return 1
    ./ait git rev-parse --abbrev-ref HEAD >/dev/null 2>&1 || return 1
}

current_task_branch() {
    local branch
    branch="$(./ait git rev-parse --abbrev-ref HEAD)"
    if [[ "$branch" == "HEAD" ]]; then
        die "Data worktree is on a detached HEAD (possibly mid-rebase). Run './ait git-health' for diagnosis, then './ait git rebase --abort' or '--continue' to recover."
    fi
    printf '%s\n' "$branch"
}

current_task_remote() {
    ./ait git remote get-url origin
}

configure_clone_identity() {
    local repo_dir="$1"
    local user_name=""
    local user_email=""

    user_name="$(./ait git config --get user.name 2>/dev/null || git config --global --get user.name 2>/dev/null || true)"
    user_email="$(./ait git config --get user.email 2>/dev/null || git config --global --get user.email 2>/dev/null || true)"

    if [[ -n "$user_name" ]]; then
        git -C "$repo_dir" config user.name "$user_name"
    fi
    if [[ -n "$user_email" ]]; then
        git -C "$repo_dir" config user.email "$user_email"
    fi
}

run_before_push_hook() {
    local repo_dir="$1"
    local attempt="$2"

    if [[ -z "${AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK:-}" ]]; then
        return 0
    fi

    AITASK_VERIFIED_UPDATE_ATTEMPT="$attempt" \
    AITASK_VERIFIED_UPDATE_TEMP_REPO="$repo_dir" \
        run_git_quiet bash "$AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK"
}

is_retryable_push_error() {
    local output="$1"
    printf '%s' "$output" | grep -Eq 'non-fast-forward|fetch first|rejected|failed to push some refs'
}

# Reconcile the local data branch with its upstream in BOTH directions. Renamed
# from sync_current_repo_from_remote(): it now pushes as well as pulls, so the
# old name was untrue.
converge_current_repo_with_remote() {
    task_data_converge "${1:-}"
}

# Local-only commit path. Sets AIT_METADATA_LOCAL_CONVERGED=1 by construction —
# it commits straight to the local branch — and NEVER touches
# AIT_METADATA_VALUE, which its caller already holds.
commit_metadata_update_local() {
    local models_file="$1"
    local agent_string="$2"
    local skill_name="$3"

    AIT_METADATA_LOCAL_CONVERGED=1

    ./ait git add "$models_file"

    if ./ait git diff --cached --quiet -- "$models_file"; then
        return
    fi

    run_git_quiet ./ait git commit -m "${_AIT_COMMIT_PREFIX} for ${agent_string} ${skill_name}"
}

commit_and_push_from_remote_clone() {
    local models_file="$1"
    local agent_string="$2"
    local skill_name="$3"
    local model_name="$4"
    local branch="$5"
    local remote_url="$6"
    local attempt="$7"
    local extra_arg="${8:-}"

    local tmpdir clone_dir new_value push_output pushed_sha
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/aitask_metadata_remote.XXXXXX")"
    clone_dir="$tmpdir/repo"

    AIT_METADATA_VALUE=""
    AIT_METADATA_LOCAL_CONVERGED=""

    if ! run_git_quiet git clone --quiet --branch "$branch" --single-branch "$remote_url" "$clone_dir"; then
        rm -rf "$tmpdir"
        die "Failed to clone task data branch '$branch' from origin"
    fi

    configure_clone_identity "$clone_dir"

    ensure_model_exists "$clone_dir/$models_file" "$model_name"
    new_value="$("$_AIT_UPDATE_MODEL_FILE_FN" "$clone_dir/$models_file" "$model_name" "$skill_name" "$extra_arg")"

    git -C "$clone_dir" add "$models_file"
    if git -C "$clone_dir" diff --cached --quiet -- "$models_file"; then
        rm -rf "$tmpdir"
        # Nothing was committed or pushed, so there is no commit that could be
        # stranded on origin: the invariant holds vacuously.
        AIT_METADATA_VALUE="$new_value"
        AIT_METADATA_LOCAL_CONVERGED=1
        return 0
    fi

    if ! run_git_quiet git -C "$clone_dir" commit -m "${_AIT_COMMIT_PREFIX} for ${agent_string} ${skill_name}"; then
        rm -rf "$tmpdir"
        die "Failed to commit metadata update"
    fi

    run_before_push_hook "$clone_dir" "$attempt"

    if push_output="$(git -C "$clone_dir" push --quiet origin "HEAD:${branch}" 2>&1)"; then
        # Capture the pushed commit BEFORE the clone is destroyed — it is the
        # subject of the local-ref invariant below.
        pushed_sha="$(git -C "$clone_dir" rev-parse HEAD 2>/dev/null || true)"
        rm -rf "$tmpdir"

        converge_current_repo_with_remote "metadata update"

        # Evaluate the invariant as a RUNTIME FACT on the local ref, not
        # inferred from TASK_CONVERGE_STATUS: a status token describes the
        # mechanism, this ancestry check describes whether the commit is
        # actually here.
        if [[ -n "$pushed_sha" ]] && _ait_data_git merge-base --is-ancestor "$pushed_sha" HEAD 2>/dev/null; then
            AIT_METADATA_LOCAL_CONVERGED=1
        else
            AIT_METADATA_LOCAL_CONVERGED=0
            warn "metadata commit ${pushed_sha:-<unknown>} is on origin/${branch} but not on the local data branch (converge: ${TASK_CONVERGE_STATUS:-none}/${TASK_CONVERGE_REASON:-none}) — recover with './ait sync'"
        fi

        AIT_METADATA_VALUE="$new_value"
        return 0
    fi

    rm -rf "$tmpdir"

    if is_retryable_push_error "$push_output"; then
        log_info "Metadata update raced with another push; retrying (${attempt}/${MAX_REMOTE_RETRIES})"
        return 10
    fi

    die "Failed to push metadata update: $push_output"
}

commit_metadata_update() {
    local models_file="$1"
    local agent_string="$2"
    local skill_name="$3"
    local model_name="$4"
    local extra_arg="${5:-}"

    # Out-params: read by the caller scripts' main(), which shellcheck cannot see
    # from inside this library.
    # shellcheck disable=SC2034
    AIT_METADATA_VALUE=""
    # shellcheck disable=SC2034
    AIT_METADATA_LOCAL_CONVERGED=""

    if ! has_remote_tracking; then
        # Same rule as commit_metadata_update_local: no value is produced here.
        commit_metadata_update_local "$models_file" "$agent_string" "$skill_name"
        return 0
    fi

    local branch remote_url attempt rc
    branch="$(current_task_branch)"
    remote_url="$(current_task_remote)"

    # Pre-converge ONCE, before the first clone. Divergence forms when the temp
    # clone is cut from an origin tip that lacks local's unpushed commits, so
    # publishing local's half first (or fast-forwarding onto origin's) keeps the
    # clone's base current. A branch already diverged on entry is reported by
    # task_data_converge and the update proceeds anyway — the usage/score bump
    # must not be lost — but its result will be partial, not success.
    converge_current_repo_with_remote "metadata update (pre-converge)"

    for attempt in $(seq 1 "$MAX_REMOTE_RETRIES"); do
        set +e
        commit_and_push_from_remote_clone "$models_file" "$agent_string" "$skill_name" "$model_name" "$branch" "$remote_url" "$attempt" "$extra_arg"
        rc=$?
        set -e

        if [[ $rc -eq 0 ]]; then
            return 0
        fi
        if [[ $rc -ne 10 ]]; then
            return "$rc"
        fi
    done

    die "Failed to update metadata after ${MAX_REMOTE_RETRIES} retries due to concurrent pushes"
}
