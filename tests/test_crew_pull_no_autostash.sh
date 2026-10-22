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
# Cells 16-17 (t2029): a conflict confined to the runner's own
# _runner_alive.yaml is resolved field by field in memory and converges — the
# remote stop is honoured, the rest of the merge tree is git's own — while any
# other conflict, an unreadable side, or a peer naming another runner defers.
#
# Cells 18-25 (t2028): the other writers of the worktree — addwork and setmode
# (shell) and git_commit_push_if_changes (the runner, `ait crew status set`) —
# never strand, conclude or join an unfinished merge or rebase. A PATH `git`
# wrapper fakes merge-tree's exit status and runs a concurrent writer at an
# exact point of the commit sequence; the Python side uses a second harness on
# the same git_cmd seam. Each injection cell first checks that the concurrent
# writer really produced its state (INJECTED:ok), and controls with ordinary
# concurrent commits pin that healthy concurrency still commits and publishes.
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
  harness.py <scripts> runner <wt> --crew C --stub-root D [--once] [--inject-after-fetch] [--interval N]
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
ap.add_argument("--interval", type=int, default=30)
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
    rc = r.run_loop(WT, args.crew, args.interval, 3, args.once, False, True)
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
#                runner_stop_wide — runner_stop, plus the peer adds peer_only.txt
#                runner_stop_and_agent — runner_stop and agent_conflict, one commit
#                runner_takeover — the peer rewrites the runner's pid, hostname
#                                  and heartbeat lines (another runner took over)
#                status_conflict — the peer sets w1's launch_mode (conflicts
#                                  with a setmode of w1)
#                meta_conflict — the peer registers w3 in _crew_meta.yaml's
#                                agents list (conflicts with an addwork)
# Optional second argument: `nested` commits nested/dir/keep.txt before
# "runner: started", so the merge base carries a subtree; `cyclic_note`
# appends a self-referencing value to the base runner file (after its last
# line, so it stays out of every peer edit's hunk).
# Sets: ROOT REPO WT PEER REMOTE BRANCH PEER_SHA STUB
setup_crew_remote_fixture() {
    local peer_change="$1" layout="${2:-}"
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

    if [[ "$layout" == nested ]]; then
        mkdir -p "$WT/nested/dir"
        echo "kept across the merge" > "$WT/nested/dir/keep.txt"
        git -C "$WT" add nested/dir/keep.txt
        git -C "$WT" commit -m "crew: nested file" --quiet
    fi

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
    if [[ "$layout" == cyclic_note ]]; then
        printf '%s\n' 'note: &n {self: *n}' >> "$WT/_runner_alive.yaml"
    fi
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
        runner_stop_wide)
            sed 's/^requested_action: null$/requested_action: stop/' \
                "$PEER/_runner_alive.yaml" > "$PEER/_runner_alive.yaml.tmp"
            mv "$PEER/_runner_alive.yaml.tmp" "$PEER/_runner_alive.yaml"
            echo "from another host" > "$PEER/peer_only.txt"
            git -C "$PEER" add _runner_alive.yaml peer_only.txt
            git -C "$PEER" commit -m "peer: request runner stop, add peer_only.txt" --quiet
            ;;
        runner_stop_and_agent)
            sed 's/^requested_action: null$/requested_action: stop/' \
                "$PEER/_runner_alive.yaml" > "$PEER/_runner_alive.yaml.tmp"
            mv "$PEER/_runner_alive.yaml.tmp" "$PEER/_runner_alive.yaml"
            sed "s/^last_heartbeat:.*/last_heartbeat: '2026-10-15 10:01:00'/" \
                "$PEER/w1_alive.yaml" > "$PEER/w1_alive.yaml.tmp"
            mv "$PEER/w1_alive.yaml.tmp" "$PEER/w1_alive.yaml"
            git -C "$PEER" commit -am "peer: request runner stop, w1 heartbeat" --quiet
            ;;
        runner_stop_bad_utf8)
            # The stop line ends in a comment holding a byte that is not UTF-8.
            { sed -n '1,7p' "$PEER/_runner_alive.yaml"; printf 'requested_action: stop # \377\n'; } \
                > "$PEER/_runner_alive.yaml.tmp"
            mv "$PEER/_runner_alive.yaml.tmp" "$PEER/_runner_alive.yaml"
            git -C "$PEER" commit -am "peer: request runner stop (bad bytes)" --quiet
            ;;
        runner_stop_bad_timestamp)
            # An unquoted timestamp YAML cannot construct (month 99).
            sed -e 's/^requested_action: null$/requested_action: stop/' \
                -e 's/^last_heartbeat: .*/last_heartbeat: 2026-99-99 10:00:00/' \
                "$PEER/_runner_alive.yaml" > "$PEER/_runner_alive.yaml.tmp"
            mv "$PEER/_runner_alive.yaml.tmp" "$PEER/_runner_alive.yaml"
            git -C "$PEER" commit -am "peer: request runner stop (bad timestamp)" --quiet
            ;;
        runner_takeover)
            sed -e 's/^pid: 4242$/pid: 9999/' -e 's/^hostname: crewhost$/hostname: otherhost/' \
                -e "s/^last_heartbeat: .*/last_heartbeat: '2026-10-15 10:07:00'/" \
                -e "s/^next_check_at: .*/next_check_at: '2026-10-15 10:07:30'/" \
                "$PEER/_runner_alive.yaml" > "$PEER/_runner_alive.yaml.tmp"
            mv "$PEER/_runner_alive.yaml.tmp" "$PEER/_runner_alive.yaml"
            git -C "$PEER" commit -am "peer: another runner took over" --quiet
            ;;
        status_conflict)
            sed 's/^launch_mode: .*/launch_mode: openshell_headless/' \
                "$PEER/w1_status.yaml" > "$PEER/w1_status.yaml.tmp"
            mv "$PEER/w1_status.yaml.tmp" "$PEER/w1_status.yaml"
            git -C "$PEER" commit -am "peer: w1 launch_mode" --quiet
            ;;
        meta_conflict)
            sed 's/^agents: \[w1\]$/agents: [w1, w3]/' \
                "$PEER/_crew_meta.yaml" > "$PEER/_crew_meta.yaml.tmp"
            mv "$PEER/_crew_meta.yaml.tmp" "$PEER/_crew_meta.yaml"
            git -C "$PEER" commit -am "peer: register w3" --quiet
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

# Rewrite one line of the crew worktree's runner file: set_runner_line <sed expr>
set_runner_line() {
    sed "$1" "$WT/_runner_alive.yaml" > "$WT/_runner_alive.yaml.tmp" &&
        mv "$WT/_runner_alive.yaml.tmp" "$WT/_runner_alive.yaml"
}

# merge-tree's verdict on two commits: "<exit>|<conflicted paths, comma-joined>|<tree>"
merge_tree_verdict() {
    local out rc
    out="$(git -C "$WT" merge-tree --write-tree --no-messages --name-only "$1" "$2")"
    rc=$?
    printf '%s|%s|%s' "$rc" "$(printf '%s\n' "$out" | sed -n '2,$p' | paste -sd, -)" \
        "$(printf '%s\n' "$out" | head -n1)"
}

