#!/usr/bin/env bash
# test_sandbox_launch.sh — sandbox launcher seam + Docker backend (t1120_5).
#
# Unit suite over lib/sandbox_launch.py with a FAKE `docker` CLI on PATH
# (records argv, scripted state — the test_setup_find_modern_python.sh
# pattern): pure argv construction, refusals, handle probes, watchdog
# wall-clock kill + at-most-once death signalling (with negative controls),
# table-driven reap filtering, workspace-copy hygiene against a dirty
# fixture repo, the chatlink.spawn_seam re-export compat, and the backend
# registry sync assert. No real docker is ever touched.
# Run: bash tests/test_sandbox_launch.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/sandbox-launch-test-XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

mkdir -p "$SCRATCH/bin"

# ---- fake docker CLI: records argv (\x1f-separated), scripted state ------
cat > "$SCRATCH/bin/docker" <<'STUB'
#!/usr/bin/env bash
{ printf '%s\x1f' "$@"; printf '\n'; } >> "$DOCKER_LOG"
case "$1" in
    run)
        echo "cid-fake"
        exit "${FAKE_RUN_RC:-0}"
        ;;
    inspect)
        # State file: "<running> <exit_code>" (e.g. "true 0", "false 137").
        # Missing file = container removed (docker inspect fails).
        [[ -f "$FAKE_STATE_FILE" ]] || { echo "no such container" >&2; exit 1; }
        read -r running exit_code < "$FAKE_STATE_FILE"
        fmt="$3"
        if [[ "$fmt" == *ExitCode* ]]; then
            echo "$running $exit_code"
        else
            echo "$running"
        fi
        ;;
    ps)
        cat "${FAKE_PS_FILE:-/dev/null}"
        exit "${FAKE_PS_RC:-0}"
        ;;
    rm)
        # rm/-f: container gone (or dead) — flip the state file if present.
        [[ -n "${FAKE_STATE_FILE:-}" ]] && echo "false 137" > "$FAKE_STATE_FILE"
        exit "${FAKE_RM_RC:-0}"
        ;;
    *)
        exit 0
        ;;
esac
STUB
chmod +x "$SCRATCH/bin/docker"

"$PYTHON" - "$PROJECT_DIR" "$SCRATCH" <<'PYEOF'
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

root = Path(sys.argv[1])
scratch = Path(sys.argv[2])
sys.path.insert(0, str(root / ".aitask-scripts"))

os.environ["PATH"] = f"{scratch / 'bin'}:{os.environ['PATH']}"
DOCKER_LOG = scratch / "docker.log"
STATE_FILE = scratch / "state"
PS_FILE = scratch / "ps.out"
os.environ["DOCKER_LOG"] = str(DOCKER_LOG)
os.environ["FAKE_STATE_FILE"] = str(STATE_FILE)
os.environ["FAKE_PS_FILE"] = str(PS_FILE)

from lib import sandbox_launch as sl
from lib.sandbox_launch import (
    BACKENDS, DEFAULT_SANDBOX_BACKEND, DEFAULT_SANDBOX_IMAGE, DockerHandle,
    DockerLauncher, LaunchError, SandboxSpec, VALID_SANDBOX_BACKENDS,
    build_docker_run_argv, get_launcher, make_workspace_copy, repo_identity,
    remove_workspace_copy,
)

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


def docker_calls():
    """Recorded fake-docker invocations as argv lists (US-separated)."""
    if not DOCKER_LOG.exists():
        return []
    out = []
    for line in DOCKER_LOG.read_text().splitlines():
        # The stub records "$@" (no argv[0]) — restore it for readability.
        out.append(["docker"] + [a for a in line.split("\x1f") if a != ""])
    return out


def reset_log():
    DOCKER_LOG.write_text("")


class FakeClock:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t


# ================= registry + re-export compat ==========================
check("BACKENDS registry in sync with VALID_SANDBOX_BACKENDS",
      set(BACKENDS) == set(VALID_SANDBOX_BACKENDS))
