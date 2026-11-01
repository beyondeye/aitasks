#!/usr/bin/env bash
# aitask_sitrep_todo.sh - The ONE writer of the per-repo sitrep store (t2175_1).
#
# The store lives at `${AITASK_SITREP_DIR:-.aitask-sitrep}/` -- repo-root-relative
# (an absolute override targets another repository's store), git-ignored, never
# committed. It is a SOURCE OF TRUTH: dismissals, agent-derived items and Q&A are
# not rebuildable from anything else, so every write is locked, atomic and
# backed up, and recovery never removes a live file.
#
#   todo.md, todo.md.bak  Part 1 (situation per theme; items grouped Pick now /
#                         Next / Waiting / Recently done / Dismissed) and Part 2
#                         (one context entry per item -- a MAP of pointers:
#                         background, origin, theme, sources, related; never
#                         status, counts or summaries)
#   qa.md, qa.md.bak      the dated Q&A log
#   store.init            written LAST by the one-time initialization
#   next_id, next_rev     the item-id and revision high-water marks
#   sources/<hex>.txt     retained passages (content-addressed, immutable)
#   recovered/            damaged files preserved by `restore`
#   .lockd/               the registry_lock.sh mutex for the whole store
#
# FORMAT. Defined, parsed and rendered by lib/sitrep_todo.py (read its header).
# Line 1 of every data file is a fixed "GENERATED FILE - DO NOT EDIT MANUALLY"
# banner and the parser is strict: a hand-edited file is refused (exit 4) until
# `restore` puts the last good generation back. The consumer contract is the
# golden store in tests/fixtures/sitrep/ -- a format change edits that fixture
# and bumps `format=`.
#
# CONCURRENCY. `lib/atomic_write.sh` gives readers a whole-old-or-whole-new view
# but does not serialize a read-modify-write, so every mutation holds the
# `lib/registry_lock.sh` mutex (shadow-store pattern) and re-reads the file under
# it. Verbs are record-level -- none replaces a whole section -- and stale
# results are refused, not merged: every change gives the item a fresh
# `rev=<N>`; `set-state --batch` lines and any `--expect-rev` write apply only
# when the item still has the observed rev (else `STALE:`), and a batch never
# touches a dismissed item (`KEPT:`) nor sets `dismissed` -- dismissal is the
# user's.
#
# IDS AND REVS ARE NEVER REUSED, INCLUDING ACROSS RESTORE. Revs are store-wide
# stamps, not per-item counters, so an (id, rev) pair names one state of one
# item forever -- a refresh computed before a restore cannot pass its rev check
# against the item as it is after. `next_id` / `next_rev` are written
# atomically BEFORE the todo.md rename that uses them (a crash between leaves a
# harmless gap), and allocation is max(counter, 1 + highest value at a
# structural position in todo.md, qa.md, both backups and recovered/) -- so an
# older backup, a lost counter or a Q&A entry naming an item the backup lacks
# can never hand a value out twice.
#
# INITIALIZATION. The first mutation of ANY verb writes the empty generation of
# qa.md, qa.md.bak, todo.md and todo.md.bak (each only if missing), then
# store.init. Data is only written after store.init exists, so a missing data
# file in an ESTABLISHED store (marker, next_id, sources/, recovered/ or any
# non-template data file present) is damage: the verbs that touch that file
# refuse with exit 4 and name `restore`; verbs on the other file keep working.
#
# RECOVERY. `restore todo|qa` verifies the .bak, copies the live file (if any)
# into recovered/, then installs the .bak over the live name in ONE rename -- an
# interrupted restore leaves the damaged original or the restored file, never
# neither -- and for todo rewrites next_id and next_rev to the full maxima.
#
# SOURCES. Agent captures under ~/.config/aitasks/frozen/ are deleted by drop,
# re-registration and freeze_abort, so a `capture:` source may only point at a
# passage retained here (`retain`), and is checked to exist, in range, under the
# lock. `task:`/`plan:`/`file:` sources must be repo-relative.
#
# `task_utils.sh` is deliberately NOT sourced: it pulls in lib/archive_utils.sh,
# which claims the process-wide EXIT trap at source time, and registry_lock's own
# EXIT trap would clobber it.
#
# TEST SEAMS (test-only). AITASK_SITREP_PAUSE_FIFO: at the points init:after_qa,
# write:after_counter, write:after_backup and restore:after_preserve the verb
# writes the point name to `<fifo>.reached`, then blocks reading one line from
# the fifo. AITASK_SITREP_NOW pins the clock (YYYY-MM-DDTHH:MM:SSZ).
# AITASK_SITREP_LOCK_TIMEOUT overrides the 10s lock-wait budget.
#
# Callers: the sitrep harvest (t2175_2) and refresh (t2175_3) scripts, and the
# sitrep skill (t2175_4).
#
# Verbs (ids are c<N> or <N>; stdin text never contains NUL):
#   add --kind K --title T [--ref R] [--group now|next|waiting]
#       [--state open|unknown] [--derived script|agent] [--checked-at TS|now|never]
#       [--context-file -]          ADDED:c<N> | EXISTS:c<N> (a non-empty ref
#                                   already present in ANY state: nothing written)
#   update <id> [--title T] [--group G] [--ref R] [--kind K] [--expect-rev N]
#                                   UPDATED:c<N>|<rev> | STALE:c<N>|<rev>
#   set-state <id> <state> [--checked-at TS|now] [--outcome T] [--expect-rev N]
#                                   STATE:c<N>|<state>|<rev> | STALE:c<N>|<rev>
#   set-state --batch               stdin: <id>|<rev>|<state>|<checked_at>|<outcome>
#                                   per line -> STATE: / STALE: / KEPT:c<N>|dismissed
#                                   / NOT_FOUND:c<N> per line
#   dismiss <id> [--outcome T] [--expect-rev N]
#                                   STATE:c<N>|dismissed|<rev>
#   situation <theme>               stdin (empty removes) -> SITUATION:<theme>|set
#                                   | removed | absent
#   upsert-context <id>             stdin -> CONTEXT:c<N>|created|replaced|unchanged
#   retain                          stdin passage (<=64 KiB) ->
#                                   RETAINED:sources/<hex>.txt#L1-L<n>
#   qa [--items c4,c5]              stdin -> QA:<timestamp>
#   restore todo|qa                 RESTORED:<file>|recovered/<name>
#                                   | RESTORED:<file>|no-damaged-copy
#   read [all|todo|context|qa]      raw text, no lock (works on a damaged file);
#                                   `todo` is Part 1, `context` Part 2
#   list [--machine]                ITEM:c<N>|<rev>|kind|state|group|checked_at|
#                                   ref|derived|outcome|title (title LAST, it may
#                                   contain `|`) | NO_ITEMS
#   context <id>                    the entry block | NO_CONTEXT:c<N>
#   check-sources                   SOURCE_OK:c<N>|<ptr> | SOURCE_MISSING:c<N>|<ptr>
#                                   per retained capture | NO_SOURCES
#   path                            the canonical absolute store dir
#
# Exit codes:
#   0  success (including EXISTS / STALE / KEPT / NO_* results)
#   2  bad request -- usage, invalid value, schema rejection, unknown id
#      (NOT_FOUND:c<N>), `..` in the root; NOTHING was locked or written
#   3  LOCK_BUSY -- another process holds the mutex; NOTHING was written
#   4  store unusable -- a file is damaged, missing or unwritable; NOTHING was
#      changed; do not retry (see `restore`)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/registry_lock.sh
source "$SCRIPT_DIR/lib/registry_lock.sh"
# shellcheck source=lib/atomic_write.sh
source "$SCRIPT_DIR/lib/atomic_write.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

