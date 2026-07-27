#!/usr/bin/env bash
# test_gates_sync_registry.sh - `ait gates sync-registry` additive reconcile (t635_34)
#
# Exercises the REAL user entry point (`./ait gates sync-registry`) against
# synthetic projects, in the fixture style of tests/test_gate_cli_wiring.sh.
#
# The workhorse is `sum_of` (byte identity): every fail-closed case asserts BOTH
# a nonzero exit AND an unchanged file, so an implementation that fails loudly
# *after* corrupting the registry cannot pass.
#
# Isolated cases use AIT_GATES_REFERENCE to point at a doctored reference —
# without it every case would run against the live shipped reference, which is
# both brittle (breaks whenever a gate is added) and unable to express the
# edge cases at all.
#
# Run: bash tests/test_gates_sync_registry.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

new_fixture() {
    local tmp; tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gatesync_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata/profiles"
    cp "$PROJECT_DIR/ait" "$tmp/ait"
    ln -s "$PROJECT_DIR/.aitask-scripts" "$tmp/.aitask-scripts"
    echo "$tmp"
}

# Byte identity of a file — proves "wrote nothing", not merely "exited nonzero".
sum_of() { cksum < "$1"; }

# Only the comment lines, so "comments preserved" is asserted directly rather
# than inferred from the file being unchanged (it is not — fills landed).
comments_of() { grep '^[[:space:]]*#' "$1" | cksum; }

sync() { ( cd "$1" && shift && ./ait gates sync-registry "$@" ); }

# A minimal reference declaring exactly one gate, so a case can isolate ONE
# action instead of also triggering NEW_GATE for the other seven shipped gates.
mini_ref() {
    local path="$1"
    cat > "$path" <<'EOF'
# doctored reference
gates:
  lint:
    type: machine
    description: "Project linter reports no errors"
    # a comment inside the block
    verifier: aitask-gate-lint
    max_retries: 2
    timeout_seconds: 300
    blocks_dependents: true
EOF
}

parse_field() {
    # parse_field <registry> <gate> <key> -> the PARSED value, via the real reader
    python3 - "$1" "$2" "$3" <<'PY'
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])) if False else "", ""))
sys.path.insert(0, os.environ["LIBDIR"])
import gate_ledger as gl
reg = gl.read_registry(sys.argv[1])
print(reg.get(sys.argv[2], {}).get(sys.argv[3], "<<missing>>"))
PY
}
export LIBDIR="$PROJECT_DIR/.aitask-scripts/lib"

gate_names() {
    python3 - "$1" <<'PY'
import sys, os
sys.path.insert(0, os.environ["LIBDIR"])
import gate_ledger as gl
print(",".join(sorted(gl.read_registry(sys.argv[1]))))
PY
}

# ===================================================================
echo "=== Test 1: additive fill + comment preservation ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
# project registry — hand maintained
gates:
  lint:
    type: machine
    description: "Project linter reports no errors"
EOF
before_comments="$(comments_of "$reg")"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_contains "fill: verifier reported" "FILLED:lint.verifier=aitask-gate-lint" "$out"
assert_contains "fill: max_retries reported" "FILLED:lint.max_retries=2" "$out"
assert_contains "fill: timeout_seconds reported" "FILLED:lint.timeout_seconds=300" "$out"
assert_contains "fill: blocks_dependents reported" "FILLED:lint.blocks_dependents=true" "$out"
assert_eq "fill: verifier now parses from the registry" "aitask-gate-lint" \
    "$(parse_field "$reg" lint verifier)"
assert_eq "fill: COMMENTS byte-identical after the write" \
    "$before_comments" "$(comments_of "$reg")"
# blocks_dependents:false / max_retries:0 are the PARSE DEFAULTS — writing them
# would be pure churn, so a reference value equal to the default is never filled.
assert_not_contains "fill: does not write a default-valued key (type)" \
    "FILLED:lint.type" "$out"

echo "=== Test 2: presence oracle — explicit empty is a CONFLICT, not a fill ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
  lint:
    type: machine
    description: "d"
    verifier: ""
    max_retries: 2
    timeout_seconds: 300
    blocks_dependents: true
