#!/usr/bin/env bash
# test_crew_git_noninteractive.sh - crew fetch/push can never prompt (t2024).
#
# Every bounded crew network operation runs through lib/bounded_run.py: a new
# session (no controlling terminal) with noninteractive_env() (GIT_ASKPASS set
# but empty, GIT_TERMINAL_PROMPT=0, SSH_ASKPASS_REQUIRE=never, SSH_ASKPASS /
# DISPLAY / WAYLAND_DISPLAY removed). GIT_TERMINAL_PROMPT=0 alone is NOT enough:
# git's prompt code still runs GIT_ASKPASS / core.askPass / SSH_ASKPASS, and a
# job with a controlling terminal can still read it.
#
# Both crew entry points are checked: the shell `crew_push` (the
# _crew_git_bounded CLI path) and the Python `git_cmd(timeout=)` (the runner /
# `ait crew status` path). Each check has a CONTROL that runs plain git under
# the same hostile environment and shows the prompt channel is really reachable,
# so a passing cell cannot be vacuous:
#   (a) git's own credential prompt — an HTTP origin answering 401;
#   (b) OpenSSH's own read_passphrase — a configured SSH command that loads a
#       passphrase-protected key with ssh-keygen (skipped when it is absent);
#   (c) a controlling terminal — under a pty, a configured SSH command records
#       whether /dev/tty opens.
#
# Run: bash tests/test_crew_git_noninteractive.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/venv_python.sh
. "$PROJECT_DIR/tests/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