check("default backend is registered",
      DEFAULT_SANDBOX_BACKEND in BACKENDS)
check("get_launcher constructs the docker backend",
      isinstance(get_launcher("docker", repo_id="r1"), DockerLauncher))
try:
    get_launcher("nope")
    check("unknown backend refused", False)
except LaunchError as exc:
    check("unknown backend refused", "nope" in str(exc))

import chatlink.spawn_seam as seam
check("spawn_seam re-exports identical seam objects",
      seam.SandboxSpec is sl.SandboxSpec
      and seam.Launcher is sl.Launcher
      and seam.LaunchError is sl.LaunchError
      and seam.NullLauncher is sl.NullLauncher
      and seam.FakeLauncher is sl.FakeLauncher)

# ================= repo_identity ========================================
rid = repo_identity(scratch)
check("repo_identity is a 12-char hex id",
      len(rid) == 12 and all(c in "0123456789abcdef" for c in rid))
check("repo_identity is resolution-stable",
      repo_identity(scratch / "x" / "..") == rid)
check("repo_identity differs per checkout",
      repo_identity(scratch / "bin") != rid)

# ================= pure argv construction ===============================
spec = SandboxSpec(
    session_id="sabc001",
    relay_dir="/tmp/relay/sabc001",
    agent_argv=("env", "X=1", "claude", "--print", "/aitask-explorechat"),
    workspace_copy_path="/tmp/ws/sabc001",
    workspace_id="W1",
    env_allowlist={"ANTHROPIC_API_KEY": "sk-test"},
    limits={"memory": "2g", "cpus": 2, "pids": 512, "wall_clock_s": 1800},
)
argv = build_docker_run_argv(spec, repo_id="rrr", image="img-x",
                             deadline_epoch=2800, uid_gid="1000:1000")
check("argv starts with docker run -d", argv[:3] == ["docker", "run", "-d"])
check("container named from session identity",
      "ait-chatlink-sabc001" in argv)
labels = [argv[i + 1] for i, a in enumerate(argv) if a == "--label"]
check("ownership labels present (session/workspace/repo/deadline)",
      labels == ["ait.chatlink.session=sabc001", "ait.chatlink.workspace=W1",
                 "ait.chatlink.repo=rrr", "ait.chatlink.deadline=2800"])
check("container runs as the gateway uid:gid (cleanup-safe ownership)",
      argv[argv.index("--user") + 1] == "1000:1000")
check("default uid_gid resolves the current process ids",
      f"{os.getuid()}:{os.getgid()}" in build_docker_run_argv(
          spec, repo_id="rrr", image="img-x", deadline_epoch=2800))
check("resource limits applied",
      argv[argv.index("--memory") + 1] == "2g"
      and argv[argv.index("--cpus") + 1] == "2"
      and argv[argv.index("--pids-limit") + 1] == "512")
mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
check("mounts: workspace at /work, relay basename keeps the session id",
      mounts == ["/tmp/ws/sabc001:/work",
                 "/tmp/relay/sabc001:/relay/sabc001"])
envs = [argv[i + 1] for i, a in enumerate(argv) if a == "-e"]
check("structural CHATLINK env exports present (session-id mount)",
      "CHATLINK_RELAY_DIR=/relay/sabc001" in envs
      and "CHATLINK_BUG_REPORT_FILE=/relay/sabc001/bug_report.md" in envs
      and "HOME=/tmp" in envs)
check("env allowlist merged on top", "ANTHROPIC_API_KEY=sk-test" in envs)
joined = "\x1f".join(argv)
check("no secret names leak into argv (bot token / git creds)",
      "DISCORD" not in joined and "BOT_TOKEN" not in joined
      and "GITHUB_TOKEN" not in joined and "GIT_" not in joined)
check("workdir + image + agent argv tail",
      argv[argv.index("--workdir") + 1] == "/work"
      and argv[argv.index("img-x"):]
      == ["img-x", "env", "X=1", "claude", "--print", "/aitask-explorechat"])

