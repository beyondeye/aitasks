#!/usr/bin/env bash
# test_deps_unblock_batch.sh - Batched dependency-unblock decision (t1472).
#
# `ait ls` used to spawn one `aitask_gate.sh deps-unblock` process per gated
# active task (190 of them, ~46ms each, 9.7s of an 18.9s run on the framework
# repo). The batch verb decides the whole candidate list in ONE process, one
# registry parse, at most one code_digest(). This file pins that the collapse
# changed NOTHING about the decision, and that the three degradation boundaries
# batching introduces all fail safe.
#
# Cases (labelled T<n> so they cannot be confused with the numbered checklists
# in the plan / other test files):
#   T1  decision parity with the per-task verb over every decision shape
#   T2  negative control — the parity comparison is load-bearing, not vacuous
#   T3  t1416 stale-witness re-validation survives batching
#   T4  digest amortization is exact (1 resolve per batch, 0 when unsigned)
#   T5  per-file isolation + the diagnostic NAMES the offending path
#   T6  registry setup failure is total, diagnosable, and exits 1
#   T7  edge cases (empty stdin, blank lines)
#   T8  bash surface parity, including exit-status propagation
#   T9  aitask_ls.sh integration unchanged
#   T10 a FAILING digest provider fails safe for EVERY signed row
#
# Per-task-verb semantics themselves live in test_dependency_unblock.sh; the
# stale-witness contract across other surfaces lives in
# test_gate_stale_witness_parity.sh.
#
# Run: bash tests/test_deps_unblock_batch.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
LS="$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"
PY_MOD="$PROJECT_DIR/.aitask-scripts/lib/gate_ledger.py"
PYTHON="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; \
          resolve_python 2>/dev/null || command -v python3 || command -v python )"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_dub_batch_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# `grep` may be shadowed by a parallel implementation (ugrep) whose -l output
# order is non-deterministic. Everything below feeds EXPLICIT path lists rather
# than a grep result, so ordering assertions test the verb, not the environment.

# --- fixtures ---------------------------------------------------------------

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
  docs_updated:
    type: machine
    description: "docs"
    blocks_dependents: false
EOF

# T2's mutated registry: build_verified no longer blocks dependents.
REG_FLIPPED="$TMP/gates_flipped.yaml"
sed 's/blocks_dependents: true/blocks_dependents: false/' "$REG" > "$REG_FLIPPED"

# write_task <path> <gates-csv|""> <also-csv|""> <marker-lines...>
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

mark() { printf '> **icon gate:%s** run=2026-01-01T00:00:00Z status=%s attempt=1' "$1" "$2"; }

batch() {  # batch <registry> < paths  -> rows on stdout, status preserved
    "$PYTHON" "$PY_MOD" deps-unblock-batch "$1"
}

# One fixture per decision shape.
F=()
write_task "$TMP/t10_ungated.md"      ""                              ""              # NO_GATES
F+=("$TMP/t10_ungated.md")
write_task "$TMP/t11_nonblocking.md"  "plan_approved"                 "" "$(mark plan_approved pass)"
F+=("$TMP/t11_nonblocking.md")        # gated, but no blocks_dependents gate -> NO_GATES
write_task "$TMP/t12_pending.md"      "build_verified"                ""              # BLOCKED
F+=("$TMP/t12_pending.md")
write_task "$TMP/t13_satisfied.md"    "plan_approved, build_verified" "" \
    "$(mark plan_approved pass)" "$(mark build_verified pass)"                        # SATISFIED
F+=("$TMP/t13_satisfied.md")
write_task "$TMP/t14_also_pending.md" "build_verified"   "docs_updated" "$(mark build_verified pass)"
F+=("$TMP/t14_also_pending.md")       # also_blocks_dependents adds docs_updated -> BLOCKED
write_task "$TMP/t15_also_ok.md"      "build_verified"   "docs_updated" \
    "$(mark build_verified pass)" "$(mark docs_updated pass)"                          # SATISFIED
F+=("$TMP/t15_also_ok.md")

# =====================================================================
echo "--- T1: decision parity with the per-task verb (all shapes) ---"
# =====================================================================

printf '%s\n' "${F[@]}" | batch "$REG" > "$TMP/batch.out" 2>/dev/null
batch_rc=$?

: > "$TMP/pertask.out"
for f in "${F[@]}"; do
    printf '%s\t%s\n' "$("$PYTHON" "$PY_MOD" deps-unblock "$f" "$REG")" "$f" >> "$TMP/pertask.out"
