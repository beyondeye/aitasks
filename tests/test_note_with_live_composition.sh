#!/usr/bin/env bash
# test_note_with_live_composition.sh — the writer -> resolver composition (t1657_5)
#
# t1657_4 RELOCATED two acceptance criteria here, because neither is assertable
# from the resolver: the resolver never appends a note and never calls
# SendMessage, so only the composition owner can observe durable-first ordering.
#
#   1. WRITE-BEFORE-LIVE. For every result the resolver can return, `ait note`
#      has already emitted NOTE_APPENDED: and committed before the resolver is
#      invoked at all.
#   2. THE DURABLE RESULT IS AUTHORITATIVE. A live lane that finds nothing — or
#      that cannot run — is a SUCCESS with live delivery unavailable, never a
#      partial failure.
#
# What is asserted here, and what is deliberately NOT:
#
# Everything up to and including LIVE_PANE: is reachable from a shell and is
# pinned below, positive case included. Everything PAST it — the SendMessage
# call, the payload's contents, LIVE_QUEUED — is a model-facing adapter
# procedure with no CLI, so it cannot be forced from here. That half is pinned
# two ways instead: §6 asserts the SKILL.md an agent actually reads STATES the
# reporting rules (the test_live_endpoint_no_sendkeys.sh precedent), and
# t1657_7 carries the live two-session manual item.
#
# §7 exists because goldens cannot do its job. A golden is generated FROM the
# template it checks, so deleting a trigger-point offer and regenerating leaves
# the suite green with the offer gone. Only an independent per-profile assertion
# can pin "this line survives every profile".
#
# Run: bash tests/test_note_with_live_composition.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/pid_anchor.sh
. "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"

PASS=0
FAIL=0
TOTAL=0

NOTE="$PROJECT_DIR/.aitask-scripts/aitask_note.sh"

# Private lock base, the documented isolation seam (t1496).
AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_note_live_lockbase_XXXXXX")"
export AITASKS_LOCK_DIR

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_note_live_XXXXXX")"
# shellcheck disable=SC2329  # invoked indirectly, by the EXIT trap below
cleanup() { rm -rf "$TMP" "$AITASKS_LOCK_DIR"; }
trap cleanup EXIT

# --- fixture ---------------------------------------------------------------
#
# Two repos, the same split test_note_append.sh uses: a CODE repo for the note's
# provenance capture (AIT_DIR), and a task-DATA repo cloned from a bare remote
# (aitask_lock.sh keeps locks on an orphan branch and refuses without an origin).

CODE="$TMP/code"
mkdir -p "$CODE"
git -C "$CODE" init -q -b main
git -C "$CODE" config user.email t@example.com
git -C "$CODE" config user.name Test
echo one > "$CODE/f.txt"
git -C "$CODE" add -A && git -C "$CODE" commit -qm first

REMOTE="$TMP/remote.git"
git init -q --bare -b main "$REMOTE"
DATA="$TMP/data"
git clone -q "$REMOTE" "$DATA" 2>/dev/null
mkdir -p "$DATA/aitasks"
git -C "$DATA" config user.email t@example.com
git -C "$DATA" config user.name Test

# <id> <implemented_with value, or "" for none>
make_task() {
    local id="$1" impl="${2:-}"
    {
        echo "---"
        echo "status: Implementing"
        [[ -n "$impl" ]] && echo "implemented_with: $impl"
        echo "---"
        echo "Body for t${id}."
    } > "$DATA/aitasks/t${id}_x.md"
}

# 900 is the target throughout; 901 is the sender. 902/903 vary the agent gate.
make_task 900 "claudecode/opus5"
make_task 901 ""
make_task 902 ""                  # implemented_with empty -> agent_unknown
make_task 903 "codex/gpt-5.4"     # a family with no adapter
git -C "$DATA" add -A && git -C "$DATA" commit -qm tasks
git -C "$DATA" push -q origin main 2>/dev/null || true
( cd "$DATA" && "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" --init ) >/dev/null 2>&1 || true

