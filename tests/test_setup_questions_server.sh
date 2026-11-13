#!/usr/bin/env bash
# test_setup_questions_server.sh - setup/launch wiring of the aitask_questions
# MCP server (t2281).
#
# Pins: the Codex seed registers the server with a repo-relative command and a
# client tool timeout above the launcher's form deadline; merge_codex_settings
# adds the table once and never overrides a user's own values; the dependency
# tier follows the registration and is NOT reachable from setup_codex_cli
# (tests drive that function directly, and it must never run pip against a real
# venv); the launcher keeps stdout clean, fails closed without the SDK, and
# passes the project, an out-of-project state directory and the deadline.
#
# Run: bash tests/test_setup_questions_server.sh

set -uo pipefail

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

SEED="$PROJECT_DIR/seed/codex_config.seed.toml"
LAUNCHER="$PROJECT_DIR/.aitask-scripts/aitask_questions_mcp.sh"
TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

toml_get() {
    python3 - "$1" "$2" <<'PY'
import sys, tomllib
try:
    d = tomllib.load(open(sys.argv[1], "rb"))
    for part in sys.argv[2].split("."):
        d = d[part]
    print(repr(d))
except KeyError:
    print("ABSENT")
except Exception as e:
    print("INVALID: %s" % e)
PY
}

# shellcheck source=../.aitask-scripts/aitask_setup.sh
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +e

echo "=== aitask_questions MCP server: setup and launch wiring (t2281) ==="

echo ""
echo "--- Group 1: the seed registration ---"
assert_eq "1 command is repo-relative launcher" "'.aitask-scripts/aitask_questions_mcp.sh'" \
    "$(toml_get "$SEED" mcp_servers.aitask_questions.command)"
seed_tool_timeout="$(toml_get "$SEED" mcp_servers.aitask_questions.tool_timeout_sec)"
launcher_default="$(sed -n 's/^timeout="\${AIT_QUESTIONS_TIMEOUT:-\([0-9]*\)}"$/\1/p' "$LAUNCHER")"
assert_contains_re "1 launcher declares a numeric default deadline" '^[0-9]+$' "$launcher_default"
if [[ "$seed_tool_timeout" =~ ^[0-9]+$ && "$launcher_default" =~ ^[0-9]+$ ]] \
    && (( seed_tool_timeout > launcher_default )); then
    assert_eq "1 client tool timeout exceeds the form deadline" ok ok
else
    assert_eq "1 client tool timeout exceeds the form deadline" \
        "tool_timeout_sec > $launcher_default" "$seed_tool_timeout"
fi
assert_file_exists "1 launcher exists" "$LAUNCHER"
if [[ -x "$LAUNCHER" ]]; then assert_eq "1 launcher is executable" ok ok
else assert_eq "1 launcher is executable" ok no; fi

echo ""
echo "--- Group 2: merge into an existing config ---"
merge_into() {
    local dir="$TESTROOT/$1"
    mkdir -p "$dir/.codex"
    printf '%s' "$2" >"$dir/.codex/config.toml"
    merge_codex_settings "$SEED" "$dir/.codex/config.toml" >/dev/null 2>"$dir/merge.err"
    echo "$dir/.codex/config.toml"
}
f="$(merge_into plain $'model = "gpt-x"\n\n[mcp_servers.other]\ncommand = "other-server"\n')"
assert_eq "2a table added" "'.aitask-scripts/aitask_questions_mcp.sh'" "$(toml_get "$f" mcp_servers.aitask_questions.command)"
assert_eq "2a tool timeout added" "$seed_tool_timeout" "$(toml_get "$f" mcp_servers.aitask_questions.tool_timeout_sec)"
assert_eq "2a user's own server kept" "'other-server'" "$(toml_get "$f" mcp_servers.other.command)"
assert_eq "2a user's scalar kept" "'gpt-x'" "$(toml_get "$f" model)"
merge_codex_settings "$SEED" "$f" >/dev/null 2>&1
assert_eq "2b re-merge keeps exactly one table header" "1" "$(grep -c '^\[mcp_servers\.aitask_questions\]$' "$f")"
assert_eq "2b re-merge still valid" "'.aitask-scripts/aitask_questions_mcp.sh'" "$(toml_get "$f" mcp_servers.aitask_questions.command)"
f="$(merge_into custom $'[mcp_servers.aitask_questions]\ncommand = "/opt/custom/launcher"\ntool_timeout_sec = 900\n')"
assert_eq "2c user's command wins" "'/opt/custom/launcher'" "$(toml_get "$f" mcp_servers.aitask_questions.command)"
assert_eq "2c user's tool timeout wins" "900" "$(toml_get "$f" mcp_servers.aitask_questions.tool_timeout_sec)"

