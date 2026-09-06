#!/usr/bin/env bash
# aitask_live_endpoint.sh - Resolve "which live agent is implementing task X?" (t1657_4).
#
# The generic half of the note mailbox's LIVE lane. Notes are its first consumer,
# NOT its owner: this script is named for the capability and contains no reference
# to any agent runtime. Composition (writer -> resolver -> adapter) belongs to the
# `aitask-note` skill (t1657_5); delivery belongs to the per-agent adapter
# procedures under live_delivery/.
#
# What it collapses: a sender used to cross-reference by hand —
#   aitask_lock.sh --check <id>   -> pid, hostname, pid_starttime
#   tmux list-panes -a            -> the pane owning that pid
#   the agent session listing     -> the session name to address
# All three become one task-centric call. If any path still needs a human to run
# `tmux list-panes` or enumerate sessions by hand, this script has failed.
#
# Usage:
#   aitask_live_endpoint.sh <task-id>        # 349, t349, 1657_4, t1657_4
#
# OUTPUT CONTRACT — exactly ONE line on stdout, always:
#   LIVE_PANE:<%pane>|<session>:<@win>.<%pane>|<pid>|agent=<family>   exit 0
#   LIVE_NONE:<reason>                                               exit 0
#   LIVE_ERROR:<reason>                                              exit 2
#
# THE ONE EXCEPTION IS `-h` / `--help`, which prints usage to stdout and exits 0:
# that invocation is addressed to a human, not to a caller. Every other usage
# error prints its help to STDERR and still emits exactly one stdout line, so a
# caller that reads the first line of stdout can never mistake prose for a
# result.
#
# LIVE_NONE is a SUCCESSFUL resolution — "there is no live endpoint" is an answer,
# not a failure — hence exit 0. LIVE_ERROR is disjoint from it and means the
# resolver itself could not run (bad usage, unresolvable task file). Callers that
# want "did we get an endpoint?" branch on the prefix; callers that want "did the
# resolver work?" branch on the exit status. Every advisory goes to stderr.
#
# The caller's durable write is unaffected by ANY outcome here: `ait note` appends
# and commits before this script is ever invoked, and no branch below can undo it.
#
# tmux is DISCOVERY infrastructure, never the transport.
# This script must not use send-keys. Keystroke injection lands in whatever UI
# state a pane happens to be in (a prompt, a shell, an editor, a half-typed
# answer), carries no agent identity or message framing, and offers no
# queued/received semantics — so delivery goes through the agent runtime's own
# cross-session mechanism, never through the pane. All tmux access goes through
# the lib/tmux_exec.sh gateway (tests/test_no_raw_tmux.sh enforces that half;
# tests/test_live_endpoint_no_sendkeys.sh enforces this one, and it requires the
# negation to sit on the same line as the verb).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/pid_anchor.sh
source "$SCRIPT_DIR/lib/pid_anchor.sh"
# shellcheck source=lib/lock_record.sh
source "$SCRIPT_DIR/lib/lock_record.sh"
# shellcheck source=lib/tmux_exec.sh
source "$SCRIPT_DIR/lib/tmux_exec.sh"

# --- Adapter registry -------------------------------------------------------
#
# Which agent families can be delivered to is DATA, not a literal in this script.
# That is what keeps the file free of any agent-runtime reference while still
# producing the `agent_unsupported` branch: the answer comes from the manifest,
# so adding a family later is one row plus one procedure file, with no edit here.
#
# Framework-owned and shipped inside .aitask-scripts/, exactly like
# gates_reference.yaml — so it needs no seed/ mirror and no aitask_setup.sh entry.
# AIT_LIVE_DELIVERY_DIR is the documented test seam: it lets a suite prove the
# manifest actually drives the decision instead of decorating it.
LIVE_DELIVERY_DIR="${AIT_LIVE_DELIVERY_DIR:-$SCRIPT_DIR/live_delivery}"
LIVE_DELIVERY_MANIFEST="$LIVE_DELIVERY_DIR/agents.txt"

# Bound on the parent walk in resolve_pane_for_pid. A process tree deeper than
# this between a lock anchor and its pane means the anchor is not a descendant of
# any pane, which `no_pane` already says.
ANCESTOR_WALK_MAX=20