EOF
before="$(sum_of "$reg")"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_contains "presence: empty verifier reported as CONFLICT" \
    'CONFLICT:lint.verifier:""|aitask-gate-lint' "$out"
assert_not_contains "presence: empty verifier NOT filled" "FILLED:lint.verifier" "$out"
assert_eq "presence: file byte-unchanged (deliberate opt-out preserved)" \
    "$before" "$(sum_of "$reg")"

echo "=== Test 3: presence oracle — explicit 0 is a CONFLICT, not a fill ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
  lint:
    type: machine
    description: "d"
    verifier: aitask-gate-lint
    max_retries: 0
    timeout_seconds: 300
    blocks_dependents: true
EOF
before="$(sum_of "$reg")"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_contains "presence(int): explicit 0 reported as CONFLICT" \
    "CONFLICT:lint.max_retries:0|2" "$out"
assert_eq "presence(int): file byte-unchanged" "$before" "$(sum_of "$reg")"

echo "=== Test 4: unlocks is never filled, in either direction ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
cat > "$d/ref.yaml" <<'EOF'
gates:
  lint:
    type: machine
    unlocks: [tests_pass]
EOF
cat > "$reg" <<'EOF'
gates:
  lint:
    type: machine
EOF
before="$(sum_of "$reg")"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_contains "unlocks: absent-in-project reported, not filled" \
    "CONFLICT:lint.unlocks:(absent)|[tests_pass]" "$out"
assert_not_contains "unlocks: never appears as a FILLED action" "FILLED:lint.unlocks" "$out"
assert_eq "unlocks: file byte-unchanged" "$before" "$(sum_of "$reg")"
assert_eq "unlocks: still absent (linear default intact)" "None" \
    "$(parse_field "$reg" lint unlocks)"

echo "=== Test 5: NEW_GATE copies the block, comments included ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
  plan_approved:
    type: human
EOF
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_contains "new gate: reported" "NEW_GATE:lint" "$out"
assert_eq "new gate: both gates present after append" "lint,plan_approved" \
    "$(gate_names "$reg")"
assert_eq "new gate: verifier copied" "aitask-gate-lint" "$(parse_field "$reg" lint verifier)"
assert_eq "new gate: timeout copied" "300" "$(parse_field "$reg" lint timeout_seconds)"
assert_eq "new gate: the block's own comment came along" "yes" \
    "$(grep -qF 'a comment inside the block' "$reg" && echo yes || echo no)"

echo "=== Test 6: NEW_GATE re-indents (the silent-corruption case) ==="
# The reference is 2-space gate / 4-space field. Pasted VERBATIM into a 4/8
# project, gate_indent becomes 4, the pasted header at 2 still reads as a gate,
# and its fields at 4 satisfy `4 <= 4` -> they become sibling gates named
# `type`, `verifier`, `description`. Silent, catastrophic.
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
    plan_approved:
        type: human
EOF
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1
assert_eq "re-indent: gate set is exactly the two real gates" "lint,plan_approved" \
    "$(gate_names "$reg")"
assert_not_contains "re-indent: no gate named 'type' was created" "type" "$(gate_names "$reg")"
assert_eq "re-indent: the copied field parses under its gate" "aitask-gate-lint" \
    "$(parse_field "$reg" lint verifier)"
assert_eq "re-indent: fields use the project's 8-column indent" "yes" \
    "$(grep -q '^        verifier: aitask-gate-lint$' "$reg" && echo yes || echo no)"

echo "=== Test 7: tab-indented project keeps tabs ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
printf 'gates:\n\tlint:\n\t\ttype: machine\n\t\tdescription: "d"\n' > "$reg"
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1
assert_eq "tabs: inserted line uses the gate's own tab indent" "yes" \
    "$(grep -q "^$(printf '\t\t')verifier: aitask-gate-lint$" "$reg" && echo yes || echo no)"
assert_eq "tabs: still parses" "aitask-gate-lint" "$(parse_field "$reg" lint verifier)"

