#!/usr/bin/env bash
# test_registry_concurrency.sh — the registry mutex prevents lost updates (t1073).
#
# Black-box test of the real entry point (`ait projects` subcommands). Before the
# fix, concurrent `add`s (fired silently on every tmux session bootstrap) did an
# unlocked whole-file read-modify-write and clobbered each other — dropping
# project_group and last_opened on the loser's entries. This pins that concurrent
# mutations now serialize so every group assignment and last_opened bump survives.
#
# Run: bash tests/test_registry_concurrency.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PROJECTS="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

PASS=0
FAIL=0
TOTAL=0

if [[ -z "$(resolve_python)" ]]; then
    echo "SKIP: no Python interpreter resolved; registry mutation requires Python."
    exit 0
fi

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

# Isolate from any AITASKS_PROJECT_<name> process env contamination.
unset "${!AITASKS_PROJECT_@}" 2>/dev/null || true

# Two throwaway aitasks projects (no `name` in config → registry name = basename;
# no project_group in config → registry is the sole group store, so a lost group
# can NOT be healed from config — exactly the t1073 scenario).
mkdir -p "$TMPROOT/projA/aitasks/metadata" "$TMPROOT/projB/aitasks/metadata"
: > "$TMPROOT/projA/aitasks/metadata/project_config.yaml"
: > "$TMPROOT/projB/aitasks/metadata/project_config.yaml"
PA="$TMPROOT/projA"
PB="$TMPROOT/projB"

REG="$TMPROOT/projects.yaml"
TODAY="$(date -u +%Y-%m-%d)"

seed_with_groups() {
    cat > "$REG" <<EOF
# aitasks per-user project registry — managed by \`ait projects\`.
# Edit by hand at your own risk; use \`ait projects add\` instead.
projects:
  - name: projA
    path: $PA
    last_opened: 2026-06-01
    project_group: team_a
  - name: projB
    path: $PB
    last_opened: 2026-06-01
    project_group: team_a
EOF
}

# --- Case 1+2: concurrent adds preserve all groups AND all last_opened ----
seed_with_groups
for _ in 1 2 3 4 5; do
    AITASKS_PROJECTS_INDEX="$REG" "$PROJECTS" add "$PA" >/dev/null 2>&1 &
    AITASKS_PROJECTS_INDEX="$REG" "$PROJECTS" add "$PB" >/dev/null 2>&1 &
done
wait

group_count=$(grep -c '^    project_group: team_a$' "$REG")
assert_eq "case1: both project_group: team_a survive concurrent adds" "2" "$group_count"

today_count=$(grep -c "^    last_opened: $TODAY\$" "$REG")
assert_eq "case2: both last_opened bumps survive concurrent adds (no lost update)" \
    "2" "$today_count"

# --- Case 3: a `group set` racing bootstrap adds is not clobbered ---------
lost=0
trials=8
for _ in $(seq 1 "$trials"); do
    # Registry with NO groups; a burst of bootstrap adds races a user group-set.
    cat > "$REG" <<EOF
# aitasks per-user project registry — managed by \`ait projects\`.
projects:
  - name: projA
    path: $PA
    last_opened: 2026-06-01
  - name: projB
    path: $PB
    last_opened: 2026-06-01
EOF
    for _ in 1 2 3; do
        AITASKS_PROJECTS_INDEX="$REG" "$PROJECTS" add "$PA" >/dev/null 2>&1 &
        AITASKS_PROJECTS_INDEX="$REG" "$PROJECTS" add "$PB" >/dev/null 2>&1 &
    done
    AITASKS_PROJECTS_INDEX="$REG" "$PROJECTS" group set projA team_a >/dev/null 2>&1 &
    wait
    grep -q '^    project_group: team_a$' "$REG" || lost=$((lost + 1))
done
assert_eq "case3: group set survives concurrent adds across $trials trials" "0" "$lost"

# --- Summary ------------------------------------------------------------
echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
