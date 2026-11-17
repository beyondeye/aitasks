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

# =============================================================================
# t2297: the question server is an explicit, explained, remembered opt-in.
# =============================================================================

# toml_equal_minus_questions <original> <candidate> -> "equal" | "differ: ..."
toml_equal_minus_questions() {
    python3 - "$1" "$2" <<'PY'
import sys, tomllib
o = tomllib.load(open(sys.argv[1], "rb"))
c = tomllib.load(open(sys.argv[2], "rb"))
s = o.get("mcp_servers")
if isinstance(s, dict):
    s.pop("aitask_questions", None)
    if not s:
        del o["mcp_servers"]
print("equal" if o == c else "differ: %r vs %r" % (o, c))
PY
}

REGISTERED_CFG=$'model = "gpt-x"\n\n[mcp_servers.other]\ncommand = "other-server"\n\n[mcp_servers.aitask_questions]\ncommand = ".aitask-scripts/aitask_questions_mcp.sh"\ntool_timeout_sec = 360\n'

echo ""
echo "--- Group 5: merge modes ---"
# merge_into above already merges the full seed, so these fixtures are plain writes.
cfg_file() {   # cfg_file <name> <content> -> path
    local dir="$TESTROOT/g5_$1"
    mkdir -p "$dir/.codex"
    printf '%s' "$2" > "$dir/.codex/config.toml"
    echo "$dir/.codex/config.toml"
}
f="$(cfg_file omit_plain $'model = "gpt-x"\n')"
merge_codex_settings "$SEED" "$f" omit >/dev/null 2>&1; rc=$?
assert_eq "5a omit: succeeds" "0" "$rc"
assert_eq "5a omit: no table added" "ABSENT" "$(toml_get "$f" mcp_servers.aitask_questions)"
assert_eq "5a omit: the seed's other keys merged" "'.aitask-scripts/aitask_session_hook.sh'" \
    "$(toml_get "$f" hooks.SessionStart | python3 -c 'import sys,ast; print(repr(ast.literal_eval(sys.stdin.read())[0]["hooks"][0]["command"]))')"
f="$(cfg_file remove_other "$REGISTERED_CFG")"
merge_codex_settings "$SEED" "$f" remove >/dev/null 2>"$TESTROOT/remove.err"; rc=$?
assert_eq "5b remove: succeeds" "0" "$rc"
assert_eq "5b remove: table gone" "ABSENT" "$(toml_get "$f" mcp_servers.aitask_questions)"
assert_eq "5b remove: user's other server kept" "'other-server'" "$(toml_get "$f" mcp_servers.other.command)"
assert_eq "5b remove: user's scalar kept" "'gpt-x'" "$(toml_get "$f" model)"
assert_contains "5b remove: says so" "Removed [mcp_servers.aitask_questions]" "$(cat "$TESTROOT/remove.err")"
f="$(cfg_file remove_last $'[mcp_servers.aitask_questions]\ncommand = "x"\n')"
merge_codex_settings /dev/null "$f" remove >/dev/null 2>&1; rc=$?
assert_eq "5c remove of the last server: succeeds" "0" "$rc"
assert_eq "5c remove of the last server: no mcp_servers left" "ABSENT" "$(toml_get "$f" mcp_servers)"
f="$(cfg_file omit_registered "$REGISTERED_CFG")"
merge_codex_settings "$SEED" "$f" omit >/dev/null 2>&1
assert_eq "5d omit keeps an existing registration" "'.aitask-scripts/aitask_questions_mcp.sh'" \
    "$(toml_get "$f" mcp_servers.aitask_questions.command)"
f="$(cfg_file removeonly "$REGISTERED_CFG")"
cp "$f" "$TESTROOT/removeonly.orig"
merge_codex_settings /dev/null "$f" remove >/dev/null 2>&1
assert_eq "5e /dev/null + remove changes nothing but the table" "equal" \
    "$(toml_equal_minus_questions "$TESTROOT/removeonly.orig" "$f")"
merge_codex_settings "$SEED" "$f" bogus >/dev/null 2>&1; rc=$?
assert_eq "5f unknown mode is refused" "1" "$rc"

