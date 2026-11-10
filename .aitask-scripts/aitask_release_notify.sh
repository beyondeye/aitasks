#!/usr/bin/env bash
# aitask_release_notify.sh - Tell resolved issues which release ships their fix
# (t2261_2).
#
# Reads the rolling release ledger (aitasks/metadata/release_issues/, written
# by aitask_issue_update.sh — see lib/release_issue_ledger.sh) and, for each
# pending record whose task commits are in <prev-tag>..<tag>, comments
# "Released in <tag>" on the issue and moves the record to released/<tag>/.
#
# Every posting run is gated, in this order, and posts nothing unless all pass:
#   1. the task data is provably fresh against origin (ril_data_freshness)
#   2. this machine is the designated one (release_notify_host)
#   3. the local run lock is free (one consumer at a time on this machine)
#   4. interrupted moves from an earlier run are completed (residue sweep)
#   5. the release is verifiably published (release_publication_check, which
#      applies the project's publication policy from project_config.yaml)
#
# Duplicate prevention covers runs serialised on the designated machine and
# sequential retries: the run lock, a hidden marker checked before each post,
# and one committed move per record. It is NOT an exactly-once guarantee.
#
# Usage: ait release-notify [--tag T] [--prev-tag P] [--dry-run] [--list] [--no-push]
# Exit:  0 complete | 1 usage | 2 refused input | 3 incomplete (nothing posted)
#        4 partial (at least one FAILED or MALFORMED record)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/issue_backends.sh
source "$SCRIPT_DIR/lib/issue_backends.sh"
# shellcheck source=lib/release_issue_ledger.sh
source "$SCRIPT_DIR/lib/release_issue_ledger.sh"

TAG=""
PREV_TAG=""
PREV_TAG_SET=false
DRY_RUN=false
LIST_ONLY=false
NO_PUSH=false

# Globals the backends read (lib/issue_backends.sh).
SOURCE=""
GITLAB_REPO_SLUG=""

# Run state.
_RN_PHASE=""
COMMITTED=0
N_POSTED=0
N_ALREADY=0
N_RESUMED=0
N_PENDING=0
N_SHIPPED=0
N_FAILED=0
N_MALFORMED=0
N_LOOKUP_FAILED=0   # set by scan_records: a containing-tag lookup that failed
VERSION_TAGS=()
CONTAINING=()

usage() {
    cat <<'EOF'
Usage: ait release-notify [--tag T] [--prev-tag P] [--dry-run] [--list] [--no-push]

Comment "Released in <tag>" on every resolved issue whose task commits are in
<prev-tag>..<tag>, then move its ledger record to released/<tag>/.

Options:
  --tag T        The release tag (default: the latest v* tag)
  --prev-tag P   The previous release tag (default: the next lower v* tag;
                 with none, all history up to T)
  --dry-run      Report what would be posted, and the gate states; change nothing
  --list         List pending records and the per-release history
  --no-push      Do not push the task data at the end
  -h, --help     Show this help

Posting is gated: fresh task data, the designated machine (release_notify_host),
the local run lock, then a verifiably published release (the project's
release_publication_* policy in aitasks/metadata/project_config.yaml).

Output lines: RANGE:, FRESHNESS:, DESIGNATION:, PUBLICATION:, RESIDUE:,
RESUMED:, DUE:, POSTED:, ALREADY_NOTIFIED:, PENDING:, SHIPPED_EARLIER:,
FAILED:, MALFORMED:, INCOMPLETE:, HINT:, PUSH:, SUMMARY:.

Exit status:
  0  complete
  1  usage error
  2  refused input (a missing or invalid tag)
  3  incomplete: a gate failed and nothing was posted
  4  partial: at least one record FAILED or is MALFORMED
EOF
}

refuse() {
    echo "aitask_release_notify.sh: $1" >&2
    exit 2
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tag)
                [[ $# -ge 2 ]] || { usage >&2; exit 1; }
                TAG="$2"; shift 2 ;;
            --prev-tag)
                [[ $# -ge 2 ]] || { usage >&2; exit 1; }
                PREV_TAG="$2"; PREV_TAG_SET=true; shift 2 ;;
            --dry-run) DRY_RUN=true; shift ;;
            --list)    LIST_ONLY=true; shift ;;
            --no-push) NO_PUSH=true; shift ;;
            -h|--help) usage; exit 0 ;;
            *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
        esac
    done
}

