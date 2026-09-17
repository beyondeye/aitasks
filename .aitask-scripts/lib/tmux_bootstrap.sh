#!/usr/bin/env bash
# tmux_bootstrap.sh - Spawn a project's tmux session detached.
#
# Shared between `aitask_ide.sh` (sourced), `tui_switcher.py` and
# `agent_restore.py` (both via the standalone CLI form below). Single source of
# truth for: how a session is named, which window is seeded first,
# which env vars are written, and whether the syncer auto-starts.
#
# Sourced form (from aitask_ide.sh):
#     source "$SCRIPT_DIR/lib/tmux_bootstrap.sh"
#     # then call any of the public helpers below.
#
# Standalone form (from tui_switcher.py via `bash <path> <root>`):
#     bash .aitask-scripts/lib/tmux_bootstrap.sh /path/to/project
#         Idempotent — no-op if the target session already exists.
#
# Create-only form (from agent_restore.py, restoring a frozen agent whose
# project has no tmux session — t1784):
#     bash .aitask-scripts/lib/tmux_bootstrap.sh --create-only /path/to/project
#         Create the session or change nothing; see spawn_session_detached.
#         Also refuses (exit 44) when tmux.default_session is unreadable.

# Guard against double-sourcing.
if [[ -n "${_AIT_TMUX_BOOTSTRAP_LOADED:-}" ]]; then
    # shellcheck disable=SC2317  # `return` is reachable when sourced.
    return 0 2>/dev/null || true
fi
_AIT_TMUX_BOOTSTRAP_LOADED=1

# Resolve our own SCRIPT_DIR so the standalone form can find sibling
# scripts (terminal_compat.sh, aitask_projects.sh). When sourced, the
# caller's SCRIPT_DIR already points at .aitask-scripts/; we recompute
# our own anchor here to stay robust to either case.
_TMUX_BOOTSTRAP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_TMUX_BOOTSTRAP_SCRIPTS_DIR="$(cd "$_TMUX_BOOTSTRAP_LIB_DIR/.." && pwd)"

# Gateway for all tmux invocations (socket flag + exact-match targeting),
# shared with the Python TmuxClient. Pulls in terminal_compat.sh (die/warn/info)
# transitively; both are guarded against double-sourcing.
# shellcheck source=tmux_exec.sh disable=SC1091
source "$_TMUX_BOOTSTRAP_LIB_DIR/tmux_exec.sh"

# --- Public helpers (callable after sourcing) ---------------------------

# --- tmux.default_session reader (t1800, t1811) -------------------------
#
# Twin of agent_launch_utils.py::read_default_session_status /
# _classify_line_value; tests/test_tmux_default_session_resolvers.py pins the
# two against each other and against PyYAML (fixed rows plus a generated
# corpus). The shared rule, measured against PyYAML 6.0.3:
#
#   * The key counts only as a direct child of a column-0 `tmux:` block (the
#     block's first indented content line fixes the child indent). The key may
#     be quoted and may have spaces before its colon.
#   * The value is read only when YAML would read back the same string:
#       - only a space separates; a non-empty value must start with one, and
#         trimming removes spaces only (NBSP is content);
#       - a tab outside quotes or a comment, and any C0/DEL/C1, U+2028/2029 or
#         U+FFFE/FFFF byte sequence on the line, is an error for YAML;
#       - quoted: closed on this line, no `\` in "…", no `''` in '…', and only
#         spaces (then an optional `#` comment) after the closing quote;
#       - plain: `#` starts a comment only first or after a space; no leading
#         indicator, no ": " and no trailing ":", and not typed by one of
#         PyYAML's implicit resolvers unless it round-trips (canonical decimal
#         ints, True, False).
#   * Structure it cannot follow is reported, not guessed: a flow or non-mapping
#     `tmux` block holding the key, a value continued onto a line indented
#     differently from the key, and a second key or later `tmux` block (YAML
#     keeps the last one).
#   * Null spellings, empty, comment-only and Unicode-whitespace-only values mean
#     "not configured".
#
# `tr '\r' '\n'` gives awk the universal newlines Python's open() applies, so
# a CRLF blank line (a lone "\r" record) cannot end the block and a CR-only
# file is not read as one record. awk reads to end of input rather than
# `exit`ing on the match: an early exit leaves `tr` writing into a closed pipe
# (SIGPIPE, exit 141), which aborts a direct call under set -e + pipefail. The
# awk runs under LC_ALL=C and matches multibyte sequences as literal byte
# strings passed through the environment, so no awk needs `\x` escapes or
# locale-aware character classes. Output uses printf, never echo — bash's echo
# swallows an option-like name such as `-n`.

