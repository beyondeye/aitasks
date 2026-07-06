#!/usr/bin/env bash
# test_codeagent_explore_relay.sh — `ait codeagent invoke explore-relay`
# dispatch tests (t1120_4).
#
# Uses the existing --dry-run seam (prints DRY_RUN: + argv, no live agent
# call): exact argv construction (env-prefixed tool-timeout exports,
# --print, --allowedTools, the /aitask-explorechat slash command); refusal
# without --headless; the two distinct env-precondition refusals
# (CHATLINK_RELAY_DIR vs CHATLINK_BUG_REPORT_FILE); codex/opencode
# "not yet supported" refusals; and a regression guard that existing
# operations still dispatch through the shared case ladder.
# Run: bash tests/test_codeagent_explore_relay.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CODEAGENT="$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"

cd "$PROJECT_DIR"   # models_*.json paths are repo-relative

PASS_COUNT=0
FAIL_COUNT=0

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "ok - $label"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "FAIL - $label: expected '$expected', got '$actual'"
    fi
}

assert_contains() {
    local label="$1" haystack="$2" needle="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "ok - $label"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "FAIL - $label: '$needle' not found in: $haystack"
    fi
}

TMP="$(mktemp -d "${TMPDIR:-/tmp}/explore_relay_test_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/relaydir"
printf 'the app crashes on login\n' > "$TMP/bug.md"

run() {  # run codeagent with controlled env; capture rc + combined output
    RUN_OUT="$(env "$@" 2>&1)" && RUN_RC=0 || RUN_RC=$?
}

# --- 1: refusal without --headless (before any env check) ---
run -u CHATLINK_RELAY_DIR -u CHATLINK_BUG_REPORT_FILE \
    "$CODEAGENT" --dry-run invoke explore-relay
assert_eq "no --headless: nonzero exit" "1" "$RUN_RC"
assert_contains "no --headless: billing refusal reason" "$RUN_OUT" \
    "explore-relay is headless-only"

# --- 2: distinct env-precondition refusals ---
run -u CHATLINK_RELAY_DIR -u CHATLINK_BUG_REPORT_FILE \
    "$CODEAGENT" --dry-run --headless invoke explore-relay
assert_eq "missing relay dir: nonzero exit" "1" "$RUN_RC"
assert_contains "missing relay dir: distinct reason" "$RUN_OUT" \
    "CHATLINK_RELAY_DIR"

run -u CHATLINK_BUG_REPORT_FILE CHATLINK_RELAY_DIR="$TMP/relaydir" \
    "$CODEAGENT" --dry-run --headless invoke explore-relay
assert_eq "missing bug report: nonzero exit" "1" "$RUN_RC"
assert_contains "missing bug report: distinct reason" "$RUN_OUT" \
    "CHATLINK_BUG_REPORT_FILE"

# relay dir set but not a directory → same fail-closed refusal
run CHATLINK_RELAY_DIR="$TMP/nonexistent" \
    CHATLINK_BUG_REPORT_FILE="$TMP/bug.md" \
    "$CODEAGENT" --dry-run --headless invoke explore-relay
assert_eq "relay dir not a directory: nonzero exit" "1" "$RUN_RC"
assert_contains "relay dir not a directory: same reason" "$RUN_OUT" \
    "CHATLINK_RELAY_DIR"

# --- 3: exact argv construction (dry-run seam) ---
run CHATLINK_RELAY_DIR="$TMP/relaydir" \
    CHATLINK_BUG_REPORT_FILE="$TMP/bug.md" \
    "$CODEAGENT" --dry-run --headless invoke explore-relay
assert_eq "valid invoke: exit 0" "0" "$RUN_RC"
assert_contains "argv: DRY_RUN line" "$RUN_OUT" "DRY_RUN:"
assert_contains "argv: env-prefixed default tool timeout" "$RUN_OUT" \
    "env BASH_DEFAULT_TIMEOUT_MS=630000"
assert_contains "argv: env-prefixed max tool timeout" "$RUN_OUT" \
    "BASH_MAX_TIMEOUT_MS=630000"
assert_contains "argv: headless print mode" "$RUN_OUT" " --print"
assert_contains "argv: allowed tools for headless" "$RUN_OUT" \
    "--allowedTools Bash\\,Read\\,Write\\,Glob\\,Grep"
assert_contains "argv: natural slash command" "$RUN_OUT" \
    "/aitask-explorechat"
# Ordering is load-bearing (caught live): --allowedTools is variadic and
# swallows a trailing positional prompt, so the prompt MUST come first.
case "$RUN_OUT" in
    *"/aitask-explorechat --allowedTools"*)
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "ok - argv: prompt precedes variadic --allowedTools"
        ;;
    *)
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "FAIL - argv: prompt must precede --allowedTools: $RUN_OUT"
        ;;
