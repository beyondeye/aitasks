#!/usr/bin/env bash
# test_crew_pull_no_autostash.sh - every crew-worktree pull ignores a user's
# rebase.autoStash / merge.autoStash (t2008), and the runner's pull converges
# without ever leaving a half-done merge in the live worktree (t2018).
#
# A crew worktree routinely holds other live processes' uncommitted tracked
# files: agent heartbeats, non-terminal status writes, queued commands and the
# runner's own heartbeat. An autostash would stash and re-apply files the caller
# does not own. Each fixture gives the crew branch an upstream — without one the
# pull dies with "no tracking information" before any stash, and every cell
# would pass vacuously — and the controls (cells 1 and 3) prove the pull really
# reaches the rebase.
#
# Cells 6-15 (t2018) drive git_pull and the runner through a small Python
# harness whose one seam wraps agentcrew_utils.git_cmd, so another process's
# action lands at an exact point between two git calls: an agent's write after
# the merge decision, a merge started independently mid-pull, or an older git
# without `merge-tree --write-tree`.
#
# Run: bash tests/test_crew_pull_no_autostash.sh

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

# Developer git config never reaches this file: a global autoStash would hide
# the defect, and a global push.autoSetupRemote would change the fixture. The
# autoStash settings each cell needs are per-repo config, which still applies.
# Sourced AFTER the counter initialisation, because the probe asserts.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

CLEANUP_DIRS=()
cleanup() {
    for d in "${CLEANUP_DIRS[@]}"; do
        rm -rf "$d" 2>/dev/null
    done
}
trap cleanup EXIT

# Cells that need a real in-memory merge proof skip, visibly, on git < 2.38.
# The probe runs in a disposable repository, and only git's usage exit (129:
# no --write-tree) means "unsupported"; any other failure fails the file
# rather than quietly skipping its core cells.
HAVE_MERGE_TREE=0
mt_probe="$(mktemp -d "${TMPDIR:-/tmp}/ait_crew_mt_probe_XXXXXX")"
CLEANUP_DIRS+=("$mt_probe")
git init --quiet "$mt_probe"
git -C "$mt_probe" -c user.email=probe@test.com -c user.name=Probe \
    commit --quiet --allow-empty -m probe
mt_err="$(git -C "$mt_probe" merge-tree --write-tree --no-messages HEAD HEAD 2>&1 >/dev/null)"
mt_rc=$?
case "$mt_rc" in
    0)   HAVE_MERGE_TREE=1 ;;
    129) ;;
    *)   assert_record_fail
         echo "FAIL: merge-tree capability probe errored (exit $mt_rc): $mt_err" ;;
esac
need_merge_tree() {
    [[ "$HAVE_MERGE_TREE" == 1 ]] && return 0
    echo "SKIP: cell $1 — $(git --version) has no merge-tree --write-tree (needs >= 2.38)"
    return 1
}

# Byte digest, and inode + ctime: a stash round trip restores the bytes but
# rewrites the file, so only the identity proves a file was never touched
# (the same pair tests/test_task_push.sh pins for the task-data pulls, t1987).
file_sha() { { sha256sum < "$1"; } 2>/dev/null | cut -d' ' -f1; }
file_ident() {
    python3 -c 'import os,sys; s=os.lstat(sys.argv[1]); print(s.st_ino, s.st_ctime_ns)' "$1" 2>/dev/null
}

CREW_ID="pull"

# The harness (see the header). Written once; the cleanup trap removes it.
HARNESS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_crew_pull_harness_XXXXXX")"
CLEANUP_DIRS+=("$HARNESS_DIR")
HARNESS="$HARNESS_DIR/crew_pull_harness.py"
cat > "$HARNESS" <<'PYEOF'
"""Drive git_pull / run_loop / main through their real code with one seam.

  harness.py <scripts> pull   <wt> [--no-batch] [--write-after conflict|proof --write-path P --write-bytes F]
  harness.py <scripts> runner <wt> --crew C --stub-root D [--once] [--inject-after-fetch]
  harness.py <scripts> main   <wt> --stub-root D -- <runner argv>

Common: --git-log F appends each git subcommand git_pull runs.
Env: HARNESS_MERGE_TREE_RC=<rc> answers `merge-tree` with that exit status and
no output; HARNESS_RECOVER=<shell cmd> runs at the first sleep after an unsafe
pull, after HOLD_CHECK.
"""
import argparse
import os
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone

ap = argparse.ArgumentParser()
ap.add_argument("scripts")
ap.add_argument("mode", choices=("pull", "runner", "main"))
ap.add_argument("worktree")
ap.add_argument("--write-after", choices=("conflict", "proof"))
ap.add_argument("--write-path")
ap.add_argument("--write-bytes")
ap.add_argument("--inject-after-fetch", action="store_true")
ap.add_argument("--no-batch", action="store_true")
ap.add_argument("--git-log")
ap.add_argument("--crew")
ap.add_argument("--stub-root")
ap.add_argument("--once", action="store_true")
# Everything after `--` is the runner's own argv (main mode).
own, runner_argv = sys.argv[1:], []
if "--" in own:
    cut = own.index("--")
    own, runner_argv = own[:cut], own[cut + 1:]
args = ap.parse_args(own)

sys.path.insert(0, args.scripts)
import agentcrew.agentcrew_utils as u  # noqa: E402

WT = os.path.abspath(args.worktree)
real_git_cmd = u.git_cmd
merge_tree_rc = os.environ.get("HARNESS_MERGE_TREE_RC")
done = set()


def git(*a, input=None):
    return subprocess.run(["git", "-C", WT, *a], capture_output=True, text=True,
                          input=input)


