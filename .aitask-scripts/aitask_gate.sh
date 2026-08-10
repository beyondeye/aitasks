#!/usr/bin/env bash
# aitask_gate.sh - Gate ledger substrate (t635_1, Phase 1).
#
# Records and derives the per-task "Gate Runs" ledger: append-only marker-first
# blockquotes in the task body, with current state derived back-to-front (last
# run per gate wins). See aidocs/gates/aitask-gate-framework.md for the contract.
#
# This is a FULL-PATH helper, not an `ait` dispatcher command (Phase 1 has no
# human consumer — `append` is called by verifiers / task-workflow checkpoint
# recording; `status`/`list` are read by tooling). The user-facing `ait gate` /
# `ait gates` surface arrives later with its first real human command.
#
# Subcommands:
#   append [--only-if-running <run-id>] <task-id> <gate> <status> [k=v ...]
#                                                Append a gate-run block (the
#                                                guard makes it a no-op once a
#                                                terminal block exists for run-id)
#   status <task-id>                             Print derived per-gate state
#   list   <task-id>                             List declared gates (+ registry)
#   deps-unblock <task-id>                       Decide if this task releases its
#                                                dependents (t635_3; python-only;
#                                                re-validates signatures, t1416)
#   deps-unblock-batch < paths                   Same decision for a whole list of
#                                                task FILE PATHS on stdin, in one
#                                                process (t1472; python-only)
#   archive-ready <task-id>                      Decide if this task may archive
#                                                (t635_4; python-only)
#   resume-point <task-id>                       Derive task-workflow re-entry
#                                                stage (t635_5; python-only)
#   workflow-phase <task-id> [--screen <f>]      Advisory workflow-phase signal
#     [--awaiting-input yes|no|unknown]          for the shadow (t1420;
#     [--kind <k>] [--agent <a>]                 python-only). Advisory ONLY —
#     [--profiles-dir <d>]                       never gate on it.
#   effective-gates <task-id> [--profile <f>]    Resolved declared set (t635_14)
#   has-gates-field <task-id>                    Exit 0 if `gates:` is present
#   should-self-record <task-id> <gate>          Exit 0 if the workflow (not the
#                                                orchestrator) records the gate
#   active <task-id> <gate>                      Exit 0 if the gate is enforced
#   materialize-active <task-id> --profile <f>   Write the active_gates tuple
#                                                (t635_33)
#   active-gates-status <task-id> --profile <f>  Tuple provenance + freshness
#   procedure-gates <task-id>                    Unmet kind:procedure gates
#   begin-procedure <task-id> <gate>             Open a procedure-gate run
#   sync-registry [--dry-run] [--registry <f>]   Additively reconcile the project
#                 [--reference <f>]              registry against the canonical
#                                                reference (t635_34; python-only)
#
# Primary path is bash + POSIX awk. The Python module lib/gate_ledger.py is the
# documented fallback (drop-in, identical output): used when AIT_GATES_BACKEND=python
# or when the awk scan fails. Keep the two output formats byte-identical.
# EXCEPTIONS — python-only verbs (no bash path exists): deps-unblock,
# deps-unblock-batch, archive-ready, resume-point, workflow-phase,
# effective-gates, procedure-gates, sync-registry.
#
# append keys: run, status, attempt, duration, type (marker line);
#              verifier, result, log, note (body lines). Others are ignored.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# NOTE: lib/registry_lock.sh is sourced LAZILY inside cmd_sync_registry, not
# here. Only that one verb needs it, and several tests scaffold a fake
# .aitask-scripts/lib/ by hand-copying a subset of libs — an unconditional
# source at startup makes every other verb crash in those fixtures with
# "No such file or directory" (see the source-on-startup rule in
# aidocs/framework/shell_conventions.md).

TASK_DIR="${TASK_DIR:-aitasks}"
GATE_LEDGER_PY="$SCRIPT_DIR/lib/gate_ledger.py"
WORKFLOW_PHASE_PY="$SCRIPT_DIR/lib/workflow_phase.py"
REGISTRY="${TASK_DIR}/metadata/gates.yaml"
# Canonical gate registry shipped with the framework. Overridable so tests can
# exercise sync-registry against a doctored reference: the test fixtures symlink
# the real .aitask-scripts/, so without this every case would run against the
# live reference and the edge cases would be unwritable (t635_34).
GATES_REFERENCE="${AIT_GATES_REFERENCE:-$SCRIPT_DIR/gates_reference.yaml}"

VALID_STATUSES="pass fail pending running skip error"
# Runs that reached a VERDICT — the ones that CLOSE an attempt. `running` and
# `pending` are in-progress bookkeeping and never consume an attempt number: a
# completed attempt leaves a `running` marker AND its terminal marker, so
# counting every marker advanced the counter by 2 per attempt (t1262). Mirrors
# TERMINAL_STATUSES in lib/gate_ledger.py; the bash<->python parity cases in
# tests/test_gate_ledger.sh keep the two honest.
TERMINAL_STATUSES="pass fail skip error"

# --- Helpers ---------------------------------------------------------------

gate_icon() {
    case "$1" in
        pass)    printf '✅' ;;
        fail)    printf '❌' ;;
        pending) printf '⏸' ;;
        running) printf '🔄' ;;
        skip)    printf '⏭' ;;
        error)   printf '⚠' ;;
        *)       printf '⚠' ;;
    esac
}

is_valid_status() {
    local s
    for s in $VALID_STATUSES; do [[ "$1" == "$s" ]] && return 0; done
    return 1
}

is_terminal_status() {
    local s
    for s in $TERMINAL_STATUSES; do [[ "$1" == "$s" ]] && return 0; done
    return 1
}

# Per-task mkdir lock (portable; mirrors aitask_create.sh acquire_child_lock).
# Serializes concurrent appends to the same task file.
_GATE_LOCK_DIR=""
acquire_gate_lock() {
    local key="$1"
    local lock_dir="/tmp/aitask_gate_lock_${key}"
    local max_retries=20 retry=0
    while ! mkdir "$lock_dir" 2>/dev/null; do
        retry=$((retry + 1))
        if [[ $retry -ge $max_retries ]]; then
            die "Failed to acquire gate append lock for $key after $max_retries attempts"
        fi
        if [[ -d "$lock_dir" ]]; then
            local lock_mtime lock_age
            if lock_mtime=$(stat -c %Y "$lock_dir" 2>/dev/null || stat -f %m "$lock_dir" 2>/dev/null); then
                lock_age=$(( $(date +%s) - lock_mtime ))
                if [[ "$lock_age" -gt 120 ]]; then
                    # Single-winner reclaim: rename is atomic, so only one
                    # waiter can claim the stale dir, and a lock re-acquired
                    # at this path after the rename is never touched. The
                    # preflight rm clears a quarantine dir leaked by a dead
                    # PID-reused process (mv onto an existing dir would nest
                    # instead of replacing).
                    local stale_dest="${lock_dir}.stale.$$"
                    rm -rf "$stale_dest" 2>/dev/null || true
                    if mv "$lock_dir" "$stale_dest" 2>/dev/null; then
                        warn "Removing stale gate lock for $key (age: ${lock_age}s)"
                        rmdir "$stale_dest" 2>/dev/null || true
                    fi
                    continue
                fi
            else
                # Lock vanished between -d and stat — retry mkdir immediately.
                continue
            fi
        fi
        sleep 0.3
    done
    _GATE_LOCK_DIR="$lock_dir"
}

release_gate_lock() {
    [[ -n "$_GATE_LOCK_DIR" ]] && rmdir "$_GATE_LOCK_DIR" 2>/dev/null || true
    _GATE_LOCK_DIR=""
}

delegate_python() {
    local py
    py="$(resolve_python 2>/dev/null || true)"
    [[ -z "$py" ]] && return 1
    "$py" "$GATE_LEDGER_PY" "$@"
}

# Second delegator: delegate_python is hardwired to gate_ledger.py, and the
# phase seam is its own module (t1420).
delegate_python_phase() {
    local py
    py="$(resolve_python 2>/dev/null || true)"
    [[ -z "$py" ]] && return 1
    "$py" "$WORKFLOW_PHASE_PY" "$@"
}