usage() {
    cat <<'EOF'
Usage: aitask_live_endpoint.sh <task-id>

Resolve a task id to the live agent session implementing it.

  <task-id>   349, t349, 1657_4 or t1657_4 (both forms accepted)

Output (exactly one line):
  LIVE_PANE:<%pane>|<session>:<@win>.<%pane>|<pid>|agent=<family>   exit 0
  LIVE_NONE:<reason>                                               exit 0
  LIVE_ERROR:<reason>                                              exit 2

LIVE_NONE reasons:
  unlocked                    no lock record — nobody holds the task
  remote_host                 the lock was taken on a different machine
  holder_dead                 the holding process is provably gone
  holder_unknown              liveness could not be established (never "dead")
  agent_unknown               the task records no implementing agent yet
  agent_unsupported:<agent>   that agent family has no delivery adapter
  no_pane                     the holder is alive but owns no tmux pane here
EOF
}

# --- Canonical task id ------------------------------------------------------
#
# Two forms circulate and they are NOT interchangeable (aitask_note.sh section 0
# documents the measurement): `aitask_lock.sh --check t1669` prints NOTHING while
# `--check 1669` works, and resolve_task_file errors on a 't' prefix. Feeding a
# t-prefixed id to either helper yields a silent empty answer that would read as
# "no lock record" — a wrong answer dressed as a correct one.
#
#   CLI input : liberal   — 349, t349, 1657_4, t1657_4
#   lookup    : BARE      — 349, 1657_4        (every helper call)
canonical_bare_id() {
    local raw="${1:-}"
    raw="${raw#t}"
    [[ "$raw" =~ ^[0-9]+(_[0-9]+)*$ ]] || return 1
    printf '%s' "$raw"
}

