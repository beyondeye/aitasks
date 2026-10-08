#!/usr/bin/env bash
# test_install_superseded_models.sh - install.sh's superseded-model check (t1910)
#
# Part 1 (function level): check_superseded_model_defaults() with the real
#   prerequisites main() loads (install.sh --source-only + aitask_setup.sh
#   --source-only) and a stub helper that reports how it was invoked.
# Part 2 (full flow): a real `install.sh --force --local-tarball` upgrade over a
#   legacy-mode project whose defaults use superseded models, non-tty.
#
# Run: bash tests/test_install_superseded_models.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0
. "$PROJECT_DIR/tests/lib/asserts.sh"

TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/test_install_superseded_XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT

INSTALL_SH="$PROJECT_DIR/install.sh"
SETUP_SH="$PROJECT_DIR/.aitask-scripts/aitask_setup.sh"

# ============================================================
# Part 1: function level
# ============================================================
echo "=== Part 1: check_superseded_model_defaults (function level) ==="

STUB_ROOT="$TEST_ROOT/stub"
mkdir -p "$STUB_ROOT/.aitask-scripts"
# Records its argv and whether stdin is /dev/null, then exits with $STUB_RC.
cat > "$STUB_ROOT/.aitask-scripts/aitask_model_supersession.py" <<'EOF'
import os, sys
devnull = os.stat("/dev/null")
st = os.fstat(0)
stdin = "devnull" if (st.st_rdev == devnull.st_rdev and st.st_ino == devnull.st_ino) else "other"
with open(os.environ["STUB_LOG"], "a") as fh:
    fh.write("ARGS:" + " ".join(sys.argv[1:]) + "\nSTDIN:" + stdin + "\n")
sys.exit(int(os.environ.get("STUB_RC", "0")))
EOF

# run_fn <existing_install> <stub_rc> <source_setup:yes|no>
# Runs the function under `set -euo pipefail` with a PIPE on stdin (a
# non-tty that is NOT /dev/null), so the test can see the function swap it.
run_fn() {
    local existing="$1" rc="$2" with_setup="$3"
    : > "$TEST_ROOT/stub.log"
    echo "piped-stdin" | STUB_LOG="$TEST_ROOT/stub.log" STUB_RC="$rc" \
        INSTALL_SH="$INSTALL_SH" SETUP_SH="$SETUP_SH" STUB_ROOT="$STUB_ROOT" \
        EXISTING="$existing" WITH_SETUP="$with_setup" \
        bash -c '
            set -euo pipefail
            . "$INSTALL_SH" --source-only
            if [[ "$WITH_SETUP" == yes ]]; then
                source "$SETUP_SH" --source-only
            fi
            INSTALL_DIR="$STUB_ROOT"
            EXISTING_INSTALL="$EXISTING"
            check_superseded_model_defaults
            echo "FN_RETURNED_0"
        ' 2>&1
}

out=$(run_fn false 0 yes)
assert_contains "fresh install: function returns 0" "FN_RETURNED_0" "$out"
assert_eq "fresh install: helper not run" "" "$(cat "$TEST_ROOT/stub.log")"

out=$(run_fn true 0 yes)
log=$(cat "$TEST_ROOT/stub.log")
assert_contains "existing install: function returns 0" "FN_RETURNED_0" "$out"
assert_contains "non-tty: report mode (check --root)" "ARGS:check --root $STUB_ROOT" "$log"
assert_not_contains "non-tty: never --interactive" "--interactive" "$log"
assert_contains "non-tty: stdin replaced by /dev/null" "STDIN:devnull" "$log"

out=$(run_fn true 5 yes)
assert_contains "failing helper: function still returns 0 under set -e" "FN_RETURNED_0" "$out"
assert_contains "failing helper: warns with the re-run command" "ait codeagent check-superseded" "$out"
assert_contains "failing helper: names the exit status" "exit 5" "$out"

