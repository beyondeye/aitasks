#!/usr/bin/env bash
# test_brainstorm_context_helper.sh - Tests for aitask_brainstorm_context.sh,
# the read-only brainstorm id -> path resolver (t1823_1).
# Run: bash tests/test_brainstorm_context_helper.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# Shared assertion helpers (see tests/lib/asserts.sh). Every assertion runs in
# this shell (no `( … )` test bodies), so the in-process counters are enough.
# shellcheck source=lib/asserts.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0
FAIL=0
TOTAL=0

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh disable=SC1091
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- Fixture ------------------------------------------------------------------
# A copy of the helper, its sourced libs and the python packages it imports
# (whole directories: brainstorm/__init__.py imports siblings transitively).
FIX="$TMP/repo"
mkdir -p "$FIX/.aitask-scripts" "$FIX/aitasks/t995" "$FIX/.git"
cp "$PROJECT_DIR/.aitask-scripts/aitask_brainstorm_context.sh" "$FIX/.aitask-scripts/"
cp -r "$PROJECT_DIR/.aitask-scripts/lib" "$FIX/.aitask-scripts/"
cp -r "$PROJECT_DIR/.aitask-scripts/brainstorm" "$FIX/.aitask-scripts/"
cp -r "$PROJECT_DIR/.aitask-scripts/agentcrew" "$FIX/.aitask-scripts/"
find "$FIX/.aitask-scripts" -name __pycache__ -type d -prune -exec rm -rf {} +
HELPER="$FIX/.aitask-scripts/aitask_brainstorm_context.sh"

echo "task" > "$FIX/aitasks/t999_topic.md"
echo "other" > "$FIX/aitasks/t998_other.md"
echo "child" > "$FIX/aitasks/t995/t995_2_child.md"
printf '[core]\n' > "$FIX/.git/config"

(cd "$FIX" && "$PYTHON" - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts")
from pathlib import Path
import yaml
from brainstorm.brainstorm_session import crew_worktree, init_session
from brainstorm.brainstorm_dag import create_node, NODES_DIR

def session(num, task_file):
    crew_worktree(num).mkdir(parents=True, exist_ok=True)
    return init_session(num, task_file=task_file, user_email="t@t", initial_spec="spec")

# 999: well-formed session. Two branches from the root, a synthesis over both,
# and a node in module "mod" whose parent lives in _umbrella.
s = session(999, "aitasks/t999_topic.md")
create_node(s, "n000_init", [], "root", {}, "root proposal")
create_node(s, "n001_a", ["n000_init"], "a", {}, "a")
create_node(s, "n002_b", ["n000_init"], "b", {}, "b")
create_node(s, "n003_synth", ["n001_a", "n002_b"], "synth", {}, "synth")
create_node(s, "n004_mod", ["n003_synth"], "mod", {}, "mod", module_label="mod")
# A node whose proposal file is gone.
create_node(s, "n005_noprop", ["n000_init"], "noprop", {}, "x")
(s / "br_proposals" / "n005_noprop.md").unlink()

# 998: hostile values that would forge fields/records if emitted raw.
s = session(998, "aitasks/t998_x\nANCESTOR:forged|x.md")
create_node(s, "n000_init", [], "root", {}, "root")
create_node(s, "n001_bad", ["a|b", "c,d", "e\nANCESTOR:x|forged", "../../x", "n000_init"],
            "bad", {}, "bad")
# Valid node id, hostile module label, reached as an ancestor.
create_node(s, "n002_child", ["n003_labelled"], "child", {}, "child")
create_node(s, "n003_labelled", [], "labelled", {}, "l", module_label="m|DEPTH:9")

# Task-file allowlist cases.
session(997, ".git/config")
session(996, "aitasks/t998_other.md")
session(995, "aitasks/t995/t995_2_child.md")
session(994, "aitasks/t994_deleted.md")
s = session(993, "aitasks/t993_whatever.md")
(s / "br_session.yaml").write_text("task_file: [unclosed\n  : : bad", encoding="utf-8")
create_node(s, "n000_init", [], "root", {}, "root")
PY
)

# 995 is a child-shaped task number whose task file is the child file.
mv "$FIX/.aitask-crews/crew-brainstorm-995" "$FIX/.aitask-crews/crew-brainstorm-995_2"
sed -i.bak 's/^task_id: .*/task_id: 995_2/' "$FIX/.aitask-crews/crew-brainstorm-995_2/br_session.yaml"
rm -f "$FIX/.aitask-crews/crew-brainstorm-995_2/br_session.yaml.bak"