SITREP_DIR="${AITASK_SITREP_DIR:-.aitask-sitrep}"
CORE="$SCRIPT_DIR/lib/sitrep_todo.py"

# Lock-wait budget only: the work done once the lock is held has no deadline.
LOCK_TIMEOUT="${AITASK_SITREP_LOCK_TIMEOUT:-10}"

# Populated by store_paths_for / read_stdin.
STORE_DIR=""
TODO=""
QA=""
MARKER=""
COUNTER=""
REV_COUNTER=""
LOCK_DIR=""
BUF=""
HAS_INPUT=""
PY=""

usage() {
    cat >&2 <<'EOF'
Usage: aitask_sitrep_todo.sh add --kind K --title T [--ref R] [--group G] [--state S]
                                 [--derived D] [--checked-at TS] [--context-file -]
       aitask_sitrep_todo.sh update <id> [--title T] [--group G] [--ref R] [--kind K] [--expect-rev N]
       aitask_sitrep_todo.sh set-state <id> <state> [--checked-at TS] [--outcome T] [--expect-rev N]
       aitask_sitrep_todo.sh set-state --batch        (lines on stdin)
       aitask_sitrep_todo.sh dismiss <id> [--outcome T] [--expect-rev N]
       aitask_sitrep_todo.sh situation <theme>        (text on stdin)
       aitask_sitrep_todo.sh upsert-context <id>      (entry on stdin)
       aitask_sitrep_todo.sh retain                   (passage on stdin)
       aitask_sitrep_todo.sh qa [--items c4,c5]       (text on stdin)
       aitask_sitrep_todo.sh restore todo|qa
       aitask_sitrep_todo.sh read [all|todo|context|qa]
       aitask_sitrep_todo.sh list [--machine]
       aitask_sitrep_todo.sh context <id>
       aitask_sitrep_todo.sh check-sources
       aitask_sitrep_todo.sh path
EOF
    exit 2
}