echo "=== Test 8: CRLF preserved ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
printf 'gates:\r\n  lint:\r\n    type: machine\r\n    description: "d"\r\n' > "$reg"
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1
lines="$(wc -l < "$reg" | tr -d ' ')"
crs="$(tr -cd '\r' < "$reg" | wc -c | tr -d ' ')"
assert_eq "crlf: every line still ends CRLF (incl. the inserted ones)" "$lines" "$crs"
assert_eq "crlf: still parses" "aitask-gate-lint" "$(parse_field "$reg" lint verifier)"

echo "=== Test 9: file with no trailing newline ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
printf 'gates:\n  plan_approved:\n    type: human' > "$reg"
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1
assert_eq "no-trailing-newline: appended block still parses" "lint,plan_approved" \
    "$(gate_names "$reg")"
assert_eq "no-trailing-newline: anchor line was terminated" "yes" \
    "$(grep -q '^    type: human$' "$reg" && echo yes || echo no)"

echo "=== Test 10: duplicate gate name -> fail closed ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
  lint:
    type: machine
    verifier: first
  lint:
    type: machine
EOF
before="$(sum_of "$reg")"
err="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>&1 >/dev/null)"; rc=$?
assert_eq "duplicate: exits nonzero" "1" "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
assert_contains "duplicate: names the offending gate" "lint" "$err"
assert_eq "duplicate: file byte-unchanged" "$before" "$(sum_of "$reg")"

echo "=== Test 11: column-0 comment truncating the mapping -> fail closed ==="
# `^\S` deactivates the parser, so everything below the comment is invisible and
# a naive sync would APPEND DUPLICATES of gates already in the file.
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
  plan_approved:
    type: human
# --- local gates below ---
  lint:
    type: machine
    verifier: mine
EOF
before="$(sum_of "$reg")"
err="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>&1 >/dev/null)"; rc=$?
assert_eq "col0-comment: exits nonzero" "1" "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
assert_contains "col0-comment: explains the truncation" "truncated" "$err"
assert_eq "col0-comment: file byte-unchanged (no duplicate append)" \
    "$before" "$(sum_of "$reg")"

echo "=== Test 12/13: gates: {} and a missing gates: key -> fail closed ==="
for body in 'gates: {}' 'other: x'; do
    d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
    mini_ref "$d/ref.yaml"
    printf '%s\n' "$body" > "$reg"
    before="$(sum_of "$reg")"
    err="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>&1 >/dev/null)"; rc=$?
    assert_eq "no-mapping ($body): exits nonzero" "1" "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
    assert_contains "no-mapping ($body): explains why" "gates:" "$err"
    assert_eq "no-mapping ($body): file byte-unchanged" "$before" "$(sum_of "$reg")"
done

echo "=== Test 14: unreadable reference must NOT report NOOP ==="
# The single most important negative test: "couldn't look" rendering as "you're
# in sync" is precisely the t1147 failure class this command exists to catch.
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
printf 'gates:\n  lint:\n    type: machine\n' > "$reg"
before="$(sum_of "$reg")"
out="$(AIT_GATES_REFERENCE="$d/nonexistent.yaml" sync "$d" 2>/dev/null)"; rc=$?
assert_eq "missing reference: exits nonzero" "1" "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
assert_not_contains "missing reference: does NOT print NOOP" "NOOP" "$out"
assert_eq "missing reference: file byte-unchanged" "$before" "$(sum_of "$reg")"

echo "=== Test 15: empty reference -> fail closed ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
printf 'gates:\n' > "$d/ref.yaml"
printf 'gates:\n  lint:\n    type: machine\n' > "$reg"
before="$(sum_of "$reg")"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"; rc=$?
assert_eq "empty reference: exits nonzero" "1" "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
assert_not_contains "empty reference: does NOT print NOOP" "NOOP" "$out"
assert_eq "empty reference: file byte-unchanged" "$before" "$(sum_of "$reg")"

echo "=== Test 16: --dry-run reports identically and writes nothing ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
  lint:
    type: machine
    description: "d"
EOF
before="$(sum_of "$reg")"
dry="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" --dry-run 2>/dev/null)"
assert_eq "dry-run: file byte-unchanged" "$before" "$(sum_of "$reg")"
wet="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_eq "dry-run: report identical to the applying run" "$dry" "$wet"

