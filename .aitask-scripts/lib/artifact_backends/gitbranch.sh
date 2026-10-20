#!/usr/bin/env bash
# artifact_backends/gitbranch.sh - git-branch backend for the shared artifact
# storage substrate (t1231_1): blobs live on a DEDICATED ORPHAN BRANCH
# (artifacts.backends.gitbranch.branch, default `aitask-artifacts`), written
# with git plumbing only — no worktree, so blobs never materialize in any
# checkout, and they stay off the aitask-data branch that `local` bloats.
#
# Layout on the branch:
#   blobs/<2hex>/<62hex>     content-addressed blob (same sharding as local/dir)
#   .ait-artifact-store      store marker: `store_id: <32 hex>`, `branch:`,
#                            `created_at:` — written ONCE, with the root commit
#   .ait-artifact-retired    migration fence (`store_id`, `retired_to`,
#                            `retired_at`), written once by gitbranch-migrate
#
# R1 — THE REMOTE IS THE STORE OF RECORD. With an `origin`, the authority is
# origin's refs/heads/<branch>; local refs/heads/<branch> is a best-effort
# mirror, never the authority. A write succeeds only once origin accepted it:
# the push is leased on the tip the write was built from
# (--force-with-lease=refs/heads/<b>:<observed>, empty = must not exist), and a
# lease rejection rebuilds on a FRESH tip. Without a remote, refs/heads/<branch>
# is authoritative and the CAS is `git update-ref <new> <old>`; nothing is
# pushed.
#
# Origin's tip is the sha `ls-remote` reports, memoized per process with the
# branch it belongs to (_ARTIFACT_GITBRANCH_MEMO_TIP / _FRESH_FOR; empty =
# confirmed absent) and replaced by the commit this process just published.
# refs/remotes/origin/<b> is updated as bookkeeping but NEVER read as
# authority: a failed prune or update can leave it stale. The memo serves
# READS only (head/get/list). Every CAS iteration refreshes unconditionally: a
# lease rejection means the observed tip was stale by definition, so a
# memoized retry would rebuild the same losing commit until the budget ran
# out. A push whose acknowledgement was lost is recognized when origin's tip
# is, or descends from, our commit — the CAS then reports a change even when
# its final iteration has nothing left to do.
# A read whose refresh fails DIES — a stale "absent" would become blob_pre=false
# and roll back a blob another clone owns.
#
# R2 — ONE PROBE (_artifact_gitbranch_probe), the seam every op, the CLI guard
# and gitbranch-migrate branch on:
#   ABSENT              no store branch anywhere — a write may create the root
#   STORE:<id>          a published store
#   UNPUBLISHED:<id>    remote mode only: origin has no <branch>, but a marked
#                       LOCAL branch does (created before origin existed). A
#                       write publishes it — pushing the local tip even when
#                       the write itself changes nothing.
#   RETIRED:<id>:<to>   the store was migrated to <to>; reads only
#   OCCUPIED            the branch exists with no valid marker — always refused,
#                       never adopted: it is somebody's branch
#
# Expected identity: ARTIFACT_GITBRANCH_STORE_ID (exported by the CLI guard from
# artifacts/gitbranch_store.json) is checked against the probe at the moment a
# store is touched, so a cache hit needs no network.
#
# ERREXIT IS OFF in every caller (with_attach_lock), so every failure path
# carries its own `die`. delete RETURNS non-zero instead (it runs from the
# rollback hooks inside the chained EXIT trap) — its body runs in a subshell.
# Index work never touches the user's index: every tree is built in a
# throwaway GIT_INDEX_FILE.
#
# Sourced by artifact_backend.sh; never executed directly. Requires
# artifact_utils.sh (artifact_shard_path, artifact_sha256,
# artifact_validate_hash) sourced first.

