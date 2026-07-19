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
#                                                dependents (t635_3; python-only)
#   archive-ready <task-id>                      Decide if this task may archive
#                                                (t635_4; python-only)
#   resume-point <task-id>                       Derive task-workflow re-entry
#                                                stage (t635_5; python-only)
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

    # Explicit python backend: delegate the whole append.
    if [[ "${AIT_GATES_BACKEND:-}" == "python" ]]; then
        local key="${task_id//\//_}"
        acquire_gate_lock "$key"
        # shellcheck disable=SC2064
        trap 'release_gate_lock' EXIT
        if [[ -n "$only_if_running" ]] && ! _gate_run_is_running "$file" "$only_if_running"; then
            release_gate_lock; trap - EXIT
            return 0  # terminal block already exists for this run — no-op
        fi
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

    # `--only-if-running` guard (atomic under the lock): if a terminal block was
    # already written for this run id, do nothing.
    if [[ -n "$only_if_running" ]] && ! _gate_run_is_running "$file" "$only_if_running"; then
        release_gate_lock; trap - EXIT
        return 0
    fi

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

# Allocate a run for a PROCEDURE-BACKED gate (kind: procedure) and open its
# `running` block. The headless orchestrator defers such gates (it never writes
# their running block / attempt / run-id), so the attended dispatch path
# (task-workflow / aitask-resume) calls this to start a run before Read-and-
# following the gate's skill. Prints RUN_ID:<id> and ATTEMPT:<n> for the caller,
# which passes them to the skill as `<task-id> <attempt> <run-id>`; the skill
# closes the run with `append --only-if-running <run-id> ... <pass|skip|fail>`.
cmd_begin_procedure() {
    local task_id="${1:-}" gate="${2:-}"
    [[ -z "$task_id" || -z "$gate" ]] && \
        die "Usage: aitask_gate.sh begin-procedure <task-id> <gate>"
    local file
    file="$(resolve_task_file "$task_id")"

    # attempt = existing gate-run marker count for this gate + 1. (Attended,
    # single-writer path; run-id is a unique timestamp regardless.)
    local existing
    existing="$(awk -v g="$gate" '
        /^>[[:space:]]*\*\*/ && /gate:/ {
            if (match($0, /gate:[A-Za-z0-9_]+/)) {
                name = substr($0, RSTART + 5, RLENGTH - 5)
                if (name == g) c++
            }
        }
        END { print c + 0 }
    ' "$file" 2>/dev/null)"
    local attempt=$((existing + 1))
    local run_id
    run_id="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # Open the running block (reuses cmd_append's lock + section handling).
    cmd_append "$task_id" "$gate" running run="$run_id" attempt="$attempt" type=machine >/dev/null

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
        run defaults to now (ISO-8601-Z); attempt auto-increments for pass/fail.
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
        `also_blocks_dependents` list.

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
        resume-point) shift; cmd_resume_point "$@" ;;
        effective-gates) shift; cmd_effective_gates "$@" ;;
        has-gates-field) shift; cmd_has_gates_field "$@" ;;
        should-self-record) shift; cmd_should_self_record "$@" ;;
        active) shift; cmd_active "$@" ;;
        materialize-active) shift; cmd_materialize_active "$@" ;;
        active-gates-status) shift; cmd_active_gates_status "$@" ;;
        procedure-gates) shift; cmd_procedure_gates "$@" ;;
        begin-procedure) shift; cmd_begin_procedure "$@" ;;
        --help|-h|help|"") show_help ;;
        *) die "Unknown command: $cmd (try --help)" ;;
    esac
}

main "$@"