# Return 0 iff the LAST marker carrying run=<run-id> has status=running — i.e. no
# terminal block has been appended for that run yet. Used by the `--only-if-running`
# conditional append (t635_11) so the orchestrator's terminal-block append is a
# no-op when the verifier already appended its own block for the same run id.
_gate_run_is_running() {
    local file="$1" rid="$2" last
    last="$(awk -v rid="$rid" '
        /^>[[:space:]]*\*\*/ && /gate:/ {
            if (match($0, /run=[^ ]+/)) {
                r = substr($0, RSTART + 4, RLENGTH - 4)
                if (r == rid && match($0, /status=[A-Za-z]+/)) {
                    last = substr($0, RSTART + 7, RLENGTH - 7)
                }
            }
        }
        END { print last }
    ' "$file" 2>/dev/null)"
    [[ "$last" == "running" ]]
}

# _gate_run_state <file> <gate> — the ledger facts a new run needs, in one pass:
#
#   OPEN:<run-id>|<attempt>    (both empty when no run is live)
#   TERMINAL:<n>
#
# A run is LIVE when its latest marker is `running` — the SAME rule
# _gate_run_is_running applies per run id, which is what makes an adopted run one
# that `append --only-if-running` can actually close. Any later marker for that
# run id (terminal OR `pending`) ends the window. <n> counts TERMINAL markers
# only, so the caller's `n + 1` gives the next attempt ORDINAL: the `running`
# block a run opens and the terminal block that closes it share one number
# (t1262). A marker with no parseable status= counts as neither — malformed data
# must not inflate the counter. Mirrors gate_ledger.live_run + next_attempt.
#
# Honors the documented AIT_GATES_BACKEND escape hatch so `begin-procedure`'s
# READ half is substitutable too, not just its append.
#
# 2-arg match() only -- the gawk-only 3-argument form is a hard syntax error
# under BSD awk, and tests/test_gate_ledger.sh greps this file for it. That grep
# also trips on a 2-arg match() sharing a line with a 3-arg substr(), so the
# RSTART/RLENGTH extractions below stay on their own lines.
_gate_run_state() {
    local file="$1" gate="$2"
    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python run-state "$file" "$gate" && return 0
        die "python gate_ledger run-state failed"
    fi
    awk -v g="$gate" -v terms=" $TERMINAL_STATUSES " '
        /^>[[:space:]]*\*\*/ && /gate:/ {
            if (!match($0, /gate:[A-Za-z0-9_]+/)) next
            if (substr($0, RSTART + 5, RLENGTH - 5) != g) next
            if (!match($0, /status=[A-Za-z]+/)) next
            st = substr($0, RSTART + 7, RLENGTH - 7)
            rid = ""
            if (match($0, /run=[^ ]+/)) {
                rid = substr($0, RSTART + 4, RLENGTH - 4)
            }
            if (index(terms, " " st " ") > 0) n++
            if (rid == "") next
            if (!(rid in seen)) { seen[rid] = 1; order[++k] = rid }
            # EVERY status updates the run latest — not just terminal/running.
            # A `pending` marker for a live run id closes the live-run window,
            # because that is exactly what _gate_run_is_running (and therefore
            # `append --only-if-running`) sees. Recording only terminal/running
            # let this scan adopt a run whose closer is a silent no-op, so the
            # gate could never be closed (t1262).
            last[rid] = st
            if (st == "running") {
                if (match($0, /attempt=[0-9]+/)) {
                    att[rid] = substr($0, RSTART + 8, RLENGTH - 8)
                }
            }
        }
        END {
            open_rid = ""
            for (i = k; i >= 1; i--) if (last[order[i]] == "running") { open_rid = order[i]; break }
            printf "OPEN:%s|%s\n", open_rid, (open_rid == "" ? "" : att[open_rid])
            printf "TERMINAL:%d\n", n + 0
        }
    ' "$file" 2>/dev/null
}

# --- append ----------------------------------------------------------------

cmd_append() {
    # Optional leading guard: `--only-if-running <run-id>` makes the append a
    # no-op when a terminal block already exists for <run-id> (t635_11). The
    # check + append run under the SAME per-task lock, so they are atomic.
    local only_if_running=""
    if [[ "${1:-}" == "--only-if-running" ]]; then
        only_if_running="${2:-}"
        [[ -z "$only_if_running" ]] && \
            die "Usage: aitask_gate.sh append --only-if-running <run-id> <task-id> <gate> <status> [k=v ...]"
        shift 2
    fi

    local task_id="${1:-}" gate="${2:-}" status="${3:-}"
    [[ -z "$task_id" || -z "$gate" || -z "$status" ]] && \
        die "Usage: aitask_gate.sh append [--only-if-running <run-id>] <task-id> <gate> <status> [k=v ...]"
    is_valid_status "$status" || \
        die "Invalid status '$status' (one of: $VALID_STATUSES)"
    shift 3

    local file
    file="$(resolve_task_file "$task_id")"

    local key="${task_id//\//_}"
    acquire_gate_lock "$key"
    # shellcheck disable=SC2064
    trap 'release_gate_lock' EXIT

    # `--only-if-running` guard (atomic under the lock): if a terminal block was
    # already written for this run id, do nothing. Checked ONCE here, for both
    # backends — it used to be written twice, once per branch.
    if [[ -n "$only_if_running" ]] && ! _gate_run_is_running "$file" "$only_if_running"; then
        release_gate_lock; trap - EXIT
        return 0
    fi

    _gate_append_locked "$file" "$gate" "$status" "$@"
    local rc=$?

    release_gate_lock
    trap - EXIT
    return "$rc"
}

# Append one gate-run block. ASSUMES THE CALLER HOLDS THE GATE LOCK for this
# task — it never locks and never unlocks, so `cmd_begin_procedure` can hold the
# lock across its live-run check and this append (the mkdir lock is not
# reentrant, so it cannot call cmd_append). Echoes the block it wrote.
_gate_append_locked() {
    local file="$1" gate="$2" status="$3"
    shift 3

    # The documented AIT_GATES_BACKEND escape hatch lives HERE, not in
    # cmd_append, so EVERY entry point reaches it — including begin-procedure,
    # whose `running` block would otherwise stay bash-only under the python
    # backend.
    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python append "$file" "$gate" "$status" "$@" \
            || die "python gate_ledger append failed"
        return 0
    fi

    # Parse k=v fields into marker / body buckets.
    local f_run="" f_attempt="" f_duration="" f_type=""
    local b_verifier="" b_result="" b_log="" b_note=""
    local kv k v
    for kv in "$@"; do
        if [[ "$kv" != *"="* ]]; then warn "Ignoring malformed key=value arg: $kv"; continue; fi
        k="${kv%%=*}"; v="${kv#*=}"
        case "$k" in
            run) f_run="$v" ;;
            attempt) f_attempt="$v" ;;
            duration) f_duration="$v" ;;
            type) f_type="$v" ;;
            verifier) b_verifier="$v" ;;
            result) b_result="$v" ;;
            log) b_log="$v" ;;
            note) b_note="$v" ;;
            status) ;;  # status is positional — ignore a stray status= arg
            *) warn "Ignoring unsupported gate field: $k" ;;
        esac
    done

    # run id (ISO-8601-Z). date -u + this format is portable (no -d).
    [[ -z "$f_run" ]] && f_run="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # attempt: explicit wins; else auto for any TERMINAL status = terminal runs
    # + 1 (t1262). `running`/`pending` get no auto number — begin-procedure
    # supplies the running block's explicitly, and its terminal closer inherits
    # the same value because non-terminal markers do not advance the count.
    if [[ -z "$f_attempt" ]] && is_terminal_status "$status"; then
        f_attempt="$(( $(_gate_run_state "$file" "$gate" | sed -n 's/^TERMINAL://p') + 1 ))"
    fi

    local icon
    icon="$(gate_icon "$status")"

    # Build marker line.
    local marker="> **${icon} gate:${gate}** run=${f_run} status=${status}"
    [[ -n "$f_attempt" ]]  && marker="${marker} attempt=${f_attempt}"
    [[ -n "$f_duration" ]] && marker="${marker} duration=${f_duration}"
    [[ -n "$f_type" ]]     && marker="${marker} type=${f_type}"

    # Build body lines (fixed order: verifier, result, log, note).
    local body=""
    [[ -n "$b_verifier" ]] && body="${body}> Verifier: \`${b_verifier}\`"$'\n'
    [[ -n "$b_result" ]]   && body="${body}> Result: ${b_result}"$'\n'
    [[ -n "$b_log" ]]      && body="${body}> Log: \`${b_log}\`"$'\n'
    [[ -n "$b_note" ]]     && body="${body}> Note: ${b_note}"$'\n'
    body="${body%$'\n'}"  # strip trailing newline

    # Ensure section exists (created at EOF — Gate Runs is the terminal section).
    local need_section=1
    grep -qE '^##[[:space:]]+Gate Runs[[:space:]]*$' "$file" && need_section=0

    local tmp
    tmp="$(dirname "$file")/.aitask_gate.$$.tmp"
    {
        cat "$file"
        # Ensure a trailing newline before appending.
        [[ -n "$(tail -c1 "$file" 2>/dev/null)" ]] && echo
        if [[ $need_section -eq 1 ]]; then
            echo
            echo "## Gate Runs"
            echo "<!-- Appended by the gate framework. Do not edit by hand; use \`./.aitask-scripts/aitask_gate.sh append\` for corrections. -->"
        fi
        echo
        echo "$marker"
        if [[ -n "$body" ]]; then
            echo ">"
            printf '%s\n' "$body"
        fi
    } > "$tmp"
    mv "$tmp" "$file"

    # Echo the appended block (marker + body) for caller confirmation.
    printf '%s\n' "$marker"
    [[ -n "$body" ]] && { printf '>\n'; printf '%s\n' "$body"; }
    return 0
}