done

assert_eq "T1 batch exits 0" "0" "$batch_rc"
assert_eq "T1 one row per input path" "${#F[@]}" "$(wc -l < "$TMP/batch.out" | tr -d ' ')"
assert_eq "T1 batch == per-task, order included" "" "$(diff "$TMP/pertask.out" "$TMP/batch.out")"

# Pin the shapes themselves, so T1 cannot pass by both sides being equally wrong.
assert_eq "T1 shapes" \
"NO_GATES
NO_GATES
BLOCKED:build_verified
SATISFIED
BLOCKED:docs_updated
SATISFIED" "$(cut -f1 "$TMP/batch.out")"

# The echoed path must be the input path verbatim (aitask_ls.sh keys off it).
assert_eq "T1 paths round-trip in input order" "$(printf '%s\n' "${F[@]}")" \
    "$(cut -f2 "$TMP/batch.out")"

# =====================================================================
echo "--- T2: negative control (the comparison is load-bearing) ---"
# =====================================================================
# ONE mutation: build_verified stops blocking dependents. If the vectors still
# matched, T1 would be comparing something that cannot vary — a passing negative
# control means the assertion is wrong.

printf '%s\n' "${F[@]}" | batch "$REG_FLIPPED" > "$TMP/batch_flipped.out" 2>/dev/null
TOTAL=$((TOTAL + 1))
if diff -q "$TMP/batch.out" "$TMP/batch_flipped.out" >/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: T2 negative control did NOT differ — T1's comparison is vacuous"
else
    PASS=$((PASS + 1))
fi
assert_contains "T2 flipped registry drops the blocking requirement" "NO_GATES" \
    "$(sed -n '3p' "$TMP/batch_flipped.out")"

# =====================================================================
echo "--- T3/T4/T10: signed-witness fixtures (git repo) ---"
# =====================================================================
# Mirrors tests/test_gate_stale_witness_parity.sh's fixture: a task whose only
# active gate is a `blocks_dependents: true` HUMAN gate, already `pass`, with a
# gitignored witness dir so signing does not move the code digest.

SREPO="$TMP/signed"
mkdir -p "$SREPO/aitasks/metadata" "$SREPO/sig"
( cd "$SREPO" && git init -q && git config user.email t@t && git config user.name t \
  && echo seed > code.txt && printf 'sig/\n' > .gitignore \
  && git add -A && git commit -qm init ) >/dev/null 2>&1

cat > "$SREPO/aitasks/metadata/gates.yaml" <<EOF
gates:
  review:
    type: human
    blocks_dependents: true
    signal_target: "$SREPO/sig/<task-id>-review.signed"
  build:
    type: machine
    blocks_dependents: true
EOF
SREG="$SREPO/aitasks/metadata/gates.yaml"
# `build` is deliberately MACHINE-typed: stale_signed_gates' pre-filter only
# considers `type: human` gates, so a task declaring only `build` never resolves
# the digest. That makes it a control row whose decision is provably independent
# of the digest provider — and SATISFIED, which is distinguishable from the
# NO_GATES an isolated/failed row produces.

signed_task() {  # signed_task <id>
    cat > "$SREPO/aitasks/t${1}_x.md" <<EOF
---
status: Implementing
gates: [review]
active_gates: [review]
---
Body.

## Gate Runs

> **✅ gate:review** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human
EOF
}
sign() { printf 'signer=tester\ncode_digest=%s\n' "$2" > "$SREPO/sig/t$1-review.signed"; }

for id in 91 92 93; do signed_task "$id"; done
# An unsigned gated task: its decision must never depend on the digest, and must
# be SATISFIED (not NO_GATES) so it cannot be confused with an isolated row.
write_task "$SREPO/aitasks/t94_unsigned.md" "build" "" "$(mark build pass)"

CUR_DIGEST="$( cd "$SREPO" && "$PYTHON" -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
import gate_ledger; print(gate_ledger.code_digest() or '')
" )"

# --- T3: a STALE signature blocks, in batch exactly as per-task ---
for id in 91 92 93; do sign "$id" "deadbeefdeadbeef"; done   # signed against other code
S_PATHS="$SREPO/aitasks/t91_x.md
$SREPO/aitasks/t92_x.md
$SREPO/aitasks/t93_x.md"