[[ -n "${_AIT_ARTIFACT_BACKEND_GITBRANCH_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_BACKEND_GITBRANCH_LOADED=1

_ARTIFACT_GB_MARKER=".ait-artifact-store"
_ARTIFACT_GB_RETIRED=".ait-artifact-retired"
_ARTIFACT_GB_MAX_ATTEMPTS=5
_ARTIFACT_GITBRANCH_FRESH_FOR=""
# Origin's tip as this process last learned it ("" = confirmed absent): the
# sha ls-remote reported (or a commit this process just published). The store
# is read from THIS, never from refs/remotes/origin/<b> — a tracking ref is
# local bookkeeping that a failed prune or update can leave stale.
_ARTIFACT_GITBRANCH_MEMO_TIP=""
# Exit status of an op whose push outcome is UNKNOWN (the push failed and
# origin could not be re-read, so the server may have applied it).
_ARTIFACT_GB_UNKNOWN=75

# Probe results (set by _artifact_gitbranch_probe; never call it inside $( )).
_AGB_TIP=""         # commit the store is read from ("" = none)
_AGB_EXPECT=""      # value a publish leases against ("" = must not exist)
_AGB_PUBLISHED=1    # 0 = the tip is a local-only store origin does not have
_AGB_STATE=""
_AGB_ID=""
_AGB_CAS_RESULT=""  # NOOP, or the commit a CAS published
_AGB_CAS_BASE=""    # the tip the successful CAS iteration built on
_AGB_UNCERTAIN=0    # 1 while a CAS has a push whose outcome is not yet known

# _agb_die <msg> -- die from the write path. While a CAS holds a push that may
# have landed (_AGB_UNCERTAIN), EVERY failure is an UNKNOWN outcome (exit
# _ARTIFACT_GB_UNKNOWN), never a clean "nothing happened": callers must keep
# reporting the possibly-applied effect.
_agb_die() {
    if (( _AGB_UNCERTAIN )); then
        die_code "$_ARTIFACT_GB_UNKNOWN" "$1 — an earlier push of this write may have landed on '${ARTIFACT_GITBRANCH_BRANCH:-?}'; the outcome is UNKNOWN. Re-run to converge."
    fi
    die "$1"
}

# _artifact_gitbranch_require -- die (in THIS shell) unless a branch is active.
_artifact_gitbranch_require() {
    [[ -n "${ARTIFACT_GITBRANCH_BRANCH:-}" ]] \
        || die "artifact_gitbranch: ARTIFACT_GITBRANCH_BRANCH not set — activate via artifact_registry_activate gitbranch"
}

_artifact_gitbranch_has_remote() { git remote get-url origin >/dev/null 2>&1; }

# Network git never prompts: a credential prompt would hang with the global
# attach lock held. (HTTPS only — an SSH prompt is outside git's control.)
_artifact_gitbranch_net() { GIT_TERMINAL_PROMPT=0 git "$@"; }

# _artifact_gitbranch_refresh <read|cas> -- set _AGB_TIP / _AGB_EXPECT /
# _AGB_PUBLISHED. `read` reuses this process's fetch; `cas` always refetches.
_artifact_gitbranch_refresh() {
    local kind="$1" b="$ARTIFACT_GITBRANCH_BRANCH" out rc=0 sha
    _AGB_TIP=""; _AGB_EXPECT=""; _AGB_PUBLISHED=1
    if ! _artifact_gitbranch_has_remote; then
        _AGB_TIP="$(git rev-parse -q --verify "refs/heads/$b^{commit}" 2>/dev/null)" || _AGB_TIP=""
        _AGB_EXPECT="$_AGB_TIP"
        return 0
    fi
    if [[ "$kind" == cas || "$_ARTIFACT_GITBRANCH_FRESH_FOR" != "$b" ]]; then
        # ls-remote first: a failed fetch cannot tell "no such branch" from
        # "origin unreachable", and only the first may be answered "absent".
        out="$(_artifact_gitbranch_net ls-remote --exit-code origin "refs/heads/$b" 2>&1)" || rc=$?
        case "$rc" in
            0)  sha="$(_artifact_gitbranch_ls_sha "$out")" \
                    || _agb_die "artifact_gitbranch: unexpected ls-remote answer for '$b': ${out%%$'\n'*}"
                # The fetch only brings the objects; the tip is ls-remote's sha.
                # (A branch that advanced in between still contains it.)
                _artifact_gitbranch_net fetch -q origin "+refs/heads/$b:refs/remotes/origin/$b" >/dev/null 2>&1 \
                    || _agb_die "artifact_gitbranch: could not fetch '$b' from origin — the remote is the store of record, so the store cannot be read without it"
                git cat-file -e "$sha^{commit}" 2>/dev/null \
                    || _agb_die "artifact_gitbranch: origin's tip $sha of '$b' is missing after the fetch"
                _ARTIFACT_GITBRANCH_MEMO_TIP="$sha" ;;
            2)  # Best-effort tidy-up only: absence is carried by the memo.
                git update-ref -d "refs/remotes/origin/$b" >/dev/null 2>&1 || true
                _ARTIFACT_GITBRANCH_MEMO_TIP="" ;;
            *)  _agb_die "artifact_gitbranch: cannot reach origin to read branch '$b' (${out##*$'\n'}) — the remote is the store of record; artifact reads and writes on the gitbranch backend need it" ;;
        esac
        _ARTIFACT_GITBRANCH_FRESH_FOR="$b"
    fi
    if [[ -n "$_ARTIFACT_GITBRANCH_MEMO_TIP" ]]; then
        _AGB_TIP="$_ARTIFACT_GITBRANCH_MEMO_TIP"; _AGB_EXPECT="$_ARTIFACT_GITBRANCH_MEMO_TIP"
        return 0
    fi
    _AGB_TIP="$(git rev-parse -q --verify "refs/heads/$b^{commit}" 2>/dev/null)" || _AGB_TIP=""
    [[ -n "$_AGB_TIP" ]] && _AGB_PUBLISHED=0
    return 0
}

