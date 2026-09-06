#!/usr/bin/env bash
# test_live_endpoint_no_sendkeys.sh — the delivery-path contract (t1657_4).
#
# Two obligations on the path from "I know the pane" to "the note is delivered".
#
# 1. tmux is DISCOVERY, never the transport (sections 1-2f). The shortest path
#    from a resolved pane to a delivered note is `tmux send-keys`, and it is
#    wrong in a way that stays invisible until it corrupts something: keystrokes
#    land in whatever UI state the pane happens to be in — a prompt, a shell, an
#    editor, a half-typed answer to an AskUserQuestion — carry no agent identity
#    or message framing, and offer no queued/received semantics. Delivery goes
#    through the agent runtime's own cross-session mechanism, or not at all.
#
#    Checked on both halves: the RESOLVER (code) against an ALLOWLIST of tmux
#    verbs, not merely "no send-keys" — that would pass a resolver which had
#    grown `paste-buffer` or `run-shell`, the same mistake in a different word;
#    and every ADAPTER named in the manifest (prose), which must state the
#    prohibition and must not instruct a send-keys anywhere. A prohibition and an
#    instruction both contain the string, so occurrences are checked for negation
#    rather than merely counted.
#
# 2. A failed join must be DIAGNOSABLE (2g-2h). The listing row format an adapter
#    joins against is an observed contract of a model-facing tool, so a rendering
#    change degrades every send to "no session match" — fail-safe, but
#    indistinguishable from "that session ended". The adapter is required to name
#    the pane it searched for and to join on the pane id.
#
# Run: bash tests/test_live_endpoint_no_sendkeys.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

RESOLVER="$PROJECT_DIR/.aitask-scripts/aitask_live_endpoint.sh"
DELIVERY_DIR="$PROJECT_DIR/.aitask-scripts/live_delivery"
MANIFEST="$DELIVERY_DIR/agents.txt"

# The complete set of tmux verbs the resolver is allowed to issue. Read-only
# discovery only. Adding a verb here is a deliberate act that shows up in review.
ALLOWED_TMUX_VERBS="list-panes"

echo "=== live delivery: transport prohibition + diagnosability (t1657_4) ==="

# --- 1. The resolver's tmux surface ---------------------------------------

assert_file_exists "1a. the resolver exists" "$RESOLVER"

# Every gateway call site, reduced to its verb.
verbs="$(grep -oE 'ait_tmux[[:space:]]+[a-z-]+' "$RESOLVER" \
    | sed 's/^ait_tmux[[:space:]]*//' | sort -u)"

assert_eq "1b. the resolver issues exactly the allowlisted tmux verb(s)" \
    "$ALLOWED_TMUX_VERBS" "$verbs"