tree_digest() {
    (cd "$FIX/.aitask-crews" && find . -print | LC_ALL=C sort && \
        find . -type f -print0 | LC_ALL=C sort -z | xargs -0 cat) | cksum
}
DIGEST_BEFORE="$(tree_digest)"

# run_helper <args...> — sets OUT, ERR, RC; runs from the fixture root.
run_helper() {
    RC=0
    OUT="$(cd "$FIX" && "$HELPER" "$@" 2>"$TMP/err")" || RC=$?
    ERR="$(cat "$TMP/err")"
}

S=".aitask-crews/crew-brainstorm-999"

# --- Found node ---------------------------------------------------------------
run_helper 999 n003_synth
assert_eq "found node exits 0" "0" "$RC"
assert_eq "found node output" "SESSION_PATH:$S
TASK_FILE:aitasks/t999_topic.md
NODE:n003_synth|PROPOSAL:$S/br_proposals/n003_synth.md|META:$S/br_nodes/n003_synth.yaml|PARENTS:n001_a,n002_b" "$OUT"

# --- Unknown node / missing proposal -----------------------------------------
run_helper 999 n777_nope n005_noprop
assert_eq "unknown node exits 0" "0" "$RC"
assert_contains "unknown node NOT_FOUND" "NODE:n777_nope|PROPOSAL:NOT_FOUND|META:NOT_FOUND|PARENTS:" "$OUT"
assert_contains "missing proposal NOT_FOUND" "NODE:n005_noprop|PROPOSAL:NOT_FOUND|META:$S/br_nodes/n005_noprop.yaml|PARENTS:n000_init" "$OUT"

# --- Missing session ----------------------------------------------------------
run_helper 12345 n000_init
assert_eq "missing session exits 0" "0" "$RC"
assert_eq "missing session output" "SESSION_PATH:NOT_FOUND" "$OUT"

# --- All nodes ----------------------------------------------------------------
run_helper 999
assert_eq "all nodes exits 0" "0" "$RC"
assert_eq_trim "all nodes lists 6 NODE lines" "6" "$(printf '%s\n' "$OUT" | grep -c '^NODE:')"

# --- Lineage ------------------------------------------------------------------
run_helper --lineage 999 n004_mod
assert_eq "lineage exits 0" "0" "$RC"
assert_eq "lineage crosses modules and keeps both branches" "SESSION_PATH:$S
TASK_FILE:aitasks/t999_topic.md
NODE:n004_mod|PROPOSAL:$S/br_proposals/n004_mod.md|META:$S/br_nodes/n004_mod.yaml|PARENTS:n003_synth
ANCESTOR:n004_mod|n003_synth|DEPTH:1|MODULE:_umbrella|PARENTS:n001_a,n002_b|PROPOSAL:$S/br_proposals/n003_synth.md
ANCESTOR:n004_mod|n001_a|DEPTH:2|MODULE:_umbrella|PARENTS:n000_init|PROPOSAL:$S/br_proposals/n001_a.md
ANCESTOR:n004_mod|n002_b|DEPTH:2|MODULE:_umbrella|PARENTS:n000_init|PROPOSAL:$S/br_proposals/n002_b.md
ANCESTOR:n004_mod|n000_init|DEPTH:3|MODULE:_umbrella|PARENTS:|PROPOSAL:$S/br_proposals/n000_init.md" "$OUT"

# --- Invocation from a subdirectory ------------------------------------------
mkdir -p "$FIX/aitasks/sub"
RC=0
OUT="$(cd "$FIX/aitasks/sub" && ../../.aitask-scripts/aitask_brainstorm_context.sh 999 n001_a)" || RC=$?
assert_eq "subdir invocation exits 0" "0" "$RC"
assert_contains "subdir invocation resolves session" "SESSION_PATH:$S" "$OUT"
assert_contains "subdir invocation resolves node" "PROPOSAL:$S/br_proposals/n001_a.md" "$OUT"

