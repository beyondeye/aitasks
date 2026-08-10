#!/usr/bin/env bash
# test_gate_stale_witness_parity.sh - Surface parity for a code-stale human-gate
# signature (t1416).
#
# t1409 made a human gate's code-bound witness re-validated on EVERY observation
# rather than only before the first `pass`, but wired that into two enforcing
# surfaces only (`gates run` and `archive-ready`). Four read-side surfaces stayed
# ledger-only, so a board badge or an `ait ls` row could report a task archivable
# / its dependents released while the enforcing guard blocked it.
#
# t1416 decided the split per surface. This file pins the three that now
# RE-VALIDATE:
#
#   1. aitask_gate.sh deps-unblock          SATISFIED -> BLOCKED:<gate>
#   2. gate_orchestrator.py unlocked        (empty)   -> <gate>
#   3. gate_ledger.read_task_gate_state     ALL_PASS  -> BLOCKED + stale_signed
#
# and the discriminating NEGATIVE case that constrains all three (the t1409 Test
# 9c constraint): a satisfied human gate with a `signal_target` but NO witness is
# the ATTENDED-recorded pass, and must never be demoted on any surface.
#
# Every assertion runs BEFORE anything re-pends the ledger. That ordering is what
# makes them discriminating: with the ledger still reading `pass`, the only thing
# that can produce BLOCKED / a non-empty unlocked set is the witness overlay.
#
# The fixture also carries the ratified counter-surface: archive_status_from_text
# must STAY ledger-only (it is a pure-text contract whose verdict is hashed into
# the trail's staleness digest), so it keeps reading ALL_PASS on the same input.
#
# Run: bash tests/test_gate_stale_witness_parity.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

ORCH="$PROJECT_DIR/.aitask-scripts/lib/gate_orchestrator.py"
GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || echo python3)"

cleanup() { for d in "${CLEANUP_DIRS[@]:-}"; do [[ -n "$d" ]] && rm -rf "$d"; done; }
trap cleanup EXIT

# --- fixture ---------------------------------------------------------------

# new_fixture [--no-git]
# A task whose ONLY active gate is a `blocks_dependents: true` human gate,
# already recorded `pass`, in a git repo with a gitignored witness dir.
new_fixture() {
    local nogit="${1:-}"
    local d
    d="$(mktemp -d "${TMPDIR:-/tmp}/test_parity_XXXXXX")"
    CLEANUP_DIRS+=("$d")
    mkdir -p "$d/aitasks/metadata" "$d/sig"
    if [[ "$nogit" != "--no-git" ]]; then
        ( cd "$d" && git init -q && git config user.email t@t && git config user.name t \
            && echo seed > code.txt && printf 'sig/\n' > .gitignore \
            && git add -A && git commit -qm init )
    else
        echo seed > "$d/code.txt"
    fi
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  review:
    type: human
    blocks_dependents: true
    signal_target: "$d/sig/<task-id>-review.signed"
EOF
    echo "$d"
}

# write_task <dir> <id> — active_gates tuple + a recorded `pass` for `review`.
# The ledger entry is written directly rather than via `gates run`, so the
# fixture's starting state is unambiguous and does not depend on the engine.
write_task() {
    local d="$1" id="$2"
    cat > "$d/aitasks/t${id}_x.md" <<EOF
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

digest_of() { ( cd "$1" && "$PY" "$ORCH" code-digest ); }

sign() {  # <dir> <id> <digest>
    printf 'signer=tester\ncode_digest=%s\n' "$3" > "$1/sig/t$2-review.signed"
}

deps_unblock() { ( cd "$1" && TASK_DIR="$1/aitasks" "$GATE" deps-unblock "$2" ); }

unlocked_of() {
    ( cd "$1" && "$PY" "$ORCH" unlocked "$1/aitasks/t${2}_x.md" \
        --registry "$1/aitasks/metadata/gates.yaml" 2>&1 )
}

# tui_state <dir> <id> <field>
# Drives read_task_gate_state the way the board does (registry supplied).
tui_state() {
    ( cd "$1" && "$PY" - "$1" "$2" "$3" <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.join(os.environ["PROJECT_DIR"], ".aitask-scripts", "lib"))
import gate_ledger as gl
d, tid, fieldname = sys.argv[1], sys.argv[2], sys.argv[3]
st = gl.read_task_gate_state(f"{d}/aitasks/t{tid}_x.md",
                             f"{d}/aitasks/metadata/gates.yaml")
v = getattr(st, fieldname)
print(",".join(v) if isinstance(v, list) else v)
PYEOF
    )
}

