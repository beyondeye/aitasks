#!/usr/bin/env bash
# test_setup_model_stats_migration.sh - the `ait setup` / `ait upgrade` hook that
# moves legacy code-agent stats into aitask-stats (t1912_5).
#
# setup_model_stats_migration runs `aitask_model_stats.py migrate` and reports
# per agent. It is never fatal: a deferral or an error is a warning and the
# function returns 0. AIT_STATS_MIGRATE=0 opts out. The protocol itself is
# tested in tests/test_model_stats_migrate.py; this file pins the hook.
#
# Runs the setup helpers via --source-only in a scratch copy of the framework,
# under a scratch HOME; never the real ~/.aitask*. No remote: the no-remote
# (local) migration path.
#
# Run: bash tests/test_setup_model_stats_migration.sh
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/framework_copy.sh
. "$PROJECT_DIR/tests/lib/framework_copy.sh"
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PASS=0
FAIL=0
TOTAL=0

PY="$(resolve_python)"
export AIT_PYTHON="$PY"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/setup-stats-migrate-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/home"
export HOME="$WORK/home" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
unset AITASKS_HOME TASK_DIR PLAN_DIR AIT_STATS_MIGRATE

# new_project <name>: a legacy-mode project (task data on main) whose three
# registries carry legacy counters, committed.
new_project() {
    local t="$WORK/$1"
    mkdir -p "$t/aitasks/metadata"
    copy_framework_tree "$PROJECT_DIR/.aitask-scripts" "$t/.aitask-scripts"
    cp "$PROJECT_DIR"/tests/golden/stats_readers/models_*.json "$t/aitasks/metadata/"
    git init -q -b main "$t"
    git -C "$t" config user.email t@example.com
    git -C "$t" config user.name T
    git -C "$t" add aitasks
    git -C "$t" commit -q -m init
    printf '%s' "$t"
}

# insetup <project> <code>: run <code> in a bash that sourced <project>'s setup.
insetup() {
    T="$1" bash -c 'source "$T/.aitask-scripts/aitask_setup.sh" --source-only; cd "$T" || exit 1; '"$2" 2>&1
}

stats_keys() {
    grep -c 'usagestats\|verifiedstats' "$1/aitasks/metadata/models_claudecode.json"
}

echo "=== Test 1: first run migrates every agent and strips the registries ==="
P1="$(new_project p1)"
out="$(insetup "$P1" 'setup_model_stats_migration; echo "RC=$?"')"
assert_contains "returns 0" "RC=0" "$out"
assert_contains "claudecode migrated" "Stats migrated: claudecode|" "$out"
assert_contains "codex migrated" "Stats migrated: codex|" "$out"
assert_contains "opencode migrated" "Stats migrated: opencode|" "$out"
assert_eq "registry stripped" "0" "$(stats_keys "$P1")"
assert_eq "marker on aitask-stats" "0" \
    "$(git -C "$P1" cat-file -e aitask-stats:migrations/claudecode.json; echo $?)"
assert_eq "worktree clean after the scoped strip commits" "" "$(git -C "$P1" status --porcelain -- aitasks)"

echo "=== Test 2: a second run is quiet and writes nothing ==="
before="$(git -C "$P1" rev-parse HEAD aitask-stats)"
out="$(insetup "$P1" 'setup_model_stats_migration; echo "RC=$?"')"
assert_contains "returns 0" "RC=0" "$out"
assert_contains "already migrated summary" "already on the aitask-stats branch" "$out"
assert_not_contains "no migrated line" "Stats migrated" "$out"
assert_eq "no new commits" "$before" "$(git -C "$P1" rev-parse HEAD aitask-stats)"

echo "=== Test 3: AIT_STATS_MIGRATE=0 opts out ==="
P3="$(new_project p3)"
out="$(AIT_STATS_MIGRATE=0 insetup "$P3" 'setup_model_stats_migration; echo "RC=$?"')"
assert_contains "returns 0" "RC=0" "$out"
assert_not_contains "nothing reported" "Stats migrated" "$out"
assert_eq "no aitask-stats branch" "" \
    "$(git -C "$P3" rev-parse --verify -q refs/heads/aitask-stats)"
assert_eq "registry untouched" "0" "$([ "$(stats_keys "$P3")" -gt 0 ]; echo $?)"

echo "=== Test 4: no Python => a deferral warning, never fatal ==="
out="$(insetup "$P3" 'resolve_python() { return 1; }; setup_model_stats_migration; echo "RC=$?"')"
assert_contains "returns 0" "RC=0" "$out"
assert_contains "deferral reported" "MIGRATE_DEFERRED:all|no_python" "$out"
assert_eq "no aitask-stats branch" "" \
    "$(git -C "$P3" rev-parse --verify -q refs/heads/aitask-stats)"

echo "=== Test 5: a failing interpreter is never fatal ==="
cat > "$WORK/badpy" <<'EOF'
#!/bin/sh
echo "boom" >&2
exit 3
EOF
chmod +x "$WORK/badpy"
out="$(insetup "$P3" "resolve_python() { echo '$WORK/badpy'; }; setup_model_stats_migration; echo \"RC=\$?\"")"
assert_contains "returns 0" "RC=0" "$out"
assert_contains "failure surfaced" "boom" "$out"
assert_contains "reported as incomplete, with the retry hint" "did not complete — retried on the next" "$out"

echo "=== Test 6: a dirty registry defers with the retry hint ==="
P6="$(new_project p6)"
sed -i 's/"notes": "/"notes": "edited /' "$P6/aitasks/metadata/models_claudecode.json"
out="$(insetup "$P6" 'setup_model_stats_migration; echo "RC=$?"')"
assert_contains "returns 0" "RC=0" "$out"
assert_contains "claudecode deferred" "MIGRATE_DEFERRED:claudecode|dirty" "$out"
assert_contains "retry hint" "retried on the next" "$out"
assert_contains "codex still migrated" "Stats migrated: codex|" "$out"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