# Stated separately so a regression reads as the specific mistake, not as a set
# inequality. These are the verbs that turn discovery into transport.
#
# A verb may appear in a COMMENT that forbids it — the resolver's header states
# the prohibition, and deleting that explanation to satisfy a grep would trade
# the reason for the rule. So the check is: never on a code line, and only on a
# comment line that negates. Same discipline as the adapter check below; a
# prohibition and an instruction both contain the string.
for forbidden in send-keys paste-buffer run-shell load-buffer set-buffer respawn-pane; do
    TOTAL=$((TOTAL + 1))
    offending="$(grep -nF -- "$forbidden" "$RESOLVER" \
        | grep -vE ':[[:space:]]*#' || true)"
    if [[ -n "$offending" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: 1c. the resolver uses '$forbidden' in code — tmux is not the transport"
        printf '        %s\n' "$offending"
    else
        PASS=$((PASS + 1))
    fi

    TOTAL=$((TOTAL + 1))
    unnegated="$(grep -nF -- "$forbidden" "$RESOLVER" \
        | grep -viE '(never|must not|not |no )' || true)"
    if [[ -n "$unnegated" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: 1c'. the resolver mentions '$forbidden' outside a prohibition:"
        printf '        %s\n' "$unnegated"
    else
        PASS=$((PASS + 1))
    fi
done

# The resolver must also stay free of any agent-runtime coupling: the family it
# reports comes from the task file and the manifest, never from a literal here.
for literal in ListAgents SendMessage claudecode; do
    TOTAL=$((TOTAL + 1))
    if grep -qF -- "$literal" "$RESOLVER"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: 1d. the resolver names '$literal' — it must be agent-runtime independent"
    else
        PASS=$((PASS + 1))
    fi
done

# --- 2. The adapters -------------------------------------------------------

assert_file_exists "2a. the adapter manifest exists" "$MANIFEST"

# Column 2 is a bare filename resolved inside the delivery directory.
adapters="$(grep -vE '^[[:space:]]*(#|$)' "$MANIFEST" | awk '{print $2}')"

TOTAL=$((TOTAL + 1))
if [[ -n "$adapters" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 2b. the manifest declares no adapters — the live lane is dead"
fi

while read -r rel; do
    [[ -n "$rel" ]] || continue
    path="$DELIVERY_DIR/$rel"
    assert_file_exists "2c. manifest row resolves to a file ($rel)" "$path"
    [[ -f "$path" ]] || continue

    # The prohibition must be STATED. An adapter that simply never mentions
    # send-keys is one edit away from using it; one that forbids it is not.
    TOTAL=$((TOTAL + 1))
    if grep -qiE '(never|must not|not).{0,40}send-keys' "$path"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: 2d. $rel does not state the send-keys prohibition"
    fi

    # …and every occurrence must be part of that prohibition, never an
    # instruction. Counting occurrences cannot tell the two apart; requiring a
    # negation on the same line can.
    offending="$(grep -niE 'send-keys' "$path" \
        | grep -viE '(never|must not|not |no )' || true)"
    TOTAL=$((TOTAL + 1))
    if [[ -z "$offending" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: 2e. $rel mentions send-keys outside a prohibition:"
        printf '        %s\n' "$offending"
    fi

    # DIAGNOSABILITY (mitigation `diagnosable_no_session_match`). The listing row
    # format the adapter joins against is an OBSERVED contract of a model-facing
    # tool, not a documented API. If its rendering changes, every send degrades
    # to "no session match" — fail-safe, but indistinguishable from "that session
    # ended", so the drift is invisible for as long as nobody looks. The adapter
    # must therefore be required to say what it searched for.
    TOTAL=$((TOTAL + 1))
    if grep -qiE 'no_session_match' "$path" \
       && grep -qiE 'searched for' "$path"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: 2g. $rel does not require a diagnostic with no_session_match"
    fi

    # …and the join key must be the PANE ID. Matching on the session name or the
    # whole target string would break on a rename or a rendering change; the pane
    # id is unique per server and is the stable half of the row.
    TOTAL=$((TOTAL + 1))
    if grep -qiE 'pane[ _-]?id' "$path" && grep -qiE 'join' "$path"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: 2h. $rel does not name the pane id as the join key"
    fi

    # An adapter is a PROCEDURE, not a script: the join it performs needs
    # model-facing tools that have no CLI. A executable dropped in here would be
    # a second, unreviewed delivery path.
    TOTAL=$((TOTAL + 1))
    if [[ -x "$path" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: 2f. $rel is executable — adapters are procedures, not scripts"
    else
        PASS=$((PASS + 1))
    fi
done <<< "$adapters"

# --- 3. Nothing executable hides in the delivery directory ----------------

TOTAL=$((TOTAL + 1))
execs="$(find "$DELIVERY_DIR" -type f -perm -u+x 2>/dev/null || true)"
if [[ -z "$execs" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 3a. executable file(s) under live_delivery/:"
    printf '        %s\n' "$execs"
fi

# --- summary ---------------------------------------------------------------

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "SOME TESTS FAILED"
exit 1
