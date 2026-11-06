#!/usr/bin/env bash
# test_relations_cli.sh - `ait relations` state lines and verbs (t1981_1).
#
# Scratch repos and a bare origin only; never the real aitask-relations branch
# and never ~/.aitask*. Assertions run in the main shell (commands are only
# captured through $( )), so the in-process counters are sufficient.
#
# Run: bash tests/test_relations_cli.sh
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PASS=0
FAIL=0
TOTAL=0

AIT_PYTHON="$(resolve_python)"
export AIT_PYTHON
SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_relations.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/relations-cli-XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home"
export HOME="$TMP/home" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
unset AITASKS_HOME AIT_RELATIONS TASK_DIR PLAN_DIR ARCHIVED_DIR ARCHIVED_PLAN_DIR

git init -q --bare "$TMP/origin.git"

new_repo() {  # new_repo <name> <with-remote:0|1> [project-name]
    local r="$TMP/$1" project="${3:-aitasks}"
    git init -q "$r"
    git -C "$r" config user.email t@example.com
    git -C "$r" config user.name T
    [[ "$2" == 1 ]] && git -C "$r" remote add origin "$TMP/origin.git"
    mkdir -p "$r/aitasks/metadata" "$r/aitasks/archived" "$r/aiplans/archived"
    printf 'project:\n  name: %s\n' "$project" > "$r/aitasks/metadata/project_config.yaml"
    local tid
    for tid in 1 2; do
        printf -- '---\nstatus: Ready\ncreated_at: 2026-01-01 10:00\n---\n\nGoal %s.\n' "$tid" \
            > "$r/aitasks/t${tid}_name.md"
    done
    printf '%s\n' "$r"
}

publish() {  # publish <repo> [type] [project]: a record "t1 <type> t2", written and flushed
    "$AIT_PYTHON" - "$1" "$PROJECT_DIR" "${2:-affects}" "${3:-aitasks}" <<'PY'
import sys
root, project, rtype, local = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
sys.path[:0] = [f"{project}/tests", f"{project}/.aitask-scripts/lib"]
from test_relations_store import record
import relations_store
out = relations_store.Store(root).write("records/t1.json", record(root, "1", [("1", "2", rtype)], project=local))
print("\n".join(out))
PY
}

relations() {  # relations <repo> <args...>: stdout, then "EXIT:<rc>" as the last line
    local repo="$1" rc=0 out
    shift
    out="$(cd "$repo" && "$SCRIPT" "$@" 2>&1)" || rc=$?
    printf '%s\nEXIT:%s\n' "$out" "$rc"
}

line() { printf '%s\n' "$1" | sed -n "${2}p"; }

# --- disabled, local-only ------------------------------------------------------
R="$(new_repo local 0)"
out="$(relations "$R" show 1)"
assert_eq "line 1 is RELATIONS_STATE" "RELATIONS_STATE:disabled" "$(line "$out" 1)"
assert_eq "line 2 is STORE" "STORE:local_only" "$(line "$out" 2)"
assert_eq "line 3 is ANALYSIS" "ANALYSIS:t1|disabled" "$(line "$out" 3)"
assert_contains "disabled is not 'no related tasks'" "relations analysis is disabled" "$out"
assert_contains "show exits 0" "EXIT:0" "$out"

# --- host_off ----------------------------------------------------------------------
printf 'project:\n  name: aitasks\nrelations:\n  enabled: true\n' > "$R/aitasks/metadata/project_config.yaml"
out="$(AIT_RELATIONS=0 relations "$R" show 1)"
assert_eq "host_off state line" "RELATIONS_STATE:host_off" "$(line "$out" 1)"
assert_eq "enabled, never analysed" "ANALYSIS:t1|never" "$(line "$out" 3)"