# _artifact_gitbranch_ls_sha <ls-remote output> -- the sha of the branch's own
# line (never a stderr line or another ref); fails on anything else.
_artifact_gitbranch_ls_sha() {
    local sha
    sha="$(printf '%s\n' "$1" | awk -v r="refs/heads/$ARTIFACT_GITBRANCH_BRANCH" '$2 == r { print $1; exit }')"
    [[ "$sha" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] || return 1
    printf '%s' "$sha"
}

# _artifact_gitbranch_classify -- derive _AGB_STATE / _AGB_ID from _AGB_TIP.
_artifact_gitbranch_classify() {
    local m to
    _AGB_ID=""
    if [[ -z "$_AGB_TIP" ]]; then _AGB_STATE="ABSENT"; return 0; fi
    m="$(git cat-file blob "$_AGB_TIP:$_ARTIFACT_GB_MARKER" 2>/dev/null)" || m=""
    _AGB_ID="$(printf '%s\n' "$m" | sed -n 's/^store_id: \([0-9a-f]\{32\}\)$/\1/p' | head -n1)"
    if [[ -z "$_AGB_ID" ]]; then _AGB_STATE="OCCUPIED"; return 0; fi
    if git cat-file -e "$_AGB_TIP:$_ARTIFACT_GB_RETIRED" 2>/dev/null; then
        to="$(git cat-file blob "$_AGB_TIP:$_ARTIFACT_GB_RETIRED" 2>/dev/null | sed -n 's/^retired_to: //p' | head -n1)"
        _AGB_STATE="RETIRED:$_AGB_ID:$to"
    elif (( _AGB_PUBLISHED )); then
        _AGB_STATE="STORE:$_AGB_ID"
    else
        _AGB_STATE="UNPUBLISHED:$_AGB_ID"
    fi
    return 0
}

# _artifact_gitbranch_probe <read|cas> -- refresh + classify (sets _AGB_*).
_artifact_gitbranch_probe() {
    _artifact_gitbranch_require
    _artifact_gitbranch_refresh "$1"
    _artifact_gitbranch_classify
}

# _artifact_gitbranch_check <read|write> -- refuse what the probe forbids.
_artifact_gitbranch_check() {
    local kind="$1" b="$ARTIFACT_GITBRANCH_BRANCH" want="${ARTIFACT_GITBRANCH_STORE_ID:-}"
    case "$_AGB_STATE" in
        OCCUPIED)
            _agb_die "artifacts.backends.gitbranch.branch is '$b', but branch '$b' already exists and is not an aitask artifact store (no $_ARTIFACT_GB_MARKER marker at its tip). Refusing to write artifact commits onto an existing branch — pick an unused branch name." ;;
        ABSENT)
            [[ -z "$want" ]] \
                || _agb_die "artifact_gitbranch: this project's artifact store $want is missing from branch '$b' (deleted on origin?) — push the branch back from a clone that still has it; the store is never re-created empty"
            return 0 ;;
    esac
    [[ -z "$want" || "$_AGB_ID" == "$want" ]] \
        || _agb_die "artifact_gitbranch: branch '$b' holds artifact store $_AGB_ID, but this project's store is $want (artifacts/gitbranch_store.json) — refusing to mix two stores"
    if [[ "$kind" == write && "$_AGB_STATE" == RETIRED:* ]]; then
        _agb_die "artifact_gitbranch: artifact store $_AGB_ID was migrated from '$b' to '${_AGB_STATE##*:}' — pull the data branch and set artifacts.backends.gitbranch.branch: ${_AGB_STATE##*:}"
    fi
    return 0
}