# --- derived ledger state (shared by `status` and `recorded-pass`) ----------

# _derive_gate_runs_table <file>
#
# The single bash-side derivation of the ledger's CURRENT state: one row per
# gate, `<gate>US<status>US<attempt>US<run>` (US = \037), in first-seen order,
# applying the same last-marker-wins rule as gate_ledger.derive_gate_runs().
# Both `status` (which formats every row) and `recorded-pass` (which tests one
# row) consume this, so the two can never derive a different current status for
# the same ledger.
#
# The separator must NOT be a tab: bash treats IFS whitespace (space/tab/
# newline) runs as a single delimiter, so `read` would silently collapse the
# empty `attempt` field of a skip/pending run and shift `run` into its place.
# \037 is non-whitespace, so empty fields survive — and it cannot occur in a
# gate name, status, attempt or run id.
#
# Exit: 0 on success (empty output = empty ledger), nonzero if awk failed —
# callers then fall back to the python backend.
_derive_gate_runs_table() {
    local file="$1"
    awk '
        /^>[[:space:]]*\*\*/ && /gate:/ {
            line = $0
            if (!match(line, /gate:[A-Za-z0-9_]+/)) next
            g = substr(line, RSTART + 5, RLENGTH - 5)
            st = "?"
            if (match(line, /status=[A-Za-z]+/)) {
                st = substr(line, RSTART + 7, RLENGTH - 7)
            }
            at = ""
            if (match(line, /attempt=[0-9]+/)) {
                at = substr(line, RSTART + 8, RLENGTH - 8)
            }
            rn = ""
            if (match(line, /run=[^ ]+/)) {
                rn = substr(line, RSTART + 4, RLENGTH - 4)
            }
            status_of[g] = st; attempt_of[g] = at; run_of[g] = rn
            if (!(g in seen)) { order[++n] = g; seen[g] = 1 }
        }
        END {
            for (i = 1; i <= n; i++) {
                g = order[i]
                printf "%s\037%s\037%s\037%s\n", g, status_of[g], attempt_of[g], run_of[g]
            }
        }
    ' "$file" 2>/dev/null
}

# --- status ----------------------------------------------------------------

cmd_status() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh status <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"

    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python status "$file"
        return $?
    fi

    local table
    if table="$(_derive_gate_runs_table "$file")"; then
        local g st at rn extra line
        while IFS=$'\037' read -r g st at rn; do
            if [[ -z "$g" ]]; then continue; fi
            extra=""
            if [[ -n "$at" ]]; then extra="attempt $at"; fi
            if [[ -n "$rn" ]]; then extra="${extra:+$extra, }run $rn"; fi
            line="$g: $st"
            if [[ -n "$extra" ]]; then line="$line ($extra)"; fi
            printf '%s\n' "$line"
        done <<< "$table"
        return 0
    fi

    # awk failed — fall back to python.
    delegate_python status "$file"
}

# --- recorded-pass ---------------------------------------------------------

# recorded-pass: decision verb (t1380). Exit 0 iff <gate>'s CURRENT derived run
# (last-marker-wins) has status `pass`; exit 1 otherwise — absent, fail, skip,
# pending, running or error.
#
# The strict `== pass` predicate deliberately mirrors gate_ledger.resume_point()
# and NOT the module-wide SATISFIED_STATUSES = {pass, skip} that archive-ready /
# deps-unblock use: a `skip` is "not applicable", which is not an approval.
#
# Degrades to exit 1 ("not recorded") when neither backend can derive the state.
# Both consumers are safe under that degrade: the Approved-Plan Stop Sequence
# then records a harmless duplicate, and the Task Abort Procedure skips a
# demotion that cannot matter because resume-point degrades to PLAN too.
cmd_recorded_pass() {
    local task_id="${1:-}" gate="${2:-}"
    [[ -z "$task_id" || -z "$gate" ]] && die "Usage: aitask_gate.sh recorded-pass <task-id> <gate>"
    local file
    file="$(resolve_task_file "$task_id")"

    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python recorded-pass "$file" "$gate"
        return $?
    fi

    local table
    table="$(_derive_gate_runs_table "$file")" || {
        delegate_python recorded-pass "$file" "$gate"
        return $?
    }

    local g st rest
    while IFS=$'\037' read -r g st rest; do
        if [[ "$g" == "$gate" && "$st" == "pass" ]]; then
            return 0
        fi
    done <<< "$table"
    return 1
}

# --- list ------------------------------------------------------------------

# Read a gate's type/description from the registry (POSIX awk; 2-level parse).
# Output: "<type>\t<description>" (either may be empty).
registry_lookup() {
    local gate="$1"
    [[ -f "$REGISTRY" ]] || { printf '\t'; return 0; }
    awk -v g="$gate" '
        # Indented "name:" with no value is a gate header.
        match($0, /^[ \t]+[A-Za-z0-9_]+:[ \t]*$/) {
            name = $0; sub(/:[ \t]*$/, "", name); sub(/^[ \t]+/, "", name)
            cur = (name == g) ? 1 : 0; next
        }
        cur && match($0, /^[ \t]+type:/) {
            v = $0; sub(/^[ \t]+type:[ \t]*/, "", v); gsub(/^"|"$/, "", v); type = v
        }
        cur && match($0, /^[ \t]+description:/) {
            v = $0; sub(/^[ \t]+description:[ \t]*/, "", v); gsub(/^"|"$/, "", v); desc = v
        }
        END { print type "\t" desc }
    ' "$REGISTRY"
}

cmd_list() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh list <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"

    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python list "$file" "$REGISTRY"
        return $?
    fi

    local gates
    gates="$(read_yaml_list "$file" gates)"
    if [[ -z "$gates" ]]; then
        echo "(no gates declared)"
        return 0
    fi

    local g meta gtype gdesc line
    while IFS= read -r g; do
        [[ -z "$g" ]] && continue
        meta="$(registry_lookup "$g")"
        gtype="${meta%%$'\t'*}"
        gdesc="${meta#*$'\t'}"
        line="$g"
        [[ -n "$gtype" ]] && line="$line [$gtype]"
        [[ -n "$gdesc" ]] && line="$line - $gdesc"
        printf '%s\n' "$line"
    done <<< "$gates"
}