# --- Test 16a: a conflict confined to the runner file converges ---
# The runner restarted with interval: 60 (line 7) while a peer set
# requested_action: stop (line 8): adjacent edits, a real conflict. The pull
# resolves the runner file field by field in memory; every other path of the
# merge tree — a nested file from the base, the peer's new file, the local new
# file — must be exactly what git's own merge produced.
test_16a_runner_file_conflict_converges() {
    echo "--- Test 16a: a runner-file conflict converges; the rest of the tree is git's merge ---"
    setup_crew_remote_fixture runner_stop_wide nested
    set_runner_line "s/^interval: 30$/interval: 60/"
    echo "local" > "$WT/local_only.txt"
    # Root names a text-mode tree rebuild would mangle: a CR (newline
    # translation turns it into a LF) and a byte that is not UTF-8.
    local cr_name=$'cr\rname.txt' raw_name=$'latin\xe9.txt'
    echo "cr" > "$WT/$cr_name"
    echo "raw" > "$WT/$raw_name"
    git -C "$WT" add -- _runner_alive.yaml local_only.txt "$cr_name" "$raw_name"
    git -C "$WT" commit -qm "runner: restarted with interval 60"
    local head_before out verdict conflicted_tree expected actual base
    head_before="$(git -C "$WT" rev-parse HEAD)"
    out="$(run_pull)"
    verdict="$(merge_tree_verdict "$head_before" "$PEER_SHA")"
    assert_eq "16a: control: git reports a conflict on the runner file only" \
        "1|_runner_alive.yaml" "${verdict%|*}"
    conflicted_tree="${verdict##*|}"
    assert_contains "16a: the pull merged" "PULL_RESULT:ok|merged" "$out"
    assert_contains "16a: the pull names the resolved file" "resolved _runner_alive.yaml" "$out"
    assert_eq "16a: HEAD's first parent is the pre-pull commit" "$head_before" \
        "$(git -C "$WT" rev-parse -q --verify 'HEAD^1')"
    assert_eq "16a: HEAD's second parent is the peer commit" "$PEER_SHA" \
        "$(git -C "$WT" rev-parse -q --verify 'HEAD^2')"
    assert_contains "16a: the merged runner file keeps the local interval" "interval: 60" \
        "$(git -C "$WT" show HEAD:_runner_alive.yaml)"
    assert_contains "16a: the merged runner file carries the remote stop" "requested_action: stop" \
        "$(git -C "$WT" show HEAD:_runner_alive.yaml)"
    assert_not_contains "16a: no conflict markers were committed" "<<<<<<<" \
        "$(git -C "$WT" show HEAD:_runner_alive.yaml)"
    expected="$(git -C "$WT" ls-tree -r "$conflicted_tree" | grep -v $'\t_runner_alive.yaml$')"
    actual="$(git -C "$WT" ls-tree -r HEAD | grep -v $'\t_runner_alive.yaml$')"
    assert_contains "16a: control: git's merge carries the nested file" "nested/dir/keep.txt" "$expected"
    assert_contains "16a: control: git's merge carries the CR name" '"cr\rname.txt"' "$expected"
    assert_contains "16a: control: git's merge carries the non-UTF-8 name" '"latin\351.txt"' "$expected"
    # ls-tree quotes unusual names (core.quotePath), so this comparison is exact.
    assert_eq "16a: every other path, mode and blob is git's own merge" "$expected" "$actual"
    assert_eq "16a: the CR name survived byte for byte" "present" \
        "$(git -C "$WT" cat-file -e "HEAD:$cr_name" 2>/dev/null && echo present || echo absent)"
    assert_eq "16a: no LF-translated twin was created" "absent" \
        "$(git -C "$WT" cat-file -e "HEAD:"$'cr\nname.txt' 2>/dev/null && echo present || echo absent)"
    assert_eq "16a: the non-UTF-8 name survived byte for byte" "present" \
        "$(git -C "$WT" cat-file -e "HEAD:$raw_name" 2>/dev/null && echo present || echo absent)"
    base="$(git -C "$WT" merge-base "$head_before" "$PEER_SHA")"
    assert_eq "16a: the nested file is the merge base's blob" \
        "$(git -C "$WT" rev-parse "$base:nested/dir/keep.txt")" \
        "$(git -C "$WT" rev-parse HEAD:nested/dir/keep.txt 2>/dev/null)"
    assert_eq "16a: the peer's new file landed" "present" \
        "$(git -C "$WT" cat-file -e HEAD:peer_only.txt 2>/dev/null && echo present || echo absent)"
    assert_eq "16a: the local new file was kept" "present" \
        "$(git -C "$WT" cat-file -e HEAD:local_only.txt 2>/dev/null && echo present || echo absent)"
    assert_eq "16a: the worktree matches the merge" "clean" \
        "$(git -C "$WT" diff --quiet HEAD -- _runner_alive.yaml && echo clean || echo dirty)"
    assert_eq "16a: no merge was left in progress" "" "$(merge_head_state)"
    assert_eq "16a: no unmerged entries" "" "$(git -C "$WT" ls-files -u)"
    assert_eq "16a: nothing was stashed" "" "$(git -C "$WT" stash list)"
}
need_merge_tree 16a && test_16a_runner_file_conflict_converges

# --- Test 16b: the running runner honours a stop through the conflict ---
# A runner started with --interval 60: its own "runner: started" commit
# rewrites line 7 next to the peer's line 8, so before t2029 every pull
# deferred and the stop was never seen.
test_16b_runner_honours_stop_through_conflict() {
    echo "--- Test 16b: run_loop converges a conflicted runner file and honours the stop ---"
    setup_crew_remote_fixture runner_stop
    dirty_agent_heartbeat
    local out rc merge
    out="$(run_runner --once --interval 60)"; rc=$?
    assert_eq "16b: run_loop exits 0" "0" "$rc"
    assert_contains "16b: the remote stop was honoured" "SHUTDOWN:complete" "$out"
    assert_not_contains "16b: no agent was launched before the stop was seen" "LAUNCH_STUB:" "$out"
    assert_eq "16b: the peer's stop commit was merged" "merged" \
        "$(git -C "$WT" merge-base --is-ancestor "$PEER_SHA" HEAD && echo merged || echo missing)"
    assert_eq "16b: the shutdown push converged (remote head == HEAD)" \
        "$(git -C "$WT" rev-parse HEAD)" "$(remote_head)"
    merge="$(git -C "$WT" rev-list --merges -n1 HEAD)"
    assert_eq "16b: control: the merged commits really conflicted" "1|_runner_alive.yaml" \
        "$(v="$(merge_tree_verdict "$merge^1" "$merge^2")"; printf '%s' "${v%|*}")"
    assert_contains "16b: the merge commit names the resolved file" "resolved _runner_alive.yaml" \
        "$(git -C "$WT" log -1 --format=%s "$merge" 2>/dev/null)"
    assert_contains "16b: the merge keeps the runner's interval" "interval: 60" \
        "$(git -C "$WT" show "$merge:_runner_alive.yaml" 2>/dev/null)"
    assert_contains "16b: the merge carries the remote stop" "requested_action: stop" \
        "$(git -C "$WT" show "$merge:_runner_alive.yaml" 2>/dev/null)"
    assert_contains "16b: the committed runner file says stopped" "status: stopped" \
        "$(git -C "$WT" show HEAD:_runner_alive.yaml)"
    assert_eq "16b: no merge was left in progress" "" "$(merge_head_state)"
    assert_eq "16b: nothing was stashed" "" "$(git -C "$WT" stash list)"
    assert_eq "16b: the agent's file bytes are unchanged" "$dirty_sha" "$(file_sha "$dirty_file")"
    assert_eq "16b: the agent's file was never rewritten (inode+ctime)" "$dirty_ident" \
        "$(file_ident "$dirty_file")"
}
need_merge_tree 16b && test_16b_runner_honours_stop_through_conflict