# ================= refusals =============================================
launcher = DockerLauncher(repo_id="rrr", poll_s=0.01, clock=FakeClock())
try:
    launcher.launch(SandboxSpec(session_id="s1", relay_dir="/tmp/r"))
    check("workspace_copy_path required", False)
except LaunchError as exc:
    check("workspace_copy_path required", "workspace_copy_path" in str(exc))

real_path = os.environ["PATH"]
os.environ["PATH"] = str(scratch / "nonexistent-bin")
try:
    launcher.launch(spec)
    check("docker absent → LaunchError", False)
except LaunchError as exc:
    check("docker absent → LaunchError", "docker not found" in str(exc))
finally:
    os.environ["PATH"] = real_path

# ================= launch + handle (fake docker) ========================
reset_log()
STATE_FILE.write_text("true 0")
clock = FakeClock(1000.0)
launcher = DockerLauncher(repo_id="rrr", image=DEFAULT_SANDBOX_IMAGE,
                          poll_s=0.01, clock=clock)
death_calls = []
death_seen = threading.Event()
def on_death(sid):
    death_calls.append(sid)
    death_seen.set()
live_spec = SandboxSpec(
    session_id="slive01", relay_dir="/tmp/relay/slive01",
    agent_argv=("claude", "--version"),
    workspace_copy_path="/tmp/ws/slive01", workspace_id="W1",
    limits={"wall_clock_s": 600}, on_death=on_death,
)
handle = launcher.launch(live_spec)
run_call = [c for c in docker_calls() if c[:2] == ["docker", "run"]][0]
check("launch invoked docker run with deadline label from clock",
      "ait.chatlink.deadline=1600" in run_call)
check("handle alive() probes docker inspect", handle.alive() is True)
check("wait() returns None while running at deadline",
      handle.wait(timeout=0.05) is None)

# observed death → at-most-once on_death from the watchdog thread
STATE_FILE.write_text("false 3")
check("death signal fired by watchdog", death_seen.wait(timeout=5.0))
time.sleep(0.05)  # give the watchdog a chance to double-fire (it must not)
check("on_death invoked exactly once with the session id",
      death_calls == ["slive01"])
check("wait() returns the exit code after death", handle.wait() == 3)
handle.fire_death_once()
check("fire_death_once is idempotent (guard flag)",
      death_calls == ["slive01"])
# NEGATIVE CONTROL: bypassing the guard reproduces the double-invoke —
# the flag is load-bearing, not decorative.
handle._death_fired = False
handle.fire_death_once()
check("negative control: guard bypass double-invokes",
      death_calls == ["slive01", "slive01"])

# raising callback is swallowed (reconciliation is the backstop)
boom = DockerHandle("ait-chatlink-sboom", session_id="sboom",
                    on_death=lambda sid: (_ for _ in ()).throw(RuntimeError()))
boom.fire_death_once()
check("raising on_death is swallowed", True)

# wall-clock breach → watchdog kills + signals
reset_log()
STATE_FILE.write_text("true 0")
death_calls.clear()
death_seen.clear()
clock.t = 1000.0
handle2 = launcher.launch(SandboxSpec(
    session_id="scap001", relay_dir="/tmp/relay/scap001",
    workspace_copy_path="/tmp/ws/scap001", workspace_id="W1",
    limits={"wall_clock_s": 50}, on_death=on_death,
))
clock.t = 1051.0  # past the 1050 deadline
check("deadline breach fires death signal", death_seen.wait(timeout=5.0))
rm_calls = [c for c in docker_calls() if c[:3] == ["docker", "rm", "-f"]]
check("deadline breach killed the container (docker rm -f)",
      any("ait-chatlink-scap001" in c for c in rm_calls))
check("deadline kill signalled once", death_calls == ["scap001"])
check("handle reports not-alive after the kill", handle2.alive() is False)