# --- empty, then published, show --json, why ----------------------------------------
R="$(new_repo remote 1)"
out="$(relations "$R" show 2)"
assert_eq "empty store" "STORE:empty" "$(line "$out" 2)"
assert_contains "empty store reports zero relations" "RELATIONS:0" "$out"
pub="$(publish "$R")"
assert_contains "record published" "PUBLISHED:1" "$pub"
out="$(relations "$R" show 2)"
assert_contains "fresh after publish" "STORE:fresh@" "$(line "$out" 2)"
assert_contains "reverse relation shown with direction" "REL:t1 affects this task|affects|aitasks#1|fresh" "$out"
json="$(cd "$R" && "$SCRIPT" show 1 --json)"
parsed="$(printf '%s' "$json" | "$AIT_PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print(d["store"].split("@")[0], d["analysis"], len(d["relations"]), d["relations"][0]["type"])')"
assert_eq "show --json parses" "fresh analysed:1(stage=1) 1 affects" "$parsed"
out="$(relations "$R" why 1 2)"
assert_contains "why prints the first ANALYSIS line" "ANALYSIS:t1|analysed:1(stage=1)" "$out"
assert_contains "why prints the second ANALYSIS line" "ANALYSIS:t2|disabled" "$out"
assert_contains "why names the recording task" "recorded_by:aitasks#1" "$out"

# --- stale, status, retained flush --------------------------------------------------
git -C "$R" remote set-url origin "$TMP/missing.git"
out="$(relations "$R" show 2)"
assert_contains "stale on an unreachable remote" "STORE:stale:" "$(line "$out" 2)"
assert_contains "stale store still shows the latest known relation" "REL:t1 affects this task" "$out"
out="$(relations "$R" status)"
assert_contains "status lists an empty outbox" "OUTBOX:none" "$out"
out="$(publish "$R")"
assert_contains "write against an unreachable remote is retained" "RETAINED:1|" "$out"
out="$(relations "$R" status)"
assert_contains "status lists the retained entry" "OUTBOX:records/t1.json|age=" "$out"
assert_not_contains "status shows the last error" "err=-" "$out"
out="$(relations "$R" flush)"
assert_contains "flush exits 3 when retained" "EXIT:3" "$out"
git -C "$R" remote set-url origin "$TMP/origin.git"
out="$(relations "$R" flush)"
assert_contains "flush exits 0 once the remote is back" "EXIT:0" "$out"

# --- symmetric relation, seen from the far end: `other` is t1, never the queried task
R3="$(new_repo symmetric 0)"
publish "$R3" coordinates_with >/dev/null
out="$(relations "$R3" show 2)"
assert_contains "symmetric reverse names the far end" "REL:this task coordinates with t1|coordinates_with|aitasks#1|fresh" "$out"

# --- the local project name qualifies every ref; it is never assumed --------------
R4="$(new_repo mobile 0 mobile)"
publish "$R4" affects mobile >/dev/null
out="$(relations "$R4" show 2)"
assert_contains "another project's name is preserved" "REL:t1 affects this task|affects|mobile#1|fresh" "$out"
out="$(relations "$R4" show mobile#2)"
assert_contains "a qualified local ref is the same task" "REL:t1 affects this task|affects|mobile#1" "$out"
json="$(cd "$R4" && "$SCRIPT" show 2 --json)"
assert_eq "show --json names the local project" "mobile mobile#2 mobile#1" \
    "$(printf '%s' "$json" | "$AIT_PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print(d["project"], d["task"], d["relations"][0]["from"])')"
R5="$(new_repo noname 0)"
: > "$R5/aitasks/metadata/project_config.yaml"
out="$(relations "$R5" show 1)"
assert_contains "a missing project.name is reported" "PROJECT_UNRESOLVED" "$out"
assert_contains "and exits 1" "EXIT:1" "$out"

# --- unknown verb, no-fetch on a clone with no data ---------------------------------
out="$(relations "$R" bogus)"
assert_contains "unknown verb exits 2" "EXIT:2" "$out"
R2="$(new_repo fresh 1)"
out="$(relations "$R2" show 1 --no-fetch)"
assert_eq "no data and no fetch is unreachable" "STORE:unreachable:no_fetch" "$(line "$out" 2)"
assert_eq "unreachable is unknown, not 'no relations'" "ANALYSIS:t1|unknown(store_unreachable)" "$(line "$out" 3)"

# --- the ait dispatcher routes `relations` ---------------------------------------------
out="$("$PROJECT_DIR/ait" relations bogus 2>&1)" && rc=0 || rc=$?
assert_eq "ait relations routes to the store CLI" "2" "$rc"

echo ""
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]] || exit 1