def git_ok(*a, input=None):
    r = git(*a, input=input)
    if r.returncode != 0:
        sys.exit(f"harness: git {' '.join(a)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def merge_head():
    r = git("rev-parse", "-q", "--verify", "MERGE_HEAD")
    return r.stdout.strip() if r.returncode == 0 else ""


def inject_merge():
    """Start a merge the way another process would, and leave it open."""
    blob = git_ok("hash-object", "-w", "--stdin", input="injected\n")
    listing = git_ok("ls-tree", "HEAD")
    tree = git_ok("mktree", input=f"{listing}\n100644 blob {blob}\tinjected.txt\n")
    side = git_ok("commit-tree", tree, "-p", "HEAD", "-m", "another process's merge")
    git_ok("merge", "--no-commit", "--no-ff", "--quiet", side)
    print(f"INJECTED:{side}", flush=True)


def wrapped_git_cmd(worktree, *a, check=True, **kw):
    sub = a[0] if a else ""
    if args.git_log:
        with open(args.git_log, "a") as fh:
            fh.write(sub + "\n")
    if sub == "merge-tree" and merge_tree_rc is not None:
        result = subprocess.CompletedProcess(
            ["git", "-C", worktree, *a], int(merge_tree_rc), "",
            "harness: merge-tree --write-tree unavailable\n")
        if check:
            result.check_returncode()
    else:
        result = real_git_cmd(worktree, *a, check=check, **kw)
    if args.write_after and "write" not in done:
        if args.write_after == "proof":
            hit = sub == "commit-tree"
        else:
            hit = sub == "merge-tree" or bool(merge_head())
        if hit:
            done.add("write")
            with open(args.write_bytes, "rb") as src, open(args.write_path, "wb") as dst:
                dst.write(src.read())
            print(f"WROTE:{os.path.basename(args.write_path)}", flush=True)
    if args.inject_after_fetch and sub == "fetch" and "inject" not in done:
        done.add("inject")
        inject_merge()
    return result


u.git_cmd = wrapped_git_cmd

if args.mode == "pull":
    res = u.git_pull(WT, batch=not args.no_batch)
    status, detail = res if isinstance(res, tuple) else ("none", "")
    print(f"PULL_RESULT:{status}|{detail}", flush=True)
    sys.exit(0)


def snapshot():
    out = {
        "HEAD": git("rev-parse", "HEAD").stdout.strip(),
        "index": git("ls-files", "-s").stdout,
        "MERGE_HEAD": merge_head(),
    }
    for name in ("_runner_alive.yaml", "w1_alive.yaml"):
        p = os.path.join(WT, name)
        try:
            st = os.lstat(p)
            with open(p, "rb") as fh:
                out[name] = (st.st_ino, st.st_ctime_ns, fh.read())
        except FileNotFoundError:
            out[name] = None
    return out


def changed_since(before):
    now = snapshot()
    return [k for k in before if before[k] != now.get(k)]


import agentcrew.agentcrew_runner as r  # noqa: E402

stub = os.path.abspath(args.stub_root)
r.launch_agent = lambda worktree, name, *a, **k: print(f"LAUNCH_STUB:{name}", flush=True)

# A real runner's heartbeats are an interval apart; in-process they can land in
# the same second as the start-up write and leave _runner_alive.yaml byte-equal
# to its commit, i.e. never dirty. Each timestamp is one second later.
_clock = [datetime(2026, 10, 15, 11, 0, 0, tzinfo=timezone.utc)]


def ticking_now_utc():
    _clock[0] += timedelta(seconds=1)
    return _clock[0].strftime("%Y-%m-%d %H:%M:%S")


r.now_utc = ticking_now_utc
UNSAFE = getattr(u, "PULL_UNSAFE", "unsafe")
snap = {}
real_pull = r.git_pull


def pull_spy(worktree, batch=False):
    res = real_pull(worktree, batch)
    if isinstance(res, tuple) and res[0] == UNSAFE and "unsafe" not in snap:
        snap["unsafe"] = snapshot()
    return res


r.git_pull = pull_spy
sleeps = [0]


def fake_sleep(_seconds):
    sleeps[0] += 1
    if sleeps[0] > 600:
        print("HARNESS_ABORT:loop_did_not_terminate", flush=True)
        os._exit(3)
    if "unsafe" in snap and "hold" not in done:
        done.add("hold")
        changed = changed_since(snap["unsafe"])
        print("HOLD_CHECK:" + ("ok" if not changed else "changed:" + ",".join(changed)),
              flush=True)
        recover = os.environ.get("HARNESS_RECOVER")
        if recover:
            subprocess.run(recover, shell=True, check=True)


# Only the RUNNER's sleep: `r.time` is the time module itself, and patching its
# `sleep` would also replace the one subprocess.Popen.wait(timeout) polls with
# inside bounded_run.run_bounded (git_cmd's bounded fetch/push, t2024), which
# would then count against the iteration cap.
r.time = types.SimpleNamespace(
    **{n: getattr(r.time, n) for n in dir(r.time) if not n.startswith("__")})
r.time.sleep = fake_sleep

if args.mode == "runner":
    r._repo_root = stub
    rc = r.run_loop(WT, args.crew, 30, 3, args.once, False, True)
else:
    r.resolve_repo_root = lambda: stub
    sys.argv = ["ait crew runner", *runner_argv]
    rc = r.main()
if "unsafe" in snap and "hold" not in done:
    changed = changed_since(snap["unsafe"])
    print("FINAL_CHECK:" + ("ok" if not changed else "changed:" + ",".join(changed)),
          flush=True)
print(f"RUN_RC:{rc}", flush=True)
sys.exit(rc or 0)
PYEOF

# setup_crew_remote_fixture <peer_change>
# A crew with one Waiting agent w1, its branch pushed with an upstream, and a
# peer commit on the remote the crew worktree has not pulled yet.
#   peer_change: peer_only      — the peer adds peer_only.txt (disjoint)
#                runner_stop    — the peer sets requested_action: stop in
#                                 _runner_alive.yaml (overlaps the runner heartbeat)
#                agent_conflict — the peer sets w1_alive.yaml's last_heartbeat
#                agent_disjoint — the peer sets w1_alive.yaml's last_message
#                peer_adds_notes — the peer adds w1_notes.md
# Sets: ROOT REPO WT PEER REMOTE BRANCH PEER_SHA STUB
setup_crew_remote_fixture() {
    local peer_change="$1"
    ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_crew_pull_XXXXXX")"
    CLEANUP_DIRS+=("$ROOT")
    REPO="$ROOT/repo"
    PEER="$ROOT/peer"
    REMOTE="$ROOT/remote.git"
    BRANCH="crew-$CREW_ID"
    WT="$REPO/.aitask-crews/$BRANCH"

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
    cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_setmode.sh"   "$REPO/.aitask-scripts/"
    echo "email: test@test.com" > "$REPO/aitasks/metadata/userconfig.yaml"
    git -C "$REPO" add -A
    git -C "$REPO" commit -m "Initial setup" --quiet

    # No origin exists yet, so the seeding addwork's own pull fails quietly and
    # its push is skipped; that is the crew scripts' best-effort contract.
    (
        cd "$REPO" || exit 1
        bash .aitask-scripts/aitask_crew_init.sh --id "$CREW_ID" \
            --add-type impl:claudecode/opus4_6 --batch
        bash .aitask-scripts/aitask_crew_addwork.sh --crew "$CREW_ID" --name w1 \
            --work2do /dev/null --type impl --batch
    ) >/dev/null 2>&1

    # The runner's alive file, in write_runner_alive's key order.
    cat > "$WT/_runner_alive.yaml" <<'EOF'
status: running
pid: 4242
hostname: crewhost
started_at: '2026-10-15 10:00:00'
last_heartbeat: '2026-10-15 10:00:00'
next_check_at: '2026-10-15 10:00:30'
interval: 30
requested_action: null
EOF
    git -C "$WT" add _runner_alive.yaml
    git -C "$WT" commit -m "runner: started" --quiet

    git init --bare --quiet "$REMOTE"
    git -C "$REPO" remote add origin "$REMOTE"
    git -C "$WT" push --quiet -u origin "$BRANCH" 2>/dev/null
    assert_eq "fixture: the crew branch has an upstream" "origin/$BRANCH" \
        "$(git -C "$WT" rev-parse --abbrev-ref '@{u}' 2>/dev/null)"

    git clone --quiet -b "$BRANCH" "$REMOTE" "$PEER" 2>/dev/null
    git -C "$PEER" config user.email "peer@test.com"
    git -C "$PEER" config user.name "Peer"
    case "$peer_change" in
        peer_only)
            echo "from another host" > "$PEER/peer_only.txt"
            git -C "$PEER" add peer_only.txt
            git -C "$PEER" commit -m "peer: add peer_only.txt" --quiet
            ;;
        runner_stop)
            sed 's/^requested_action: null$/requested_action: stop/' \
                "$PEER/_runner_alive.yaml" > "$PEER/_runner_alive.yaml.tmp"
            mv "$PEER/_runner_alive.yaml.tmp" "$PEER/_runner_alive.yaml"
            git -C "$PEER" commit -am "peer: request runner stop" --quiet
            ;;
        agent_conflict)
            sed "s/^last_heartbeat:.*/last_heartbeat: '2026-10-15 10:01:00'/" \
                "$PEER/w1_alive.yaml" > "$PEER/w1_alive.yaml.tmp"
            mv "$PEER/w1_alive.yaml.tmp" "$PEER/w1_alive.yaml"
            git -C "$PEER" commit -am "peer: w1 heartbeat" --quiet
            ;;
        agent_disjoint)
            sed "s/^last_message:.*/last_message: peer note/" \
                "$PEER/w1_alive.yaml" > "$PEER/w1_alive.yaml.tmp"
            mv "$PEER/w1_alive.yaml.tmp" "$PEER/w1_alive.yaml"
            git -C "$PEER" commit -am "peer: w1 message" --quiet
            ;;
        peer_adds_notes)
            echo "peer notes" > "$PEER/w1_notes.md"
            git -C "$PEER" add w1_notes.md
            git -C "$PEER" commit -m "peer: add w1_notes.md" --quiet
            ;;
    esac
    git -C "$PEER" push --quiet 2>/dev/null
    PEER_SHA="$(git -C "$PEER" rev-parse HEAD)"
    assert_eq "fixture: the remote is ahead of the crew worktree" "1" \
        "$(git -C "$REMOTE" rev-list --count "$(git -C "$WT" rev-parse HEAD)..refs/heads/$BRANCH")"

    git -C "$REPO" config rebase.autoStash true
    git -C "$REPO" config merge.autoStash true

    # graceful_shutdown's `ait crew command send-all`, as a logging stub.
    STUB="$ROOT/stub"
    mkdir -p "$STUB"
    printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$*" >> "%s/ait_calls.log"\n' "$STUB" > "$STUB/ait"
    chmod +x "$STUB/ait"
}