# deps-unblock: decide whether this task releases its dependents (t635_3).
# Python-only: the decision combines the registry `blocks_dependents` flag, the
# per-task `also_blocks_dependents` list, and ledger derivation, so it delegates
# to lib/gate_ledger.py rather than re-implementing the registry-flag + two-list
# logic in awk. Prints one of: SATISFIED | BLOCKED:<csv> | NO_GATES. If python is
# unavailable, degrades to NO_GATES so callers fall back to today's
# file-existence behavior.
#
# Single-task callers and tests only. `aitask_ls.sh` used to invoke this as ONE
# SUBPROCESS PER gated active task on every `ait ls` (190 of them, ~46ms each,
# = 9.7s of an 18.9s run in the framework repo itself); since t1472 it calls
# `deps-unblock-batch` below instead, which decides the whole candidate list in
# one process. Anything added on THIS path is still multiplied by N for any
# caller that loops over it — prefer the batch verb for list-shaped work.
#
# Since t1416 the decision also RE-VALIDATES a code-bound signature: a required
# gate whose ledger reads `pass` but whose witness was signed against different
# code counts as unsatisfied, because `review_approved` / `merge_approved` are
# both `blocks_dependents: true` and the two code-bound gates — a dependent must
# not build on code the reviewer never approved. Cost is bounded by the no-git
# pre-filter: a task with no stamped witness pays nothing (~2us), and only a
# witness-carrying task shells out to git (~5ms). Linear in the number of SIGNED
# tasks, not in N.
cmd_deps_unblock() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh deps-unblock <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"
    delegate_python deps-unblock "$file" "$REGISTRY" || echo "NO_GATES"
}

# deps-unblock-batch: the batched twin of deps-unblock (t1472). Reads task FILE
# PATHS on stdin (one per line, already resolved — no resolve_task_file pass) and
# prints `<decision>\t<path>` per NON-EMPTY input line, in input order (blank
# lines are skipped and produce no row — key off the echoed path rather than the
# line position). The path round-trips so the CALLER keeps ownership of id
# normalization; nothing here needs to agree with bash about how a filename maps
# to a task id.
#
# No `|| echo NO_GATES` fallback: on a python-unavailable failure the caller sees
# NO output, which is exactly equivalent to N x NO_GATES (no task enters the
# dep-satisfied set) — the same degradation the per-task verb produces.
#
# Exit status passes through: 0 = every row decided, 1 = registry setup failed
# and every row is a conservative NO_GATES (rows are still printed first).
#
# NOTE: `aitask_ls.sh` discards this verb's stderr AND ignores its exit status,
# because in both failure shapes the rows it reads are already safe. A systematic
# failure is therefore INVISIBLE in `ait ls` output — "nothing is gated" and "the
# decider is broken" look identical there. Diagnose by running the verb by hand
# with stderr attached:
#   printf '%s\n' aitasks/t123_x.md | ./.aitask-scripts/aitask_gate.sh deps-unblock-batch
cmd_deps_unblock_batch() {
    delegate_python deps-unblock-batch "$REGISTRY"
}

# archive-ready: decide whether this task may archive (t635_4). Python-only
# (parallels deps-unblock — a new low-frequency decision, only at archival).
# Prints one of: ALL_PASS (every declared gate passed), BLOCKED:<csv> (declared
# gates not all pass), or NO_GATES (no declared gates → archive as today). If
# python is unavailable, degrades to NO_GATES so archival proceeds as today.
#
# The registry is passed so the decision also RE-VALIDATES code-bound human-gate
# signatures (t1409): a gate whose ledger says `pass` still blocks when its
# `ait gate pass` witness was signed against a different code state. This verb
# only REPORTS that — recording the resulting `pending` is `ait gates run`'s job
# (the single writer of observed human-gate blocks).
cmd_archive_ready() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh archive-ready <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"
    delegate_python archive-ready "$file" "$REGISTRY" || echo "NO_GATES"
}

# procedure-gates: list the task's declared PROCEDURE-BACKED gates (kind:
# procedure) that are NOT terminal-satisfied (t635_19) — one per line, empty if
# none. The attended dispatch seam (task-workflow Step 8 / aitask-resume) runs
# each such gate's skill. Python-only; degrades to empty (no dispatch) if python
# is unavailable.
cmd_procedure_gates() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh procedure-gates <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"
    delegate_python procedure-gates "$file" "$REGISTRY" || true
}

# resume-point: derive the task-workflow re-entry stage from the recorded
# checkpoint ledger (t635_5). Python-only (parallels archive-ready). Keys off the
# recorded plan_approved / review_approved runs, NOT the declared `gates:` field.
# Prints one of: PLAN (nothing durable recorded → plan from scratch),
# IMPLEMENT (plan approved, review pending → resume implementation), or
# POSTIMPL (reviewed → resume at post-implementation). If python is unavailable,
# degrades to PLAN so the workflow plans from scratch as today.
cmd_resume_point() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh resume-point <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"
    delegate_python resume-point "$file" || echo "PLAN"
}

# workflow-phase: the ADVISORY workflow-phase signal for the shadow companion
# (t1420). Python-only. Prints ONE `|`-delimited status line; see
# lib/workflow_phase.py format_signal. A stdout-token verb like resume-point —
# NOT one of gate-cli.md's exit-code decision verbs.
#
# This is a HINT that changes a default, never a check that changes what is
# permitted: no caller may refuse an action because of the value it reads here.
#
# Screen tiers are suppressed unless the caller asserts currency with
# --awaiting-input yes, so the bare `workflow-phase <id>` form is purely
# ledger-derived and cannot be poisoned by stale scrollback. Degrades to an
# all-UNKNOWN line when python is unavailable.
cmd_workflow_phase() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh workflow-phase <task-id> [--screen <f>] [--awaiting-input yes|no|unknown] [--kind <k>] [--agent <a>] [--profiles-dir <d>]"
    shift
    local file
    file="$(resolve_task_file "$task_id")"
    delegate_python_phase signal "$file" "$@" \
        || echo "PHASE:UNKNOWN|WAITING:UNKNOWN|SOURCE:none|CONSULTED:-|RECORDING:unknown|DETAIL:phase signal unavailable"
}

# effective-gates: resolve a task's effective gate set (t635_14). The task's
# literal `gates:` field wins when present (even `[]`); otherwise fall back to the
# active profile's `default_gates` (when --profile names a readable file). Used by
# the task-workflow producer trigger in the read-only planning window. Python-only;
# degrades to empty output (no gates → producer skipped) when python is
# unavailable. Prints one gate per line.
cmd_effective_gates() {
    local task_id="" profile=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --profile) profile="${2:-}"; shift 2 ;;
            *) task_id="$1"; shift ;;
        esac
    done
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh effective-gates <task-id> [--profile <file>]"
    local file
    file="$(resolve_task_file "$task_id")"
    delegate_python effective-gates "$file" "$profile" || true
}

# --- Active-gates tuple (t635_33) ------------------------------------------
#
# The profile renders a gate-machinery ceiling (`rendered_gates`, defaulting to
# `default_gates`); the task's `gates:` selects within it. The profile-filtered
# result is persisted at claim time as an atomic four-field tuple
# (active_gates / active_gates_filtered / active_gates_profile /
# active_gates_digest) that every enforcer consumes. The DECISION verbs below
# (`active`, `has-gates-field`, `should-self-record`) are pure bash — always
# available, clean 0/1 exit, no python-availability ambiguity. The ACTION /
# introspection verbs (`materialize-active`, `active-gates-status`) delegate the
# full compute to lib/gate_ledger.py `compute-active` — the single compute
# implementation — passing the t1156 manual-verification allowlist from
# task_utils.sh so there is one source for it.

# 12-hex sha256 of a string — byte-identical twin of gate_ledger._hash12
# (cross-checked by tests/test_gate_active_gates.sh).
_gate_hash12() {
    local s="$1" hex
    if command -v sha256sum >/dev/null 2>&1; then
        hex="$(printf '%s' "$s" | sha256sum | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
        hex="$(printf '%s' "$s" | shasum -a 256 | awk '{print $1}')"
    elif command -v openssl >/dev/null 2>&1; then
        hex="$(printf '%s' "$s" | openssl dgst -sha256 | awk '{print $NF}')"
    else
        die "No sha256 tool available (need sha256sum, shasum, or openssl)"
    fi
    printf '%s' "${hex:0:12}"
}

# Key-presence oracle: exit 0 iff <file> declares <key>: at all (even `[]`).
# Scans only the frontmatter of a fenced markdown file; scans the whole file
# when unfenced (profile YAML).
_yaml_has_key() {
    local file="$1" key="$2"
    awk -v k="$key" '
        NR == 1 && $0 == "---" { fenced = 1; next }
        fenced && $0 == "---" { exit }
        index($0, k ":") == 1 { found = 1; exit }
        END { exit found ? 0 : 1 }
    ' "$file"
}