# The exact command that re-runs this invocation (for hints).
same_command() {
    local cmd="ait release-notify --tag $TAG"
    if [[ "$PREV_TAG_SET" == true && -n "$PREV_TAG" ]]; then cmd+=" --prev-tag $PREV_TAG"; fi
    printf '%s\n' "$cmd"
}

tag_commit() { git rev-parse --verify --quiet "refs/tags/${1}^{commit}" 2>/dev/null; }

# git_lines <array-name> <git args…> — git's full output as lines, or rc 1
# when git failed. Captured with $( ) so the status is git's own: neither
# `| head` (SIGPIPE on a large output, under pipefail) nor `mapfile < <(git …)`
# (whose success says nothing about git) — an empty or truncated list from a
# failed git must never read as a real one.
git_lines() {
    local -n _gl_out="$1"
    local _gl_text
    shift
    _gl_out=()
    _gl_text="$(git "$@" 2>/dev/null)" || return 1
    [[ -n "$_gl_text" ]] || return 0
    mapfile -t _gl_out <<< "$_gl_text"
}

# An unestablished precondition before the gate: nothing was posted.
abort_unknown() {
    echo "INCOMPLETE:$1"
    echo "HINT:$2"
    exit 3
}

# The v* tags, newest first, read in full.
version_tags() {
    git_lines VERSION_TAGS tag --list 'v*' --sort=-version:refname \
        || abort_unknown "tags:git_failed" "git tag --list failed; nothing was posted. Fix the repository, then re-run"
}

resolve_tags() {
    local i
    version_tags
    if [[ -z "$TAG" ]]; then
        TAG="${VERSION_TAGS[0]:-}"
        [[ -n "$TAG" ]] || refuse "no v* tag found; pass --tag"
    fi
    ril_valid_tag "$TAG" || refuse "invalid tag: $TAG"
    tag_commit "$TAG" >/dev/null || refuse "tag not found: $TAG"
    if [[ "$PREV_TAG_SET" == false ]]; then
        PREV_TAG=""
        for i in "${!VERSION_TAGS[@]}"; do
            if [[ "${VERSION_TAGS[i]}" == "$TAG" ]]; then
                PREV_TAG="${VERSION_TAGS[i+1]:-}"
                break
            fi
        done
    fi
    if [[ -n "$PREV_TAG" ]]; then
        ril_valid_tag "$PREV_TAG" || refuse "invalid previous tag: $PREV_TAG"
        tag_commit "$PREV_TAG" >/dev/null || refuse "previous tag not found: $PREV_TAG"
    fi
}

# --- Commits ---------------------------------------------------------------

RANGE_LOG=""   # "<sha>\t<subject>" lines in PREV_TAG..TAG
PREV_LOG=""    # the same, reachable from PREV_TAG (empty without one)

load_logs() {
    local hint="git log failed; nothing was posted. Fix the repository, then re-run"
    if [[ -n "$PREV_TAG" ]]; then
        RANGE_LOG="$(git log --format='%H%x09%s' "refs/tags/$PREV_TAG..refs/tags/$TAG" --)" \
            || abort_unknown "log:git_failed" "$hint"
        PREV_LOG="$(git log --format='%H%x09%s' "refs/tags/$PREV_TAG" --)" \
            || abort_unknown "log:git_failed" "$hint"
    else
        RANGE_LOG="$(git log --format='%H%x09%s' "refs/tags/$TAG" --)" \
            || abort_unknown "log:git_failed" "$hint"
        PREV_LOG=""
    fi
}

# task_commit_re <task_id> — the commit-tag regex: a parent id P matches (tP)
# and (tP_<n>); a child id P_C matches (tP_C) only.
task_commit_re() {
    if [[ "$1" == *_* ]]; then
        printf '%s\n' "\\(t${1}\\)"
    else
        printf '%s\n' "\\(t${1}(_[0123456789]+)?\\)"
    fi
}

