#!/usr/bin/env bash
# test_frozen_dry_run_wrapper.sh — `aitask_frozen.sh` argv forwarding (t1705_7).
#
# The TUIs' real entry point to the frozen engines is this WRAPPER, not the
# Python module. Its `freeze` case used to be `[ $# -eq 2 ]`, so the three-word
# `freeze --all --dry-run` exited 2 on usage before Python ever ran: the
# confirmation-count path would have been dead through its only real caller
# while engine-level tests passed green. This pins that the relaxed gate
# forwards the exact argv, and that the forms it must still reject are still
# rejected.
#
# WHY A FAKE ENGINE, AND NOT THE REAL ONE.
#
# `--dry-run` mutates nothing *when the dispatch is correct* — and that is
# precisely the thing under test, so it cannot be the safety argument. Worse,
# `AITASKS_AGENT_SESSIONS_FILE` isolates only the JSON store: session discovery
# (`agent_launch_utils.discover_aitasks_sessions`) queries the CURRENT tmux
# server on every call. Running the real engine here would enumerate whatever
# agents the developer has open, and a regression in the dry-run branch would
# then FREEZE them. So this test substitutes a fake engine that only echoes its
# argv: real freezing is impossible by construction rather than by argument.
#
# The engine's own grammar — which forms are accepted, and that every rejected
# one calls neither mutator — is `tests/test_freeze_argument_grammar.py`.
#
# Run: bash tests/test_frozen_dry_run_wrapper.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# --- An isolated wrapper whose engines are fakes ---------------------------

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/lib"

cp "$PROJECT_DIR/.aitask-scripts/aitask_frozen.sh" "$TMP/aitask_frozen.sh"
# The wrapper sources these two before dispatching; symlink the real ones so the
# thing under test is the wrapper's own logic and nothing else.
ln -s "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$TMP/lib/"
ln -s "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"  "$TMP/lib/"

# Fake engines: print the verb and argv, then exit 0. Nothing to freeze, no
# store to touch, no tmux to query.
for engine in agent_freeze agent_restore; do
  cat > "$TMP/lib/$engine.py" <<'PY'
import sys
print("ENGINE_ARGV:" + " ".join(sys.argv[1:]))
PY
done

run_wrapper() {
  ( "$TMP/aitask_frozen.sh" "$@" ) 2>&1
}
run_status() {
  ( "$TMP/aitask_frozen.sh" "$@" ) >/dev/null 2>&1
  echo $?
}

# --- Forwarding: the new form reaches the engine verbatim ------------------

out="$(run_wrapper freeze --all --dry-run)"
assert_contains "freeze --all --dry-run reaches the engine verbatim" \
  "ENGINE_ARGV:freeze --all --dry-run" "$out"
assert_eq "…and exits 0 rather than on usage" \
  "0" "$(run_status freeze --all --dry-run)"

# --- The ordinary forms, in the SAME isolation (the control) ---------------
#
# A forwarding test that only covered the new spelling could pass while the
# relaxed gate had broken the two forms that already worked.

out="$(run_wrapper freeze '%5')"
assert_contains "freeze <pane> still forwards verbatim" \
  "ENGINE_ARGV:freeze %5" "$out"

out="$(run_wrapper freeze --all)"
assert_contains "freeze --all still forwards verbatim" \
  "ENGINE_ARGV:freeze --all" "$out"

# --- Still rejected by the shell, before any engine runs -------------------

out="$(run_wrapper freeze)"
assert_not_contains "bare freeze never reaches the engine" "ENGINE_ARGV:" "$out"
assert_contains "bare freeze prints usage" "Usage: aitask_frozen.sh" "$out"
assert_eq "bare freeze exits 2" "2" "$(run_status freeze)"

out="$(run_wrapper)"
assert_not_contains "no verb never reaches the engine" "ENGINE_ARGV:" "$out"
assert_eq "no verb exits 2" "2" "$(run_status)"

out="$(run_wrapper bogus --all)"
assert_contains "an unknown verb is named" "unknown verb: bogus" "$out"
assert_not_contains "an unknown verb never reaches the engine" \
  "ENGINE_ARGV:" "$out"

# `reconcile` and `drop` keep their exact arities — the relaxation was scoped to
# `freeze`, and a wildcard here would let a typo through to a destructive verb.
assert_eq "reconcile still refuses an extra argument" \
  "2" "$(run_status reconcile --all)"
assert_eq "drop still refuses two arguments" \
  "2" "$(run_status drop id1 id2)"
out="$(run_wrapper drop 7f3a2c1d)"
assert_contains "drop <id> still forwards to the FREEZE engine" \
  "ENGINE_ARGV:drop 7f3a2c1d" "$out"

# --- The usage text documents the new form ---------------------------------

out="$(run_wrapper freeze)"
assert_contains "usage documents freeze --all [--dry-run]" \
  "freeze --all [--dry-run]" "$out"

# --- Summary ---------------------------------------------------------------
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