# ledger_only_twin <dir> <id> — the RATIFIED pure-text surface.
ledger_only_twin() {
    ( cd "$1" && "$PY" - "$1" "$2" <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.join(os.environ["PROJECT_DIR"], ".aitask-scripts", "lib"))
import gate_ledger as gl
d, tid = sys.argv[1], sys.argv[2]
with open(f"{d}/aitasks/t{tid}_x.md", encoding="utf-8") as fh:
    print(gl.archive_status_from_text(fh.read())[0])
PYEOF
    )
}

export PROJECT_DIR

# ============================================================
# Test 1: all three surfaces flip when the signature goes stale
# ============================================================
test_surfaces_flip_on_stale() {
    echo "=== Test 1: deps-unblock / unlocked / read_task_gate_state re-validate ==="
    local d; d="$(new_fixture)"
    write_task "$d" 50
    sign "$d" 50 "$(digest_of "$d")"

    # --- Seeded state: signed against the CURRENT code. Asserting the flip
    #     without this would be vacuous — an unsigned or already-blocked task
    #     reaches the same verdicts for entirely different reasons.
    assert_eq "fresh signature -> dependents released" "SATISFIED" \
        "$(deps_unblock "$d" 50)"
    assert_eq "fresh signature -> nothing unlocked" "" "$(unlocked_of "$d" 50)"
    assert_eq "fresh signature -> TUI reads archivable" "ALL_PASS" \
        "$(tui_state "$d" 50 archive_decision)"
    assert_eq "fresh signature -> TUI reports no stale gate" "" \
        "$(tui_state "$d" 50 stale_signed)"

    # --- Change CODE (not the ledger). The witness is now stamped-but-wrong.
    ( cd "$d" && echo after-signoff >> code.txt )

    # Precondition that makes every assertion below discriminating: the ledger
    # is untouched, so ONLY the witness overlay can change any verdict.
    assert_contains "pre-check: the ledger still reads pass" "status=pass" \
        "$(cat "$d/aitasks/t50_x.md")"

    assert_eq "stale signature -> dependents NOT released" "BLOCKED:review" \
        "$(deps_unblock "$d" 50)"
    assert_eq "stale signature -> gate reported unlocked again" "review" \
        "$(unlocked_of "$d" 50)"
    assert_eq "stale signature -> TUI archival blocked" "BLOCKED" \
        "$(tui_state "$d" 50 archive_decision)"
    assert_eq "stale signature -> TUI names the stale gate" "review" \
        "$(tui_state "$d" 50 stale_signed)"
    assert_eq "stale signature -> TUI dependents blocked" "BLOCKED" \
        "$(tui_state "$d" 50 dependents_decision)"

    # The raw ledger is preserved on the TUI surface: `current` keeps `pass`, so
    # a renderer can show BOTH facts. A demotion that rewrote `current` would
    # make the badge count drop with nothing to explain it.
    assert_contains "stale signature -> raw ledger run kept for display" \
        "review" "$(tui_state "$d" 50 status_text)"

    # --- RATIFIED counter-surface: the pure-text twin must NOT move.
    assert_eq "ratified: archive_status_from_text stays ledger-only" "ALL_PASS" \
        "$(ledger_only_twin "$d" 50)"

    # --- Re-signing the new code state closes the loop on all three.
    sign "$d" 50 "$(digest_of "$d")"
    assert_eq "re-signed -> dependents released again" "SATISFIED" \
        "$(deps_unblock "$d" 50)"
    assert_eq "re-signed -> nothing unlocked again" "" "$(unlocked_of "$d" 50)"
    assert_eq "re-signed -> TUI archivable again" "ALL_PASS" \
        "$(tui_state "$d" 50 archive_decision)"
}

# ============================================================
# Test 2: an ABSENT witness is the attended pass — never demoted
# ============================================================
test_absent_witness_never_demoted() {
    echo "=== Test 2: attended-recorded pass (no witness) is never demoted ==="
    local d; d="$(new_fixture)"
    write_task "$d" 51
    # Deliberately NO sign() call: the gate has a signal_target configured, but
    # an attended session records the pass from the interactive approval and
    # never writes a witness. Demoting on `absent` would break that whole lane.
    ( cd "$d" && echo unrelated-change >> code.txt )

    assert_eq "absent witness -> dependents still released" "SATISFIED" \
        "$(deps_unblock "$d" 51)"
    assert_eq "absent witness -> nothing unlocked" "" "$(unlocked_of "$d" 51)"
    assert_eq "absent witness -> TUI archivable" "ALL_PASS" \
        "$(tui_state "$d" 51 archive_decision)"
    assert_eq "absent witness -> no stale gate reported" "" \
        "$(tui_state "$d" 51 stale_signed)"
}

