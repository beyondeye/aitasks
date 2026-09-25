#!/usr/bin/env bash
# shellcheck disable=SC2016  # the bash -c snippets expand in the child, by design
# test_claude_hook_status.sh - detecting a missing Claude Code session hook (t1849).
#
# `ait upgrade` stages the hook seed but only `ait setup` merges it, so an
# upgraded-only project has no hook. lib/claude_hook_status.sh is what notices.
# Covers:
#   A  claude_session_hook_status — every state, incl. the Python-less branches
#   B  claude_session_hook_runtime — why the hook could not work, per reason
#   C  the repair advice / hints follow the runtime reason
#   D  merge_claude_hooks now FAILS (non-zero) instead of warning and returning 0
#   E  install.sh's upgrade-path report
#   F  `ait ide`'s frozen-agent offer prints the forward-looking note
#
# "Python hidden" = PATH is a temp bin dir holding a symlink to every command on
# the real PATH except python*/pypy*, plus a temp HOME (no ~/.aitask venv).
#
# Run: bash tests/test_claude_hook_status.sh

set -uo pipefail

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

LIB="$PROJECT_DIR/.aitask-scripts/lib/claude_hook_status.sh"
SEED="$PROJECT_DIR/seed/claude_settings.hooks.json"
TESTROOT="$(mktemp -d "${TMPDIR:-/tmp}/t1849_status_XXXXXX")"
trap 'rm -rf "$TESTROOT"' EXIT

# --- fixtures --------------------------------------------------------------

# The real PATH minus the framework's own ~/.aitask/* dirs: its python3 there is
# a wrapper that execs $HOME/.aitask/venv/bin/python, so under the temp HOMEs
# below it would exit 127 and look like a broken interpreter.
CLEAN_PATH=""
IFS=':' read -r -a _path_dirs <<<"$PATH"
for _d in "${_path_dirs[@]}"; do
    case "$_d" in */.aitask/*|*/.aitask) continue ;; esac
    CLEAN_PATH="${CLEAN_PATH:+$CLEAN_PATH:}$_d"
done
REAL_PY="$(PATH="$CLEAN_PATH" command -v python3)"

# A PATH without any python.
NOPY_BIN="$TESTROOT/nopy_bin"
mkdir -p "$NOPY_BIN"
IFS=':' read -r -a _path_dirs <<<"$CLEAN_PATH"
for _d in "${_path_dirs[@]}"; do
    [[ -d "$_d" ]] || continue
    for _f in "$_d"/*; do
        _n="${_f##*/}"
        case "$_n" in python*|pypy*) continue ;; esac
        [[ -x "$_f" && ! -e "$NOPY_BIN/$_n" ]] && ln -s "$_f" "$NOPY_BIN/$_n"
    done
done

# A "pre-minimum" interpreter: the real python3 for everything except the
# sys.version_info predicate, which it fails.
OLD_PY="$TESTROOT/old_python"
cat >"$OLD_PY" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do case "\$a" in *version_info*) exit 1 ;; esac; done
exec "$REAL_PY" "\$@"
EOF
chmod +x "$OLD_PY"

EMPTY_HOME="$TESTROOT/home_empty"
mkdir -p "$EMPTY_HOME"
OLD_VENV_HOME="$TESTROOT/home_oldvenv"
mkdir -p "$OLD_VENV_HOME/.aitask/venv/bin"
ln -s "$OLD_PY" "$OLD_VENV_HOME/.aitask/venv/bin/python"

# make_proj <name> — a project dir with the hook seed staged in metadata.
make_proj() {
    local dir="$TESTROOT/$1"
    mkdir -p "$dir/aitasks/metadata" "$dir/.aitask-scripts"
    ln -s "$PROJECT_DIR/.aitask-scripts/lib" "$dir/.aitask-scripts/lib"
    cp "$SEED" "$dir/aitasks/metadata/claude_settings.hooks.json"
    echo "$dir"
}

# in_env <mode> <cmd...> — run a shell snippet in a fresh process.
#   mode: normal | nopy | override_old | venv_old
in_env() {
    local mode="$1"; shift
    case "$mode" in
        normal)       env -u AIT_PYTHON HOME="$EMPTY_HOME" PATH="$CLEAN_PATH" bash -c "$1" _ "${@:2}" ;;
        nopy)         env -u AIT_PYTHON HOME="$EMPTY_HOME" PATH="$NOPY_BIN" bash -c "$1" _ "${@:2}" ;;
        override_old) env AIT_PYTHON="$OLD_PY" HOME="$EMPTY_HOME" PATH="$CLEAN_PATH" bash -c "$1" _ "${@:2}" ;;
        venv_old)     env -u AIT_PYTHON HOME="$OLD_VENV_HOME" PATH="$CLEAN_PATH" bash -c "$1" _ "${@:2}" ;;
    esac
}