# Write <yaml> as t<id>_lock.yaml on the fixture's lock branch — the same
# plumbing-only seam test_live_endpoint_degradation.sh uses. remote_host,
# holder_dead and holder_unknown cannot arise from a real claim on this machine,
# so forging is the only way to reach them.
forge_lock() {
    local id="$1" yaml="$2"
    (
        cd "$DATA" || exit 1
        git fetch -q origin aitask-locks 2>/dev/null || true
        local parent blob newtree commit
        parent="$(git rev-parse origin/aitask-locks 2>/dev/null || true)"
        blob="$(printf '%s' "$yaml" | git hash-object -w --stdin)"
        newtree="$(
            {
                [[ -n "$parent" ]] && git ls-tree origin/aitask-locks \
                    | grep -v "$(printf '\t')t${id}_lock.yaml\$"
                printf '100644 blob %s\tt%s_lock.yaml\n' "$blob" "$id"
            } | git mktree
        )"
        if [[ -n "$parent" ]]; then
            commit="$(echo forge | git commit-tree "$newtree" -p "$parent")"
        else
            commit="$(echo forge | git commit-tree "$newtree")"
        fi
        git push -q --force origin "$commit:refs/heads/aitask-locks"
    )
}

THIS_HOST="$(hostname)"
DEAD_PID="$( ( sleep 0 & echo $! ) )"
wait 2>/dev/null || true
LIVE_PID=$$
LIVE_TOKEN="$(get_pid_starttime "$LIVE_PID")"
LIVE_KIND="$(get_pid_starttime_kind "$LIVE_PID")"

