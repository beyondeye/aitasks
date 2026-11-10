#!/usr/bin/env bash
# release_issue_ledger.sh - The rolling "issues fixed since the last release"
# ledger (t2261).
#
# Contract: the "Ledger contract" section of the t2261 parent plan
# (aiplans/p2261_release_issue_notifications.md, under aiplans/archived/ once
# it lands). In short:
#
#   <root>/pending/<task_id>--<key>.rec           written by ril_record
#   <root>/released/<tag>/<task_id>--<key>.rec    moved there by the release
#                                                 consumer (t2261_2)
#
#   <root> is ${TASK_DIR:-aitasks}/metadata/release_issues: on the task-data
#   branch in branch mode, on the code branch in legacy mode.
#
#   <key> is the first 16 hex characters of
#   `printf '%s' "$issue_url" | git hash-object --stdin`. It is only a
#   filename. IDENTITY is the exact task_id + issue_url bytes stored in the
#   file, and a filename hit whose stored pair differs is refused
#   (hash_collision), never treated as a match.
#
#   One `key=value` field per line, read by exact key match, and every value
#   validated on write AND on read:
#       schema=1
#       task_id=<N or N_M>
#       issue_url=<http(s) URL in the contract charset>
#       platform=github|gitlab
#       action=closed|commented|closed_silent
#       recorded_at=<YYYY-MM-DDTHH:MM:SSZ>
#
# One file per record, so two machines recording between syncs never write the
# same path. Writers on ONE machine are serialized by the release_issues ledger
# lock (lib/ledger_block.sh, built on lib/stale_lock.sh).
#
# A released copy carries the six pending fields plus:
#       released_tag=<the release tag; also the directory name>
#       notified_at=<YYYY-MM-DDTHH:MM:SSZ>
#       outcome=posted|already_present
#       commits=<full sha>[,<full sha>...]
#
# Requires lib/task_utils.sh to be sourced first (task_git, die/warn, the scoped
# commit helpers). The release consumer (aitask_release_notify.sh, t2261_2) uses
# the move, resume and freshness helpers at the end of this file.

[[ -n "${_AIT_RELEASE_ISSUE_LEDGER_LOADED:-}" ]] && return 0
_AIT_RELEASE_ISSUE_LEDGER_LOADED=1

# shellcheck source=ledger_block.sh
source "$(dirname "${BASH_SOURCE[0]}")/ledger_block.sh"
# shellcheck source=release_publication.sh
source "$(dirname "${BASH_SOURCE[0]}")/release_publication.sh"

RIL_SCHEMA=1
# The contract's URL charset as a tr(1) set. Always used under LC_ALL=C, so the
# ranges are byte ranges in every locale.
RIL_URL_CHARSET="A-Za-z0-9._~:/?#@!\$&'()*+,;=%-"
# The fields of a pending record, in the order the writer emits them.
RIL_PENDING_FIELDS=(schema task_id issue_url platform action recorded_at)
# The fields a released copy adds, in the order the move writes them.
RIL_RELEASED_FIELDS=(released_tag notified_at outcome commits)
# Status carrier for ril_record's EXIT trap. Declared here because its only
# assignment lives inside a single-quoted trap string, which shellcheck cannot
# see into.
_ril_rc=0

# --- Paths -----------------------------------------------------------------

ril_root() { printf '%s\n' "${TASK_DIR:-aitasks}/metadata/release_issues"; }

# ril_key <issue_url> — the 16-hex filename key. rc 1 when git cannot hash.
ril_key() {
    local h
    h="$(printf '%s' "${1-}" | git hash-object --stdin 2>/dev/null)" || return 1
    h="${h:0:16}"
    [[ "$h" =~ ^[0123456789abcdef]{16}$ ]] || return 1
    printf '%s\n' "$h"
}

# ril_name <task_id> <issue_url> — the record's filename.
ril_name() {
    local key
    key="$(ril_key "${2-}")" || return 1
    printf '%s--%s.rec\n' "${1-}" "$key"
}

# --- Validation ------------------------------------------------------------
#
# Digits are spelled out ([0123456789], never [0-9]) so no check depends on how
# a locale collates a range.

ril_valid_task_id() { [[ "${1-}" =~ ^[0123456789]+(_[0123456789]+)?$ ]]; }

ril_valid_url() {
    local v="${1-}" rest
    case "$v" in
        http://?*|https://?*) ;;
        *) return 1 ;;
    esac
    # Every byte outside the charset survives the delete. The `x` sentinel: $( )
    # strips trailing newlines, so a URL whose only stray byte is a trailing
    # newline would otherwise leave nothing behind and pass (the idiom of
    # validate_file_ref in lib/task_utils.sh).
    rest="$(printf '%s' "$v" | LC_ALL=C tr -d "$RIL_URL_CHARSET"; printf x)"
    [[ "$rest" == "x" ]]
}

ril_valid_enum() {
    local v="${1-}" alt
    shift
    for alt in "$@"; do
        if [[ "$v" == "$alt" ]]; then return 0; fi
    done
    return 1
}

ril_valid_iso_utc() {
    [[ "${1-}" =~ ^[0123456789]{4}-[0123456789]{2}-[0123456789]{2}T[0123456789]{2}:[0123456789]{2}:[0123456789]{2}Z$ ]]
}

# A release tag: it becomes a directory name, a comment marker and a URL path
# segment (rp_valid_tag, lib/release_publication.sh).
ril_valid_tag() { rp_valid_tag "${1-}"; }

ril_valid_commits() {
    [[ "${1-}" =~ ^[0123456789abcdef]{40}(,[0123456789abcdef]{40})*$ ]]
}