status_of() {  # status_of <mode> <dir>
    in_env "$1" 'source "$1"; claude_session_hook_status "$2"' "$LIB" "$2"
}

echo "=== Claude Code session hook status (t1849) ==="

echo ""
echo "--- Group A: claude_session_hook_status ---"

P="$(make_proj a_noseed)"; rm "$P/aitasks/metadata/claude_settings.hooks.json"
assert_eq "A: no seed -> NO_SEED" "NO_SEED" "$(status_of normal "$P")"

P="$(make_proj a_nofile)"
assert_eq "A: no settings.json -> MISSING" "MISSING" "$(status_of normal "$P")"
assert_eq "A: no settings.json, Python hidden -> MISSING (no parse needed)" "MISSING" \
    "$(status_of nopy "$P")"

P="$(make_proj a_unnamed)"; mkdir -p "$P/.claude"
printf '{"env": {"K": "V"}}\n' >"$P/.claude/settings.json"
assert_eq "A: settings.json without the hook -> MISSING" "MISSING" "$(status_of normal "$P")"
assert_eq "A: ...and with Python hidden (never names the script) -> MISSING" "MISSING" \
    "$(status_of nopy "$P")"

P="$(make_proj a_matcher)"; mkdir -p "$P/.claude"
cat >"$P/.claude/settings.json" <<'EOF'
{"hooks": {"SessionStart": [
  {"matcher": "clear", "hooks": [{"type": "command", "command": "$CLAUDE_PROJECT_DIR/.aitask-scripts/aitask_session_hook.sh"}]}
]}}
EOF
assert_eq "A: hook under a different matcher -> MISSING (merge would add it)" "MISSING" \
    "$(status_of normal "$P")"
assert_eq "A: ...and with Python hidden it cannot be decided -> UNKNOWN" "UNKNOWN" \
    "$(status_of nopy "$P")"

P="$(make_proj a_installed)"; mkdir -p "$P/.claude"
cp "$SEED" "$P/.claude/settings.json"
assert_eq "A: seed copied -> INSTALLED" "INSTALLED" "$(status_of normal "$P")"

P="$(make_proj a_abs)"; mkdir -p "$P/.claude"
cat >"$P/.claude/settings.json" <<EOF
{"hooks": {"SessionStart": [
  {"matcher": "startup|resume", "hooks": [{"type": "command", "command": "$P/.aitask-scripts/aitask_session_hook.sh"}]}
]}}
EOF
assert_eq "A: absolute-path spelling of the same script -> INSTALLED" "INSTALLED" \
    "$(status_of normal "$P")"

P="$(make_proj a_badjson)"; mkdir -p "$P/.claude"
printf '{"hooks": {\n' >"$P/.claude/settings.json"
assert_eq "A: invalid JSON -> INVALID (never MISSING)" "INVALID" "$(status_of normal "$P")"

P="$(make_proj a_hookslist)"; mkdir -p "$P/.claude"
printf '{"hooks": []}\n' >"$P/.claude/settings.json"
assert_eq "A: hooks is a list -> INVALID" "INVALID" "$(status_of normal "$P")"

echo ""
echo "--- Group B: claude_session_hook_runtime ---"
runtime_of() { in_env "$1" 'source "$1"; claude_session_hook_runtime' "$LIB"; }

assert_eq "B: normal machine -> OK" "OK" "$(runtime_of normal)"
assert_eq "B: Python hidden -> NO_PYTHON3" "NO_PYTHON3" "$(runtime_of nopy)"
assert_eq "B: AIT_PYTHON older than the minimum -> OVERRIDE_TOO_OLD" \
    "OVERRIDE_TOO_OLD:$OLD_PY" "$(runtime_of override_old)"
assert_eq "B: old venv interpreter, no override -> TOO_OLD" \
    "TOO_OLD:$OLD_VENV_HOME/.aitask/venv/bin/python" "$(runtime_of venv_old)"
assert_eq "B: _runtime_ok fails with Python hidden" "1" \
    "$(in_env nopy 'source "$1"; claude_session_hook_runtime_ok; echo $?' "$LIB")"
assert_eq "B: _runtime_ok passes normally" "0" \
    "$(in_env normal 'source "$1"; claude_session_hook_runtime_ok; echo $?' "$LIB")"
BROKEN_BIN="$TESTROOT/broken_bin"
mkdir -p "$BROKEN_BIN"
printf '#!/usr/bin/env bash\nexit 127\n' >"$BROKEN_BIN/python3"
chmod +x "$BROKEN_BIN/python3"
out="$(env AIT_PYTHON="$REAL_PY" HOME="$EMPTY_HOME" PATH="$BROKEN_BIN:$CLEAN_PATH" \
    bash -c 'source "$1"; claude_session_hook_runtime; claude_session_hook_repair' _ "$LIB")"
