#!/usr/bin/env bash
# test_helper_whitelist_coverage.sh - every helper a skill invokes is allow-listed
# in every permission touchpoint, and no touchpoint allows a path that does not
# exist (t2198).
#
# Two defects motivated this, both found by hand-running the audit (t2175_4):
#   - `aitask_gate_record.sh` (gate-recording.md) had no entry in the repo's own
#     .claude/settings.local.json while the other four touchpoints did.
#   - every `aitask_parallel_admission` entry named the stem WITHOUT `.sh`, while
#     parallel-admission.md runs `aitask_parallel_admission.sh`. Codex's
#     prefix_rule compares argv tokens exactly and OpenCode's `<cmd> *` glob needs
#     a literal space after the stem, so those entries never matched anything.
#
# Coverage goes through the real audit (`aitask_audit_wrappers.sh
# discover-helpers` + `audit-helper-whitelist`), never a re-implementation of
# its matcher, so a stronger matcher is inherited here without change.
#
# CLAIM BOUNDARY: the coverage check proves an entry NAMING each helper exists in
# each touchpoint, as helper_present_in_touchpoint() matches it -- not that the
# entry is an effective allow. For Codex touchpoints 3/6 that matcher checks only
# the `pattern = [...]` text and ignores `decision` (a `decision = "forbidden"`
# rule audits as covered), and for Claude touchpoints 1/4 it greps the whole file
# (a `permissions.deny` entry would audit as covered). Touchpoint 7 does require
# `": "allow"`. Making the matcher decision-aware is the shared audit's job, not
# this test's.
#
# Run: bash tests/test_helper_whitelist_coverage.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
cd "$PROJECT_DIR" || exit 1

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

AUDIT_SH="./.aitask-scripts/aitask_audit_wrappers.sh"

# fatal <message> -- a probe that returned nothing would make every assertion
# below loop over an empty list and pass vacuously, so it aborts the run.
fatal() {
    echo "FATAL: $1"
    echo
    echo "PASS: $PASS, FAIL: $((FAIL + 1)), TOTAL: $((TOTAL + 1))"
    exit 1
}

# dead_entries <file> -> one line per `.aitask-scripts/<path>` token in <file>
# that does not name a regular file in this checkout. Tokens are the characters
# a helper path may contain, so the `:*` (Claude), `"]` (Codex) and ` *`
# (OpenCode) suffixes all end the token -- a stem entry yields the bare stem.
dead_entries() {
    local p
    grep -oE '\.aitask-scripts/[A-Za-z0-9_./-]+' "$1" | sort -u | while IFS= read -r p; do
        [[ -f "$PROJECT_DIR/$p" ]] || printf '%s\n' "$p"
    done
}

# --- Probes ---------------------------------------------------------------

tp_out="$("$AUDIT_SH" touchpoints 2>/dev/null)" || fatal "touchpoints probe failed"
TP_FILES="$(printf '%s\n' "$tp_out" | sed -n 's/^TOUCHPOINT:[0-9]*://p')"
TP_COUNT="$(printf '%s\n' "$TP_FILES" | grep -c . || true)"
[[ "$TP_COUNT" -gt 0 ]] || fatal "touchpoints probe returned no touchpoints"

helpers_out="$("$AUDIT_SH" discover-helpers 2>/dev/null)" || fatal "discover-helpers probe failed"
HELPERS="$(printf '%s\n' "$helpers_out" | sed -n 's/^HELPER://p')"
HELPER_COUNT="$(printf '%s\n' "$HELPERS" | grep -c . || true)"
[[ "$HELPER_COUNT" -gt 0 ]] || fatal "discover-helpers returned no helpers"

# The two helpers this task fixed must be in the discovered set, or Test 1 would
# pass without ever looking at them.
assert_contains "discover-helpers reports aitask_gate_record.sh" \
    "aitask_gate_record.sh" "$HELPERS"
assert_contains "discover-helpers reports aitask_parallel_admission.sh" \
    "aitask_parallel_admission.sh" "$HELPERS"

# --- Negative control (a): the audit can report a gap -----------------------

fake_missing="$("$AUDIT_SH" audit-helper-whitelist aitask_no_such_helper_t2198.sh \
    | grep -c '^MISSING:' || true)"
assert_eq "audit reports a never-listed helper in all $TP_COUNT touchpoints" \
    "$TP_COUNT" "$fake_missing"

# --- Test 1: every skill-invoked helper is listed in every touchpoint --------