# --- Malformed input (the one hard error) ------------------------------------
for bad_node in "../x" ".." "." "a/b" "a|b" "a,b" "$(printf 'a\nb')"; do
    run_helper 999 "$bad_node"
    assert_eq "malformed node id exits 2: $(printf '%q' "$bad_node")" "2" "$RC"
    assert_eq "malformed node id prints no stdout: $(printf '%q' "$bad_node")" "" "$OUT"
done
for bad_num in "12a" "1_" "../999" "" "_1"; do
    run_helper "$bad_num"
    assert_exit_nonzero_rc "bad task num rejected: '$bad_num'" "$RC"
    assert_eq "bad task num prints no stdout: '$bad_num'" "" "$OUT"
done
run_helper "12a"
assert_eq "bad task num exits 2" "2" "$RC"
run_helper --bogus 999
assert_exit_nonzero_rc "unknown option rejected" "$RC"

# --- Delimiter-bearing values never forge fields or records ------------------
run_helper --lineage 998 n001_bad n002_child
assert_eq "hostile session exits 0" "0" "$RC"
assert_eq "hostile task_file is INVALID" "TASK_FILE:INVALID" "$(printf '%s\n' "$OUT" | sed -n 2p)"
assert_not_contains "no forged record" "forged" "$OUT"
bad_keys="$(printf '%s\n' "$OUT" | grep -vcE '^(SESSION_PATH|TASK_FILE|NODE|ANCESTOR):' || true)"
assert_eq_trim "every line is a known record" "0" "$bad_keys"
bad_fields="$(printf '%s\n' "$OUT" | grep '^ANCESTOR:' | awk -F'|' 'NF != 6' | wc -l)"
assert_eq_trim "every ANCESTOR line has 6 fields" "0" "$bad_fields"
bad_node_fields="$(printf '%s\n' "$OUT" | grep '^NODE:' | awk -F'|' 'NF != 4' | wc -l)"
assert_eq_trim "every NODE line has 4 fields" "0" "$bad_node_fields"
assert_contains "unsafe parents encoded" "PARENTS:!INVALID,!INVALID,!INVALID,!INVALID,n000_init" "$OUT"
assert_contains "unsafe ancestor line" "ANCESTOR:n001_bad|!INVALID|DEPTH:1|MODULE:!MISSING|PARENTS:|PROPOSAL:NOT_FOUND" "$OUT"
assert_eq_trim "each unsafe ancestor reported once" "4" \
    "$(printf '%s\n' "$OUT" | grep -c '^ANCESTOR:n001_bad|!INVALID|')"
assert_contains "hostile module label encoded" "ANCESTOR:n002_child|n003_labelled|DEPTH:1|MODULE:!INVALID|PARENTS:|PROPOSAL:" "$OUT"

# --- Task-file allowlist ------------------------------------------------------
run_helper 997
assert_eq "existing .git/config is INVALID" "TASK_FILE:INVALID" "$(printf '%s\n' "$OUT" | sed -n 2p)"
run_helper 996
assert_eq "another task's file is INVALID" "TASK_FILE:INVALID" "$(printf '%s\n' "$OUT" | sed -n 2p)"
run_helper 995_2
assert_eq "child task file accepted" "TASK_FILE:aitasks/t995/t995_2_child.md" "$(printf '%s\n' "$OUT" | sed -n 2p)"
run_helper 994
assert_eq "allowed shape but deleted is NOT_FOUND" "TASK_FILE:NOT_FOUND" "$(printf '%s\n' "$OUT" | sed -n 2p)"
run_helper 999
assert_eq "own task file accepted" "TASK_FILE:aitasks/t999_topic.md" "$(printf '%s\n' "$OUT" | sed -n 2p)"

# --- Malformed br_session.yaml -----------------------------------------------
run_helper 993
assert_eq "malformed session yaml exits 0" "0" "$RC"
assert_eq "malformed session yaml task file NOT_FOUND" "TASK_FILE:NOT_FOUND" "$(printf '%s\n' "$OUT" | sed -n 2p)"
assert_contains "malformed session yaml still resolves nodes" "NODE:n000_init|" "$OUT"
assert_not_contains "malformed session yaml: no traceback" "Traceback" "$ERR"

# --- Read-only proof ----------------------------------------------------------
assert_eq "crew trees unchanged by every invocation" "$DIGEST_BEFORE" "$(tree_digest)"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

if [[ "$FAIL" -gt 0 ]]; then
    echo "SOME TESTS FAILED"
    exit 1
else
    echo "ALL TESTS PASSED"
fi