# assert_runner_conflict_defers <label> <expected PULL_RESULT line>
# Runs the pull on the prepared fixture: it must defer with exactly that
# detail and leave HEAD, the runner file's bytes and the merge state alone.
assert_runner_conflict_defers() {
    local label="$1" expected="$2" head_before alive_sha out
    head_before="$(git -C "$WT" rev-parse HEAD)"
    alive_sha="$(file_sha "$WT/_runner_alive.yaml")"
    out="$(run_pull)"
    assert_eq "$label: the pull defers with the reason" "$expected" \
        "$(printf '%s\n' "$out" | grep '^PULL_RESULT:')"
    assert_eq "$label: HEAD did not move" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
    assert_eq "$label: the runner file's bytes are unchanged" "$alive_sha" \
        "$(file_sha "$WT/_runner_alive.yaml")"
    assert_eq "$label: no merge was left in progress" "" "$(merge_head_state)"
    assert_eq "$label: no unmerged entries" "" "$(git -C "$WT" ls-files -u)"
    assert_eq "$label: nothing was stashed" "" "$(git -C "$WT" stash list)"
}

# --- Test 16c: any other conflict, or an unreadable side, still defers ---
test_16c_other_conflicts_defer() {
    echo "--- Test 16c(i): a second conflicted path keeps today's deferral ---"
    setup_crew_remote_fixture runner_stop_and_agent
    set_runner_line "s/^interval: 30$/interval: 60/"
    sed "s/^last_heartbeat:.*/last_heartbeat: '2026-10-15 10:02:00'/" \
        "$WT/w1_alive.yaml" > "$WT/w1_alive.yaml.tmp" && mv "$WT/w1_alive.yaml.tmp" "$WT/w1_alive.yaml"
    git -C "$WT" commit -qam "runner: iteration 12"
    assert_runner_conflict_defers "16c(i)" \
        "PULL_RESULT:deferred|merge_conflict: _runner_alive.yaml, w1_alive.yaml"

    echo "--- Test 16c(ii): an unparseable runner file defers ---"
    setup_crew_remote_fixture runner_stop
    local_commit _runner_alive.yaml "s/^interval: 30$/interval: [60/" "runner: broken write"
    assert_runner_conflict_defers "16c(ii)" \
        "PULL_RESULT:deferred|merge_conflict: _runner_alive.yaml (runner file unreadable on one side)"

    # An incoming blob the runner cannot decode or construct is an unreadable
    # side — a deferral, never an exception that ends the runner.
    local peer_case
    for peer_case in bad_utf8 bad_timestamp; do
        echo "--- Test 16c($peer_case): an unreadable incoming runner file defers ---"
        setup_crew_remote_fixture "runner_stop_$peer_case"
        local_commit _runner_alive.yaml "s/^interval: 30$/interval: 60/" "runner: restarted"
        assert_runner_conflict_defers "16c($peer_case)" \
            "PULL_RESULT:deferred|merge_conflict: _runner_alive.yaml (runner file unreadable on one side)"
    done

    # A self-referencing value parses, but every side loads its own copy and
    # comparing them recurses without end. It must defer, not raise.
    echo "--- Test 16c(cyclic): a self-referencing runner-file value defers ---"
    setup_crew_remote_fixture runner_stop cyclic_note
    assert_contains "16c(cyclic): fixture: the base runner file carries the cyclic value" \
        "note: &n {self: *n}" "$(git -C "$WT" show HEAD:_runner_alive.yaml)"
    local_commit _runner_alive.yaml "s/^interval: 30$/interval: 60/" "runner: restarted"
    assert_runner_conflict_defers "16c(cyclic)" \
        "PULL_RESULT:deferred|merge_conflict: _runner_alive.yaml (runner file unreadable on one side)"
}
need_merge_tree 16c && test_16c_other_conflicts_defer

# --- Test 16d: a peer naming another runner defers (runner_identity_guard) ---
# Another runner took over on the peer (pid/hostname/heartbeat, lines 2-6)
# while this one restarted with interval: 60 (line 7). The field merge would
# overwrite the other runner's claim, so the pull defers instead.
test_16d_competing_runner_defers() {
    echo "--- Test 16d: competing runner identities defer ---"
    setup_crew_remote_fixture runner_takeover
    local_commit _runner_alive.yaml "s/^interval: 30$/interval: 60/" "runner: restarted"
    local head_before
    head_before="$(git -C "$WT" rev-parse HEAD)"
    assert_runner_conflict_defers "16d" \
        "PULL_RESULT:deferred|merge_conflict: _runner_alive.yaml (competing runner identities: otherhost/9999 vs crewhost/4242)"
    local verdict
    verdict="$(merge_tree_verdict "$head_before" "$PEER_SHA")"
    assert_eq "16d: control: git reports a conflict on the runner file only" \
        "1|_runner_alive.yaml" "${verdict%|*}"
}
need_merge_tree 16d && test_16d_competing_runner_defers

# --- Test 17: the runner file's field-merge and identity rules (pure functions) ---
echo "--- Test 17: runner-file field merge and identity guard table ---"
table="$("$AITASK_PYTHON" - "$PROJECT_DIR/.aitask-scripts" 2>&1 <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import agentcrew.agentcrew_utils as u

def merged(name, base, ours, theirs, key):
    res = u._merge_runner_alive_fields(base, ours, theirs)
    if res is None:
        print(f"{name}|<unresolved>")
    else:
        print(f"{name}|{repr(res[key]) if key in res else '<absent>'}")

ra = "requested_action"
merged("status_theirs_only", {"status": "running"}, {"status": "running"}, {"status": "stopped"}, "status")
merged("hostname_theirs_only", {"hostname": "a"}, {"hostname": "a"}, {"hostname": "b"}, "hostname")
merged("owned_absent_on_ours", {"interval": 30}, {}, {"interval": 30}, "interval")
merged("interval_both_changed", {"interval": 30}, {"interval": 60}, {"interval": 90}, "interval")
merged("ra_theirs_stop", {ra: None}, {ra: None}, {ra: "stop"}, ra)
merged("ra_ours_stop", {ra: None}, {ra: "stop"}, {ra: None}, ra)
merged("ra_addadd_ours_stop", {}, {ra: "stop"}, {ra: None}, ra)
merged("ra_historical_stop_cleared", {ra: "stop"}, {ra: None}, {ra: "stop"}, ra)
merged("ra_theirs_cleared", {ra: "stop"}, {ra: "stop"}, {ra: None}, ra)
merged("ra_both_changed_no_stop", {ra: None}, {ra: "hold"}, {ra: "wait"}, ra)
merged("other_theirs_only", {"note": "a"}, {"note": "a"}, {"note": "b"}, "note")
merged("other_both_changed", {"note": "a"}, {"note": "b"}, {"note": "c"}, "note")
merged("other_deleted_one_side", {"note": "a"}, {}, {"note": "a"}, "note")
order = u._merge_runner_alive_fields({}, {"a": 1, "b": 2}, {"c": 3, "a": 1, "b": 2})
print("key_order|" + ",".join(order))