# ril_valid_field <field> <value> — rc 0 valid, 1 invalid, 2 unknown field.
ril_valid_field() {
    case "${1-}" in
        schema)      [[ "${2-}" == "$RIL_SCHEMA" ]] ;;
        task_id)     ril_valid_task_id "${2-}" ;;
        issue_url)   ril_valid_url "${2-}" ;;
        platform)    ril_valid_enum "${2-}" github gitlab ;;
        action)      ril_valid_enum "${2-}" closed commented closed_silent ;;
        recorded_at) ril_valid_iso_utc "${2-}" ;;
        released_tag) ril_valid_tag "${2-}" ;;
        notified_at)  ril_valid_iso_utc "${2-}" ;;
        outcome)      ril_valid_enum "${2-}" posted already_present ;;
        commits)      ril_valid_commits "${2-}" ;;
        *)           return 2 ;;
    esac
}

# _ril_known_field <key> — a PENDING field. This is the whitelist of
# ril_validate_pending_record and must stay pending-only: widening it would let
# a pending record carry released-only keys (even duplicated, invalid ones) and
# still validate.
_ril_known_field() {
    local f
    for f in "${RIL_PENDING_FIELDS[@]}"; do
        if [[ "${1-}" == "$f" ]]; then return 0; fi
    done
    return 1
}

_ril_known_released_field() {
    local f
    for f in "${RIL_RELEASED_FIELDS[@]}"; do
        if [[ "${1-}" == "$f" ]]; then return 0; fi
    done
    return 1
}

# _ril_readable_field <key> — any field ril_read may be asked for.
_ril_readable_field() { _ril_known_field "${1-}" || _ril_known_released_field "${1-}"; }

# Every byte of a record is printable ASCII or a newline. Counted with wc, not
# compared through $( ): a command substitution silently drops NUL bytes, which
# would make a file holding one look clean.
_ril_file_bytes_ok() {
    local n
    n="$(LC_ALL=C tr -d '\n -~' < "$1" 2>/dev/null | wc -c | tr -d ' ')"
    [[ "$n" == "0" ]]
}

# --- Reading ---------------------------------------------------------------

# ril_read <path> <field> — print one field's value.
#   rc 0  printed
#   rc 1  the file is missing or unreadable
#   rc 2  unknown field
#   rc 3  MALFORMED: a stray byte in the file, the key missing or repeated, or
#         the value invalid
ril_read() {
    local path="${1-}" field="${2-}" n val
    _ril_readable_field "$field" || return 2
    [[ -f "$path" && -r "$path" ]] || return 1
    _ril_file_bytes_ok "$path" || return 3
    # Field names come from the fixed set above, so they are safe in a pattern.
    n="$(grep -c -- "^${field}=" "$path" 2>/dev/null || true)"
    [[ "$n" == "1" ]] || return 3
    val="$(sed -n "s/^${field}=//p" "$path" 2>/dev/null)" || return 1
    ril_valid_field "$field" "$val" || return 3
    printf '%s\n' "$val"
}

# _ril_pending_fields_ok <path> — each of the six pending fields occurs exactly
# once with a valid value. Other keys are not judged here: the whole-record
# validators below decide which other keys a record may carry.
#   rc 0 valid | 3 MALFORMED
_ril_pending_fields_ok() {
    local f rc
    for f in "${RIL_PENDING_FIELDS[@]}"; do
        rc=0
        ril_read "$1" "$f" >/dev/null || rc=$?
        [[ "$rc" == 0 ]] || return 3
    done
    return 0
}

# ril_validate_pending_record <path> — the whole file: every line is key=value
# with a known pending key, each key occurs exactly once, every value is valid.
#   rc 0 valid | 1 unreadable | 3 MALFORMED
ril_validate_pending_record() {
    local path="${1-}" line
    [[ -f "$path" && -r "$path" ]] || return 1
    _ril_file_bytes_ok "$path" || return 3
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" == *=* ]] || return 3
        _ril_known_field "${line%%=*}" || return 3
    done < "$path"
    _ril_pending_fields_ok "$path"
}

# ril_validate_released_record <path> — the whole released copy: every line is
# key=value with a pending or released key, each of the ten keys occurs exactly
# once, and every value is valid.
#   rc 0 valid | 1 unreadable | 3 MALFORMED
ril_validate_released_record() {
    local path="${1-}" line f rc
    [[ -f "$path" && -r "$path" ]] || return 1
    _ril_file_bytes_ok "$path" || return 3
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" == *=* ]] || return 3
        _ril_readable_field "${line%%=*}" || return 3
    done < "$path"
    for f in "${RIL_PENDING_FIELDS[@]}" "${RIL_RELEASED_FIELDS[@]}"; do
        rc=0
        ril_read "$path" "$f" >/dev/null || rc=$?
        [[ "$rc" == 0 ]] || return 3
    done
    return 0
}

