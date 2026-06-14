#!/usr/bin/env bash
# test_dependency_unblock.sh - Dependency-unblock semantics for gated tasks (t635_3).
#
# Covers:
#   1. The decision (gate_ledger.py / aitask_gate.sh deps-unblock):
#      SATISFIED | BLOCKED:<csv> | NO_GATES, registry blocks_dependents flag,
#      per-task also_blocks_dependents augmentation.
#   2. aitask_ls.sh blocking integration: a gated upstream whose required gates
#      all pass unblocks its dependents (before archival) while a non-required
#      gate still pends; an ungated upstream blocks while active (today's behavior).
#
# Durability of the also_blocks_dependents field across update/create/fold lives
# in test_gate_frontmatter_roundtrip.sh.
#
# Run: bash tests/test_dependency_unblock.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
LS="$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"
PY="$PROJECT_DIR/.aitask-scripts/lib/gate_ledger.py"
PYTHON="$(command -v python3 || command -v python)"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_dep_unblock_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# Fixture registry: integration gates block dependents, pre-code ones do not.
REG="$TMP/gates.yaml"
cat > "$REG" <<'EOF'
gates:
  plan_approved:
    type: human
    description: "plan"
    blocks_dependents: false
  build_verified:
    type: machine
    description: "build"
    blocks_dependents: true
  review_approved:
    type: human
    description: "review"
    blocks_dependents: true
EOF

# Helper: write a task file with a gates: line and optional gate-run markers.
# write_task <path> <gates-csv-or-empty> <also-csv-or-empty> <marker-lines...>
write_task() {
    local path="$1" gates="$2" also="$3"; shift 3
    {
        printf '%s\n' "---" "priority: high" "effort: medium" "depends: []" \
            "issue_type: feature" "status: Implementing"
        [[ -n "$gates" ]] && printf 'gates: [%s]\n' "$gates"
        [[ -n "$also" ]] && printf 'also_blocks_dependents: [%s]\n' "$also"
        printf '%s\n' "---" "" "## Gate Runs"
        for m in "$@"; do printf '%s\n' "$m"; done
    } > "$path"
}

mark() { # mark <gate> <status> -> a marker line
    printf '> **icon gate:%s** run=2026-01-01T00:00:00Z status=%s attempt=1' "$1" "$2"
}

# =====================================================================
echo "--- Part 1: deps-unblock decision (gate_ledger.py) ---"
# =====================================================================

# (a) required gate still pending -> BLOCKED
write_task "$TMP/a.md" "plan_approved, build_verified" "" "$(mark plan_approved pass)"
assert_eq "required build_verified pending -> BLOCKED" "BLOCKED:build_verified" \
    "$("$PYTHON" "$PY" deps-unblock "$TMP/a.md" "$REG")"

# (b) all required pass -> SATISFIED
write_task "$TMP/b.md" "plan_approved, build_verified" "" \
    "$(mark plan_approved pass)" "$(mark build_verified pass)"
assert_eq "all required pass -> SATISFIED" "SATISFIED" \
    "$("$PYTHON" "$PY" deps-unblock "$TMP/b.md" "$REG")"

# (c) only a non-blocking gate declared -> NO_GATES
write_task "$TMP/c.md" "plan_approved" "" "$(mark plan_approved pass)"
assert_eq "only non-blocking gate declared -> NO_GATES" "NO_GATES" \
    "$("$PYTHON" "$PY" deps-unblock "$TMP/c.md" "$REG")"

# (d) no gates field at all -> NO_GATES
write_task "$TMP/d.md" "" ""
assert_eq "no gates field -> NO_GATES" "NO_GATES" \
    "$("$PYTHON" "$PY" deps-unblock "$TMP/d.md" "$REG")"

# (e) per-task also_blocks_dependents adds a requirement
write_task "$TMP/e.md" "build_verified" "docs_updated" "$(mark build_verified pass)"
assert_eq "also_blocks_dependents adds docs_updated -> BLOCKED" "BLOCKED:docs_updated" \
    "$("$PYTHON" "$PY" deps-unblock "$TMP/e.md" "$REG")"