def ident(name, base, ours, theirs):
    print(f"{name}|{u._competing_runner_identity(base, ours, theirs)}")

h1 = {"hostname": "h", "pid": 1}
ident("id_takeover", h1, h1, {"hostname": "o", "pid": 9})
ident("id_unchanged", h1, h1, h1)
ident("id_ours_restarted", h1, {"hostname": "h", "pid": 2}, h1)
ident("id_addadd_equal", {}, h1, h1)
PY
)"
expected_table="status_theirs_only|'running'
hostname_theirs_only|'a'
owned_absent_on_ours|<absent>
interval_both_changed|60
ra_theirs_stop|'stop'
ra_ours_stop|'stop'
ra_addadd_ours_stop|'stop'
ra_historical_stop_cleared|None
ra_theirs_cleared|None
ra_both_changed_no_stop|'wait'
other_theirs_only|'b'
other_both_changed|<unresolved>
other_deleted_one_side|<absent>
key_order|a,b,c
id_takeover|True
id_unchanged|False
id_ours_restarted|False
id_addadd_equal|False"
assert_eq "17: the field-merge and identity table" "$expected_table" "$table"

# =============================================================================
# Cells 18-25 (t2028): the shell writers and git_commit_push_if_changes
# =============================================================================

REAL_GIT="$(command -v git)"

# Another crew process acting once, at the moment a harness picks:
#   merge      — commits the shared staged index, then opens a merge of a side
#                commit on a disjoint path. A bare `git merge` refuses on a
#                dirty index, so this is the only way one can start once the
#                writer under test has staged.
#   commit     — an ordinary heartbeat commit of the shared index (it takes the
#                staged change of the writer under test with it)
#   commit-own — an ordinary heartbeat commit of _runner_alive.yaml alone
#                (--only: the other staged changes stay staged)
# Always the real git, never the PATH wrapper. Writes one INJECTED: line to
# $HARNESS_INJECT_LOG and nothing to stdout.
WRITER="$HARNESS_DIR/concurrent_writer.sh"
cat > "$WRITER" <<'SHEOF'
#!/usr/bin/env bash
wt="$1" kind="$2"
g() { "$REAL_GIT" -C "$wt" "$@"; }
say() { printf '%s\n' "$*" >> "$HARNESS_INJECT_LOG"; }
heartbeat() {
    sed "s/^last_heartbeat: .*/last_heartbeat: '2026-10-15 10:09:$1'/" "$wt/_runner_alive.yaml" \
        > "$wt/_runner_alive.yaml.tmp" && mv "$wt/_runner_alive.yaml.tmp" "$wt/_runner_alive.yaml"
}
case "$kind" in
    merge)
        g commit --quiet -m "concurrent writer" || { say "INJECTED:failed commit $?"; exit 0; }
        concurrent="$(g rev-parse HEAD)"
        blob="$(printf 'injected\n' | g hash-object -w --stdin)" &&
            tree="$( { g ls-tree HEAD; printf '100644 blob %s\tinjected.txt\n' "$blob"; } | g mktree)" &&
            side="$(g commit-tree "$tree" -p HEAD -m "another process's merge")" ||
            { say "INJECTED:failed side $?"; exit 0; }
        g merge --no-commit --no-ff --no-autostash --quiet "$side" >/dev/null 2>&1 ||
            { say "INJECTED:failed merge $?"; exit 0; }
        merge_head="$(g rev-parse -q --verify MERGE_HEAD)" || { say "INJECTED:failed merge_head 1"; exit 0; }
        say "INJECTED:ok merge $concurrent $merge_head"
        ;;
    commit)
        heartbeat 11
        g add _runner_alive.yaml && g commit --quiet -m "concurrent heartbeat" ||
            { say "INJECTED:failed commit $?"; exit 0; }
        say "INJECTED:ok commit $(g rev-parse HEAD)"
        ;;
    commit-own)
        heartbeat 22
        g commit --quiet -m "concurrent heartbeat" --only -- _runner_alive.yaml ||
            { say "INJECTED:failed commit $?"; exit 0; }
        say "INJECTED:ok commit-own $(g rev-parse HEAD)"
        ;;
    *) say "INJECTED:failed kind 2" ;;
esac
SHEOF
chmod +x "$WRITER"

# PATH stand-in for git, for the crew shell scripts. Logs each subcommand to
# $HARNESS_GIT_LOG; HARNESS_GIT_MERGE_TREE_RC=<rc> answers merge-tree with that
# status and no output (129 = a git without --write-tree);
# HARNESS_GIT_AFTER_REBASE_STAGE=<file> appends a line to that tracked file and
# stages it after a rebase that stopped; HARNESS_GIT_INJECT=<kind>@<point> runs
# the concurrent writer once, at after-add | after-write-tree |
# before-update-ref | after-update-ref.
GITWRAP_DIR="$HARNESS_DIR/gitwrap"
mkdir -p "$GITWRAP_DIR"
cat > "$GITWRAP_DIR/git" <<'SHEOF'
#!/usr/bin/env bash
args=("$@")
i=0 wt="." sub=""
while (( i < ${#args[@]} )); do
    case "${args[i]}" in
        -C) wt="${args[i+1]}"; i=$((i + 2)) ;;
        -c) i=$((i + 2)) ;;
        -*) i=$((i + 1)) ;;
        *)  sub="${args[i]}"; break ;;
    esac
done
[[ -n "${HARNESS_GIT_LOG:-}" ]] && printf '%s\n' "$sub" >> "$HARNESS_GIT_LOG"
if [[ "$sub" == merge-tree && -n "${HARNESS_GIT_MERGE_TREE_RC:-}" ]]; then
    exit "$HARNESS_GIT_MERGE_TREE_RC"
fi
point="${HARNESS_GIT_INJECT#*@}"
inject() {
    [[ -n "${HARNESS_GIT_INJECT:-}" && ! -e "$HARNESS_INJECT_LOG.done" ]] || return 0
    : > "$HARNESS_INJECT_LOG.done"
    "$WRITER" "$wt" "${HARNESS_GIT_INJECT%@*}" >&2
}
[[ "$point:$sub" == before-update-ref:update-ref ]] && inject
"$REAL_GIT" "$@"
rc=$?
case "$point:$sub" in
    after-add:add|after-write-tree:write-tree|after-update-ref:update-ref) inject ;;