# CSV of a YAML list field ("" when absent/empty) — matches the python
# ",".join() canonical form used in the digest inputs.
_yaml_list_csv() {
    read_yaml_list "$1" "$2" | paste -sd, -
}

# Validate the two digest halves checkable WITHOUT a profile: gates-half vs the
# current raw `gates:` field, outputs-half vs the stored tuple values. Mirrors
# gate_ledger._digest_profileless_halves_match.
_digest_halves_ok() {
    local file="$1" digest g_half o_half gates_input outputs_input
    digest="$(read_yaml_field "$file" active_gates_digest)"
    [[ "$digest" =~ ^[0-9a-f]{12}\.[0-9a-f]{12}\.[0-9a-f]{12}$ ]] || return 1
    g_half="${digest%%.*}"
    o_half="${digest##*.}"
    if _yaml_has_key "$file" gates; then
        gates_input="gates=$(_yaml_list_csv "$file" gates)"
    else
        gates_input="gates=absent"
    fi
    outputs_input="active=$(_yaml_list_csv "$file" active_gates)|filtered=$(_yaml_list_csv "$file" active_gates_filtered)"
    [[ "$(_gate_hash12 "$gates_input")" == "$g_half" \
       && "$(_gate_hash12 "$outputs_input")" == "$o_half" ]]
}

# The task's enforced gate set as a CSV: the validated `active_gates` tuple when
# present and intact, else the raw `gates:` fallback (declared intent — the
# pre-materialization behavior). Mirrors gate_ledger.read_active_tuple_from_text
# so bash and python enforcers agree, including on the stale/corrupt case.
_active_set_csv() {
    local file="$1"
    if _yaml_has_key "$file" active_gates && _digest_halves_ok "$file"; then
        _yaml_list_csv "$file" active_gates
    else
        _yaml_list_csv "$file" gates
    fi
}

# active: decision verb (t635_33, folded t635_25). Exit 0 iff <gate> is in the
# task's ENFORCED active set; exit 1 otherwise. Pure bash. Replaces the
# `effective-gates | grep` producer-trigger shape — callers branch on the exit
# code, no text parsing.
cmd_active() {
    local task_id="${1:-}" gate="${2:-}"
    [[ -z "$task_id" || -z "$gate" ]] && die "Usage: aitask_gate.sh active <task-id> <gate>"
    local file
    file="$(resolve_task_file "$task_id")"
    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python active "$file" "$gate"
        return $?
    fi
    local set_csv
    set_csv="$(_active_set_csv "$file")"
    [[ ",${set_csv}," == *",${gate},"* ]]
}

# has-gates-field: field-presence oracle (t635_14). Exit 0 iff the task's
# frontmatter declares a `gates:` key AT ALL (even `gates: []`); exit 1 when
# absent — so a deliberate `gates: []` opt-out is never overwritten (`list`
# can't make this distinction). Pure bash (t635_33; previously python-only).
cmd_has_gates_field() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh has-gates-field <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"
    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python has-gates-field "$file"
        return $?
    fi
    _yaml_has_key "$file" gates
}

# should-self-record: decide whether task-workflow self-records <gate> at Step 7
# (t635_13/t635_14/t635_33). Exit 0 = record (gate NOT in the enforced active
# set); exit 1 = skip (the gate is enforced, so the Step-9 orchestrator records
# it — a self-record here would double-record). Reads the same set the
# orchestrator runs from. Pure bash (previously python-only).
cmd_should_self_record() {
    local task_id="${1:-}" gate="${2:-}"
    [[ -z "$task_id" || -z "$gate" ]] && die "Usage: aitask_gate.sh should-self-record <task-id> <gate>"
    local file
    file="$(resolve_task_file "$task_id")"
    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        delegate_python should-self-record "$file" "$gate"
        return $?
    fi
    local set_csv
    set_csv="$(_active_set_csv "$file")"
    [[ ",${set_csv}," != *",${gate},"* ]]
}

_mv_allowlist_csv() {
    printf '%s' "${MANUAL_VERIFICATION_REACHABLE_GATES// /,}"
}

# Derive the provenance stamp from a profile path: the path under .../profiles/
# without the extension (`fast`, `local/fast`); basename for out-of-tree paths.
_profile_stamp_name() {
    local p="$1" name
    case "$p" in
        *"/profiles/"*) name="${p##*/profiles/}" ;;
        *) name="$(basename "$p")" ;;
    esac
    name="${name%.yaml}"
    name="${name%.yml}"
    printf '%s' "$name"
}

# Single compute path shared by materialize-active and active-gates-status so
# freshness comparison applies the identical rule (incl. the t1156
# manual-verification allowlist, sourced ONCE from task_utils.sh). Delegates to
# lib/gate_ledger.py — the only full-compute implementation. Output:
# ACTIVE:<csv> / FILTERED:<csv> / DIGEST:<digest>.
cmd_compute_active() {  # internal: <task-file> <profile-file>
    delegate_python compute-active "$1" "$2" "$(_mv_allowlist_csv)"
}

# materialize-active: action verb (t635_33). Computes the task's active-gates
# tuple under --profile and persists it in ONE atomic aitask_update.sh call
# (all four fields), then commits the task file path-scoped. Stdout is exactly
# one line: MATERIALIZED:<csv> | MATERIALIZED:(empty) | NOOP:unchanged.
#
# Always run at claim time (task-workflow Step 4), even for lean profiles —
# writing `active_gates: []` is the safety valve that neutralizes a
# declared-but-unrendered gate. Hard-fails (nonzero) when the profile is
# missing/invalid or the compute backend is unavailable, and on that path
# CLEARS any previously persisted tuple: the old snapshot's profileless digest
# halves would still validate, so leaving it in place would keep the PREVIOUS
# profile's enforcement authoritative under the CURRENT profile's rendered
# workflow (over-blocking on a fast→default switch, under-enforcing on the
# reverse). After a failed re-derivation the raw `gates:` fallback must truly
# govern, exactly as the caller is told. The whole read-compute-write
# transaction runs under the per-task gate mutex, so it can never interleave
# with a concurrent append.
# Early "no verifier" warning (t635_34). Fires at CLAIM time for a gate that is
# in the task's ENFORCED active set but that no path can ever satisfy — so the
# user learns at pick time instead of discovering it when archival blocks with
# `blocked: no verifier configured (deferred)`.
#
# Scoped to the ACTIVE set on purpose: a gate outside the profile's rendered
# ceiling is already filtered out and never enforced, so warning about it would
# be noise (t635_33's model). Human gates (pend on a signal) and kind:procedure
# gates (run by the attended agent) are legitimately verifier-less and must not
# warn — the shared `gate_ledger.unverifiable_reason` predicate, which
# `gate_orchestrator.blocked_reason` also calls, owns that decision.
#
# stderr ONLY: `materialize-active`'s stdout is contractually a single status
# line that task-workflow Step 4 parses.
_warn_unverifiable_active() {
    local active_csv="$1"
    [[ -z "$active_csv" ]] && return 0
    [[ -f "$REGISTRY" ]] || return 0
    local out line gate reason
    out="$(delegate_python unverifiable-gates "$REGISTRY" "$active_csv" 2>/dev/null || true)"
    [[ -z "$out" ]] && return 0
    while IFS= read -r line; do
        [[ "$line" == UNVERIFIABLE:* ]] || continue
        gate="${line#UNVERIFIABLE:}"
        reason="${gate#*:}"
        gate="${gate%%:*}"
        warn "materialize-active: active gate '$gate' has $reason in $REGISTRY — it will block archival. Run \`ait gates sync-registry\` to reconcile the registry."
    done <<< "$out"
}