# Run the REAL entry point inside the data repo. Never a replica of the
# composition: a test that re-implemented the order would pass no matter what
# the script did.
run_note() { ( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" "$@" ); }

task_body() { cat "$DATA/aitasks/t${1}_x.md"; }
line1() { printf '%s\n' "$1" | sed -n '1p'; }
line2() { printf '%s\n' "$1" | sed -n '2p'; }
nlines() { printf '%s\n' "$1" | grep -c . ; }

# Assert the shared shape of every write-before-live case in one place, so each
# case below states only what is specific to it.
#
# <label-prefix> <stdout> <rc> <expected line 2>
assert_durable_first() {
    local p="$1" out="$2" rc="$3" want2="$4"
    assert_eq "$p durable line comes FIRST" \
        "1" "$(printf '%s\n' "$(line1 "$out")" | grep -c '^NOTE_APPENDED:')"
    assert_eq "$p live line is the resolver's answer, verbatim" "$want2" "$(line2 "$out")"
    assert_eq "$p exactly two lines" "2" "$(nlines "$out")"
    assert_eq "$p exit follows the DURABLE lane" "0" "$rc"

    # The id-bearing line is only a claim until the note is on disk AND
    # committed. Both are checked, because an uncommitted note is a different
    # (id-bearing, non-zero) outcome that must never reach this path.
    local id="${out#NOTE_APPENDED:}"; id="${id%%|*}"
    assert_contains "$p the note is in the target's Inbox" "id=$id" "$(task_body 900)"
    assert_eq "$p …and the task file is committed" \
        "" "$(git -C "$DATA" status --porcelain -- aitasks/t900_x.md)"
}

set +e

echo "=== ait note --with-live: the composition contract (t1657_5) ==="
echo ""

# --- 1. WRITE-BEFORE-LIVE, over every LIVE_NONE reason ---------------------
#
# The complete enumeration from t1657_4's degradation table. Each one is a
# DEGRADATION, not an error: the note is durable in every single case.

echo "--- 1. write-before-live, all 7 LIVE_NONE reasons ---"

# Runs FIRST, on the fixture's own initial state: `unlocked` means no lock
# RECORD at all, so it cannot be reached by forging one.
out="$(run_note 900 --from 901 --with-live --text "unlocked case" 2>/dev/null)"; rc=$?
assert_durable_first "1a." "$out" "$rc" "LIVE_NONE:unlocked"

forge_lock 900 "task_id: 900
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: some-other-host
pid: $LIVE_PID
pid_starttime: $LIVE_TOKEN
pid_starttime_kind: $LIVE_KIND
"
out="$(run_note 900 --from 901 --with-live --text "remote host case" 2>/dev/null)"; rc=$?
assert_durable_first "1b." "$out" "$rc" "LIVE_NONE:remote_host"

forge_lock 900 "task_id: 900
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: $THIS_HOST
pid: $DEAD_PID
pid_starttime: 999999999
pid_starttime_kind: proc
"
out="$(run_note 900 --from 901 --with-live --text "holder dead case" 2>/dev/null)"; rc=$?
assert_durable_first "1c." "$out" "$rc" "LIVE_NONE:holder_dead"

# `unknown` is never collapsed into `dead` (the t1465 defect class): "I cannot
# tell" and "nobody is there" are different answers to a sender.
forge_lock 900 "task_id: 900
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: $THIS_HOST
pid: $LIVE_PID
pid_starttime: definitely-not-this-processes-token
pid_starttime_kind: unrecognised-kind
"
out="$(run_note 900 --from 901 --with-live --text "holder unknown case" 2>/dev/null)"; rc=$?
assert_durable_first "1d." "$out" "$rc" "LIVE_NONE:holder_unknown"

# A live, local, alive holder from here on, so the AGENT gate is what decides.
live_lock() {
    forge_lock "$1" "task_id: $1
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: $THIS_HOST
pid: $LIVE_PID
pid_starttime: $LIVE_TOKEN
pid_starttime_kind: $LIVE_KIND
"
}

# agent_unknown is the Step 4 -> Step 7 attribution window: locked, local and
# alive, but `implemented_with` is not written until Step 7. It must read as
# unavailable, never as an error.
sed -i.bak '/implemented_with/d' "$DATA/aitasks/t900_x.md" && rm -f "$DATA/aitasks/t900_x.md.bak"
git -C "$DATA" add -A && git -C "$DATA" commit -qm "clear impl" >/dev/null 2>&1
live_lock 900
out="$(run_note 900 --from 901 --with-live --text "agent unknown case" 2>/dev/null)"; rc=$?
assert_durable_first "1e." "$out" "$rc" "LIVE_NONE:agent_unknown"

# A family the manifest does not carry. Restore attribution first, as a codex one.
python3 - "$DATA/aitasks/t900_x.md" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace("status: Implementing\n", "status: Implementing\nimplemented_with: codex/gpt-5.4\n", 1)
open(p, "w").write(s)
PY
git -C "$DATA" add -A && git -C "$DATA" commit -qm "codex impl" >/dev/null 2>&1
out="$(run_note 900 --from 901 --with-live --text "unsupported agent case" 2>/dev/null)"; rc=$?
assert_durable_first "1f." "$out" "$rc" "LIVE_NONE:agent_unsupported:codex"

# no_pane: a claudecode holder, alive and local, but the tmux gateway points at
# a server that does not exist, so no pane map can be built.
python3 - "$DATA/aitasks/t900_x.md" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read().replace("codex/gpt-5.4", "claudecode/opus5", 1)
open(p, "w").write(s)
PY
git -C "$DATA" add -A && git -C "$DATA" commit -qm "claudecode impl" >/dev/null 2>&1
out="$( cd "$DATA" && AIT_DIR="$CODE" AITASKS_TMUX_SOCKET="ait_nonexistent_$$" \
        "$NOTE" 900 --from 901 --with-live --text "no pane case" 2>/dev/null )"; rc=$?
assert_durable_first "1g." "$out" "$rc" "LIVE_NONE:no_pane"

# --- 2. The errexit regression --------------------------------------------
#
# The resolver DELIBERATELY exits 2 on LIVE_ERROR:*, and aitask_note.sh runs
# under `set -euo pipefail`. A bare invocation or a plain "$( )" capture would
# abort HERE — after the append and the commit — leaving the caller a
# NOTE_APPENDED: line, no second line, and a non-zero status. That is the
# failure this whole group exists to catch, and it is invisible to §1 because
# every reason there exits 0.
#
# It also has to be forced. All three LIVE_ERROR reasons are UNREACHABLE through
# the real composition by construction: `usage` and `bad_task_id` cannot occur
# because `ait note` validates and canonicalizes the id before the resolver is
# called, and `task_not_found` cannot occur because a missing target returns
# NOTE_TARGET_MISSING: and short-circuits the live lane entirely. AIT_LIVE_ENDPOINT_SH
# is the documented seam, so the coverage is honest rather than a real path
# dressed up as one.

echo ""
echo "--- 2. a resolver that exits 2 must not abort the caller ---"

STUBS="$TMP/stubs"; mkdir -p "$STUBS"

cat > "$STUBS/exit2.sh" <<'EOS'
#!/usr/bin/env bash
echo "LIVE_ERROR:task_not_found:999"
exit 2
EOS
cat > "$STUBS/silent_exit2.sh" <<'EOS'
#!/usr/bin/env bash
exit 2
EOS
cat > "$STUBS/garbage.sh" <<'EOS'
#!/usr/bin/env bash
echo "who knows what this is"
exit 0
EOS
cat > "$STUBS/three_lines.sh" <<'EOS'
#!/usr/bin/env bash
echo "LIVE_NONE:unlocked"
echo "second line that must be ignored"
echo "third line too"
exit 0
EOS
cat > "$STUBS/counter.sh" <<'EOS'
#!/usr/bin/env bash
echo called >> "$STUB_CALL_LOG"
echo "LIVE_NONE:unlocked"
EOS
chmod +x "$STUBS"/*.sh

run_note_stub() {   # <stub> <note args...>
    local stub="$1"; shift
    ( cd "$DATA" && AIT_DIR="$CODE" AIT_LIVE_ENDPOINT_SH="$STUBS/$stub" "$NOTE" "$@" )
}

out="$(run_note_stub exit2.sh 900 --from 901 --with-live --text "exit2" 2>/dev/null)"; rc=$?
assert_durable_first "2a." "$out" "$rc" "LIVE_ERROR:task_not_found:999"

out="$(run_note_stub silent_exit2.sh 900 --from 901 --with-live --text "silent" 2>/dev/null)"; rc=$?
assert_durable_first "2b." "$out" "$rc" "LIVE_ERROR:resolver_unavailable"

# An unparseable answer is NOT "no live endpoint". Reporting it as LIVE_NONE
# would make a broken resolver indistinguishable from an idle task.
out="$(run_note_stub garbage.sh 900 --from 901 --with-live --text "garbage" 2>/dev/null)"; rc=$?
assert_durable_first "2c." "$out" "$rc" "LIVE_ERROR:resolver_unavailable"

out="$(run_note_stub three_lines.sh 900 --from 901 --with-live --text "three" 2>/dev/null)"; rc=$?
assert_durable_first "2d." "$out" "$rc" "LIVE_NONE:unlocked"

# A resolver that does not exist at all lands on the same branch.
out="$(run_note_stub does_not_exist.sh 900 --from 901 --with-live --text "absent" 2>/dev/null)"; rc=$?
assert_durable_first "2e." "$out" "$rc" "LIVE_ERROR:resolver_unavailable"

# --- 3. The POSITIVE branch, against a real pane --------------------------
#
# §1 and §2 only ever prove the DEGRADED answers. Without this, a composition
# that could never produce a usable endpoint would pass every other case here.

echo ""
echo "--- 3. the positive LIVE_PANE branch ---"

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — the positive live branch is not exercised"
else
    # shellcheck source=lib/tmux_isolation.sh
    . "$SCRIPT_DIR/lib/tmux_isolation.sh"
    require_isolated_tmux
    unset AIT_AGENT_PID

    SOCK="ait_notelive_$$"
    # shellcheck disable=SC2329  # invoked indirectly, by the EXIT trap below
    cleanup() { tmux -L "$SOCK" kill-server 2>/dev/null || true; rm -rf "$TMP" "$AITASKS_LOCK_DIR"; }

    # The claim runs as the pane's OWN command, so tmux supplies $TMUX and
    # $TMUX_PANE and the lock anchors to the pane process by construction.
    # Setting them by hand would test the fixture instead.
    claim_cmd="cd '$DATA' && AITASKS_LOCK_DIR='$AITASKS_LOCK_DIR'"
    claim_cmd="$claim_cmd AITASKS_TMUX_SOCKET='$SOCK'"
    claim_cmd="$claim_cmd '$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh' 902 --email 'alice@test.com'"
    claim_cmd="$claim_cmd > claim.out 2>&1; echo \$? > claim.rc; sleep 300"
    tmux -L "$SOCK" new-session -d -x 80 -y 10 -n notelive "$claim_cmd" 2>/dev/null

    PANE_PID=""
    for _ in $(seq 1 30); do
        PANE_PID=$(tmux -L "$SOCK" list-panes -F '#{pane_pid}' 2>/dev/null | head -1)
        [[ -n "$PANE_PID" ]] && break
        sleep 0.2
    done
    for _ in $(seq 1 120); do [[ -s "$DATA/claim.rc" ]] && break; sleep 0.25; done

    if [[ -z "$PANE_PID" || ! -s "$DATA/claim.rc" ]]; then
        TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
        echo "FAIL: 3-setup could not start a pane / finish the in-pane claim"
    else
        # ORDERING CONTROL, run FIRST — while the task is in exactly the state a
        # real claim leaves it: locked, Implementing, `implemented_with` still
        # empty because Step 7 has not run. If this did not answer agent_unknown,
        # the positive case below would prove nothing about the seed.
        out="$( cd "$DATA" && AIT_DIR="$CODE" AITASKS_TMUX_SOCKET="$SOCK" \
                "$NOTE" 902 --from 901 --with-live --text "control" 2>/dev/null )"; rc=$?
        assert_eq "3a. CONTROL: unseeded attribution short-circuits at the agent gate" \
            "LIVE_NONE:agent_unknown" "$(line2 "$out")"
        assert_eq "3b. CONTROL: still a durable success" "0" "$rc"

        # Independent ground truth, read from tmux rather than rebuilt from the
        # resolver's own format. `#{window_id}` already carries its '@'.
        PANE_ID="$(tmux -L "$SOCK" list-panes -a -F '#{pane_id}' 2>/dev/null | head -1)"
        EXPECT_TARGET="$(tmux -L "$SOCK" list-panes -a \
            -F '#{session_name}:#{window_id}.#{pane_id}' 2>/dev/null | head -1)"

        python3 - "$DATA/aitasks/t902_x.md" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
if "implemented_with" not in s:
    s = s.replace("status: Implementing\n",
                  "status: Implementing\nimplemented_with: claudecode/opus5\n", 1)
open(p, "w").write(s)
PY
        git -C "$DATA" add -A && git -C "$DATA" commit -qm "seed impl 902" >/dev/null 2>&1

        out="$( cd "$DATA" && AIT_DIR="$CODE" AITASKS_TMUX_SOCKET="$SOCK" \
                "$NOTE" 902 --from 901 --with-live --text "positive" 2>/dev/null )"; rc=$?

        assert_eq "3c. durable line still comes first" \
            "1" "$(printf '%s\n' "$(line1 "$out")" | grep -c '^NOTE_APPENDED:')"
        assert_eq "3d. exactly two lines" "2" "$(nlines "$out")"
        assert_eq "3e. exit 0" "0" "$rc"
        assert_eq "3f. the WHOLE live line, built from tmux's own rendering" \
            "LIVE_PANE:${PANE_ID}|${EXPECT_TARGET}|${PANE_PID}|agent=claudecode" \
            "$(line2 "$out")"

        # The adapter joins on the pane id alone, so it must be present as such.
        got_target="$(line2 "$out")"; got_target="${got_target#LIVE_PANE:*|}"
        got_target="${got_target%%|*}"
        assert_contains "3g. the target ends in the pane id (the adapter's join key)" \
            ".$PANE_ID" "$got_target"

        note_id="$(line1 "$out")"; note_id="${note_id#NOTE_APPENDED:}"; note_id="${note_id%%|*}"
        assert_contains "3h. the durable entry the adapter must name exists on disk" \
            "id=$note_id" "$(task_body 902)"
    fi
fi

# --- 4. A failed durable write must NOT reach the resolver ----------------
#
# The other half of write-before-live: if the note did not land, there is
# nothing to tell anyone about, and the live lane must not run at all.

echo ""
echo "--- 4. durable failure short-circuits the live lane ---"

STUB_CALL_LOG="$TMP/calls.log"; export STUB_CALL_LOG
: > "$STUB_CALL_LOG"

out="$(run_note_stub counter.sh 999999 --from 901 --with-live --text "missing" 2>/dev/null)"; rc=$?
assert_eq "4a. missing target reports the durable outcome" "NOTE_TARGET_MISSING:999999" "$out"
assert_eq "4b. …on exactly one line" "1" "$(nlines "$out")"
assert_exit_nonzero_rc "4c. …and a non-zero exit" "$rc"
assert_eq "4d. the resolver was never invoked" "0" "$(grep -c . "$STUB_CALL_LOG")"

: > "$STUB_CALL_LOG"
out="$( cd "$DATA" && AIT_DIR="$CODE" AIT_LIVE_ENDPOINT_SH="$STUBS/counter.sh" \
        AIT_NOTE_FAIL_AFTER_APPEND=1 \
        "$NOTE" 900 --from 901 --with-live --text "post-append failure" 2>/dev/null )"; rc=$?
assert_contains "4e. a post-append failure is id-bearing" "NOTE_APPENDED_UNCOMMITTED:" "$out"
assert_eq "4f. …on exactly one line" "1" "$(nlines "$out")"
assert_exit_nonzero_rc "4g. …and a non-zero exit" "$rc"
assert_eq "4h. an UNCOMMITTED note never reaches the live lane" \
    "0" "$(grep -c . "$STUB_CALL_LOG")"

# --- 5. mitigation `default_path_one_line_control` ------------------------
#
# The default path must be untouched. Without this, the one-line contract that
# three other surfaces parse could regress silently the moment the live lane
# grew a second line.

echo ""
echo "--- 5. the default path is still exactly one line ---"

: > "$STUB_CALL_LOG"
out="$( cd "$DATA" && AIT_DIR="$CODE" AIT_LIVE_ENDPOINT_SH="$STUBS/counter.sh" \
        "$NOTE" 900 --from 901 --text "no flag" 2>/dev/null )"; rc=$?
assert_eq "5a. without --with-live, exactly one line" "1" "$(nlines "$out")"
assert_eq "5b. …and it is the durable line" \
    "1" "$(printf '%s\n' "$out" | grep -c '^NOTE_APPENDED:')"
assert_exit_zero_rc "5c. …exit 0" "$rc"
assert_eq "5d. the resolver is not invoked without the flag" \
    "0" "$(grep -c . "$STUB_CALL_LOG")"

assert_contains "5e. --with-live is refused twice over" \
    "NOTE_ERROR:duplicate-option:--with-live" \
    "$(run_note 900 --from 901 --with-live --with-live --text x 2>/dev/null)"

# --- 6. mitigation `skill_prose_contract_test` ----------------------------
#
# Everything past LIVE_PANE: is a model-facing procedure with no CLI, so the
# reporting rules can only be pinned in the artifact an agent actually reads.
# Same shape as test_live_endpoint_no_sendkeys.sh's adapter checks.

echo ""
echo "--- 6. the skill STATES its reporting rules ---"

SKILL="$PROJECT_DIR/.claude/skills/aitask-note/SKILL.md"
assert_file_exists "6a. the skill exists" "$SKILL"
skill_body="$(cat "$SKILL" 2>/dev/null)"

assert_contains_re "6b. the description conveys WHEN, not just what" \
    '^description:.*[Uu]se when' "$skill_body"
assert_contains_re "6c. it is user-invocable" '^user-invocable: true$' "$skill_body"
assert_contains_re "6d. the durable result is stated as authoritative" \
    '[Tt]he durable result is authoritative' "$skill_body"
assert_contains_re "6e. LIVE_NONE after a write is stated as a SUCCESS" \
    'LIVE_NONE.{0,80}success' "$skill_body"
assert_contains_re "6f. …and explicitly not a partial failure" \
    'never a partial failure' "$skill_body"
assert_contains_re "6g. LIVE_QUEUED is enqueued, never read" \
    'LIVE_QUEUED.{0,60}enqueued, never read' "$skill_body"
assert_contains_re "6h. a note is never auto-actioned" \
    'never auto-actioned' "$skill_body"
assert_contains_re "6i. from= is stated to be a claim" \
    '`from=` is a claim' "$skill_body"
assert_contains "6j. it reuses Related Task Discovery rather than rematching" \
    "task-workflow/related-task-discovery.md" "$skill_body"
assert_contains "6k. it composes through the fused seam" "--with-live" "$skill_body"
assert_contains "6l. delivery is delegated to the manifest's adapter" \
    "live_delivery/agents.txt" "$skill_body"
# tmux identifies the endpoint; it is never the transport.
assert_contains "6m. send-keys is named and prohibited" "send-keys" "$skill_body"
assert_contains_re "6n. …and the prohibition sits on the same line as the verb" \
    '(never|not|prohibited).{0,60}send-keys|send-keys.{0,60}(never|not|prohibited)' \
    "$skill_body"

# --- 7. trigger-point offers survive EVERY profile ------------------------
#
# Goldens cannot assert this: a golden is generated FROM the template it checks,
# so deleting an offer and regenerating leaves the suite green with the offer
# gone. Exactly-once, not merely present — that also pins that an offer was not
# duplicated into both arms of a conditional.
#
# The two sites that make this load-bearing: task-workflow's Step 8d sits inside
# `{% if 'risk_evaluated' in rendered_set %}` and aitask-review's Step 5 inside
# `{% if profile.review_auto_continue %}`. An offer placed inside either renders
# for one profile and vanishes for another.

echo ""
echo "--- 7. the /aitask-note offer renders under every profile ---"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
AIT_PY="$(require_ait_python 2>/dev/null)"
if [[ -z "$AIT_PY" ]] || ! "$AIT_PY" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in the framework venv — run 'ait setup'"
else
    render_of() {  # <authored file>  <profile>
        "$AIT_PY" "$PROJECT_DIR/.aitask-scripts/lib/skill_template.py" \
            "$PROJECT_DIR/$1" \
            "$PROJECT_DIR/aitasks/metadata/profiles/$2.yaml" claude 2>/dev/null
    }
    for site in \
        "task-workflow:.claude/skills/task-workflow/SKILL.md" \
        "aitask-qa:.claude/skills/aitask-qa/SKILL.md.j2" \
        "aitask-review:.claude/skills/aitask-review/SKILL.md.j2"
    do
        name="${site%%:*}"; file="${site#*:}"
        for profile in default fast remote; do
            assert_eq "7. ${name} (${profile}) offers /aitask-note exactly once" \
                "1" "$(render_of "$file" "$profile" | grep -c '/aitask-note')"
        done
    done

    # The COMMITTED rendered closure, which is the artifact that actually ships.
    # A stale `aitask_skill_rerender.sh remote` is invisible to every check
    # above, because those all re-render from the template on the spot.
    assert_eq "7z. the committed task-workflow-remote- closure carries it too" \
        "1" "$(grep -c '/aitask-note' \
                "$PROJECT_DIR/.claude/skills/task-workflow-remote-/SKILL.md" 2>/dev/null)"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "SOME TESTS FAILED"
    exit 1
fi