# Stand-in for a running agent's uncommitted heartbeat write.
# Sets: dirty_file dirty_sha dirty_ident
dirty_agent_heartbeat() {
    dirty_file="$WT/w1_alive.yaml"
    echo "last_heartbeat: '2026-10-15 10:05:00'" >> "$dirty_file"
    dirty_sha="$(file_sha "$dirty_file")"
    dirty_ident="$(file_ident "$dirty_file")"
}

# The dirty file was never rewritten, never stashed, and never committed.
assert_dirty_untouched() {
    local label="$1" rel
    rel="$(basename "$dirty_file")"
    assert_eq "$label: the dirty file's bytes are unchanged" "$dirty_sha" "$(file_sha "$dirty_file")"
    assert_eq "$label: the dirty file was never rewritten (inode+ctime)" "$dirty_ident" "$(file_ident "$dirty_file")"
    assert_eq "$label: nothing was stashed" "" "$(git -C "$WT" stash list)"
    assert_eq "$label: the dirty file is still uncommitted" "dirty" \
        "$(git -C "$WT" diff --quiet -- "$rel" && echo clean || echo dirty)"
}

# A local commit the crew worktree has not pushed: the branch is now diverged.
# local_commit <file> <sed expression> <message>
local_commit() {
    sed "$2" "$WT/$1" > "$WT/$1.tmp" && mv "$WT/$1.tmp" "$WT/$1"
    git -C "$WT" commit -qam "$3"
}