# ============================================================
# Test 3: an UNSTAMPED witness stays accepted (backward compat)
# ============================================================
test_unstamped_witness_accepted() {
    echo "=== Test 3: witness with no code_digest stays accepted ==="
    local d; d="$(new_fixture)"
    write_task "$d" 52
    printf 'signer=tester\n' > "$d/sig/t52-review.signed"   # no code_digest=
    ( cd "$d" && echo unrelated-change >> code.txt )

    assert_eq "unstamped witness -> dependents released" "SATISFIED" \
        "$(deps_unblock "$d" 52)"
    assert_eq "unstamped witness -> nothing unlocked" "" "$(unlocked_of "$d" 52)"
    assert_eq "unstamped witness -> TUI archivable" "ALL_PASS" \
        "$(tui_state "$d" 52 archive_decision)"
}

# ============================================================
# Test 4: an UNVERIFIABLE digest fails open to ledger truth
# ============================================================
#   `code_digest()` returns None with no git / no commits. That is the documented
#   "unverifiable -> accept" policy, and it is now exposed through three public
#   surfaces where an unhandled failure would crash a TUI or falsely block
#   dependents. Driven through the DOCUMENTED seam (a non-git fixture dir), the
#   same way test_gate_orchestrator.sh and test_gate_verifiers.sh force it —
#   not through a test-only override.
test_unverifiable_digest_fails_open() {
    echo "=== Test 4: unverifiable digest -> accept, on every surface ==="
    local d; d="$(new_fixture --no-git)"
    write_task "$d" 53
    # A STAMPED witness whose digest cannot possibly match anything, in a dir
    # where the digest is uncomputable. Nothing may be guessed `stale` here.
    printf 'signer=tester\ncode_digest=deadbeefdeadbeef\n' \
        > "$d/sig/t53-review.signed"

    # Positive control: prove the digest really is unresolvable in this fixture,
    # or the three assertions below would pass for the wrong reason.
    assert_eq "fixture really has no computable digest" "" "$(digest_of "$d")"

    assert_eq "unverifiable -> dependents released" "SATISFIED" \
        "$(deps_unblock "$d" 53)"
    assert_eq "unverifiable -> nothing unlocked" "" "$(unlocked_of "$d" 53)"
    assert_eq "unverifiable -> TUI archivable" "ALL_PASS" \
        "$(tui_state "$d" 53 archive_decision)"
    assert_eq "unverifiable -> no stale gate reported" "" \
        "$(tui_state "$d" 53 stale_signed)"
}

# ============================================================
# Test 5: a non-blocks_dependents gate does not hold dependents
# ============================================================
#   Guards against over-demotion: deps-unblock must demote over the REQUIRED set
#   only. A stale signature on a gate nobody flagged blocking must not start
#   holding dependents that were never held before.
test_stale_non_blocking_gate_does_not_hold_dependents() {
    echo "=== Test 5: stale signature on a non-blocking gate frees dependents ==="
    local d; d="$(new_fixture)"
    sed -i 's/blocks_dependents: true/blocks_dependents: false/' \
        "$d/aitasks/metadata/gates.yaml"
    write_task "$d" 54
    sign "$d" 54 "$(digest_of "$d")"
    ( cd "$d" && echo after-signoff >> code.txt )

    # Required set is empty -> NO_GATES (file-existence fallback), unchanged.
    assert_eq "non-blocking stale gate -> NO_GATES, not BLOCKED" "NO_GATES" \
        "$(deps_unblock "$d" 54)"
    # ...but archival, which requires ALL declared gates, still sees it.
    assert_eq "non-blocking stale gate -> archival still blocked" "BLOCKED" \
        "$(tui_state "$d" 54 archive_decision)"
}

# --- run -------------------------------------------------------------------

test_surfaces_flip_on_stale
test_absent_witness_never_demoted
test_unstamped_witness_accepted
test_unverifiable_digest_fails_open
test_stale_non_blocking_gate_does_not_hold_dependents

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ $FAIL -eq 0 ]]; then
    echo "All tests PASSED"
    exit 0
fi
echo "FAILURES: $FAIL"
exit 1
