#!/usr/bin/env bash
# test_monitor_tmux_injection.sh — tmux command-construction hardening (t985).
#
# monitor_core.send_keys / send_enter / spawn_tui build tmux argv that reaches a
# pane/window named by an applink client. These tests assert the injection
# guards: a `--` end-of-options separator on send-keys, and a TUI_NAMES allowlist
# on spawn_tui (whose last arg is a shell command). Run:
#   bash tests/test_monitor_tmux_injection.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

from monitor.monitor_core import TmuxMonitor, TUI_NAMES

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")

# Build a monitor without the heavy constructor; intercept tmux_run to capture
# the argv (and run NOTHING).
m = TmuxMonitor.__new__(TmuxMonitor)
m.session = "aitasks"
captured = []
def fake_tmux_run(cmd, **kw):
    captured.append(list(cmd))
    return (0, "")
m.tmux_run = fake_tmux_run

# --- send_keys: `--` ends option parsing ----------------------------------
captured.clear()
m.send_keys("%1", "hello")
cmd = captured[-1]
check("send_keys inserts -- before keys", "--" in cmd and cmd.index("--") == cmd.index("hello") - 1)
check("send_keys non-literal omits -l", "-l" not in cmd)

captured.clear()
m.send_keys("%1", "-R", literal=False)
cmd = captured[-1]
# The dangerous case: a leading-dash key must be positional (after --), not a flag.
check("send_keys leading-dash key sits after --", cmd[-1] == "-R" and cmd[-2] == "--")
check("send_keys -R is not parsed as a tmux flag", cmd.index("-R") > cmd.index("--"))

captured.clear()
m.send_keys("%1", "text", literal=True)
cmd = captured[-1]
check("send_keys literal keeps -l before --", cmd == ["send-keys", "-t", "%1", "-l", "--", "text"])

captured.clear()
m.send_enter("%2")
cmd = captured[-1]
check("send_enter inserts -- before Enter", cmd == ["send-keys", "-t", "%2", "--", "Enter"])

# --- spawn_tui: allowlist closes the shell-command sink -------------------
# A valid registry name builds the new-window argv and runs.
valid = sorted(TUI_NAMES)[0]
captured.clear()
ok = m.spawn_tui(valid)
check("spawn_tui valid name returns True", ok is True)
check("spawn_tui valid name issued new-window", captured and captured[-1][0] == "new-window")

# Hostile names (shell metacharacters) are refused BEFORE any tmux runs.
for evil in ("board; rm -rf ~", "$(touch /tmp/pwned)", "x`id`", "a|b", "not-a-tui"):
    captured.clear()
    ok = m.spawn_tui(evil)
    check(f"spawn_tui refuses {evil!r}", ok is False)
    check(f"spawn_tui runs NO tmux command for {evil!r}", captured == [])

print(f"\nALL PASSED ({PASS} checks)")
PYEOF