# mapped_commits <task_id> <log> — the "<sha>\t<subject>" lines for the task.
mapped_commits() {
    local re line subj
    re="$(task_commit_re "$1")"
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        subj="${line#*$'\t'}"
        if [[ "$subj" =~ $re ]]; then printf '%s\n' "$line"; fi
    done <<< "$2"
}

# --- Records ---------------------------------------------------------------
#
# scan_records fills, per pending record: DUE_* (to post), and prints the
# PENDING / SHIPPED_EARLIER / MALFORMED lines for the rest when $1 is "report".
DUE_PATHS=()
DUE_TASKS=()
DUE_URLS=()
DUE_PLATFORMS=()
DUE_COMMITS=()   # newline-separated "<sha>\t<subject>" per record

scan_records() {
    local report="$1" f task url platform state mapped earlier newest e
    DUE_PATHS=(); DUE_TASKS=(); DUE_URLS=(); DUE_PLATFORMS=(); DUE_COMMITS=()
    N_PENDING=0; N_SHIPPED=0; N_MALFORMED=0; N_LOOKUP_FAILED=0
    for f in "$(ril_root)"/pending/*.rec; do
        [[ -e "$f" ]] || continue
        if ! ril_validate_pending_record "$f"; then
            N_MALFORMED=$((N_MALFORMED + 1))
            [[ "$report" == report ]] && echo "MALFORMED:$f"
            continue
        fi
        task="$(ril_read "$f" task_id)"
        url="$(ril_read "$f" issue_url)"
        platform="$(ril_read "$f" platform)"
        state="$(_ril_hit_state "$f")"
        if [[ -n "${UNRESOLVED_RESIDUE[$(basename "$f")]+x}" ]]; then
            # An interrupted move of this record could not be completed: leave
            # the record alone until a human has looked at the residue.
            N_PENDING=$((N_PENDING + 1))
            [[ "$report" == report ]] && echo "PENDING:$task|$url|residue_unresolved"
            continue
        fi
        if [[ "$state" != committed ]]; then
            N_PENDING=$((N_PENDING + 1))
            [[ "$report" == report ]] && echo "PENDING:$task|$url|uncommitted_record"
            continue
        fi
        mapped="$(mapped_commits "$task" "$RANGE_LOG")"
        if [[ -n "$mapped" ]]; then
            DUE_PATHS+=("$f"); DUE_TASKS+=("$task"); DUE_URLS+=("$url")
            DUE_PLATFORMS+=("$platform"); DUE_COMMITS+=("$mapped")
            continue
        fi
        earlier=""
        [[ -n "$PREV_LOG" ]] && earlier="$(mapped_commits "$task" "$PREV_LOG")"
        if [[ -n "$earlier" ]]; then
            newest="${earlier%%$'\t'*}"
            e=""
            if ! git_lines CONTAINING tag --contains "$newest" --list 'v*' --sort=version:refname; then
                # Not due either way, but which release shipped it is unknown:
                # say so instead of guessing, and do not report the run complete.
                N_LOOKUP_FAILED=$((N_LOOKUP_FAILED + 1))
                [[ "$report" == report ]] && echo "FAILED:$task|$url|tag_lookup_failed"
                continue
            fi
            e="${CONTAINING[0]:-}"
            if [[ -n "$e" ]] && ril_valid_tag "$e"; then
                N_SHIPPED=$((N_SHIPPED + 1))
                if [[ "$report" == report ]]; then
                    echo "SHIPPED_EARLIER:$task|$url|$e"
                    echo "HINT:t$task shipped in $e, before this range; it stays pending (no automatic catch-up). Notify it with: ait release-notify --tag $e"
                fi
                continue
            fi
        fi
        N_PENDING=$((N_PENDING + 1))
        [[ "$report" == report ]] && echo "PENDING:$task|$url|no_commits"
    done
    return 0
}

print_due() {
    local i n
    for i in "${!DUE_PATHS[@]}"; do
        n="$(printf '%s\n' "${DUE_COMMITS[i]}" | grep -c . || true)"
        echo "DUE:${DUE_TASKS[i]}|${DUE_URLS[i]}|$n"
    done
}

# --- List mode ---------------------------------------------------------------

list_ledger() {
    local root f d any=0
    root="$(ril_root)"
    echo "PENDING_RECORDS:"
    for f in "$root"/pending/*.rec; do
        [[ -e "$f" ]] || continue
        any=1
        if ril_validate_pending_record "$f"; then
            echo "  t$(ril_read "$f" task_id) $(ril_read "$f" issue_url) ($(ril_read "$f" action), $(ril_read "$f" recorded_at))"
        else
            echo "  MALFORMED $f"
        fi
    done
    [[ "$any" == 1 ]] || echo "  (none)"
    for d in "$root"/released/*/; do
        [[ -d "$d" ]] || continue
        echo "RELEASED:$(basename "$d")"
        for f in "$d"*.rec; do
            [[ -e "$f" ]] || continue
            if ril_validate_released_record "$f"; then
                echo "  t$(ril_read "$f" task_id) $(ril_read "$f" issue_url) ($(ril_read "$f" outcome), $(ril_read "$f" notified_at))"
            else
                echo "  MALFORMED $f"
            fi
        done
    done
}