# ril_find <task_id> <issue_url> — look the pair up in pending/ and released/.
#   rc 0  prints pending:<path> or released:<path> (same pair stored there)
#   rc 1  no file of that name
#   rc 3  prints <path>: a file of that name is MALFORMED
#   rc 4  prints <path>: hash_collision (same name, different stored pair)
#   rc 5  the key could not be derived
# Presence only: whether git holds the file is _ril_hit_state's question.
ril_find() {
    local task="${1-}" url="${2-}" name root f kind st_task st_url
    name="$(ril_name "$task" "$url")" || return 5
    root="$(ril_root)"
    for f in "$root/pending/$name" "$root"/released/*/"$name"; do
        [[ -e "$f" ]] || continue
        if [[ "$f" == "$root/pending/$name" ]]; then kind=pending; else kind=released; fi
        st_task="$(ril_read "$f" task_id)" || { printf '%s\n' "$f"; return 3; }
        st_url="$(ril_read "$f" issue_url)" || { printf '%s\n' "$f"; return 3; }
        if [[ "$st_task" == "$task" && "$st_url" == "$url" ]]; then
            printf '%s:%s\n' "$kind" "$f"
            return 0
        fi
        printf '%s\n' "$f"
        return 4
    done
    return 1
}

# _ril_hit_state <path> — the git state of a record file. Prints exactly one of
#   committed   in HEAD, and the worktree and index match it
#   untracked   not in HEAD, not in the index
#   staged      not in HEAD, added to the index (A / AM)
#   modified    in HEAD, but the worktree or index differs
#   unknown     the status probe failed, or any other shape
# Writes nothing. Both probes are on task_git's read-only list
# (_ait_git_subcmd_is_readonly), so neither dies on a wedged data worktree;
# `cat-file` is not on that list and would.
_ril_hit_state() {
    local path="$1" st st_rc=0 in_head=0
    if task_git rev-parse --verify --quiet "HEAD:$path" >/dev/null 2>&1; then
        in_head=1
    fi
    # -uall: with an untracked pending/ directory, plain status would name the
    # directory instead of the file.
    st="$(task_git status --porcelain --untracked-files=all -- "$path" 2>/dev/null)" || st_rc=$?
    if [[ "$st_rc" != 0 ]]; then
        echo unknown
        return 0
    fi
    if [[ "$in_head" == 1 ]]; then
        if [[ -z "$st" ]]; then echo committed; else echo modified; fi
        return 0
    fi
    case "$st" in
        '?? '*)         echo untracked ;;
        'A  '*|'AM '*)  echo staged ;;
        *)              echo unknown ;;
    esac
}

# --- Writing ---------------------------------------------------------------
#
# State of one ril_record run (the subshell owns these, so nothing leaks):
#   _RIL_TMP    the temp file being written, "" once gone
#   _RIL_PATH   the record path this run published
#   _RIL_OWNED  1 while this run published _RIL_PATH and git does not hold it

# The ONE deletion of a published record, shared by the failed-commit branch
# and the cleanup. It deletes only a file THIS run published (_RIL_OWNED=1) that
# is absent from HEAD. A file git already holds is never deleted: another
# operation in the shared checkout may have committed it, before the helper's
# status check (it then returns 2) or after it (its own commit then fails with
# "nothing to commit" and it returns 1), and deleting it would leave a tracked
# deletion.
_ril_delete_if_owned_and_absent() {
    if [[ "${_RIL_OWNED:-0}" != 1 || -z "${_RIL_PATH:-}" ]]; then return 0; fi
    if ! task_git rev-parse --verify --quiet "HEAD:$_RIL_PATH" >/dev/null 2>&1; then
        rm -f -- "$_RIL_PATH"
    fi
    _RIL_OWNED=0
}

_ril_record_cleanup() {
    if [[ -n "${_RIL_TMP:-}" ]]; then rm -f -- "$_RIL_TMP"; fi
    _RIL_TMP=""
    # Nested, so no late die inside the cleanup can pre-empt the lock release
    # that follows it. stdout is dropped (the ledger's result-line channel);
    # stderr is NOT: on a wedged data worktree the cleanup leaves this run's
    # staged entries in place and names them there, and that warning is the
    # only record of what to unstage once the operation is resolved (t2271).
    ( ait_unstage_staged_by_us ) >/dev/null || true
    _ril_delete_if_owned_and_absent
}

# _ril_finish <line> <rc> — end ril_record: clean up on failure, release the
# lock, drop the EXIT trap, print the one result line, and exit the subshell.
#
# Shared by ril_record and the release consumer's move / resume helpers; each
# names its own failure cleanup in _RIL_CLEANUP_FN (default: the writer's).
_ril_finish() {
    local line="$1" rc="$2"
    if [[ "$rc" != 0 ]]; then "${_RIL_CLEANUP_FN:-_ril_record_cleanup}"; fi
    if ! ait_ledger_lock_release; then
        warn "release-issue ledger lock was not released cleanly; the next writer reclaims it once this process has exited"
    fi
    trap - EXIT
    if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi
    printf '%s\n' "$line"
    exit "$rc"
}

# _ril_commit_record <task_id> <path> — commit one record, path-scoped.
#   rc 0  git holds exactly these bytes (committed now or by someone else)
#   rc 1  not committed, and the path is absent from HEAD
#   rc 2  not committed by us, and HEAD holds something else at the path
# Never decided from the helper's own rc alone: neither 1 nor 2 says where the
# bytes are, because a competing commit can produce either.
_ril_commit_record() {
    local task="$1" path="$2" crc=0
    ait_commit_paths_staging_untracked \
        "ait: Record release-pending issue for t${task}" "$path" || crc=$?
    if [[ "$crc" == 0 ]]; then return 0; fi
    if [[ "$(_ril_hit_state "$path")" == committed ]] \
            && task_git diff --quiet HEAD -- "$path" 2>/dev/null; then
        return 0
    fi
    if task_git rev-parse --verify --quiet "HEAD:$path" >/dev/null 2>&1; then
        return 2
    fi
    return 1
}

# _ril_on_existing <task_id> <issue_url> — resolve a record of this name that
# already exists. Finishes ril_record on any hit; returns 0 only when there is
# none. A duplicate needs both:
#   - validity: ril_find read only the identity fields, and a committed record
#     the release consumer would reject is not a duplicate of anything;
#   - persistence: a writer killed between publishing and committing leaves a
#     complete record that nothing has committed, so only the `committed` state
#     is a duplicate.
_ril_on_existing() {
    local task="$1" url="$2" hit hrc=0 kind hpath
    hit="$(ril_find "$task" "$url")" || hrc=$?
    case "$hrc" in
        0) ;;
        1) return 0 ;;
        3) _ril_finish "RELEASE_LEDGER_FAILED:malformed_record:$hit" 1 ;;
        4) _ril_finish "RELEASE_LEDGER_FAILED:hash_collision:$hit" 1 ;;
        *) _ril_finish "RELEASE_LEDGER_FAILED:key_failed" 1 ;;
    esac
    kind="${hit%%:*}"
    hpath="${hit#*:}"
    # Validate before judging persistence. A malformed file is kept as it is
    # (this run did not publish it, so _RIL_OWNED is 0) and reported for a human.
    # Each kind is judged as the whole record it must be.
    if [[ "$kind" == pending ]]; then
        if ! ril_validate_pending_record "$hpath"; then
            _ril_finish "RELEASE_LEDGER_FAILED:malformed_record:$hpath" 1
        fi
    elif ! ril_validate_released_record "$hpath"; then
        _ril_finish "RELEASE_LEDGER_FAILED:malformed_record:$hpath" 1
    fi
    case "$(_ril_hit_state "$hpath")" in
        committed)
            _ril_finish "RELEASE_LEDGER:duplicate:$hpath" 0 ;;
        untracked|staged)
            # A released copy is half of the release consumer's move; committing
            # it alone here would split that move.
            if [[ "$kind" != pending ]]; then
                _ril_finish "RELEASE_LEDGER_FAILED:uncommitted_record:$hpath" 1
            fi
            # The residue of an interrupted writer, validated above. This run did
            # not publish it, so _RIL_OWNED stays 0 and nothing here can delete it.
            if _ril_commit_record "$task" "$hpath"; then
                _ril_finish "RELEASE_LEDGER:recorded:$hpath" 0
            fi
            _ril_finish "RELEASE_LEDGER_FAILED:residue_commit_failed:$hpath" 1 ;;
        modified)
            _ril_finish "RELEASE_LEDGER_FAILED:uncommitted_change:$hpath" 1 ;;
        *)
            _ril_finish "RELEASE_LEDGER_FAILED:persistence_unknown:$hpath" 1 ;;
    esac
}

# ril_record <task_id> <issue_url> <platform> <action> — record one resolved
# issue. The body is a SUBSHELL, so its EXIT trap, lock token and staging list
# can never leak into the caller, and a die in a shared helper ends only this
# subshell. Call it directly, never inside $( ) — redirect stdout to a file to
# capture the line.
#
# stdout, exactly one line:
#   RELEASE_LEDGER:recorded:<path>              rc 0  committed by this run
#   RELEASE_LEDGER:duplicate:<path>             rc 0  already committed
#   RELEASE_LEDGER_FAILED:<reason>[:<path>]     rc 1
# or NOTHING when a shared helper died (rc 1, with the die on stderr).
#
# Runs with errexit off (callers use `|| rc=$?`), so every step checks its own
# status.
ril_record() (
    local task="${1-}" url="${2-}" platform="${3-}" action="${4-}"
    # Never inherit the caller's ledger lock: an early _ril_finish releases
    # "the held lock", which must be one this subshell took (the caller may hold
    # the release_notify run lock in the same globals).
    _AIT_LEDGER_LOCK_DIR=""
    _AIT_LEDGER_LOCK_TOKEN=""
    local name dir path recorded_at crc=0
    # shellcheck disable=SC2030  # subshell-local by design (see above)
    _RIL_TMP=""
    _RIL_PATH=""
    _RIL_OWNED=0

    ril_valid_task_id "$task" || _ril_finish "RELEASE_LEDGER_FAILED:invalid_task_id" 1
    ril_valid_url "$url" || _ril_finish "RELEASE_LEDGER_FAILED:invalid_url" 1
    ril_valid_enum "$platform" github gitlab \
        || _ril_finish "RELEASE_LEDGER_FAILED:invalid_platform" 1
    ril_valid_enum "$action" closed commented closed_silent \
        || _ril_finish "RELEASE_LEDGER_FAILED:invalid_action" 1
    name="$(ril_name "$task" "$url")" || _ril_finish "RELEASE_LEDGER_FAILED:key_failed" 1
    recorded_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    ril_valid_iso_utc "$recorded_at" || _ril_finish "RELEASE_LEDGER_FAILED:clock_failed" 1
    dir="$(ril_root)/pending"
    path="$dir/$name"

    # Held across find + write + commit, so two local writers of one pair can
    # never both decide "absent".
    ait_ledger_lock_acquire release_issues ledger \
        "release-issue ledger lock" "release-issue ledger lock"
    trap '_ril_rc=$?; _ril_record_cleanup; ait_ledger_lock_exit_trap "$_ril_rc"' EXIT
    if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi

    _ril_on_existing "$task" "$url"

    # --- Write, then publish without clobbering ---------------------------
    mkdir -p -- "$dir" 2>/dev/null || _ril_finish "RELEASE_LEDGER_FAILED:write_failed" 1
    _RIL_TMP="$(mktemp "$dir/.${name}.XXXXXX" 2>/dev/null)" || {
        _RIL_TMP=""
        _ril_finish "RELEASE_LEDGER_FAILED:write_failed" 1
    }
    {
        printf 'schema=%s\n' "$RIL_SCHEMA" &&
        printf 'task_id=%s\n' "$task" &&
        printf 'issue_url=%s\n' "$url" &&
        printf 'platform=%s\n' "$platform" &&
        printf 'action=%s\n' "$action" &&
        printf 'recorded_at=%s\n' "$recorded_at"
    } > "$_RIL_TMP" 2>/dev/null || _ril_finish "RELEASE_LEDGER_FAILED:write_failed" 1
    chmod 0644 "$_RIL_TMP" 2>/dev/null || _ril_finish "RELEASE_LEDGER_FAILED:write_failed" 1
    # A hard link publishes atomically and refuses an existing target on every
    # platform; `mv -n` reports a skipped move differently across coreutils
    # versions.
    if ! ln -- "$_RIL_TMP" "$path" 2>/dev/null; then
        if [[ -e "$path" ]]; then
            # Published without the lock (e.g. a sync landed it): resolve it as
            # a hit. _RIL_OWNED is still 0, so it can never be deleted.
            rm -f -- "$_RIL_TMP"
            _RIL_TMP=""
            _ril_on_existing "$task" "$url"
            _ril_finish "RELEASE_LEDGER_FAILED:publish_raced" 1
        fi
        _ril_finish "RELEASE_LEDGER_FAILED:write_failed" 1
    fi
    _RIL_PATH="$path"
    _RIL_OWNED=1
    cmp -s "$_RIL_TMP" "$path" || _ril_finish "RELEASE_LEDGER_FAILED:write_failed" 1
    rm -f -- "$_RIL_TMP"
    _RIL_TMP=""

    # --- Commit ------------------------------------------------------------
    _ril_commit_record "$task" "$path" || crc=$?
    case "$crc" in
        0)
            _RIL_OWNED=0
            _ril_finish "RELEASE_LEDGER:recorded:$path" 0 ;;
        1)
            # Not committed and absent from HEAD: roll back. The only deletion
            # path is the shared rule, never a bare rm.
            _ril_delete_if_owned_and_absent
            if [[ -e "$path" ]] || task_git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
                _ril_finish "RELEASE_LEDGER_FAILED:rollback_failed:$path" 1
            fi
            _ril_finish "RELEASE_LEDGER_FAILED:commit_failed" 1 ;;
        *)
            # HEAD holds something else at this path. Not ours to discard.
            _RIL_OWNED=0
            _ril_finish "RELEASE_LEDGER_FAILED:commit_unverified:$path" 1 ;;
    esac
)

# === Release consumer helpers (t2261_2) =====================================

# --- Data freshness ---------------------------------------------------------
#
# ril_data_freshness — is the local task data PROVABLY up to date with origin?
# Prints one state line; rc 0 only for `fresh`:
#   fresh | behind:<n> | unknown:<no_remote|fetch_error|missing_ref|
#                                count_failed|detached|probe_failed>
# Anything short of a proven count of 0 is not fresh. (desync_state.py is not
# used: its count_ahead_behind returns 0,0 when rev-list fails.) The probe is a
# subshell, so a task_git die on a wedged data worktree ends only the probe,
# and an empty answer reads as unknown, never as fresh.
ril_data_freshness() {
    local out
    out="$(_ril_freshness_probe 2>/dev/null)" || true
    case "$out" in
        fresh)              echo fresh; return 0 ;;
        behind:*|unknown:*) echo "$out"; return 1 ;;
        *)                  echo "unknown:probe_failed"; return 1 ;;
    esac
}

_ril_freshness_probe() (
    local ref n
    local -a g
    if [[ "$(ait_data_mode)" == branch ]]; then
        ref=aitask-data
        g=(task_git)
    else
        g=(git)
        ref="$(git symbolic-ref --quiet --short HEAD 2>/dev/null)" || { echo unknown:detached; exit 0; }
    fi
    "${g[@]}" remote get-url origin >/dev/null 2>&1 || { echo unknown:no_remote; exit 0; }
    # An explicit refspec: a bare `fetch origin <ref>` updates the tracking ref
    # only when remote.origin.fetch maps that branch, and would otherwise leave a
    # stale refs/remotes/origin/<ref> to compare against. This one writes it.
    "${g[@]}" fetch --quiet origin "+refs/heads/$ref:refs/remotes/origin/$ref" >/dev/null 2>&1 \
        || { echo unknown:fetch_error; exit 0; }
    "${g[@]}" rev-parse --verify --quiet "refs/heads/$ref" >/dev/null 2>&1 \
        || { echo unknown:missing_ref; exit 0; }
    "${g[@]}" rev-parse --verify --quiet "refs/remotes/origin/$ref" >/dev/null 2>&1 \
        || { echo unknown:missing_ref; exit 0; }
    n="$("${g[@]}" rev-list --count "refs/heads/$ref..refs/remotes/origin/$ref" 2>/dev/null)" \
        || { echo unknown:count_failed; exit 0; }
    [[ "$n" =~ ^[0123456789]+$ ]] || { echo unknown:count_failed; exit 0; }
    if (( n > 0 )); then echo "behind:$n"; else echo fresh; fi
)

# --- Designated notification machine ---------------------------------------
#
# release_notify_designation — is THIS machine the one that posts? Reads
# `release_notify_host` from project_config.yaml (the shared policy reader) and
# compares it byte-exact with `hostname`. rc 0 only for `designated`:
#   designated:<host> | not_designated:<designated>|<this> | unset |
#   unknown:<policy_unreadable:<reason>|hostname>
# No distributed lock and no failover: reassignment is a deliberate edit.
release_notify_designation() {
    local this
    if ! release_publication_policy_load; then
        echo "unknown:policy_unreadable:$RP_POLICY_ERR"
        return 1
    fi
    if [[ -z "$RP_HOST" ]]; then
        echo unset
        return 1
    fi
    this="$(hostname 2>/dev/null)" || this=""
    if [[ -z "$this" ]]; then
        echo unknown:hostname
        return 1
    fi
    if [[ "$this" == "$RP_HOST" ]]; then
        echo "designated:$RP_HOST"
        return 0
    fi
    echo "not_designated:$RP_HOST|$this"
    return 1
}

# --- Moving a record to released/<tag>/ -------------------------------------
#
# State of one move / resume run (the subshell owns these):
#   _RIL_TMP      a temp file being written, "" once gone
#   _RIL_PATH     the released path THIS run published (_RIL_OWNED=1)
#   _RIL_PENDING  the pending path this run removed
#   _RIL_SAVE     its saved bytes (outside the repository)
#   _RIL_REMOVED  1 while the removal is not known to have been committed
#
# Two crash windows exist between "post" and "committed": after the released
# copy is published (both files on disk), and after the pending file is removed
# (an uncommitted released copy plus a tracked deletion). A process that dies in
# either leaves residue that ril_list_residue finds and ril_resume_move
# completes. The cleanup below covers only failures this process lives through.

# Test seam: kill the move at <point> (after_publish | after_remove). Honoured
# only when the marker file exists in the lock base, the same gating as the
# scoped-commit seam, so an exported variable alone can never arm it.
_ril_move_seam() {
    [[ -n "${_RIL_MOVE_TEST_SEAM:-}" && "$_RIL_MOVE_TEST_SEAM" == "${1-}" ]] || return 0
    local base
    base="$(dirname "$(ait_lock_dir data_index)")" || return 0
    [[ -f "$base/.ril_move_test_seams" ]] || return 0
    warn "release ledger move: TEST SEAM ACTIVE - killing the move at $1"
    kill -KILL "$BASHPID"
}

# Runs only inside the move / resume subshells, which own the _RIL_* state.
# shellcheck disable=SC2031
_ril_move_cleanup() {
    if [[ -n "${_RIL_TMP:-}" ]]; then rm -f -- "$_RIL_TMP"; fi
    _RIL_TMP=""
    # Same isolation and stream rule as _ril_record_cleanup: stderr carries the
    # wedged-worktree warning naming any entries left staged.
    ( ait_unstage_staged_by_us ) >/dev/null || true
    # Restore the pending record only while HEAD still holds it: if the removal
    # was committed after all, restoring would plant an untracked copy.
    if [[ "${_RIL_REMOVED:-0}" == 1 && -n "${_RIL_PENDING:-}" && -n "${_RIL_SAVE:-}" \
            && ! -e "$_RIL_PENDING" ]] \
            && task_git rev-parse --verify --quiet "HEAD:$_RIL_PENDING" >/dev/null 2>&1; then
        cp -- "$_RIL_SAVE" "$_RIL_PENDING" 2>/dev/null || true
    fi
    _RIL_REMOVED=0
    _ril_delete_if_owned_and_absent
    if [[ -n "${_RIL_SAVE:-}" ]]; then rm -f -- "$_RIL_SAVE"; fi
    _RIL_SAVE=""
}

# _ril_move_landed <released> <pending> — the move is in HEAD: the released copy
# is committed with exactly the worktree bytes, and the pending path is gone
# from both HEAD and the worktree. Decided from git state, never from a commit
# helper's return code.
_ril_move_landed() {
    local released="$1" pending="$2"
    [[ "$(_ril_hit_state "$released")" == committed ]] || return 1
    task_git diff --quiet HEAD -- "$released" 2>/dev/null || return 1
    [[ ! -e "$pending" ]] || return 1
    ! task_git rev-parse --verify --quiet "HEAD:$pending" >/dev/null 2>&1
}

# _ril_commit_move <task> <tag> <released> <pending> — one path-scoped commit of
# the released copy and the pending deletion. `commit -o` commits a tracked
# path's deletion without staging (see ait_commit_paths_staging_untracked).
_ril_commit_move() {
    local task="$1" tag="$2" released="$3" pending="$4"
    local -a paths=("$released")
    if task_git ls-files --error-unmatch -- "$pending" >/dev/null 2>&1; then
        paths+=("$pending")
    fi
    ait_commit_paths_staging_untracked \
        "ait: Record release notice for t${task} (${tag})" "${paths[@]}" || true
}

# _ril_save_and_remove_pending <pending> — keep the bytes, then remove it.
_ril_save_and_remove_pending() {
    local pending="$1"
    _RIL_SAVE="$(mktemp "${TMPDIR:-/tmp}/ait_ril_pending_XXXXXX" 2>/dev/null)" \
        || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    cp -- "$pending" "$_RIL_SAVE" 2>/dev/null || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    _RIL_PENDING="$pending"
    rm -f -- "$pending" 2>/dev/null || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    _RIL_REMOVED=1
}

_ril_move_lock() {
    ait_ledger_lock_acquire release_issues ledger \
        "release-issue ledger lock" "release-issue ledger lock"
    trap '_ril_rc=$?; _ril_move_cleanup; ait_ledger_lock_exit_trap "$_ril_rc"' EXIT
    if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi
}

# _ril_resume_locked <released_path> — complete an interrupted move. Runs with
# the ledger lock held, inside a move/resume subshell; always finishes it.
#
# Residue is adopted only when every check passes:
#   1. the released copy is a valid whole record;
#   2. its directory is released/<released_tag>/;
#   3. its filename is ril_name of its own task_id + issue_url;
#   4. HEAD holds the pending record of that name, and its six fields equal the
#      released copy's byte for byte;
#   5. the pending path is either unchanged from HEAD or deleted from the
#      worktree (` D`), and nothing else;
#   6. the released copy is untracked, staged, or committed (never modified).
# Any mismatch leaves every file as it is, for a human.
_ril_resume_locked() {
    local released="$1" name dir tag task url pending rstate pst f a b src
    ril_validate_released_record "$released" \
        || _ril_finish "RIL_MOVE_FAILED:residue_malformed:$released" 1
    name="$(basename -- "$released")"
    dir="$(dirname -- "$released")"
    tag="$(basename -- "$dir")"
    [[ "$dir" == "$(ril_root)/released/$tag" ]] \
        || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
    [[ "$(ril_read "$released" released_tag)" == "$tag" ]] \
        || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
    task="$(ril_read "$released" task_id)" || _ril_finish "RIL_MOVE_FAILED:residue_malformed:$released" 1
    url="$(ril_read "$released" issue_url)" || _ril_finish "RIL_MOVE_FAILED:residue_malformed:$released" 1
    [[ "$(ril_name "$task" "$url" 2>/dev/null)" == "$name" ]] \
        || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
    pending="$(ril_root)/pending/$name"

    rstate="$(_ril_hit_state "$released")"
    case "$rstate" in
        untracked|staged|committed) ;;
        *) _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1 ;;
    esac

    task_git rev-parse --verify --quiet "HEAD:$pending" >/dev/null 2>&1 \
        || _ril_finish "RIL_MOVE_FAILED:unverifiable:$released" 1
    _RIL_TMP="$(mktemp "${TMPDIR:-/tmp}/ait_ril_head_XXXXXX" 2>/dev/null)" \
        || _ril_finish "RIL_MOVE_FAILED:unverifiable:$released" 1
    src="$_RIL_TMP"
    task_git show "HEAD:$pending" > "$src" 2>/dev/null \
        || _ril_finish "RIL_MOVE_FAILED:unverifiable:$released" 1
    ril_validate_pending_record "$src" \
        || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
    for f in "${RIL_PENDING_FIELDS[@]}"; do
        a="$(ril_read "$src" "$f")" || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
        b="$(ril_read "$released" "$f")" || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
        [[ "$a" == "$b" ]] || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
    done
    rm -f -- "$src"
    _RIL_TMP=""

    pst="$(task_git status --porcelain --untracked-files=all -- "$pending" 2>/dev/null)" \
        || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
    if [[ -e "$pending" ]]; then
        [[ -z "$pst" ]] || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
        _ril_save_and_remove_pending "$pending"
    else
        [[ "$pst" == " D $pending" ]] || _ril_finish "RIL_MOVE_FAILED:residue_mismatch:$released" 1
    fi

    _ril_commit_move "$task" "$tag" "$released" "$pending"
    if _ril_move_landed "$released" "$pending"; then
        _RIL_REMOVED=0
        if [[ -n "${_RIL_SAVE:-}" ]]; then rm -f -- "$_RIL_SAVE"; fi
        _RIL_SAVE=""
        _ril_finish "RIL_MOVE_RESUMED:$released" 0
    fi
    _ril_finish "RIL_MOVE_FAILED:commit_failed:$released" 1
}

# ril_move_released <pending_path> <tag> <outcome> <commits_csv> — move one
# committed pending record to released/<tag>/ in ONE path-scoped commit.
# Subshell body, like ril_record: its ledger lock, EXIT trap and staging list
# never touch the caller (whose own run lock lives in the same lock globals).
# Call it directly, never inside $( ).
#
# stdout, exactly one line:
#   RIL_MOVED:<released path>                rc 0
#   RIL_MOVE_RESUMED:<released path>         rc 0  a released copy already
#                                                  existed and was adopted
#   RIL_MOVE_FAILED:<reason>[:<path>]        rc 1
# or NOTHING when a shared helper died or the process was killed (rc != 0).
ril_move_released() (
    local pending="${1-}" tag="${2-}" outcome="${3-}" commits="${4-}"
    # Never inherit the caller's ledger lock: an early _ril_finish releases
    # "the held lock", which must be one this subshell took (the caller may hold
    # the release_notify run lock in the same globals).
    _AIT_LEDGER_LOCK_DIR=""
    _AIT_LEDGER_LOCK_TOKEN=""
    local task url name dir released now f val
    _RIL_TMP=""
    _RIL_PATH=""
    _RIL_OWNED=0
    _RIL_PENDING=""
    _RIL_SAVE=""
    _RIL_REMOVED=0
    _RIL_CLEANUP_FN=_ril_move_cleanup

    ril_valid_tag "$tag" || _ril_finish "RIL_MOVE_FAILED:invalid_tag" 1
    ril_valid_enum "$outcome" posted already_present || _ril_finish "RIL_MOVE_FAILED:invalid_outcome" 1
    ril_valid_commits "$commits" || _ril_finish "RIL_MOVE_FAILED:invalid_commits" 1
    now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    ril_valid_iso_utc "$now" || _ril_finish "RIL_MOVE_FAILED:clock_failed" 1

    _ril_move_lock

    ril_validate_pending_record "$pending" || _ril_finish "RIL_MOVE_FAILED:malformed_pending:$pending" 1
    task="$(ril_read "$pending" task_id)" || _ril_finish "RIL_MOVE_FAILED:malformed_pending:$pending" 1
    url="$(ril_read "$pending" issue_url)" || _ril_finish "RIL_MOVE_FAILED:malformed_pending:$pending" 1
    name="$(ril_name "$task" "$url")" || _ril_finish "RIL_MOVE_FAILED:key_failed" 1
    [[ "$pending" == "$(ril_root)/pending/$name" ]] \
        || _ril_finish "RIL_MOVE_FAILED:path_mismatch:$pending" 1
    dir="$(ril_root)/released/$tag"
    released="$dir/$name"
    # A released copy of this record already exists: an earlier run died after
    # publishing it. Adopt it (or refuse it) instead of publishing over it.
    if [[ -e "$released" || -L "$released" ]]; then
        _ril_resume_locked "$released"
    fi
    [[ "$(_ril_hit_state "$pending")" == committed ]] \
        || _ril_finish "RIL_MOVE_FAILED:pending_not_committed:$pending" 1

    mkdir -p -- "$dir" 2>/dev/null || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    _RIL_TMP="$(mktemp "$dir/.${name}.XXXXXX" 2>/dev/null)" || {
        _RIL_TMP=""
        _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    }
    # Rebuilt field by field from validated reads, so the released copy never
    # inherits a stray byte or a missing final newline.
    : > "$_RIL_TMP" || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    for f in "${RIL_PENDING_FIELDS[@]}"; do
        val="$(ril_read "$pending" "$f")" || _ril_finish "RIL_MOVE_FAILED:malformed_pending:$pending" 1
        printf '%s=%s\n' "$f" "$val" >> "$_RIL_TMP" || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    done
    {
        printf 'released_tag=%s\n' "$tag" &&
        printf 'notified_at=%s\n' "$now" &&
        printf 'outcome=%s\n' "$outcome" &&
        printf 'commits=%s\n' "$commits"
    } >> "$_RIL_TMP" 2>/dev/null || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    chmod 0644 "$_RIL_TMP" 2>/dev/null || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    ril_validate_released_record "$_RIL_TMP" || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    if ! ln -- "$_RIL_TMP" "$released" 2>/dev/null; then
        if [[ -e "$released" ]]; then
            rm -f -- "$_RIL_TMP"
            _RIL_TMP=""
            _ril_resume_locked "$released"
        fi
        _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    fi
    _RIL_PATH="$released"
    _RIL_OWNED=1
    cmp -s "$_RIL_TMP" "$released" || _ril_finish "RIL_MOVE_FAILED:write_failed" 1
    rm -f -- "$_RIL_TMP"
    _RIL_TMP=""
    _ril_move_seam after_publish

    _ril_save_and_remove_pending "$pending"
    _ril_move_seam after_remove

    _ril_commit_move "$task" "$tag" "$released" "$pending"
    if _ril_move_landed "$released" "$pending"; then
        _RIL_OWNED=0
        _RIL_REMOVED=0
        if [[ -n "${_RIL_SAVE:-}" ]]; then rm -f -- "$_RIL_SAVE"; fi
        _RIL_SAVE=""
        _ril_finish "RIL_MOVED:$released" 0
    fi
    _ril_finish "RIL_MOVE_FAILED:commit_failed:$released" 1
)

# ril_resume_move <released_path> — complete one interrupted move found by
# ril_list_residue. Same output contract as ril_move_released, with
# RIL_MOVE_RESUMED on success. Subshell body; call it directly.
ril_resume_move() (
    local released="${1-}"
    # Never inherit the caller's ledger lock: an early _ril_finish releases
    # "the held lock", which must be one this subshell took (the caller may hold
    # the release_notify run lock in the same globals).
    _AIT_LEDGER_LOCK_DIR=""
    _AIT_LEDGER_LOCK_TOKEN=""
    _RIL_TMP=""
    _RIL_PATH=""
    _RIL_OWNED=0
    _RIL_PENDING=""
    _RIL_SAVE=""
    _RIL_REMOVED=0
    _RIL_CLEANUP_FN=_ril_move_cleanup
    case "$released" in
        "$(ril_root)"/released/*/*.rec) ;;
        *) _ril_finish "RIL_MOVE_FAILED:invalid_path:$released" 1 ;;
    esac
    _ril_move_lock
    [[ -e "$released" ]] || _ril_finish "RIL_MOVE_FAILED:not_found:$released" 1
    _ril_resume_locked "$released"
)

# ril_list_residue — the traces of interrupted moves, one per line:
#   released:<path>   a released copy git does not hold yet, or one whose
#                     pending twin HEAD still holds
#   unpaired:<path>   a pending record deleted from the worktree with no
#                     released copy of that name anywhere
# Writes nothing. rc 1 when the git probes failed (the list is then unknown).
ril_list_residue() {
    local root f name out
    root="$(ril_root)"
    for f in "$root"/released/*/*.rec; do
        [[ -e "$f" ]] || continue
        name="$(basename -- "$f")"
        if [[ "$(_ril_hit_state "$f")" != committed ]] \
                || task_git rev-parse --verify --quiet "HEAD:$root/pending/$name" >/dev/null 2>&1; then
            printf 'released:%s\n' "$f"
        fi
    done
    out="$(task_git ls-files --deleted -- "$root/pending/" 2>/dev/null)" || return 1
    while IFS= read -r f; do
        [[ -n "$f" ]] || continue
        name="$(basename -- "$f")"
        if ! compgen -G "$root/released/*/$name" >/dev/null; then
            printf 'unpaired:%s\n' "$f"
        fi
    done <<< "$out"
    return 0
}