cmd_materialize_active() {
    local task_id="" profile=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --profile) profile="${2:-}"; shift 2 ;;
            *) task_id="$1"; shift ;;
        esac
    done
    # No --profile is a CALLER contract error (the skill skips the call when no
    # profile is in scope — the persisted snapshot keeps governing by design),
    # so it does not clear anything.
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh materialize-active <task-id> --profile <file>"
    local file
    file="$(resolve_task_file "$task_id")"
    [[ -z "$profile" ]] && \
        die "materialize-active: no profile given — nothing written (raw gates: fallback governs)"

    local profile_name
    profile_name="$(_profile_stamp_name "$profile")"

    local key="${task_id//\//_}"
    acquire_gate_lock "$key"
    # shellcheck disable=SC2064
    trap 'release_gate_lock' EXIT

    # Hard-fail helper for the profiled path: a re-derivation that cannot
    # complete must not leave a stale snapshot governing — drop the tuple
    # (grouped deletion) so the raw-gates fallback truly applies, and report
    # HONESTLY both whether the clear succeeded and which state now governs
    # (a failed clear leaves the OLD tuple authoritative — its profileless
    # digest halves still validate — so claiming the fallback governs there
    # would be self-contradictory). The raw fallback is only the declared
    # intent, NOT the current profile's defaults — the caller (task-workflow
    # Step 4) must therefore ABORT the pick on this exit, not continue with
    # potentially under-enforced state.
    _materialize_fail() {
        local state="no prior tuple present; raw gates: fallback governs"
        if _yaml_has_key "$file" active_gates; then
            if "$SCRIPT_DIR/aitask_update.sh" --batch "$task_id" --clear-active-gates \
                    --silent >/dev/null 2>&1; then
                state="stale tuple cleared; raw gates: fallback governs"
            else
                state="WARNING: stale tuple could NOT be cleared — the outdated tuple may still govern; clear it (aitask_update.sh --batch $task_id --clear-active-gates) before relying on enforcement"
            fi
        fi
        release_gate_lock; trap - EXIT
        die "materialize-active: $1 — $state"
    }

    if [[ ! -f "$profile" || ! -r "$profile" ]]; then
        _materialize_fail "profile not a readable file: $profile"
    fi

    local out
    if ! out="$(cmd_compute_active "$file" "$profile")"; then
        _materialize_fail "compute failed (python unavailable or invalid profile?)"
    fi
    local active filtered digest
    active="$(printf '%s\n' "$out" | sed -n 's/^ACTIVE://p')"
    filtered="$(printf '%s\n' "$out" | sed -n 's/^FILTERED://p')"
    digest="$(printf '%s\n' "$out" | sed -n 's/^DIGEST://p')"
    if [[ -z "$digest" ]]; then
        _materialize_fail "compute produced no digest"
    fi

    # Path-scoped persistence, shared by the write path and the NOOP repair
    # below. The tuple is already durable in the task FILE (the local
    # enforcement source of truth); the commit is what makes it visible to
    # other checkouts of the task-data branch. Git output is fully quieted so
    # stdout stays a single status line. The rev-parse probe is the non-git
    # seam: fixtures / dirs with no repo skip persistence silently (return 0);
    # in a REAL repo, exit 1 = the file has pending changes git refused to
    # commit.
    _persist_task_file() {
        if ! task_git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
            # Only a context with NO git markers at all is the expected
            # non-git seam (fixtures/tests) — persistence is not applicable.
            # A present .git / .aitask-data whose rev-parse fails is a BROKEN
            # task-data repo: persistence cannot be verified → failure.
            if [[ ! -e .git && ! -e .aitask-data ]]; then
                return 0
            fi
            return 1
        fi
        # Capture the status command's own exit separately: a failing status
        # with empty stdout must read as "unverified", never as "clean".
        local st
        if ! st="$(task_git status --porcelain -- "$file" 2>/dev/null)"; then
            return 1
        fi
        [[ -z "$st" ]] && return 0
        { task_git add -- "$file" \
            && task_git commit -m "ait: Materialize active gates for t${task_id}" -- "$file"; \
        } >/dev/null 2>&1
    }

    # Idempotence: identical persisted tuple → no rewrite, no updated_at bump.
    # Persistence is still VERIFIED/repaired: a previous invocation may have
    # written the tuple but failed its commit (e.g. transient index lock), and
    # an unchanged re-pick must heal that pending state, not skip past it.
    if _yaml_has_key "$file" active_gates \
        && [[ "$(_yaml_list_csv "$file" active_gates)" == "$active" ]] \
        && [[ "$(_yaml_list_csv "$file" active_gates_filtered)" == "$filtered" ]] \
        && [[ "$(read_yaml_field "$file" active_gates_profile)" == "$profile_name" ]] \
        && [[ "$(read_yaml_field "$file" active_gates_digest)" == "$digest" ]]; then
        release_gate_lock
        trap - EXIT
        # Also warn on the unchanged path: re-picking an in-flight task is the
        # COMMON case, and a warning that only fired on the first
        # materialization would be invisible for exactly the tasks that have
        # been sitting blocked (t635_34).
        _warn_unverifiable_active "$active"
        if _persist_task_file; then
            echo "NOOP:unchanged"
        else
            warn "materialize-active: task file still has uncommitted changes git refused to commit"
            echo "NOOP_UNCOMMITTED:pending-persist"
        fi
        return 0
    fi

    if ! "$SCRIPT_DIR/aitask_update.sh" --batch "$task_id" \
            --active-gates "$active" \
            --active-gates-filtered "$filtered" \
            --active-gates-profile "$profile_name" \
            --active-gates-digest "$digest" \
            --silent >/dev/null; then
        _materialize_fail "tuple write failed"
    fi

    release_gate_lock
    trap - EXIT

    _warn_unverifiable_active "$active"

    local status_word="MATERIALIZED"
    if ! _persist_task_file; then
        status_word="MATERIALIZED_UNCOMMITTED"
        warn "materialize-active: git persist failed for $file (tuple written locally; commit it with the task data)"
    fi
    if [[ -n "$active" ]]; then
        echo "${status_word}:${active}"
    else
        echo "${status_word}:(empty)"
    fi
}

# active-gates-status: provenance/staleness introspection (t635_33). First line:
# ABSENT | FRESH | STALE:<stamped>-><current>; when a tuple exists, the stored
# tuple follows as ACTIVE:/FILTERED:/PROFILE: lines. Compares stamp, digest,
# and stored values against a recomputation under --profile (same compute path
# as materialize-active).
cmd_active_gates_status() {
    local task_id="" profile=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --profile) profile="${2:-}"; shift 2 ;;
            *) task_id="$1"; shift ;;
        esac
    done
    [[ -z "$task_id" || -z "$profile" ]] && \
        die "Usage: aitask_gate.sh active-gates-status <task-id> --profile <file>"
    local file
    file="$(resolve_task_file "$task_id")"
    [[ -r "$profile" ]] || die "active-gates-status: profile not readable: $profile"

    local profile_name
    profile_name="$(_profile_stamp_name "$profile")"
    delegate_python active-status "$file" "$profile" "$profile_name" "$(_mv_allowlist_csv)" \
        || die "active-gates-status: compute failed (python unavailable?)"
    if _yaml_has_key "$file" active_gates; then
        echo "ACTIVE:$(_yaml_list_csv "$file" active_gates)"
        echo "FILTERED:$(_yaml_list_csv "$file" active_gates_filtered)"
        echo "PROFILE:$(read_yaml_field "$file" active_gates_profile)"
    fi
}

# --- begin-procedure (procedure-backed gates, t635_19) ---------------------