# --- setup_codex_cli fixtures ------------------------------------------------
make_cfx() {   # make_cfx <name> [config-content] -> dir
    local dir="$TESTROOT/cfx_$1"
    rm -rf "$dir"
    mkdir -p "$dir/.aitask-scripts" "$dir/seed" "$dir/aitasks/metadata/codex_skills/aitask-pick"
    cp "$SEED" "$dir/aitasks/metadata/codex_config.seed.toml"
    cp "$PROJECT_DIR/seed/codex_rules.default.rules" "$dir/aitasks/metadata/"
    cp "$PROJECT_DIR/seed/codex_instructions.seed.md" "$PROJECT_DIR/seed/aitasks_agent_instructions.seed.md" "$dir/seed/"
    echo "# Pick skill" > "$dir/aitasks/metadata/codex_skills/aitask-pick/SKILL.md"
    printf 'codeagent_coauthor_domain: aitasks.io\n' > "$dir/aitasks/metadata/project_config.yaml"
    if [[ -n "${2:-}" ]]; then
        mkdir -p "$dir/.codex"
        printf '%s' "$2" > "$dir/.codex/config.toml"
    fi
    echo "$dir"
}

# run_cfx <dir> <flag:1|0|""> <tty:1|0> <stdin> [fn] — runs <fn> (default
# setup_codex_cli) in a subshell and prints its output plus the run state:
#   STATE:<action>|<optout_failed>|<decision_written>   DEPS:yes|no
# Extra shell code to run before <fn> (stubs) comes from $CFX_PRE.
run_cfx() {
    local dir="$1" flag="$2" tty="$3" input="$4" fn="${5:-setup_codex_cli}"
    printf '%s' "$input" > "$TESTROOT/cfx.stdin"
    (
        SCRIPT_DIR="$dir/.aitask-scripts"
        CODEX_QUESTIONS_FLAG="$flag"
        CODEX_QUESTIONS_ACTION=""; CODEX_QUESTIONS_OPTOUT_FAILED=0; CODEX_QUESTIONS_DECISION_WRITTEN=0
        if [[ "$tty" == 1 ]]; then _setup_stdin_is_tty() { return 0; }
        else _setup_stdin_is_tty() { return 1; }; fi
        eval "${CFX_PRE:-}"
        "$fn" < "$TESTROOT/cfx.stdin"
        echo "STATE:${CODEX_QUESTIONS_ACTION}|${CODEX_QUESTIONS_OPTOUT_FAILED}|${CODEX_QUESTIONS_DECISION_WRITTEN}"
        if questions_deps_wanted >/dev/null 2>&1; then echo "DEPS:yes"; else echo "DEPS:no"; fi
    ) 2>&1
}
state_of() { printf '%s\n' "$1" | sed -n 's/^STATE://p'; }
deps_of()  { printf '%s\n' "$1" | sed -n 's/^DEPS://p'; }
decline_line() { grep -c '^codex_questions_server:' "$1/aitasks/metadata/project_config.yaml"; }
decline_value() { sed -n 's/^codex_questions_server:[[:space:]]*//p' "$1/aitasks/metadata/project_config.yaml"; }
reg_of() { if grep -q '^\[mcp_servers\.aitask_questions\]' "$1/.codex/config.toml" 2>/dev/null; then echo yes; else echo no; fi; }

echo ""
echo "--- Group 6: setup_codex_cli end-to-end ---"
d="$(make_cfx g6a)"; out="$(run_cfx "$d" "" 0 "")"
assert_eq "6a non-TTY, no flag: registered" "yes" "$(reg_of "$d")"
assert_eq "6a state" "register|0|0" "$(state_of "$out")"
assert_eq "6a deps wanted" "yes" "$(deps_of "$out")"
assert_contains "6a explanation shown" "Without it, Codex asks these questions in plain text" "$out"
assert_contains "6a non-interactive default named" "non-interactive: registering the question server" "$out"
d="$(make_cfx g6b)"; out="$(run_cfx "$d" 0 0 "")"
assert_eq "6b flag 0, fresh: no table" "no" "$(reg_of "$d")"
assert_eq "6b flag 0, fresh: config is valid TOML with the seed's features" "True" \
    "$(toml_get "$d/.codex/config.toml" features.default_mode_request_user_input)"
