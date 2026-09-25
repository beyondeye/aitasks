#!/usr/bin/env bash
# shellcheck disable=SC2016  # the bash -c snippets expand in the child, by design
# test_setup_hooks_only.sh - `ait setup --hooks-only` through its real command path (t1849).
#
# Runs `bash <fixture>/.aitask-scripts/aitask_setup.sh --hooks-only ...` in a
# temporary git project (a copy of aitask_setup.sh + lib/, a tracked VERSION and
# the staged hook seed), with HOME pointed at a temp dir. Covers consent (no
# terminal, --yes, a PTY answering n / Y), the order of checks (installed before
# consent, runtime before any write), failure never looking like success, the
# commit, and that no other setup step runs.
#
# The PTY cases use tests/lib/pty_drive.py: every setup prompt is gated on
# [[ -t 0 ]], and a pipe would silently take the non-interactive branch.
#
# Run: bash tests/test_setup_hooks_only.sh

set -uo pipefail

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

SEED="$PROJECT_DIR/seed/claude_settings.hooks.json"
TESTROOT="$(mktemp -d "${TMPDIR:-/tmp}/t1849_hooksonly_XXXXXX")"
trap 'rm -rf "$TESTROOT"' EXIT

# The real PATH minus ~/.aitask/*: the framework's python3 wrapper there execs
# $HOME/.aitask/venv/bin/python, which does not exist under the temp HOME.
CLEAN_PATH=""
IFS=':' read -r -a _path_dirs <<<"$PATH"
for _d in "${_path_dirs[@]}"; do
    case "$_d" in */.aitask/*|*/.aitask) continue ;; esac
    CLEAN_PATH="${CLEAN_PATH:+$CLEAN_PATH:}$_d"
done
REAL_PY="$(PATH="$CLEAN_PATH" command -v python3)"

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

OLD_PY="$TESTROOT/old_python"
cat >"$OLD_PY" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do case "\$a" in *version_info*) exit 1 ;; esac; done
exec "$REAL_PY" "\$@"
EOF
chmod +x "$OLD_PY"

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid
export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid

# make_proj <name> — a committed fixture project; prints its path.
make_proj() {
    local dir="$TESTROOT/$1"
    mkdir -p "$dir/.aitask-scripts" "$dir/aitasks/metadata" "$TESTROOT/home_$1"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$dir/.aitask-scripts/"
    cp -r "$PROJECT_DIR/.aitask-scripts/lib" "$dir/.aitask-scripts/lib"
    cp "$PROJECT_DIR/.aitask-scripts/VERSION" "$dir/.aitask-scripts/VERSION"
    cp "$SEED" "$dir/aitasks/metadata/claude_settings.hooks.json"
    (
        cd "$dir" && git init -q && git add -A && git commit -qm init
    ) >/dev/null 2>&1
    echo "$dir"
}

# run_setup <dir> <mode> <args...> — non-interactive; output in OUT, status in RC.
#   mode: normal | nopy | override_old
run_setup() {
    local dir="$1" mode="$2"; shift 2
    local -a envs=(env -u AIT_PYTHON HOME="$TESTROOT/home_${dir##*/}" PATH="$CLEAN_PATH")
    case "$mode" in
        nopy) envs=(env -u AIT_PYTHON HOME="$TESTROOT/home_${dir##*/}" PATH="$NOPY_BIN") ;;
        override_old) envs=(env AIT_PYTHON="$OLD_PY" HOME="$TESTROOT/home_${dir##*/}" PATH="$CLEAN_PATH") ;;
    esac
    RC=0
    OUT="$("${envs[@]}" bash "$dir/.aitask-scripts/aitask_setup.sh" "$@" </dev/null 2>&1)" || RC=$?
}

# run_pty <dir> <answers-csv> <args...> — under a real PTY.
run_pty() {
    local dir="$1" answers="$2"; shift 2
    RC=0
    OUT="$("$REAL_PY" "$PROJECT_DIR/tests/lib/pty_drive.py" --answers "$answers" -- \
        env -u AIT_PYTHON HOME="$TESTROOT/home_${dir##*/}" PATH="$CLEAN_PATH" \
        bash "$dir/.aitask-scripts/aitask_setup.sh" "$@" 2>&1)" || RC=$?
}

count_hook() {
    [[ -f "$1" ]] || { echo 0; return; }
    "$REAL_PY" - "$1" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(-1); raise SystemExit(0)
n = 0
for g in d.get("hooks", {}).get("SessionStart", []) or []:
    for h in (g.get("hooks") or []):
        if "aitask_session_hook.sh" in (h.get("command") or ""):
            n += 1
print(n)
PY
}