# Byte strings for the awk classifier (see _tmux_bootstrap_default_session_scan).
_TMUX_BOOTSTRAP_YAML_CTRL="$(printf '\001\002\003\004\005\006\007\010\013\014\015\016\017\020\021\022\023\024\025\026\027\030\031\032\033\034\035\036\037\177')"
_TMUX_BOOTSTRAP_YAML_C1LEAD="$(printf '\302')"
_TMUX_BOOTSTRAP_YAML_C1TAIL="$(printf '\200\201\202\203\204\205\206\207\210\211\212\213\214\215\216\217\220\221\222\223\224\225\226\227\230\231\232\233\234\235\236\237')"
_TMUX_BOOTSTRAP_YAML_BREAKS="$(printf '\342\200\250|\342\200\251|\357\277\276|\357\277\277')"
_TMUX_BOOTSTRAP_YAML_BLANKS="$(printf ' |\t|\302\240|\341\232\200|\342\200\200|\342\200\201|\342\200\202|\342\200\203|\342\200\204|\342\200\205|\342\200\206|\342\200\207|\342\200\210|\342\200\211|\342\200\212|\342\200\257|\342\201\237|\343\200\200')"
_TMUX_BOOTSTRAP_YAML_BOM="$(printf '\357\273\277')"

# awk functions shared by the reader (scan) and the writer (render), so both
# agree on which line opens the `tmux` block and which carries the key. Callers
# pass `-v SQ="'"`.
#   key_match(s, name): 1 if s opens key `name` (plain or quoted, spaces allowed
#     before the colon); sets KREST to the text after the colon.
#   header_kind(line): for a column-0 line, "" unless it opens `tmux`; "map"
#     (nothing, a comment, a named `&anchor` or exactly `!!map` after the colon),
#     "flow" (`{`/`[`) or "invalid" (any other inline content — every other tag
#     included, since YAML fails or reads a non-mapping). Mirrors
#     agent_launch_utils._tmux_header_kind.
# shellcheck disable=SC2016  # awk source, not shell expansions
_TMUX_BOOTSTRAP_AWK_KEYS='
        function key_match(s, name,    n, q) {
            n = length(name)
            if (substr(s, 1, n) == name) {
                s = substr(s, n + 1)
            } else {
                q = substr(s, 1, 1)
                if ((q == "\"" || q == SQ) && substr(s, 2, n) == name && substr(s, n + 2, 1) == q)
                    s = substr(s, n + 3)
                else
                    return 0
            }
            sub(/^ */, "", s)
            if (substr(s, 1, 1) != ":") return 0
            KREST = substr(s, 2)
            return 1
        }
        function header_kind(line,    r, p, c) {
            if (!key_match(line, "tmux")) return ""
            r = KREST
            if (r == "") return "map"
            if (substr(r, 1, 1) != " ") return ""
            p = index(r, " #")
            if (p) r = substr(r, 1, p - 1)
            sub(/^ +/, "", r); sub(/ +$/, "", r)
            if (r == "") return "map"
            c = substr(r, 1, 1)
            if (c == "{" || c == "[") return "flow"
            if (r == "!!map" || r ~ /^&[0-9A-Za-z_-]+$/) return "map"
            return "invalid"
        }
'

