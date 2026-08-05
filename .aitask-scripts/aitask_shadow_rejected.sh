#!/usr/bin/env bash
# aitask_shadow_rejected.sh - Locked writer/reader for the per-task shadow
# concern-rejection store (t1427_1).
#
# The store lives at `${AITASK_SHADOW_DIR:-.aitask-shadow}/<task_id>/rejected.md`
# — bare task id (no `t` prefix, mirroring `.aitask-gates/`), repo-root-relative,
# git-ignored, never committed, created lazily by the writer. It records concerns
# the user rejected in the monitor/minimonitor concern picker so the shadow agent
# can suppress them on the next review round.
#
# File layout — markdown, because `list` output is fed back to the shadow as
# prompt context:
#
#   <!-- next_id: 3 -->
#
#   ### r1 | 2026-08-05T14:02:11Z | producer: plan-challenge
#   - [high | Step 7 guard] The guard double-commits when the lock was held.
#
# ENTRY IDS NEVER REPEAT. Line 1 carries a never-decreasing high-water mark;
# `add` assigns from it and advances it, `remove` preserves it verbatim and never
# lowers it. Deriving the next id from `max(existing)+1` instead would re-issue
# an id whenever the highest entry was removed, and a stale `remove` from a
# second TUI session would then un-reject a *different* concern — the picker
# pre-fetches its view and deliberately does no staleness handling. The counter
# lives inside the store file (not a sibling) so the id reservation and the entry
# write are ONE atomic render; a sibling file could be lost independently or
# leave a crash window between the two writes. When the header is absent or
# corrupt the value bootstraps from `max(entry id)+1`; that degraded path is
# self-healing, but the header is the authority whenever present.
#
# A store emptied by `remove` keeps its header rather than being deleted: it is
# therefore never zero-byte (`ait_atomic_render` refuses a zero-byte result) and
# the high-water mark survives. `list` decides emptiness on "no `### r` entries",
# not on file absence.
#
# CONCURRENCY. `ait monitor` and `ait minimonitor` can both be open against the
# same followed agent, so every mutation is a read-modify-write on a shared file.
# `lib/atomic_write.sh` gives readers a whole-old-or-whole-new view but
# explicitly does NOT serialize an RMW, so each mutation additionally holds the
# `lib/registry_lock.sh` mutex (mkdir-based, owner-token release, steals only a
# provably dead PID) and lands through `ait_atomic_render`. Never an open-coded
# mktemp-then-mv. `list` takes no lock — the atomic rename is enough.
#
# `task_utils.sh` is deliberately NOT sourced: it pulls in lib/archive_utils.sh,
# which claims the process-wide EXIT trap at source time, and registry_lock's own
# EXIT trap would clobber it. Nothing here needs it.
#
# The own-root guard protects `prune`. `add`/`remove` write through
# `ait_atomic_resolve`, which follows a file symlink chain by design; the store
# is local-only and git-ignored, so a symlinked `rejected.md` is out of scope.
#
# Callers: the monitor TUIs (rejection persistence / un-reject) and the shadow
# skill's concern producers (`list` before emitting a concern block).
#
# Verbs:
#   add <task_id> [--producer <name>]
#                       - Canonical `- [priority | region] body` marker lines on
#                         stdin, one per line. Prints ADDED:<n>.
#   list <task_id> [--machine]
#                       - Default: the store body, header stripped. --machine:
#                         REJECTED:<id>|<ts>|<producer>|<marker line> per entry
#                         (marker LAST — it contains `|`; split('|', 3)).
#                         NO_REJECTIONS when empty or missing.
#   remove <task_id> <id>...
#                       - Drop entries. Prints REMOVED:<csv> / NOT_FOUND:<csv>.
#                         TUI-invoked machinery, not a user-facing CLI.
#   prune <task_id>     - Delete the task's store dir. Prints PRUNED:<task_id> or
#                         PRUNED:absent. Called at archival, best-effort.
#
# Exit codes:
#   0  success
#   2  usage error / malformed task id / no valid input
#   3  LOCK_BUSY   - another process holds the mutex; NOTHING was written
#   4  ERROR       - the store could not be written; NOTHING was changed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/registry_lock.sh
source "$SCRIPT_DIR/lib/registry_lock.sh"
# shellcheck source=lib/atomic_write.sh
source "$SCRIPT_DIR/lib/atomic_write.sh"