# ================= reap_orphans (table-driven) ==========================
reset_log()
del os.environ["FAKE_STATE_FILE"]  # rm must not flip handle state here
rows = [
    "c1\texited\ts1\t1500",        # exited → rm, not live
    "c2\trunning\ts2\t500",        # past deadline (now=1000) → rm -f
    "c3\trunning\ts3\t2000",       # within deadline → LIVE
    "c4\trunning\ts4\tnotanum",    # malformed deadline → fail-closed rm -f
    "garbage-line-without-tabs",   # ignored
]
PS_FILE.write_text("\n".join(rows) + "\n")
clock.t = 1000.0
live = launcher.reap_orphans("W1")
check("reap returns only the live in-deadline session", live == ["s3"])
calls = docker_calls()
ps_call = [c for c in calls if c[:2] == ["docker", "ps"]][0]
check("reap filters on BOTH workspace and repo labels "
      "(foreign-repo containers never enumerated)",
      "label=ait.chatlink.workspace=W1" in ps_call
      and "label=ait.chatlink.repo=rrr" in ps_call)
check("exited container removed (plain rm)",
      ["docker", "rm", "c1"] in calls)
check("past-deadline container killed (rm -f)",
      ["docker", "rm", "-f", "c2"] in calls)
check("malformed deadline reaped fail-closed (rm -f)",
      ["docker", "rm", "-f", "c4"] in calls)
check("live container untouched",
      not any(c[:2] == ["docker", "rm"] and "c3" in c for c in calls))

os.environ["FAKE_PS_RC"] = "1"
try:
    launcher.reap_orphans("W1")
    check("reap failure raises (daemon assumes none live)", False)
except LaunchError:
    check("reap failure raises (daemon assumes none live)", True)
del os.environ["FAKE_PS_RC"]

# rm failure must ALSO raise — a session must never be silently dropped
# from the live set while its container may still be running.
os.environ["FAKE_RM_RC"] = "1"
try:
    launcher.reap_orphans("W1")
    check("reap rm failure raises (session never silently dropped)", False)
except LaunchError as exc:
    check("reap rm failure raises (session never silently dropped)",
          "rm" in str(exc))
del os.environ["FAKE_RM_RC"]

# ================= workspace copy (dirty fixture repo) ==================
def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t",
                    "-c", "user.name=t", *args],
                   check=True, capture_output=True)

fixture = scratch / "fixture-repo"
fixture.mkdir()
git(fixture, "init", "-q")
(fixture / "committed.txt").write_text("committed\n")
(fixture / "sub").mkdir()
(fixture / "sub" / "nested.txt").write_text("nested\n")
git(fixture, "add", ".")
git(fixture, "commit", "-q", "-m", "base")
# dirty state, all three kinds:
(fixture / "committed.txt").write_text("UNSTAGED EDIT\n")
(fixture / "staged.txt").write_text("staged-not-committed\n")
git(fixture, "add", "staged.txt")
(fixture / "untracked.txt").write_text("untracked\n")

dest = scratch / "wscopy"
make_workspace_copy(fixture, dest)
check("committed content present in the copy",
      (dest / "committed.txt").read_text() == "committed\n"
      and (dest / "sub" / "nested.txt").exists())
check("staged + untracked files never leak",
      not (dest / "staged.txt").exists()
      and not (dest / "untracked.txt").exists())
check("unstaged edits never leak (HEAD content, not worktree)",
      "UNSTAGED" not in (dest / "committed.txt").read_text())
check("no .git in the copy", not (dest / ".git").exists())

try:
    make_workspace_copy(fixture, dest)
    check("existing dest refused (never overwrite)", False)
except LaunchError:
    check("existing dest refused (never overwrite)", True)

bad_dest = scratch / "wscopy-bad"
try:
    make_workspace_copy(scratch / "not-a-repo", bad_dest)
    check("copy failure raises LaunchError", False)
except LaunchError:
    check("copy failure raises LaunchError", True)
check("no partial dir left after a failed copy", not bad_dest.exists())

remove_workspace_copy(dest)
check("remove_workspace_copy removes the copy (idempotent)",
      not dest.exists())
remove_workspace_copy(dest)  # second call: no raise

print(f"\nAll {PASS} Python checks passed.")
PYEOF

echo
echo "PASS: test_sandbox_launch.sh"
