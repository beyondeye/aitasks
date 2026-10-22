#!/usr/bin/env bash
# artifact_fetch_exclusion.sh - keep routine fetches off the gitbranch artifact
# store (t2099; design: aidocs/artifact_storage_lifecycle.md D1(a), §3).
#
# A negative refspec `^refs/heads/<store>` in remote.<r>.fetch makes
# `git fetch <r>` and `git fetch --all --prune` skip the store branch, while the
# gitbranch backend's explicit-refspec fetch keeps working. This file holds the
# git-config MECHANICS only; aitask_artifact.sh `fetch-exclusion` gathers the
# inputs (config, store record, retired list) and calls in.
#
# SHARED MODE (every named remote): add `^refs/heads/<b>` for every desired
# branch, never touching another fetch value. Ownership lives in
# remote.<r>.aitaskExclude (multi-valued branch names): a value is claimed ONLY
# when we add it, so an identical entry the user wrote is never claimed and
# never removed. Owned names that left the desired set are released.
# Ordering is crash-safe: ownership is recorded BEFORE the value is added (an
# interruption leaves owned-but-absent, which the next run adds), and a release
# writes remote.<r>.aitaskReleasing "<branch> <target count>" BEFORE its first
# change, so a retry converges on that count and never removes a second
# occurrence — a copy the user added survives every failure boundary.
#
# DEDICATED MODE (one declared store-only remote, never origin): skipFetchAll
# true and a negative-only fetch set. Reversible through a write-ahead state key
# remote.<r>.aitaskDedicatedState (saved | active | restoring):
#   * backup: remote.<r>.aitaskSavedFetch (multi, original order) plus the
#     SENTINEL remote.<r>.aitaskSavedSkipFetchAll (`unset` | `set:<raw>`).
#     INVARIANT: sentinel present <=> the backup is complete and authoritative.
#     It is written LAST when saving and deleted FIRST when clearing (right after
#     the live restore succeeded), so a partial backup is never read as whole.
#   * the backup is taken exactly once: live settings are not touched before
#     state=saved, so leftovers with no state come only from an interrupted save
#     and are re-taken; in `saved`/`active` it is never re-taken.
#   * remote.<r>.aitaskDedicatedSet records the branches dedicated mode wrote
#     (a write-ahead union during a rewrite). Stay and Leave from `active` run a
#     drift check first: skipFetchAll true and every live value one of those
#     ^refs/heads/<b>. A remote someone edited — a positive mapping or a
#     negative refspec of their own — is refused with recovery commands, never
#     guessed at.
#
# SERIALIZATION: every read-modify-write runs under ONE lock in the git common
# dir (shared by the main checkout, the .aitask-data linked worktree and task
# worktrees), and every piece of state is read only after it is held. The lock
# is a registry_lock; that adapter tracks a single active lock per process, so
# afx_with_lock refuses to nest rather than deadlock or corrupt its bookkeeping.
#
# ERREXIT: afx_with_lock runs its callback as `"$@" || rc=$?`, which suspends
# errexit for the whole call tree. Every fallible step below therefore carries
# its own `|| return 1` (or `|| _afx_fail`).
#
# Requires terminal_compat.sh (die/warn) sourced first.