# --- Posting -----------------------------------------------------------------

# The hidden marker that makes a re-run a no-op for an already-notified issue.
marker_for() { printf '<!-- aitask-release:%s t%s -->' "$TAG" "$1"; }

comment_body() {
    local task="$1" commits="$2" url="$3" line
    marker_for "$task"
    printf '\n## Released in %s\n\n' "$TAG"
    printf 'The fix for this issue (aitask t%s) ships in [%s](%s).\n\n' "$task" "$TAG" "$url"
    printf '### Commits in this release\n\n```\n'
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        printf '%s %s\n' "${line:0:12}" "${line#*$'\t'}"
    done <<< "$commits"
    printf '```\n'
}

# set_source <platform> <issue_url> — the backend globals for one record.
set_source() {
    SOURCE="$1"
    GITLAB_REPO_SLUG=""
    if [[ "$SOURCE" == gitlab ]]; then
        # shellcheck disable=SC2034  # read by glab_repo_flag (lib/issue_backends.sh)
        GITLAB_REPO_SLUG="$(gitlab_extract_repo_from_issue_url "$2")"
    fi
}

# move_record <i> <outcome> — move due record i; prints the result line.
move_record() {
    local i="$1" outcome="$2" shas line out mrc=0 why
    shas="$(printf '%s\n' "${DUE_COMMITS[i]}" | cut -f1 | paste -sd, -)"
    out="$(mktemp "${TMPDIR:-/tmp}/ait_relnotify_mv_XXXXXX")"
    ril_move_released "${DUE_PATHS[i]}" "$TAG" "$outcome" "$shas" > "$out" || mrc=$?
    line="$(head -n1 "$out" 2>/dev/null || true)"
    rm -f "$out"
    case "$line" in
        RIL_MOVED:*|RIL_MOVE_RESUMED:*)
            COMMITTED=$((COMMITTED + 1))
            if [[ "$outcome" == posted ]]; then
                N_POSTED=$((N_POSTED + 1))
                echo "POSTED:${DUE_TASKS[i]}|${DUE_URLS[i]}|${line#*:}"
            else
                N_ALREADY=$((N_ALREADY + 1))
                echo "ALREADY_NOTIFIED:${DUE_TASKS[i]}|${DUE_URLS[i]}|${line#*:}"
            fi ;;
        *)
            N_FAILED=$((N_FAILED + 1))
            why="${line#RIL_MOVE_FAILED:}"
            why="${why%%:*}"
            [[ -n "$line" ]] || why="move_died_rc_$mrc"
            echo "FAILED:${DUE_TASKS[i]}|${DUE_URLS[i]}|$why"
            echo "HINT:the comment for t${DUE_TASKS[i]} is on the issue; a re-run finds its marker and records the move: $(same_command)" ;;
    esac
}

