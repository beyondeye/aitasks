#!/usr/bin/env bash
# shellcheck disable=SC2034  # CODEX_QUESTIONS_REG_REASON is read by the sourcing caller.
# codex_questions_registration.sh - does a Codex config register the
# aitask_questions MCP server? (t2324)
#
# Codex starts the server for EVERY valid TOML spelling of the registration:
#   [mcp_servers.aitask_questions]                 (the spelling `ait setup` writes)
#   [mcp_servers."aitask_questions"]               (a quoted key)
#   mcp_servers.aitask_questions.command = "…"     (top-level dotted keys)
# so a literal-header grep is only the fast path; a miss is decided by parsing.
#
# Two consumers, two policies over the same three-way answer:
#   - aitask_setup.sh (questions_server_registered): only a positive detection
#     counts as "registered" -- the registration is the remembered opt-in.
#   - aitask_gate.sh (codex_attended_approvals): an INSPECTION FAILURE enforces
#     the approval guard. The guard is the half of the scope condition that
#     turns receipts on, so "could not tell" must never read as "absent" there:
#     a broken interpreter may block approvals, it must never drop them.
#     Spec: aidocs/codeagents/codex_questions.md "Gate enforcement -> Scope".
#
# Sourced lazily (indented, inside the consumer functions), never on startup.

[[ -n "${_AIT_CODEX_QUESTIONS_REGISTRATION_LOADED:-}" ]] && return 0
_AIT_CODEX_QUESTIONS_REGISTRATION_LOADED=1

# Set to a short reason whenever codex_questions_registration returns 2; read
# by the caller (aitask_gate.sh) for its warning.
CODEX_QUESTIONS_REG_REASON=""

# codex_questions_registration <config> [<python-candidate>...]
#   0  registered
#   1  confirmed absent: the config provably does not exist, or the parsed config has no
#      mcp_servers.aitask_questions, or it is not valid TOML (Codex refuses a
#      config it cannot parse, so it starts nothing from it)
#   2  inspection failed (CODEX_QUESTIONS_REG_REASON says why): the file cannot
#      be read, a directory above it cannot be searched (so it may exist), or
#      it may name the server and no candidate interpreter could parse it
#
# Decision order:
#   1. the path provably does not exist -> 1 (codex_questions_config_absence);
#      it may exist behind an unsearchable directory -> 2; a path that is not a
#      readable regular file -> 2
#   2. the literal header -> 0
#   3. sound no-parser prefilter -> 1: the file holds neither the substring
#      `aitask_questions` nor any \u / \U escape. A TOML key is one atom (a
#      bare, basic-quoted or literal-quoted segment of a dotted key); a
#      basic-string key spells a letter only literally or through a \u / \U
#      escape, a literal-string key only literally. So a key equal to
#      aitask_questions always leaves one of those byte patterns behind, and a
#      project that does not register the server never needs an interpreter.
#   4. parse with each candidate in turn (empty / not-found ones skipped). The
#      verdict is the printed REG:<x> token ONLY, never an exit status: 1 is
#      Python's own failure code, so a crashing interpreter (traceback, 126,
#      127) would otherwise pass for "absent". REG:noparser (neither tomllib
#      nor tomli) or no token -> next candidate.
#   5. no candidate produced a verdict -> 2
# codex_questions_config_absence <path> [<depth>]
#   0  provably absent   1  present   2  cannot tell
# A failed `[[ -e ]]` is NOT proof of absence: stat() fails with EACCES, not
# just ENOENT, when a directory on the way to the path cannot be searched --
# and the file may well be there. Walking up the lexical ancestors, absence is
# proven only when the nearest existing one RESOLVES (its own stat succeeds)
# and is either a directory this process can search (the lookup then really
# found nothing) or not a directory at all (nothing can live below it). A
# symlink ancestor that does not resolve is either dangling (proven absent) or
# points through an unsearchable directory (unknown): it is followed, and is
# proven dangling only when its target is itself provably absent. <depth>
# bounds that following against symlink loops; running out is "cannot tell".
codex_questions_config_absence() {
    local p="$1" depth="${2:-0}" d target rc
    [[ -e "$p" || -L "$p" ]] && return 1
    (( depth > 40 )) && return 2
    d="$(dirname -- "$p")"
    [[ "$d" == "$p" ]] && return 2
    if [[ -e "$d" ]]; then
        [[ -d "$d" ]] || return 0
        [[ -x "$d" ]] && return 0
        return 2
    fi
    if [[ -L "$d" ]]; then
        target="$(readlink -- "$d" 2>/dev/null)" || return 2
        [[ -n "$target" ]] || return 2
        [[ "$target" == /* ]] || target="$(dirname -- "$d")/$target"
        rc=0
        codex_questions_config_absence "$target" "$((depth + 1))" || rc=$?
        (( rc == 0 )) && return 0
        return 2
    fi
    codex_questions_config_absence "$d" "$((depth + 1))" && return 0
    return 2
}

codex_questions_registration() {
    local config="$1"; shift
    local rc cand out tried=""
    CODEX_QUESTIONS_REG_REASON=""

    rc=0
    codex_questions_config_absence "$config" || rc=$?
    case "$rc" in
        0) return 1 ;;
        2) CODEX_QUESTIONS_REG_REASON="cannot search the directory holding $config"; return 2 ;;
    esac
    if [[ ! -f "$config" || ! -r "$config" ]]; then
        CODEX_QUESTIONS_REG_REASON="unreadable: $config"
        return 2
    fi

    rc=0
    grep -q '^\[mcp_servers\.aitask_questions\]' "$config" 2>/dev/null || rc=$?
    case "$rc" in
        0) return 0 ;;
        1) ;;
        *) CODEX_QUESTIONS_REG_REASON="unreadable: $config"; return 2 ;;
    esac

    rc=0
    grep -Eq 'aitask_questions|\\[uU]' "$config" 2>/dev/null || rc=$?
    case "$rc" in
        0) ;;
        1) return 1 ;;
        *) CODEX_QUESTIONS_REG_REASON="unreadable: $config"; return 2 ;;
    esac

    for cand in "$@"; do
        [[ -n "$cand" ]] || continue
        command -v "$cand" >/dev/null 2>&1 || continue
        tried+="${tried:+, }$cand"
        out="$("$cand" - "$config" 2>/dev/null <<'PY' || true
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("REG:noparser")
        raise SystemExit(0)
try:
    with open(sys.argv[1], "rb") as f:
        d = tomllib.load(f)
except tomllib.TOMLDecodeError:
    print("REG:invalid")
    raise SystemExit(0)
s = d.get("mcp_servers")
print("REG:yes" if isinstance(s, dict) and "aitask_questions" in s else "REG:no")
PY
)"
        case "$out" in
            REG:yes) return 0 ;;
            REG:no|REG:invalid) return 1 ;;
        esac
    done

    CODEX_QUESTIONS_REG_REASON="no working TOML parser (tried: ${tried:-none})"
    return 2
}
