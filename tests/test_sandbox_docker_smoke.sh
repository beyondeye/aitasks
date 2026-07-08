#!/usr/bin/env bash
# test_sandbox_docker_smoke.sh — in-container relay smoke test (t1120_5).
#
# Spawns a REAL container through the seam (lib/sandbox_launch.py
# DockerLauncher) with a mounted relay dir and a workspace copy of this
# repo's committed HEAD; a stub bash agent inside asks one question via
# aitask_relay_ask.sh, the host writes the answer, and the payload lands
# via aitask_relay_payload.sh — proving bind mounts, workdir layout, env
# exports, and in-image tooling together. Production-path assertions cover
# the real agent CLI (claude present in-image) and the explore-relay
# dry-run argv resolving in-container — no billed agent run. Negative
# control: a second container is killed mid-question and the death signal
# + not-alive handle are asserted (the daemon-side cancellation path is
# covered by tests/test_chatlink_daemon.sh).
#
# Skip-capable: SKIPs when docker (or the ait-chatlink-agent image) is
# absent. Build the image with:
#   docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/
# Run: bash tests/test_sandbox_docker_smoke.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
    echo "skip - docker not found (install Docker to run the sandbox smoke)"
    echo "PASS: test_sandbox_docker_smoke.sh (skipped)"
    exit 0
fi
if ! docker image inspect ait-chatlink-agent >/dev/null 2>&1; then
    echo "skip - ait-chatlink-agent image not built (docker build -t" \
         "ait-chatlink-agent .aitask-scripts/chatlink/docker/)"
    echo "PASS: test_sandbox_docker_smoke.sh (skipped)"
    exit 0
fi

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/sandbox-smoke-XXXXXX")"
cleanup() {
    # Belt-and-braces: remove any container this test may have leaked.
    docker ps -aq --filter "label=ait.chatlink.workspace=SMOKE-W1" \
        | xargs -r docker rm -f >/dev/null 2>&1 || true
    rm -rf "$SCRATCH"
}
trap cleanup EXIT

# -- production-path assertion 1: agent CLI available in the image ----------
docker run --rm ait-chatlink-agent sh -c \
    'command -v claude >/dev/null && claude --version >/dev/null'
echo "ok - image carries a runnable claude CLI"

# -- production-path assertion 2: explore-relay dry-run argv resolves -------
mkdir -p "$SCRATCH/relay-env"
echo "stub report" > "$SCRATCH/relay-env/bug_report.md"
dry_out="$(cd "$PROJECT_DIR" && \
    CHATLINK_RELAY_DIR="$SCRATCH/relay-env" \
    CHATLINK_BUG_REPORT_FILE="$SCRATCH/relay-env/bug_report.md" \
    ./ait codeagent invoke explore-relay --headless --dry-run 2>&1 | \
    grep '^DRY_RUN:' || true)"
if [[ -z "$dry_out" ]]; then
    echo "FAIL: explore-relay --dry-run produced no DRY_RUN line" >&2
    exit 1
fi
# Leading executables of the production argv must resolve in-image.
read -r first second _ <<< "${dry_out#DRY_RUN: }"
for exe in "$first" "$second"; do
    case "$exe" in
        *=*) continue ;;  # env assignment, not an executable
    esac
    docker run --rm ait-chatlink-agent sh -c "command -v '$exe' >/dev/null"
done
echo "ok - production explore-relay argv executables resolve in-image"
echo "     ($dry_out)"

# -- in-container relay round trip + kill negative control ------------------
"$PYTHON" - "$PROJECT_DIR" "$SCRATCH" <<'PYEOF'
import json
import os
import sys
import threading
import time
from pathlib import Path

root = Path(sys.argv[1])
scratch = Path(sys.argv[2])
sys.path.insert(0, str(root / ".aitask-scripts"))

from lib.sandbox_launch import (
    DockerLauncher, SandboxSpec, make_workspace_copy, repo_identity,
)
from chatlink.relay import Answer, SessionDir, create_session_dir

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")

STUB_AGENT = """#!/bin/bash
# Stub agent: one relay question, then the payload — no LLM, no billing.
set -e
cd /work
out="$(./.aitask-scripts/aitask_relay_ask.sh \
    --relay-dir "$CHATLINK_RELAY_DIR" \
    --text "Which module is affected?" --header "Module" \
    --option "auth::the auth module" --option "ui::the ui layer" \
    --timeout 120)"
echo "$out" | grep -q "STATUS:answered" || exit 3
grep -q "stub bug report" "$CHATLINK_BUG_REPORT_FILE" || exit 4
printf 'The %s module crashes on save.\\n' \
    "$(echo "$out" | sed -n 's/^VALUE://p' | head -1)" | \
    ./.aitask-scripts/aitask_relay_payload.sh \
        --relay-dir "$CHATLINK_RELAY_DIR" \
        --name stub_bug --title "Stub bug" --priority medium \
        --effort low --issue-type bug --description-file -
"""

