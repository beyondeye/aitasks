#!/usr/bin/env bash
# aitask_sitrep_harvest.sh - Harvest finished agents into the sitrep store (t2175_2).
#
# Turns a finished or frozen agent's output into sitrep items and stub context
# entries, so the agent's window can be closed without losing its follow-up
# information. NOT a store writer: every store write goes through
# aitask_sitrep_todo.sh (the store's one writer); parsing, identity and item
# building live in lib/sitrep_harvest.py (read its header for the grammar and
# the run-identity rules).
#
# Verbs:
#   record <id> [--force]     harvest a session record's capture.txt, then write
#                             its harvest RECEIPT (`<capture.txt>.harvested`)
#   all [--root <path>]       every record holding capture text (any state),
#                             each into its own repository's store
#   banner --task <id> [--skill <name>]
#                             the workflow-end path: the closing message plus
#                             the banner on stdin. Prints `HARVEST_RUN:<16 hex>`
#                             as its FIRST stdout line -- the agent's tool-call
#                             display records it in the pane, and a later
#                             capture harvest uses it to recognise this run.
#   capture --root <path> [--agent W] [--task T] [--operation op]
#                             a capture on stdin (t2175_5's live-pane path)
#   case list|show|read|review|replay|export|check-fixture ...
#                             the review-case corpus (lib/sitrep_corpus.py,
#                             t2175_6); `replay --apply` runs under the mutex
#
# Wire lines (stdout, one per event):
#   HARVEST_RUN:<16 hex>                       banner only, first line
#   HARVEST_ITEM:<src>|c<N>|added|exists|<kind>|<ref or ->
#   HARVEST_WARN:<src>|<reason>
#   HARVEST_REVIEW:<src>|c<N>|added|exists|case=<16 hex>|<reason codes>
#                                              uncertain output kept for review
#                                              (also before a cached
#                                              already_harvested)
#   final:  HARVESTED:<src>|added=<a>|existing=<e>[|review=c<N>]
#         | HARVEST_NONE:<src>|no_capture|nothing_found|already_harvested
#                                  |sitrep_agent
#         | HARVEST_FAILED:<src>|<reason>
# Exit codes: 0 success (incl. NONE), 1 at least one harvest failed, 2 usage.
#
# ONE STORE PER REPOSITORY. Every verb maps its root to the repository's main
# worktree (a linked `aiwork/<task>` worktree, even a removed one, maps to the
# repo that owns it), and writes `<main>/.aitask-sitrep`. If that path is not
# git-ignored, `.aitask-sitrep/` is appended to the repo's LOCAL
# `--git-path info/exclude` (never committed) and re-checked; still not ignored
# => HARVEST_FAILED:store_not_ignorable. A non-git root needs no rule. Nothing
# at all is written (no store, no exclude line) when the parse finds nothing.
#
# CONFIDENCE AND REVIEW CASES (t2175_6). Before any receipt, the parse is
# checked (lib/sitrep_harvest.py `assess`): an incomplete banner, a malformed
# follow-up token, a truncated passage, a banner line no parsed banner starts,
# a malformed `Created:` reference, a harvest marker no banner claims, or a
# piped message without a banner -- each occurrence on its own. Any reason
# keeps the WHOLE raw input verbatim (`raw/<hex>.txt`) with its diagnostics and
# ONE durable "Analyze unparsed agent output" review item (lib/sitrep_corpus.py)
# -- all before the receipt. Useful partial items are still written. No banner
# at all (an agent frozen mid-work) or an unresolved foreign task is no reason.
#
# RECEIPTS AND THE DESTRUCTIVE ROUTES. Deletion is allowed after reliable
# extraction, or after raw evidence plus a durable review item were recorded:
# only then does a `record` harvest (including nothing_found) write
# `<capture.txt>.harvested` = sha256 of the capture text + the store path +
# `cert=2` (the certification version; a failed case write withholds it).
# lib/agent_sessions.py `capture_harvested()` checks sha AND cert -- a legacy
# receipt without `cert=2` authorises nothing, and `record` re-harvests it --
# and the two library routes that delete a frozen agent's text refuse without it:
#   drop    -> HARVEST_REQUIRED:<id>, exit 9 (aitask_agent_sessions.sh drop;
#              reached by aitask_frozen.sh drop and the monitor kill path).
#              `--skip-harvest` is the explicit discard.
#   purge   -> the record is KEPT (`KEPT:<id>|unharvested_text`), any state.
# Ungated on purpose: a verified restore (the conversation is back) and
# freeze_abort (the agent never stopped). The receipt dies with the capture
# directory, and a re-freeze that rewrites capture.txt invalidates it by sha.
#
# BUDGETS. The full harvest runs only where a caller can afford it: after a
# freeze (best-effort, AITASK_SITREP_HARVEST_TIMEOUT, default 60s) and in
# `aitask_frozen.sh drop` before the viewer is killed (default 120s, a detached
# run-shell job). The store `drop` / `purge` gates are a receipt read (ms), so
# they fit the monitor's 10s and the freeze engine's 20s store calls. This
# script's own mutex wait (AITASK_SITREP_HARVEST_LOCK_TIMEOUT, default 20s) is
# shorter than either harvest budget. A cancelled harvest writes no receipt, so
# cancellation can only make the gates refuse.
#
# CONCURRENCY. Identity checks (does this run already have an item?) read the
# store and then add, so every apply holds the per-store harvest mutex
# `<store>/.harvest.lockd` (lib/registry_lock.sh). The writer's own `.lockd` is
# separate; the writer subprocesses never wait on this one.
#
# THE SITREP AGENT IS NEVER HARVESTED (t2175_4). A record whose window is the
# sitrep window (`agent-sitrep`, `agent-sitrep-<n>`) gets its receipt and
# `HARVEST_NONE:<id>|sitrep_agent`: its screen only echoes the store, so a
# harvest would feed the store back into itself. The receipt keeps drop and
# purge unblocked.
#
# SKILL-INVOKED by `banner` (workflow-end.md) and by the sitrep skill, which
# runs `all --root <repo>` on start; that is why this helper has the
# code-agent allow-list entries (see
# aidocs/framework/aitasks_extension_points.md). It issues no raw tmux.
#
# TEST SEAMS (test-only). AITASK_SITREP_HARVEST_PAUSE_FIFO: once the mutex is
# held the verb writes `apply:locked` to `<fifo>.reached`, then blocks reading
# one line from the fifo. AITASK_SITREP_HARVEST_RUN_ID (16 hex) pins the run id
# `banner` would otherwise draw at random. AITASK_SITREP_HARVEST_FAULT=<point>
# (case:raw, case:files, case:item, receipt) fails the harvest at that point;
# AITASK_SITREP_RAW_MAX lowers the raw-input cap (bytes).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/registry_lock.sh
source "$SCRIPT_DIR/lib/registry_lock.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