assert_eq "6b state" "skip|0|1" "$(state_of "$out")"
assert_eq "6b deps not wanted" "no" "$(deps_of "$out")"
assert_eq "6b decline recorded" "false" "$(decline_value "$d")"
d="$(make_cfx g6c "$REGISTERED_CFG")"; out="$(run_cfx "$d" 0 0 "")"
assert_eq "6c flag 0, registered: removed" "no" "$(reg_of "$d")"
assert_eq "6c user's other server kept" "'other-server'" "$(toml_get "$d/.codex/config.toml" mcp_servers.other.command)"
assert_eq "6c state" "unregister|0|1" "$(state_of "$out")"
assert_contains "6c says it was removed and mcp stays" "mcp stays in the shared venv" "$out"
d="$(make_cfx g6d "$REGISTERED_CFG")"; out="$(run_cfx "$d" "" 0 "")"
assert_eq "6d no flag, registered: kept" "yes" "$(reg_of "$d")"
assert_contains "6d hint names the removal flag" "ait setup --no-codex-questions" "$out"
assert_not_contains "6d no prompt for a remembered yes" "Register the aitask_questions question server?" "$out"
assert_eq "6d deps wanted (revalidate/repair)" "yes" "$(deps_of "$out")"
d="$(make_cfx g6e)"; printf 'codex_questions_server: false\n' >> "$d/aitasks/metadata/project_config.yaml"
out="$(run_cfx "$d" 1 0 "")"
assert_eq "6e flag 1: registered over a recorded decline" "yes" "$(reg_of "$d")"
assert_eq "6e flag 1: decline cleared in place" "true" "$(decline_value "$d")"
assert_eq "6e flag 1: one key line" "1" "$(decline_line "$d")"
d="$(make_cfx g6f)"; out="$(run_cfx "$d" "" 1 $'\nn\n')"
assert_contains "6f TTY: the prompt is shown" "Register the aitask_questions question server? [Y/n]" "$out"
assert_contains "6f TTY: explanation mentions restart" "Restart Codex afterwards" "$out"
assert_eq "6f TTY n: skipped" "no" "$(reg_of "$d")"
assert_eq "6f TTY n: decline recorded" "false" "$(decline_value "$d")"
assert_contains "6f TTY n: names the opt-in flag" "ait setup --with-codex-questions" "$out"
d="$(make_cfx g6g)"; out="$(run_cfx "$d" "" 1 $'\n\n')"
assert_eq "6g TTY empty line: registered (default Y)" "yes" "$(reg_of "$d")"
assert_eq "6g TTY empty line: no decline written" "0" "$(decline_line "$d")"
d="$(make_cfx g6h "$REGISTERED_CFG")"
python3 - "$d/aitasks/metadata/codex_config.seed.toml" <<'PY'
import re, sys
p = sys.argv[1]
t = open(p).read()
t = re.sub(r"\n\[mcp_servers\.aitask_questions\][^\[]*", "\n", t)
open(p, "w").write(t)
PY
rm -f "$d/.codex/config.toml"; out="$(run_cfx "$d" "" 0 "")"
assert_eq "6h table-less custom seed: config still created" "True" \
    "$(toml_get "$d/.codex/config.toml" features.default_mode_request_user_input)"
assert_eq "6h table-less custom seed: nothing registered" "no" "$(reg_of "$d")"
assert_contains "6h table-less custom seed: says why" "carries no [mcp_servers.aitask_questions] table" "$out"