stale_batch=$( cd "$SREPO" && printf '%s\n' "$S_PATHS" | batch "$SREG" 2>/dev/null )
stale_pertask=$( cd "$SREPO" && "$PYTHON" "$PY_MOD" deps-unblock "$SREPO/aitasks/t91_x.md" "$SREG" )
assert_eq "T3 stale witness blocks in batch" \
    "BLOCKED:review" "$(printf '%s\n' "$stale_batch" | sed -n '1p' | cut -f1)"
assert_eq "T3 batch agrees with per-task on a stale witness" \
    "$stale_pertask" "$(printf '%s\n' "$stale_batch" | sed -n '1p' | cut -f1)"

# A FRESH signature must release — otherwise T3 would pass on any always-blocked bug.
for id in 91 92 93; do sign "$id" "$CUR_DIGEST"; done
fresh_batch=$( cd "$SREPO" && printf '%s\n' "$S_PATHS" | batch "$SREG" 2>/dev/null )
assert_eq "T3 fresh witness releases (contrast case)" \
    "SATISFIED" "$(printf '%s\n' "$fresh_batch" | sed -n '1p' | cut -f1)"

# =====================================================================
echo "--- T4: digest amortization is exact ---"
# =====================================================================
# code_digest() itself issues 3 git commands (rev-parse / diff / ls-files), so
# "git was called once" is NOT the assertion. Count resolutions of the digest
# CHANNEL instead, through the documented `current_digest` callable seam.

amort=$( cd "$SREPO" && GL_LIB="$PROJECT_DIR/.aitask-scripts/lib" "$PYTHON" - "$SREG" "$SREPO" <<'PY'
import os, sys
sys.path.insert(0, os.environ['GL_LIB'])
import gate_ledger

reg, root = sys.argv[1], sys.argv[2]
calls = {"n": 0}
def provider():
    calls["n"] += 1
    return gate_ledger.code_digest()

signed = [f"{root}/aitasks/t{i}_x.md" for i in (91, 92, 93)]
rows, err = gate_ledger.dependents_status_batch(signed, reg, current_digest=provider)
print(f"signed_calls={calls['n']}")
print(f"signed_decisions={','.join(r[1] for r in rows)}")

calls["n"] = 0
unsigned = [f"{root}/aitasks/t94_unsigned.md"] * 3
gate_ledger.dependents_status_batch(unsigned, reg, current_digest=provider)
print(f"unsigned_calls={calls['n']}")
PY
)
assert_contains "T4 3 signed tasks resolve the digest exactly ONCE" \
    "signed_calls=1" "$amort"
assert_contains "T4 unsigned tasks never resolve it (no-git pre-filter)" \
    "unsigned_calls=0" "$amort"
assert_contains "T4 amortization did not change the decision" \
    "signed_decisions=SATISFIED,SATISFIED,SATISFIED" "$amort"

# =====================================================================
echo "--- T10: a FAILING digest provider fails safe for EVERY signed row ---"
# =====================================================================
# The regression test for the _DigestMemo hazard: memoizing a failed provider as
# a bare None would make witness_state read it as `unstamped` = ACCEPT, so signed
# rows 2..N would return SATISFIED on a witness nobody re-validated. The provider
# below would return a VALID digest if called again — that is what makes the
# broken behavior visible instead of indistinguishable from a correct fallback.

t10=$( cd "$SREPO" && GL_LIB="$PROJECT_DIR/.aitask-scripts/lib" "$PYTHON" - "$SREG" "$SREPO" <<'PY'
import os, sys, io, contextlib
sys.path.insert(0, os.environ['GL_LIB'])
import gate_ledger

reg, root = sys.argv[1], sys.argv[2]
calls = {"n": 0}
def flaky():
    calls["n"] += 1
    if calls["n"] == 1:
        raise RuntimeError("digest provider exploded")
    return gate_ledger.code_digest()      # a VALID digest, if ever retried

paths = [f"{root}/aitasks/t{i}_x.md" for i in (91, 92, 93)] + \
        [f"{root}/aitasks/t94_unsigned.md"]
err = io.StringIO()
with contextlib.redirect_stderr(err):
    rows, setup_error = gate_ledger.dependents_status_batch(
        paths, reg, current_digest=flaky)
print(f"provider_calls={calls['n']}")
print(f"decisions={','.join(r[1] for r in rows)}")
print(f"setup_error={setup_error is not None}")
print(f"diagnostics={len([l for l in err.getvalue().splitlines() if l.strip()])}")
PY
)
assert_contains "T10 all THREE signed rows fall back, not just the first" \
    "decisions=NO_GATES,NO_GATES,NO_GATES,SATISFIED" "$t10"