echo "=== Test 17: idempotence ==="
after_first="$(sum_of "$reg")"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_eq "idempotent: second run reports exactly NOOP" "NOOP" "$out"
assert_eq "idempotent: second run changes no bytes" "$after_first" "$(sum_of "$reg")"

echo "=== Test 18: PROFILE_UNKNOWN is report-only, and scans local/ ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
printf 'gates:\n  lint:\n    type: machine\n    description: "d"\n    verifier: aitask-gate-lint\n    max_retries: 2\n    timeout_seconds: 300\n    blocks_dependents: true\n' > "$reg"
mkdir -p "$d/aitasks/metadata/profiles/local"
printf 'name: fast\ndefault_gates: [not_a_gate]\n' > "$d/aitasks/metadata/profiles/fast.yaml"
printf 'name: x\nrendered_gates: [nope]\n' > "$d/aitasks/metadata/profiles/local/x.yaml"
p1="$(sum_of "$d/aitasks/metadata/profiles/fast.yaml")"
p2="$(sum_of "$d/aitasks/metadata/profiles/local/x.yaml")"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_contains "profiles: unknown gate in default_gates reported" \
    "PROFILE_UNKNOWN:fast.default_gates:not_a_gate" "$out"
assert_contains "profiles: local/ profile scanned with its prefix" \
    "PROFILE_UNKNOWN:local/x.rendered_gates:nope" "$out"
assert_eq "profiles: fast.yaml byte-unchanged (never edited)" \
    "$p1" "$(sum_of "$d/aitasks/metadata/profiles/fast.yaml")"
assert_eq "profiles: local/x.yaml byte-unchanged (never edited)" \
    "$p2" "$(sum_of "$d/aitasks/metadata/profiles/local/x.yaml")"
# A gate the SAME run adds must not be reported: otherwise --dry-run and the
# applying run would disagree.
d2="$(new_fixture)"; reg2="$d2/aitasks/metadata/gates.yaml"
mini_ref "$d2/ref.yaml"
printf 'gates:\n  plan_approved:\n    type: human\n' > "$reg2"
printf 'name: fast\ndefault_gates: [lint]\n' > "$d2/aitasks/metadata/profiles/fast.yaml"
out="$(AIT_GATES_REFERENCE="$d2/ref.yaml" sync "$d2" --dry-run 2>/dev/null)"
assert_not_contains "profiles: a gate this run ADDS is not reported unknown" \
    "PROFILE_UNKNOWN:fast.default_gates:lint" "$out"

echo "=== Test 19: reworded description is deliberately NOT a conflict ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
  lint:
    type: machine
    description: "our own wording"
    verifier: aitask-gate-lint
    max_retries: 2
    timeout_seconds: 300
    blocks_dependents: true
EOF
before="$(sum_of "$reg")"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_not_contains "description: reworded prose is not reported" \
    "CONFLICT:lint.description" "$out"
assert_eq "description: run is a clean NOOP" "NOOP" "$out"
assert_eq "description: file byte-unchanged" "$before" "$(sum_of "$reg")"

echo "=== Test 20: lock held by a live process -> fail closed ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
printf 'gates:\n  lint:\n    type: machine\n    description: "d"\n' > "$reg"
lock="/tmp/aitask_gate_registry_sync"
rm -rf "$lock"; mkdir -p "$lock"
# A LIVE pid: the mutex may only steal a provably-dead holder, never one that
# is merely old.
sleep 60 &
live_pid=$!
printf 'token-held\n%s\n' "$live_pid" > "$lock/owner"
before="$(sum_of "$reg")"
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1; rc=$?
kill "$live_pid" 2>/dev/null || true
rm -rf "$lock"
assert_eq "lock: exits nonzero rather than proceeding unlocked" "1" \
    "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
assert_eq "lock: file byte-unchanged" "$before" "$(sum_of "$reg")"

echo "=== Test 21: dispatcher wiring ==="
d="$(new_fixture)"
out="$( cd "$d" && ./ait gates --help 2>&1 )"
assert_contains "wiring: ait gates --help lists sync-registry" "sync-registry" "$out"
out="$( cd "$d" && ./ait gates bogus 2>&1 )"; rc=$?
assert_eq "wiring: unknown subcommand still exits 1" "1" "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
assert_contains "wiring: Available list mentions sync-registry" "sync-registry" "$out"

