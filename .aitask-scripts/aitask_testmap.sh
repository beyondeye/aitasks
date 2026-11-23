#!/usr/bin/env bash
set -euo pipefail

# aitask_testmap.sh — the `ait testmap <verb>` shim (t1852_4, test map M1.4).
#
# Resolves the ait-testmap engine binary through a STRICT handshake and execs
# it with the caller's arguments, untouched. It never downloads, never edits
# PATH and never writes a file: a host without a matching engine gets a
# diagnostic naming the exact path and the repair, never a fetch and never a
# "close enough" binary. (`ait` also skip-lists `testmap` from its update
# check, so the dispatcher adds no network call or stdout line either.)
#
# Tiers, in order — the first one that is SET decides, and a failed tier never
# falls through to the next one (that would run an engine the caller did not
# ask for):
#   1. AIT_TESTMAP_BIN=<abs path>  the override: any executable file, no
#                                   version check (fake engines in tests,
#                                   air-gapped hosts). Announced on stderr.
#   2. AIT_ENGINE=dev              $AITASKS_HOME/engine/dev/ait-testmap, whose
#                                   version must be <VERSION>-dev+<hex 7..64>.
#   3. (default)                   $AITASKS_HOME/engine/v<VERSION>/ait-testmap,
#                                   whose version must equal VERSION exactly.
#                                   No other v* slot is ever consulted (never
#                                   newest-wins).
# VERSION is .aitask-scripts/VERSION. A slot's version is read from the
# engine's text `version` output (exactly one `VERSION:<v>` line), with stdin
# closed so a verb that reads stdin (`test --changes -`) still gets all of it.
#
# Interfaces (each row pinned by the named tests/test_testmap_shim.sh case)
#
# | shape | contract | pinned by |
# |---|---|---|
# | tier order | override > dev > release; a set tier that fails is final; the override needs no per-user root: the root is loaded first, so an override engine inherits AITASKS_HOME / AITASKS_HOME_LOCK whenever one can be established, but its failure only matters after tier 1, so the override works without HOME | O1, O2, D2; t2348 S2, S6 |
# | stdout | only ever the engine's own output | R1, O1, W1 |
# | exec | args verbatim, engine exit status returned, stdin passed through | R1, R2 |
# | ENGINE_OVERRIDE:<path> | stderr, whenever tier 1 is taken | O1 |
# | ENGINE_REJECTED:<path>|not-absolute | stderr; override path is relative | O2 |
# | ENGINE_REJECTED:<path>|not-executable | stderr; override missing/non-x, or a slot file without +x | O2, R7 |
# | ENGINE_REJECTED:<path>|version-unreadable | stderr; `version` failed or printed != 1 VERSION: line | R7 |
# | ENGINE_REJECTED:<path>|version-mismatch|<found>|<required> | stderr; required is <V> or <V>-dev+<sha> | R4, R6, D2 |
# | ENGINE_MISSING:<path>|run 'ait setup' or set AIT_TESTMAP_BIN | stderr, exit 3; release slot | R3, R4, R5, E1 |
# | ENGINE_MISSING:<path>|run 'ait engine build' or unset AIT_ENGINE | stderr, exit 3; dev slot | D2, D3 |
# | ENGINE_MISSING:<path>|fix or unset AIT_TESTMAP_BIN | stderr, exit 3; override | O2 |
# | ENGINE_PATH_UNSAFE:<var> | stderr, exit 3; a path field holds a pipe, CR or LF (named by variable, value withheld): AITASKS_HOME, AIT_TESTMAP_BIN, or SCRIPT_DIR (the framework dir, only when VERSION is also invalid) | U1, U2 |
# | VERSION_INVALID:<file> | stderr, exit 3; VERSION missing, unreadable, empty or outside [A-Za-z0-9._+-] (no raw shell error leaks) | V1, V2, U2 |
# | USAGE:AIT_ENGINE must be 'dev' or unset | stderr, exit 64; also with neither AITASKS_HOME nor HOME (the mode check still answers before the root is needed) | D4; t2348 S4 |
# | ENGINE_HOME_UNSET:AITASKS_HOME|set AITASKS_HOME, or a non-empty HOME | stderr, exit 3; a dev/release lookup with AITASKS_HOME unset/empty and HOME unset/empty — no slot is probed, never a root-level /.aitasks default; the override tier needs neither, and an invalid AIT_ENGINE still answers USAGE/64 | t2348 S1, S2, S4 (tests/test_aitasks_home_unset_home.sh) |
# | ENGINE_ROOT_INVALID:AITASKS_HOME|<reason> | stderr, exit 3; dev/release lookup when lib/aitasks_home.sh refused a root it could not assign (reason root-unsettable: a readonly empty AITASKS_HOME, or a readonly AITASKS_HOME_LOCK with another value); no slot is probed | t2348 S5 |
# | ENGINE_LIB_FAILED:<lib>|run 'ait setup' to repair the install | stderr, exit 3; dev/release lookup when lib/aitasks_home.sh is missing, unreadable or broken (no refusal reason reported); ENGINE_PATH_UNSAFE:SCRIPT_DIR when that path cannot travel as a field | t2348 S7 |
# | dev version rule | <VERSION>-dev+ then ^[0-9a-f]{7,64}$ | D1, D2 |
# | resolver API | `source aitask_testmap.sh --source-only`; `rc=0; testmap_resolve_engine || rc=$?` → rc 0 + TESTMAP_ENGINE_BIN, or rc 3/64 + TESTMAP_ENGINE_ERROR (one full line above); never execs | A1 |
# | no network | `ait testmap` runs no update check (no stdout notice, no background curl) | W1, W2, W4 |
#
# Other exit codes are the engine's own (0/1/2/3/64/75 — goengines/README.md
# "## Interfaces"); callers that must tell "engine absent" from an engine's
# own exit 3 probe with testmap_resolve_engine first.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The per-user framework root ($AITASKS_HOME, lib/aitasks_home.sh, t1852_1) is
# loaded inside testmap_resolve_engine, BEFORE the override tier, so an override
# engine inherits AITASKS_HOME / AITASKS_HOME_LOCK whenever a root can be
# established. A load failure is reported only AFTER the override tier, so the
# override keeps working without HOME (t2348).

