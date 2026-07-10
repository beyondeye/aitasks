#!/usr/bin/env bash
# test_chatlink_tui.sh — chatlink status TUI tests (t1120_6).
#
# 1. `--smoke`: construct the app + exit 0 without the event loop or I/O.
# 2. Textual run_test() Pilot: render-level assertions on the session table
#    and status line against a seeded SessionsStore + audit log.
# 3. Guard: importing chatlink.daemon must NOT load textual (the TUI is the
#    only chatlink module allowed to).
# Run: bash tests/test_chatlink_tui.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

if ! "$PYTHON" -c "import textual" 2>/dev/null; then
    echo "SKIP: textual not installed"
    exit 0
fi

# ---- 1. smoke ---------------------------------------------------------------
PYTHONPATH="$PROJECT_DIR/.aitask-scripts" \
    "$PYTHON" -m chatlink.chatlink_app --smoke
echo "ok - chatlink_app --smoke exits 0"

# ---- 2 + 3. Pilot render assertions + import guard --------------------------
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import sys
import tempfile
import time
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

# Import-order guard: the daemon first, then assert textual stayed out.
import chatlink.daemon  # noqa: F401
assert "textual" not in sys.modules, \
    "FAIL: chatlink.daemon must not load textual"
print("ok - chatlink.daemon import does not load textual")

from textual.widgets import DataTable, Log, Static  # noqa: E402

from chatlink.audit import AUDIT_FILENAME  # noqa: E402
from chatlink.chatlink_app import ChatlinkApp  # noqa: E402
from chatlink.sessions_store import SessionRecord, SessionsStore  # noqa: E402

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="chatlink-tui-test-"))
    now = time.time()
    store = SessionsStore(tmp / "sessions", clock=lambda: now)
    r1 = store.new_record("solder01", "U1VERYLONGID")
    r1.state = "done"
    r1.created_at = now - 7200
    store.save(r1)
    r2 = store.new_record("snewer01", "U2")
    r2.state = "asking"
    r2.created_at = now - 90
    store.save(r2)
    (tmp / "sessions" / AUDIT_FILENAME).write_text(
        "2026-01-01 INFO intake accepted session=snewer01 user=U2\n")

    app = ChatlinkApp(sessions_dir=tmp / "sessions", clock=lambda: now)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#sessions_table", DataTable)
        check("two session rows rendered", table.row_count == 2)
        newest = table.get_row_at(0)
        check("rows sorted newest-first", newest[0] == "snewer01")
        check("state column rendered", newest[1] == "asking")
        check("initiator tag truncated",
              table.get_row_at(1)[2] == "U1VERYLO…")
        check("age column rendered", newest[3] == "1m")
        status = app.query_one("#status_line", Static)
        check("status line reports gateway activity",
              "gateway" in str(status.render()))
        log = app.query_one("#audit_log", Log)
        check("audit tail rendered",
              "intake accepted" in "\n".join(log.lines))
        await app.action_quit()

    print(f"\nPASS: {PASS}, FAIL: 0")


asyncio.run(main())
PYEOF

echo
echo "PASS: test_chatlink_tui.sh"