echo "=== Test 22: header-only gate, siblings have fields (indent rung 2) ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
cat > "$reg" <<'EOF'
gates:
  plan_approved:
      type: human
  lint:
EOF
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1
assert_eq "rung2: fill adopted the observed 6-column house style" "yes" \
    "$(grep -q '^      verifier: aitask-gate-lint$' "$reg" && echo yes || echo no)"
assert_eq "rung2: it parses as a FIELD of lint, not a new gate" "aitask-gate-lint" \
    "$(parse_field "$reg" lint verifier)"
assert_eq "rung2: gate set unchanged" "lint,plan_approved" "$(gate_names "$reg")"

echo "=== Test 23: NO gate anywhere has a field (indent rung 3) ==="
# field_ws is None for every block, so there is nothing to observe. The derived
# indent must still be provably deeper than gate_indent.
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
printf 'gates:\n  lint:\n' > "$reg"
err="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>&1 >/dev/null)"
assert_eq "rung3: fill parses as a field, not a sibling gate" "aitask-gate-lint" \
    "$(parse_field "$reg" lint verifier)"
assert_eq "rung3: gate set is still just lint" "lint" "$(gate_names "$reg")"
assert_contains "rung3: the derived indent is disclosed on stderr" "derived" "$err"

echo "=== Test 24: bare gates: with no gate headers (indent rung 4) ==="
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
printf 'gates:\n' > "$reg"
before="$(sum_of "$reg")"
err="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>&1 >/dev/null)"; rc=$?
assert_eq "rung4: exits nonzero rather than inventing both indent levels" "1" \
    "$([[ $rc -ne 0 ]] && echo 1 || echo 0)"
assert_contains "rung4: explains the empty mapping" "empty" "$err"
assert_eq "rung4: file byte-unchanged" "$before" "$(sum_of "$reg")"

echo "=== Test 25: gates.yaml is itself a FILE symlink ==="
# realpath before the atomic replace: replacing the LINK path would destroy the
# symlink and leave a regular file in its place.
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
mini_ref "$d/ref.yaml"
mkdir -p "$d/real"
cat > "$d/real/gates.yaml" <<'EOF'
gates:
  lint:
    type: machine
    description: "d"
EOF
rm -f "$reg"; ln -s "$d/real/gates.yaml" "$reg"
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1
assert_eq "symlink(file): the path is STILL a symlink" "yes" \
    "$([[ -L "$reg" ]] && echo yes || echo no)"
assert_eq "symlink(file): it still points at the same target" "$d/real/gates.yaml" \
    "$(readlink "$reg")"
assert_eq "symlink(file): the TARGET received the fill" "aitask-gate-lint" \
    "$(parse_field "$d/real/gates.yaml" lint verifier)"
assert_eq "symlink(file): no tempfile left behind" "" \
    "$(find "$d/real" "$d/aitasks/metadata" -name '.aitask_gate.*.tmp' 2>/dev/null)"

echo "=== Test 26: aitasks/ is a DIRECTORY symlink (the live layout) ==="
d="$(new_fixture)"
mini_ref "$d/ref.yaml"
mkdir -p "$d/.aitask-data/aitasks/metadata/profiles"
cat > "$d/.aitask-data/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  lint:
    type: machine
    description: "d"
EOF
rm -rf "$d/aitasks"; ln -s "$d/.aitask-data/aitasks" "$d/aitasks"
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1
assert_eq "symlink(dir): aitasks/ is still a symlink" "yes" \
    "$([[ -L "$d/aitasks" ]] && echo yes || echo no)"
assert_eq "symlink(dir): the real file received the fill" "aitask-gate-lint" \
    "$(parse_field "$d/.aitask-data/aitasks/metadata/gates.yaml" lint verifier)"

echo "=== Test 27: forward schema — unknown keys survive a NEW_GATE copy ==="
# The walk only recognises `key:` lines (plus `- item` under `unlocks`), so a
# copy bounded by the LAST FIELD would truncate an unknown key's block list.
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
cat > "$d/ref.yaml" <<'EOF'
gates:
  lint:
    type: machine
    verifier: aitask-gate-lint
    future_scalar: someval
    requires:
      - alpha
      - beta