echo ""
echo "--- Group 7: failure paths never leave a registration that installs mcp ---"
BADV="$TESTROOT/badvenv"; mkdir -p "$BADV/bin" "$TESTROOT/badpath"
printf '#!/usr/bin/env bash\nexit 1\n' > "$BADV/bin/python"
printf '#!/usr/bin/env bash\nexit 1\n' > "$TESTROOT/badpath/python3"
chmod +x "$BADV/bin/python" "$TESTROOT/badpath/python3"
CFX_PRE='VENV_DIR="$TESTROOT/badvenv"; PATH="$TESTROOT/badpath:$PATH"'
d="$(make_cfx g7a)"; out="$(run_cfx "$d" 0 0 "")"
assert_file_not_exists "7a fresh decline, merge fails: no config published" "$d/.codex/config.toml"
assert_eq "7a state: opt-out failed" "skip|1|1" "$(state_of "$out")"
assert_eq "7a deps not wanted" "no" "$(deps_of "$out")"
assert_contains "7a says the opt-out failed" "opt-out failed" "$out"
d="$(make_cfx g7b "$REGISTERED_CFG")"; cp "$d/.codex/config.toml" "$TESTROOT/g7b.orig"
out="$(run_cfx "$d" 0 0 "")"
if cmp -s "$TESTROOT/g7b.orig" "$d/.codex/config.toml"; then assert_eq "7b failed removal: config byte-identical" same same
else assert_eq "7b failed removal: config byte-identical" same changed; fi
assert_eq "7b state: opt-out failed" "unregister|1|1" "$(state_of "$out")"
assert_eq "7b deps not wanted although still registered" "no" "$(deps_of "$out")"
assert_contains "7b distinct failure message" "opt-out failed" "$out"
assert_not_contains "7b no success message" "Removed the aitask_questions question server" "$out"
CFX_PRE='merge_codex_settings() { return 0; }'   # "succeeds" but rewrites nothing
d="$(make_cfx g7c "$REGISTERED_CFG")"; cp "$d/.codex/config.toml" "$TESTROOT/g7c.orig"
out="$(run_cfx "$d" 0 0 "")"
assert_contains "7c validation rejects a still-registered candidate" "Rejected the rewritten .codex/config.toml" "$out"
assert_eq "7c state: the rejected removal counts as a failed opt-out" "unregister|1|1" "$(state_of "$out")"
assert_not_contains "7c no success message" "Removed the aitask_questions question server" "$out"
if cmp -s "$TESTROOT/g7c.orig" "$d/.codex/config.toml"; then assert_eq "7c config untouched" same same
else assert_eq "7c config untouched" same changed; fi
assert_eq "7c deps not wanted" "no" "$(deps_of "$out")"
assert_eq "7c no temp file left behind" "" "$(find "$d/.codex" -name '.config.toml.*')"
CFX_PRE=""

echo ""
echo "--- Group 8: --no-codex-questions works without the Codex setup ---"
CUSTOM_CFG=$'approval_policy = "never"\n\n[mcp_servers.other]\ncommand = "other-server"\nargs = ["--x"]\n\n[mcp_servers.aitask_questions]\ncommand = "x"\n\n[profiles.fast]\nmodel = "m"\n'
CFX_PRE='_is_agent_installed() { return 1; }'
d="$(make_cfx g8a "$CUSTOM_CFG")"; cp "$d/.codex/config.toml" "$TESTROOT/g8a.orig"
out="$(run_cfx "$d" 0 0 "" setup_codex_agent)"
assert_eq "8a Codex not installed + flag 0: table removed" "no" "$(reg_of "$d")"
assert_eq "8a everything else parsed-equal" "equal" "$(toml_equal_minus_questions "$TESTROOT/g8a.orig" "$d/.codex/config.toml")"
assert_eq "8a decline recorded" "false" "$(decline_value "$d")"
assert_eq "8a deps not wanted" "no" "$(deps_of "$out")"
assert_file_not_exists "8a no Codex skills installed" "$d/.agents/skills/aitask-pick/SKILL.md"
d="$(make_cfx g8b "$CUSTOM_CFG")"; cp "$d/.codex/config.toml" "$TESTROOT/g8b.orig"
out="$(run_cfx "$d" 1 0 "" setup_codex_agent)"
if cmp -s "$TESTROOT/g8b.orig" "$d/.codex/config.toml"; then assert_eq "8b Codex not installed + flag 1: no change" same same
else assert_eq "8b Codex not installed + flag 1: no change" same changed; fi
assert_contains "8b says the flag had no effect" "--with-codex-questions had no effect" "$out"
CFX_PRE=""
d="$(make_cfx g8c "$CUSTOM_CFG")"; cp "$d/.codex/config.toml" "$TESTROOT/g8c.orig"
out="$(run_cfx "$d" 0 1 $'n\n')"
assert_contains "8c skills prompt declined" "Skipped Codex CLI skill installation" "$out"
assert_eq "8c declined skills + flag 0: table removed" "no" "$(reg_of "$d")"
assert_eq "8c everything else parsed-equal" "equal" "$(toml_equal_minus_questions "$TESTROOT/g8c.orig" "$d/.codex/config.toml")"
assert_file_not_exists "8c no Codex skills installed" "$d/.agents/skills/aitask-pick/SKILL.md"
d="$(make_cfx g8d "$CUSTOM_CFG")"; cp "$d/.codex/config.toml" "$TESTROOT/g8d.orig"
out="$(run_cfx "$d" 1 1 $'n\n')"
if cmp -s "$TESTROOT/g8d.orig" "$d/.codex/config.toml"; then assert_eq "8d declined skills + flag 1: no change" same same
else assert_eq "8d declined skills + flag 1: no change" same changed; fi
assert_contains "8d says the flag had no effect" "--with-codex-questions had no effect" "$out"
CFX_PRE='VENV_DIR="$TESTROOT/badvenv"; PATH="$TESTROOT/badpath:$PATH"; _is_agent_installed() { return 1; }'
d="$(make_cfx g8e "$CUSTOM_CFG")"; cp "$d/.codex/config.toml" "$TESTROOT/g8e.orig"
out="$(run_cfx "$d" 0 0 "" setup_codex_agent)"
if cmp -s "$TESTROOT/g8e.orig" "$d/.codex/config.toml"; then assert_eq "8e standalone removal failure: config untouched" same same
else assert_eq "8e standalone removal failure: config untouched" same changed; fi
assert_eq "8e standalone removal failure: deps not wanted" "no" "$(deps_of "$out")"
assert_contains "8e standalone removal failure: says so" "Could not remove the aitask_questions server" "$out"
CFX_PRE=""