_TM_MODE_USAGE="USAGE:AIT_ENGINE must be 'dev' or unset"

# _tm_safe <value> — true when <value> can travel as one line-protocol field.
_tm_safe() {
    [[ "$1" != *'|'* && "$1" != *$'\n'* && "$1" != *$'\r'* ]]
}

# _tm_engine_version <bin> — print the engine's version, or return 1 when it
# cannot be read: `version` failed, printed no or several VERSION: lines, or a
# value that cannot travel as a field.
_tm_engine_version() {
    local out found count
    out="$("$1" version </dev/null 2>/dev/null)" || return 1
    count="$(printf '%s\n' "$out" | grep -c '^VERSION:' || true)"
    [[ "$count" == "1" ]] || return 1
    found="$(printf '%s\n' "$out" | sed -n 's/^VERSION://p')"
    [[ -n "$found" ]] && _tm_safe "$found" || return 1
    printf '%s\n' "$found"
}

# _tm_check_slot <bin> <release|dev> <V> — true when the slot holds an engine
# whose version satisfies the tier. A rejection is reported on stderr; a plain
# absence prints nothing (the caller reports ENGINE_MISSING).
_tm_check_slot() {
    local bin="$1" mode="$2" v="$3" found required
    [[ -e "$bin" ]] || return 1
    if [[ ! -f "$bin" || ! -x "$bin" ]]; then
        printf 'ENGINE_REJECTED:%s|not-executable\n' "$bin" >&2
        return 1
    fi
    if ! found="$(_tm_engine_version "$bin")"; then
        printf 'ENGINE_REJECTED:%s|version-unreadable\n' "$bin" >&2
        return 1
    fi
    if [[ "$mode" == "release" ]]; then
        required="$v"
        [[ "$found" == "$v" ]] && return 0
    else
        required="$v-dev+<sha>"
        if [[ "$found" == "$v-dev+"* ]]; then
            [[ "${found#"$v-dev+"}" =~ ^[0-9a-f]{7,64}$ ]] && return 0
        fi
    fi
    printf 'ENGINE_REJECTED:%s|version-mismatch|%s|%s\n' "$bin" "$found" "$required" >&2
    return 1
}