# Usage-class refusal with a specific reason. Exit 2, never `die` (which is 1).
err_usage() {
    printf 'Error: %s\n' "$1" >&2
    exit 2
}

# Store-unusable refusal. Exit 4: nothing was changed, do not retry.
err_store() {
    printf 'Error: %s\n' "$1" >&2
    exit 4
}

# Refuse a root with a `..` segment before ANY filesystem access.
validate_root() {
    case "/$SITREP_DIR/" in
        */../*) err_usage "sitrep root '$SITREP_DIR' contains a '..' segment" ;;
    esac
    [[ "$LOCK_TIMEOUT" =~ ^[0-9]+$ ]] \
        || err_usage "AITASK_SITREP_LOCK_TIMEOUT must be a whole number of seconds"
}

store_paths_for() {
    STORE_DIR="$SITREP_DIR"
    TODO="$STORE_DIR/todo.md"
    QA="$STORE_DIR/qa.md"
    MARKER="$STORE_DIR/store.init"
    COUNTER="$STORE_DIR/next_id"
    REV_COUNTER="$STORE_DIR/next_rev"
    LOCK_DIR="$STORE_DIR/.lockd"
}

need_python() {
    PY="$(resolve_python)"
    [[ -n "$PY" ]] || err_store "no Python interpreter found (run 'ait setup')"
}

# Read stdin into BUF. The sentinel keeps trailing newlines; `&&` makes the
# substitution's status cat's, so a failed read is never committed as input.
read_stdin() {
    local b
    if ! b="$(cat && printf x)"; then
        err_store "could not read stdin"
    fi
    BUF="${b%x}"
    HAS_INPUT=1
}

# Feed BUF to a pipeline. The core reads its whole stdin before anything else,
# so this printf never meets a closed pipe.
feed() {
    [[ -n "$HAS_INPUT" ]] && printf '%s' "$BUF"
    return 0
}

# py <op> [args...] -- the core, stdin from BUF.
py() {
    feed | "$PY" "$CORE" "$@"
}

# Validate a request without touching the store. Exit 2 on refusal.
precheck() {
    local rc=0
    py "$@" --check-only >/dev/null || rc=$?
    case "$rc" in
        0) ;;
        2) exit 2 ;;
        *) err_store "request validation failed unexpectedly (exit $rc)" ;;
    esac
}

# Acquire the mutex or report LOCK_BUSY and exit 3. NEVER proceed unlocked.
lock_or_busy() {
    # registry_lock_acquire uses a plain `mkdir`, so the parent must exist -- and
    # a failure to create it is a WRITE error, not contention (reporting it as
    # LOCK_BUSY after the full timeout would blame a writer that does not exist).
    if ! mkdir -p "$STORE_DIR" 2>/dev/null; then
        err_store "cannot create store directory '$STORE_DIR'"
    fi
    if [[ ! -w "$STORE_DIR" ]]; then
        err_store "store directory '$STORE_DIR' is not writable"
    fi
    # The lock path must be a REAL directory or absent: acquire serializes by
    # racing `mkdir "$LOCK_DIR"`. A symlink is rejected even when it points at a
    # directory (`-d` follows it, `mkdir` still fails on the link itself).
    if [[ -L "$LOCK_DIR" ]]; then
        err_store "lock path '$LOCK_DIR' is a symlink; expected a real directory"
    fi
    if [[ -e "$LOCK_DIR" && ! -d "$LOCK_DIR" ]]; then
        err_store "lock path '$LOCK_DIR' exists but is not a directory"
    fi
    if ! registry_lock_acquire "$LOCK_DIR" "$LOCK_TIMEOUT"; then
        echo "LOCK_BUSY"
        exit 3
    fi
    sweep_stale_temps
}

# With the mutex held no other writer of this store is mid-write, so a staging
# temp beside a store file can only be a killed writer's leftover. Only the
# exact `.<name>.XXXXXX` shapes ait_atomic_tmp creates are removed.
sweep_stale_temps() {
    local name f
    for name in todo.md todo.md.bak qa.md qa.md.bak next_id next_rev store.init; do
        for f in "$STORE_DIR/.$name."??????; do
            [[ -f "$f" && ! -L "$f" ]] && rm -f -- "$f"
        done
    done
    return 0
}

release() {
    registry_lock_release "$LOCK_DIR"
}

# Test-only pause point -- see TEST SEAMS in the header.
pause_seam() {
    [[ -n "${AITASK_SITREP_PAUSE_FIFO:-}" ]] || return 0
    printf '%s\n' "$1" > "${AITASK_SITREP_PAUSE_FIFO}.reached"
    local _line
    read -r _line < "$AITASK_SITREP_PAUSE_FIFO" || true
}

# Renderers (see lib/atomic_write.sh: every fallible command is guarded).
_render_empty() { "$PY" "$CORE" empty "$1" || return 1; }
_render_copy() { cat -- "$1" || return 1; }
_render_buf() { printf '%s' "$BUF"; }

write_marker() {
    ait_atomic_write_text "$MARKER" "format=1" \
        || err_store "could not write '$MARKER'"
}

# One-time initialization -- see INITIALIZATION in the header. Order matters:
# the marker goes LAST, so its presence means every data file was written.
init_store() {
    local f kind
    for f in "$QA" "$QA.bak" PAUSE "$TODO" "$TODO.bak"; do
        if [[ "$f" == PAUSE ]]; then
            pause_seam init:after_qa
            continue
        fi
        kind=todo
        [[ "$f" == "$QA"* ]] && kind=qa
        [[ -e "$f" ]] && continue
        ait_atomic_render "$f" _render_empty "$kind" \
            || err_store "could not initialize '$f'"
    done
    write_marker
}

# Under the lock: initialize a fresh store, heal a lost marker, and refuse when
# the file this verb touches (`todo`, `qa` or `none`) is missing from an
# established store.
ensure_store() {
    local need="$1" state
    state="$("$PY" "$CORE" state --store "$STORE_DIR")" \
        || err_store "cannot inspect the store '$STORE_DIR'"
    if [[ "$state" == *"ESTABLISHED=0"* ]]; then
        init_store
        return 0
    fi
    if [[ "$state" == *"MARKER=0"* && "$state" == *"TODO=ok"* && "$state" == *"QA=ok"* ]]; then
        write_marker
    fi
    case "$need" in
        todo|qa)
            local up
            up="$(printf '%s' "$need" | tr '[:lower:]' '[:upper:]')"
            if [[ "$state" == *"$up=missing"* ]]; then
                err_store "$need.md is missing from an established store -- run \`aitask_sitrep_todo.sh restore $need\`"
            fi
            ;;
    esac
}

# Print a core result block, minus the @-directives meant for this wrapper.
print_results() {
    [[ -n "$1" ]] || return 0
    printf '%s\n' "$1" | grep -v '^@' || true
}

directive() {
    printf '%s\n' "$2" | sed -n "s/^@$1://p" | head -n1
}

# mutate <todo|qa> <op> [args...] -- the shared locked mutation sequence:
# precheck already ran; lock -> ensure -> core renders into a staged temp ->
# next_id (add) -> roll .bak -> one rename. Results print only after the commit.
mutate() {
    local kind="$1" dest res rc=0 tmp next
    shift
    dest="$STORE_DIR/$kind.md"
    lock_or_busy
    ensure_store "$kind"
    dest="$(ait_atomic_resolve "$dest")" || err_store "cannot resolve '$dest'"
    tmp="$(ait_atomic_tmp "$dest")" || err_store "cannot stage a write beside '$dest'"
    res="$(py "$@" --store "$STORE_DIR" --out "$tmp")" || rc=$?
    case "$rc" in
        0) ;;
        2) ait_atomic_discard "$tmp"; release; print_results "$res"; exit 2 ;;
        4) ait_atomic_discard "$tmp"; exit 4 ;;
        *) ait_atomic_discard "$tmp"; err_store "the sitrep core failed (exit $rc); nothing was written" ;;
    esac
    if [[ ! -s "$tmp" ]]; then
        # Nothing changed (EXISTS / STALE / KEPT / an identical value).
        ait_atomic_discard "$tmp"
        release
        print_results "$res"
        return 0
    fi
    # Reserve ids and revision stamps BEFORE the rename that uses them: a crash
    # in between leaves a harmless gap, never a value handed out twice.
    local reserved=0 pair
    for pair in "NEXT_ID:$COUNTER" "NEXT_REV:$REV_COUNTER"; do
        next="$(directive "${pair%%:*}" "$res")"
        [[ -n "$next" ]] || continue
        if ! ait_atomic_write_text "${pair#*:}" "$next"; then
            ait_atomic_discard "$tmp"
            err_store "could not reserve the high-water mark in '${pair#*:}'"
        fi
        reserved=1
    done
    [[ "$reserved" -eq 0 ]] || pause_seam write:after_counter
    if ! ait_atomic_render "$dest.bak" _render_copy "$dest"; then
        ait_atomic_discard "$tmp"
        err_store "could not roll the backup '$dest.bak'"
    fi
    pause_seam write:after_backup
    ait_atomic_commit "$tmp" "$dest" || err_store "could not write '$dest'"
    release
    print_results "$res"
}

# --- verbs ------------------------------------------------------------------

cmd_add() {
    local args=() ctx=false
    while [ $# -gt 0 ]; do
        case "$1" in
            --kind|--title|--ref|--group|--state|--derived|--checked-at)
                [ $# -ge 2 ] || err_usage "$1 requires a value"
                args+=("$1" "$2"); shift 2 ;;
            --context-file)
                [ $# -ge 2 ] || err_usage "--context-file requires a value"
                [[ "$2" == "-" ]] || err_usage "--context-file takes '-' (the entry on stdin)"
                ctx=true; shift 2 ;;
            *) usage ;;
        esac
    done
    if [[ "$ctx" == true ]]; then
        read_stdin
        args+=(--input -)
    fi
    precheck add "${args[@]}"
    mutate todo add "${args[@]}"
}

cmd_update() {
    [ $# -ge 1 ] || usage
    local args=("$1")
    shift
    while [ $# -gt 0 ]; do
        case "$1" in
            --title|--group|--ref|--kind|--expect-rev)
                [ $# -ge 2 ] || err_usage "$1 requires a value"
                args+=("$1" "$2"); shift 2 ;;
            *) usage ;;
        esac
    done
    precheck update "${args[@]}"
    mutate todo update "${args[@]}"
}

_state_opts() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --checked-at|--outcome|--expect-rev)
                [ $# -ge 2 ] || err_usage "$1 requires a value"
                STATE_ARGS+=("$1" "$2"); shift 2 ;;
            *) usage ;;
        esac
    done
}

cmd_set_state() {
    [ $# -ge 1 ] || usage
    if [[ "$1" == "--batch" ]]; then
        [ $# -eq 1 ] || usage
        read_stdin
        precheck set-state-batch --input -
        mutate todo set-state-batch --input -
        return
    fi
    [ $# -ge 2 ] || usage
    STATE_ARGS=("$1" "$2")
    shift 2
    _state_opts "$@"
    precheck set-state "${STATE_ARGS[@]}"
    mutate todo set-state "${STATE_ARGS[@]}"
}

cmd_dismiss() {
    [ $# -ge 1 ] || usage
    STATE_ARGS=("$1" dismissed)
    shift
    _state_opts "$@"
    precheck set-state "${STATE_ARGS[@]}"
    mutate todo set-state "${STATE_ARGS[@]}"
}

cmd_situation() {
    [ $# -eq 1 ] || usage
    read_stdin
    precheck situation "$1" --input -
    mutate todo situation "$1" --input -
}

cmd_upsert_context() {
    [ $# -eq 1 ] || usage
    read_stdin
    precheck upsert-context "$1" --input -
    mutate todo upsert-context "$1" --input -
}

cmd_qa() {
    local args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --items)
                [ $# -ge 2 ] || err_usage "--items requires a value"
                args+=(--items "$2"); shift 2 ;;
            *) usage ;;
        esac
    done
    read_stdin
    precheck qa "${args[@]}" --input -
    mutate qa qa "${args[@]}" --input -
}

cmd_retain() {
    [ $# -eq 0 ] || usage
    read_stdin
    precheck retain
    lock_or_busy
    ensure_store none
    mkdir -p "$STORE_DIR/sources" 2>/dev/null \
        || err_store "cannot create '$STORE_DIR/sources'"
    local res rc=0 target
    res="$(py retain --store "$STORE_DIR")" || rc=$?
    case "$rc" in
        0) ;;
        2) release; exit 2 ;;
        *) exit 4 ;;
    esac
    target="$(directive TARGET "$res")"
    if [[ -n "$target" ]]; then
        ait_atomic_render "$STORE_DIR/$target" _render_buf \
            || err_store "could not write '$STORE_DIR/$target'"
    fi
    release
    print_results "$res"
}

cmd_restore() {
    [ $# -eq 1 ] || usage
    local kind="$1" live bak preserved="" name
    case "$kind" in
        todo|qa) ;;
        *) err_usage "restore takes 'todo' or 'qa'" ;;
    esac
    [[ -d "$STORE_DIR" ]] || err_store "no sitrep store at '$STORE_DIR'"
    live="$STORE_DIR/$kind.md"
    bak="$live.bak"
    lock_or_busy
    if ! "$PY" "$CORE" verify "$kind" "$bak" >/dev/null; then
        err_store "cannot restore $kind.md: its backup is missing or unreadable"
    fi
    if [[ -e "$live" || -L "$live" ]]; then
        mkdir -p "$STORE_DIR/recovered" 2>/dev/null \
            || err_store "cannot create '$STORE_DIR/recovered'"
        name="$kind.md.$(date -u +%Y%m%dT%H%M%SZ).$$"
        AIT_ATOMIC_ALLOW_EMPTY=1 ait_atomic_render "$STORE_DIR/recovered/$name" _render_copy "$live" \
            || err_store "could not preserve the damaged '$live'"
        preserved="recovered/$name"
    fi
    pause_seam restore:after_preserve
    ait_atomic_render "$live" _render_copy "$bak" \
        || err_store "could not install the backup over '$live'"
    if [[ "$kind" == todo ]]; then
        # The restored generation carries older ids and revs; pin both marks to
        # the maximum ever seen so neither is handed out again.
        local n pair
        for pair in "alloc:$COUNTER" "alloc-rev:$REV_COUNTER"; do
            n="$("$PY" "$CORE" "${pair%%:*}" --store "$STORE_DIR")" \
                || err_store "could not recompute the high-water mark for '${pair#*:}'"
            ait_atomic_write_text "${pair#*:}" "$n" \
                || err_store "could not write '${pair#*:}'"
        done
    fi
    if [[ ! -f "$MARKER" && -f "$TODO" && -f "$QA" ]]; then
        write_marker
    fi
    release
    echo "RESTORED:$kind.md|${preserved:-no-damaged-copy}"
}

# Read-only verbs: no lock -- every write lands via rename, so a reader always
# observes one whole generation.
cmd_readonly() {
    local rc=0
    "$PY" "$CORE" "$@" --store "$STORE_DIR" || rc=$?
    case "$rc" in
        0) ;;
        2) exit 2 ;;
        *) exit 4 ;;
    esac
}

main() {
    local verb="${1:-}"
    [ -n "$verb" ] || usage
    shift
    case "$verb" in
        -h|--help) usage ;;
    esac
    validate_root
    store_paths_for
    need_python
    case "$verb" in
        add)            cmd_add "$@" ;;
        update)         cmd_update "$@" ;;
        set-state)      cmd_set_state "$@" ;;
        dismiss)        cmd_dismiss "$@" ;;
        situation)      cmd_situation "$@" ;;
        upsert-context) cmd_upsert_context "$@" ;;
        retain)         cmd_retain "$@" ;;
        qa)             cmd_qa "$@" ;;
        restore)        cmd_restore "$@" ;;
        read)
            [ $# -le 1 ] || usage
            cmd_readonly read "${1:-all}" ;;
        list)
            [[ $# -eq 0 || ( $# -eq 1 && "$1" == "--machine" ) ]] || usage
            cmd_readonly list ;;
        context)
            [ $# -eq 1 ] || usage
            cmd_readonly context "$1" ;;
        check-sources)
            [ $# -eq 0 ] || usage
            cmd_readonly check-sources ;;
        path)
            [ $# -eq 0 ] || usage
            cmd_readonly path ;;
        *) usage ;;
    esac
}

main "$@"