# _artifact_gitbranch_build <base|""> <seed|""> <msg> -- build one commit in a
# throwaway index and print its sha, or NOOP when the tree did not change.
# The index starts from <seed> (default <base>; empty = an empty tree). Stdin
# carries the edits: `100644 blob <oid>\t<path>` adds, `rm\t<path>` removes.
_artifact_gitbranch_build() {
    local base="$1" seed="${2:-$1}" msg="$3"
    (
        tmpd="$(mktemp -d "${TMPDIR:-/tmp}/ait-gitbranch.XXXXXX")" || exit 1
        # shellcheck disable=SC2064  # expand now: tmpd is this subshell's
        trap "rm -rf '$tmpd'" EXIT   # archive-sweep: subshell-local
        # A NONEXISTENT path: git rejects a zero-byte index file.
        export GIT_INDEX_FILE="$tmpd/index"
        if [[ -n "$seed" ]]; then git read-tree "$seed" || exit 1
        else git read-tree --empty || exit 1; fi
        adds=""; rms=()
        while IFS= read -r line; do
            case "$line" in
                rm$'\t'*) rms+=( "${line#rm$'\t'}" ) ;;
                ?*)       adds+="$line"$'\n' ;;
            esac
        done
        if [[ -n "$adds" ]]; then printf '%s' "$adds" | git update-index --add --index-info || exit 1; fi
        if (( ${#rms[@]} )); then git update-index --force-remove -- "${rms[@]}" || exit 1; fi
        tree="$(git write-tree)" || exit 1
        if [[ -n "$base" ]]; then
            [[ "$tree" == "$(git rev-parse "$base^{tree}")" ]] && { echo NOOP; exit 0; }
            printf '%s\n' "$msg" | git commit-tree "$tree" -p "$base" || exit 1
        else
            printf '%s\n' "$msg" | git commit-tree "$tree" || exit 1
        fi
    )
}

# _artifact_gitbranch_mirror <commit> -- best-effort local refs/heads update:
# only when the local ref is absent or still at the tip the write built on, so
# a diverged local branch is never overwritten. Never fails the op.
_artifact_gitbranch_mirror() {
    local c="$1" b="$ARTIFACT_GITBRANCH_BRANCH" cur
    cur="$(git rev-parse -q --verify "refs/heads/$b" 2>/dev/null)" || cur=""
    if [[ -z "$cur" ]]; then
        git update-ref "refs/heads/$b" "$c" "" >/dev/null 2>&1 || true
    elif [[ "$cur" == "$_AGB_TIP" ]]; then
        git update-ref "refs/heads/$b" "$c" "$cur" >/dev/null 2>&1 || true
    fi
    return 0
}

# _artifact_gitbranch_published <commit> -- bookkeeping after origin accepted
# <commit>: the memo (so this process's post-put head sees it without a fetch),
# then best-effort tracking ref and mirror — neither is ever read as authority.
_artifact_gitbranch_published() {
    _ARTIFACT_GITBRANCH_MEMO_TIP="$1"
    _ARTIFACT_GITBRANCH_FRESH_FOR="$ARTIFACT_GITBRANCH_BRANCH"
    git update-ref "refs/remotes/origin/$ARTIFACT_GITBRANCH_BRANCH" "$1" >/dev/null 2>&1 || true
    _artifact_gitbranch_mirror "$1"
}

# _artifact_gitbranch_publish <commit> -- 0 published, 1 lease lost (retry);
# dies on a hard failure. A failed push is classified by re-reading origin, not
# by parsing git's stderr: at our commit -> applied (ack lost); moved elsewhere
# -> lost the race; unmoved -> origin refused; unreadable -> UNKNOWN (exit
# _ARTIFACT_GB_UNKNOWN), never "nothing was published".
_artifact_gitbranch_publish() {
    local c="$1" b="$ARTIFACT_GITBRANCH_BRANCH" err rc=0 lsout lrc=0 now
    if ! _artifact_gitbranch_has_remote; then
        git update-ref "refs/heads/$b" "$c" "$_AGB_EXPECT" >/dev/null 2>&1 && return 0
        return 1
    fi
    err="$(_artifact_gitbranch_net push -q --force-with-lease="refs/heads/$b:$_AGB_EXPECT" origin "$c:refs/heads/$b" 2>&1)" || rc=$?
    if (( rc == 0 )); then
        _artifact_gitbranch_published "$c"
        return 0
    fi
    lsout="$(_artifact_gitbranch_net ls-remote --exit-code origin "refs/heads/$b" 2>&1)" || lrc=$?
    if (( lrc == 0 )); then
        now="$(_artifact_gitbranch_ls_sha "$lsout")" || lrc=1
    fi
    case "$lrc" in
        0) ;;
        2) now="" ;;
        *) die_code "$_ARTIFACT_GB_UNKNOWN" "artifact_gitbranch: the push of $c to '$b' failed and origin cannot be re-read (git: ${err%%$'\n'*}) — the outcome is UNKNOWN: origin may have applied it. Re-run once origin is reachable." ;;
    esac
    # The server applied our push and only the acknowledgement was lost.
    if [[ "$now" == "$c" ]]; then
        _artifact_gitbranch_published "$c"
        return 0
    fi
    [[ "$now" != "$_AGB_EXPECT" ]] && return 1
    _agb_die "artifact_gitbranch: origin refused the push to '$b' (git: ${err%%$'\n'*}) — nothing was published"
}