[[ -n "${_AIT_ARTIFACT_FETCH_EXCLUSION_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_FETCH_EXCLUSION_LOADED=1

_AIT_AFX_DIR_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/registry_lock.sh
source "$_AIT_AFX_DIR_SELF/registry_lock.sh"

AFX_LOCK_TIMEOUT="${AFX_LOCK_TIMEOUT:-10}"
# shellcheck disable=SC2034  # read by aitask_artifact.sh and aitask_sync.sh
AFX_FINGERPRINT_KEY="aitask.fetchExclusionFingerprint"
# Negative refspecs arrived in git 2.29.
_AFX_MIN_MAJOR=2
_AFX_MIN_MINOR=29

_AFX_CHANGED=0   # set by the apply core when any config value changed
_AFX_FAILED=0    # set when a remote was refused or a write failed

# afx_git_version -- print `git --version`'s version field (e.g. 2.56.0).
afx_git_version() {
    git --version 2>/dev/null | sed -n 's/^git version \([0-9][0-9.]*\).*/\1/p' | head -n1
}

# afx_git_supports_negative_refspec -- 0 when git >= 2.29. Integer compare of
# major.minor (no `sort -V`: not portable).
afx_git_supports_negative_refspec() {
    local v maj min
    v="$(afx_git_version)"
    maj="${v%%.*}"; min="${v#*.}"; min="${min%%.*}"
    [[ "$maj" =~ ^[0-9]+$ && "$min" =~ ^[0-9]+$ ]] || return 1
    (( maj > _AFX_MIN_MAJOR || (maj == _AFX_MIN_MAJOR && min >= _AFX_MIN_MINOR) ))
}

# afx_lock_dir -- the lock path in the repository's common git dir (absolute).
afx_lock_dir() {
    local d
    d="$(git rev-parse --git-common-dir 2>/dev/null)" || return 1
    [[ -n "$d" ]] || return 1
    d="$(cd "$d" && pwd -P)" || return 1
    printf '%s/ait-fetch-exclusion.lock' "$d"
}

# afx_with_lock <fn> [args...] -- run <fn> holding the fetch-exclusion lock.
# Prints FETCH_EXCLUSION:BUSY and returns 1 when the lock stays held past
# AFX_LOCK_TIMEOUT. Never nests: a process already holding a registry lock is a
# programming error (the adapter tracks one lock per process).
afx_with_lock() {
    if [[ -n "${_registry_lock_dir:-}" ]]; then
        die "artifact_fetch_exclusion: programming error — called while this process holds the registry lock '${_registry_lock_dir}'; run the fetch exclusion only after that lock is released"
    fi
    local dir rc=0
    dir="$(afx_lock_dir)" || { warn "artifact_fetch_exclusion: cannot resolve the git common dir"; return 1; }
    if ! registry_lock_acquire "$dir" "$AFX_LOCK_TIMEOUT" "fetch-exclusion lock"; then
        echo "FETCH_EXCLUSION:BUSY"
        warn "artifact_fetch_exclusion: another fetch-exclusion update is in progress — retry (lock: $dir)"
        return 1
    fi
    "$@" || rc=$?
    registry_lock_release "$dir"
    return "$rc"
}

# The two source files every apply reads, relative to the data worktree (and,
# with --also-ref, to that ref's tree).
AFX_INPUT_FILES=( aitasks/metadata/project_config.yaml artifacts/gitbranch_store.json )

# afx_input_ids <data_dir> [<ref>] -- one line per source input: the content id
# of each working-tree file ("none" when absent) and, with <ref>, each file's
# blob id there. Raw bytes (--no-filters): the same id the apply computes over
# its snapshot, so equal ids mean equal bytes.
afx_input_ids() {
    local data_dir="$1" ref="${2:-}" f id
    for f in "${AFX_INPUT_FILES[@]}"; do
        if [[ -f "$data_dir/$f" ]]; then id="$(git hash-object --no-filters -- "$data_dir/$f")" || return 1
        else id=none; fi
        printf 'local %s %s\n' "$f" "$id"
        if [[ -n "$ref" ]]; then
            id="$(git rev-parse -q --verify "$ref:$f" 2>/dev/null)" || id=none
            printf 'ref %s %s\n' "$f" "$id"
        fi
    done
}

# afx_fingerprint_from <input-ids> -- the fingerprint of an apply over exactly
# <input-ids> (afx_input_ids output) and the CURRENT remote state: the remote
# list and every remote.* key (so a hand-deleted exclusion re-triggers) and the
# git version. The apply stores this over the inputs it actually CONSUMED.
afx_fingerprint_from() {
    {
        printf '%s\n' "$1"
        echo "remotes:"; git remote || return 1
        echo "config:"; git config --get-regexp '^remote\.' 2>/dev/null || true
        git --version
    } | git hash-object --stdin
}

# afx_fingerprint <data_dir> [<ref>] -- the fingerprint of the LIVE inputs.
# Matching the stored one means exactly these inputs were already applied.
afx_fingerprint() {
    local ids
    ids="$(afx_input_ids "$1" "${2:-}")" || return 1
    afx_fingerprint_from "$ids"
}

# ── small config helpers ─────────────────────────────────────────────────────

_afx_fail() { warn "artifact_fetch_exclusion: $1"; _AFX_FAILED=1; return 1; }

# _afx_get_all <key> -- print every value (nothing when unset).
_afx_get_all() { git config --get-all "$1" 2>/dev/null || true; }

# _afx_unset_all <key> [<value-regex>] -- unset; "no such key" (5) is success.
_afx_unset_all() {
    local rc=0
    git config --unset-all "$@" 2>/dev/null || rc=$?
    (( rc == 0 || rc == 5 ))
}

# _afx_in <needle> <values...> -- exact membership.
_afx_in() {
    local n="$1" v; shift
    for v in "$@"; do [[ "$v" == "$n" ]] && return 0; done
    return 1
}

# _afx_regex_escape <value> -- escape for git config's value regex. Values are
# `^refs/heads/<b>` or bare branch names, whose charset is [A-Za-z0-9._/-]
# (artifact_registry.check_ref_name), so only `^` and `.` are special.
_afx_regex_escape() {
    local s="$1"
    s="${s//./\\.}"
    s="${s//^/\\^}"
    printf '%s' "$s"
}

# _afx_count <key> <value> -- how many times <key> holds exactly <value>.
_afx_count() {
    local key="$1" value="$2" count=0 v
    while IFS= read -r v; do [[ "$v" == "$value" ]] && count=$((count + 1)); done < <(_afx_get_all "$key")
    printf '%s' "$count"
}

# _afx_set_count <key> <value> <target> -- make <key> hold <value> exactly
# <target> times (git 2.29 has no --fixed-value, so a removal is unset-all plus
# re-adds). Idempotent and convergent: an interruption anywhere is repaired by
# running it again with the same target — which is why the release path records
# the target BEFORE the first write (see _afx_release).
_afx_set_count() {
    local key="$1" value="$2" target="$3" count i
    count="$(_afx_count "$key" "$value")"
    if (( count > target )); then
        _afx_unset_all "$key" "^$(_afx_regex_escape "$value")\$" || return 1
        count=0
    fi
    for (( i = count; i < target; i++ )); do git config --add "$key" "$value" || return 1; done
    return 0
}

# _afx_release <remote> <branch> -- release OUR ^refs/heads/<branch>, keeping
# every copy the user added. Write-ahead: remote.<r>.aitaskReleasing records
# "<branch> <target occurrence count>" BEFORE the first change, so a retry after
# a failure at ANY step converges on the same count instead of removing a second
# occurrence. Then ownership, then the marker.
_afx_release() {
    local r="$1" b="$2" v="^refs/heads/$2" m target="" count
    while IFS= read -r m; do
        [[ "${m%% *}" == "$b" ]] && target="${m#* }"
    done < <(_afx_get_all "remote.$r.aitaskReleasing")
    if [[ -z "$target" ]]; then
        count="$(_afx_count "remote.$r.fetch" "$v")"
        target=$(( count > 0 ? count - 1 : 0 ))
        git config --add "remote.$r.aitaskReleasing" "$b $target" \
            || { _afx_fail "remote '$r': could not record the release of $v"; return 1; }
    fi
    [[ "$target" =~ ^[0-9]+$ ]] \
        || { _afx_fail "remote '$r': unreadable release marker for '$b' (remote.$r.aitaskReleasing)"; return 1; }
    _afx_set_count "remote.$r.fetch" "$v" "$target" \
        || { _afx_fail "could not remove $v from remote.$r.fetch"; return 1; }
    _afx_unset_all "remote.$r.aitaskExclude" "^$(_afx_regex_escape "$b")\$" \
        || { _afx_fail "could not release ownership of $v on remote '$r'"; return 1; }
    _afx_unset_all "remote.$r.aitaskReleasing" "^$(_afx_regex_escape "$b") " \
        || { _afx_fail "remote '$r': could not clear the release marker for '$b'"; return 1; }
    echo "RELEASED:$r:$b"; _AFX_CHANGED=1
    return 0
}

# ── shared mode ──────────────────────────────────────────────────────────────

# _afx_shared <remote> <branch>... -- add the desired exclusions, release owned
# ones that left the desired set. Never touches any other fetch value.
_afx_shared() {
    local r="$1"; shift
    local -a want=( "$@" ) fetch owned pending
    local b v m
    # Finish any release a previous run left half-done, whatever its branch is
    # now: the marker, not ownership, is what says it was started.
    mapfile -t pending < <(_afx_get_all "remote.$r.aitaskReleasing")
    for m in "${pending[@]}"; do
        [[ -n "$m" ]] || continue
        _afx_release "$r" "${m%% *}" || return 1
    done
    mapfile -t fetch < <(_afx_get_all "remote.$r.fetch")
    mapfile -t owned < <(_afx_get_all "remote.$r.aitaskExclude")
    for b in "${want[@]}"; do
        v="^refs/heads/$b"
        _afx_in "$v" "${fetch[@]}" && continue
        # Present-but-unowned values were skipped above; absent: claim, then add
        # (an interruption leaves owned-but-absent, which the next run adds).
        if ! _afx_in "$b" "${owned[@]}"; then
            git config --add "remote.$r.aitaskExclude" "$b" \
                || { _afx_fail "could not record ownership of $v on remote '$r'"; return 1; }
            owned+=( "$b" )
        fi
        git config --add "remote.$r.fetch" "$v" \
            || { _afx_fail "could not add $v to remote.$r.fetch"; return 1; }
        echo "EXCLUDED:$r:$b"; _AFX_CHANGED=1
    done
    for b in "${owned[@]}"; do
        _afx_in "$b" "${want[@]}" && continue
        _afx_release "$r" "$b" || return 1
    done
    return 0
}

# ── dedicated mode ───────────────────────────────────────────────────────────

_afx_state() { git config --get "remote.$1.aitaskDedicatedState" 2>/dev/null || true; }
_afx_has_sentinel() { git config --get "remote.$1.aitaskSavedSkipFetchAll" >/dev/null 2>&1; }

# _afx_recovery <remote> -- print the manual recovery commands for a remote
# whose dedicated-mode state cannot be restored automatically.
_afx_recovery() {
    local r="$1" v s
    {
        echo "  Recovery for remote '$r' (inspect 'git config --get-regexp \"^remote\\.$r\\.\"' first):"
        echo "    git config --unset-all remote.$r.fetch"
        while IFS= read -r v; do
            [[ -n "$v" ]] && printf "    git config --add remote.%s.fetch '%s'\n" "$r" "$v"
        done < <(_afx_get_all "remote.$r.aitaskSavedFetch")
        s="$(git config --get "remote.$r.aitaskSavedSkipFetchAll" 2>/dev/null)" || s=""
        case "$s" in
            set:*) printf "    git config remote.%s.skipFetchAll '%s'\n" "$r" "${s#set:}" ;;
            *)     echo "    git config --unset remote.$r.skipFetchAll" ;;
        esac
        echo "    git config --unset-all remote.$r.aitaskSavedFetch; git config --unset-all remote.$r.aitaskDedicatedSet; git config --unset remote.$r.aitaskSavedSkipFetchAll; git config --unset remote.$r.aitaskDedicatedState"
        echo "  Then re-run: ait artifact fetch-exclusion apply"
    } >&2
}