assert_contains "B: python3 on PATH that does not run -> PYTHON3_BROKEN (despite AIT_PYTHON)" \
    "PYTHON3_BROKEN:$BROKEN_BIN/python3" "$out"
assert_contains "B: ...repair names it and says to fix it" "repair or replace it" "$out"
WRAP_HOME="$TESTROOT/home_wrapper"
mkdir -p "$WRAP_HOME/.aitask/bin"
cp "$BROKEN_BIN/python3" "$WRAP_HOME/.aitask/bin/python3"
out="$(env -u AIT_PYTHON HOME="$WRAP_HOME" PATH="$WRAP_HOME/.aitask/bin:$CLEAN_PATH" \
    bash -c 'source "$1"; claude_session_hook_repair' _ "$LIB")"
assert_contains "B: the framework wrapper broken -> full ait setup repairs it" \
    "the full 'ait setup', which repairs it" "$out"
# The memo must not stand in for a fresh resolution: a stale value resolved
# before AIT_PYTHON changed would hide the override.
assert_eq "B: a stale resolve_python memo is bypassed" "OVERRIDE_TOO_OLD:$OLD_PY" \
    "$(in_env override_old 'source "$1"; _AIT_RESOLVED_PYTHON="$2"; claude_session_hook_runtime' "$LIB" "$REAL_PY")"

echo ""
echo "--- Group C: repair advice follows the runtime reason ---"
hint_of() { in_env "$1" 'source "$1"; claude_session_hook_hint' "$LIB"; }

h="$(hint_of normal)"
assert_contains "C: runtime OK -> hint offers the shortcut" "ait setup --hooks-only" "$h"
assert_contains "C: hint says it only helps agents started afterwards" "started afterwards" "$h"
assert_contains "C: hint says existing no-session records stay view-only" "stay view-only" "$h"
h="$(hint_of nopy)"
assert_contains "C: Python hidden -> hint names the full ait setup" "the full 'ait setup'" "$h"
assert_not_contains "C: Python hidden -> hint does NOT offer --hooks-only" "--hooks-only" "$h"
h="$(hint_of venv_old)"
assert_contains "C: old venv -> full ait setup" "the full 'ait setup'" "$h"
h="$(hint_of override_old)"
assert_contains "C: old override -> names AIT_PYTHON" "AIT_PYTHON=$OLD_PY" "$h"
assert_contains "C: old override -> says to unset or repoint it" "unset AIT_PYTHON" "$h"
assert_not_contains "C: old override -> never says 'full ait setup'" "full 'ait setup'" "$h"
assert_contains "C: invalid hint names the file and the repair" "not valid JSON" \
    "$(in_env normal 'source "$1"; claude_session_hook_invalid_hint' "$LIB")"

echo ""
echo "--- Group D: merge_claude_hooks reports failure ---"
merge_rc() {  # merge_rc <mode> <dir>
    in_env "$1" '
        source "$1" --source-only >/dev/null 2>&1
        SCRIPT_DIR="$2/.aitask-scripts"
        rc=0
        merge_claude_hooks "$2/aitasks/metadata/claude_settings.hooks.json" "$2/.claude/settings.json" >/dev/null 2>&1 || rc=$?
        echo "$rc"' "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$2"
}
P="$(make_proj d_bad)"; mkdir -p "$P/.claude"; printf 'not json\n' >"$P/.claude/settings.json"
before="$(cksum <"$P/.claude/settings.json")"
assert_eq "D: invalid JSON -> non-zero" "1" "$(merge_rc normal "$P")"
assert_eq "D: ...and the file is unchanged" "$before" "$(cksum <"$P/.claude/settings.json")"
P="$(make_proj d_nopy)"; mkdir -p "$P/.claude"; printf '{"env": {}}\n' >"$P/.claude/settings.json"
assert_eq "D: no Python -> non-zero" "1" "$(merge_rc nopy "$P")"
# A write that fails part-way (here: RLIMIT_FSIZE, with SIGXFSZ ignored so the
# write returns EFBIG instead of killing the shell) must leave the original file
# intact -- a plain `> file` would already have truncated it.
P="$(make_proj d_fsize)"; mkdir -p "$P/.claude"
"$REAL_PY" -c 'import json; print(json.dumps({"env": {"K%d" % i: "v" * 40 for i in range(200)}}, indent=2))' \
    >"$P/.claude/settings.json"
