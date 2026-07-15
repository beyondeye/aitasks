#!/usr/bin/env bash
# test_applink_setup_gitignore.sh — `ait setup` seeds the applink_sessions/
# data-branch .gitignore rule (t1132).
#
# setup_data_branch appends a per-PC secrets gitignore block for
# aitasks/metadata/applink_sessions/ (TLS cert/key + bearer sessions.json). A
# fresh downstream install that later pairs applink must not commit those
# secrets on the blanket `git add .` that setup runs on the data branch. This
# guards the seeding logic independently of this repo's already-present manual
# rule. Run:
#   bash tests/test_applink_setup_gitignore.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SETUP="$PROJECT_DIR/.aitask-scripts/aitask_setup.sh"

PASS_COUNT=0
FAIL_COUNT=0
pass() { PASS_COUNT=$((PASS_COUNT + 1)); echo "ok - $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "FAIL - $1"; }

# --- Part 1: source guard — setup_data_branch seeds the applink block --------
# The exact defect (t1132) was the absence of this block; if it is ever removed,
# fresh installs regress. Assert both the idempotency guard and the append line.
if grep -qE 'grep -qxF "aitasks/metadata/applink_sessions/"' "$SETUP" \
   && grep -qE 'echo "aitasks/metadata/applink_sessions/"' "$SETUP"; then
    pass "aitask_setup.sh seeds the applink_sessions/ gitignore block"
else
    fail "aitask_setup.sh does NOT seed the applink_sessions/ gitignore block"
fi

# --- Part 2: behavioural check-ignore + negative control ---------------------
# Parse the ignore path the script actually seeds (don't re-hardcode it), write
# it into a fresh git repo's .gitignore, and confirm it ignores the applink
# secrets — and nothing more.
SEEDED_PATH="$(grep -oE 'echo "aitasks/metadata/applink_sessions/[^"]*"' "$SETUP" \
    | head -1 | sed -E 's/^echo "//; s/"$//')"

if [ -z "$SEEDED_PATH" ]; then
    fail "could not parse the seeded applink ignore path from aitask_setup.sh"
else
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    git -C "$TMP" init -q
    printf '%s\n' "$SEEDED_PATH" > "$TMP/.gitignore"

    # Positive: the live secret files must be ignored via the seeded dir rule.
    for f in \
        "aitasks/metadata/applink_sessions/tls_key.pem" \
        "aitasks/metadata/applink_sessions/sessions.json"; do
        if git -C "$TMP" check-ignore -q "$f"; then
            pass "check-ignore matches applink secret: $f"
        else
            fail "check-ignore does NOT match applink secret: $f"
        fi
    done

    # Negative control: a sibling metadata file must NOT be ignored (no over-match).
    NEG="aitasks/metadata/labels.txt"
    if git -C "$TMP" check-ignore -q "$NEG"; then
        fail "negative control unexpectedly ignored: $NEG"
    else
        pass "negative control not ignored: $NEG"
    fi
fi

echo ""
echo "PASS: $PASS_COUNT, FAIL: $FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