_afx_refuse() {  # _afx_refuse <token> <remote> <why>
    echo "FETCH_EXCLUSION:$1:$2"
    warn "artifact_fetch_exclusion: remote '$2': $3"
    _afx_recovery "$2"
    _AFX_FAILED=1
    return 1
}

# _afx_live_is_ours <remote> -- the drift check: skipFetchAll true and every
# live fetch value is ^refs/heads/<b> for a <b> dedicated mode itself wrote
# (remote.<r>.aitaskDedicatedSet). Anything else — a positive mapping, or a
# negative refspec the user added — is someone's edit, never ours to drop.
_afx_live_is_ours() {
    local r="$1" v skip
    local -a written
    skip="$(git config --get "remote.$r.skipFetchAll" 2>/dev/null)" || return 1
    [[ "$skip" == true ]] || return 1
    mapfile -t written < <(_afx_get_all "remote.$r.aitaskDedicatedSet")
    while IFS= read -r v; do
        [[ "$v" == "^refs/heads/"* ]] || return 1
        _afx_in "${v#^refs/heads/}" "${written[@]}" || return 1
    done < <(_afx_get_all "remote.$r.fetch")
    return 0
}

# _afx_write_dedicated_live <remote> <branch>... -- idempotent live rewrite.
# Write-ahead record: the new branches join aitaskDedicatedSet BEFORE live is
# touched, and stale ones leave it only AFTER, so at every interruption point
# the live set is a subset of the record and the drift check stays truthful.
_afx_write_dedicated_live() {
    local r="$1" b; shift
    local -a written
    mapfile -t written < <(_afx_get_all "remote.$r.aitaskDedicatedSet")
    for b in "$@"; do
        _afx_in "$b" "${written[@]}" || git config --add "remote.$r.aitaskDedicatedSet" "$b" || return 1
    done
    _afx_unset_all "remote.$r.fetch" || return 1
    for b in "$@"; do git config --add "remote.$r.fetch" "^refs/heads/$b" || return 1; done
    git config "remote.$r.skipFetchAll" true || return 1
    _afx_prune_dedicated_set "$r" "$@"
}

