#!/usr/bin/env bash
# test_brainstorm_addwork_deadline.sh - brainstorm's registration deadline (t2024).
#
# brainstorm_crew._run_addwork bounds `ait crew addwork`. On expiry it sends a
# STOP REQUEST (SIGTERM to addwork alone), which addwork honours between steps:
# writing and committing the registration and the rebase always finish, a
# fetch/push in flight ends within its own bound, and the rest of publishing is
# skipped. Only an addwork still running _ADDWORK_STOP_GRACE_S later (a hung
# hook or signing step) is killed, and _addwork_outcome then reads the crew
# worktree back.
#
# Every cell drives the real _run_addwork (through a stub ./ait that execs the
# real aitask_crew_addwork.sh) with the deadline and stop grace patched short:
#   D1  the deadline expires during a slow pre-commit hook
#   D2  ... during the rebase (a slow commit signer, while rebase-merge exists)
#   D3  a commit signer that hangs and ignores SIGTERM: the last resort
#   D4  ... during a hanging fetch: publishing is skipped
#   D5  _addwork_outcome on constructed worktree states
#   D6  KeyboardInterrupt through the real nesting (_run_addwork -> addwork ->
#       bounded_run CLI -> git -> TERM-ignoring transport)
#   D7  the last-resort kill through the same nesting
#   D8  an outer cancellation landing in the nested runner's own timeout cleanup
# D6/D7 use the default graces (outer 5s, nested CLI 3s): the inner cleanup must
# finish before the outer SIGKILL, or the TERM-ignoring transport survives.
#
# Run: bash tests/test_brainstorm_addwork_deadline.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/venv_python.sh
. "$PROJECT_DIR/tests/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

# Developer git config never reaches this file (a global hook path, signing
# key or autoStash would change every cell). Sourced after the counters,
# because the probe asserts.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

unset AIT_CREW_GIT_TIMEOUT AIT_BOUNDED_RUN_GRACE

