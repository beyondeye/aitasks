#!/usr/bin/env bash
# test_setup_relations.sh - `ait setup`'s task-relations activation (t1981_3).
#
# report_relations_state prints RELATIONS:disabled by default (an absent
# relations.enabled), or RELATIONS:enabled(<agent>, cap <N>/day). The activation
# question (ask_relations_activation) fires only on a terminal and only while
# the key is absent; batch (non-tty) setup never asks. A "yes" that cannot
# resolve project.name leaves the key absent.
#
# Runs the setup helpers via --source-only in a scratch copy of the framework,
# under a scratch HOME; never the real ~/.aitask*. The tty cases need
# util-linux `script` and are skipped without it.
#
# Run: bash tests/test_setup_relations.sh
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
WORK="$(mktemp -d "${TMPDIR:-/tmp}/setup-relations-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/home"
export HOME="$WORK/home" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
export AITASKS_PROJECTS_INDEX="$WORK/projects.yaml"
unset AITASKS_HOME AIT_RELATIONS TASK_DIR PLAN_DIR

# new_project <name> <config text>: a scratch project with a copy of the framework.
new_project() {
    local t="$WORK/$1"
    mkdir -p "$t/aitasks/metadata"
    copy_framework_tree "$PROJECT_DIR/.aitask-scripts" "$t/.aitask-scripts"
    cp "$PROJECT_DIR/seed/codeagent_config.json" "$t/aitasks/metadata/codeagent_config.json"
    cp "$PROJECT_DIR"/aitasks/metadata/models_*.json "$t/aitasks/metadata/" 2>/dev/null
    printf '%s' "$2" > "$t/aitasks/metadata/project_config.yaml"
    git init -q "$t"
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

# intty <project> <answer> <code>: as insetup, on a pseudo-terminal fed <answer>.
intty() {
    printf '%s\n' "$2" | T="$1" script -qec \
        'bash -c '\''source "$T/.aitask-scripts/aitask_setup.sh" --source-only; cd "$T" || exit 1; '"$3"\''' \
        /dev/null 2>&1
}

key_of() { "$PY" "$1/.aitask-scripts/lib/relations_config.py" state "$1" | sed -n 's/^RELATIONS_KEY://p'; }
line() { printf '%s\n' "$1" | tr -d '\r' | grep -- "^$2" || true; }

BASE=$'project:\n  name: proj\n'

# --- R1: absent key -> RELATIONS:disabled, with the enable hint -----------------
P="$(new_project r1 "$BASE")"
out="$(insetup "$P" report_relations_state)"
assert_eq "R1 absent key reports disabled" "RELATIONS:disabled" "$(line "$out" RELATIONS:)"
assert_contains "R1 the enable hint is shown" "ait relations enable" "$out"

# --- R2: batch (non-tty) setup never asks and leaves the key absent -------------
out="$(insetup "$P" 'ask_relations_activation </dev/null; echo DONE')"
assert_not_contains "R2 batch: no question" "Enable background task-relations analysis" "$out"
assert_eq "R2 batch: the key stays absent" "absent" "$(key_of "$P")"

# --- R3: enabled -> RELATIONS:enabled(<agent>, cap <N>/day) ---------------------
P3="$(new_project r3 "$BASE"$'relations:\n  enabled: true\n  max_jobs_per_day: 7\n')"
out="$(insetup "$P3" report_relations_state)"
assert_eq "R3 enabled reports agent and cap" "RELATIONS:enabled(claudecode/sonnet5_5, cap 7/day)" \
    "$(line "$out" RELATIONS:)"

if command -v script >/dev/null 2>&1 && script --version 2>&1 | grep -q util-linux; then
    # --- R4: tty "y" -> enabled: true, committed ----------------------------------
    P4="$(new_project r4 "$BASE")"
    out="$(intty "$P4" y ask_relations_activation)"
    assert_contains "R4 tty: the question is asked" "Enable background task-relations analysis? [y/N]" "$out"
    assert_eq "R4 tty yes: enabled written" "true" "$(key_of "$P4")"
    assert_contains "R4 tty yes: committed" "enabled: true" \
        "$(git -C "$P4" show HEAD:aitasks/metadata/project_config.yaml)"

    # --- R5: tty default (empty answer) -> enabled: false, never asked again -------
    P5="$(new_project r5 "$BASE")"
    intty "$P5" "" ask_relations_activation >/dev/null
    assert_eq "R5 tty default: false written" "false" "$(key_of "$P5")"
    out="$(intty "$P5" y ask_relations_activation)"
    assert_not_contains "R5 answered: not asked again" "[y/N]" "$out"
    assert_eq "R5 answered: unchanged" "false" "$(key_of "$P5")"

    # --- R6: tty "y" without a resolvable project.name -> key stays absent --------
    P6="$(new_project r6 $'other: 1\n')"
    : > "$AITASKS_PROJECTS_INDEX"
    out="$(intty "$P6" y ask_relations_activation)"
    assert_contains "R6 unresolved name: explained" "Set project.name, then run: ait relations enable" "$out"
    assert_eq "R6 unresolved name: the key stays absent" "absent" "$(key_of "$P6")"
else
    echo "SKIP: R4-R6 (util-linux script not available)"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
