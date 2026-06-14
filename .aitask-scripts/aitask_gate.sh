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
#   append <task-id> <gate> <status> [k=v ...]   Append a gate-run block
#   status <task-id>                             Print derived per-gate state
#   list   <task-id>                             List declared gates (+ registry)
#   deps-unblock <task-id>                       Decide if this task releases its
#                                                dependents (t635_3; python-only)
#   archive-ready <task-id>                      Decide if this task may archive
#                                                (t635_4; python-only)
#
# Primary path is bash + POSIX awk. The Python module lib/gate_ledger.py is the
# documented fallback (drop-in, identical output): used when AIT_GATES_BACKEND=python
# or when the awk scan fails. Keep the two output formats byte-identical.
#
# append keys: run, status, attempt, duration, type (marker line);
#              verifier, result, log, note (body lines). Others are ignored.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

TASK_DIR="${TASK_DIR:-aitasks}"
GATE_LEDGER_PY="$SCRIPT_DIR/lib/gate_ledger.py"
REGISTRY="${TASK_DIR}/metadata/gates.yaml"

VALID_STATUSES="pass fail pending running skip error"

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
            local lock_age
            lock_age=$(( $(date +%s) - $(stat -c %Y "$lock_dir" 2>/dev/null || stat -f %m "$lock_dir" 2>/dev/null || echo "0") ))
            if [[ "$lock_age" -gt 120 ]]; then
                warn "Removing stale gate lock for $key (age: ${lock_age}s)"
                rmdir "$lock_dir" 2>/dev/null || true
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

# --- append ----------------------------------------------------------------

cmd_append() {
    local task_id="${1:-}" gate="${2:-}" status="${3:-}"
    [[ -z "$task_id" || -z "$gate" || -z "$status" ]] && \
        die "Usage: aitask_gate.sh append <task-id> <gate> <status> [k=v ...]"
    is_valid_status "$status" || \
        die "Invalid status '$status' (one of: $VALID_STATUSES)"
    shift 3

    local file
    file="$(resolve_task_file "$task_id")"

    # Explicit python backend: delegate the whole append.
    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        local key="${task_id//\//_}"
        acquire_gate_lock "$key"
        # shellcheck disable=SC2064
        trap 'release_gate_lock' EXIT
        delegate_python append "$file" "$gate" "$status" "$@" || die "python gate_ledger append failed"
        release_gate_lock
        trap - EXIT
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

    local key="${task_id//\//_}"
    acquire_gate_lock "$key"
    # shellcheck disable=SC2064
    trap 'release_gate_lock' EXIT

    # run id (ISO-8601-Z). date -u + this format is portable (no -d).
    [[ -z "$f_run" ]] && f_run="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # attempt: explicit wins; else auto for pass/fail = existing count + 1.
    if [[ -z "$f_attempt" && ( "$status" == "pass" || "$status" == "fail" ) ]]; then
        local existing
        existing="$(awk -v g="$gate" '
            /^>[[:space:]]*\*\*/ && /gate:/ {
                if (match($0, /gate:[A-Za-z0-9_]+/)) {
                    name = substr($0, RSTART + 5, RLENGTH - 5)
                    if (name == g) c++
                }
            }
            END { print c + 0 }
        ' "$file")"
        f_attempt="$((existing + 1))"
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

    release_gate_lock
    trap - EXIT

    # Echo the appended block (marker + body) for caller confirmation.
    printf '%s\n' "$marker"
    [[ -n "$body" ]] && { printf '>\n'; printf '%s\n' "$body"; }
    return 0
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

    local out
    if out="$(awk '
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
                extra = ""
                if (attempt_of[g] != "") extra = "attempt " attempt_of[g]
                if (run_of[g] != "") extra = (extra == "" ? "" : extra ", ") "run " run_of[g]
                line = g ": " status_of[g]
                if (extra != "") line = line " (" extra ")"
                print line
            }
        }
    ' "$file" 2>/dev/null)"; then
        [[ -n "$out" ]] && printf '%s\n' "$out"
        return 0
    fi

    # awk failed — fall back to python.
    delegate_python status "$file"
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
# per-task `also_blocks_dependents` list, and ledger derivation. It is a new,
# low-frequency decision (only on `ait ls`, only for gated active tasks), so it
# delegates to lib/gate_ledger.py rather than re-implementing the registry-flag
# + two-list logic in awk. Prints one of: SATISFIED | BLOCKED:<csv> | NO_GATES.
# If python is unavailable, degrades to NO_GATES so callers fall back to today's
# file-existence behavior.
cmd_deps_unblock() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh deps-unblock <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"
    delegate_python deps-unblock "$file" "$REGISTRY" || echo "NO_GATES"
}

# archive-ready: decide whether this task may archive (t635_4). Python-only
# (parallels deps-unblock — a new low-frequency decision, only at archival).
# Prints one of: ALL_PASS (every declared gate passed), BLOCKED:<csv> (declared
# gates not all pass), or NO_GATES (no declared gates → archive as today). If
# python is unavailable, degrades to NO_GATES so archival proceeds as today.
cmd_archive_ready() {
    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_gate.sh archive-ready <task-id>"
    local file
    file="$(resolve_task_file "$task_id")"
    delegate_python archive-ready "$file" || echo "NO_GATES"
}

# --- usage / dispatch ------------------------------------------------------

show_help() {
    cat <<'EOF'
Usage: aitask_gate.sh <command> [args]

Gate ledger substrate — record and derive per-task gate-run state.

Commands:
  append <task-id> <gate> <status> [k=v ...]
        Append a marker-first gate-run blockquote to the task's "## Gate Runs"
        section. <status>: pass | fail | pending | running | skip | error.
        Keys: run, attempt, duration, type (marker line);
              verifier, result, log, note (body lines).
        run defaults to now (ISO-8601-Z); attempt auto-increments for pass/fail.

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
        `also_blocks_dependents` list.

  archive-ready <task-id>
        Decide whether this task may archive (t635_4). Prints ALL_PASS (every
        declared gate passed), BLOCKED:<csv> (declared gates not all pass), or
        NO_GATES (no declared gates → archive as today). Unlike deps-unblock,
        ALL declared gates must pass (no `blocks_dependents` filtering).

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
        archive-ready) shift; cmd_archive_ready "$@" ;;
        --help|-h|help|"") show_help ;;
        *) die "Unknown command: $cmd (try --help)" ;;
    esac
}

main "$@"