echo ""
echo "--- Group 9: a recorded decline is honoured ---"
d="$(make_cfx g9)"
run_cfx "$d" "" 1 $'\nn\n' >/dev/null
assert_eq "9a interactive n recorded the decline" "false" "$(decline_value "$d")"
out="$(run_cfx "$d" "" 0 "")"
assert_eq "9b later non-TTY run: still unregistered" "no" "$(reg_of "$d")"
assert_contains "9b names the decline and the flag" "declined for this project" "$out"
assert_not_contains "9b no prompt" "Register the aitask_questions question server?" "$out"
assert_eq "9b deps not wanted" "no" "$(deps_of "$out")"
out="$(run_cfx "$d" "" 1 $'\n')"
assert_not_contains "9c later TTY run: no prompt" "Register the aitask_questions question server?" "$out"
assert_eq "9c later TTY run: still unregistered" "no" "$(reg_of "$d")"
run_cfx "$d" 1 0 "" >/dev/null; run_cfx "$d" 0 0 "" >/dev/null; run_cfx "$d" 1 0 "" >/dev/null
assert_eq "9d repeated writes keep exactly one key line" "1" "$(decline_line "$d")"
assert_eq "9d last write wins" "true" "$(decline_value "$d")"
assert_eq "9d flag 1 registered it" "yes" "$(reg_of "$d")"
d="$(make_cfx g9e "$REGISTERED_CFG")"; printf 'codex_questions_server: false\n' >> "$d/aitasks/metadata/project_config.yaml"
out="$(run_cfx "$d" "" 0 "")"
assert_eq "9e registered + declined: kept" "yes" "$(reg_of "$d")"
assert_contains "9e mismatch warning names both flags" "--no-codex-questions' removes it, 'ait setup --with-codex-questions' clears the decline" "$out"
d="$(make_cfx g9f)"; rm -f "$d/aitasks/metadata/project_config.yaml"
out="$(run_cfx "$d" 0 0 "")"; rc=$?
assert_eq "9f missing project_config: setup continues" "0" "$rc"
assert_contains "9f missing project_config: warns" "the decline is not recorded" "$out"
assert_eq "9f missing project_config: still not registered" "no" "$(reg_of "$d")"
assert_eq "9f missing project_config: nothing to commit" "skip|0|0" "$(state_of "$out")"