# testmap_resolve_engine — run the handshake without exec'ing anything.
# rc 0: TESTMAP_ENGINE_BIN is the engine to run.
# rc 3 / 64: TESTMAP_ENGINE_ERROR is the one diagnostic line to print.
# Call it guarded (`rc=0; testmap_resolve_engine || rc=$?`): this file sets
# errexit when sourced.
testmap_resolve_engine() {
    TESTMAP_ENGINE_BIN=""
    TESTMAP_ENGINE_ERROR=""
    local version_file="$SCRIPT_DIR/VERSION" v="" slot
    local home_lib="$SCRIPT_DIR/lib/aitasks_home.sh" home_rc=0

    # A missing or unreadable file reads as empty: the shell's own error would
    # be a raw, unstructured stderr line (and would echo an unsafe path).
    if [[ -f "$version_file" ]]; then
        { v="$(<"$version_file")"; } 2>/dev/null || v=""
    fi
    v="${v%$'\r'}"
    if [[ -z "$v" || ! "$v" =~ ^[A-Za-z0-9._+-]+$ ]]; then
        # The file path is the field; a framework dir that cannot travel as
        # one is named by variable instead (the error stays ONE line). Only
        # this line carries SCRIPT_DIR, so a valid VERSION never needs it.
        if _tm_safe "$version_file"; then
            TESTMAP_ENGINE_ERROR="VERSION_INVALID:$version_file"
        else
            TESTMAP_ENGINE_ERROR="ENGINE_PATH_UNSAFE:SCRIPT_DIR"
        fi
        return 3
    fi

    # The per-user root: loaded BEFORE the override, so an override engine
    # still inherits AITASKS_HOME / AITASKS_HOME_LOCK whenever a root can be
    # established, but REQUIRED only after it. The override works without
    # HOME (t2348). The lib's own Error line is dropped, so
    # TESTMAP_ENGINE_ERROR stays the one diagnostic line. The refusal reason
    # is reset first, because a lib that never ran leaves it unset.
    AITASKS_HOME_REFUSAL=""
    # shellcheck source=lib/aitasks_home.sh
    source "$home_lib" 2>/dev/null || home_rc=$?

    # Tier 1 — the override.
    if [[ -n "${AIT_TESTMAP_BIN:-}" ]]; then
        if ! _tm_safe "$AIT_TESTMAP_BIN"; then
            TESTMAP_ENGINE_ERROR="ENGINE_PATH_UNSAFE:AIT_TESTMAP_BIN"
            return 3
        fi
        printf 'ENGINE_OVERRIDE:%s\n' "$AIT_TESTMAP_BIN" >&2
        if [[ "$AIT_TESTMAP_BIN" != /* ]]; then
            printf 'ENGINE_REJECTED:%s|not-absolute\n' "$AIT_TESTMAP_BIN" >&2
        elif [[ ! -f "$AIT_TESTMAP_BIN" || ! -x "$AIT_TESTMAP_BIN" ]]; then
            printf 'ENGINE_REJECTED:%s|not-executable\n' "$AIT_TESTMAP_BIN" >&2
        else
            TESTMAP_ENGINE_BIN="$AIT_TESTMAP_BIN"
            return 0
        fi
        TESTMAP_ENGINE_ERROR="ENGINE_MISSING:$AIT_TESTMAP_BIN|fix or unset AIT_TESTMAP_BIN"
        return 3
    fi

    # The default root is needed only from here on (dev + release slots).
    if [[ "$home_rc" -ne 0 ]]; then
        case "${AITASKS_HOME_REFUSAL:-}" in
            home-unset)
                # Keep the old check order: a blank root passed _tm_safe, so
                # the next answer was the mode check, and an invalid
                # AIT_ENGINE still gets USAGE/64.
                case "${AIT_ENGINE:-}" in
                    ""|dev)
                        TESTMAP_ENGINE_ERROR="ENGINE_HOME_UNSET:AITASKS_HOME|set AITASKS_HOME, or a non-empty HOME"
                        return 3 ;;
                    *)
                        TESTMAP_ENGINE_ERROR="$_TM_MODE_USAGE"
                        return 64 ;;
                esac ;;
            "")
                # The lib never reported a reason: missing, unreadable or
                # broken. That is an incomplete install, not a HOME problem.
                if _tm_safe "$home_lib"; then
                    TESTMAP_ENGINE_ERROR="ENGINE_LIB_FAILED:$home_lib|run 'ait setup' to repair the install"
                else
                    TESTMAP_ENGINE_ERROR="ENGINE_PATH_UNSAFE:SCRIPT_DIR"
                fi
                return 3 ;;
            *)
                TESTMAP_ENGINE_ERROR="ENGINE_ROOT_INVALID:AITASKS_HOME|$AITASKS_HOME_REFUSAL"
                return 3 ;;
        esac
    fi

    if ! _tm_safe "$AITASKS_HOME"; then
        TESTMAP_ENGINE_ERROR="ENGINE_PATH_UNSAFE:AITASKS_HOME"
        return 3
    fi

    # Tier 2 — the developer slot.
    case "${AIT_ENGINE:-}" in
        "") ;;
        dev)
            slot="$(aitasks_engine_dir dev)/ait-testmap"
            if _tm_check_slot "$slot" dev "$v"; then
                TESTMAP_ENGINE_BIN="$slot"
                return 0
            fi
            TESTMAP_ENGINE_ERROR="ENGINE_MISSING:$slot|run 'ait engine build' or unset AIT_ENGINE"
            return 3
            ;;
        *)
            TESTMAP_ENGINE_ERROR="$_TM_MODE_USAGE"
            return 64
            ;;
    esac

    # Tier 3 — the release slot for exactly this framework VERSION.
    slot="$(aitasks_engine_dir "$v")/ait-testmap"
    if _tm_check_slot "$slot" release "$v"; then
        TESTMAP_ENGINE_BIN="$slot"
        return 0
    fi
    TESTMAP_ENGINE_ERROR="ENGINE_MISSING:$slot|run 'ait setup' or set AIT_TESTMAP_BIN"
    return 3
}

[[ "${1:-}" == "--source-only" ]] && return 0 2>/dev/null || true

rc=0
testmap_resolve_engine || rc=$?
if [[ "$rc" -ne 0 ]]; then
    printf '%s\n' "$TESTMAP_ENGINE_ERROR" >&2
    exit "$rc"
fi
exec "$TESTMAP_ENGINE_BIN" "$@"