# An agent's fresh heartbeat, as bytes a hook writes at an exact moment.
# Sets: agent_bytes agent_sha
agent_heartbeat_bytes() {
    agent_bytes="$ROOT/agent_heartbeat"
    printf "last_heartbeat: '2026-10-15 10:03:00'\nlast_message: still working\n" > "$agent_bytes"
    agent_sha="$(file_sha "$agent_bytes")"
}

peer_file_state() {
    [[ -e "$WT/peer_only.txt" ]] && echo present || echo absent
}

remote_head() {
    git -C "$REMOTE" rev-parse "refs/heads/$BRANCH"
}

merge_head_state() {
    git -C "$WT" rev-parse -q --verify MERGE_HEAD 2>/dev/null
}

run_addwork_w2() {
    (cd "$REPO" && bash .aitask-scripts/aitask_crew_addwork.sh --crew "$CREW_ID" --name w2 \
        --work2do /dev/null --type impl --batch 2>&1)
}

run_setmode_w1() {
    (cd "$REPO" && bash .aitask-scripts/aitask_crew_setmode.sh --crew "$CREW_ID" --name w1 \
        --mode interactive 2>&1)
}

# The runner's pull, through the real helper. Prints PULL_RESULT:<status>|<detail>.
run_pull() {
    "$AITASK_PYTHON" "$HARNESS" "$PROJECT_DIR/.aitask-scripts" pull "$WT" "$@" 2>&1
}

# run_loop itself, as an already-running runner meets the peer's commit.
run_runner() {
    "$AITASK_PYTHON" "$HARNESS" "$PROJECT_DIR/.aitask-scripts" runner "$WT" \
        --crew "$CREW_ID" --stub-root "$STUB" "$@" 2>&1
}

# The `ait crew runner` entry point (main), from the repository root.
run_main() {
    (cd "$REPO" && "$AITASK_PYTHON" "$HARNESS" "$PROJECT_DIR/.aitask-scripts" main "$WT" \
        --stub-root "$STUB" -- --crew "$CREW_ID" "$@")
}

echo "=== crew pulls ignore autoStash (t2008) and converge without half-done merges (t2018) ==="

# --- Test 1: addwork control — a clean tree pulls and pushes ---
echo "--- Test 1: addwork, clean worktree (control) ---"
setup_crew_remote_fixture peer_only
out="$(run_addwork_w2)"; rc=$?
assert_eq "1: addwork exits 0" "0" "$rc"
assert_contains "1: addwork reports ADDED" "ADDED:w2" "$out"
assert_eq "1: the pull reached the rebase (peer commit landed)" "present" "$(peer_file_state)"
assert_eq "1: the push landed" "$(git -C "$WT" rev-parse HEAD)" "$(remote_head)"
assert_eq "1: nothing was stashed" "" "$(git -C "$WT" stash list)"

# --- Test 2: addwork never autostashes another agent's heartbeat ---
echo "--- Test 2: addwork ignores rebase.autoStash=true ---"
setup_crew_remote_fixture peer_only
dirty_agent_heartbeat
out="$(run_addwork_w2)"; rc=$?
assert_eq "2: addwork exits 0 (best-effort pull)" "0" "$rc"
assert_contains "2: addwork reports ADDED" "ADDED:w2" "$out"
assert_dirty_untouched "2"
assert_eq "2: the pull refused (peer commit did not land)" "absent" "$(peer_file_state)"
assert_contains "2: addwork's own commit was made" "crew: Add agent 'w2'" \
    "$(git -C "$WT" log -1 --format=%s)"

# --- Test 3: setmode control — a clean tree pulls and pushes ---
echo "--- Test 3: setmode, clean worktree (control) ---"
setup_crew_remote_fixture peer_only
out="$(run_setmode_w1)"; rc=$?
assert_eq "3: setmode exits 0" "0" "$rc"
assert_contains "3: setmode reports UPDATED" "UPDATED:w1:interactive" "$out"
assert_eq "3: the pull reached the rebase (peer commit landed)" "present" "$(peer_file_state)"
assert_eq "3: the push landed" "$(git -C "$WT" rev-parse HEAD)" "$(remote_head)"
assert_eq "3: nothing was stashed" "" "$(git -C "$WT" stash list)"

# --- Test 4: setmode never autostashes another agent's heartbeat ---
echo "--- Test 4: setmode ignores rebase.autoStash=true ---"
setup_crew_remote_fixture peer_only
dirty_agent_heartbeat
out="$(run_setmode_w1)"; rc=$?
assert_eq "4: setmode exits 0 (best-effort pull)" "0" "$rc"
assert_contains "4: setmode reports UPDATED" "UPDATED:w1:interactive" "$out"
assert_dirty_untouched "4"
assert_eq "4: the pull refused (peer commit did not land)" "absent" "$(peer_file_state)"
assert_contains "4: setmode's own commit was made" "Set launch_mode=interactive" \
    "$(git -C "$WT" log -1 --format=%s)"

# --- Test 5: the runner's pull, disjoint edit ---
# The fast-forward writes around a dirty file the incoming commit does not
# touch, so the peer commit lands — which also proves the pull ran.
echo "--- Test 5: runner git_pull ignores merge.autoStash=true (disjoint) ---"
setup_crew_remote_fixture peer_only
dirty_agent_heartbeat
out="$(run_pull)"
assert_contains "5: the pull reports ok" "PULL_RESULT:ok|" "$out"
assert_dirty_untouched "5"
assert_eq "5: the merge ran (peer commit landed)" "present" "$(peer_file_state)"
assert_eq "5: HEAD is the remote head" "$(remote_head)" "$(git -C "$WT" rev-parse HEAD)"

