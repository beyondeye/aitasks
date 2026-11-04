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

# setup_data_branch writes its data-worktree rules from the shared rule table
# (_ait_gitignore_group, t2197), so read the table rather than the source text.
# shellcheck source=/dev/null
source "$SETUP" --source-only
set +euo pipefail

# --- Part 1: source guard — setup_data_branch seeds the applink rule ---------
# The exact defect (t1132) was the absence of this rule; if it is ever removed,
# fresh installs regress. Assert the table group and that Step 3 writes it.
_ait_gitignore_group data_applink
# shellcheck disable=SC2154  # _ait_gi_rules is set by the sourced table
if [ "${#_ait_gi_rules[@]}" -eq 1 ] \
   && [ "${_ait_gi_rules[0]}" = "aitasks/metadata/applink_sessions/" ]; then
    pass "the data_applink group holds the applink_sessions/ rule"
else
    fail "the data_applink group does NOT hold exactly the applink_sessions/ rule"
fi
if declare -f setup_data_branch | grep -qw data_applink; then
    pass "setup_data_branch writes the data_applink group"
else
    fail "setup_data_branch does NOT write the data_applink group"
fi

# --- Part 2: behavioural check-ignore + negative control ---------------------
# Take the ignore path the script actually seeds from the table (don't
# re-hardcode it), write it into a fresh git repo's .gitignore, and confirm it
# ignores the applink secrets — and nothing more.
SEEDED_PATH="${_ait_gi_rules[0]}"

if [ -z "$SEEDED_PATH" ]; then
    fail "could not read the seeded applink ignore path from the rule table"
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