CLEANUP_DIRS=()
cleanup() {
    for d in "${CLEANUP_DIRS[@]}"; do
        for f in "$d"/*.pids; do
            [[ -f "$f" ]] && xargs kill -KILL < "$f" 2>/dev/null
        done
        rm -rf "$d" 2>/dev/null
    done
}
trap cleanup EXIT

HARNESS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_addwork_deadline_harness_XXXXXX")"
CLEANUP_DIRS+=("$HARNESS_DIR")
HARNESS="$HARNESS_DIR/harness.py"
cat > "$HARNESS" <<'PYEOF'
"""Drive brainstorm_crew._run_addwork / _addwork_outcome from a fixture repo.

  harness.py <scripts> run      (env: HARNESS_CREW, HARNESS_AGENT, HARNESS_DEADLINE,
                                 HARNESS_STOP_GRACE, [HARNESS_INTERRUPT_AFTER])
  harness.py <scripts> outcome  (env: HARNESS_CREW, HARNESS_AGENT)
Prints RESULT:ok:<name> | RESULT:error:<message> | RESULT:interrupted, then ELAPSED:<s>.
"""
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import brainstorm.brainstorm_crew as bc  # noqa: E402

crew, agent = os.environ["HARNESS_CREW"], os.environ["HARNESS_AGENT"]
if sys.argv[2] == "outcome":
    try:
        print("RESULT:ok:" + bc._addwork_outcome(crew, agent, 1), flush=True)
    except RuntimeError as exc:
        print("RESULT:error:" + str(exc), flush=True)
    sys.exit(0)

deadline = float(os.environ["HARNESS_DEADLINE"])
bc._addwork_timeout = lambda: deadline
bc._ADDWORK_STOP_GRACE_S = float(os.environ["HARNESS_STOP_GRACE"])
interrupt_after = os.environ.get("HARNESS_INTERRUPT_AFTER")
if interrupt_after:
    def _interrupt(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGALRM, _interrupt)
    signal.setitimer(signal.ITIMER_REAL, float(interrupt_after))
start = time.monotonic()
try:
    result = "RESULT:ok:" + bc._run_addwork(crew, agent, "impl", "g1", Path("/dev/null"))
except RuntimeError as exc:
    result = "RESULT:error:" + str(exc)
except KeyboardInterrupt:
    result = "RESULT:interrupted"
finally:
    signal.setitimer(signal.ITIMER_REAL, 0)
print(result, flush=True)
print(f"ELAPSED:{time.monotonic() - start:.1f}", flush=True)
PYEOF

# new_crew <crew_id> — a fake aitask repo whose crew is published to a bare
# remote with an upstream, plus a stub ./ait that execs the real addwork.
# Sets: ROOT REPO REMOTE WT
new_crew() {
    local id="$1"
    ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_addwork_deadline_XXXXXX")"
    CLEANUP_DIRS+=("$ROOT")
    REPO="$ROOT/repo"
    REMOTE="$ROOT/remote.git"
    mkdir -p "$REPO/aitasks/metadata"
    git -C "$REPO" init --quiet
    git -C "$REPO" config user.email "test@test.com"
    git -C "$REPO" config user.name "Test"
    setup_fake_aitask_repo "$REPO"
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"   "$REPO/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/launch_modes_sh.sh"   "$REPO/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/launch_modes.py"      "$REPO/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh"      "$REPO/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_addwork.sh"   "$REPO/.aitask-scripts/"
    echo "email: test@test.com" > "$REPO/aitasks/metadata/userconfig.yaml"
    cat > "$REPO/ait" <<'EOF'
#!/usr/bin/env bash
# Fixture dispatcher: only `ait crew addwork` is needed.
if [[ "${1:-} ${2:-}" == "crew addwork" ]]; then
    shift 2
    exec bash "$(cd "$(dirname "$0")" && pwd)/.aitask-scripts/aitask_crew_addwork.sh" "$@"
fi
echo "fixture ait: unsupported: $*" >&2
exit 2
EOF
    chmod +x "$REPO/ait"
    git -C "$REPO" add -A
    git -C "$REPO" commit -m "Initial setup" --quiet
    git init --bare --quiet "$REMOTE"
    git -C "$REPO" remote add origin "$REMOTE"
    (cd "$REPO" && bash .aitask-scripts/aitask_crew_init.sh --id "$id" \
        --add-type impl:claudecode/opus4_6 --batch) >/dev/null 2>&1
    WT="$REPO/.aitask-crews/crew-$id"
    assert_eq "fixture: crew-$id is published with an upstream" "origin/crew-$id" \
        "$(git -C "$WT" rev-parse --abbrev-ref '@{u}' 2>/dev/null)"
}

# run_harness <mode> — sets RESULT ELAPSED (cwd: $REPO). A harness that
# printed no RESULT line crashed: show its stderr so the failure is readable.
run_harness() {
    (cd "$REPO" && "$AITASK_PYTHON" "$HARNESS" "$PROJECT_DIR/.aitask-scripts" "$1") \
        >"$ROOT/h.out" 2>"$ROOT/h.err"
    RESULT="$(sed -n 's/^RESULT://p' "$ROOT/h.out" | head -1)"
    ELAPSED="$(sed -n 's/^ELAPSED://p' "$ROOT/h.out" | head -1)"
    if [[ -z "$RESULT" ]]; then
        echo "harness printed no RESULT; its stderr:" >&2
        cat "$ROOT/h.err" >&2
    fi
}

# elapsed_cmp <cell> <what> <op> <seconds> — ELAPSED <op> <seconds>, op is le or ge.
elapsed_cmp() {
    local cell="$1" what="$2" op="$3" limit="$4" ok
    if [[ "$op" == le ]]; then
        ok="$(awk -v e="${ELAPSED:-999}" -v m="$limit" 'BEGIN { print (e <= m) ? "yes" : "no" }')"
    else
        ok="$(awk -v e="${ELAPSED:--1}" -v m="$limit" 'BEGIN { print (e >= m) ? "yes" : "no" }')"
    fi
    assert_eq "$cell: $what (${op} ${limit}s; took ${ELAPSED:-?}s)" "yes" "$ok"
}

remote_tip() { git -C "$REMOTE" rev-parse -q --verify "refs/heads/crew-$1" 2>/dev/null; }
committed() { git -C "$WT" cat-file -e "HEAD:$1_status.yaml" 2>/dev/null && echo yes || echo no; }
merge_state() {
    "$AITASK_PYTHON" -c '
import sys
sys.path.insert(0, sys.argv[1])
from agentcrew_utils import crew_merge_state
print(crew_merge_state(sys.argv[2]))
' "$PROJECT_DIR/.aitask-scripts/agentcrew" "$WT"
}

# all_gone <cell> <pidfile> — the file is non-empty and none of its pids is alive.
all_gone() {
    local cell="$1" file="$2" pid alive=""
    sleep 0.3
    assert_eq "$cell: fixture: the stub recorded its pids" "yes" \
        "$([[ -s "$file" ]] && echo yes || echo no)"
    for pid in $(cat "$file" 2>/dev/null); do
        kill -0 "$pid" 2>/dev/null && alive="$alive $pid"
    done
    assert_eq "$cell: no stub process survives" "" "$alive"
}

# signer <mode> — install a stub gpg.program and turn on commit signing.
#   slow-rebase: fast for addwork's commit, 4s for the rebase's re-sign
#   hang-commit: the commit's signature hangs and ignores SIGTERM
signer() {
    local mode="$1"
    cat > "$ROOT/gpg" <<EOF
#!/bin/sh
n=\$(cat "$ROOT/gpg.count" 2>/dev/null || echo 0); n=\$((n + 1)); echo \$n > "$ROOT/gpg.count"
gd=\$(git rev-parse --git-dir 2>/dev/null)
if [ -d "\$gd/rebase-merge" ]; then where=in-rebase; else where=no-rebase; fi
echo "call \$n: \$where" >> "$ROOT/gpg.log"
cat >/dev/null
case "$mode:\$n" in
    slow-rebase:2) sleep 4 ;;
    hang-commit:1) echo \$\$ >> "$ROOT/gpg.pids"; trap '' TERM; sleep 30 ;;
esac
printf '\n[GNUPG:] SIG_CREATED D 22 8 00 1700000000 FAKE\n' >&2
printf -- '-----BEGIN PGP SIGNATURE-----\n\nZmFrZQ==\n-----END PGP SIGNATURE-----\n'
EOF
    chmod +x "$ROOT/gpg"
    git -C "$REPO" config user.signingkey FAKE
    git -C "$REPO" config gpg.program "$ROOT/gpg"
    git -C "$REPO" config commit.gpgSign true
}

# hang_origin — origin becomes an ssh URL whose transport ignores SIGTERM and
# never answers; the stub records its pid and its parent's (git's) pid.
hang_origin() {
    cat > "$ROOT/hang-ssh" <<EOF
#!/bin/sh
echo \$\$ \$PPID >> "$ROOT/hang.pids"
trap '' TERM
exec sleep 30
EOF
    chmod +x "$ROOT/hang-ssh"
    git -C "$REPO" config core.sshCommand "$ROOT/hang-ssh"
    git -C "$REPO" config ssh.variant ssh
    git -C "$REPO" remote set-url origin "ssh://crew-hang.invalid/repo.git"
}

echo "=== brainstorm's addwork deadline is a stop request (t2024) ==="

# --- D1: slow commit hook ---
echo "--- D1: the deadline expires during a slow pre-commit hook ---"
new_crew d1
remote_before="$(remote_tip d1)"
cat > "$REPO/.git/hooks/pre-commit" <<EOF
#!/bin/sh
echo start >> "$ROOT/hook.log"
sleep 4
echo end >> "$ROOT/hook.log"
EOF
chmod +x "$REPO/.git/hooks/pre-commit"
HARNESS_CREW=d1 HARNESS_AGENT=a1 HARNESS_DEADLINE=1 HARNESS_STOP_GRACE=15 run_harness run
assert_eq "D1: registration succeeds" "ok:a1" "$RESULT"
assert_contains "D1: the hook ran to completion (never killed)" "end" "$(cat "$ROOT/hook.log" 2>/dev/null)"
elapsed_cmp "D1" "it waited for the commit" ge 4
elapsed_cmp "D1" "it finished inside the stop grace" le 12
assert_eq "D1: the registration is committed" "yes" "$(committed a1)"
assert_eq "D1: no merge state" "None" "$(merge_state)"
assert_eq "D1: publishing was skipped (stop honoured)" "$remote_before" "$(remote_tip d1)"

# --- D2: slow rebase ---
echo "--- D2: the deadline expires during the rebase ---"
new_crew d2
git clone --quiet --branch crew-d2 "$REMOTE" "$ROOT/peer"
git -C "$ROOT/peer" -c user.email=p@p -c user.name=p commit --quiet --allow-empty -m "peer commit"
git -C "$ROOT/peer" push --quiet origin crew-d2
peer_tip="$(remote_tip d2)"
signer slow-rebase
HARNESS_CREW=d2 HARNESS_AGENT=a1 HARNESS_DEADLINE=1 HARNESS_STOP_GRACE=15 run_harness run
assert_eq "D2: registration succeeds" "ok:a1" "$RESULT"
assert_contains "D2: the stop request arrived while the rebase was in progress" \
    "call 2: in-rebase" "$(cat "$ROOT/gpg.log" 2>/dev/null)"
elapsed_cmp "D2" "it waited for the rebase" ge 4
assert_eq "D2: the rebase completed onto the peer commit" "yes" \
    "$(git -C "$WT" merge-base --is-ancestor "$peer_tip" HEAD && echo yes || echo no)"
assert_eq "D2: the registration is committed" "yes" "$(committed a1)"
assert_eq "D2: no merge state" "None" "$(merge_state)"
assert_eq "D2: publishing was skipped (stop honoured)" "$peer_tip" "$(remote_tip d2)"

# --- D3: a signer that hangs: the last resort ---
echo "--- D3: a hung commit signer is killed and the state read back ---"
new_crew d3
signer hang-commit
export AIT_BOUNDED_RUN_GRACE=2
HARNESS_CREW=d3 HARNESS_AGENT=a1 HARNESS_DEADLINE=1 HARNESS_STOP_GRACE=2 run_harness run
unset AIT_BOUNDED_RUN_GRACE
assert_contains "D3: reported as a registration failure" "error:" "$RESULT"
assert_contains "D3: names the hung step" "a git hook or commit signing" "$RESULT"
assert_contains "D3: reports the state it read back" "written and staged" "$RESULT"
assert_contains "D3: offers to complete it" "commit -m" "$RESULT"
assert_contains "D3: offers to discard it" "rm -q --cached" "$RESULT"
assert_contains "D3: the files really are staged" "a1_status.yaml" \
    "$(git -C "$WT" diff --cached --name-only)"
assert_eq "D3: the registration is not committed" "no" "$(committed a1)"
assert_eq "D3: git left no index.lock" "absent" \
    "$([[ -e "$(git -C "$WT" rev-parse --git-path index.lock)" ]] && echo present || echo absent)"
elapsed_cmp "D3" "the last resort is bounded" le 12
all_gone "D3" "$ROOT/gpg.pids"

# --- D4: a hanging fetch ---
echo "--- D4: the deadline expires during a hanging fetch ---"
new_crew d4
hang_origin
export AIT_CREW_GIT_TIMEOUT=3 AIT_BOUNDED_RUN_GRACE=2
HARNESS_CREW=d4 HARNESS_AGENT=a1 HARNESS_DEADLINE=1 HARNESS_STOP_GRACE=15 run_harness run
unset AIT_CREW_GIT_TIMEOUT AIT_BOUNDED_RUN_GRACE
assert_eq "D4: registration succeeds" "ok:a1" "$RESULT"
elapsed_cmp "D4" "the stop ends publishing" le 9
assert_eq "D4: only the fetch reached the transport (push skipped)" "1" \
    "$(wc -l < "$ROOT/hang.pids" | tr -d ' ')"
assert_eq "D4: the registration is committed" "yes" "$(committed a1)"
all_gone "D4" "$ROOT/hang.pids"

# --- D5: the read-back on constructed states ---
echo "--- D5: _addwork_outcome reports what is actually there ---"
new_crew d5
(cd "$REPO" && bash .aitask-scripts/aitask_crew_addwork.sh --crew d5 --name done1 \
    --work2do /dev/null --type impl --batch) >/dev/null 2>&1
HARNESS_CREW=d5 HARNESS_AGENT=done1 run_harness outcome
assert_eq "D5: committed → success" "ok:done1" "$RESULT"
printf 'status: Waiting\n' > "$WT/staged1_status.yaml"
git -C "$WT" add staged1_status.yaml
HARNESS_CREW=d5 HARNESS_AGENT=staged1 run_harness outcome
assert_contains "D5: staged → written and staged" "written and staged" "$RESULT"
git -C "$WT" rm -q --cached staged1_status.yaml
rm -f "$WT/staged1_status.yaml"
HARNESS_CREW=d5 HARNESS_AGENT=ghost run_harness outcome
assert_contains "D5: nothing → nothing registered" "Nothing was registered" "$RESULT"
# A rebase stopped on a conflict.
echo base > "$WT/conflict.txt"
git -C "$WT" add conflict.txt
git -C "$WT" commit --quiet -m base
git -C "$WT" push --quiet
git clone --quiet --branch crew-d5 "$REMOTE" "$ROOT/peer5"
echo theirs > "$ROOT/peer5/conflict.txt"
git -C "$ROOT/peer5" -c user.email=p@p -c user.name=p commit --quiet -am theirs
git -C "$ROOT/peer5" push --quiet origin crew-d5
echo ours > "$WT/conflict.txt"
git -C "$WT" commit --quiet -am ours
git -C "$WT" fetch --quiet
git -C "$WT" rebase --quiet >/dev/null 2>&1
assert_eq "D5: fixture: the rebase stopped" "rebase_in_progress" "$(merge_state)"
HARNESS_CREW=d5 HARNESS_AGENT=ghost run_harness outcome
assert_contains "D5: a rebase → named" "an unfinished rebase" "$RESULT"
assert_contains "D5: a rebase → its remedy" "rebase --abort" "$RESULT"
git -C "$WT" rebase --abort

# --- D6: nested cancellation, KeyboardInterrupt ---
echo "--- D6: KeyboardInterrupt tears down the whole nested tree ---"
new_crew d6
hang_origin
export AIT_CREW_GIT_TIMEOUT=30
HARNESS_CREW=d6 HARNESS_AGENT=a1 HARNESS_DEADLINE=100 HARNESS_STOP_GRACE=15 \
    HARNESS_INTERRUPT_AFTER=1 run_harness run
unset AIT_CREW_GIT_TIMEOUT
assert_eq "D6: the interrupt propagates" "interrupted" "$RESULT"
elapsed_cmp "D6" "cleanup fits the outer grace" le 8
all_gone "D6" "$ROOT/hang.pids"

# --- D7: nested cancellation, last resort ---
echo "--- D7: the last-resort kill reaches the nested transport ---"
new_crew d7
hang_origin
export AIT_CREW_GIT_TIMEOUT=30
HARNESS_CREW=d7 HARNESS_AGENT=a1 HARNESS_DEADLINE=1 HARNESS_STOP_GRACE=1 run_harness run
unset AIT_CREW_GIT_TIMEOUT
assert_eq "D7: the committed registration is read back as success" "ok:a1" "$RESULT"
elapsed_cmp "D7" "the kill is bounded" le 10
all_gone "D7" "$ROOT/hang.pids"

# --- D8: outer cancellation during the inner runner's own timeout cleanup ---
# The fetch times out at about 1.4s and the nested CLI then waits out its 3s
# grace for the TERM-ignoring transport (until about 4.4s). The outer
# KeyboardInterrupt at 3s TERMs addwork's group, which includes that CLI,
# mid-cleanup: the CLI must finish its SIGKILL before it dies by the TERM, or
# the transport, alone in its separate session, survives.
echo "--- D8: a cancellation landing in the nested runner's timeout cleanup ---"
new_crew d8
hang_origin
export AIT_CREW_GIT_TIMEOUT=1
HARNESS_CREW=d8 HARNESS_AGENT=a1 HARNESS_DEADLINE=100 HARNESS_STOP_GRACE=15 \
    HARNESS_INTERRUPT_AFTER=3 run_harness run
unset AIT_CREW_GIT_TIMEOUT
assert_eq "D8: the interrupt propagates" "interrupted" "$RESULT"
elapsed_cmp "D8" "cleanup fits the outer grace" le 9
all_gone "D8" "$ROOT/hang.pids"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

[[ "$FAIL" -eq 0 ]] || { echo "SOME TESTS FAILED"; exit 1; }
echo "ALL TESTS PASSED"