post_due() {
    local i task url platform bodies lrc release_url body prc
    release_url="$(release_publication_release_url "$TAG")"
    for i in "${!DUE_PATHS[@]}"; do
        task="${DUE_TASKS[i]}"; url="${DUE_URLS[i]}"; platform="${DUE_PLATFORMS[i]}"
        set_source "$platform" "$url"
        lrc=0
        bodies="$(source_list_comment_bodies "$url" 2>/dev/null)" || lrc=$?
        if [[ "$lrc" != 0 ]]; then
            N_FAILED=$((N_FAILED + 1))
            echo "FAILED:$task|$url|comment_list_unknown"
            continue
        fi
        # A plain substring test, never `printf | grep -q`: under pipefail an
        # early match closes the pipe, printf dies of SIGPIPE, and a found
        # marker would read as absent — posting a duplicate.
        if [[ "$bodies" == *"$(marker_for "$task")"* ]]; then
            move_record "$i" already_present
            continue
        fi
        body="$(comment_body "$task" "${DUE_COMMITS[i]}" "$release_url")"
        prc=0
        # A subshell: a backend die (missing CLI) fails this record, not the run.
        ( source_add_comment "$(source_issue_ref "$url")" "$body" ) >/dev/null 2>&1 || prc=$?
        if [[ "$prc" != 0 ]]; then
            N_FAILED=$((N_FAILED + 1))
            echo "FAILED:$task|$url|post_failed"
            continue
        fi
        move_record "$i" posted
    done
}

# --- Residue -----------------------------------------------------------------

RESIDUE_LINES=""
RESIDUE_SCAN_OK=true
declare -A UNRESOLVED_RESIDUE=()   # record filename -> 1, for residue the sweep refused

scan_residue() {
    RESIDUE_SCAN_OK=true
    RESIDUE_LINES="$(ril_list_residue)" || RESIDUE_SCAN_OK=false
    local l
    while IFS= read -r l; do
        [[ -n "$l" ]] || continue
        echo "RESIDUE:${l#*:}|${l%%:*}"
    done <<< "$RESIDUE_LINES"
    [[ "$RESIDUE_SCAN_OK" == true ]] || echo "RESIDUE:-|scan_failed"
    return 0
}

sweep_residue() {
    local l kind path out line task
    [[ "$RESIDUE_SCAN_OK" == true ]] || { N_FAILED=$((N_FAILED + 1)); echo "FAILED:-|-|residue_scan_failed"; }
    while IFS= read -r l; do
        [[ -n "$l" ]] || continue
        kind="${l%%:*}"
        path="${l#*:}"
        if [[ "$kind" == unpaired ]]; then
            N_FAILED=$((N_FAILED + 1))
            UNRESOLVED_RESIDUE["$(basename "$path")"]=1
            echo "FAILED:-|$path|unpaired_pending_deletion"
            echo "HINT:$path was deleted but never moved to released/; restore it (./ait git checkout -- $path) or commit the deletion deliberately"
            continue
        fi
        out="$(mktemp "${TMPDIR:-/tmp}/ait_relnotify_rs_XXXXXX")"
        ril_resume_move "$path" > "$out" || true
        line="$(head -n1 "$out" 2>/dev/null || true)"
        rm -f "$out"
        task="$(ril_read "$path" task_id 2>/dev/null || echo -)"
        case "$line" in
            RIL_MOVE_RESUMED:*)
                COMMITTED=$((COMMITTED + 1))
                N_RESUMED=$((N_RESUMED + 1))
                echo "RESUMED:$task|$(ril_read "$path" issue_url 2>/dev/null || echo -)|$path" ;;
            *)
                N_FAILED=$((N_FAILED + 1))
                UNRESOLVED_RESIDUE["$(basename "$path")"]=1
                line="${line#RIL_MOVE_FAILED:}"
                echo "FAILED:$task|$path|${line%%:*}"
                echo "HINT:$path was left as it is; inspect it and its pending twin by hand" ;;
        esac
    done <<< "$RESIDUE_LINES"
}

# --- Exit --------------------------------------------------------------------

summary() {
    echo "SUMMARY:posted=$N_POSTED already=$N_ALREADY resumed=$N_RESUMED pending=$N_PENDING shipped_earlier=$N_SHIPPED failed=$((N_FAILED + N_LOOKUP_FAILED)) malformed=$N_MALFORMED"
}

incomplete() {
    echo "INCOMPLETE:$1"
    echo "HINT:$2"
    summary
    exit 3
}