echo ""
echo "--- Group 3: the dependency tier follows the registration ---"
reg="$TESTROOT/reg/.aitask-scripts"
mkdir -p "$reg" "$TESTROOT/reg/.codex"
saved_script_dir="$SCRIPT_DIR"
SCRIPT_DIR="$reg"
questions_server_registered; assert_eq "3a no config: not registered" "1" "$?"
printf '[tui]\nwhimsy = false\n' >"$TESTROOT/reg/.codex/config.toml"
questions_server_registered; assert_eq "3b config without the table: not registered" "1" "$?"
printf '# [mcp_servers.aitask_questions]\n' >"$TESTROOT/reg/.codex/config.toml"
questions_server_registered; assert_eq "3c commented-out table: not registered" "1" "$?"
cp "$SEED" "$TESTROOT/reg/.codex/config.toml"
questions_server_registered; assert_eq "3d seeded config: registered" "0" "$?"
SCRIPT_DIR="$saved_script_dir"

body="$(declare -f setup_codex_cli)"
assert_not_contains "3e setup_codex_cli never installs packages" "setup_questions_deps" "$body"
assert_not_contains "3e setup_codex_cli never calls pip" "pip" "$body"

pip_calls="$TESTROOT/pip.calls"
: >"$pip_calls"
saved_venv="$VENV_DIR"
VENV_DIR="$TESTROOT/no-venv"
out="$(setup_questions_deps 2>&1)"; rc=$?
assert_eq "3f missing venv: returns 0" "0" "$rc"
assert_contains "3f missing venv: says how to retry" "Re-run 'ait setup'" "$out"
mkdir -p "$TESTROOT/venv/bin"
printf '#!/usr/bin/env bash\necho "$@" >>"%s"\nexit 1\n' "$pip_calls" >"$TESTROOT/venv/bin/pip"
printf '#!/usr/bin/env bash\nexit 1\n' >"$TESTROOT/venv/bin/python"
chmod +x "$TESTROOT/venv/bin/pip" "$TESTROOT/venv/bin/python"
VENV_DIR="$TESTROOT/venv"
out="$(setup_questions_deps 2>&1)"; rc=$?
assert_eq "3g failing pip: setup still returns 0" "0" "$rc"
assert_contains "3g failing pip: warns the server will be unavailable" "unavailable" "$out"
assert_contains "3g pip was asked for the pinned range" "mcp>=2.3,<2.4" "$(cat "$pip_calls")"
VENV_DIR="$saved_venv"

echo ""
echo "--- Group 4: the launcher ---"
fake="$TESTROOT/fakepy"
mkdir -p "$fake"
# A python that has no mcp: every `-c 'import ...'` probe fails.
printf '#!/usr/bin/env bash\nexit 1\n' >"$fake/python3"
chmod +x "$fake/python3"
out="$(HOME="$TESTROOT/home" AIT_PYTHON="" PATH="$fake:/usr/bin:/bin" "$LAUNCHER" 2>"$TESTROOT/launch.err")"; rc=$?
assert_eq "4a no SDK: exits non-zero" "3" "$rc"
assert_eq "4a no SDK: stdout stays empty" "" "$out"
assert_contains "4a no SDK: stderr names the fix" "ait setup" "$(cat "$TESTROOT/launch.err")"
assert_dir_not_exists "4a no SDK: no state directory created" "$TESTROOT/home/.local/state/aitasks"

# A python that passes the probe and records the server argv.
cat >"$fake/okpy" <<PY
#!/usr/bin/env bash
if [[ "\$1" == "-c" ]]; then exit 0; fi
printf '%s\n' "\$@" >"$TESTROOT/argv"
PY
chmod +x "$fake/okpy"
out="$(HOME="$TESTROOT/home" XDG_STATE_HOME="" AIT_PYTHON="$fake/okpy" "$LAUNCHER" 2>&1)"; rc=$?
assert_eq "4b launch: exit status is the server's" "0" "$rc"
assert_eq "4b launch: launcher itself prints nothing" "" "$out"
argv="$(cat "$TESTROOT/argv" 2>/dev/null)"
assert_contains "4b entry point" "$PROJECT_DIR/.aitask-scripts/aitask_questions_server.py" "$argv"
assert_contains "4b project is this checkout" "$(cd "$PROJECT_DIR" && pwd -P)" "$argv"
assert_contains "4b state lives outside the project" "$TESTROOT/home/.local/state/aitasks/questions" "$argv"
assert_contains "4b default deadline passed" "$launcher_default" "$argv"
assert_contains "4b live-validated multi-select route is the default" "text" "$argv"
HOME="$TESTROOT/home" AIT_PYTHON="$fake/okpy" AIT_QUESTIONS_STATE_DIR="$TESTROOT/dir with space" \
    AIT_QUESTIONS_TIMEOUT=45 AIT_QUESTIONS_MULTISELECT=native "$LAUNCHER" >/dev/null 2>&1
argv="$(cat "$TESTROOT/argv")"
assert_contains "4c state override with a space survives as one argument" "$TESTROOT/dir with space" "$argv"
assert_eq "4c overrides passed" "45 native" "$(sed -n '/^--timeout$/{n;p}; /^--multiselect-mode$/{n;p}' "$TESTROOT/argv" | tr '\n' ' ' | sed 's/ $//')"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