before="$(cksum <"$P/.claude/settings.json")"
rc="$(in_env normal '
    source "$1" --source-only >/dev/null 2>&1
    SCRIPT_DIR="$2/.aitask-scripts"
    trap "" XFSZ; ulimit -f 4
    rc=0
    merge_claude_hooks "$2/aitasks/metadata/claude_settings.hooks.json" "$2/.claude/settings.json" >/dev/null 2>&1 || rc=$?
    echo "$rc"' "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$P")"
assert_eq "D: write hits the file-size limit -> non-zero" "1" "$rc"
assert_eq "D: ...and the original file is intact (not truncated)" "$before" \
    "$(cksum <"$P/.claude/settings.json")"
assert_eq "D: ...and no staging temp is left behind" "" \
    "$(find "$P/.claude" -name '.settings.json.*' 2>/dev/null)"

P="$(make_proj d_ok)"; mkdir -p "$P/.claude"; printf '{"env": {}}\n' >"$P/.claude/settings.json"
assert_eq "D: valid settings -> 0" "0" "$(merge_rc normal "$P")"
assert_eq "D: ...and afterwards the status is INSTALLED" "INSTALLED" "$(status_of normal "$P")"

echo ""
echo "--- Group E: install.sh upgrade-path report ---"
report() {  # report <mode> <dir> <existing:true|false>
    in_env "$1" '
        source "$1" --source-only >/dev/null 2>&1
        INSTALL_DIR="$2"; EXISTING_INSTALL="$3"
        report_claude_session_hook 2>&1' "$PROJECT_DIR/install.sh" "$2" "$3"
}
P="$(make_proj e_missing)"
out="$(report normal "$P" true)"
assert_contains "E: upgrade + missing hook -> hint" "session hook is not installed" "$out"
assert_contains "E: ...offering the shortcut" "ait setup --hooks-only" "$out"
assert_eq "E: fresh install -> silent" "" "$(report normal "$P" false)"
out="$(report nopy "$P" true)"
assert_contains "E: upgrade, no settings.json, Python hidden -> still warns" \
    "session hook is not installed" "$out"
assert_contains "E: ...and points to the full ait setup" "the full 'ait setup'" "$out"
P="$(make_proj e_installed)"; mkdir -p "$P/.claude"; cp "$SEED" "$P/.claude/settings.json"
assert_eq "E: upgrade + installed hook -> silent" "" "$(report normal "$P" true)"
P="$(make_proj e_invalid)"; mkdir -p "$P/.claude"; printf '{\n' >"$P/.claude/settings.json"
assert_contains "E: upgrade + invalid settings -> invalid hint" "not valid JSON" \
    "$(report normal "$P" true)"

echo ""
echo "--- Group F: ait ide frozen-agent offer ---"
STUB="$TESTROOT/frozen_stub.sh"
cat >"$STUB" <<'EOF'
#!/usr/bin/env bash
[[ "$1" == gone ]] && cat "$GONE_FILE"
exit 0
EOF
chmod +x "$STUB"
GONE_ONE="$TESTROOT/gone_one"
echo "GONE:cccccccc|gone|agent-c||2026-09-21T22:42:00Z|no_session|no_task_id" >"$GONE_ONE"
GONE_NONE="$TESTROOT/gone_none"; : >"$GONE_NONE"
offer() {  # offer <dir> <gone_file> <tty:0|1>
    printf 's\n' | env -u AIT_PYTHON HOME="$EMPTY_HOME" PATH="$CLEAN_PATH" GONE_FILE="$2" AITASKS_TEST_MODE=1 \
        AIT_IDE_FROZEN_ASSUME_TTY="$3" bash -c \
        'source "$1"; ide_offer_frozen_agents "$2" S "$3"' _ \
        "$PROJECT_DIR/.aitask-scripts/lib/ide_frozen_offer.sh" "$1" "$STUB" 2>&1
}
P="$(make_proj f_missing)"
out="$(offer "$P" "$GONE_ONE" 0)"
assert_contains "F: non-interactive, gone record + missing hook -> note" \
    "Separately, about future Claude Code sessions" "$out"
out="$(offer "$P" "$GONE_ONE" 1)"
assert_contains "F: interactive, gone record + missing hook -> note" \
    "Separately, about future Claude Code sessions" "$out"
assert_contains "F: ...and the menu still follows" "[V] Recreate viewers" "$out"
assert_eq "F: no gone records -> nothing printed" "" "$(offer "$P" "$GONE_NONE" 0)"
P="$(make_proj f_installed)"; mkdir -p "$P/.claude"; cp "$SEED" "$P/.claude/settings.json"
assert_not_contains "F: hook installed -> no note" "Separately" "$(offer "$P" "$GONE_ONE" 0)"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