yesno() { if "$@"; then echo yes; else echo no; fi; }

echo "=== ait setup --hooks-only (t1849) ==="

echo ""
echo "--- consent ---"
P="$(make_proj c_nottty)"
run_setup "$P" normal --hooks-only
assert_eq "no terminal, no --yes -> exit 2" "2" "$RC"
assert_contains "...with the refusal message" "needs an interactive answer" "$OUT"
assert_eq "...and no settings.json written" "no" "$(yesno test -f "$P/.claude/settings.json")"

P="$(make_proj c_decline)"
run_pty "$P" 'n' --hooks-only
assert_contains "PTY: the prompt is shown" "Install the session hook?" "$OUT"
assert_eq "PTY, answer n -> exit 0" "0" "$RC"
assert_eq "PTY, answer n -> nothing installed" "no" "$(yesno test -f "$P/.claude/settings.json")"

P="$(make_proj c_accept)"
run_pty "$P" 'Y,Y' --hooks-only
assert_eq "PTY, answer Y -> exit 0" "0" "$RC"
assert_eq "PTY, answer Y -> hook installed" "1" "$(count_hook "$P/.claude/settings.json")"
assert_eq "...and committed, alone" ".claude/settings.json" \
    "$(git -C "$P" log -1 --name-only --format= 2>/dev/null)"
assert_eq "...and the tree is clean afterwards" "" "$(git -C "$P" status --porcelain 2>/dev/null)"

echo ""
echo "--- repeated runs: installed is checked before consent ---"
run_pty "$P" 'Y' --hooks-only
assert_contains "PTY re-run -> already installed" "already installed" "$OUT"
assert_not_contains "...and no prompt" "Install the session hook?" "$OUT"
run_setup "$P" normal --hooks-only
assert_eq "no terminal, no --yes, already installed -> exit 0" "0" "$RC"
assert_contains "...already installed" "already installed" "$OUT"

P="$(make_proj c_yes_tty)"
run_pty "$P" 'n,Y' --hooks-only --yes
assert_eq "PTY + --yes -> exit 0" "0" "$RC"
assert_not_contains "PTY + --yes -> no consent prompt" "Install the session hook?" "$OUT"
assert_eq "PTY + --yes, even answering n -> hook installed" "1" \
    "$(count_hook "$P/.claude/settings.json")"

P="$(make_proj c_yes)"
run_setup "$P" normal --hooks-only --yes
assert_eq "no terminal + --yes -> exit 0" "0" "$RC"
assert_eq "no terminal + --yes -> hook installed" "1" "$(count_hook "$P/.claude/settings.json")"

echo ""
echo "--- nothing else runs ---"
assert_not_contains "no OS detection" "Detected OS" "$OUT"
assert_not_contains "no framework setup banner" "aitask framework setup" "$OUT"
assert_not_contains "no venv step" "venv" "$OUT"
assert_eq "\$HOME/.aitask was not created" "no" "$(yesno test -e "$TESTROOT/home_c_yes/.aitask")"

echo ""
echo "--- failure never looks like success ---"
P="$(make_proj f_invalid)"
mkdir -p "$P/.claude"; printf '{"hooks": {\n' >"$P/.claude/settings.json"
before="$(cksum <"$P/.claude/settings.json")"
run_pty "$P" 'Y,Y' --hooks-only
assert_eq "invalid settings (PTY, Y) -> exit 1" "1" "$RC"
assert_contains "...with the invalid hint" "not valid JSON" "$OUT"
assert_not_contains "...no success line" "hook installed" "$OUT"
assert_not_contains "...and no prompt" "Install the session hook?" "$OUT"
assert_eq "...file byte-for-byte unchanged" "$before" "$(cksum <"$P/.claude/settings.json")"

P="$(make_proj f_noseed)"
rm "$P/aitasks/metadata/claude_settings.hooks.json"
run_setup "$P" normal --hooks-only --yes
assert_eq "no seed (installed layout) -> exit 1" "1" "$RC"
# An installed project has no seed/ (install.sh deletes it), so `ait setup`
# cannot restore the seed there -- only the installer can.
assert_not_contains "...does NOT claim ait setup restores it" "run 'ait setup' to restore it" "$OUT"
assert_contains "...points to the installer" "install.sh | bash -s -- --force" "$OUT"
# `ait` may run from a subdirectory; install.sh defaults to ".", so the copied
# command must name the project root.
assert_contains "...with --dir naming the project root" \
    "--force --dir $(printf '%q' "$(cd "$P" && pwd -P)")" "$OUT"
