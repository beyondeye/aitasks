#!/usr/bin/env bash
# test_gates_reference_drift.sh - Drift guard for the canonical gate registry
# reference (t1147).
#
# .aitask-scripts/gates_reference.yaml is the single source of truth for the
# shipped gate registry (it reaches installed projects because .aitask-scripts/
# is framework-synced, unlike seed/). The framework's own live runtime registry
# (aitasks/metadata/gates.yaml on the aitask-data branch) must stay
# field-identical to it — this test fails when the two diverge, in either
# direction, so a gate change that updates one copy and forgets the other never
# ships stale (the exact failure class behind t1147).
#
# Part 1 (structural, always runs): every machine gate whose `kind` is not
#   `procedure` must carry a non-empty `verifier`, and the full framework gate
#   set must be present. This is what a stale pre-verifier copy violates.
# Part 2 (parity, non-optional in the framework repo): parse the live registry
#   from the aitask-data BRANCH REF (`git show aitask-data:...`) — no worktree
#   checkout needed — and assert semantic equality with the reference across
#   ALL fields parsed by gate_ledger.read_registry(). If neither the branch ref
#   nor a legacy checked-out registry exists, this FAILS loudly as a validation
#   gap (never a silent pass). Downstream projects don't run this
#   framework-internal test.
#
# Run: bash tests/test_gates_reference_drift.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

REFERENCE="$PROJECT_DIR/.aitask-scripts/gates_reference.yaml"

# The registry parser is Python (lib/gate_ledger.py read_registry — the
# canonical stdlib parser). A drift guard that silently skips is a silent
# drift channel, so a missing interpreter is a hard failure here.
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"
if [[ -z "$PY" ]]; then
    echo "FAIL: no python interpreter available — drift guard cannot run (validation gap)"
    exit 1
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_gates_ref_drift_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# =====================================================================
echo "--- Part 1: structural checks on the reference (always run) ---"
# =====================================================================

assert_eq "reference file exists" "yes" "$([[ -f "$REFERENCE" ]] && echo yes || echo no)"

structural_out="$("$PY" - "$REFERENCE" <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "lib"))
from gate_ledger import read_registry

reg = read_registry(sys.argv[1])

expected_gates = {
    "plan_approved", "risk_evaluated", "build_verified", "tests_pass",
    "lint", "docs_updated", "review_approved", "merge_approved",
}
missing = expected_gates - set(reg)
if missing:
    print("MISSING_GATES:%s" % ",".join(sorted(missing)))

# Every command-driven machine gate must have a verifier — the t1147 failure
# class is a machine gate shipping with no verifier mapping.
for name, meta in sorted(reg.items()):
    if meta["type"] == "machine" and meta["kind"] != "procedure":
        if not meta["verifier"]:
            print("NO_VERIFIER:%s" % name)

# The async human gates must keep their signal transport.
for name in ("review_approved", "merge_approved"):
    if name in reg and (not reg[name]["signal"] or not reg[name]["signal_target"]):
        print("NO_SIGNAL:%s" % name)

print("STRUCTURAL_DONE")
PYEOF
)"

assert_eq "structural scan completed" "STRUCTURAL_DONE" "$(printf '%s\n' "$structural_out" | tail -1)"
assert_eq "all framework gates present" "" "$(printf '%s\n' "$structural_out" | grep '^MISSING_GATES:' || true)"
assert_eq "every command machine gate has a verifier" "" "$(printf '%s\n' "$structural_out" | grep '^NO_VERIFIER:' || true)"
assert_eq "async human gates keep signal transport" "" "$(printf '%s\n' "$structural_out" | grep '^NO_SIGNAL:' || true)"

# =====================================================================
echo "--- Part 2: field-complete parity with the live registry ---"
# =====================================================================

# Resolve the live registry WITHOUT requiring a .aitask-data worktree: read it
# from the aitask-data branch ref. Legacy mode (registry tracked on the current
# branch) falls back to the checked-out file. No source at all = loud failure.
LIVE_FILE="$TMP/live_gates.yaml"
live_source=""
if git -C "$PROJECT_DIR" rev-parse --verify --quiet aitask-data >/dev/null; then
    if git -C "$PROJECT_DIR" show aitask-data:aitasks/metadata/gates.yaml > "$LIVE_FILE" 2>/dev/null; then
        live_source="branch-ref"
    fi
fi
if [[ -z "$live_source" && -f "$PROJECT_DIR/aitasks/metadata/gates.yaml" ]]; then
    cp "$PROJECT_DIR/aitasks/metadata/gates.yaml" "$LIVE_FILE"
    live_source="legacy-checkout"
fi

if [[ -z "$live_source" ]]; then
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: no live registry source found (no aitask-data branch ref, no aitasks/metadata/gates.yaml)"
    echo "  The parity guard could not run — this is a validation gap, not a pass."
else
    echo "live registry source: $live_source"
    parity_out="$("$PY" - "$REFERENCE" "$LIVE_FILE" <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "lib"))
from gate_ledger import read_registry

ref = read_registry(sys.argv[1])
live = read_registry(sys.argv[2])

drift = False
for name in sorted(set(ref) | set(live)):
    if name not in ref:
        print("ONLY_IN_LIVE:%s" % name); drift = True
        continue
    if name not in live:
        print("ONLY_IN_REFERENCE:%s" % name); drift = True
        continue
    for field in sorted(set(ref[name]) | set(live[name])):
        rv, lv = ref[name].get(field), live[name].get(field)
        if rv != lv:
            print("FIELD_DRIFT:%s.%s reference=%r live=%r" % (name, field, rv, lv))
            drift = True
print("DRIFT" if drift else "IN_SYNC")
PYEOF
)"
    assert_eq "reference == live registry (all fields)" "IN_SYNC" "$(printf '%s\n' "$parity_out" | tail -1)"
    if printf '%s\n' "$parity_out" | grep -qv '^IN_SYNC$'; then
        printf '%s\n' "$parity_out" | grep -v '^IN_SYNC$' | sed 's/^/  /'
    fi
fi

# =====================================================================
echo "--- Part 3: packaging + consumer wiring ---"
# =====================================================================

# The release artifact ships tracked files only — an untracked reference would
# pass local runs while the packaged install silently omits it (t1147 C5).
ref_porcelain="$(git -C "$PROJECT_DIR" status --porcelain -- .aitask-scripts/gates_reference.yaml 2>/dev/null || true)"
assert_eq "reference is git-tracked or staged (ships in the artifact)" "" \
    "$(printf '%s\n' "$ref_porcelain" | grep '^??' || true)"

# Consumer wiring: both install paths must read the canonical reference, and
# neither may still point at the removed seed/gates.yaml.
assert_eq "install.sh reads the canonical reference" "yes" \
    "$(grep -qF '.aitask-scripts/gates_reference.yaml' "$PROJECT_DIR/install.sh" && echo yes || echo no)"
assert_eq "aitask_setup.sh reads the canonical reference" "yes" \
    "$(grep -qF '.aitask-scripts/gates_reference.yaml' "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" && echo yes || echo no)"
assert_eq "no consumer still reads seed/gates.yaml" "" \
    "$(grep -l 'seed/gates\.yaml' "$PROJECT_DIR/install.sh" "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" 2>/dev/null || true)"

# =====================================================================
echo ""
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
exit 0