# sync-registry: additively reconcile the project's gate registry against the
# canonical reference (t635_34). Fills only keys that are textually ABSENT;
# a key present with a different value is reported as a CONFLICT and never
# overwritten. Comments and formatting are preserved (edits are line splices),
# which is the main thing `ait upgrade --force`'s PyYAML deep-merge destroys.
#
# Python-only: the merge planner, the presence oracle and the post-write
# self-verification all live in lib/gate_registry_sync.py.
#
# Serialized with the repo-level registry mutex, NOT acquire_gate_lock's
# per-task key — this mutates a shared file, not a task file. Readers take no
# lock and need none: the write is an atomic os.replace, so no reader ever sees
# a torn file. Do not "fix" readers to take this lock.
cmd_sync_registry() {
    local dry_run=0 registry="$REGISTRY" reference="$GATES_REFERENCE"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) dry_run=1; shift ;;
            --registry) registry="${2:-}"; shift 2 ;;
            --reference) reference="${2:-}"; shift 2 ;;
            *) die "Usage: aitask_gate.sh sync-registry [--dry-run] [--registry <file>] [--reference <file>]" ;;
        esac
    done

    local py
    py="$(resolve_python 2>/dev/null || true)"
    [[ -z "$py" ]] && die "sync-registry requires python3 (no bash path exists)"

    # Lazily sourced: see the note at the top of this file.
    # shellcheck source=lib/registry_lock.sh
    source "$SCRIPT_DIR/lib/registry_lock.sh"

    # Enumerate profiles through the canonical scanner so user-local profiles
    # (profiles/local/*.yaml) are covered exactly as everywhere else.
    local profiles=() pdir="${PROFILES_DIR:-${TASK_DIR}/metadata/profiles}"
    local line fname
    if [[ -d "$pdir" ]]; then
        while IFS= read -r line; do
            [[ "$line" == PROFILE\|* ]] || continue
            fname="$(printf '%s' "$line" | cut -d'|' -f2)"
            [[ -n "$fname" ]] && profiles+=("$pdir/$fname")
        done < <(PROFILES_DIR="$pdir" "$SCRIPT_DIR/aitask_scan_profiles.sh" 2>/dev/null || true)
    fi

    registry_lock_acquire "/tmp/aitask_gate_registry_sync" 10 || \
        die "sync-registry: another sync holds the registry lock — nothing written"
    trap 'registry_lock_release "/tmp/aitask_gate_registry_sync"' EXIT

    local rc=0 out
    out="$("$py" "$GATE_LEDGER_PY" sync-registry "$registry" "$reference" "$dry_run" \
        "$SCRIPT_DIR" "${profiles[@]+"${profiles[@]}"}")" || rc=$?

    registry_lock_release "/tmp/aitask_gate_registry_sync"
    trap - EXIT

    [[ -n "$out" ]] && printf '%s\n' "$out"
    if [[ "$rc" -ne 0 ]]; then
        return "$rc"
    fi
    # Only when the file actually changed — a NOOP run has nothing to commit,
    # and a "not committed" hint there would be noise the user learns to ignore.
    if [[ "$dry_run" -eq 0 ]] && printf '%s' "$out" | grep -q '^\(FILLED\|NEW_GATE\):'; then
        warn "registry updated but NOT committed — review it, then: ./ait git add ${registry}"
    fi
    return 0
}

# Allocate a run for a PROCEDURE-BACKED gate (kind: procedure) and open its
# `running` block. The headless orchestrator defers such gates (it never writes
# their running block / attempt / run-id), so the attended dispatch path
# (task-workflow / aitask-resume) calls this to start a run before Read-and-
# following the gate's skill. Prints RUN_ID:<id> and ATTEMPT:<n> for the caller,
# which passes them to the skill as `<task-id> <attempt> <run-id>`; the skill
# closes the run with `append --only-if-running <run-id> ... <pass|skip|fail>`.
#
# A gate has AT MOST ONE LIVE RUN. A repeat call — a crash/resume re-dispatch
# (`procedure-gates` still lists a gate that is neither pass nor skip) or a
# concurrent launch — ADOPTS the open run rather than opening a second (t1262).
cmd_begin_procedure() {
    local task_id="${1:-}" gate="${2:-}"
    [[ -z "$task_id" || -z "$gate" ]] && \
        die "Usage: aitask_gate.sh begin-procedure <task-id> <gate>"
    local file
    file="$(resolve_task_file "$task_id")"

    # The live-run check and the append must be ONE critical section, or two
    # racing dispatches each see "no live run" and each open one. _gate_append_locked
    # exists for exactly this: the mkdir lock is not reentrant, so calling
    # cmd_append here would deadlock against our own hold.
    local key="${task_id//\//_}"
    acquire_gate_lock "$key"
    # shellcheck disable=SC2064
    trap 'release_gate_lock' EXIT

    local state open_field attempt run_id terminal
    state="$(_gate_run_state "$file" "$gate")"
    open_field="$(printf '%s\n' "$state" | sed -n 's/^OPEN://p')"
    terminal="$(printf '%s\n' "$state" | sed -n 's/^TERMINAL://p')"

    if [[ -n "${open_field%%|*}" ]]; then
        # Adopt: same run id, same attempt, nothing appended. The caller's closing
        # `append --only-if-running <run-id>` then closes the run that is actually
        # open. The notice goes to stderr so stdout's two-line contract is
        # byte-identical to the open path.
        run_id="${open_field%%|*}"
        attempt="${open_field#*|}"
        [[ -z "$attempt" ]] && attempt="$((terminal + 1))"
        warn "gate:${gate} already has a live run (${run_id}) — adopting it instead of opening a second"
    else
        # attempt = terminal runs recorded for this gate + 1 (t1262): this running
        # block and the terminal block the gate skill appends for the SAME run id
        # carry the SAME number.
        attempt="$((terminal + 1))"
        # Same shape as gate_orchestrator._run_machine_gate's run id. A bare
        # second-resolution timestamp collides when two runs start within one
        # second (observed), which would make two runs indistinguishable.
        run_id="$(date -u +%Y-%m-%dT%H:%M:%SZ)-${gate}-a${attempt}"
        _gate_append_locked "$file" "$gate" running \
            run="$run_id" attempt="$attempt" type=machine >/dev/null
    fi

    release_gate_lock
    trap - EXIT

    printf 'RUN_ID:%s\nATTEMPT:%s\n' "$run_id" "$attempt"
}

# --- usage / dispatch ------------------------------------------------------