# _tmux_bootstrap_default_session_scan <project_root>
#
# Prints exactly one line: `ok<TAB><value>` (an empty value means "not
# configured", including a missing config file) or `bad<TAB><shape>`, with
# <shape> from agent_launch_utils.DEFAULT_SESSION_PROBLEM_SHAPES. Writes nothing
# to stderr and always returns 0; the public helpers below decide what to say.
_tmux_bootstrap_default_session_scan() {
    local cfg="$1/aitasks/metadata/project_config.yaml"
    if [[ ! -f "$cfg" ]]; then
        printf 'ok\t\n'
        return 0
    fi
    tr '\r' '\n' < "$cfg" | LC_ALL=C \
        CTRL="$_TMUX_BOOTSTRAP_YAML_CTRL" C1LEAD="$_TMUX_BOOTSTRAP_YAML_C1LEAD" \
        C1TAIL="$_TMUX_BOOTSTRAP_YAML_C1TAIL" BREAKS="$_TMUX_BOOTSTRAP_YAML_BREAKS" \
        BLANKS="$_TMUX_BOOTSTRAP_YAML_BLANKS" BOM="$_TMUX_BOOTSTRAP_YAML_BOM" \
        awk -v SQ="'" "$_TMUX_BOOTSTRAP_AWK_KEYS"'
        function has_control(s,    i, n, c, k) {
            n = length(s)
            for (i = 1; i <= n; i++) {
                c = substr(s, i, 1)
                if (index(ENVIRON["CTRL"], c)) return 1
                if (c == ENVIRON["C1LEAD"] && i < n && index(ENVIRON["C1TAIL"], substr(s, i + 1, 1))) return 1
            }
            for (k = 1; k <= nbreaks; k++) if (index(s, BRK[k])) return 1
            return 0
        }
        function strip_blank(s,    k, p, seq) {
            for (k = 1; k <= nblanks; k++) {
                seq = BLK[k]
                while ((p = index(s, seq)) > 0) s = substr(s, 1, p - 1) substr(s, p + length(seq))
            }
            return s
        }
        # PyYAML 6.0.3 implicit resolvers (yaml/resolver.py): bool, int, float,
        # timestamp, merge, value. Keep in sync with _YAML_TYPED_PLAIN.
        function typed(v) {
            if (v ~ /^(yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF)$/) return 1
            if (v ~ /^[-+]?(0b[0-1_]+|0[0-7_]+|0|[1-9][0-9_]*|0x[0-9a-fA-F_]+|[1-9][0-9_]*(:[0-5]?[0-9])+)$/) return 1
            if (v ~ /^([-+]?[0-9][0-9_]*\.[0-9_]*([eE][-+][0-9]+)?|\.[0-9][0-9_]*([eE][-+][0-9]+)?|[-+]?[0-9][0-9_]*(:[0-5]?[0-9])+\.[0-9_]*|[-+]?\.(inf|Inf|INF)|\.(nan|NaN|NAN))$/) return 1
            if (v ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) return 1
            if (v ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?([Tt]|[ \t]+)[0-9][0-9]?:[0-9][0-9]:[0-9][0-9](\.[0-9]*)?([ \t]*(Z|[-+][0-9][0-9]?(:[0-9][0-9])?))?$/) return 1
            return (v == "<<" || v == "=")
        }
        # Sets CVAL to the value (empty = not configured); returns a shape or "".
        function classify(raw,    h, s, q, e, body, tr, cut, v) {
            CVAL = ""
            if (raw == "") return ""
            if (has_control(raw)) return "tab_or_control"
            h = substr(raw, 1, 1)
            if (h != " ") return (h == "\t" ? "tab_or_control" : "missing_separator")
            s = raw
            sub(/^ +/, "", s)
            if (s == "") return ""
            q = substr(s, 1, 1)
            if (q == "\"" || q == SQ) {
                e = index(substr(s, 2), q)
                if (e == 0) return "continuation"
                e = e + 1
                if (q == SQ && substr(s, e + 1, 1) == SQ) return "quoted_escape"
                body = substr(s, 2, e - 2)
                if (q == "\"" && index(body, "\\")) return "quoted_escape"
                tr = substr(s, e + 1)
                sub(/^ +/, "", tr)
                if (tr != "" && substr(tr, 1, 1) != "#")
                    return (substr(tr, 1, 1) == "\t" ? "tab_or_control" : "trailing_content")
                if (strip_blank(body) != "") CVAL = body
                return ""
            }
            if (q == "#") return ""
            cut = index(s, " #")
            v = (cut ? substr(s, 1, cut - 1) : s)
            sub(/ +$/, "", v)
            if (index(v, "\t")) return "tab_or_control"
            h = substr(v, 1, 1)
            if (h == "|" || h == ">") return "block_scalar"
            if (h == "[" || h == "{") return "flow_collection"
            if (h == "&" || h == "*" || h == "!") return "node_property"
            if (index(",]}%@`", h)) return "indicator"
            if ((h == "-" || h == "?" || h == ":") && (length(v) == 1 || substr(v, 2, 1) == " ")) return "indicator"
            if (v == "~" || v == "null" || v == "Null" || v == "NULL") return ""
            if (index(v, ": ") || substr(v, length(v), 1) == ":") return "mapping_indicator"
            if (typed(v) && v !~ /^(0|-?[1-9][0-9]*|True|False)$/) return "typed_scalar"
            if (strip_blank(v) != "") CVAL = v
            return ""
        }
        BEGIN {
            nbreaks = split(ENVIRON["BREAKS"], BRK, "|")
            nblanks = split(ENVIRON["BLANKS"], BLK, "|")
            block = ""; ci = -1; found = 0; val = ""; problem = ""; check_next = 0
        }
        {
            line = $0
            if (NR == 1 && substr(line, 1, length(ENVIRON["BOM"])) == ENVIRON["BOM"])
                line = substr(line, length(ENVIRON["BOM"]) + 1)
            t = line
            gsub(/[ \t]/, "", t)
            if (t == "") next
            t = line
            sub(/^[ \t]+/, "", t)
            if (substr(t, 1, 1) == "#") next
            c1 = substr(line, 1, 1)
            if (check_next) {
                # The line after the key decides whether its value continues.
                check_next = 0
                if (c1 == " ") {
                    match(line, /^ +/)
                    if (RLENGTH != ci && problem == "") problem = "continuation"
                }
            }
            if (c1 != " " && c1 != "\t") {
                h = header_kind(line)
                if (h != "" && found && problem == "") problem = "duplicate_key"
                if ((h == "flow" || h == "invalid") && index(line, "default_session") && problem == "")
                    problem = (h == "flow" ? "flow_mapping" : "invalid_block")
                block = h; ci = -1
                next
            }
            # Tab indentation is invalid YAML; the Python twin ignores it too.
            if (block == "" || c1 == "\t") next
            if (block != "map") {
                if (index(line, "default_session") && problem == "")
                    problem = (block == "flow" ? "flow_mapping" : "invalid_block")
                next
            }
            match(line, /^ +/)
            ind = RLENGTH
            if (ci < 0) ci = ind
            if (ind != ci) next
            if (!key_match(substr(line, ind + 1), "default_session")) next
            if (found) {
                if (problem == "") problem = "duplicate_key"
                next
            }
            found = 1
            shape = classify(KREST)
            if (shape != "" && problem == "") problem = shape
            val = CVAL
            check_next = 1
        }
        END {
            if (problem != "") printf "bad\t%s\n", problem
            else printf "ok\t%s\n", val
        }
    '
}