# _afx_prune_dedicated_set <remote> <branch>... -- drop record entries that are
# no longer written (only after live holds exactly <branch>...).
_afx_prune_dedicated_set() {
    local r="$1" b; shift
    local -a written
    mapfile -t written < <(_afx_get_all "remote.$r.aitaskDedicatedSet")
    for b in "${written[@]}"; do
        [[ -n "$b" ]] || continue
        _afx_in "$b" "$@" || _afx_unset_all "remote.$r.aitaskDedicatedSet" "^$(_afx_regex_escape "$b")\$" || return 1
    done
    return 0
}

# _afx_live_matches <remote> <branch>... -- live already equals the desired set.
_afx_live_matches() {
    local r="$1"; shift
    local -a live want=()
    local b
    mapfile -t live < <(_afx_get_all "remote.$r.fetch")
    for b in "$@"; do want+=( "^refs/heads/$b" ); done
    (( ${#live[@]} == ${#want[@]} )) || return 1
    for b in "${want[@]}"; do _afx_in "$b" "${live[@]}" || return 1; done
    [[ "$(git config --get "remote.$r.skipFetchAll" 2>/dev/null)" == true ]]
}

# _afx_dedicated_enter <remote> <branch>... -- Enter, resume or Stay.
_afx_dedicated_enter() {
    local r="$1"; shift
    local st v s
    st="$(_afx_state "$r")"
    if [[ "$st" == restoring ]]; then
        # An interrupted Leave, now declared again: finish it, then enter fresh.
        _afx_dedicated_leave "$r" || return 1
        st=""
    fi
    case "$st" in
        "")
            # Live is untouched before state=saved, so leftovers are a partial save.
            _afx_unset_all "remote.$r.aitaskSavedSkipFetchAll" || { _afx_fail "remote '$r': could not clear a partial backup"; return 1; }
            _afx_unset_all "remote.$r.aitaskSavedFetch" || { _afx_fail "remote '$r': could not clear a partial backup"; return 1; }
            _afx_unset_all "remote.$r.aitaskDedicatedSet" || { _afx_fail "remote '$r': could not clear a partial backup"; return 1; }
            while IFS= read -r v; do
                git config --add "remote.$r.aitaskSavedFetch" "$v" \
                    || { _afx_fail "remote '$r': could not save remote.$r.fetch"; return 1; }
            done < <(_afx_get_all "remote.$r.fetch")
            if s="$(git config --get "remote.$r.skipFetchAll" 2>/dev/null)"; then s="set:$s"; else s="unset"; fi
            git config "remote.$r.aitaskSavedSkipFetchAll" "$s" \
                || { _afx_fail "remote '$r': could not save skipFetchAll"; return 1; }
            git config "remote.$r.aitaskDedicatedState" saved \
                || { _afx_fail "remote '$r': could not record the saved state"; return 1; }
            ;&
        saved)
            _afx_has_sentinel "$r" \
                || { _afx_refuse DEDICATED_STATE_INVALID "$r" "state '$(_afx_state "$r")' without a complete backup"; return 1; }
            _afx_write_dedicated_live "$r" "$@" \
                || { _afx_fail "remote '$r': could not write the dedicated fetch set"; return 1; }
            git config "remote.$r.aitaskDedicatedState" active \
                || { _afx_fail "remote '$r': could not record the active state"; return 1; }
            echo "DEDICATED:$r"; _AFX_CHANGED=1
            ;;
        active)
            _afx_has_sentinel "$r" \
                || { _afx_refuse DEDICATED_STATE_INVALID "$r" "state 'active' without a complete backup"; return 1; }
            if _afx_live_matches "$r" "$@"; then
                # An interrupted rewrite may have left stale record entries.
                _afx_prune_dedicated_set "$r" "$@" \
                    || { _afx_fail "remote '$r': could not prune the dedicated-set record"; return 1; }
                return 0
            fi
            _afx_live_is_ours "$r" \
                || { _afx_refuse DEDICATED_DRIFT "$r" "the dedicated fetch settings were edited by hand"; return 1; }
            _afx_write_dedicated_live "$r" "$@" \
                || { _afx_fail "remote '$r': could not rewrite the dedicated fetch set"; return 1; }
            echo "DEDICATED:$r"; _AFX_CHANGED=1
            ;;
        *)  _afx_refuse DEDICATED_STATE_INVALID "$r" "unknown dedicated state '$st'"; return 1 ;;
    esac
    return 0
}