# _artifact_gitbranch_missing_entries <src> <dst> -- print `ls-tree` lines for
# every blobs/ entry of <src> that <dst> lacks. Both listings go through files,
# never an argument or environment string: a store of a few thousand blobs
# exceeds the kernel's per-string exec limit. Every step is checked.
_artifact_gitbranch_missing_entries() {
    (
        tmpd="$(mktemp -d "${TMPDIR:-/tmp}/ait-gitbranch-diff.XXXXXX")" || exit 1
        # shellcheck disable=SC2064  # expand now: tmpd is this subshell's
        trap "rm -rf '$tmpd'" EXIT   # archive-sweep: subshell-local
        git ls-tree -r --name-only "$2" -- blobs/ > "$tmpd/have" || exit 1
        git ls-tree -r "$1" -- blobs/ > "$tmpd/src" || exit 1
        awk -F'\t' 'FILENAME == ARGV[1] { have[$0] = 1; next } NF >= 2 && !($2 in have)' \
            "$tmpd/have" "$tmpd/src" || exit 1
    )
}

# _artifact_gitbranch_mint_marker -- write a fresh marker blob, print its oid.
_artifact_gitbranch_mint_marker() {
    local id
    id="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')" || return 1
    [[ "$id" =~ ^[0-9a-f]{32}$ ]] || return 1
    printf 'store_id: %s\nbranch: %s\ncreated_at: %s\n' "$id" "$ARTIFACT_GITBRANCH_BRANCH" "$(date '+%Y-%m-%d %H:%M')" \
        | git hash-object -w --stdin
}

# _artifact_gitbranch_cas_noop <applied|""> -- end a CAS iteration that had
# nothing left to do. When an earlier push of ours landed (<applied>), the CAS
# DID change the branch: report the current tip, not NOOP.
_artifact_gitbranch_cas_noop() {
    _AGB_UNCERTAIN=0
    _AGB_CAS_BASE="$_AGB_TIP"
    if [[ -n "$1" ]]; then _AGB_CAS_RESULT="$_AGB_TIP"; else _AGB_CAS_RESULT="NOOP"; fi
    return 0
}