# --- Test 6: an already-running runner converges on the peer's stop request ---
# run_loop commits "runner: started" (its push is rejected: the remote is
# ahead), then iteration 1 pulls BEFORE rewriting its own heartbeat (t2018), so
# _runner_alive.yaml is clean at the pull and the diverged branches merge: the
# runner's started-lines and the peer's requested_action line are not adjacent.
test_6_runner_converges() {
    echo "--- Test 6: runner pulls before its heartbeat and honours a remote stop ---"
    setup_crew_remote_fixture runner_stop
    dirty_agent_heartbeat
    local out rc
    out="$(run_runner --once)"; rc=$?
    assert_eq "6: run_loop exits 0" "0" "$rc"
    assert_contains "6: the remote stop was honoured" "SHUTDOWN:complete" "$out"
    assert_not_contains "6: no agent was launched before the stop was seen" "LAUNCH_STUB:" "$out"
    assert_eq "6: the peer's stop commit was merged" "merged" \
        "$(git -C "$WT" merge-base --is-ancestor "$PEER_SHA" HEAD && echo merged || echo missing)"
    assert_eq "6: the shutdown push converged (remote head == HEAD)" \
        "$(git -C "$WT" rev-parse HEAD)" "$(remote_head)"
    assert_contains "6: the committed runner file says stopped" "status: stopped" \
        "$(git -C "$WT" show HEAD:_runner_alive.yaml)"
    assert_contains "6: graceful_shutdown sent the agents kill" "send-all" \
        "$(cat "$STUB/ait_calls.log" 2>/dev/null)"
    assert_eq "6: no merge was left in progress" "" "$(merge_head_state)"
    assert_eq "6: nothing was stashed" "" "$(git -C "$WT" stash list)"
    # The runner's existing `git add -A` commits the agent's file at shutdown;
    # what must hold is that no pull step stashed or rewrote it.
    assert_eq "6: the agent's file bytes are unchanged" "$dirty_sha" "$(file_sha "$dirty_file")"
    assert_eq "6: the agent's file was never rewritten (inode+ctime)" "$dirty_ident" \
        "$(file_ident "$dirty_file")"
}
need_merge_tree 6 && test_6_runner_converges

# --- Test 7: the runner's pull, overlapping dirty file ---
# If the runner's own file is dirty at the pull (its previous commit failed),
# an incoming commit touching it is refused cleanly — no stash, no rewrite, no
# merge state — and the next iteration's commit clears the way. Recovery comes
# from run_loop's ordering (Test 6), never from git_pull rewriting the file.
echo "--- Test 7: runner git_pull ignores merge.autoStash=true (overlapping) ---"
setup_crew_remote_fixture runner_stop
dirty_file="$WT/_runner_alive.yaml"
sed -e "s/^last_heartbeat: .*/last_heartbeat: '2026-10-15 10:05:00'/" \
    -e "s/^next_check_at: .*/next_check_at: '2026-10-15 10:05:30'/" \
    "$dirty_file" > "$dirty_file.tmp"
mv "$dirty_file.tmp" "$dirty_file"
dirty_sha="$(file_sha "$dirty_file")"
dirty_ident="$(file_ident "$dirty_file")"
head_before="$(git -C "$WT" rev-parse HEAD)"
out="$(run_pull)"
assert_contains "7: the pull is deferred" "PULL_RESULT:deferred|" "$out"
assert_dirty_untouched "7"
assert_eq "7: the merge refused (HEAD did not move)" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
assert_eq "7: no merge was left in progress" "" "$(merge_head_state)"

# --- Test 8: a conflict is never written to the live worktree ---
# Both sides changed w1_alive.yaml's last_heartbeat line, and the agent lands a
# fresh heartbeat the moment the merge is decided (after merge-tree, or as soon
# as a MERGE_HEAD exists — so a merge-then-abort recovery would be caught
# reverting it). The agent's bytes must survive and no merge state may remain.
test_8_conflict_keeps_concurrent_write() {
    echo "--- Test 8: conflicting pull defers and keeps a concurrent agent write ---"
    setup_crew_remote_fixture agent_conflict
    local_commit w1_alive.yaml "s/^last_heartbeat:.*/last_heartbeat: '2026-10-15 10:02:00'/" \
        "runner: iteration 7"
    agent_heartbeat_bytes
    local head_before out
    head_before="$(git -C "$WT" rev-parse HEAD)"
    out="$(run_pull --write-after conflict --write-path "$WT/w1_alive.yaml" \
        --write-bytes "$agent_bytes")"
    assert_contains "8: the agent's write landed in the window" "WROTE:w1_alive.yaml" "$out"
    assert_contains "8: the pull is deferred" "PULL_RESULT:deferred|" "$out"
    assert_contains "8: the deferral names the conflicted file" "w1_alive.yaml" \
        "$(printf '%s' "$out" | grep '^PULL_RESULT:')"
    assert_eq "8: the agent's heartbeat survived" "$agent_sha" "$(file_sha "$WT/w1_alive.yaml")"
    assert_eq "8: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
    assert_eq "8: no merge was left in progress" "" "$(merge_head_state)"
    assert_eq "8: no unmerged entries" "" "$(git -C "$WT" ls-files -u)"
    assert_eq "8: nothing was stashed" "" "$(git -C "$WT" stash list)"
}
need_merge_tree 8 && test_8_conflict_keeps_concurrent_write