# _afx_dedicated_leave <remote> -- restore the saved settings (resumable).
_afx_dedicated_leave() {
    local r="$1" st v s
    st="$(_afx_state "$r")"
    case "$st" in
        active)
            _afx_has_sentinel "$r" \
                || { _afx_refuse DEDICATED_STATE_INVALID "$r" "state 'active' without a complete backup"; return 1; }
            _afx_live_is_ours "$r" \
                || { _afx_refuse DEDICATED_DRIFT "$r" "the dedicated fetch settings were edited by hand, so the saved ones cannot be restored automatically"; return 1; }
            ;&
        saved)
            # From `saved` the Enter was interrupted: live is partial by
            # definition and the complete backup is authoritative.
            _afx_has_sentinel "$r" \
                || { _afx_refuse DEDICATED_STATE_INVALID "$r" "state '$st' without a complete backup"; return 1; }
            git config "remote.$r.aitaskDedicatedState" restoring \
                || { _afx_fail "remote '$r': could not record the restoring state"; return 1; }
            ;&
        restoring)
            if _afx_has_sentinel "$r"; then
                _afx_unset_all "remote.$r.fetch" || { _afx_fail "remote '$r': could not clear remote.$r.fetch"; return 1; }
                while IFS= read -r v; do
                    git config --add "remote.$r.fetch" "$v" \
                        || { _afx_fail "remote '$r': could not restore remote.$r.fetch"; return 1; }
                done < <(_afx_get_all "remote.$r.aitaskSavedFetch")
                s="$(git config --get "remote.$r.aitaskSavedSkipFetchAll" 2>/dev/null)" || s=""
                case "$s" in
                    set:*) git config "remote.$r.skipFetchAll" "${s#set:}" \
                               || { _afx_fail "remote '$r': could not restore skipFetchAll"; return 1; } ;;
                    unset) _afx_unset_all "remote.$r.skipFetchAll" \
                               || { _afx_fail "remote '$r': could not restore skipFetchAll"; return 1; } ;;
                    *)     _afx_refuse DEDICATED_STATE_INVALID "$r" "unreadable saved skipFetchAll '$s'"; return 1 ;;
                esac
                # The sentinel goes FIRST: from here on the restore is complete.
                _afx_unset_all "remote.$r.aitaskSavedSkipFetchAll" \
                    || { _afx_fail "remote '$r': could not mark the restore complete"; return 1; }
            fi
            _afx_unset_all "remote.$r.aitaskSavedFetch" \
                || { _afx_fail "remote '$r': could not delete the saved fetch values"; return 1; }
            _afx_unset_all "remote.$r.aitaskDedicatedSet" \
                || { _afx_fail "remote '$r': could not delete the dedicated-set record"; return 1; }
            _afx_unset_all "remote.$r.aitaskDedicatedState" \
                || { _afx_fail "remote '$r': could not clear the dedicated state"; return 1; }
            echo "RESTORED:$r"; _AFX_CHANGED=1
            ;;
        "") return 0 ;;
        *)  _afx_refuse DEDICATED_STATE_INVALID "$r" "unknown dedicated state '$st'"; return 1 ;;
    esac
    return 0
}