# --- Adapter lookup ---------------------------------------------------------
#
# Echo the adapter procedure's path for <family>, or return 1 when no USABLE
# adapter is declared. Two whitespace-separated columns; '#' comments and blank
# lines ignored. Column 2 is a bare filename resolved against LIVE_DELIVERY_DIR,
# so the same manifest works under the AIT_LIVE_DELIVERY_DIR test seam and a '/'
# or '..' in it is rejected rather than followed out of the directory.
#
# A NAME MATCH IS NOT ENOUGH. `LIVE_PANE` is a promise the caller acts on: it
# means "there is a live endpoint AND something to deliver through". A truncated
# row (a family name with no second column) or a row naming a file that is not
# there would otherwise resolve to LIVE_PANE, and the caller would then have no
# procedure to run — a failure that surfaces one layer too late, after the
# durable note has already reported a live endpoint. So the procedure file must
# exist and be readable before the family counts as supported; anything less is
# `agent_unsupported`, which is exactly what it is.
#
# A missing manifest is "no family is deliverable", not an error — a truncated
# install degrades every send to the durable lane rather than crashing it.
adapter_for_family() {
    local family="${1:-}" name file _rest
    [[ -n "$family" && -r "$LIVE_DELIVERY_MANIFEST" ]] || return 1
    while read -r name file _rest; do
        [[ -z "$name" || "$name" == \#* ]] && continue
        [[ "$name" == "$family" ]] || continue
        # A row must name a procedure, and it must name one inside the delivery
        # directory: this is a data file, so a path is untrusted input.
        [[ -n "$file" ]] || return 1
        case "$file" in */*|..|.) return 1 ;; esac
        # A READABLE REGULAR FILE, not merely a readable path: `-r` alone is true
        # for a directory, so a row naming one would pass the gate and promise an
        # adapter the caller cannot read. `-f` is the half that makes "readable"
        # mean "readable AS A PROCEDURE".
        [[ -f "$LIVE_DELIVERY_DIR/$file" && -r "$LIVE_DELIVERY_DIR/$file" ]] || return 1
        printf '%s' "$LIVE_DELIVERY_DIR/$file"
        return 0
    done < "$LIVE_DELIVERY_MANIFEST"
    return 1
}

# --- PID -> pane ------------------------------------------------------------
#
# Echo "<pane_id>\t<session>:<window_id>.<pane_id>" for the pane owning <pid>, or
# return 1.
#
# The target string's shape is NOT free choice: it must match how the agent
# session listing renders a pane, because the adapter joins the two. Measured on
# this framework's own sessions, a listing row reads `tmux aitasks:@2.%2` for a
# pane whose tmux `window_index` is 3 and whose `window_id` is `@2` — so the
# middle field is `#{window_id}` (which already carries its own '@'), never
# `@#{window_index}`. Using the index would produce a target that looks right and
# matches nothing.
#
# pane_pid FIRST: the framework launches every agent as its pane's own process
# (lib/agent_launch_utils.py::launch_in_tmux passes the bare CLI command with no
# wrapper), so a lock anchored by get_session_anchor_pid rung 2 IS a pane_pid and
# hits directly. The ancestor walk is the fallback for rung 1 — an
# AIT_AGENT_PID-anchored lock whose PID is a descendant of the pane process.
#
# Only the gateway socket is searched. An agent on some other tmux server is
# invisible here and reads as `no_pane`; that is the honest boundary, since the
# framework launches every managed agent on the gateway socket.
resolve_pane_for_pid() {
    local want="${1:-}" panes ppid hops
    [[ "$want" =~ ^[0-9]+$ ]] && (( want > 0 )) || return 1

    panes="$(ait_tmux list-panes -a -F \
        "#{pane_pid}"$'\t'"#{pane_id}"$'\t'"#{session_name}:#{window_id}.#{pane_id}" \
        2>/dev/null || true)"
    [[ -n "$panes" ]] || return 1

    hops=0
    while [[ "$want" =~ ^[0-9]+$ ]] && (( want > 1 && hops <= ANCESTOR_WALK_MAX )); do
        local line
        line="$(printf '%s\n' "$panes" | awk -F'\t' -v p="$want" '$1 == p { print $2 "\t" $3; exit }')"
        if [[ -n "$line" ]]; then
            printf '%s' "$line"
            return 0
        fi
        ppid="$(ps -o ppid= -p "$want" 2>/dev/null | tr -d '[:space:]')"
        [[ "$ppid" =~ ^[0-9]+$ ]] || return 1
        want="$ppid"
        hops=$(( hops + 1 ))
    done
    return 1
}

# --- Main -------------------------------------------------------------------

main() {
    local raw="${1:-}"
    # `--help` is the only invocation addressed to a human, so it is the only one
    # allowed to put prose on stdout. Every other usage error keeps stdout to its
    # single result line — a caller reading the first line must never find
    # `Usage:` there.
    case "$raw" in
        -h|--help) usage; exit 0 ;;
    esac
    [[ $# -eq 1 && -n "$raw" ]] || { usage >&2; echo "LIVE_ERROR:usage"; exit 2; }

    local bare
    bare="$(canonical_bare_id "$raw")" || { echo "LIVE_ERROR:bad_task_id"; exit 2; }

    # 1. The lock record. Its stdout IS the record; absence is exit 1 + empty.
    lock_record_read "$bare" || { echo "LIVE_NONE:unlocked"; exit 0; }

    # 2. Host scope. The lock records `hostname` precisely so a cross-machine
    #    holder degrades to the durable lane instead of being chased.
    if [[ "$LOCK_REC_HOST" != "$(hostname)" ]]; then
        echo "LIVE_NONE:remote_host"; exit 0
    fi

    # 3. Liveness. THREE states, and `unknown` is never collapsed into `dead` —
    #    that conflation is the t1465 defect class. A lock written before the PID
    #    anchor existed carries no `pid:` at all; it arrives here as an empty PID
    #    and answers `unknown`, which is the fail-safe direction.
    local liveness
    liveness="$(lock_holder_liveness "$LOCK_REC_PID" "${LOCK_REC_TOKEN:--}" "${LOCK_REC_KIND:-proc}")"
    case "$liveness" in
        dead)    echo "LIVE_NONE:holder_dead";    exit 0 ;;
        unknown) echo "LIVE_NONE:holder_unknown"; exit 0 ;;
    esac

    # 4. The implementing agent family. `implemented_with` is written by Agent
    #    Attribution at Step 7 while the lock is claimed at Step 4, so during
    #    planning a task is legitimately Implementing, locked, and blank here.
    #    That window must read as UNKNOWN -> durable lane, never as an error.
    local task_file agent_string family
    if ! task_file="$(resolve_task_file "$bare" 2>/dev/null)" || [[ -z "$task_file" ]]; then
        echo "LIVE_ERROR:task_not_found:$bare"; exit 2
    fi
    agent_string="$(extract_implemented_with "$task_file")"
    family="${agent_string%%/*}"
    if [[ -z "$family" ]]; then
        echo "LIVE_NONE:agent_unknown"; exit 0
    fi
    # Deliberately NOT parse_agent_string: it die()s on an unrecognised agent,
    # which is exactly the input this branch exists to answer for.
    if ! adapter_for_family "$family" >/dev/null; then
        echo "LIVE_NONE:agent_unsupported:$family"; exit 0
    fi

    # 5. The pane. Everything above is agent-runtime independent, and so is this.
    local pane_line pane_id target
    if ! pane_line="$(resolve_pane_for_pid "$LOCK_REC_PID")"; then
        echo "LIVE_NONE:no_pane"; exit 0
    fi
    pane_id="${pane_line%%$'\t'*}"
    target="${pane_line#*$'\t'}"

    printf 'LIVE_PANE:%s|%s|%s|agent=%s\n' "$pane_id" "$target" "$LOCK_REC_PID" "$family"
}

main "$@"