EOF
printf 'gates:\n  plan_approved:\n    type: human\n' > "$reg"
AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" >/dev/null 2>&1
assert_eq "forward-schema: unknown scalar key copied" "yes" \
    "$(grep -q 'future_scalar: someval' "$reg" && echo yes || echo no)"
assert_eq "forward-schema: unknown key's block list NOT truncated (alpha)" "yes" \
    "$(grep -q -- '- alpha' "$reg" && echo yes || echo no)"
assert_eq "forward-schema: unknown key's block list NOT truncated (beta)" "yes" \
    "$(grep -q -- '- beta' "$reg" && echo yes || echo no)"
assert_eq "forward-schema: known keys still parse" "aitask-gate-lint" \
    "$(parse_field "$reg" lint verifier)"
assert_eq "forward-schema: no spurious gates from the copied content" \
    "lint,plan_approved" "$(gate_names "$reg")"

echo "=== Test 28: unknown keys are NOT filled into an existing gate ==="
# Documented asymmetry: the writer must never emit a key read_registry cannot
# consume. The drift guard in test_gates_reference_drift.sh is what stops the
# real reference from growing such a key unnoticed.
d="$(new_fixture)"; reg="$d/aitasks/metadata/gates.yaml"
cat > "$d/ref.yaml" <<'EOF'
gates:
  lint:
    type: machine
    verifier: aitask-gate-lint
    future_scalar: someval
EOF
printf 'gates:\n  lint:\n    type: machine\n' > "$reg"
out="$(AIT_GATES_REFERENCE="$d/ref.yaml" sync "$d" 2>/dev/null)"
assert_contains "asymmetry: the known key IS filled" "FILLED:lint.verifier" "$out"
assert_not_contains "asymmetry: the unknown key is NOT filled" "future_scalar" "$out"
assert_eq "asymmetry: unknown key absent from the registry" "no" \
    "$(grep -q 'future_scalar' "$reg" && echo yes || echo no)"

echo "=== Test 29: FILL_KEYS is a subset of what the parser can consume ==="
# A key the writer can emit but the reader ignores would make the file say
# something the readers cannot see.
sub="$(python3 - <<'PY'
import os, sys
sys.path.insert(0, os.environ["LIBDIR"])
import gate_ledger as gl, gate_registry_sync as grs
known = set(gl._GATE_FIELD_KEYS)
print("yes" if set(grs.FILL_KEYS) <= known else "no:" + str(set(grs.FILL_KEYS) - known))
PY
)"
assert_eq "allowlist: FILL_KEYS subset of _GATE_FIELD_KEYS" "yes" "$sub"
export PROJECT_DIR
covered="$(python3 - <<'PY'
import os, sys
sys.path.insert(0, os.environ["LIBDIR"])
import gate_ledger as gl
ref = os.path.join(os.environ["PROJECT_DIR"], ".aitask-scripts", "gates_reference.yaml")
lay = gl.registry_layout(open(ref, encoding="utf-8").read())
seen = set()
for b in lay.blocks.values():
    seen |= set(b.fields)
unknown = seen - set(gl._GATE_FIELD_KEYS)
print("yes" if not unknown else "no:" + ",".join(sorted(unknown)))
PY
)"
assert_eq "allowlist: reference declares no key the parser cannot consume" "yes" "$covered"

echo "=== Harness self-test: the assertion machinery actually reports ==="
# Catches the failure mode where a stubbed asserts.sh makes everything "pass".
if ( PASS=0; FAIL=0; TOTAL=0
     assert_eq "self-test (expected to fail)" a b >/dev/null 2>&1
     [[ $FAIL -eq 1 && $TOTAL -eq 1 ]] ); then
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: harness self-test — assert_eq did not report a mismatch"
fi

# Assertion-count pin: catches the OTHER harness failure mode, where the body
# aborts early (a failed mktemp, an unbound variable) so a whole block never
# runs and the summary still reads all-green.
assert_eq "assertion count (update when adding assertions)" "92" "$TOTAL"

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "All tests PASSED"
exit 0