# ── the apply core (call under afx_with_lock) ────────────────────────────────

# afx_apply_core <declared-remote|""> <dedicated 0|1> <branch>... -- bring every
# named remote to the desired exclusion set. Prints per-remote tokens and a final
# CHANGED/UNCHANGED; returns 1 when any remote was refused or a write failed
# (the other remotes are still processed).
afx_apply_core() {
    local decl="$1" ded="$2"; shift 2
    local -a want=( "$@" ) remotes
    local r target=""
    _AFX_CHANGED=0; _AFX_FAILED=0
    mapfile -t remotes < <(git remote)
    if (( ${#remotes[@]} == 0 )); then
        echo "FETCH_EXCLUSION:NO_REMOTES"
        return 0
    fi
    if [[ "$ded" == 1 ]]; then
        if [[ "$decl" == origin ]]; then
            warn "artifact_fetch_exclusion: remote_dedicated is declared for 'origin', which carries the code and task data — using shared mode there instead"
        elif _afx_in "$decl" "${remotes[@]}"; then
            target="$decl"
        else
            warn "artifact_fetch_exclusion: remote_dedicated is declared, but '$decl' is not a registered git remote — no remote is put in dedicated mode"
        fi
    fi
    for r in "${remotes[@]}"; do
        if [[ -n "$target" && "$r" == "$target" ]]; then
            _afx_dedicated_enter "$r" "${want[@]}" || true
            continue
        fi
        if [[ -n "$(_afx_state "$r")" ]]; then
            _afx_dedicated_leave "$r" || continue
        fi
        _afx_shared "$r" "${want[@]}" || true
    done
    if (( _AFX_CHANGED )); then echo "FETCH_EXCLUSION:CHANGED"; else echo "FETCH_EXCLUSION:UNCHANGED"; fi
    (( _AFX_FAILED == 0 ))
}