BLOCKING_AGENT = """#!/bin/bash
# Blocks on a relay question until killed (negative-control container).
cd /work
./.aitask-scripts/aitask_relay_ask.sh --relay-dir "$CHATLINK_RELAY_DIR" \
    --text "Never answered?" --option "x::x" --timeout 300
"""

def wait_for(pred, timeout=60.0, step=0.25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(step)
    return False

# Workspace copy of THIS repo's committed HEAD (the production shape) —
# shared read-mostly by both containers via separate copies.
ws1 = make_workspace_copy(root, scratch / "ws1")
check("workspace copy carries the relay helpers + no .git",
      (ws1 / ".aitask-scripts" / "aitask_relay_ask.sh").exists()
      and not (ws1 / ".git").exists())
stub = ws1 / "stub_agent.sh"
stub.write_text(STUB_AGENT)
stub.chmod(0o755)

relay_root = scratch / "relay"
relay_root.mkdir()
session = create_session_dir(relay_root)
sid = session.session_id
(session.path / "bug_report.md").write_text("stub bug report\n")

deaths = []
death_seen = threading.Event()
def on_death(s):
    deaths.append(s)
    death_seen.set()

launcher = DockerLauncher(repo_id=repo_identity(root), poll_s=1.0)
handle = launcher.launch(SandboxSpec(
    session_id=sid,
    relay_dir=str(session.path),
    agent_argv=("bash", "/work/stub_agent.sh"),
    workspace_copy_path=str(ws1),
    workspace_id="SMOKE-W1",
    limits={"memory": "512m", "cpus": 1, "pids": 256, "wall_clock_s": 300},
    on_death=on_death,
))
check("container launched and alive", handle.alive())

# Agent asks → host answers (the gateway's role) → agent continues.
check("question emitted from inside the container",
      wait_for(lambda: session.read_question(1) is not None, timeout=90))
q = session.read_question(1)
check("question round-tripped through the bind mount",
      q.session_id == sid and q.options[0].value == "o0")
check("host answer accepted",
      session.write_answer(Answer(id=q.id, seq=1, status="answered",
                                  values=["o0"], answered_by="U1")))
exit_code = handle.wait(timeout=90)
check("agent continued after the answer and exited cleanly", exit_code == 0)
payload = session.read_payload()
check("payload.json landed with the stub content",
      payload is not None and payload["name"] == "stub_bug"
      and "auth" in payload["description"])
check("stub agent death signalled after clean exit",
      death_seen.wait(timeout=15) and deaths == [sid])

# -- negative control: kill mid-question ⇒ death signal + not-alive --------
ws2 = make_workspace_copy(root, scratch / "ws2")
blocker = ws2 / "stub_agent.sh"
blocker.write_text(BLOCKING_AGENT)
blocker.chmod(0o755)
session2 = create_session_dir(relay_root)
sid2 = session2.session_id
(session2.path / "bug_report.md").write_text("stub bug report\n")

deaths2 = []
death_seen2 = threading.Event()
handle2 = launcher.launch(SandboxSpec(
    session_id=sid2,
    relay_dir=str(session2.path),
    agent_argv=("bash", "/work/stub_agent.sh"),
    workspace_copy_path=str(ws2),
    workspace_id="SMOKE-W1",
    limits={"memory": "512m", "cpus": 1, "pids": 256, "wall_clock_s": 300},
    on_death=lambda s: (deaths2.append(s), death_seen2.set()),
))
check("negative control: container blocked on its question",
      wait_for(lambda: session2.read_question(1) is not None, timeout=90))
handle2.kill()
check("negative control: death signal fired after mid-question kill",
      death_seen2.wait(timeout=15) and deaths2 == [sid2])
check("negative control: handle reports not-alive", handle2.alive() is False)
# The daemon-side stand-in writes the cancelled answer (the real daemon
# path is covered by test_chatlink_daemon.sh) — never-clobber holds.
check("cancelled answer written for the pending question",
      session2.write_answer(Answer(id=session2.read_question(1).id, seq=1,
                                   status="cancelled")))

# reap: everything from this smoke workspace is gone afterwards
live = launcher.reap_orphans("SMOKE-W1")
check("reap after the smoke reports no live sessions", live == [])

print(f"\nAll {PASS} Python checks passed.")
PYEOF

echo
echo "PASS: test_sandbox_docker_smoke.sh"