assert_contains "T10 the failed provider is never retried" "provider_calls=1" "$t10"
assert_contains "T10 one diagnostic per failed signed row" "diagnostics=3" "$t10"
assert_contains "T10 a provider failure is NOT a setup failure" "setup_error=False" "$t10"

# =====================================================================
echo "--- T5: per-file isolation, and the diagnostic names the path ---"
# =====================================================================

MISSING="$TMP/does_not_exist_t99.md"
iso_out=$( printf '%s\n%s\n%s\n' "$TMP/t13_satisfied.md" "$MISSING" "$TMP/t12_pending.md" \
           | batch "$REG" 2>"$TMP/iso.err" )
iso_rc=$?
assert_exit_zero_rc "T5 a bad row does not fail the batch" "$iso_rc"
assert_eq "T5 good rows still decided, bad row isolated" \
"SATISFIED
NO_GATES
BLOCKED:build_verified" "$(printf '%s\n' "$iso_out" | cut -f1)"
assert_contains "T5 diagnostic NAMES the offending path" "$MISSING" "$(cat "$TMP/iso.err")"
assert_eq "T5 exactly one diagnostic" "1" \
    "$(grep -c . "$TMP/iso.err" | tr -d ' ')"

# =====================================================================
echo "--- T6: registry setup failure is total, diagnosable, exit 1 ---"
# =====================================================================
# A DIRECTORY passes read_registry's os.path.exists guard and then raises in
# open() — unlike a missing file, which correctly returns {}. This is the case
# that runs OUTSIDE every per-file guard.

setup_out=$( printf '%s\n%s\n' "$TMP/t13_satisfied.md" "$TMP/t12_pending.md" \
             | batch "$TMP" 2>"$TMP/setup.err" )
setup_rc=$?
assert_exit_nonzero_rc "T6 setup failure exits nonzero" "$setup_rc"
assert_eq "T6 exit status is exactly 1" "1" "$setup_rc"
assert_eq "T6 every input row still gets a row" "2" \
    "$(printf '%s\n' "$setup_out" | grep -c . | tr -d ' ')"
assert_eq "T6 all rows are a conservative NO_GATES" \
"NO_GATES
NO_GATES" "$(printf '%s\n' "$setup_out" | cut -f1)"
assert_eq "T6 paths still round-trip in input order" \
"$TMP/t13_satisfied.md
$TMP/t12_pending.md" "$(printf '%s\n' "$setup_out" | cut -f2)"
assert_eq "T6 ONE diagnostic, not one per row" "1" \
    "$(grep -c . "$TMP/setup.err" | tr -d ' ')"
assert_contains "T6 diagnostic names the registry" "$TMP" "$(cat "$TMP/setup.err")"

# A MISSING registry is NOT a setup failure — read_registry returns {}.
miss_out=$( printf '%s\n' "$TMP/t13_satisfied.md" | batch "$TMP/absent.yaml" 2>/dev/null )
miss_rc=$?
assert_exit_zero_rc "T6 missing registry is not a setup failure" "$miss_rc"
assert_eq "T6 missing registry decides against an empty registry" "NO_GATES" \
    "$(printf '%s\n' "$miss_out" | cut -f1)"

# =====================================================================
echo "--- T7: edge cases ---"
# =====================================================================

empty_out=$( printf '' | batch "$REG" 2>/dev/null ); empty_rc=$?
assert_exit_zero_rc "T7 empty stdin exits 0" "$empty_rc"
assert_eq "T7 empty stdin produces no rows" "" "$empty_out"

# The documented contract is one row per NON-EMPTY input line, in input order —
# NOT one row per raw stdin line. Pin that explicitly: 5 stdin lines, 2 of them
# blank, must yield exactly 2 rows. A caller mapping rows to line positions
# would misalign here, which is why the docs say to key off the echoed path.
blank_in=$(printf '\n%s\n\n%s\n\n' "$TMP/t13_satisfied.md" "$TMP/t12_pending.md")
blank_out=$( printf '%s\n' "$blank_in" | batch "$REG" 2>/dev/null )
assert_eq "T7 rows == NON-EMPTY input lines (not raw lines)" "2" \
    "$(printf '%s\n' "$blank_out" | grep -c . | tr -d ' ')"
assert_eq "T7 surviving rows keep input order and decide correctly" \
"SATISFIED
BLOCKED:build_verified" "$(printf '%s\n' "$blank_out" | cut -f1)"
assert_eq "T7 echoed paths are the non-empty inputs" \
"$TMP/t13_satisfied.md
$TMP/t12_pending.md" "$(printf '%s\n' "$blank_out" | cut -f2)"

