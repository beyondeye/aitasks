#!/usr/bin/env bash
# test_applink_devices.sh — UI test for the applink Devices screen (t822_7).
#
# Drives DevicesScreen through Textual's run_test harness against a fake server:
# the device table renders one row per session (with name/platform/state/paired/
# last-seen/location), sorts by pairing time, and the 'x' revoke action removes
# the highlighted device. No sockets/tmux — a stub server stands in.
# Run: bash tests/test_applink_devices.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

if ! "$PYTHON" -c "import textual" 2>/dev/null; then
    echo "SKIP: textual not installed (run 'ait setup' first)"
    exit 0
fi

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "applink"))

import applink_app as A
from sessions import Session
from textual.app import App
from textual.widgets import DataTable


class FakeServer:
    def __init__(self):
        now = time.time()
        self.error = None
        self._sessions = [
            Session(bearer="b2", profile="read_only", device_name="iPad", platform="ios",
                    created_at=now - 3600, last_seen=now - 1800, state="Suspended"),
            Session(bearer="b1", profile="full", device_name="Pixel 8 Pro", platform="android",
                    location="Berlin, DE", created_at=now - 120, last_seen=now - 5, state="Connected"),
        ]
        self.revoked = []

    def connection_state(self):
        return "Connected"

    def active_sessions(self):
        return list(self._sessions)

    async def revoke_session(self, bearer):
        self.revoked.append(bearer)
        self._sessions = [s for s in self._sessions if s.bearer != bearer]
        return True


class FakeRuntime:
    port = 8765

    def __init__(self):
        self.server = FakeServer()


class HostApp(App):
    def __init__(self):
        super().__init__()
        self.runtime = FakeRuntime()

    def on_mount(self):
        self.push_screen(A.DevicesScreen())


def check(label, cond):
    assert cond, f"FAIL: {label}"
    print(f"ok - {label}")


async def main():
    app = HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        check("DevicesScreen is active", isinstance(screen, A.DevicesScreen))
        table = screen.query_one("#devices_table", DataTable)
        check("two device rows rendered", table.row_count == 2)
        # rows sorted by created_at: iPad (older) first, Pixel second
        check("rows sorted by pairing time", screen._bearers_by_row == ["b2", "b1"])
        pixel = table.get_row_at(1)
        check("device name/model shown", pixel[0] == "Pixel 8 Pro")
        check("platform shown", pixel[1] == "android")
        check("connection state shown", pixel[2] == "Connected")
        check("location shown when provided", pixel[5] == "Berlin, DE")
        ipad = table.get_row_at(0)
        check("missing location renders as dash", ipad[5] == "—")

        # revoke the highlighted (Pixel) device
        table.move_cursor(row=1)
        await pilot.pause()
        await screen.action_revoke_selected()
        await pilot.pause()
        check("revoke targeted the highlighted device", app.runtime.server.revoked == ["b1"])
        check("revoked row removed from table", table.row_count == 1)
        await app.action_quit()

    print("\nALL PASSED")


asyncio.run(main())
PYEOF