write_task "$TMP/e2.md" "build_verified" "docs_updated" \
    "$(mark build_verified pass)" "$(mark docs_updated pass)"
assert_eq "also_blocks_dependents satisfied -> SATISFIED" "SATISFIED" \
    "$("$PYTHON" "$PY" deps-unblock "$TMP/e2.md" "$REG")"

# (f) the bash surface resolves + delegates identically
mkdir -p "$TMP/repo/aitasks/metadata"
cp "$REG" "$TMP/repo/aitasks/metadata/gates.yaml"
write_task "$TMP/repo/aitasks/t90_sat.md" "plan_approved, build_verified" "" \
    "$(mark plan_approved pass)" "$(mark build_verified pass)"
out=$( cd "$TMP/repo" && TASK_DIR=aitasks "$GATE" deps-unblock 90 )
assert_eq "aitask_gate.sh deps-unblock matches python path" "SATISFIED" "$out"

# =====================================================================
echo "--- Part 2: aitask_ls.sh blocking integration ---"
# =====================================================================
LREPO="$TMP/lsrepo"
mkdir -p "$LREPO/aitasks/metadata"
cp "$PROJECT_DIR/seed/gates.yaml" "$LREPO/aitasks/metadata/gates.yaml"
: > "$LREPO/aitasks/metadata/labels.txt"
printf 'feature\nbug\nchore\n' > "$LREPO/aitasks/metadata/task_types.txt"

dep_task() { # dep_task <path> <depends-id>
    cat > "$1" <<EOF
---
priority: high
effort: medium
depends: [$2]
issue_type: feature
status: Ready
---
dependent
EOF
}

# Scenario A: gated upstream with a required gate still pending -> dependent blocked.
write_task "$LREPO/aitasks/t10_up_blocked.md" "build_verified, review_approved" "" \
    "$(mark build_verified pass)"
dep_task "$LREPO/aitasks/t20_dep_a.md" 10

# Scenario B: gated upstream, all required pass, a non-required gate pending ->
# dependent UNBLOCKED (the regression fix).
write_task "$LREPO/aitasks/t11_up_satisfied.md" "plan_approved, build_verified, review_approved" "" \
    "$(mark plan_approved pending)" "$(mark build_verified pass)" "$(mark review_approved pass)"
dep_task "$LREPO/aitasks/t21_dep_b.md" 11

# Scenario C: ungated upstream still active -> dependent blocked (today's behavior).
cat > "$LREPO/aitasks/t12_up_ungated.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
---
ungated upstream
EOF
dep_task "$LREPO/aitasks/t22_dep_c.md" 12

ls_out=$( cd "$LREPO" && TASK_DIR=aitasks "$LS" -v 99 2>&1 )
line_a=$(printf '%s\n' "$ls_out" | grep '^t20_dep_a.md' || true)
line_b=$(printf '%s\n' "$ls_out" | grep '^t21_dep_b.md' || true)
line_c=$(printf '%s\n' "$ls_out" | grep '^t22_dep_c.md' || true)

assert_contains "gated upstream, required pending -> dependent blocked" \
    "Blocked (by 10)" "$line_a"
assert_not_contains "gated upstream, required all pass -> dependent UNBLOCKED" \
    "Blocked" "$line_b"
assert_contains "ungated active upstream -> dependent blocked (control)" \
    "Blocked (by 12)" "$line_c"

# Zero-overhead guard: a repo with no gated files produces no candidates.
NREPO="$TMP/nogates"
mkdir -p "$NREPO/aitasks/metadata"
: > "$NREPO/aitasks/metadata/labels.txt"
printf 'feature\n' > "$NREPO/aitasks/metadata/task_types.txt"
cat > "$NREPO/aitasks/t30_plain.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
---
plain
EOF
n_out=$( cd "$NREPO" && TASK_DIR=aitasks "$LS" -v 9 2>&1 )
assert_contains "ungated repo lists normally" "t30_plain.md" "$n_out"

# --- syntax checks ---
TOTAL=$((TOTAL + 1))
if bash -n "$GATE" && bash -n "$LS"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: syntax check"
fi

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