# Developer git config never reaches this file (a global credential helper or
# askpass would change what the controls see). Sourced after the counters,
# because the probe asserts.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_crew_noninteractive_XXXXXX")"
SERVER_PID=""
cleanup() {
    [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null
    rm -rf "$ROOT" 2>/dev/null
}
trap cleanup EXIT

# Generous: every crew path below must fail fast, long before this bound.
export AIT_CREW_GIT_TIMEOUT=20

SENTINEL="$ROOT/askpass-sentinel"
SENTINEL_LOG="$ROOT/askpass.log"
cat > "$SENTINEL" <<EOF
#!/bin/sh
echo "asked: \$*" >> "$SENTINEL_LOG"
echo not-a-secret
EOF
chmod +x "$SENTINEL"

WT="$ROOT/wt"
git init -q "$WT"
git -C "$WT" config user.email t@t
git -C "$WT" config user.name t
git -C "$WT" commit -q --allow-empty -m one
git -C "$WT" config core.askPass "$SENTINEL"
git -C "$WT" remote add origin "http://127.0.0.1:1/unused.git"

# The hostile desktop: every askpass channel points at the sentinel, and
# OpenSSH is told to prefer askpass even when a terminal exists.
hostile() {
    GIT_ASKPASS="$SENTINEL" SSH_ASKPASS="$SENTINEL" SSH_ASKPASS_REQUIRE=force \
        DISPLAY=:0 "$@"
}

sentinel_calls() { [[ -f "$SENTINEL_LOG" ]] && wc -l < "$SENTINEL_LOG" | tr -d ' ' || echo 0; }

# run_shell_push — the shell crew path; sets RC, ERR, ELAPSED.
run_shell_push() {
    local start=$SECONDS
    hostile bash -c '. "$1/.aitask-scripts/lib/agentcrew_utils.sh" && crew_push "$2"' \
        _ "$PROJECT_DIR" "$WT" >/dev/null 2>"$ROOT/err"
    RC=$?
    ERR="$(cat "$ROOT/err")"
    ELAPSED=$(( SECONDS - start ))
}

# run_python_push — the Python crew path (git_cmd with a timeout); sets RC, ERR, ELAPSED.
run_python_push() {
    local start=$SECONDS out
    out="$(hostile "$AITASK_PYTHON" -c '
import sys
sys.path.insert(0, sys.argv[1])
from agentcrew_utils import git_cmd
r = git_cmd(sys.argv[2], "push", "--quiet", "-u", "origin", "HEAD", check=False, timeout=20)
print(r.returncode)
sys.stderr.write(r.stderr)
' "$PROJECT_DIR/.aitask-scripts/agentcrew" "$WT" 2>"$ROOT/err")"
    RC="$out"
    ERR="$(cat "$ROOT/err")"
    ELAPSED=$(( SECONDS - start ))
}

fast() {
    assert_eq "$1: fails fast instead of waiting on a prompt" "yes" \
        "$( (( ELAPSED <= 10 )) && echo yes || echo "no: ${ELAPSED}s")"
}

echo "=== crew fetch/push never prompt (t2024) ==="

# --- (a) git's own credential prompt ---
echo "--- Test 1: an HTTP origin asking for credentials ---"
cat > "$ROOT/srv401.py" <<'EOF'
import http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def _deny(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="crew"')
        self.send_header("Content-Length", "0")
        self.end_headers()
    do_GET = do_POST = _deny
    def log_message(self, *a):
        pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H)
with open(sys.argv[1], "w") as fh:
    fh.write(str(srv.server_address[1]))
srv.serve_forever()
EOF
"$AITASK_PYTHON" "$ROOT/srv401.py" "$ROOT/port" &
SERVER_PID=$!
for _ in $(seq 50); do [[ -s "$ROOT/port" ]] && break; sleep 0.1; done
git -C "$WT" remote set-url origin "http://127.0.0.1:$(cat "$ROOT/port")/repo.git"

: > "$SENTINEL_LOG"
hostile git -C "$WT" ls-remote origin >/dev/null 2>&1
assert_eq "1: control: plain git asks the askpass sentinel" "yes" \
    "$( (( $(sentinel_calls) > 0 )) && echo yes || echo no)"

: > "$SENTINEL_LOG"
run_shell_push
assert_eq "1: crew_push fails" "1" "$RC"
assert_eq "1: crew_push never runs an askpass program" "0" "$(sentinel_calls)"
assert_contains "1: crew_push reports git's no-prompt failure" "terminal prompts disabled" "$ERR"
fast "1 (shell)"

: > "$SENTINEL_LOG"
run_python_push
assert_eq "1: git_cmd(timeout=) fails" "yes" "$([[ "$RC" != 0 ]] && echo yes || echo no)"
assert_eq "1: git_cmd(timeout=) never runs an askpass program" "0" "$(sentinel_calls)"
assert_contains "1: git_cmd reports git's no-prompt failure" "terminal prompts disabled" "$ERR"
fast "1 (python)"

kill "$SERVER_PID" 2>/dev/null
SERVER_PID=""

# --- (b) OpenSSH's own read_passphrase ---
echo "--- Test 2: a configured SSH command that needs a key passphrase ---"
if ! command -v ssh-keygen >/dev/null 2>&1; then
    echo "SKIP: 2: ssh-keygen is not installed"
else
    ssh-keygen -q -t ed25519 -N 'crew-passphrase' -C crew -f "$ROOT/locked_key" </dev/null >/dev/null
    cat > "$ROOT/passphrase-ssh" <<EOF
#!/bin/sh
# Load a passphrase-protected key through OpenSSH's read_passphrase — the code
# ssh itself prompts with — then fail like an unreachable host.
ssh-keygen -y -f "$ROOT/locked_key" </dev/null >/dev/null 2>&1
exit 255
EOF
    chmod +x "$ROOT/passphrase-ssh"
    git -C "$WT" config core.sshCommand "$ROOT/passphrase-ssh"
    git -C "$WT" config ssh.variant ssh
    git -C "$WT" remote set-url origin "ssh://crew-locked.invalid/repo.git"

    : > "$SENTINEL_LOG"
    hostile git -C "$WT" ls-remote origin >/dev/null 2>&1
    assert_eq "2: control: plain git lets OpenSSH ask the sentinel" "yes" \
        "$( (( $(sentinel_calls) > 0 )) && echo yes || echo no)"

    : > "$SENTINEL_LOG"
    run_shell_push
    assert_eq "2: crew_push fails" "1" "$RC"
    assert_eq "2: crew_push leaves OpenSSH no askpass to run" "0" "$(sentinel_calls)"
    fast "2 (shell)"

    : > "$SENTINEL_LOG"
    run_python_push
    assert_eq "2: git_cmd(timeout=) leaves OpenSSH no askpass to run" "0" "$(sentinel_calls)"
    fast "2 (python)"
    git -C "$WT" config --unset core.sshCommand
fi

# --- (c) a controlling terminal ---
echo "--- Test 3: under a terminal, the transport cannot reach it ---"
TTY_LOG="$ROOT/tty.log"
cat > "$ROOT/tty-ssh" <<EOF
#!/bin/sh
if ( : < /dev/tty ) 2>/dev/null; then echo tty >> "$TTY_LOG"; else echo no-tty >> "$TTY_LOG"; fi
exit 255
EOF
chmod +x "$ROOT/tty-ssh"
git -C "$WT" config core.sshCommand "$ROOT/tty-ssh"
git -C "$WT" config ssh.variant ssh
git -C "$WT" remote set-url origin "ssh://crew-tty.invalid/repo.git"

# in_pty <cmd...> — run <cmd> as the session leader of a fresh pty, which is
# then its controlling terminal (pty.fork = setsid + TIOCSCTTY).
cat > "$ROOT/in_pty.py" <<'EOF'
import os, pty, sys
pid, fd = pty.fork()
if pid == 0:
    os.execvp(sys.argv[1], sys.argv[1:])
while True:
    try:
        if not os.read(fd, 4096):
            break
    except OSError:
        break
_, status = os.waitpid(pid, 0)
sys.exit(os.waitstatus_to_exitcode(status))
EOF
in_pty() { "$AITASK_PYTHON" "$ROOT/in_pty.py" "$@" >/dev/null 2>&1; }
last_tty() { tail -1 "$TTY_LOG" 2>/dev/null; }

: > "$TTY_LOG"
in_pty git -C "$WT" ls-remote origin
assert_eq "3: control: plain git's transport can open the terminal" "tty" "$(last_tty)"

: > "$TTY_LOG"
in_pty bash -c '. "$1/.aitask-scripts/lib/agentcrew_utils.sh" && crew_push "$2"' \
    _ "$PROJECT_DIR" "$WT"
assert_eq "3: crew_push's transport has no terminal" "no-tty" "$(last_tty)"

: > "$TTY_LOG"
in_pty "$AITASK_PYTHON" -c '
import sys
sys.path.insert(0, sys.argv[1])
from agentcrew_utils import git_cmd
git_cmd(sys.argv[2], "push", "--quiet", "-u", "origin", "HEAD", check=False, timeout=20)
' "$PROJECT_DIR/.aitask-scripts/agentcrew" "$WT"
assert_eq "3: git_cmd(timeout=)'s transport has no terminal" "no-tty" "$(last_tty)"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

[[ "$FAIL" -eq 0 ]] || { echo "SOME TESTS FAILED"; exit 1; }
echo "ALL TESTS PASSED"