show_help() {
    cat <<'EOF'
Usage: aitask_gate.sh <command> [args]

Gate ledger substrate — record and derive per-task gate-run state.

Commands:
  append [--only-if-running <run-id>] <task-id> <gate> <status> [k=v ...]
        Append a marker-first gate-run blockquote to the task's "## Gate Runs"
        section. <status>: pass | fail | pending | running | skip | error.
        Keys: run, attempt, duration, type (marker line);
              verifier, result, log, note (body lines).
        run defaults to now (ISO-8601-Z); attempt defaults to (terminal runs
        for this gate) + 1 for any terminal status, so a `running` block and
        the terminal block closing it share one number.
        --only-if-running <run-id>: append only if no terminal block exists yet
        for <run-id> (the run is still "running"); else no-op. Used by the
        orchestrator to write a terminal block exactly once per run (t635_11).

  status <task-id>
        Print derived current state per gate (last run wins).

  list <task-id>
        List the gates declared in the task's `gates:` frontmatter, enriched
        with type/description from aitasks/metadata/gates.yaml.

  deps-unblock <task-id>
        Decide whether this task releases its dependents (t635_3). Prints
        SATISFIED (all required gates pass), BLOCKED:<csv> (required gates still
        pending), or NO_GATES (no required-to-unblock gates → caller falls back
        to file-existence). "Required" = declared gates flagged
        `blocks_dependents` in the registry, plus the task's
        `also_blocks_dependents` list. A required gate whose ledger reads `pass`
        but whose code-bound signature is stale counts as NOT satisfied (t1416),
        so BLOCKED can name a gate that `status` still shows as passing.

  deps-unblock-batch < task-file-paths
        Batched twin of deps-unblock, for list-shaped callers (t1472). Reads task
        FILE PATHS on stdin (one per line) and prints `<decision><TAB><path>` per
        NON-EMPTY input line, in INPUT ORDER — every non-empty input line always
        yields exactly one output line. Blank lines are skipped and produce no
        row, so map results by the echoed path, not by line position.
        Decisions are identical to the per-task verb (both route
        through one shared core), but the whole list is decided in ONE process
        with one registry parse and at most one code-digest, replacing `ait ls`'s
        former one-subprocess-per-gated-task fan-out.
        Exit 0 = every row decided; a task file that cannot be read or decided is
        isolated to NO_GATES with a stderr diagnostic naming it. Exit 1 = registry
        setup failed, so EVERY row is a conservative NO_GATES (one diagnostic,
        not one per row); the rows are still printed before the nonzero exit.

  archive-ready <task-id>
        Decide whether this task may archive (t635_4). Prints ALL_PASS (every
        declared gate passed), BLOCKED:<csv> (declared gates not all pass), or
        NO_GATES (no declared gates → archive as today). Unlike deps-unblock,
        ALL declared gates must pass (no `blocks_dependents` filtering).

  resume-point <task-id>
        Derive the task-workflow re-entry stage from the recorded checkpoint
        ledger (t635_5). Prints PLAN (nothing durable recorded → plan from
        scratch), IMPLEMENT (plan_approved pass, review_approved pending →
        resume implementation), or POSTIMPL (review_approved pass → resume at
        post-implementation). Keys off the recorded plan_approved/review_approved
        runs, not the declared `gates:` field.

  workflow-phase <task-id> [--screen <file>] [--awaiting-input yes|no|unknown]
                 [--kind <awaiting_input_kind>] [--agent <name>]
                 [--profiles-dir <dir>]
        ADVISORY workflow-phase signal for the shadow companion (t1420). Prints
        one `|`-delimited line: PHASE (PLAN|IMPLEMENT|POSTIMPL|UNKNOWN), WAITING,
        SOURCE (which tier answered), CONSULTED, RECORDING, DETAIL.

        This is a HINT, not a gate: it may never be used to refuse an action.
        UNKNOWN is a real answer meaning "cannot tell" — distinct from PLAN.

        --awaiting-input defaults to `unknown`, which SUPPRESSES the screen
        tiers, so the bare form is purely ledger-derived and cannot be poisoned
        by an answered prompt still sitting in scrollback. Only a caller that can
        observe the pane's input state should pass `yes`. --kind/--agent add the
        per-agent native-dialog tier; without them only the agent-neutral
        workflow-prompt tier applies.

  effective-gates <task-id> [--profile <file>]
        Resolve the task's effective gate set (t635_14). The literal `gates:`
        field wins when present (even `[]`); otherwise fall back to the profile's
        `default_gates` (when --profile names a readable file). Prints one gate
        per line. Used by the task-workflow producer trigger during planning.

  has-gates-field <task-id>
        Field-presence oracle (t635_14): exit 0 iff the task declares a `gates:`
        key at all (even `gates: []`), exit 1 when absent. The Step-7 backfill
        keys off this so an explicit `gates: []` opt-out is never overwritten.

  should-self-record <task-id> <gate>
        Decide whether task-workflow self-records <gate> at Step 7 (t635_14/
        t635_33): exit 0 = record (gate not in the enforced active set),
        exit 1 = skip (enforced → the orchestrator records it; avoids a
        double-record). Pure bash.

  recorded-pass <task-id> <gate>
        Decision verb (t1380): exit 0 iff <gate>'s CURRENT recorded run
        (last-marker-wins) has status `pass`; exit 1 otherwise (absent, fail,
        skip, pending, running, error). Reads the RECORDED ledger, not the
        declared/active gate set. The strict `== pass` test mirrors
        resume-point, not archive-ready's {pass, skip}. Degrades to exit 1.
        Used by the Approved-Plan Stop Sequence (record the approval once) and
        the Task Abort Procedure (re-open a stale plan_approved).

  active <task-id> <gate>
        Decision verb (t635_33): exit 0 iff <gate> is in the task's ENFORCED
        active set — the validated active_gates tuple when present/intact, else
        the raw `gates:` fallback. Pure bash; callers branch on the exit code
        (replaces `effective-gates | grep`).

  materialize-active <task-id> --profile <file>
        Action verb (t635_33): compute the task's profile-filtered active-gates
        tuple (active_gates, active_gates_filtered, active_gates_profile,
        active_gates_digest) and persist all four atomically, committing the
        task file path-scoped. Prints ONE line: MATERIALIZED:<csv|(empty)> |
        MATERIALIZED_UNCOMMITTED:<csv|(empty)> (tuple written + enforced
        locally, but the git repo refused the path-scoped commit — commit the
        task data to make it cross-PC visible) | NOOP:unchanged (identical
        tuple; any pending commit of the task file is verified/repaired) |
        NOOP_UNCOMMITTED:pending-persist (identical tuple, repair commit still
        refused). Outside a git context (fixtures) persistence is skipped
        silently. Hard-fails
        (nonzero, and clears any prior tuple) on an unreadable/invalid
        profile or compute failure — the CALLER must abort its flow then. Run
        at claim time (task-workflow Step 4), ALWAYS — writing
        `active_gates: []` is what makes a declared-but-unrendered gate
        invisible to every enforcer.

  active-gates-status <task-id> --profile <file>
        Freshness/provenance introspection (t635_33). First line: ABSENT |
        FRESH | STALE:<stamped>-><current>; when a tuple exists, the stored
        tuple follows as ACTIVE:/FILTERED:/PROFILE: lines. The enforced-set
        display verb (`list` shows the DECLARED intent).

  procedure-gates <task-id>
        List the task's declared PROCEDURE-BACKED gates (kind: procedure) not yet
        terminal-satisfied (t635_19) — one per line. The attended dispatch seam
        runs each such gate's skill.

  begin-procedure <task-id> <gate>
        Start a run for a PROCEDURE-BACKED gate (kind: procedure, t635_19): open
        its `running` block and print RUN_ID:<id> / ATTEMPT:<n>. The attended
        dispatch (task-workflow / aitask-resume) calls this before running the
        gate's skill, which closes the run via `append --only-if-running`.
        ATTEMPT is the gate's run ORDINAL and must be passed back verbatim on
        that closing append. A gate has at most one live run: a repeat call
        (crash/resume re-dispatch, concurrent launch) ADOPTS the open run —
        same RUN_ID, same ATTEMPT, nothing appended.

  sync-registry [--dry-run] [--registry <file>] [--reference <file>]
        Additively reconcile the project's gate registry
        (aitasks/metadata/gates.yaml) against the canonical framework reference
        (.aitask-scripts/gates_reference.yaml) — the repair for a registry
        seeded before the verifier keys shipped, whose tasks block on
        `no verifier configured` and cannot archive (t635_34).

        ONLY fills keys that are textually ABSENT. A key present with a
        different value is reported and never overwritten. Comments and
        formatting are preserved, unlike `ait upgrade --force`, whose YAML
        round-trip rewrites the file and reports nothing.

        Applies by default; --dry-run previews the identical report without
        writing. Prints one line per action:
          FILLED:<gate>.<key>=<value>          key added from the reference
          NEW_GATE:<gate>                      whole gate block appended
          CONFLICT:<gate>.<key>:<proj>|<ref>   differs — left alone, decide
                                               manually ((absent) = the project
                                               lacks a key that is never
                                               auto-filled, e.g. `unlocks`)
          PROFILE_UNKNOWN:<profile>.<key>:<gate>
                                               a profile declares a gate with no
                                               registry entry (report only —
                                               profiles are never edited)
          NOOP                                 already in sync

        Note: filling `timeout_seconds` gives a previously UNBOUNDED machine
        gate a wall-clock ceiling, and filling `blocks_dependents: true` makes
        the gate hold dependent tasks until it passes. Both are visible as
        FILLED: lines — use --dry-run first if that matters.

        Refuses to write (nonzero, file untouched) when the registry cannot be
        edited safely: duplicate gate names, fields indented at gate level, a
        `gates:` mapping truncated by a column-0 comment with entries below it,
        an empty mapping, or a missing/unreadable reference. Python-only.

        The registry is NOT committed — review, then `./ait git add`.

Backend:
  Primary path is bash + awk. Set AIT_GATES_BACKEND=python to force the
  lib/gate_ledger.py fallback (identical output).
EOF
}

main() {
    local cmd="${1:-}"
    case "$cmd" in
        append) shift; cmd_append "$@" ;;
        status) shift; cmd_status "$@" ;;
        list)   shift; cmd_list "$@" ;;
        deps-unblock) shift; cmd_deps_unblock "$@" ;;
        deps-unblock-batch) shift; cmd_deps_unblock_batch "$@" ;;
        archive-ready) shift; cmd_archive_ready "$@" ;;
        resume-point) shift; cmd_resume_point "$@" ;;
        workflow-phase) shift; cmd_workflow_phase "$@" ;;
        effective-gates) shift; cmd_effective_gates "$@" ;;
        has-gates-field) shift; cmd_has_gates_field "$@" ;;
        should-self-record) shift; cmd_should_self_record "$@" ;;
        recorded-pass) shift; cmd_recorded_pass "$@" ;;
        active) shift; cmd_active "$@" ;;
        materialize-active) shift; cmd_materialize_active "$@" ;;
        active-gates-status) shift; cmd_active_gates_status "$@" ;;
        procedure-gates) shift; cmd_procedure_gates "$@" ;;
        begin-procedure) shift; cmd_begin_procedure "$@" ;;
        sync-registry) shift; cmd_sync_registry "$@" ;;
        --help|-h|help|"") show_help ;;
        *) die "Unknown command: $cmd (try --help)" ;;
    esac
}

main "$@"