SHADOW_DIR="${AITASK_SHADOW_DIR:-.aitask-shadow}"

# Mutation timeout is generous; prune's is short on purpose — it runs inside
# aitask_archive.sh, and archival must never stall behind a contended store.
MUTATE_LOCK_TIMEOUT=10
PRUNE_LOCK_TIMEOUT=2

# Populated by resolve_task_id / store_paths_for.
TASK_ID=""
STORE_DIR=""
STORE_FILE=""
LOCK_DIR=""

usage() {
    cat >&2 <<'EOF'
Usage: aitask_shadow_rejected.sh add <task_id> [--producer <name>]   (markers on stdin)
       aitask_shadow_rejected.sh list <task_id> [--machine]
       aitask_shadow_rejected.sh remove <task_id> <id>...
       aitask_shadow_rejected.sh prune <task_id>
EOF
    exit 2
}

# Usage-class refusal with a specific reason. Exit 2, never `die` (which is 1).
err_usage() {
    printf 'Error: %s\n' "$1" >&2
    exit 2
}

# Validate and normalize the task id, matching aitask_shadow_context.sh.
# Sets TASK_ID. Called directly (never in a subshell) so `exit 2` propagates.
resolve_task_id() {
    local raw="${1:-}"
    local id="${raw#t}"
    if [[ ! "$id" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
        printf "Error: invalid task id: '%s' (expected N, tN, N_M, or tN_M)\n" \
            "$raw" >&2
        exit 2
    fi
    TASK_ID="$id"
}

# Derive the store/lock paths for the resolved TASK_ID. The lock dir is derived
# from the DATA path so an AITASK_SHADOW_DIR override moves both together — a
# lock keyed to the default while the data went elsewhere would serialize
# nothing.
store_paths_for() {
    STORE_DIR="$SHADOW_DIR/$TASK_ID"
    STORE_FILE="$STORE_DIR/rejected.md"
    LOCK_DIR="${STORE_FILE}.lockd"
}

# Acquire the mutex or report LOCK_BUSY and exit 3. NEVER proceed unlocked:
# registry_lock_acquire returns 1 rather than stealing a live holder, and an
# unlocked write is exactly the lost update this mutex exists to stop.
lock_or_busy() {
    local timeout="$1"
    # registry_lock_acquire uses a plain `mkdir`, so the parent must exist —
    # and a failure to create it is a WRITE error, not contention. Swallowing it
    # would leave registry_lock_acquire spinning on a lock dir it can never
    # create until its timeout expires, then reporting LOCK_BUSY: the caller
    # waits the full timeout and is told a competing writer holds the mutex,
    # when in truth the store path is unusable (root is a regular file, the
    # parent is read-only, …). Diagnose it here instead, immediately.
    if ! mkdir -p "$STORE_DIR" 2>/dev/null; then
        printf "Error: cannot create store directory '%s'\n" "$STORE_DIR" >&2
        exit 4
    fi
    if [[ ! -w "$STORE_DIR" ]]; then
        printf "Error: store directory '%s' is not writable\n" "$STORE_DIR" >&2
        exit 4
    fi
    # The lock path must be a REAL directory or absent — registry_lock_acquire
    # serializes precisely by racing `mkdir "$LOCK_DIR"`. Anything else standing
    # at that path makes the mkdir fail forever, so acquire would again spin out
    # its whole timeout and report LOCK_BUSY with no competing writer in
    # existence.
    #
    # A symlink is rejected UNCONDITIONALLY, including one pointing at a real
    # directory: `-d` follows symlinks, so a `! -d` test would wave it through,
    # yet `mkdir` still fails with EEXIST on the link itself. acquire only ever
    # creates this path with a plain `mkdir` and removes it with `rm -rf`, so a
    # symlink here is never something it made and never something it can use.
    #
    # A real existing directory IS the genuine held-lock case and is left to
    # acquire, which knows how to wait out a live holder and steal from a
    # provably dead one.
    if [[ -L "$LOCK_DIR" ]]; then
        printf "Error: lock path '%s' is a symlink; expected a real directory\n" \
            "$LOCK_DIR" >&2
        exit 4
    fi
    if [[ -e "$LOCK_DIR" && ! -d "$LOCK_DIR" ]]; then
        printf "Error: lock path '%s' exists but is not a directory\n" "$LOCK_DIR" >&2
        exit 4
    fi
    if ! registry_lock_acquire "$LOCK_DIR" "$timeout"; then
        echo "LOCK_BUSY"
        exit 3
    fi
}

# --- Header helpers ---------------------------------------------------------

# Print the store's next-id high-water mark: the header value when present and
# canonical, otherwise max(entry id)+1, otherwise 1.
#
# "Canonical" is `[1-9][0-9]*` — a positive decimal with no leading zero — not
# merely "some digits". Two corrupt headers would otherwise get through: `0`
# issues an `r0` outside the documented monotonic-from-1 scheme, and a
# leading-zero value like `08` is parsed as OCTAL by bash arithmetic, which
# aborts with `value too great for base` — an undocumented exit 1 that loses the
# append. Anything non-canonical falls through to the documented self-heal.
# The max() fallback is forced to base 10 for the same reason: an entry id
# written as `r08` by some future writer must not crash the arithmetic.
_read_next_id() {
    local f="$1" n="" max=""
    if [[ -f "$f" ]]; then
        n=$(sed -n 's/^<!-- next_id: \([1-9][0-9]*\) -->$/\1/p' "$f" | head -n1)
        if [[ -z "$n" ]]; then
            max=$(sed -n 's/^### r\([0-9][0-9]*\) |.*/\1/p' "$f" | sort -n | tail -n1)
            [[ -n "$max" ]] && n=$(( 10#$max + 1 ))
        fi
    fi
    [[ -n "$n" ]] || n=1
    printf '%s\n' "$n"
}

# Emit the header line plus its trailing blank line.
_render_header() {
    printf '<!-- next_id: %s -->\n\n' "$1"
}

# Print the store body with the header line (and the blank line after it)
# removed. A store without a header is printed unchanged.
_strip_header() {
    awk '
        NR == 1 && /^<!-- next_id: [0-9]+ -->$/ { seen = 1; next }
        NR == 2 && seen == 1 && $0 == "" { next }
        { print }
    ' "$1"
}

# Print the ids currently present in the store, one per line.
_entry_ids() {
    [[ -f "$1" ]] || return 0
    sed -n 's/^### r\([0-9][0-9]*\) |.*/\1/p' "$1"
}

# --- add --------------------------------------------------------------------

_add_body() {
    _render_header "$(( next_id + marker_count ))" || return 1
    if [[ -f "$STORE_FILE" ]]; then
        _strip_header "$STORE_FILE" || return 1
    fi
    local i=0 m
    for m in "${markers[@]}"; do
        printf '### r%s | %s | producer: %s\n' \
            "$(( next_id + i ))" "$stamp" "$producer" || return 1
        printf '%s\n\n' "$m" || return 1
        i=$(( i + 1 ))
    done
}

cmd_add() {
    resolve_task_id "${1:-}"
    shift || true

    local producer="unknown"
    while [ $# -gt 0 ]; do
        case "$1" in
            --producer)
                [ $# -ge 2 ] || err_usage "--producer requires a value"
                producer="$2"; shift 2 ;;
            *) usage ;;
        esac
    done

    # Sanitize at the WRITE SITE: `|` is the machine-protocol delimiter and a
    # newline would forge an entry boundary. Both are undecidable on read.
    producer="${producer//|/ }"
    producer="$(printf '%s' "$producer" | tr -d '\n\r')"
    producer="${producer#"${producer%%[![:space:]]*}"}"
    producer="${producer%"${producer##*[![:space:]]}"}"
    [[ -n "$producer" ]] || producer="unknown"

    # Read and validate stdin BEFORE taking the lock, so a bad or empty input
    # never acquires the mutex and never reports a success-shaped result.
    local markers=() line
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^[[:space:]]*$ ]] && continue
        case "$line" in
            "- ["*) markers+=("$line") ;;
            *) err_usage "not a canonical concern marker line: $line" ;;
        esac
    done
    [[ ${#markers[@]} -gt 0 ]] || err_usage \
        "no concern marker lines on stdin (expected at least one '- [priority | region] body')"

    store_paths_for
    lock_or_busy "$MUTATE_LOCK_TIMEOUT"

    local next_id marker_count stamp
    next_id="$(_read_next_id "$STORE_FILE")"
    marker_count=${#markers[@]}
    stamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    if ! ait_atomic_render "$STORE_FILE" _add_body; then
        echo "Error: could not write $STORE_FILE" >&2
        exit 4
    fi
    echo "ADDED:$marker_count"
}

# --- list -------------------------------------------------------------------

cmd_list() {
    resolve_task_id "${1:-}"
    shift || true

    local machine=false
    while [ $# -gt 0 ]; do
        case "$1" in
            --machine) machine=true; shift ;;
            *) usage ;;
        esac
    done

    store_paths_for

    # No lock: every write lands via rename, so a reader always observes one
    # whole generation. All resolution outcomes exit 0 (line-protocol
    # convention shared with aitask_shadow_context.sh).
    if [[ ! -f "$STORE_FILE" ]] || [[ -z "$(_entry_ids "$STORE_FILE")" ]]; then
        echo "NO_REJECTIONS"
        return 0
    fi

    if [[ "$machine" == true ]]; then
        # The marker line goes LAST because it contains `|`; the id, timestamp
        # and sanitized producer never do, so consumers use split('|', 3).
        awk '
            /^### r[0-9]+ \| / {
                head = $0
                sub(/^### r/, "", head)
                split(head, part, "[|]")
                id = part[1]; ts = part[2]; prod = part[3]
                gsub(/^[ \t]+|[ \t]+$/, "", id)
                gsub(/^[ \t]+|[ \t]+$/, "", ts)
                gsub(/^[ \t]+|[ \t]+$/, "", prod)
                sub(/^producer: /, "", prod)
                if ((getline marker) > 0) {
                    printf "REJECTED:r%s|%s|%s|%s\n", id, ts, prod, marker
                }
            }
        ' "$STORE_FILE"
    else
        _strip_header "$STORE_FILE"
    fi
}

# --- remove -----------------------------------------------------------------

_remove_body() {
    _render_header "$keep_next" || return 1
    _strip_header "$STORE_FILE" | awk -v ids="$drop_csv" '
        function flush() {
            if (cur != "" && !(curid in drop)) printf "%s", cur
            cur = ""; curid = ""
        }
        BEGIN { n = split(ids, a, ","); for (i = 1; i <= n; i++) drop[a[i]] = 1 }
        /^### r[0-9]+ \| / {
            flush()
            match($0, /r[0-9]+/)
            curid = substr($0, RSTART + 1, RLENGTH - 1)
            cur = $0 "\n"
            next
        }
        { if (curid != "") cur = cur $0 "\n"; else print }
        END { flush() }
    ' || return 1
}

cmd_remove() {
    resolve_task_id "${1:-}"
    shift || true
    [ $# -gt 0 ] || err_usage "remove requires at least one entry id"

    # Normalize `r3` and `3` to the bare number.
    local wanted=() a n
    for a in "$@"; do
        n="${a#r}"
        [[ "$n" =~ ^[0-9]+$ ]] || err_usage "invalid entry id: '$a' (expected rN or N)"
        wanted+=("$n")
    done

    store_paths_for
    lock_or_busy "$MUTATE_LOCK_TIMEOUT"

    local present found=() missing=()
    present="$(_entry_ids "$STORE_FILE")"
    for n in "${wanted[@]}"; do
        if printf '%s\n' "$present" | grep -qx "$n"; then
            found+=("$n")
        else
            missing+=("$n")
        fi
    done

    if [[ ${#found[@]} -gt 0 ]]; then
        # The header is carried through untouched: never lowered, so a removed
        # id is never handed out again.
        local keep_next drop_csv
        keep_next="$(_read_next_id "$STORE_FILE")"
        drop_csv="$(IFS=,; printf '%s' "${found[*]}")"
        if ! ait_atomic_render "$STORE_FILE" _remove_body; then
            echo "Error: could not write $STORE_FILE" >&2
            exit 4
        fi
        printf 'REMOVED:%s\n' "$(IFS=,; printf 'r%s' "${found[0]}"; \
            for n in "${found[@]:1}"; do printf ',r%s' "$n"; done)"
    fi
    if [[ ${#missing[@]} -gt 0 ]]; then
        printf 'NOT_FOUND:%s\n' "$(printf 'r%s' "${missing[0]}"; \
            for n in "${missing[@]:1}"; do printf ',r%s' "$n"; done)"
    fi
}

# --- prune ------------------------------------------------------------------

cmd_prune() {
    resolve_task_id "${1:-}"
    shift || true
    [ $# -eq 0 ] || usage

    store_paths_for

    # 1. Absence check BEFORE any realpath. `realpath` fails on a path with two
    #    missing components, which is exactly `<root>/<id>` on the first archive
    #    in a repo that has never created the store root — under `set -e` that
    #    would abort instead of reporting absent.
    if [[ ! -d "$STORE_DIR" ]]; then
        echo "PRUNED:absent"
        return 0
    fi

    # 2. Only ever delete under our own root. The fallback keeps a
    #    canonicalization failure from aborting (aitask_explain_cleanup.sh idiom).
    local base canonical
    base="$(realpath "$SHADOW_DIR" 2>/dev/null || echo "$SHADOW_DIR")"
    canonical="$(realpath "$STORE_DIR" 2>/dev/null || echo "$STORE_DIR")"
    if [[ "$canonical" != "$base/$TASK_ID" ]]; then
        printf "Error: refusing to prune '%s' — it resolves to '%s', outside '%s'\n" \
            "$STORE_DIR" "$canonical" "$base" >&2
        exit 4
    fi

    # 3. Coordinate with add/remove: the lock dir lives INSIDE the directory
    #    being pruned, so an unlocked delete could yank the mutex out from under
    #    a mid-write mutation and discard its rename.
    lock_or_busy "$PRUNE_LOCK_TIMEOUT"

    # 4. Remove the store's regular files but NOT the held `.lockd` (a
    #    directory). `-type f` also sweeps any stale `.rejected.md.XXXXXX`
    #    staging temp left by a crashed writer, which would otherwise defeat the
    #    rmdir below.
    find "$STORE_DIR" -maxdepth 1 -type f -exec rm -f {} + 2>/dev/null || true

    # 5. Release (removes the `.lockd`), then 6. plain rmdir — never `rm -rf`,
    #    so a concurrent waiter's freshly re-created lock survives and the dir is
    #    simply left behind, re-prunable by any later prune.
    registry_lock_release "$LOCK_DIR"
    rmdir "$STORE_DIR" 2>/dev/null || true

    echo "PRUNED:$TASK_ID"
}

main() {
    local verb="${1:-}"
    [ -n "$verb" ] || usage
    shift
    case "$verb" in
        add)    cmd_add "$@" ;;
        list)   cmd_list "$@" ;;
        remove) cmd_remove "$@" ;;
        prune)  cmd_prune "$@" ;;
        -h|--help) usage ;;
        *)      usage ;;
    esac
}

main "$@"