esac
if [[ "$sub" == rebase && -n "${HARNESS_GIT_AFTER_REBASE_STAGE:-}" ]]; then
    gp="$("$REAL_GIT" -C "$wt" rev-parse --git-path rebase-merge)"
    [[ "$gp" == /* ]] || gp="$wt/$gp"
    if [[ -e "$gp" ]]; then
        echo "staged_by: another crew process" >> "$wt/$HARNESS_GIT_AFTER_REBASE_STAGE"
        "$REAL_GIT" -C "$wt" add -- "$HARNESS_GIT_AFTER_REBASE_STAGE"
    fi
fi
exit "$rc"
SHEOF
chmod +x "$GITWRAP_DIR/git"

# git_commit_push_if_changes through its real code, with the concurrent writer
# run once at <point> through the git_cmd seam.
COMMIT_HARNESS="$HARNESS_DIR/crew_commit_harness.py"
cat > "$COMMIT_HARNESS" <<'PYEOF'
"""crew_commit_harness.py <scripts> <wt> <message> [--inject <kind>@<point>]"""
import os
import subprocess
import sys

scripts, wt, message = sys.argv[1:4]
inject = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "--inject" else ""
sys.path.insert(0, scripts)
import agentcrew.agentcrew_utils as u  # noqa: E402

kind, _, point = inject.partition("@")
WT = os.path.abspath(wt)
real_git_cmd = u.git_cmd
done = []


def writer():
    if inject and not done:
        done.append(True)
        subprocess.run([os.environ["WRITER"], WT, kind], check=False, stdout=sys.stderr)


def wrapped_git_cmd(worktree, *a, **kw):
    sub = a[0] if a else ""
    if point == "before-update-ref" and sub == "update-ref":
        writer()
    result = real_git_cmd(worktree, *a, **kw)
    if (point, sub) in (("after-add", "add"), ("after-write-tree", "write-tree"),
                        ("after-update-ref", "update-ref")):
        writer()
    return result


u.git_cmd = wrapped_git_cmd
u.git_commit_push_if_changes(WT, message, batch=True)
print("COMMIT_HARNESS:done", flush=True)
PYEOF

# new_inject_log — a fresh log for this cell's concurrent writer.
new_inject_log() {
    INJECT_LOG="$ROOT/inject.log"
    rm -f "$INJECT_LOG" "$INJECT_LOG.done" "$ROOT/git.log"
    : > "$INJECT_LOG"
}

# run_cli [VAR=value ...] -- <script> <args...> — a crew script from $REPO with
# the git wrapper first on PATH. Sets RC OUT ERR.
run_cli() {
    local envs=() script
    while [[ "$1" != "--" ]]; do envs+=("$1"); shift; done
    shift
    script="$1"
    shift
    (cd "$REPO" && env PATH="$GITWRAP_DIR:$PATH" REAL_GIT="$REAL_GIT" WRITER="$WRITER" \
        HARNESS_INJECT_LOG="$INJECT_LOG" HARNESS_GIT_LOG="$ROOT/git.log" "${envs[@]}" \
        bash ".aitask-scripts/$script" "$@") >"$ROOT/out" 2>"$ROOT/err"
    RC=$?
    OUT="$(cat "$ROOT/out")"
    ERR="$(cat "$ROOT/err")"
}
setmode_w1() { run_cli "${@:2}" -- aitask_crew_setmode.sh --crew "$CREW_ID" --name w1 --mode "$1"; }
addwork_as() {
    run_cli "${@:2}" -- aitask_crew_addwork.sh --crew "$CREW_ID" --name "$1" \
        --work2do /dev/null --type impl --batch
}

# run_commit <message> [<kind>@<point>] — the Python commit path. Sets RC OUT ERR.
run_commit() {
    local inj=()
    [[ -n "${2:-}" ]] && inj=(--inject "$2")
    env REAL_GIT="$REAL_GIT" WRITER="$WRITER" HARNESS_INJECT_LOG="$INJECT_LOG" \
        "$AITASK_PYTHON" "$COMMIT_HARNESS" "$PROJECT_DIR/.aitask-scripts" "$WT" "$1" "${inj[@]}" \
        >"$ROOT/out" 2>"$ROOT/err"
    RC=$?
    OUT="$(cat "$ROOT/out")"
    ERR="$(cat "$ROOT/err")"
}

# The real `ait crew status set`, from $REPO. Sets RC OUT ERR.
status_set_w1() {
    (cd "$REPO" && "$AITASK_PYTHON" "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" \
        --crew "$CREW_ID" --agent w1 set --status "$1") >"$ROOT/out" 2>"$ROOT/err"
    RC=$?
    OUT="$(cat "$ROOT/out")"
    ERR="$(cat "$ROOT/err")"
}

# The worktree's unfinished operation, as the runner sees it (the Python
# crew_merge_state, which predates t2028 and is what the runner holds on).
crew_state() {
    "$AITASK_PYTHON" -c 'import sys
sys.path.insert(0, sys.argv[1])
from agentcrew.agentcrew_utils import crew_merge_state
print(crew_merge_state(sys.argv[2]) or "")' "$PROJECT_DIR/.aitask-scripts" "$WT"
}

# The same, from the shell twin the crew scripts refuse on.
crew_state_sh() {
    ( . "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" >/dev/null 2>&1; crew_merge_state "$WT" )
}

# HEAD | branch | index digest | state | MERGE_HEAD
wt_snapshot() {
    printf '%s|%s|%s|%s|%s' "$(git -C "$WT" rev-parse HEAD)" \
        "$(git -C "$WT" symbolic-ref -q HEAD)" \
        "$(git -C "$WT" ls-files -s | sha256sum | cut -d' ' -f1)" \
        "$(crew_state)" "$(merge_head_state)"
}

# assert_injected <cell> <kind> — the concurrent writer really ran, and for a
# merge MERGE_HEAD existed when it finished (the writer checks that before it
# prints INJECTED:ok). Sets INJECTED_COMMIT and, for a merge, INJECTED_MERGE_HEAD.
assert_injected() {
    local line
    line="$(grep '^INJECTED:' "$INJECT_LOG" 2>/dev/null | head -n1)"
    assert_contains "$1: setup: the concurrent writer ran ($2)" "INJECTED:ok $2 " "$line"
    INJECTED_COMMIT="$(printf '%s' "$line" | cut -d' ' -f3)"
    INJECTED_MERGE_HEAD="$(printf '%s' "$line" | cut -d' ' -f4)"
}

assert_linear() {
    assert_eq "$1: history stays linear" "" "$(git -C "$WT" rev-list --min-parents=2 HEAD)"
}

assert_no_unsafe_report() {
    assert_not_contains "$1: no unfinished-operation report" "unfinished" "$ERR"
    assert_not_contains "$1: no commit-skipped warning" "git commit skipped" "$ERR"
}

assert_published() {
    assert_eq "$1: the remote holds the local tip" "$(git -C "$WT" rev-parse HEAD)" "$(remote_head)"
}

# The crew worktree catches up with its upstream, so a push is a fast-forward.
catch_up_with_remote() {
    git -C "$WT" fetch --quiet && git -C "$WT" merge --ff-only --no-autostash --quiet '@{u}'
    assert_eq "fixture: the crew worktree is level with the remote" "$(remote_head)" \
        "$(git -C "$WT" rev-parse HEAD)"
}

# A stopped rebase in the crew worktree, made by hand: a local commit to
# <file> conflicts with the peer's.
stop_a_rebase_by_hand() {
    local_commit "$1" "$2" "local: conflicting edit"
    git -C "$WT" fetch --quiet
    git -C "$WT" rebase --no-autostash --quiet >/dev/null 2>&1
    assert_eq "fixture: the rebase stopped" "rebase_in_progress" "$(crew_state)"
}

# A merge left open in the crew worktree, made by hand (clean, uncommitted).
open_a_merge_by_hand() {
    local blob tree side
    blob="$(printf 'by hand\n' | git -C "$WT" hash-object -w --stdin)"
    tree="$( { git -C "$WT" ls-tree HEAD; printf '100644 blob %s\tby_hand.txt\n' "$blob"; } | git -C "$WT" mktree)"
    side="$(git -C "$WT" commit-tree "$tree" -p HEAD -m "a merge by hand")"
    git -C "$WT" merge --no-commit --no-ff --no-autostash --quiet "$side" >/dev/null 2>&1
    assert_eq "fixture: a merge is open" "merge_in_progress" "$(crew_state)"
}

# --- Test 18: a rebase that would conflict is never opened ---
test_18a_setmode_conflict_not_rebased() {
    echo "--- Test 18a: setmode, conflicting upstream → not rebased, nothing opened ---"
    setup_crew_remote_fixture status_conflict
    new_inject_log
    setmode_w1 interactive
    assert_eq "18a: setmode succeeds" "0" "$RC"
    assert_contains "18a: UPDATED printed" "UPDATED:w1:interactive" "$OUT"
    assert_eq "18a: no unfinished operation" "" "$(crew_state)"
    assert_eq "18a: HEAD is on the crew branch" "refs/heads/$BRANCH" "$(git -C "$WT" symbolic-ref -q HEAD)"
    assert_eq "18a: HEAD is setmode's commit" "crew: Set launch_mode=interactive for agent 'w1' in crew '$CREW_ID'" \
        "$(git -C "$WT" log -1 --format=%s)"
    assert_eq "18a: the remote is unchanged" "$PEER_SHA" "$(remote_head)"
    assert_contains "18a: the warning names the conflict" "not rebased onto its upstream: it conflicts in w1_status.yaml" "$ERR"
    assert_not_contains "18a: no rebase ran" "rebase" "$(cat "$ROOT/git.log")"
}
need_merge_tree 18a && test_18a_setmode_conflict_not_rebased

test_18b_addwork_conflict_not_rebased() {
    echo "--- Test 18b: addwork, conflicting upstream → not rebased, nothing opened ---"
    setup_crew_remote_fixture meta_conflict
    new_inject_log
    addwork_as w2
    assert_eq "18b: addwork succeeds" "0" "$RC"
    assert_contains "18b: ADDED printed" "ADDED:w2" "$OUT"
    assert_eq "18b: no unfinished operation" "" "$(crew_state)"
    assert_eq "18b: HEAD is on the crew branch" "refs/heads/$BRANCH" "$(git -C "$WT" symbolic-ref -q HEAD)"
    assert_eq "18b: HEAD is addwork's commit" "crew: Add agent 'w2' to crew '$CREW_ID'" \
        "$(git -C "$WT" log -1 --format=%s)"
    assert_eq "18b: the remote is unchanged" "$PEER_SHA" "$(remote_head)"
    assert_contains "18b: the warning names the conflict" "it conflicts in _crew_meta.yaml" "$ERR"
}
need_merge_tree 18b && test_18b_addwork_conflict_not_rebased

# --- Test 19: a rebase that stops anyway is left and reported, never aborted ---
echo "--- Test 19a: setmode, a stopped rebase (no merge proof) is left and reported ---"
setup_crew_remote_fixture status_conflict
new_inject_log
setmode_w1 interactive HARNESS_GIT_MERGE_TREE_RC=129
assert_exit_nonzero_rc "19a: setmode fails" "$RC"
assert_not_contains "19a: no UPDATED" "UPDATED:" "$OUT"
assert_eq "19a: the rebase is left in progress" "rebase_in_progress" "$(crew_state)"
assert_eq "19a: the remote is unchanged" "$PEER_SHA" "$(remote_head)"
assert_contains "19a: the report names it" "has an unfinished rebase (rebase_in_progress)" "$ERR"
assert_contains "19a: the report says it was not aborted" "left in progress, not aborted" "$ERR"
assert_contains "19a: the report carries the remedy" "rebase --abort" "$ERR"
assert_not_contains "19a: nothing pushed" "push" "$(cat "$ROOT/git.log")"

echo "--- Test 19b: addwork, a stopped rebase (no merge proof) is left and reported ---"
setup_crew_remote_fixture meta_conflict
new_inject_log
addwork_as w2 HARNESS_GIT_MERGE_TREE_RC=129
assert_exit_nonzero_rc "19b: addwork fails" "$RC"
assert_not_contains "19b: no ADDED" "ADDED:" "$OUT"
assert_eq "19b: the rebase is left in progress" "rebase_in_progress" "$(crew_state)"
assert_eq "19b: the remote is unchanged" "$PEER_SHA" "$(remote_head)"
assert_contains "19b: addwork says the agent is registered but not published" \
    "is registered (committed) in crew '$CREW_ID' but not published" "$ERR"
assert_not_contains "19b: nothing pushed" "push" "$(cat "$ROOT/git.log")"

# --- Test 20: a write staged during the stopped rebase survives ---
echo "--- Test 20: a foreign write staged while the rebase is stopped survives ---"
setup_crew_remote_fixture status_conflict
new_inject_log
setmode_w1 interactive HARNESS_GIT_MERGE_TREE_RC=129 HARNESS_GIT_AFTER_REBASE_STAGE=_runner_alive.yaml
assert_exit_nonzero_rc "20: setmode fails" "$RC"
assert_eq "20: the rebase is left in progress" "rebase_in_progress" "$(crew_state)"
assert_contains "20: the staged write is in the worktree" "staged_by: another crew process" \
    "$(cat "$WT/_runner_alive.yaml")"
assert_contains "20: the staged write is in the index" "staged_by: another crew process" \
    "$(git -C "$WT" show :_runner_alive.yaml)"

# --- Test 21: a failed merge proof never rebases ---
echo "--- Test 21: a merge proof that errors → no rebase, worktree as it was ---"
setup_crew_remote_fixture peer_only
new_inject_log
setmode_w1 interactive HARNESS_GIT_MERGE_TREE_RC=128
assert_eq "21: setmode succeeds" "0" "$RC"
assert_contains "21: UPDATED printed" "UPDATED:w1:interactive" "$OUT"
assert_contains "21: the warning says the proof failed" "the merge proof failed (git merge-tree exit 128)" "$ERR"
assert_not_contains "21: no rebase ran" "rebase" "$(cat "$ROOT/git.log")"
assert_eq "21: no unfinished operation" "" "$(crew_state)"
assert_eq "21: HEAD is setmode's commit" "crew: Set launch_mode=interactive for agent 'w1' in crew '$CREW_ID'" \
    "$(git -C "$WT" log -1 --format=%s)"

# --- Test 22: addwork and setmode refuse an existing unfinished operation ---
# test_22 <label> <merge|rebase> <setmode|addwork>
test_22() {
    local label="$1" state="$2" cli="$3" before status_sha
    echo "--- Test $label: $cli refuses a $state left in the worktree ---"
    if [[ "$state" == merge ]]; then
        setup_crew_remote_fixture peer_only
        open_a_merge_by_hand
    else
        setup_crew_remote_fixture agent_conflict
        stop_a_rebase_by_hand w1_alive.yaml "s/^last_heartbeat:.*/last_heartbeat: '2026-10-15 10:02:00'/"
    fi
    new_inject_log
    assert_eq "$label: the shell probe agrees with the runner's" "$(crew_state)" "$(crew_state_sh)"
    before="$(wt_snapshot)"
    status_sha="$(file_sha "$WT/w1_status.yaml")"
    if [[ "$cli" == setmode ]]; then
        setmode_w1 interactive
        assert_not_contains "$label: no UPDATED" "UPDATED:" "$OUT"
        assert_eq "$label: the status file is untouched" "$status_sha" "$(file_sha "$WT/w1_status.yaml")"
    else
        addwork_as w2
        assert_not_contains "$label: no ADDED" "ADDED:" "$OUT"
        assert_eq "$label: no agent file written" "" "$(cd "$WT" && ls w2_* 2>/dev/null)"
    fi
    assert_exit_nonzero_rc "$label: $cli fails" "$RC"
    assert_eq "$label: HEAD, index and state unchanged" "$before" "$(wt_snapshot)"
    assert_contains "$label: the refusal names the state" "${state}_in_progress" "$ERR"
}
test_22 22a merge setmode
test_22 22b merge addwork
test_22 22c rebase setmode
test_22 22d rebase addwork

# --- Test 23: concurrent writers during setmode's commit ---
# The fixture's peer commit is disjoint, so a setmode that commits rebases onto
# it and publishes.
test_23_merge() {
    local label="$1" point="$2" remote_before
    echo "--- Test $label: a merge opened at $point never gets concluded ---"
    setup_crew_remote_fixture peer_only
    new_inject_log
    remote_before="$(remote_head)"
    setmode_w1 interactive "HARNESS_GIT_INJECT=merge@$point"
    assert_injected "$label" merge
    assert_exit_nonzero_rc "$label: setmode fails" "$RC"
    assert_not_contains "$label: no UPDATED" "UPDATED:" "$OUT"
    assert_eq "$label: the merge is still open" "$INJECTED_MERGE_HEAD" "$(merge_head_state)"
    assert_eq "$label: HEAD is the concurrent writer's commit" "$INJECTED_COMMIT" "$(git -C "$WT" rev-parse HEAD)"
    assert_contains "$label: the refusal names the merge" "has an unfinished merge (merge_in_progress)" "$ERR"
    assert_eq "$label: the remote is unchanged" "$remote_before" "$(remote_head)"
}
test_23_merge 23a after-add
test_23_merge 23b after-write-tree
test_23_merge 23c before-update-ref

SETMODE_SUBJECT="crew: Set launch_mode=interactive for agent 'w1' in crew '$CREW_ID'"

echo "--- Test 23d: control — an own-path commit lands before setmode's swap → retried ---"
setup_crew_remote_fixture peer_only
new_inject_log
setmode_w1 interactive HARNESS_GIT_INJECT=commit-own@before-update-ref
assert_injected 23d commit-own
assert_eq "23d: setmode succeeds" "0" "$RC"
assert_contains "23d: UPDATED printed" "UPDATED:w1:interactive" "$OUT"
assert_eq "23d: setmode's commit lands on top of the concurrent one" \
    "$SETMODE_SUBJECT|concurrent heartbeat|peer: add peer_only.txt" \
    "$(git -C "$WT" log -3 --format=%s | paste -sd'|' -)"
assert_contains "23d: HEAD carries setmode's change" "launch_mode: interactive" "$(git -C "$WT" show HEAD:w1_status.yaml)"
assert_linear 23d
assert_no_unsafe_report 23d
assert_published 23d

echo "--- Test 23e: control — a commit takes setmode's staged change before its swap ---"
setup_crew_remote_fixture peer_only
new_inject_log
setmode_w1 interactive HARNESS_GIT_INJECT=commit@before-update-ref
assert_injected 23e commit
assert_eq "23e: setmode succeeds" "0" "$RC"
assert_contains "23e: UPDATED printed" "UPDATED:w1:interactive" "$OUT"
assert_eq "23e: no empty commit of setmode's own" "concurrent heartbeat|peer: add peer_only.txt" \
    "$(git -C "$WT" log -2 --format=%s | paste -sd'|' -)"
assert_contains "23e: HEAD carries setmode's change" "launch_mode: interactive" "$(git -C "$WT" show HEAD:w1_status.yaml)"
assert_linear 23e
assert_no_unsafe_report 23e
assert_published 23e

echo "--- Test 23f: control — an ordinary commit right after setmode's own ---"
setup_crew_remote_fixture peer_only
new_inject_log
setmode_w1 interactive HARNESS_GIT_INJECT=commit@after-update-ref
assert_injected 23f commit
assert_eq "23f: setmode succeeds" "0" "$RC"
assert_eq "23f: both commits, in order" "concurrent heartbeat|$SETMODE_SUBJECT|peer: add peer_only.txt" \
    "$(git -C "$WT" log -3 --format=%s | paste -sd'|' -)"
assert_linear 23f
assert_no_unsafe_report 23f
assert_published 23f
new_inject_log
setmode_w1 headless
assert_eq "23f: a later setmode still works" "0" "$RC"
assert_contains "23f: the later setmode committed" "launch_mode: headless" "$(git -C "$WT" show HEAD:w1_status.yaml)"

echo "--- Test 23g: control — a commit takes setmode's staged change right after the add ---"
setup_crew_remote_fixture peer_only
new_inject_log
setmode_w1 interactive HARNESS_GIT_INJECT=commit@after-add
assert_injected 23g commit
assert_eq "23g: setmode succeeds" "0" "$RC"
assert_eq "23g: no empty commit of setmode's own" "concurrent heartbeat|peer: add peer_only.txt" \
    "$(git -C "$WT" log -2 --format=%s | paste -sd'|' -)"
assert_contains "23g: HEAD carries setmode's change" "launch_mode: interactive" "$(git -C "$WT" show HEAD:w1_status.yaml)"
assert_no_unsafe_report 23g
assert_published 23g

# --- Test 24: git_commit_push_if_changes (the runner, `ait crew status set`) ---
set_w1_status() {
    sed "s/^status: .*/status: $1/" "$WT/w1_status.yaml" > "$WT/w1_status.yaml.tmp" &&
        mv "$WT/w1_status.yaml.tmp" "$WT/w1_status.yaml"
}

echo "--- Test 24a: a stopped rebase → nothing staged, nothing committed ---"
setup_crew_remote_fixture agent_conflict
stop_a_rebase_by_hand w1_alive.yaml "s/^last_heartbeat:.*/last_heartbeat: '2026-10-15 10:02:00'/"
new_inject_log
echo "dirty: yes" >> "$WT/w1_status.yaml"
before="$(wt_snapshot)"
run_commit "runner: iteration 1"
assert_eq "24a: HEAD, index and state unchanged" "$before" "$(wt_snapshot)"
assert_eq "24a: the change is still unstaged" "dirty" \
    "$(git -C "$WT" diff --quiet -- w1_status.yaml && echo clean || echo dirty)"
assert_contains "24a: the warning says why" "git commit skipped (runner: iteration 1): unfinished rebase_in_progress" "$ERR"

test_24_merge() {
    local label="$1" point="$2"
    echo "--- Test $label: a merge opened at $point never gets concluded ---"
    setup_crew_remote_fixture peer_only
    catch_up_with_remote
    new_inject_log
    set_w1_status Running
    run_commit "runner: iteration 2" "merge@$point"
    assert_injected "$label" merge
    assert_eq "$label: the merge is still open" "$INJECTED_MERGE_HEAD" "$(merge_head_state)"
    assert_eq "$label: HEAD is the concurrent writer's commit" "$INJECTED_COMMIT" "$(git -C "$WT" rev-parse HEAD)"
    assert_contains "$label: the warning names the merge" "unfinished merge_in_progress" "$ERR"
    assert_eq "$label: nothing pushed" "$PEER_SHA" "$(remote_head)"
}
test_24_merge 24b after-add
test_24_merge 24c before-update-ref

echo "--- Test 24d: control — an own-path commit lands before the swap → retried, pushed ---"
setup_crew_remote_fixture peer_only
catch_up_with_remote
new_inject_log
set_w1_status Completed
run_commit "agent w1: Running -> Completed" commit-own@before-update-ref
assert_injected 24d commit-own
assert_eq "24d: the commit lands on top of the concurrent one" \
    "agent w1: Running -> Completed|concurrent heartbeat" "$(git -C "$WT" log -2 --format=%s | paste -sd'|' -)"
assert_contains "24d: HEAD carries the status change" "status: Completed" "$(git -C "$WT" show HEAD:w1_status.yaml)"
assert_linear 24d
assert_no_unsafe_report 24d
assert_published 24d
out="$(run_runner --once 2>&1)"
assert_not_contains "24d: the runner then runs normally" "PULL_UNSAFE" "$out"

echo "--- Test 24e: control — a commit takes the staged change before the swap → still pushed ---"
setup_crew_remote_fixture peer_only
catch_up_with_remote
new_inject_log
set_w1_status Completed
run_commit "agent w1: Running -> Completed" commit@before-update-ref
assert_injected 24e commit
assert_eq "24e: no empty commit of its own" "concurrent heartbeat" "$(git -C "$WT" log -1 --format=%s)"
assert_contains "24e: HEAD carries the status change" "status: Completed" "$(git -C "$WT" show HEAD:w1_status.yaml)"
assert_linear 24e
assert_no_unsafe_report 24e
assert_published 24e

echo "--- Test 24f: control — an ordinary commit right after the swap ---"
setup_crew_remote_fixture peer_only
catch_up_with_remote
new_inject_log
set_w1_status Running
run_commit "runner: iteration 3" commit@after-update-ref
assert_injected 24f commit
assert_eq "24f: both commits, in order" "concurrent heartbeat|runner: iteration 3" \
    "$(git -C "$WT" log -2 --format=%s | paste -sd'|' -)"
assert_linear 24f
assert_no_unsafe_report 24f
new_inject_log
set_w1_status Completed
run_commit "runner: iteration 4"
assert_eq "24f: a later call commits normally" "runner: iteration 4" "$(git -C "$WT" log -1 --format=%s)"
assert_no_unsafe_report 24f
assert_published 24f

echo "--- Test 24g: \`ait crew status set\` during a stopped rebase ---"
setup_crew_remote_fixture agent_conflict
local_commit w1_status.yaml "s/^status: .*/status: Running/" "local: w1 running"
stop_a_rebase_by_hand w1_alive.yaml "s/^last_heartbeat:.*/last_heartbeat: '2026-10-15 10:02:00'/"
new_inject_log
head_before="$(git -C "$WT" rev-parse HEAD)"
status_set_w1 Completed
assert_contains "24g: the status is set" "STATUS_SET:w1:Running:Completed" "$OUT"
assert_contains "24g: the status file says so" "status: Completed" "$(cat "$WT/w1_status.yaml")"
assert_eq "24g: nothing committed" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
assert_eq "24g: the rebase is left alone" "rebase_in_progress" "$(crew_state)"
assert_contains "24g: the warning says the change is uncommitted" "git commit skipped (agent w1: Running -> Completed)" "$ERR"

echo "--- Test 24h: control — once the rebase is resolved, the same call commits ---"
git -C "$WT" rebase --abort
set_w1_status Completed
run_commit "agent w1: Running -> Completed"
assert_eq "24h: committed" "agent w1: Running -> Completed" "$(git -C "$WT" log -1 --format=%s)"
assert_no_unsafe_report 24h

# --- Test 24i: a staging failure is reported, never read as "no work" ---
echo "--- Test 24i: a held index.lock → git add fails → reported, never silently dropped ---"
setup_crew_remote_fixture peer_only
catch_up_with_remote
new_inject_log
index_lock="$(git -C "$WT" rev-parse --git-path index.lock)"
[[ "$index_lock" == /* ]] || index_lock="$WT/$index_lock"
: > "$index_lock"
head_before="$(git -C "$WT" rev-parse HEAD)"
setmode_w1 interactive
assert_exit_nonzero_rc "24i: setmode fails" "$RC"
assert_not_contains "24i: setmode prints no UPDATED" "UPDATED:" "$OUT"
assert_contains "24i: setmode names the failed add" "git add failed in crew worktree" "$ERR"
assert_eq "24i: setmode committed nothing" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
set_w1_status Completed
run_commit "agent w1: Running -> Completed"
assert_eq "24i: nothing committed" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
assert_contains "24i: the warning names the failed add" \
    "git commit skipped (agent w1: Running -> Completed): git add failed" "$ERR"
assert_contains "24i: the change is still in the worktree" "status: Completed" "$(cat "$WT/w1_status.yaml")"
rm -f "$index_lock"
run_commit "agent w1: Running -> Completed"
assert_eq "24i: control: with the lock gone the same call commits" "agent w1: Running -> Completed" \
    "$(git -C "$WT" log -1 --format=%s)"
assert_no_unsafe_report 24i

# --- Test 25: the shell probe and the runner's agree (clean, unknown) ---
echo "--- Test 25: shell and runner crew_merge_state agree ---"
assert_eq "25: clean worktree" "|" "$(crew_state)|$(crew_state_sh)"
saved_wt="$WT"
WT="$ROOT/not_a_repo"
mkdir -p "$WT"
assert_eq "25: git cannot answer → probe_failed" "probe_failed|probe_failed" "$(crew_state)|$(crew_state_sh)"
WT="$saved_wt"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

[[ "$FAIL" -eq 0 ]] || { echo "SOME TESTS FAILED"; exit 1; }
echo "ALL TESTS PASSED"