# _artifact_gitbranch_cas <op> [args] -- the write loop: fresh refresh, probe,
# check, build, publish; retries only a lost lease. Sets _AGB_CAS_RESULT
# (NOOP or the published commit) and _AGB_CAS_BASE. A NOOP ends the loop
# WITHOUT pushing only for a published store: an UNPUBLISHED tip is pushed
# as-is, so an unchanged local-only store can never yield a write success.
#   put <oid> <relpath>        add one blob (a root also gets a fresh marker)
#   delete <relpath>           remove one blob
#   init                       a marker-only root
#   migrate <src> <store-id>   union of <src>'s blobs/ (root = <src>'s tree)
#   retire <to>                add the migration fence
_artifact_gitbranch_cas() {
    local op="$1"; shift
    local b="$ARTIFACT_GITBRANCH_BRANCH" attempt=0 lines seed msg c prc moid have p
    # Commits of ours whose push failed while origin moved on: each may still
    # have landed (lost acknowledgement), possibly with another writer's commit
    # on top. After every fresh refresh, one that is now an ancestor of the tip
    # DID land — so a later NOOP iteration still reports a change.
    local pending=() applied="" arc
    _AGB_UNCERTAIN=0
    while (( attempt < _ARTIFACT_GB_MAX_ATTEMPTS )); do
        attempt=$((attempt + 1))
        _artifact_gitbranch_refresh cas
        if [[ -n "$_AGB_TIP" ]]; then
            for p in ${pending[@]+"${pending[@]}"}; do
                # 0 = landed, 1 = did not; anything else is NOT an answer.
                arc=0; git merge-base --is-ancestor "$p" "$_AGB_TIP" 2>/dev/null || arc=$?
                case "$arc" in
                    0) applied="$p" ;;
                    1) ;;
                    *) _agb_die "artifact_gitbranch: could not tell whether $p landed on '$b' (git merge-base exit $arc)" ;;
                esac
            done
        fi
        _artifact_gitbranch_classify
        if [[ "$op" == retire ]]; then _artifact_gitbranch_check read
        else _artifact_gitbranch_check write; fi
        lines=""; seed=""
        case "$op" in
            put)
                msg="ait: Store artifact blob ${2#blobs/}"
                if [[ -n "$_AGB_TIP" ]]; then
                    # Byte-exact, not presence: an entry whose object differs
                    # from the verified one is corruption, repaired here.
                    have="$(git rev-parse -q --verify "$_AGB_TIP:$2" 2>/dev/null)" || have=""
                    if [[ "$have" != "$1" ]]; then
                        lines="100644 blob $1"$'\t'"$2"$'\n'
                        [[ -z "$have" ]] || { msg="ait: Repair corrupt artifact blob ${2#blobs/}"
                            warn "artifact_gitbranch_put: corrupt store entry for ${2#blobs/} on '$b' — repairing with verified bytes"; }
                    fi
                else
                    moid="$(_artifact_gitbranch_mint_marker)" || _agb_die "artifact_gitbranch: could not write the store marker"
                    lines="100644 blob $1"$'\t'"$2"$'\n'"100644 blob $moid"$'\t'"$_ARTIFACT_GB_MARKER"$'\n'
                    msg="ait: Initialize artifact store on $b"
                fi ;;
            delete)
                if [[ -z "$_AGB_TIP" ]]; then _artifact_gitbranch_cas_noop "$applied"; return 0; fi
                msg="ait: Remove artifact blob ${1#blobs/}"
                lines="rm"$'\t'"$1"$'\n' ;;
            init)
                msg="ait: Initialize artifact store on $b"
                if [[ -z "$_AGB_TIP" ]]; then
                    moid="$(_artifact_gitbranch_mint_marker)" || _agb_die "artifact_gitbranch: could not write the store marker"
                    lines="100644 blob $moid"$'\t'"$_ARTIFACT_GB_MARKER"$'\n'
                fi ;;
            migrate)
                [[ -z "$_AGB_TIP" || "$_AGB_ID" == "$2" ]] \
                    || _agb_die "artifact_gitbranch: branch '$b' now holds artifact store $_AGB_ID, not $2 — refusing to merge two stores"
                msg="ait: Migrate artifact store $2 blobs"
                if [[ -z "$_AGB_TIP" ]]; then
                    seed="$1"; lines="rm"$'\t'"$_ARTIFACT_GB_RETIRED"$'\n'
                else
                    lines="$(_artifact_gitbranch_missing_entries "$1" "$_AGB_TIP")" \
                        || _agb_die "artifact_gitbranch: could not compare '$b' with the migration source $1"
                    [[ -z "$lines" ]] || lines+=$'\n'
                fi ;;
            retire)
                case "$_AGB_STATE" in
                    RETIRED:*)
                        [[ "${_AGB_STATE##*:}" == "$1" ]] \
                            || _agb_die "artifact_gitbranch: branch '$b' is already retired to '${_AGB_STATE##*:}', not '$1'"
                        _artifact_gitbranch_cas_noop "$applied"; return 0 ;;
                    ABSENT) _agb_die "artifact_gitbranch: there is no artifact store on '$b' to retire" ;;
                esac
                # An UNPUBLISHED store is fenced and published in one push.
                moid="$(printf 'store_id: %s\nretired_to: %s\nretired_at: %s\n' "$_AGB_ID" "$1" "$(date '+%Y-%m-%d %H:%M')" \
                    | git hash-object -w --stdin)" || _agb_die "artifact_gitbranch: could not write the migration fence"
                msg="ait: Retire artifact store $_AGB_ID (migrated to $1)"
                lines="100644 blob $moid"$'\t'"$_ARTIFACT_GB_RETIRED"$'\n' ;;
            *) _agb_die "artifact_gitbranch: internal: unknown CAS op '$op'" ;;
        esac
        c="$(printf '%s' "$lines" | _artifact_gitbranch_build "$_AGB_TIP" "$seed" "$msg")" \
            || _agb_die "artifact_gitbranch: could not build the commit for '$b'"
        if [[ "$c" == NOOP ]]; then
            if (( _AGB_PUBLISHED )); then _artifact_gitbranch_cas_noop "$applied"; return 0; fi
            c="$_AGB_TIP"
        fi
        prc=0
        _artifact_gitbranch_publish "$c" || prc=$?
        if (( prc == 0 )); then _AGB_UNCERTAIN=0; _AGB_CAS_RESULT="$c"; _AGB_CAS_BASE="$_AGB_TIP"; return 0; fi
        pending+=( "$c" ); _AGB_UNCERTAIN=1
        sleep "0.$((RANDOM % 4 + 1))"
    done
    # Exhausted. If any attempt may have landed, the outcome is UNKNOWN, not
    # "nothing published".
    if [[ -n "$applied" ]] || (( ${#pending[@]} )); then
        die_code "$_ARTIFACT_GB_UNKNOWN" "artifact_gitbranch: could not settle '$b' after $_ARTIFACT_GB_MAX_ATTEMPTS attempts (concurrent writers?) — an earlier push may have landed; the outcome is UNKNOWN. Re-run to converge."
    fi
    _agb_die "artifact_gitbranch: could not publish to '$b' after $_ARTIFACT_GB_MAX_ATTEMPTS attempts (concurrent writers?) — nothing was published"
}

# ── Contract ops ──────────────────────────────────────────────────────────────

# artifact_gitbranch_head <hash> -- exit 0 iff the blob is on the store's tip.
# Dies (never answers "absent") when the store cannot be read: callers turn
# "absent" into blob_pre=false, and their rollback then deletes the blob.
artifact_gitbranch_head() {
    local rel
    rel="$(artifact_shard_path "$1")" || die "artifact_gitbranch_head: invalid hash: $1"
    _artifact_gitbranch_probe read
    _artifact_gitbranch_check read
    [[ -n "$_AGB_TIP" ]] || return 1
    git cat-file -e "$_AGB_TIP:blobs/$rel" 2>/dev/null
}

# artifact_gitbranch_get <hash> <dest> -- write the blob to <dest> ("-" = stdout).
artifact_gitbranch_get() {
    local hash="$1" dest="$2" rel
    [[ -n "$dest" ]] || die "artifact_gitbranch_get: empty destination for $hash"
    rel="$(artifact_shard_path "$hash")" || die "artifact_gitbranch_get: invalid hash: $hash"
    _artifact_gitbranch_probe read
    _artifact_gitbranch_check read
    if [[ -z "$_AGB_TIP" ]] || ! git cat-file -e "$_AGB_TIP:blobs/$rel" 2>/dev/null; then
        die "artifact_gitbranch_get: blob not present on branch '$ARTIFACT_GITBRANCH_BRANCH': $hash"
    fi
    if [[ "$dest" == "-" ]]; then
        git cat-file blob "$_AGB_TIP:blobs/$rel" || die "artifact_gitbranch_get: could not read $hash"
    else
        git cat-file blob "$_AGB_TIP:blobs/$rel" > "$dest" || die "artifact_gitbranch_get: could not write $hash to $dest"
    fi
}

# artifact_gitbranch_put <hash> <file> -- store the blob; returns only once the
# store of record holds exactly these bytes. Idempotent (no commit) for a
# PUBLISHED store already carrying the identical object; an unpublished store
# is published even then, and a wrong-bytes entry is repaired.
artifact_gitbranch_put() {
    local hash="$1" src="$2" rel oid tmp
    [[ -f "$src" ]] || die "artifact_gitbranch_put: not a file: $src"
    rel="$(artifact_shard_path "$hash")" || die "artifact_gitbranch_put: invalid hash: $hash"
    _artifact_gitbranch_probe read
    _artifact_gitbranch_check write
    oid="$(git hash-object -w -- "$src")" || die "artifact_gitbranch_put: could not write the blob object for $hash"
    # Verify the STAGED bytes (the object that will be published), as dir.sh
    # verifies its temp before installing: the source may change under us.
    tmp="$(mktemp "${TMPDIR:-/tmp}/ait-gitbranch-put.XXXXXX")" || die "artifact_gitbranch_put: mktemp failed"
    if ! git cat-file blob "$oid" > "$tmp" || [[ "$(artifact_sha256 "$tmp")" != "$hash" ]]; then
        rm -f "$tmp"
        die "artifact_gitbranch_put: staged bytes for $hash failed verification — nothing published"
    fi
    rm -f "$tmp"
    # Idempotent only when the published entry IS these bytes (same object id),
    # never on mere presence: a wrong-bytes entry goes through the CAS repair.
    if [[ "$_AGB_STATE" == STORE:* ]] \
            && [[ "$(git rev-parse -q --verify "$_AGB_TIP:blobs/$rel" 2>/dev/null)" == "$oid" ]]; then
        return 0
    fi
    _artifact_gitbranch_cas put "$oid" "blobs/$rel"
}

# artifact_gitbranch_delete <hash> -- remove the blob (no-op if absent). RETURNS
# non-zero, never dies: it runs from the rollback hooks in the EXIT trap.
artifact_gitbranch_delete() {
    artifact_validate_hash "$1" || { warn "artifact_gitbranch_delete: invalid hash: '$1'"; return 1; }
    ( _artifact_gitbranch_delete_body "$1" ) || return 1
}

_artifact_gitbranch_delete_body() {
    local rel
    rel="$(artifact_shard_path "$1")" || exit 1
    _artifact_gitbranch_require
    _artifact_gitbranch_cas delete "blobs/$rel"
}

# artifact_gitbranch_list -- print every stored hash (sha256:<hex>).
artifact_gitbranch_list() {
    local out
    _artifact_gitbranch_probe read
    _artifact_gitbranch_check read
    [[ -n "$_AGB_TIP" ]] || return 0
    out="$(git ls-tree -r --name-only "$_AGB_TIP" -- blobs/)" \
        || die "artifact_gitbranch_list: could not list branch '$ARTIFACT_GITBRANCH_BRANCH'"
    printf '%s\n' "$out" | sed -n 's|^blobs/\([0-9a-f]\{2\}\)/\([0-9a-f]\{62\}\)$|sha256:\1\2|p'
}

# artifact_gitbranch_init -- create (or publish) the store eagerly; optional,
# since the first write creates it too. Prints INITIALIZED:branch <b> or
# ALREADY_INITIALIZED:branch <b>.
artifact_gitbranch_init() {
    _artifact_gitbranch_probe read
    _artifact_gitbranch_check write
    if [[ "$_AGB_STATE" != STORE:* ]]; then
        _artifact_gitbranch_cas init
        if [[ "$_AGB_CAS_RESULT" != NOOP ]]; then
            printf 'INITIALIZED:branch %s\n' "$ARTIFACT_GITBRANCH_BRANCH"
            return 0
        fi
    fi
    printf 'ALREADY_INITIALIZED:branch %s\n' "$ARTIFACT_GITBRANCH_BRANCH"
}

# ── Identity / migration helpers (aitask_artifact.sh only) ───────────────────

# artifact_gitbranch_store_id -- print the active branch's store id (empty when
# it has no valid marker).
artifact_gitbranch_store_id() {
    _artifact_gitbranch_probe read
    printf '%s\n' "$_AGB_ID"
}

# artifact_gitbranch_probe_state -- FRESH probe; print "<state>\t<tip>".
artifact_gitbranch_probe_state() {
    _artifact_gitbranch_probe cas
    printf '%s\t%s\n' "$_AGB_STATE" "$_AGB_TIP"
}

# artifact_gitbranch_migrate_from <src-commit> <store-id> -- copy every blob of
# <src-commit> onto the active branch, which must be ABSENT or hold <store-id>
# (re-checked on every CAS iteration). Prints "<tip> <changed:0|1>".
artifact_gitbranch_migrate_from() {
    _artifact_gitbranch_require
    _artifact_gitbranch_cas migrate "$1" "$2"
    if [[ "$_AGB_CAS_RESULT" == NOOP ]]; then printf '%s 0\n' "$_AGB_CAS_BASE"
    else printf '%s 1\n' "$_AGB_CAS_RESULT"; fi
}

# artifact_gitbranch_retire <to> -- fence the active branch: from now on every
# write to it dies (R2 RETIRED). Prints "<fenced-tip> <changed:0|1>". The fence
# is leased on a freshly fetched tip, so the fenced tip holds every blob anyone
# managed to publish to the branch.
artifact_gitbranch_retire() {
    _artifact_gitbranch_require
    _artifact_gitbranch_cas retire "$1"
    if [[ "$_AGB_CAS_RESULT" == NOOP ]]; then printf '%s 0\n' "$_AGB_CAS_BASE"
    else printf '%s 1\n' "$_AGB_CAS_RESULT"; fi
}