CORE="$SCRIPT_DIR/lib/sitrep_harvest.py"
CORPUS="$SCRIPT_DIR/lib/sitrep_corpus.py"
LOCK_TIMEOUT="${AITASK_SITREP_HARVEST_LOCK_TIMEOUT:-20}"
EXCLUDE_RULE=".aitask-sitrep/"

PY=""
BUF=""

usage() {
    cat >&2 <<'EOF'
Usage: aitask_sitrep_harvest.sh record <id> [--force]
       aitask_sitrep_harvest.sh all [--root <path>]
       aitask_sitrep_harvest.sh banner --task <id> [--skill <name>]   (text on stdin)
       aitask_sitrep_harvest.sh capture --root <path> [--agent W] [--task T] [--operation op]
       aitask_sitrep_harvest.sh case list|show|read|review|replay|export|check-fixture ...
EOF
    exit 2
}

err_usage() {
    printf 'Error: %s\n' "$1" >&2
    exit 2
}

no_dotdot() {
    case "/$1/" in
        */../*) err_usage "path '$1' contains a '..' segment" ;;
    esac
}

need_python() {
    PY="$(resolve_python)"
    if [[ -z "$PY" ]]; then
        echo "HARVEST_FAILED:${1:-harvest}|no_python"
        exit 1
    fi
}

read_stdin() {
    local b
    if ! b="$(cat && printf x)"; then
        echo "HARVEST_FAILED:${1:-harvest}|stdin_unreadable"
        exit 1
    fi
    BUF="${b%x}"
}

feed() { printf '%s' "$BUF"; }

pause_seam() {
    [[ -n "${AITASK_SITREP_HARVEST_PAUSE_FIFO:-}" ]] || return 0
    printf '%s\n' "$1" > "${AITASK_SITREP_HARVEST_PAUSE_FIFO}.reached"
    local _line
    read -r _line < "$AITASK_SITREP_HARVEST_PAUSE_FIFO" || true
}

# Make `<root>/.aitask-sitrep/` git-ignored, locally. Returns 1 when it cannot.
ensure_ignored() {
    local root="$1" exclude
    git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
    git -C "$root" check-ignore -q ".aitask-sitrep/todo.md" 2>/dev/null && return 0
    exclude="$(git -C "$root" rev-parse --path-format=absolute --git-path info/exclude 2>/dev/null)" \
        || return 1
    [[ -n "$exclude" ]] || return 1
    mkdir -p "$(dirname "$exclude")" 2>/dev/null || return 1
    if [[ -s "$exclude" && -n "$(tail -c1 "$exclude")" ]]; then
        printf '\n' >> "$exclude" || return 1
    fi
    printf '# aitasks sitrep store (per-repo, local-only; added by aitask_sitrep_harvest.sh)\n%s\n' \
        "$EXCLUDE_RULE" >> "$exclude" || return 1
    # Re-check: a negation rule elsewhere can still un-ignore it.
    git -C "$root" check-ignore -q ".aitask-sitrep/todo.md" 2>/dev/null
}

# Run a command with the store's harvest mutex held (the store made
# git-ignored and writable first). Every identity check (does this run or
# input already have an item?) runs under it.
#   with_harvest_lock <src> <root> <cmd...>
with_harvest_lock() {
    local src="$1" root="$2"; shift 2
    local store="$root/.aitask-sitrep" lockdir rc=0
    if ! ensure_ignored "$root"; then
        echo "HARVEST_FAILED:$src|store_not_ignorable"
        return 1
    fi
    if ! mkdir -p "$store" 2>/dev/null || [[ ! -w "$store" ]]; then
        echo "HARVEST_FAILED:$src|store_unwritable"
        return 1
    fi
    lockdir="$store/.harvest.lockd"
    if [[ -L "$lockdir" || ( -e "$lockdir" && ! -d "$lockdir" ) ]]; then
        echo "HARVEST_FAILED:$src|harvest_lock_unusable"
        return 1
    fi
    if ! registry_lock_acquire "$lockdir" "$LOCK_TIMEOUT"; then
        echo "HARVEST_FAILED:$src|harvest_lock_busy"
        return 1
    fi
    pause_seam apply:locked
    "$@" || rc=$?
    registry_lock_release "$lockdir"
    return "$rc"
}

apply_from_buf() { feed | "$PY" "$CORE" apply "$@"; }
apply_no_stdin() { "$PY" "$CORE" apply "$@" </dev/null; }

# Run `apply` for one source with the store's harvest mutex held.
#   locked_apply <src> <root> <stdin? 0|1> <apply args...>
locked_apply() {
    local src="$1" root="$2" use_stdin="$3"; shift 3
    if [[ "$use_stdin" == 1 ]]; then
        with_harvest_lock "$src" "$root" apply_from_buf "$@" --root-canonical "$root"
    else
        with_harvest_lock "$src" "$root" apply_no_stdin "$@" --root-canonical "$root"
    fi
}

# plan, then (if there is work) apply. Prints every line but `WORK:`.
#   run_source <src> <stdin? 0|1> <source args...>
run_source() {
    local src="$1" use_stdin="$2"; shift 2
    local out rc=0 line work=""
    if [[ "$use_stdin" == 1 ]]; then
        out="$(feed | "$PY" "$CORE" plan "$@")" || rc=$?
    else
        out="$("$PY" "$CORE" plan "$@" </dev/null)" || rc=$?
    fi
    while IFS= read -r line; do
        case "$line" in
            WORK:*) work="${line#WORK:}" ;;
            "") ;;
            *) printf '%s\n' "$line" ;;
        esac
    done <<<"$out"
    if [[ "$rc" -ne 0 ]]; then
        [[ -n "$out" ]] || echo "HARVEST_FAILED:$src|plan_exit_$rc"
        return 1
    fi
    [[ -n "$work" ]] || return 0
    # The whole remainder is the root: no separator, so `|` in a path is data.
    locked_apply "$src" "$work" "$use_stdin" "$@"
}

cmd_record() {
    local id="${1:-}"; shift || true
    [[ "$id" =~ ^[0-9a-f]{8}$ ]] || err_usage "record id must be 8 lowercase hex: '$id'"
    local force=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force) force=(--force) ;;
            *) err_usage "unknown argument: $1" ;;
        esac
        shift
    done
    need_python "$id"
    run_source "$id" 0 record "$id" "${force[@]}"
}

cmd_all() {
    local root=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --root) root="${2:-}"; [[ -n "$root" ]] || err_usage "--root needs a path"; shift ;;
            *) err_usage "unknown argument: $1" ;;
        esac
        shift
    done
    [[ -z "$root" ]] || no_dotdot "$root"
    need_python all
    local out rc=0 failed=0 line
    if [[ -n "$root" ]]; then
        out="$("$PY" "$CORE" plan all --root "$root" </dev/null)" || rc=$?
    else
        out="$("$PY" "$CORE" plan all </dev/null)" || rc=$?
    fi
    if [[ "$rc" -ne 0 ]]; then
        printf '%s\n' "$out"
        return 1
    fi
    while IFS= read -r line; do
        case "$line" in
            RECORD:*) run_source "${line#RECORD:}" 0 record "${line#RECORD:}" || failed=1 ;;
            "") ;;
            *) printf '%s\n' "$line" ;;
        esac
    done <<<"$out"
    return "$failed"
}

new_run_id() {
    local id
    if [[ -n "${AITASK_SITREP_HARVEST_RUN_ID:-}" ]]; then
        [[ "$AITASK_SITREP_HARVEST_RUN_ID" =~ ^[0-9a-f]{16}$ ]] \
            || err_usage "AITASK_SITREP_HARVEST_RUN_ID must be 16 lowercase hex"
        printf '%s' "$AITASK_SITREP_HARVEST_RUN_ID"
        return 0
    fi
    id="$(od -An -N8 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n')"
    [[ "$id" =~ ^[0-9a-f]{16}$ ]] || id="$(printf '%08x%08x' "$$" "$RANDOM$RANDOM")"
    printf '%s' "${id:0:16}"
}

cmd_banner() {
    local task="" skill=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --task) task="${2:-}"; shift ;;
            --skill) skill="${2:-}"; shift ;;
            *) err_usage "unknown argument: $1" ;;
        esac
        shift
    done
    task="${task#t}"
    [[ "$task" =~ ^[1-9][0-9]*(_[1-9][0-9]*)?$ ]] || err_usage "--task must be a task id: '$task'"
    [[ -z "$skill" || "$skill" =~ ^[A-Za-z0-9_-]+$ ]] || err_usage "--skill must be a plain name"
    local run
    run="$(new_run_id)"
    # FIRST stdout line, before anything can fail: the tool-call display shows
    # a command's first output line even when it collapses the rest.
    echo "HARVEST_RUN:$run"
    need_python "run-$run"
    read_stdin "run-$run"
    run_source "run-$run" 1 banner --run "$run" --task "$task" --skill "$skill"
}

cmd_capture() {
    local root="" agent="" task="" op=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --root) root="${2:-}"; shift ;;
            --agent) agent="${2:-}"; shift ;;
            --task) task="${2:-}"; shift ;;
            --operation) op="${2:-}"; shift ;;
            *) err_usage "unknown argument: $1" ;;
        esac
        shift
    done
    [[ -n "$root" ]] || err_usage "capture needs --root"
    no_dotdot "$root"
    [[ "$root" == /* ]] || err_usage "--root must be an absolute path"
    need_python capture
    read_stdin capture
    run_source capture 1 capture --root "$root" --agent "$agent" --task "$task" --operation "$op"
}

# case <verb> ...: the review-case corpus (lib/sitrep_corpus.py, t2175_6).
# `replay --apply` writes items like a harvest, so it runs under the harvest
# mutex of its store; every other verb is a read or a plain writer call.
cmd_case() {
    [[ $# -ge 1 ]] || usage
    need_python case
    local a apply=0 out root rc=0
    for a in "$@"; do
        [[ "$a" == "--apply" ]] && apply=1
    done
    if [[ "$1" != "replay" || "$apply" == 0 ]]; then
        exec "$PY" "$CORPUS" "$@"
    fi
    out="$("$PY" "$CORPUS" lockroot "$@")" || rc=$?
    if [[ "$rc" -ne 0 ]]; then
        [[ -z "$out" ]] || printf '%s\n' "$out"
        return "$rc"
    fi
    root="${out#LOCK_ROOT:}"
    [[ "$out" == LOCK_ROOT:* && -n "$root" ]] || { echo "REPLAY_FAILED:case|lock_root"; return 1; }
    with_harvest_lock "case" "$root" "$PY" "$CORPUS" "$@" --root-canonical "$root" </dev/null
}

main() {
    [[ $# -ge 1 ]] || usage
    [[ "$LOCK_TIMEOUT" =~ ^[0-9]+$ ]] \
        || err_usage "AITASK_SITREP_HARVEST_LOCK_TIMEOUT must be a whole number of seconds"
    local verb="$1"; shift
    case "$verb" in
        record)  cmd_record "$@" ;;
        all)     cmd_all "$@" ;;
        banner)  cmd_banner "$@" ;;
        capture) cmd_capture "$@" ;;
        case)    cmd_case "$@" ;;
        -h|--help) usage ;;
        *) err_usage "unknown verb: $verb" ;;
    esac
}

main "$@"