# =====================================================================
echo "--- T8: bash surface parity + exit-status propagation ---"
# =====================================================================

BREPO="$TMP/bashrepo"
mkdir -p "$BREPO/aitasks/metadata"
cp "$REG" "$BREPO/aitasks/metadata/gates.yaml"
write_task "$BREPO/aitasks/t90_sat.md" "plan_approved, build_verified" "" \
    "$(mark plan_approved pass)" "$(mark build_verified pass)"
write_task "$BREPO/aitasks/t91_blk.md" "build_verified" ""

b_paths=$(printf '%s\n%s\n' "aitasks/t90_sat.md" "aitasks/t91_blk.md")
sh_out=$( cd "$BREPO" && printf '%s\n' "$b_paths" | TASK_DIR=aitasks "$GATE" deps-unblock-batch 2>/dev/null )
sh_rc=$?
py_out=$( cd "$BREPO" && printf '%s\n' "$b_paths" | batch "aitasks/metadata/gates.yaml" 2>/dev/null )
assert_exit_zero_rc "T8 bash surface exits 0 on the clean path" "$sh_rc"
assert_eq "T8 bash surface == python module output" "$py_out" "$sh_out"
assert_eq "T8 decisions are the expected shapes" \
"SATISFIED
BLOCKED:build_verified" "$(printf '%s\n' "$sh_out" | cut -f1)"

# Setup failure must propagate through the bash wrapper too.
mkdir -p "$BREPO/broken/metadata/gates.yaml"
sh_bad=$( cd "$BREPO" && printf '%s\n' "aitasks/t90_sat.md" \
          | TASK_DIR=broken "$GATE" deps-unblock-batch 2>/dev/null )
sh_bad_rc=$?
assert_eq "T8 bash surface propagates exit 1 on setup failure" "1" "$sh_bad_rc"
assert_eq "T8 bash surface still emits the conservative row" "NO_GATES" \
    "$(printf '%s\n' "$sh_bad" | cut -f1)"

# =====================================================================
echo "--- T9: aitask_ls.sh integration unchanged ---"
# =====================================================================

LREPO="$TMP/lsrepo"
mkdir -p "$LREPO/aitasks/metadata"
cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" "$LREPO/aitasks/metadata/gates.yaml"
: > "$LREPO/aitasks/metadata/labels.txt"
printf 'feature\nbug\nchore\n' > "$LREPO/aitasks/metadata/task_types.txt"

# Upstream t40: gated, all blocks_dependents gates pass -> releases dependents.
cat > "$LREPO/aitasks/t40_upstream.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
gates: [build_verified, review_approved]
active_gates: [build_verified, review_approved]
---
up

## Gate Runs

> **✅ gate:build_verified** run=2026-01-01T00:00:00Z status=pass attempt=1
> **✅ gate:review_approved** run=2026-01-01T00:00:00Z status=pass attempt=1
EOF
cat > "$LREPO/aitasks/t41_dependent.md" <<'EOF'
---
priority: high
effort: medium
depends: [40]
issue_type: feature
status: Ready
---
dep
EOF

ls_out=$( cd "$LREPO" && TASK_DIR=aitasks "$LS" -v 9 2>&1 )
assert_contains "T9 dependent is listed" "t41_dependent.md" "$ls_out"
assert_not_contains "T9 gated-satisfied upstream unblocks its dependent" \
    "Blocked" "$(printf '%s\n' "$ls_out" | grep 't41_dependent')"

# With the registry broken (T6 shape), ls must degrade to blocked, not crash.
rm -f "$LREPO/aitasks/metadata/gates.yaml"
mkdir -p "$LREPO/aitasks/metadata/gates.yaml"
ls_broken=$( cd "$LREPO" && TASK_DIR=aitasks "$LS" -v 9 2>&1 ); ls_broken_rc=$?
assert_exit_zero_rc "T9 ls survives a broken registry" "$ls_broken_rc"
# t40 is `Implementing`; aitask_ls.sh filters to Ready (STATUS_FILTER), so the
# dependent is the observable row here.
assert_contains "T9 ls still lists tasks with a broken registry" "t41_dependent.md" "$ls_broken"
assert_contains "T9 dependent falls back to Blocked (file-existence)" \
    "Blocked" "$(printf '%s\n' "$ls_broken" | grep 't41_dependent')"

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
