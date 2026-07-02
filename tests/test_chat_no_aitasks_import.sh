#!/usr/bin/env bash
# test_chat_no_aitasks_import.sh — decoupling guard for the chat package (t1074_1).
#
# The chat layer is deliberately NOT aitasks-specific: importing it must pull
# in no framework module (monitor/, applink/, board/, lib/, aitask_*) and no
# third-party dependency. This guard keeps accidental coupling out — see
# CLAUDE.md "chat package" and aiplans/p1074_chat_adapter_abstraction_layer.md.
# Run: bash tests/test_chat_no_aitasks_import.sh

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
scripts_dir = root / ".aitask-scripts"
# Insert BOTH the package root and the framework dirs a coupled import would
# resolve through — the guard must fail because chat doesn't import them,
# not because they were unresolvable.
for extra in (scripts_dir, scripts_dir / "lib", scripts_dir / "board"):
    sys.path.insert(0, str(extra))

before = set(sys.modules)

import chat  # noqa: F401

new_modules = set(sys.modules) - before

PASS = 0
def check(label, cond, detail=""):
    global PASS
    assert cond, f"FAIL: {label}{': ' + detail if detail else ''}"
    PASS += 1
    print(f"ok - {label}")

# 1. No framework package/module got imported.
FRAMEWORK_PREFIXES = ("monitor", "applink", "aitask", "board", "tui_", "tmux_",
                      "task_yaml", "gate_ledger", "agent_launch_utils")
offenders = sorted(m for m in new_modules
                   if m.split(".")[0].startswith(FRAMEWORK_PREFIXES))
check("no framework module imported", not offenders, f"offenders={offenders}")

# 2. Nothing new was loaded from .aitask-scripts outside the chat package
#    (catches framework files imported under an unanticipated name), and
# 3. nothing new came from outside the stdlib + chat (no third-party deps).
stdlib_names = getattr(sys, "stdlib_module_names", frozenset())
outside_chat, nonstd = [], []
for name in sorted(new_modules):
    mod = sys.modules.get(name)
    f = getattr(mod, "__file__", None)
    top = name.split(".")[0]
    if f and str(scripts_dir) in f and top != "chat":
        outside_chat.append(name)
    if top != "chat" and top not in stdlib_names:
        nonstd.append(name)
check("nothing loaded from .aitask-scripts outside chat/", not outside_chat,
      f"modules={outside_chat}")
check("no third-party module imported", not nonstd, f"modules={nonstd}")

# 4. The full public surface resolves without any of the above.
check("public API fully importable", len(chat.__all__) == 41
      and all(hasattr(chat, n) for n in chat.__all__))

print(f"\nPASS: {PASS} checks")
PYEOF