echo ""
echo "--- Group 11: removal and merge keep quoted / escaped values ---"
# Literal strings with double quotes, a Windows-style backslash path, a basic
# string with escapes, a quoted (dotted) key, comments — all valid TOML the old
# serializer could not round-trip (it emitted f'"{v}"' unescaped).
QUOTED_HEAD=$'# my project codex config\nmodel = "gpt-x"\n\n[mcp_servers.other]\ncommand = "other"\nargs = [\'say "hello"\', \'C:\\tools\\x\']\nnote = "a \\"q\\" \\\\ b\\tc"\n\n[mcp_servers."my.server"]\ncommand = "m"\n'
QUOTED_TABLE=$'\n[mcp_servers.aitask_questions]\ncommand = ".aitask-scripts/aitask_questions_mcp.sh"\ntool_timeout_sec = 360\n'
QUOTED_TAIL=$'\n# comment that belongs to the next table\n[profiles.fast]\nmodel = "m"\n'
values_of() {   # values_of <config> -> the quoted values, one per line
    python3 - "$1" <<'PY'
import sys, tomllib
d = tomllib.load(open(sys.argv[1], "rb"))
o = d["mcp_servers"]["other"]
print(repr(o["args"])); print(repr(o["note"])); print(repr(d["mcp_servers"]["my.server"]["command"]))
PY
}
mkdir -p "$TESTROOT/g11/.codex"; G11="$TESTROOT/g11/.codex/config.toml"
printf '%s%s%s' "$QUOTED_HEAD" "$QUOTED_TABLE" "$QUOTED_TAIL" > "$G11"
cp "$G11" "$TESTROOT/g11.orig"; values_of "$G11" > "$TESTROOT/g11.values"
apply_codex_config /dev/null "$G11" remove >/dev/null 2>&1; rc=$?
assert_eq "11a standalone removal with quoted values: succeeds" "0" "$rc"
assert_eq "11a table gone" "no" "$(grep -q '^\[mcp_servers\.aitask_questions\]' "$G11" && echo yes || echo no)"
assert_eq "11a every other byte kept (text cut)" "$(printf '%s%s' "$QUOTED_HEAD" "$QUOTED_TAIL")" "$(cat "$G11")"
assert_eq "11a parsed equal minus the table" "equal" "$(toml_equal_minus_questions "$TESTROOT/g11.orig" "$G11")"
d="$(make_cfx g11b "$(printf '%s%s%s' "$QUOTED_HEAD" "$QUOTED_TABLE" "$QUOTED_TAIL")")"
out="$(run_cfx "$d" 0 0 "")"
assert_eq "11b unregister via the seed merge: removed" "no" "$(reg_of "$d")"
assert_eq "11b quoted values survive the re-serializing merge" "$(cat "$TESTROOT/g11.values")" "$(values_of "$d/.codex/config.toml")"
assert_eq "11b not reported as a failed opt-out" "unregister|0|1" "$(state_of "$out")"
f="$(cfg_file keep_quoted "$(printf '%s%s' "$QUOTED_HEAD" "$QUOTED_TAIL")")"
merge_codex_settings "$SEED" "$f" >/dev/null 2>&1; merge_codex_settings "$SEED" "$f" >/dev/null 2>&1; rc=$?
assert_eq "11c keep-merge twice: succeeds" "0" "$rc"
assert_eq "11c keep-merge twice: quoted values unchanged" "$(cat "$TESTROOT/g11.values")" "$(values_of "$f")"
f="$(cfg_file dotted $'model = "gpt-x"\nmcp_servers.aitask_questions.command = "x"\nmcp_servers.other.command = "o"\n')"
cp "$f" "$TESTROOT/dotted.orig"
apply_codex_config /dev/null "$f" remove >/dev/null 2>&1; rc=$?
assert_eq "11d dotted-key registration (no header to cut): falls back and succeeds" "0" "$rc"
assert_eq "11d dotted-key registration: parsed equal minus the table" "equal" "$(toml_equal_minus_questions "$TESTROOT/dotted.orig" "$f")"
d="$(make_cfx g11e)"; run_cfx "$d" "" 0 "" >/dev/null
assert_contains "11e fresh seed copy carries the seed's comment block" "# aitask_questions — local STDIO MCP server" "$(cat "$d/.codex/config.toml")"
apply_codex_config /dev/null "$d/.codex/config.toml" remove >/dev/null 2>&1
assert_eq "11e removal also drops the seed's own comment block" "0" "$(grep -c 'aitask_questions' "$d/.codex/config.toml")"
assert_contains "11e the other seed comments stay" "SessionStart hook" "$(cat "$d/.codex/config.toml")"

