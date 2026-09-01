#!/usr/bin/env bash
# test_note_section_order.sh - Risk mitigation `pin_section_order` (t1657_2).
#
# THE INVARIANT: '## Inbox' must always sit ABOVE '## Gate Runs'.
#
# It is load-bearing and held only by convention. Both gate-append paths
# (_gate_append_locked in aitask_gate.sh and gate_ledger.append_block) append at
# EOF, so an Inbox placed BELOW the ledger would silently swallow every future
# gate block — the ledger would keep "working" while its records landed inside
# someone's mailbox.
#
# WHY BOTH CREATION ORDERS. ait_ledger_append_section has three paths and which
# one runs depends on what already exists in the file:
#
#   Gate Runs exists, no Inbox   -> create_before anchor-insert  (ledger_block.sh:150)
#   Inbox exists                 -> append_at="section_end"      (:167)
#   neither exists               -> EOF create                   (:194)
#
# A note-then-gate test alone exercises only the THIRD path: the Inbox is
# created at EOF because its anchor is absent, and the ordering then holds by
# arrival order rather than by create_before. The gate-then-note order is the
# one that actually drives the anchor-insert branch the whole design rests on.
#
# WHY BOTH BACKENDS. The bash and Python gate backends each have their own
# EOF-append path, so one passing proves nothing about the other.
#
# Run: bash tests/test_note_section_order.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

NOTE="$PROJECT_DIR/.aitask-scripts/aitask_note.sh"
GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_note_order_lock_XXXXXX")"
export AITASKS_LOCK_DIR
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_note_order_XXXXXX")"
cleanup() { rm -rf "$TMP" "$AITASKS_LOCK_DIR"; }
trap cleanup EXIT

CODE="$TMP/code"
mkdir -p "$CODE"
git -C "$CODE" init -q -b main
git -C "$CODE" config user.email t@example.com
git -C "$CODE" config user.name Test
echo one > "$CODE/f.txt"
git -C "$CODE" add -A && git -C "$CODE" commit -qm first

DATA="$TMP/data"
mkdir -p "$DATA/aitasks/metadata"
git -C "$DATA" init -q -b main
git -C "$DATA" config user.email t@example.com
git -C "$DATA" config user.name Test
cat > "$DATA/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  tests_pass:
    type: machine
    description: "Run project test suite; must all pass"
EOF

make_task() {
    cat > "$DATA/aitasks/t${1}_x.md" <<EOF
---
status: Implementing
gates: [tests_pass]
---
Body for t${1}.
EOF
}

# Section order in the file, as a single comparable string.
section_order() {
    grep -n '^## Inbox$\|^## Gate Runs$' "$DATA/aitasks/t${1}_x.md" \
        | sed 's/^[0-9]*://' | tr '\n' ',' | sed 's/,$//'
}

add_note() {
    ( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" "$1" --from 900 --text "n$1" ) \
        >/dev/null 2>&1
}
add_gate() {
    ( cd "$DATA" && AIT_GATES_BACKEND="$2" "$GATE" append "$1" tests_pass pass ) \
        >/dev/null 2>&1
}

echo "=== pin_section_order: Inbox stays above Gate Runs (t1657_2) ==="

n=0
for backend in "" "python"; do
    label="${backend:-bash}"
    if [[ "$backend" == "python" ]]; then
        # The Python backend needs an interpreter; skip loudly rather than
        # silently passing if none is resolvable.
        PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; \
               resolve_python 2>/dev/null || true)"
        if [[ -z "$PY" ]]; then
            echo "SKIP backend=python: no interpreter resolvable"
            continue
        fi
    fi

    # --- Order A: GATE first, then the note. ---
    # This is the anchor-insert path: '## Gate Runs' already exists, so the note
    # writer must place '## Inbox' BEFORE it via create_before.
    n=$((n + 1)); id="91${n}"
    make_task "$id"
    add_gate "$id" "$backend"
    assert_eq "A/${label}. gate ledger exists first" "## Gate Runs" "$(section_order "$id")"
    add_note "$id"
    assert_eq "A/${label}. note inserted ABOVE the existing ledger" \
        "## Inbox,## Gate Runs" "$(section_order "$id")"
    # A second gate block must still land in the ledger, not in the Inbox.
    add_gate "$id" "$backend"
    assert_eq "A/${label}. order survives a later gate append" \
        "## Inbox,## Gate Runs" "$(section_order "$id")"
    assert_eq "A/${label}. both gate blocks are under Gate Runs" "2" \
        "$(awk '/^## Gate Runs$/{f=1} f && /^> \*\*.*gate:/{c++} END{print c+0}' \
            "$DATA/aitasks/t${id}_x.md")"
    assert_eq "A/${label}. the note is NOT inside the ledger" "0" \
        "$(awk '/^## Gate Runs$/{f=1} f && /^> \*\*.*note:/{c++} END{print c+0}' \
            "$DATA/aitasks/t${id}_x.md")"

    # --- Order B: NOTE first, then the gate. ---
    # The anchor is absent, so the Inbox is created at EOF; the ledger is then
    # created at EOF after it. The ordering holds by arrival rather than by
    # create_before — a different code path reaching the same invariant.
    n=$((n + 1)); id="91${n}"
    make_task "$id"
    add_note "$id"
    assert_eq "B/${label}. inbox exists first" "## Inbox" "$(section_order "$id")"
    add_gate "$id" "$backend"
    assert_eq "B/${label}. ledger created BELOW the inbox" \
        "## Inbox,## Gate Runs" "$(section_order "$id")"
    # The regression this whole mitigation exists to catch: a gate block landing
    # inside the mailbox.
    assert_eq "B/${label}. gate block is under Gate Runs, not in the Inbox" "1" \
        "$(awk '/^## Gate Runs$/{f=1} f && /^> \*\*.*gate:/{c++} END{print c+0}' \
            "$DATA/aitasks/t${id}_x.md")"
    add_note "$id"
    assert_eq "B/${label}. a second note still lands in the Inbox" "2" \
        "$(awk '/^## Inbox$/{f=1} /^## Gate Runs$/{f=0} f && /^> \*\*.*note:/{c++} END{print c+0}' \
            "$DATA/aitasks/t${id}_x.md")"
    assert_eq "B/${label}. and does not disturb the order" \
        "## Inbox,## Gate Runs" "$(section_order "$id")"
done

echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