esac

# --- 4: codex/opencode → honest "not yet supported" refusals ---
run CHATLINK_RELAY_DIR="$TMP/relaydir" \
    CHATLINK_BUG_REPORT_FILE="$TMP/bug.md" \
    "$CODEAGENT" --dry-run --headless --agent-string codex/gpt5_4 \
    invoke explore-relay
assert_eq "codex: nonzero exit" "1" "$RUN_RC"
assert_contains "codex: not-yet-supported reason" "$RUN_OUT" \
    "not yet supported for codex"

run CHATLINK_RELAY_DIR="$TMP/relaydir" \
    CHATLINK_BUG_REPORT_FILE="$TMP/bug.md" \
    "$CODEAGENT" --dry-run --headless \
    --agent-string opencode/openai_gpt_5_1_codex \
    invoke explore-relay
assert_eq "opencode: nonzero exit" "1" "$RUN_RC"
assert_contains "opencode: not-yet-supported reason" "$RUN_OUT" \
    "not yet supported for opencode"

# --- 5: regression guard — existing operations still dispatch ---
run "$CODEAGENT" --dry-run invoke pick 42
assert_eq "regression: pick dispatches" "0" "$RUN_RC"
assert_contains "regression: pick argv intact" "$RUN_OUT" "/aitask-pick"

run "$CODEAGENT" --dry-run invoke raw -p "hello"
assert_eq "regression: raw dispatches" "0" "$RUN_RC"

run "$CODEAGENT" --dry-run --headless invoke batch-review src/
assert_eq "regression: batch-review --headless dispatches" "0" "$RUN_RC"
assert_contains "regression: batch-review headless keeps --print" \
    "$RUN_OUT" " --print"

run "$CODEAGENT" --dry-run invoke bogus-op
assert_eq "regression: unknown op still refused" "1" "$RUN_RC"
assert_contains "regression: unknown op lists explore-relay as supported" \
    "$RUN_OUT" "explore-relay"

# --- 6: env-name drift guard — the SESSION_DIR-suffixed variant was
# deliberately eliminated (single canonical CHATLINK_RELAY_DIR; see
# p1120_4). It must never reappear on any surface. (Token split so this
# guard does not match its own source.)
DRIFT_TOKEN="CHATLINK_SESSION""_DIR"
if grep -rn "$DRIFT_TOKEN" \
    "$PROJECT_DIR/.aitask-scripts" "$PROJECT_DIR/.claude" \
    "$PROJECT_DIR/tests" "$PROJECT_DIR/aidocs" 2>/dev/null \
    | grep -v __pycache__ | grep -q .; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "FAIL - env drift: $DRIFT_TOKEN reappeared"
else
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "ok - env drift: no $DRIFT_TOKEN anywhere"
fi

# ---------------------------------------------------------------------------
# 7: LIVE smoke (opt-in: RUN_LIVE_EXPLORE_RELAY=1) — one REAL headless
# `claude --print /aitask-explorechat` run. Billed call; skipped by default.
# Proves the two links no dry-run/fake-agent test can reach:
#   (a) slash-command discovery + --allowedTools in print mode;
#   (b) the BASH_*_TIMEOUT_MS exports carry a real skill invocation past
#       the ~120 s default Bash-tool timeout (the answer to the FIRST
#       question is deliberately delayed > 150 s).
# The ≥1-question guarantee is structural: the skill's final confirmation
# question is NON-SKIPPABLE, so a question always appears.
# ---------------------------------------------------------------------------

if [ "${RUN_LIVE_EXPLORE_RELAY:-0}" = "1" ]; then
    echo ""
    echo "--- live smoke (RUN_LIVE_EXPLORE_RELAY=1) ---"
    LIVE_DIR="$TMP/slive01"
    mkdir -p "$LIVE_DIR"
    cat > "$TMP/live_bug.md" <<'EOF'