P="$(make_proj f_noseed_src)"
rm "$P/aitasks/metadata/claude_settings.hooks.json"
mkdir -p "$P/seed"; cp "$SEED" "$P/seed/claude_settings.hooks.json"
run_setup "$P" normal --hooks-only --yes
assert_eq "no seed (source checkout with seed/) -> exit 1" "1" "$RC"
assert_contains "...naming ait setup, which copies seed/" "run 'ait setup' to restore it" "$OUT"

P="$(make_proj f_readonly)"
mkdir -p "$P/.claude"; printf '{"env": {"K": "V"}}\n' >"$P/.claude/settings.json"
chmod 444 "$P/.claude/settings.json"
if [[ "$(id -u)" != 0 ]]; then
    run_setup "$P" normal --hooks-only --yes
    assert_eq "read-only settings.json -> exit 1" "1" "$RC"
    assert_contains "...says it is not writable" ".claude/settings.json is not writable" "$OUT"
    assert_not_contains "...no 'Merged' success line" "Merged aitasks session hook" "$OUT"
    assert_eq "...hook still absent" "0" "$(count_hook "$P/.claude/settings.json")"
fi
chmod 644 "$P/.claude/settings.json"

echo ""
echo "--- runtime before any write ---"
P="$(make_proj r_nopy)"
run_setup "$P" nopy --hooks-only --yes
assert_eq "Python hidden + --yes -> exit 1" "1" "$RC"
assert_contains "...names the full ait setup" "the full 'ait setup'" "$OUT"
assert_eq "...and NO settings.json written" "no" "$(yesno test -f "$P/.claude/settings.json")"

P="$(make_proj r_override)"
run_setup "$P" override_old --hooks-only --yes
assert_eq "old AIT_PYTHON + --yes -> exit 1" "1" "$RC"
assert_contains "...names AIT_PYTHON" "AIT_PYTHON=$OLD_PY" "$OUT"
assert_contains "...says to unset or repoint it" "unset AIT_PYTHON" "$OUT"
assert_not_contains "...never sends the user to the full ait setup" "full 'ait setup'" "$OUT"
assert_eq "...and no write" "no" "$(yesno test -f "$P/.claude/settings.json")"
# Following the advice really changes the interpreter the session store picks.
selected="$(env -u AIT_PYTHON HOME="$TESTROOT/home_r_override" PATH="$CLEAN_PATH" \
    bash -c 'source "$1"; resolve_python' _ "$P/.aitask-scripts/lib/python_resolve.sh")"
assert_eq "AIT_PYTHON unset -> the store would select the real python3" "$REAL_PY" "$selected"
run_setup "$P" normal --hooks-only --yes
assert_eq "...and --hooks-only --yes now installs the hook" "1" "$(count_hook "$P/.claude/settings.json")"

# A working AIT_PYTHON does not rescue a python3 that will not run: the hook
# calls bare python3 to read its payload.
BROKEN_BIN="$TESTROOT/broken_bin"
mkdir -p "$BROKEN_BIN"
printf '#!/usr/bin/env bash\nexit 127\n' >"$BROKEN_BIN/python3"
chmod +x "$BROKEN_BIN/python3"
P="$(make_proj r_broken)"
RC=0
OUT="$(env AIT_PYTHON="$REAL_PY" HOME="$TESTROOT/home_r_broken" PATH="$BROKEN_BIN:$CLEAN_PATH" \
    bash "$P/.aitask-scripts/aitask_setup.sh" --hooks-only --yes </dev/null 2>&1)" || RC=$?
assert_eq "broken python3 on PATH, working AIT_PYTHON -> exit 1" "1" "$RC"
assert_contains "...names the broken python3" "$BROKEN_BIN/python3" "$OUT"
assert_eq "...and no write" "no" "$(yesno test -f "$P/.claude/settings.json")"

echo ""
echo "--- flags ---"
P="$(make_proj x_flags)"
run_setup "$P" normal --yes
assert_eq "--yes without --hooks-only -> exit 1" "1" "$RC"
assert_contains "...explains why" "only meaningful with --hooks-only" "$OUT"
assert_eq "...and no write" "no" "$(yesno test -f "$P/.claude/settings.json")"
run_setup "$P" normal --help
assert_contains "--help lists --hooks-only" "--hooks-only" "$OUT"
assert_contains "--help lists --yes" "--yes " "$OUT"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