# _tmux_bootstrap_report_unreadable <config_path> <shape>
#
# The structured sentinel first (parsed by
# agent_launch_utils.parse_default_session_unreadable), then the human line —
# the same two-line shape as the BOOTSTRAP_FAILED: refusals.
_tmux_bootstrap_report_unreadable() {
    printf 'DEFAULT_SESSION_UNREADABLE:%s:%s\n' "$2" "$1" >&2
    # shellcheck disable=SC2016  # the backticks are literal text in the message
    printf 'Warning: tmux.default_session in %s is not a single-line plain or quoted value (%s); write it as e.g. `default_session: myproject`\n' "$1" "$2" >&2
}

# _tmux_bootstrap_default_session_raw <project_root>
#
# Prints the configured `tmux.default_session`, or nothing when it is not
# configured; returns 0. When the value cannot be read faithfully, prints
# nothing to stdout, reports it on stderr and returns 2 — the caller decides
# whether to fall back (ait ide, ensure-mode bootstrap) or refuse
# (--create-only), or to leave the file alone (ait setup).
_tmux_bootstrap_default_session_raw() {
    local scan
    scan=$(_tmux_bootstrap_default_session_scan "$1")
    case "$scan" in
        bad$'\t'*)
            _tmux_bootstrap_report_unreadable "$1/aitasks/metadata/project_config.yaml" "${scan#bad$'\t'}"
            return 2
            ;;
        ok$'\t'?*)
            printf '%s\n' "${scan#ok$'\t'}"
            ;;
    esac
    return 0
}