echo ""
echo "--- Group 12: writers follow symlinks and publish atomically ---"
mkdir -p "$TESTROOT/g12real" "$TESTROOT/g12/.codex"
printf '%s' "$REGISTERED_CFG" > "$TESTROOT/g12real/config.toml"
ln -s "$TESTROOT/g12real/config.toml" "$TESTROOT/g12/.codex/config.toml"
apply_codex_config /dev/null "$TESTROOT/g12/.codex/config.toml" remove >/dev/null 2>&1; rc=$?
assert_eq "12a removal through a symlinked config: succeeds" "0" "$rc"
assert_eq "12a the link is still a link" "yes" "$([[ -L "$TESTROOT/g12/.codex/config.toml" ]] && echo yes || echo no)"
assert_eq "12a the backing file lost the table" "no" "$(grep -q '^\[mcp_servers\.aitask_questions\]' "$TESTROOT/g12real/config.toml" && echo yes || echo no)"
assert_eq "12a the backing file kept the rest" "'other-server'" "$(toml_get "$TESTROOT/g12real/config.toml" mcp_servers.other.command)"
d="$(make_cfx g12b)"; mkdir -p "$d/.codex" "$TESTROOT/g12breal"
printf 'model = "gpt-x"\n' > "$TESTROOT/g12breal/config.toml"; chmod 640 "$TESTROOT/g12breal/config.toml"
ln -s "$TESTROOT/g12breal/config.toml" "$d/.codex/config.toml"
run_cfx "$d" "" 0 "" >/dev/null
assert_eq "12b setup merge through a symlink: still a link" "yes" "$([[ -L "$d/.codex/config.toml" ]] && echo yes || echo no)"
assert_eq "12b setup merge through a symlink: backing file registered" "yes" \
    "$(grep -q '^\[mcp_servers\.aitask_questions\]' "$TESTROOT/g12breal/config.toml" && echo yes || echo no)"
assert_eq "12b file mode kept" "640" "$(stat -c '%a' "$TESTROOT/g12breal/config.toml")"
d="$(make_cfx g12c)"; mkdir -p "$TESTROOT/g12creal"
mv "$d/aitasks/metadata/project_config.yaml" "$TESTROOT/g12creal/project_config.yaml"
chmod 640 "$TESTROOT/g12creal/project_config.yaml"
ln -s "$TESTROOT/g12creal/project_config.yaml" "$d/aitasks/metadata/project_config.yaml"
ino_before="$(stat -c '%i' "$TESTROOT/g12creal/project_config.yaml")"
run_cfx "$d" 0 0 "" >/dev/null
assert_eq "12c decision write through a symlink: still a link" "yes" "$([[ -L "$d/aitasks/metadata/project_config.yaml" ]] && echo yes || echo no)"
assert_eq "12c backing project_config got the decline" "false" "$(sed -n 's/^codex_questions_server:[[:space:]]*//p' "$TESTROOT/g12creal/project_config.yaml")"
assert_eq "12c mode kept" "640" "$(stat -c '%a' "$TESTROOT/g12creal/project_config.yaml")"
if [[ "$(stat -c '%i' "$TESTROOT/g12creal/project_config.yaml")" != "$ino_before" ]]; then
    assert_eq "12c published by rename, never truncated in place" ok ok
else
    assert_eq "12c published by rename, never truncated in place" "new inode" "same inode"
fi
run_cfx "$d" 1 0 "" >/dev/null
assert_eq "12d rewrite of the key line: still a link and one line" "yes|1" \
    "$([[ -L "$d/aitasks/metadata/project_config.yaml" ]] && echo yes || echo no)|$(grep -c '^codex_questions_server:' "$TESTROOT/g12creal/project_config.yaml")"
cp "$TESTROOT/g12creal/project_config.yaml" "$TESTROOT/g12c.orig"
CFX_PRE='_render_codex_questions_decision() { echo "partial"; return 1; }'
out="$(run_cfx "$d" 0 0 "")"
CFX_PRE=""
if cmp -s "$TESTROOT/g12c.orig" "$TESTROOT/g12creal/project_config.yaml"; then
    assert_eq "12e a failed render leaves project_config intact" same same
else
    assert_eq "12e a failed render leaves project_config intact" same changed
fi
assert_contains "12e a failed render warns" "Could not record codex_questions_server" "$out"
assert_eq "12e a failed render commits nothing" "0" "$(state_of "$out" | cut -d'|' -f3)"
assert_eq "12f no stray temp files" "" "$(find "$TESTROOT/g12creal" "$TESTROOT/g12real" "$TESTROOT/g12breal" -name '.*.??????' 2>/dev/null)"