# --- Test 9: an agent write after the merge proof stops the advance ---
# The merge is proven clean in memory and the commit is built; the agent then
# writes a file that merge would update. The fast-forward refuses instead of
# overwriting it. 9b is the same fixture with no concurrent write.
test_9_write_after_proof() {
    echo "--- Test 9: agent write after the merge proof is kept; the advance defers ---"
    setup_crew_remote_fixture agent_disjoint
    echo "local" > "$WT/local_only.txt"
    git -C "$WT" add local_only.txt
    git -C "$WT" commit -qm "runner: iteration 8"
    agent_heartbeat_bytes
    local head_before out
    head_before="$(git -C "$WT" rev-parse HEAD)"
    out="$(run_pull --write-after proof --write-path "$WT/w1_alive.yaml" \
        --write-bytes "$agent_bytes")"
    assert_contains "9: the agent's write landed after the proof" "WROTE:w1_alive.yaml" "$out"
    assert_contains "9: the pull is deferred" "PULL_RESULT:deferred|" "$out"
    assert_contains "9: the deferral names the agent's file" "w1_alive.yaml" \
        "$(printf '%s' "$out" | grep '^PULL_RESULT:')"
    assert_eq "9: the agent's heartbeat survived" "$agent_sha" "$(file_sha "$WT/w1_alive.yaml")"
    assert_eq "9: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
    assert_eq "9: no merge was left in progress" "" "$(merge_head_state)"
    assert_eq "9: nothing was stashed" "" "$(git -C "$WT" stash list)"

    echo "--- Test 9b: the same diverged pull merges when nothing interferes (control) ---"
    setup_crew_remote_fixture agent_disjoint
    echo "local" > "$WT/local_only.txt"
    git -C "$WT" add local_only.txt
    git -C "$WT" commit -qm "runner: iteration 8"
    out="$(run_pull)"
    assert_contains "9b: the pull reports ok" "PULL_RESULT:ok|" "$out"
    assert_eq "9b: HEAD is a two-parent merge" "merge" \
        "$(git -C "$WT" rev-parse -q --verify 'HEAD^2' >/dev/null && echo merge || echo single)"
    assert_contains "9b: the peer's change landed" "last_message: peer note" \
        "$(git -C "$WT" show HEAD:w1_alive.yaml)"
    assert_eq "9b: the local commit was kept" "kept" \
        "$(git -C "$WT" cat-file -e HEAD:local_only.txt 2>/dev/null && echo kept || echo lost)"
    assert_eq "9b: the worktree matches the merge" "clean" \
        "$(git -C "$WT" diff --quiet HEAD -- w1_alive.yaml && echo clean || echo dirty)"
    assert_eq "9b: no merge was left in progress" "" "$(merge_head_state)"
}
need_merge_tree 9 && test_9_write_after_proof

# --- Test 10: a merge state left by someone else blocks every runner entry ---
# (a) a conflicting merge started by hand; (b) a `pull --rebase` stopped on a
# conflict and resolved with `git add` but never continued. The runner's
# start-up and --check refuse before reading any crew file, touch nothing, and
# abort nothing, and the state check runs before the fetch.
assert_unsafe_entry_points() {
    local label="$1" reason="$2" out err rc
    out="$(run_main --once --batch 2>&1)"; rc=$?
    assert_eq "$label: start-up exits 1" "1" "$rc"
    assert_contains "$label: start-up reports the state" "PULL_UNSAFE:$reason" "$out"
    assert_not_contains "$label: start-up never read a crew file" "Traceback" "$out"
    assert_not_contains "$label: start-up launched nothing" "LAUNCH_STUB:" "$out"
    out="$(run_main --check --batch 2>&1)"; rc=$?
    assert_eq "$label: --check exits 1" "1" "$rc"
    assert_contains "$label: --check reports the state" "PULL_UNSAFE:$reason" "$out"
    assert_not_contains "$label: --check never read a crew file" "Traceback" "$out"
    err="$ROOT/stderr.txt"
    out="$(run_main --once 2>"$err")"; rc=$?
    assert_eq "$label: non-batch start-up exits 1" "1" "$rc"
    assert_contains "$label: non-batch names the worktree" "crew-$CREW_ID" "$(cat "$err")"
    assert_contains "$label: non-batch names the state" "$reason" "$(cat "$err")"
}

echo "--- Test 10a: a merge started by hand blocks start-up and --check ---"
setup_crew_remote_fixture runner_stop
local_commit _runner_alive.yaml "s/^requested_action: null$/requested_action: hold/" "side"
side_sha="$(git -C "$WT" rev-parse HEAD)"
git -C "$WT" reset -q --hard HEAD~1
local_commit _runner_alive.yaml "s/^requested_action: null$/requested_action: keep/" "local"
git -C "$WT" merge -q "$side_sha" >/dev/null 2>&1
assert_eq "10a: fixture: a merge is in progress" "$side_sha" "$(merge_head_state)"
assert_contains "10a: fixture: the runner file holds conflict markers" "<<<<<<<" \
    "$(cat "$WT/_runner_alive.yaml")"
head_before="$(git -C "$WT" rev-parse HEAD)"
index_before="$(git -C "$WT" ls-files -s)"
alive_sha="$(file_sha "$WT/_runner_alive.yaml")"
alive_ident="$(file_ident "$WT/_runner_alive.yaml")"
tracking_before="$(git -C "$WT" rev-parse "refs/remotes/origin/$BRANCH")"
assert_unsafe_entry_points "10a" merge_in_progress
assert_eq "10a: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
assert_eq "10a: the index was not touched" "$index_before" "$(git -C "$WT" ls-files -s)"
assert_eq "10a: the runner file's bytes are unchanged" "$alive_sha" "$(file_sha "$WT/_runner_alive.yaml")"
assert_eq "10a: the runner file was never rewritten" "$alive_ident" "$(file_ident "$WT/_runner_alive.yaml")"
assert_eq "10a: nothing was fetched (the state check runs before the fetch)" "$tracking_before" \
    "$(git -C "$WT" rev-parse "refs/remotes/origin/$BRANCH")"
assert_eq "10a: the merge was not aborted" "$side_sha" "$(merge_head_state)"

echo "--- Test 10b: a stopped rebase blocks start-up and --check ---"
setup_crew_remote_fixture agent_conflict
local_commit w1_alive.yaml "s/^last_heartbeat:.*/last_heartbeat: '2026-10-15 10:02:00'/" \
    "runner: iteration 7"