# audit_helpers <audit-script> -> sets MISSING_OUT (the MISSING: lines) and
# AUDIT_ERRORS (one `<helper>:rc=<n>` per invocation that exited non-zero).
# The file runs without errexit, so an unchecked $( ) would turn an audit that
# crashed before printing into an empty -- i.e. "fully covered" -- result.
audit_helpers() {
    local audit="$1" helper out rc
    MISSING_OUT=""
    AUDIT_ERRORS=""
    while IFS= read -r helper; do
        rc=0
        out="$("$audit" audit-helper-whitelist "$helper")" || rc=$?
        if [[ "$rc" -ne 0 ]]; then
            AUDIT_ERRORS+="$helper:rc=$rc"$'\n'
        fi
        [[ -n "$out" ]] && MISSING_OUT+="$out"$'\n'
    done <<<"$HELPERS"
}

audit_helpers "$AUDIT_SH"
assert_eq "audit-helper-whitelist exits 0 for all $HELPER_COUNT helpers" \
    "" "$AUDIT_ERRORS"
assert_eq "all $HELPER_COUNT skill-invoked helpers are allow-listed in every touchpoint" \
    "" "$MISSING_OUT"

# --- Negative control (c): a crashing audit is an error, not coverage --------
# A stand-in audit that exits 42 with no output for one helper: the loop must
# report that invocation, while its stdout alone would read as "no gaps".

stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/t2198_audit_stub_XXXXXX")"
cat > "$stub_dir/audit.sh" <<'EOF'
#!/usr/bin/env bash
[[ "$2" == "aitask_gate_record.sh" ]] && exit 42
exit 0
EOF
chmod +x "$stub_dir/audit.sh"
audit_helpers "$stub_dir/audit.sh"
assert_eq "crashing audit: its stdout alone shows no gaps (premise)" "" "$MISSING_OUT"
assert_eq "crashing audit: the failed invocation is reported" \
    "aitask_gate_record.sh:rc=42" "${AUDIT_ERRORS%$'\n'}"
rm -rf "$stub_dir"

# --- Negative control (b): the dead-entry scan flags the stem shape ---------

scratch="$(mktemp -d "${TMPDIR:-/tmp}/t2198_whitelist_XXXXXX")"
cat > "$scratch/prefix.rules" <<'EOF'
prefix_rule(pattern = ["./.aitask-scripts/aitask_parallel_admission"], decision = "allow", justification = "Aitasks helper script")
prefix_rule(pattern = ["./.aitask-scripts/aitask_parallel_admission.sh"], decision = "allow", justification = "Aitasks helper script")
EOF
cat > "$scratch/claude.json" <<'EOF'
      "Bash(./.aitask-scripts/aitask_parallel_admission:*)",
      "Bash(./.aitask-scripts/aitask_brainstorm_apply_patcher.sh:*)",
EOF
cat > "$scratch/opencode.json" <<'EOF'
      "./.aitask-scripts/aitask_parallel_admission *": "allow",
EOF
assert_eq "scan flags the Codex stem rule and keeps the .sh rule" \
    ".aitask-scripts/aitask_parallel_admission" "$(dead_entries "$scratch/prefix.rules")"
assert_eq "scan flags the Claude stem entry and a retired helper" \
    "$(printf '%s\n%s' .aitask-scripts/aitask_brainstorm_apply_patcher.sh \
        .aitask-scripts/aitask_parallel_admission)" \
    "$(dead_entries "$scratch/claude.json")"
assert_eq "scan flags the OpenCode stem entry" \
    ".aitask-scripts/aitask_parallel_admission" "$(dead_entries "$scratch/opencode.json")"
rm -rf "$scratch"

# --- Test 2: no touchpoint allows a path that does not exist ----------------
#
# An extensionless stem or a retired helper is an entry no command ever matches:
# dead weight that also hides the real gap from a reader.

token_total=0
while IFS= read -r tp_file; do
    n="$(grep -oE '\.aitask-scripts/[A-Za-z0-9_./-]+' "$tp_file" | grep -c . || true)"
    token_total=$((token_total + n))
    assert_eq "$tp_file allows only paths that exist" "" "$(dead_entries "$tp_file")"
done <<<"$TP_FILES"
[[ "$token_total" -gt 0 ]] || fatal "no .aitask-scripts/ entries found in any touchpoint"

# --- Summary ---

echo
echo "PASS: $PASS, FAIL: $FAIL, TOTAL: $TOTAL"
[[ "$FAIL" -eq 0 ]]