# The EXIT trap. A die while acquiring the run lock (its retries exhausted)
# is an incomplete run, not a crash. The status reaches the ledger trap as an
# argument, so a cleanup can never mask it.
# shellcheck disable=SC2329  # invoked from the EXIT trap string
_rn_on_exit() {
    local rc="$1"
    if [[ "$_RN_PHASE" == run_lock && "$rc" != 0 ]]; then
        echo "INCOMPLETE:run_lock:busy"
        echo "HINT:another release-notify run holds the lock on this machine; wait for it, then re-run: $(same_command)"
        rc=3
    fi
    ait_ledger_lock_exit_trap "$rc"
}

do_push() {
    local st
    if [[ "$NO_PUSH" == true || "$COMMITTED" == 0 ]]; then
        echo "PUSH:skipped"
        return 0
    fi
    st="$( task_push >&2; printf '%s' "${TASK_PUSH_STATUS:-}" )" || st=""
    case "$st" in
        pushed|up-to-date) echo "PUSH:ok" ;;
        no-remote)         echo "PUSH:skipped" ;;
        *)                 echo "PUSH:failed" ;;
    esac
}

main() {
    local fresh desig pub
    parse_args "$@"

    # Listing the ledger needs no release range (a new project has no tags).
    if [[ "$LIST_ONLY" == true ]]; then
        list_ledger
        exit 0
    fi
    resolve_tags

    echo "RANGE:${PREV_TAG:-(root)}..$TAG"
    load_logs
    scan_residue

    if [[ "$DRY_RUN" == true ]]; then
        scan_records report
        print_due
        echo "FRESHNESS:$(ril_data_freshness || true)"
        echo "DESIGNATION:$(release_notify_designation || true)"
        pub="$(release_publication_check "$TAG" || true)"
        echo "$pub"
        summary
        exit 0
    fi

    # --- The posting gate. Freshness and designation are checked even when
    # nothing is due locally: "nothing to do" from stale data is not an
    # all-clear.
    fresh="$(ril_data_freshness)" || \
        incomplete "freshness:$fresh" "run ./ait sync (resolve any conflict), then re-run: $(same_command)"
    echo "FRESHNESS:$fresh"
    # The policy is read before anything that depends on it (the designation
    # lives in the same file), so a mis-saved key is named as such.
    release_publication_policy_load || \
        incomplete "policy_unreadable:$RP_POLICY_ERR" "fix the release_notify_host / release_publication_* keys in aitasks/metadata/project_config.yaml, then re-run: $(same_command)"
    desig="$(release_notify_designation)" || {
        if [[ "$desig" == unset ]]; then
            incomplete "designation:unset" "add 'release_notify_host: $(hostname 2>/dev/null)' to aitasks/metadata/project_config.yaml to make this the notification machine"
        elif [[ "$desig" == not_designated:* ]]; then
            local d="${desig#not_designated:}"
            incomplete "designation:$desig" "notifications run only on ${d%%|*}: run '$(same_command)' there"
        fi
        incomplete "designation:$desig" "fix release_notify_host in aitasks/metadata/project_config.yaml, then re-run: $(same_command)"
    }
    echo "DESIGNATION:$desig"

    _RN_PHASE=run_lock
    trap 'rc=$?; _rn_on_exit "$rc"' EXIT
    if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi
    ait_ledger_lock_acquire release_notify run "release-notify run lock" "release-notify run lock"
    _RN_PHASE=locked

    # Complete interrupted moves first, so a record whose comment is already
    # posted is never classified due again; then classify from scratch.
    sweep_residue
    scan_records quiet

    if (( ${#DUE_PATHS[@]} )); then
        print_due
        pub="$(release_publication_check "$TAG")" || \
            incomplete "not_published:${pub#PUBLICATION:}" "nothing was posted and every record stays pending; re-run once the release is published: $(same_command)"
        echo "$pub"
        release_publication_origin || \
            incomplete "not_published:unknown:platform" "origin is not a GitHub or GitLab remote"
        post_due
    fi

    # Report what stays pending, now that the sweep and the posts are done. A
    # due record that FAILED is still due and already has its FAILED line.
    scan_records report

    do_push
    summary
    if (( N_FAILED > 0 || N_LOOKUP_FAILED > 0 || N_MALFORMED > 0 )); then exit 4; fi
    exit 0
}

main "$@"