echo ""
echo "--- Group 13: every valid spelling of the registration counts, through the setup paths ---"
QUOTED_REG=$'model = "gpt-x"\n\n[mcp_servers.other]\ncommand = "other-server"\n\n[mcp_servers."aitask_questions"]\ncommand = "questions"\n'
DOTTED_REG=$'model = "gpt-x"\nmcp_servers.aitask_questions.command = "questions"\n\n[mcp_servers.other]\ncommand = "other-server"\n'
parsed_reg() {   # parsed_reg <config> -> yes|no (semantic, not grep)
    python3 - "$1" <<'PY'
import sys, tomllib
d = tomllib.load(open(sys.argv[1], "rb"))
print("yes" if "aitask_questions" in d.get("mcp_servers", {}) else "no")
PY
}
for form in quoted dotted; do
    if [[ "$form" == quoted ]]; then cfg="$QUOTED_REG"; else cfg="$DOTTED_REG"; fi
    f="$(cfg_file "reg_$form" "$cfg")"
    questions_server_registered "$f"; assert_eq "13 $form spelling: detected as registered" "0" "$?"

    CFX_PRE='_is_agent_installed() { return 1; }'
    d="$(make_cfx "g13a_$form" "$cfg")"; cp "$d/.codex/config.toml" "$TESTROOT/g13a_$form.orig"
    out="$(run_cfx "$d" 0 0 "" setup_codex_agent)"
    CFX_PRE=""
    assert_eq "13a $form, Codex not installed + --no: removed" "no" "$(parsed_reg "$d/.codex/config.toml")"
    assert_eq "13a $form: everything else parsed-equal" "equal" \
        "$(toml_equal_minus_questions "$TESTROOT/g13a_$form.orig" "$d/.codex/config.toml")"
    assert_eq "13a $form: not a failed opt-out" "unregister|0|1" "$(state_of "$out")"
    assert_contains "13a $form: reports the removal" "Removed the aitask_questions server" "$out"
    assert_not_contains "13a $form: never claims it was not registered" "not registered; the decline is recorded" "$out"

    d="$(make_cfx "g13c_$form" "$cfg")"; out="$(run_cfx "$d" 0 0 "")"
    assert_eq "13c $form, setup_codex_cli + --no: removed" "no" "$(parsed_reg "$d/.codex/config.toml")"
    assert_eq "13c $form: unregistered, not skipped" "unregister|0|1" "$(state_of "$out")"
    assert_eq "13c $form: deps not wanted" "no" "$(deps_of "$out")"

    d="$(make_cfx "g13d_$form" "$cfg")"; out="$(run_cfx "$d" "" 0 "")"
    assert_eq "13d $form, no flag: kept" "yes" "$(parsed_reg "$d/.codex/config.toml")"
    assert_contains "13d $form: treated as the remembered yes" "registered (kept)" "$out"
    assert_not_contains "13d $form: no prompt" "Register the aitask_questions question server?" "$out"
    assert_eq "13d $form: deps wanted (revalidate/repair)" "yes" "$(deps_of "$out")"
done
printf '# [mcp_servers."aitask_questions"]\nx = 1\n' > "$TESTROOT/g13_commented.toml"
questions_server_registered "$TESTROOT/g13_commented.toml"; assert_eq "13e commented-out quoted table: not registered" "1" "$?"
printf 'this is = = not toml\n' > "$TESTROOT/g13_broken.toml"
questions_server_registered "$TESTROOT/g13_broken.toml"; assert_eq "13f unparseable config: not registered" "1" "$?"

echo ""
echo "--- Group 10: flag parsing ---"
G10_HOME="$TESTROOT/g10home"; mkdir -p "$G10_HOME"
out="$(env -u AITASKS_HOME HOME="$G10_HOME" bash "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" \
    --with-codex-questions --no-codex-questions </dev/null 2>&1)"; rc=$?
assert_eq "10a both flags: refused" "1" "$rc"
assert_contains "10a both flags: says why" "cannot be combined" "$out"
out="$(env -u AITASKS_HOME HOME="$G10_HOME" bash "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" \
    --hooks-only --no-codex-questions </dev/null 2>&1)"; rc=$?
assert_eq "10b --hooks-only + flag: refused" "1" "$rc"
assert_contains "10b --hooks-only + flag: says why" "--hooks-only cannot be combined with --with-codex-questions" "$out"
assert_eq "10c refusals ran no setup step (scratch HOME untouched)" "" "$(ls -A "$G10_HOME")"
usage_out="$(bash "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --help 2>&1)"
assert_contains "10d --help lists --with-codex-questions" "--with-codex-questions" "$usage_out"
assert_contains "10d --help lists --no-codex-questions" "--no-codex-questions" "$usage_out"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