git -C "$WT" pull --quiet --rebase --no-autostash >/dev/null 2>&1
agent_heartbeat_bytes
cp "$agent_bytes" "$WT/w1_alive.yaml"
git -C "$WT" add w1_alive.yaml
rebase_dir="$(git -C "$WT" rev-parse --git-path rebase-merge)"
[[ "$rebase_dir" == /* ]] || rebase_dir="$WT/$rebase_dir"
assert_dir_exists "10b: fixture: a rebase is in progress" "$rebase_dir"
assert_eq "10b: fixture: its conflict is resolved (no unmerged entries)" "" \
    "$(git -C "$WT" ls-files -u)"
# The peer moves on, so a fetch would move the tracking ref.
echo "more from another host" > "$PEER/peer_more.txt"
git -C "$PEER" add peer_more.txt
git -C "$PEER" commit -qm "peer: more"
git -C "$PEER" push --quiet 2>/dev/null
head_before="$(git -C "$WT" rev-parse HEAD)"
index_before="$(git -C "$WT" ls-files -s)"
alive_sha="$(file_sha "$WT/_runner_alive.yaml")"
alive_ident="$(file_ident "$WT/_runner_alive.yaml")"
tracking_before="$(git -C "$WT" rev-parse "refs/remotes/origin/$BRANCH")"
assert_unsafe_entry_points "10b" rebase_in_progress
assert_eq "10b: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
assert_eq "10b: the index was not touched" "$index_before" "$(git -C "$WT" ls-files -s)"
assert_eq "10b: the runner file's bytes are unchanged" "$alive_sha" "$(file_sha "$WT/_runner_alive.yaml")"
assert_eq "10b: the runner file was never rewritten" "$alive_ident" "$(file_ident "$WT/_runner_alive.yaml")"
assert_eq "10b: nothing was fetched" \
    "$tracking_before" "$(git -C "$WT" rev-parse "refs/remotes/origin/$BRANCH")"
assert_dir_exists "10b: the rebase was not aborted" "$rebase_dir"

# --- Test 11: a merge state that appears during the pull makes the runner hold ---
# Another process starts a merge right after the runner's fetch. The
# pull reports unsafe; the runner then reads, rewrites and stages nothing until
# a human recovers (HOLD_CHECK compares the state at the first sleep with the
# state when the pull returned), and resumes on the next iteration.
test_11_runner_holds_then_resumes() {
    echo "--- Test 11: runner holds on a merge state injected mid-pull, then resumes ---"
    setup_crew_remote_fixture runner_stop
    dirty_agent_heartbeat
    local out rc
    out="$(HARNESS_RECOVER="git -C '$WT' merge --abort" run_runner --inject-after-fetch)"; rc=$?
    assert_contains "11: another process's merge was injected" "INJECTED:" "$out"
    assert_eq "11: the pull reported the merge state exactly once" "1" \
        "$(printf '%s\n' "$out" | grep -c '^PULL_UNSAFE:merge_in_progress$')"
    assert_contains "11: nothing was rewritten or staged while holding" "HOLD_CHECK:ok" "$out"
    assert_contains "11: after recovery the remote stop was honoured" "SHUTDOWN:complete" "$out"
    assert_eq "11: run_loop exits 0" "0" "$rc"
    assert_eq "11: the shutdown push converged (remote head == HEAD)" \
        "$(git -C "$WT" rev-parse HEAD)" "$(remote_head)"
    assert_eq "11: the injected merge never reached a commit" "absent" \
        "$(git -C "$WT" cat-file -e HEAD:injected.txt 2>/dev/null && echo present || echo absent)"
    assert_eq "11: no merge was left in progress" "" "$(merge_head_state)"
}
need_merge_tree 11 && test_11_runner_holds_then_resumes

echo "--- Test 11b: --once stops on the injected merge state and leaves it alone ---"
setup_crew_remote_fixture runner_stop
dirty_agent_heartbeat
out="$(run_runner --once --inject-after-fetch)"; rc=$?
injected_sha="$(printf '%s\n' "$out" | sed -n 's/^INJECTED://p')"
assert_eq "11b: run_loop exits 1" "1" "$rc"
assert_contains "11b: the pull reported the merge state" "PULL_UNSAFE:merge_in_progress" "$out"
assert_not_contains "11b: no shutdown ran" "SHUTDOWN:" "$out"
assert_contains "11b: nothing was read into a write, rewritten or staged" "FINAL_CHECK:ok" "$out"
assert_eq "11b: the injected merge is still in progress" "$injected_sha" "$(merge_head_state)"
assert_contains "11b: its staged entry is untouched" "injected.txt" \
    "$(git -C "$WT" diff --cached --name-only)"
# run_loop's "runner: started" commit sweeps the agent's file before the loop
# (its existing `git add -A`); from then on nothing may stash or rewrite it.
assert_eq "11b: the agent's file bytes are unchanged" "$dirty_sha" "$(file_sha "$dirty_file")"
assert_eq "11b: the agent's file was never rewritten (inode+ctime)" "$dirty_ident" \
    "$(file_ident "$dirty_file")"
assert_eq "11b: nothing was stashed" "" "$(git -C "$WT" stash list)"

# --- Test 12: without a merge proof a diverged pull defers, touching nothing ---
# git < 2.38 has no `merge-tree --write-tree` (exit 129); any other failure is a
# failed proof. Neither falls back to a merge in the live worktree.
echo "--- Test 12: no merge proof → deferred, worktree untouched ---"
for case in "129:merge_proof_unsupported" "128:merge_proof_failed"; do
    rc_fake="${case%%:*}"
    reason="${case#*:}"
    setup_crew_remote_fixture peer_only
    echo "local" > "$WT/local_only.txt"
    git -C "$WT" add local_only.txt
    git -C "$WT" commit -qm "runner: iteration 9"
    head_before="$(git -C "$WT" rev-parse HEAD)"
    git_log="$ROOT/git_calls.log"
    out="$(HARNESS_MERGE_TREE_RC="$rc_fake" run_pull --git-log "$git_log")"
    assert_contains "12/$rc_fake: the pull is deferred as $reason" "PULL_RESULT:deferred|$reason" "$out"
    assert_eq "12/$rc_fake: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
    assert_eq "12/$rc_fake: no merge was left in progress" "" "$(merge_head_state)"
    assert_eq "12/$rc_fake: no unmerged entries" "" "$(git -C "$WT" ls-files -u)"
    assert_eq "12/$rc_fake: the peer's commit was not merged" "absent" "$(peer_file_state)"
    assert_contains "12/$rc_fake: the merge proof was attempted" "merge-tree" "$(cat "$git_log")"
    assert_eq "12/$rc_fake: no commit was built" "0" "$(grep -c '^commit-tree$' "$git_log")"
    assert_eq "12/$rc_fake: no merge ran in the worktree" "0" "$(grep -c '^merge$' "$git_log")"
done

# --- Test 13: an incoming file never overwrites a locally ignored one ---
# git overwrites ignored files by default. The agent's w1_notes.md is ignored
# here (info/exclude) and the peer adds a tracked w1_notes.md: both the
# fast-forward (13a) and the diverged merge (13b) must refuse and keep it.
setup_ignored_notes() {
    setup_crew_remote_fixture peer_adds_notes
    local exclude
    exclude="$(git -C "$WT" rev-parse --git-path info/exclude)"
    [[ "$exclude" == /* ]] || exclude="$WT/$exclude"
    mkdir -p "$(dirname "$exclude")"
    echo "w1_notes.md" >> "$exclude"
    echo "agent's own notes" > "$WT/w1_notes.md"
    notes_sha="$(file_sha "$WT/w1_notes.md")"
    assert_eq "13: fixture: the agent's notes are ignored" "ignored" \
        "$(git -C "$WT" check-ignore -q w1_notes.md && echo ignored || echo visible)"
}

echo "--- Test 13a: fast-forward refuses to overwrite an ignored file ---"
setup_ignored_notes
head_before="$(git -C "$WT" rev-parse HEAD)"
out="$(run_pull)"
assert_contains "13a: the pull is deferred" "PULL_RESULT:deferred|merge_refused" "$out"
assert_eq "13a: the agent's ignored notes survived" "$notes_sha" "$(file_sha "$WT/w1_notes.md")"
assert_eq "13a: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
assert_eq "13a: no merge was left in progress" "" "$(merge_head_state)"

test_13b_merge_keeps_ignored() {
    echo "--- Test 13b: a diverged merge refuses to overwrite an ignored file ---"
    setup_ignored_notes
    echo "local" > "$WT/local_only.txt"
    git -C "$WT" add local_only.txt
    git -C "$WT" commit -qm "runner: iteration 10"
    local head_before out
    head_before="$(git -C "$WT" rev-parse HEAD)"
    out="$(run_pull)"
    assert_contains "13b: the pull is deferred" "PULL_RESULT:deferred|merge_refused" "$out"
    assert_eq "13b: the agent's ignored notes survived" "$notes_sha" "$(file_sha "$WT/w1_notes.md")"
    assert_eq "13b: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
    assert_eq "13b: no merge was left in progress" "" "$(merge_head_state)"
}
need_merge_tree 13b && test_13b_merge_keeps_ignored

# --- Test 14: the synthetic merge commit honours commit.gpgSign ---
# commit-tree does not read commit.gpgSign; `git merge` does. With signing on,
# a failing signer defers the pull (14a) and a working one signs the merge (14b).
test_14_signing() {
    local case program head_before out
    for case in fail ok; do
        echo "--- Test 14 ($case): commit.gpgSign=true, signer that ${case}s ---"
        setup_crew_remote_fixture peer_only
        echo "local" > "$WT/local_only.txt"
        git -C "$WT" add local_only.txt
        git -C "$WT" commit -qm "runner: iteration 11"
        program="$ROOT/gpg_$case"
        if [[ "$case" == fail ]]; then
            printf '#!/bin/sh\ncat >/dev/null\necho "gpg: signing failed: no secret key" >&2\nexit 2\n' > "$program"
        else
            printf '#!/bin/sh\ncat >/dev/null\nprintf "\\n[GNUPG:] SIG_CREATED D 1 8 00 0 STUB\\n" >&2\nprintf -- "-----BEGIN PGP SIGNATURE-----\\n\\nstub\\n-----END PGP SIGNATURE-----\\n"\n' > "$program"
        fi
        chmod +x "$program"
        git -C "$REPO" config commit.gpgSign true
        git -C "$REPO" config gpg.program "$program"
        head_before="$(git -C "$WT" rev-parse HEAD)"
        out="$(run_pull)"
        if [[ "$case" == fail ]]; then
            assert_contains "14a: a signing failure defers the pull" \
                "PULL_RESULT:deferred|merge_commit_failed" "$out"
            assert_eq "14a: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
            assert_eq "14a: the peer's commit was not merged" "absent" "$(peer_file_state)"
            assert_eq "14a: no merge was left in progress" "" "$(merge_head_state)"
        else
            assert_contains "14b: the pull merged" "PULL_RESULT:ok|merged" "$out"
            assert_eq "14b: HEAD is a two-parent merge" "merge" \
                "$(git -C "$WT" rev-parse -q --verify 'HEAD^2' >/dev/null && echo merge || echo single)"
            assert_contains "14b: the merge commit is signed" "gpgsig " \
                "$(git -C "$WT" cat-file commit HEAD)"
        fi
    done
}
need_merge_tree 14 && test_14_signing

# --- Test 15: a failed fetch is reported, never read past ---
# The tracking ref still equals HEAD, but the remote is unreachable: the pull
# must defer with the transport error, not report "up to date".
echo "--- Test 15: an unreachable upstream defers with the fetch error ---"
setup_crew_remote_fixture peer_only
git -C "$REPO" remote set-url origin "$ROOT/missing.git"
assert_eq "15: fixture: the cached upstream equals HEAD" "$(git -C "$WT" rev-parse HEAD)" \
    "$(git -C "$WT" rev-parse '@{u}')"
head_before="$(git -C "$WT" rev-parse HEAD)"
out="$(run_pull)"
assert_contains "15: the pull is deferred as a failed fetch" "PULL_RESULT:deferred|fetch_failed" "$out"
assert_eq "15: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
out="$(run_pull --no-batch)"
assert_contains "15: non-batch warns about the fetch" "git pull warning: fetch_failed" "$out"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

[[ "$FAIL" -eq 0 ]] || { echo "SOME TESTS FAILED"; exit 1; }
echo "ALL TESTS PASSED"