The relay ask helper (.aitask-scripts/aitask_relay_ask.sh) sometimes seems
to print VALUE lines even after a timeout. I expected STATUS:timeout to
carry no VALUE lines at all. Seen once; not sure if my invocation was wrong.
EOF

    CHATLINK_RELAY_DIR="$LIVE_DIR" CHATLINK_BUG_REPORT_FILE="$TMP/live_bug.md" \
        "$CODEAGENT" --headless invoke explore-relay \
        > "$TMP/live_out.txt" 2>&1 &
    LIVE_PID=$!

    answer_question() {  # $1 = seq; generic strategy: first option, else free text
        python3 - "$LIVE_DIR" "$1" <<'PYEOF'
import json, sys
from pathlib import Path
d = Path(sys.argv[1]); seq = sys.argv[2]
if (d / f"answer-{seq}.json").exists():
    sys.exit(0)   # never clobber (e.g. a helper-written timeout answer)
q = json.load(open(d / f"question-{seq}.json"))
a = {"id": q["id"], "seq": q["seq"], "status": "answered",
     "answered_by": "live-smoke"}
if q["options"]:
    a["values"] = [q["options"][0]["value"]]; a["free_text"] = None
else:
    a["values"] = []; a["free_text"] = "proceed as you see fit"
tmp = d / f"answer-{seq}.json.smoke.tmp2"
tmp.write_text(json.dumps(a))
tmp.rename(d / f"answer-{seq}.json")
PYEOF
    }

    # Wait for the FIRST question (exploration may take a few minutes)
    FIRST_SEQ=""
    for _ in $(seq 1 360); do   # up to 6 min
        for qf in "$LIVE_DIR"/question-*.json; do
            [ -e "$qf" ] || continue
            seqno="${qf##*question-}"; seqno="${seqno%.json}"
            [ -f "$LIVE_DIR/answer-$seqno.json" ] || { FIRST_SEQ="$seqno"; break; }
        done
        [ -n "$FIRST_SEQ" ] && break
        kill -0 "$LIVE_PID" 2>/dev/null || break
        sleep 1
    done
    assert_eq "live: a question appeared (structural ≥1 guarantee)" "1" \
        "$([ -n "$FIRST_SEQ" ] && echo 1 || echo 0)"

    if [ -n "$FIRST_SEQ" ]; then
        # (b) delayed-answer leg: hold the first answer past the ~120 s
        # default tool timeout, then answer.
        echo "live: delaying answer to question-$FIRST_SEQ by 160 s..."
        sleep 160
        # Negative control BEFORE we answer: if the default tool timeout had
        # killed the helper (~120 s), the skill would have moved on — a
        # later question, a helper/timeout answer for this seq, or the
        # payload would already exist. Still-blocked = the BASH_*_TIMEOUT_MS
        # exports held.
        NEXT_SEQ=$((FIRST_SEQ + 1))
        STILL_BLOCKED=1
        [ -f "$LIVE_DIR/question-$NEXT_SEQ.json" ] && STILL_BLOCKED=0
        [ -f "$LIVE_DIR/answer-$FIRST_SEQ.json" ] && STILL_BLOCKED=0
        [ -f "$LIVE_DIR/payload.json" ] && STILL_BLOCKED=0
        assert_eq "live: agent still blocked at 160 s (tool-timeout exports held)" \
            "1" "$STILL_BLOCKED"
        answer_question "$FIRST_SEQ"
        # Answer any subsequent questions promptly; wait for payload/exit.
        for _ in $(seq 1 360); do   # up to a further 6 min
            for qf in "$LIVE_DIR"/question-*.json; do
                [ -e "$qf" ] || continue
                seqno="${qf##*question-}"; seqno="${seqno%.json}"
                [ -f "$LIVE_DIR/answer-$seqno.json" ] || answer_question "$seqno"
            done
            [ -f "$LIVE_DIR/payload.json" ] && ! kill -0 "$LIVE_PID" 2>/dev/null && break
            kill -0 "$LIVE_PID" 2>/dev/null || { sleep 2; break; }
            sleep 1
        done
    fi

    wait "$LIVE_PID" && LIVE_RC=0 || LIVE_RC=$?
    assert_eq "live: agent exit 0" "0" "$LIVE_RC"
    assert_eq "live: payload.json landed" "1" \
        "$([ -f "$LIVE_DIR/payload.json" ] && echo 1 || echo 0)"
    if [ -f "$LIVE_DIR/payload.json" ]; then
        LIVE_CONFORM="$(python3 - "$PROJECT_DIR" "$LIVE_DIR/payload.json" <<'PYEOF'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / ".aitask-scripts"))
from chatlink.relay import TaskPayload
TaskPayload.from_dict(json.load(open(sys.argv[2])))
print("LIVE_PAYLOAD_OK")
PYEOF
)"
        assert_eq "live: payload validates via shared schema" \
            "LIVE_PAYLOAD_OK" "$LIVE_CONFORM"
        # First answer was delayed >150s: if the helper had been killed by
        # the default tool timeout, answer-<first> would be a helper-written
        # status:timeout instead of our answered write landing first.
        assert_contains "live: delayed answer consumed as answered" \
            "$(cat "$LIVE_DIR/answer-$FIRST_SEQ.json")" '"answered"'
    fi
else
    echo "skip - live smoke (set RUN_LIVE_EXPLORE_RELAY=1 to run; billed headless call)"
fi

echo ""
echo "PASS: $PASS_COUNT, FAIL: $FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