out=$(run_fn true 0 no)
assert_contains "no resolver loaded: function returns 0" "FN_RETURNED_0" "$out"
assert_contains "no resolver loaded: warns" "Python resolver not loaded" "$out"
assert_eq "no resolver loaded: helper not run" "" "$(cat "$TEST_ROOT/stub.log")"

# ============================================================
# Part 2: full install.sh upgrade, non-tty
# ============================================================
echo "=== Part 2: install.sh --force upgrade over superseded defaults ==="

TARBALL="$TEST_ROOT/aitasks.tar.gz"
# A release-shaped tarball of this checkout (packaging/ carries the global shim).
(
    cd "$PROJECT_DIR" || exit 1
    tar czf "$TARBALL" --exclude='__pycache__' \
        .aitask-scripts/ ait packaging/ seed/ .claude/skills/ 2>/dev/null
)

PROJECT="$TEST_ROOT/proj"
FAKE_HOME="$TEST_ROOT/home"
# The isolated HOME has no framework venv, so a ~/.aitask/bin/python3 wrapper
# inherited on PATH would point at nothing. Drop those entries: the install then
# resolves the system python3, as on a machine without the framework yet.
CLEAN_PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '/\.aitask/bin$' | paste -sd: -)
mkdir -p "$PROJECT" "$FAKE_HOME"
(
    cd "$PROJECT" || exit 1
    git init --quiet -b master
    git config user.email "test@test.com"
    git config user.name "Test User"
    git config commit.gpgsign false
    echo "# project" > README.md
    git add README.md
    git commit -q -m "Initial commit"
) || { echo "FATAL: could not init test repo"; exit 1; }

# First install, then pin the defaults to what an older release shipped.
HOME="$FAKE_HOME" PATH="$CLEAN_PATH" bash "$INSTALL_SH" --dir "$PROJECT" --local-tarball "$TARBALL" \
    </dev/null >/dev/null 2>&1
config="$PROJECT/aitasks/metadata/codeagent_config.json"
assert_eq "precondition: first install wrote the config" "yes" "$([[ -f "$config" ]] && echo yes || echo no)"
jq '.defaults.pick = "claudecode/opus5"
    | .defaults.explain = "claudecode/sonnet5"
    | .defaults.qa = "claudecode/haiku4_5"' "$config" > "$config.tmp" && mv "$config.tmp" "$config"
(
    cd "$PROJECT" || exit 1
    git add -A
    git commit -q -m "ait: Add aitask framework (older defaults)"
)
config_before=$(jq -S '.defaults' "$config")

rc=0
upgrade_output=$(HOME="$FAKE_HOME" PATH="$CLEAN_PATH" timeout 600 bash "$INSTALL_SH" --force --dir "$PROJECT" \
    --local-tarball "$TARBALL" </dev/null 2>&1) || rc=$?
assert_eq "upgrade completed" "0" "$rc"
assert_contains "upgrade ran the check" "Checking for superseded code-agent model defaults" "$upgrade_output"
assert_contains "report lists opus5 -> opus5_5" \
    "claudecode/opus5 (pick) — superseded by claudecode/opus5_5" "$upgrade_output"
assert_contains "report lists sonnet5 -> sonnet5_5" \
    "claudecode/sonnet5 (explain) — superseded by claudecode/sonnet5_5" "$upgrade_output"
assert_contains "report gives the re-run hint" \
    "Run 'ait codeagent check-superseded' in a terminal" "$upgrade_output"
assert_not_contains "custom haiku4_5 default never offered" "claudecode/haiku4_5 (" "$upgrade_output"
assert_eq "non-tty upgrade leaves the defaults unchanged" "$config_before" "$(jq -S '.defaults' "$config")"
assert_eq "supersession table delivered with the framework" \
    "$(cat "$PROJECT_DIR/.aitask-scripts/lib/model_supersessions.json")" \
    "$(cat "$PROJECT/.aitask-scripts/lib/model_supersessions.json")"
assert_eq "merged config committed by the framework update, nothing left dirty" "0" \
    "$(git -C "$PROJECT" status --porcelain -- aitasks/metadata/codeagent_config.json | wc -l | tr -d ' ')"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