# _tmux_bootstrap_resolve_session <project_root>
#
# Prints the tmux session name for <project_root>: the configured
# `tmux.default_session`, or the literal "aitasks" when it is absent, blank, or
# unreadable (reported on stderr by the raw reader).
_tmux_bootstrap_resolve_session() {
    local name rc=0
    name=$(_tmux_bootstrap_default_session_raw "$1") || rc=$?
    if [[ $rc -eq 2 ]]; then
        printf "Warning: using tmux session 'aitasks' instead\n" >&2
    fi
    if [[ $rc -ne 0 || -z "$name" ]]; then
        name=aitasks
    fi
    printf '%s\n' "$name"
}

# _tmux_bootstrap_session_for <project_root> [override]
#
# The session `ait ide` targets: a non-empty <override> verbatim (`--session`),
# otherwise the resolved session for <project_root>.
_tmux_bootstrap_session_for() {
    if [[ -n "${2:-}" ]]; then
        printf '%s\n' "$2"
        return 0
    fi
    _tmux_bootstrap_resolve_session "$1"
}

# _tmux_bootstrap_yaml_session_literal <name>
#
# The YAML spelling of <name> that the reader above reads back verbatim: plain
# for an identifier YAML does not type (not a bool or null spelling), otherwise
# single-quoted, or double-quoted when the name holds a `'` (the reader refuses
# a doubled `''`). Returns 1 for a name no spelling carries — one holding both a
# `'` and a `"` or `\`. Control characters are left to the caller's read-back.
_tmux_bootstrap_yaml_session_literal() {
    local v="$1"
    if [[ "$v" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] \
        && ! [[ "$v" =~ ^(yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF|null|Null|NULL)$ ]]; then
        printf '%s' "$v"
    elif [[ "$v" != *\'* ]]; then
        printf "'%s'" "$v"
    elif [[ "$v" != *\"* && "$v" != *\\* ]]; then
        printf '"%s"' "$v"
    else
        return 1
    fi
}

# _tmux_bootstrap_render_default_session <config_file> <yaml_literal>
#
# Prints <config_file> with `tmux.default_session` set to <yaml_literal>, without
# modifying the file. Only the direct child of the LAST column-0 `tmux:` block
# (the one YAML keeps) at the block's child indent is replaced, keeping the key's
# own spelling and dropping its old value and comment; a nested
# `syncer: default_session:` is left alone. With no key in that block the key is
# inserted right after the header at the child indent (2 when the block has no
# children); with no block, one is appended. The literal is passed through the
# environment, never `awk -v`, which would process backslash escapes. CRLF line
# endings are preserved, including on inserted lines.
_tmux_bootstrap_render_default_session() {
    LC_ALL=C LITERAL="$2" BOM="$_TMUX_BOOTSTRAP_YAML_BOM" \
        awk -v SQ="'" "$_TMUX_BOOTSTRAP_AWK_KEYS"'
        function bare(i,    l) {
            l = L[i]
            sub(/\r$/, "", l)
            if (i == 1 && substr(l, 1, length(ENVIRON["BOM"])) == ENVIRON["BOM"])
                l = substr(l, length(ENVIRON["BOM"]) + 1)
            return l
        }
        function eol(i) { return (L[i] ~ /\r$/) ? "\r" : "" }
        { L[NR] = $0 }
        END {
            n = NR; hdr = 0
            for (i = 1; i <= n; i++) {
                c = substr(bare(i), 1, 1)
                if (c == "" || c == " " || c == "\t" || c == "#") continue
                if (header_kind(bare(i)) == "map") hdr = i
            }
            if (!hdr) {
                for (i = 1; i <= n; i++) print L[i]
                e = (n ? eol(1) : "")
                printf "%s\ntmux:%s\n  default_session: %s%s\n", e, e, ENVIRON["LITERAL"], e
                exit
            }
            ci = -1; key = 0
            for (i = hdr + 1; i <= n; i++) {
                l = bare(i)
                t = l; gsub(/[ \t]/, "", t)
                if (t == "") continue
                t = l; sub(/^[ \t]+/, "", t)
                if (substr(t, 1, 1) == "#") continue
                c = substr(l, 1, 1)
                if (c != " " && c != "\t") break
                if (c == "\t") continue
                match(l, /^ +/); ind = RLENGTH
                if (ci < 0) ci = ind
                if (ind == ci && key_match(substr(l, ind + 1), "default_session")) { key = i; break }
            }
            for (i = 1; i <= n; i++) {
                if (i == key) {
                    l = bare(i)
                    key_match(substr(l, ci + 1), "default_session")
                    print substr(l, 1, length(l) - length(KREST)) " " ENVIRON["LITERAL"] eol(i)
                    continue
                }
                print L[i]
                if (i == hdr && !key) {
                    pad = ""
                    for (k = 0; k < (ci > 0 ? ci : 2); k++) pad = pad " "
                    print pad "default_session: " ENVIRON["LITERAL"] eol(i)
                }
            }
        }
    ' "$1"
}

# _tmux_bootstrap_read_syncer_autostart <project_root>
#
# Echoes "1" if tmux.syncer.autostart is true in <project_root>'s
# project_config.yaml; "0" otherwise (mirrors
# aitask_ide.sh::read_syncer_autostart).
_tmux_bootstrap_read_syncer_autostart() {
    local root="$1"
    local cfg="$root/aitasks/metadata/project_config.yaml"
    [[ -f "$cfg" ]] || { echo "0"; return; }
    local out
    out=$(awk '
        /^tmux:/ { intmux=1; next }
        intmux && /^  syncer:/ { insyncer=1; next }
        insyncer && /^    autostart:/ {
            sub(/^    autostart:[ \t]*/, "")
            gsub(/"/, "")
            gsub(/'"'"'/, "")
            sub(/[[:space:]]+$/, "")
            if ($0 == "true") { print "1"; exit }
            print "0"; exit
        }
        /^[^ #]/ && !/^tmux:/ { intmux=0; insyncer=0 }
        intmux && /^  [^ ]/ && !/^  syncer:/ { insyncer=0 }
    ' "$cfg" 2>/dev/null)
    [[ -z "$out" ]] && out="0"
    echo "$out"
}

# _tmux_bootstrap_set_project_registry <project_root> <session>
#
# Registers <project_root> under the per-session tmux global env var
# AITASKS_PROJECT_<session> AND appends it to the per-user persistent
# index via `aitask_projects.sh add`. Both writes are best-effort.
_tmux_bootstrap_set_project_registry() {
    local root="$1"
    local session="$2"
    ait_tmux set-environment -g "AITASKS_PROJECT_${session}" "$root" 2>/dev/null || true
    "$_TMUX_BOOTSTRAP_SCRIPTS_DIR/aitask_projects.sh" add "$root" >/dev/null 2>&1 || true
}

# _tmux_bootstrap_ensure_syncer_window <project_root> <session>
#
# If the project's syncer autostart flag is on AND the session does
# not already have a `syncer` window, creates one (with cwd anchored
# at <project_root> so `ait syncer` resolves correctly).
_tmux_bootstrap_ensure_syncer_window() {
    local root="$1"
    local session="$2"
    local autostart
    autostart=$(_tmux_bootstrap_read_syncer_autostart "$root")
    [[ "$autostart" == "1" ]] || return 0
    local session_t
    session_t="$(ait_tmux_session_target "$session")"
    if ! ait_tmux list-windows -t "$session_t" -F '#{window_name}' 2>/dev/null | grep -qx 'syncer'; then
        ait_tmux new-window -t "${session_t}:" -c "$root" -n syncer 'ait syncer' 2>/dev/null || true
    fi
}

# _tmux_bootstrap_report_exists <session>
#
# The --create-only refusal: a structured sentinel first (parsed by
# agent_restore._bootstrap_project_session), then the human-readable detail —
# the same two-line shape as the BOOTSTRAP_FAILED:stale_path refusal.
_tmux_bootstrap_report_exists() {
    echo "BOOTSTRAP_FAILED:session_exists:$1" >&2
    echo "spawn_session_detached: session '$1' already exists; --create-only leaves it untouched" >&2
}

# spawn_session_detached <project_root> [--create-only]
#
# Idempotently spawns a detached tmux session for <project_root> with
# the project's configured session name and a seeded `monitor` window.
# If the session already exists, only the per-session env / persistent
# registry / syncer-window steps run (the existing session is left
# untouched). Safe to call from inside another tmux session.
#
# --create-only: CREATE the session or change NOTHING (t1784). The default
# mode is "ensure", which is right for `ait ide` — a user running it in a
# project means "this session is mine" — but wrong for a caller that must not
# claim a session it does not own: the registry and syncer steps would re-point
# a same-named session belonging to another project at <project_root>, and
# `discover_aitasks_sessions()` falls back to that registry entry. With the flag:
#   - an existing session of that name is left completely untouched (no env,
#     no registry, no syncer window) and reported on stderr as
#     BOOTSTRAP_FAILED:session_exists:<name>, exit 43;
#   - so is one created concurrently between the check and `new-session`: the
#     duplicate `new-session` fails and the name now exists — same report;
#   - only after THIS call created the session do the registry and syncer steps
#     run, and stdout then carries BOOTSTRAP_CREATED:<name> — the one answer a
#     caller may treat as ownership;
#   - an unreadable `tmux.default_session` is refused before any tmux call
#     (BOOTSTRAP_FAILED:default_session_unreadable:<shape>, exit 44). Ensure
#     mode instead warns (DEFAULT_SESSION_UNREADABLE:<shape>:<cfg>) and uses
#     "aitasks": its callers can show that warning, a detached restore cannot.
#
# Exit codes: 2 usage / not a directory, 3 tmux missing, 4 new-session failed,
# 42 not an aitasks project (BOOTSTRAP_FAILED:stale_path), 43 the session
# already exists (--create-only only), 44 unreadable default_session
# (--create-only only).
spawn_session_detached() {
    local root="$1"
    local mode="${2:-}"
    if [[ -n "$mode" && "$mode" != "--create-only" ]]; then
        echo "spawn_session_detached: unknown option: $mode" >&2
        return 2
    fi
    if [[ -z "$root" ]]; then
        echo "spawn_session_detached: missing <project_root>" >&2
        return 2
    fi
    if [[ ! -d "$root" ]]; then
        echo "spawn_session_detached: not a directory: $root" >&2
        return 2
    fi
    if [[ ! -f "$root/aitasks/metadata/project_config.yaml" ]]; then
        # Structured sentinel consumed by tui_switcher._ensure_session_live
        # (race-condition path: entry was OK at switcher mount but went
        # STALE before bootstrap). Followed by the human-readable detail
        # so casual CLI users still see what went wrong.
        echo "BOOTSTRAP_FAILED:stale_path" >&2
        echo "spawn_session_detached: not an aitasks project: $root" >&2
        return 42
    fi

    local session session_t scan shape
    scan=$(_tmux_bootstrap_default_session_scan "$root")
    if [[ "$scan" == bad$'\t'* ]]; then
        shape="${scan#bad$'\t'}"
        _tmux_bootstrap_report_unreadable "$root/aitasks/metadata/project_config.yaml" "$shape"
        if [[ "$mode" == "--create-only" ]]; then
            # A caller that cannot show a warning must not create a session
            # under a guessed name: refuse before touching tmux (t1811).
            echo "BOOTSTRAP_FAILED:default_session_unreadable:$shape" >&2
            echo "spawn_session_detached: tmux.default_session is unreadable ($shape); --create-only creates nothing" >&2
            return 44
        fi
        echo "spawn_session_detached: using tmux session 'aitasks' instead" >&2
        session=aitasks
    else
        session="${scan#ok$'\t'}"
        [[ -n "$session" ]] || session=aitasks
    fi
    session_t="$(ait_tmux_session_target "$session")"

    command -v tmux >/dev/null || {
        echo "spawn_session_detached: tmux is not installed" >&2
        return 3
    }

    if ! ait_tmux has-session -t "$session_t" 2>/dev/null; then
        # Legacy-session detection (t953): a same-name session may still live
        # on the user's default server from before the dedicated-socket move
        # (tmux cannot move sessions between servers). Warn-only here — this
        # path is non-interactive (tui_switcher bootstrap); `ait ide` runs its
        # own interactive offer before reaching this helper. Skipped when the
        # gateway already targets the default server.
        local sock_name
        sock_name="$(ait_tmux_socket_name)"
        if [[ -n "$sock_name" && "$sock_name" != "default" ]] \
            && ait_tmux_legacy has-session -t "$session_t" 2>/dev/null; then
            echo "WARNING: session '$session' also exists on the legacy default tmux server;" >&2
            echo "         run 'AITASKS_TMUX_SOCKET=default ait ide' to reach it." >&2
        fi
        # First session => this call creates the tmux SERVER. Spawn it inside a
        # persistent systemd-user service (session.slice) so a compositor /
        # app.slice teardown no longer kills the server (t943). The socket flag
        # comes from the gateway (dedicated `-L ait` by default, t953); the
        # helper also fixes the new server's cgroup placement. It degrades
        # gracefully (setsid → plain tmux) where systemd --user is unavailable.
        # new-session -s takes a literal session name; do not prefix '='.
        ait_tmux_new_session_persistent "$session" "$root" monitor 'ait monitor' \
            || {
                # --create-only: a name that exists NOW was created concurrently
                # by someone else. It is not ours — report it and touch nothing.
                if [[ "$mode" == "--create-only" ]] \
                    && ait_tmux has-session -t "$session_t" 2>/dev/null; then
                    _tmux_bootstrap_report_exists "$session"
                    return 43
                fi
                echo "spawn_session_detached: tmux new-session failed for '$session'" >&2
                return 4
            }
    elif [[ "$mode" == "--create-only" ]]; then
        # An existing session, and the caller asked to create or change nothing:
        # return BEFORE the registry / syncer steps, which would re-point it.
        _tmux_bootstrap_report_exists "$session"
        return 43
    fi

    _tmux_bootstrap_set_project_registry "$root" "$session"
    _tmux_bootstrap_ensure_syncer_window "$root" "$session"
    if [[ "$mode" == "--create-only" ]]; then
        echo "BOOTSTRAP_CREATED:$session"
    fi
    return 0
}

# --- Standalone CLI dispatch -------------------------------------------

# When invoked as `bash tmux_bootstrap.sh <project_root>`, dispatch
# to spawn_session_detached. Distinguish "sourced vs. executed" via
# BASH_SOURCE[0] == $0.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -euo pipefail
    _tmux_bootstrap_mode=""
    if [[ "${1:-}" == "--create-only" ]]; then
        _tmux_bootstrap_mode="--create-only"
        shift
    fi
    if [[ $# -lt 1 ]]; then
        echo "Usage: tmux_bootstrap.sh [--create-only] <project_root>" >&2
        exit 2
    fi
    # Source error helpers only when standalone (saves a round-trip
    # when sourced by aitask_ide.sh, which already loads them).
    # shellcheck source=terminal_compat.sh disable=SC1091
    source "$_TMUX_BOOTSTRAP_LIB_DIR/terminal_compat.sh"
    spawn_session_detached "$1" ${_tmux_bootstrap_mode:+"$_tmux_bootstrap_mode"}
fi
