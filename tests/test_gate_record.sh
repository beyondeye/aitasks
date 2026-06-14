#!/usr/bin/env bash
# test_gate_record.sh - Tests for aitask_gate_record.sh (t635_2).
#
# aitask_gate_record.sh is the thin best-effort wrapper task-workflow uses to
# record a checkpoint into the gate ledger AND persist it (commit path-scoped +
# best-effort push) so the gate state is visible from every PC. These tests run
# against a legacy-mode temp git repo (no .aitask-data → task_git/task_push use
# plain git in CWD):
#   - happy path: appends the gate-run block, status derives pass, and the
#     change is committed in a path-scoped "ait: Record <gate> gate" commit,
#   - the commit touches ONLY the task file,
#   - best-effort: a bad append (invalid status) never crashes the wrapper and
#     creates no commit,
#   - no remote configured → the push step no-ops cleanly (exit 0),
#   - --help prints usage.
#
# Run: bash tests/test_gate_record.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

RECORD="$PROJECT_DIR/.aitask-scripts/aitask_gate_record.sh"
GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_gate_record_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# --- Legacy-mode git repo fixture (no .aitask-data → plain git in CWD) ---
git -C "$TMP" init -q
git -C "$TMP" config user.email "test@example.com"
git -C "$TMP" config user.name "Gate Record Test"

mkdir -p "$TMP/aitasks/metadata"
cat > "$TMP/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  plan_approved:
    type: human
    description: "Implementation plan reviewed and approved before coding begins"
EOF

cat > "$TMP/aitasks/t77_demo.md" <<'EOF'
---
priority: high
status: Implementing
---

## Context
Body for t77.
EOF

git -C "$TMP" add -A
git -C "$TMP" commit -qm "seed task fixture"

# Helper: run the wrapper from inside the repo with a relative TASK_DIR
# (exactly how `ait` invokes helper scripts after cd'ing to the repo root).
run_record() {
    ( cd "$TMP" && TASK_DIR="aitasks" "$RECORD" "$@" )
}
run_status() {
    ( cd "$TMP" && TASK_DIR="aitasks" "$GATE" status "$@" )
}

# ============================================================
echo "--- happy path: append + path-scoped commit ---"
# ============================================================
run_record 77 plan_approved pass type=human
rc=$?
assert_eq "wrapper exits 0 on success" "0" "$rc"

file_content="$(cat "$TMP/aitasks/t77_demo.md")"
assert_contains "gate-run block appended" "> **✅ gate:plan_approved**" "$file_content"
assert_contains "status recorded pass" "status=pass" "$file_content"
assert_contains "type=human recorded" "type=human" "$file_content"

status_out="$(run_status 77)"
assert_contains "status derives plan_approved: pass" "plan_approved: pass" "$status_out"

# The append must have been committed, path-scoped, with the ait: message.
head_msg="$(git -C "$TMP" log -1 --pretty=%s)"
assert_eq "commit subject is the ait: record message" \
    "ait: Record plan_approved gate for t77" "$head_msg"

changed="$(git -C "$TMP" show --name-only --pretty=format: HEAD | grep -v '^$' || true)"
assert_eq "commit touches ONLY the task file" "aitasks/t77_demo.md" "$changed"

# Working tree is clean (nothing left uncommitted from the recording).
porcelain="$(git -C "$TMP" status --porcelain)"
assert_eq "working tree clean after record" "" "$porcelain"

# ============================================================
echo "--- best-effort: invalid status never crashes, no commit ---"
# ============================================================
commits_before="$(git -C "$TMP" rev-list --count HEAD)"
run_record 77 plan_approved notastatus >/dev/null 2>&1
rc=$?
assert_eq "wrapper exits 0 even when append fails" "0" "$rc"
commits_after="$(git -C "$TMP" rev-list --count HEAD)"
assert_eq "no commit created on failed append" "$commits_before" "$commits_after"

# ============================================================
echo "--- no remote configured: push step no-ops (already exit 0 above) ---"
# ============================================================
# The happy-path run had no remote; reaching here with exit 0 proves task_push
# was best-effort. Assert explicitly that there is no remote in the fixture.
remotes="$( cd "$TMP" && git remote )"
assert_eq "fixture has no remote (push was a no-op)" "" "$remotes"

# ============================================================
echo "--- --help prints usage and exits 0 ---"
# ============================================================
help_out="$("$RECORD" --help)"
rc=$?
assert_eq "--help exits 0" "0" "$rc"
assert_contains "--help shows usage" "Usage: aitask_gate_record.sh" "$help_out"

# ============================================================
echo ""
echo "========================================"
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================"
[[ "$FAIL" -eq 0 ]]
