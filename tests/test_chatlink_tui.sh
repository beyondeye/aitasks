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
from chatlink.preflight import CheapChecks, CheckResult  # noqa: E402
from chatlink.sessions_store import SessionRecord, SessionsStore  # noqa: E402

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


# --- preflight seams (t1149_2): deterministic fakes, no subprocess -----------

def fake_cheap():
    return CheapChecks(results=[
        CheckResult(id="config_file", category="transport", severity="pass",
                    message="config file: /tmp/chatlink_config.yaml"),
        CheckResult(id="allowlist", category="transport", severity="warn",
                    message="both allowlists empty",
                    fix_hint="add reporter ids"),
        CheckResult(id="token", category="transport", severity="fail",
                    message="bot token missing",
                    fix_hint="write the bot token"),
    ])


expensive_calls = {"n": 0, "raise": False}


def spy_expensive():
    expensive_calls["n"] += 1
    if expensive_calls["raise"]:
        raise RuntimeError("probe blew up")
    return [
        CheckResult(id="docker_binary", category="runtime", severity="pass",
                    message="docker binary present"),
        CheckResult(id="docker_image", category="runtime", severity="warn",
                    message="sandbox image ait-chatlink-agent not built",
                    fix_hint="docker build -t ait-chatlink-agent …"),
        CheckResult(id="explore_relay_agent_command", category="operation",
                    severity="pass",
                    message="agent command: fake-agent … (5 words)"),
    ]


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

    # Fixed expensive rows via the pure render helper (unmounted app —
    # deterministic uncached states, no worker race).
    bare = ChatlinkApp(sessions_dir=tmp / "sessions", clock=lambda: now,
                       cheap_runner=fake_cheap,
                       expensive_runner=spy_expensive)
    idle = bare._render_preflight(fake_cheap().results, now)
    for label in ("docker binary", "sandbox image",
                  "explore-relay agent command"):
        check(f"uncached idle row present: {label}",
              f"{label}" in idle and "not checked yet" in idle)
    bare._expensive_running = True
    checking = bare._render_preflight(fake_cheap().results, now)
    check("uncached running rows show checking",
          checking.count("checking") >= 3 and "not checked yet"
          not in checking)
    check("cheap pass row glyph", "✓ config file:" in idle)
    check("cheap warn row keeps fix hint",
          "! both allowlists empty — add reporter ids" in idle)
    check("cheap fail row keeps fix hint",
          "✗ bot token missing — write the bot token" in idle)
    check("bucket labels rendered",
          "[transport]" in idle and "[runtime]" in idle
          and "[operation]" in idle)

    app = ChatlinkApp(sessions_dir=tmp / "sessions", clock=lambda: now,
                      cheap_runner=fake_cheap,
                      expensive_runner=spy_expensive)
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

        # ---- preflight panel (t1149_2) -----------------------------------
        panel = app.query_one("#preflight_panel", Static)

        # Live worker path: on_mount kicked the real thread worker; wait for
        # run_worker -> call_from_thread delivery to land in the widget.
        await app.workers.wait_for_complete()
        await pilot.pause()
        text = str(panel.render())
        check("on_mount worker ran once", expensive_calls["n"] == 1)
        check("cheap rows rendered in live panel",
              "✗ bot token missing" in text)
        check("expensive results delivered to widget",
              "✓ docker binary present" in text
              and "! sandbox image ait-chatlink-agent not built" in text
              and "agent command: fake-agent" in text)
        check("cached expensive rows carry age", "ago)" in text)

        # NEGATIVE CONTROL: poll ticks never invoke the expensive seam.
        for _ in range(4):
            app._refresh_view()
        await pilot.pause()
        check("poll ticks never run expensive checks",
              expensive_calls["n"] == 1)

        # On-demand refresh DOES re-kick the worker (end-to-end via `r`).
        await pilot.press("r")
        await app.workers.wait_for_complete()
        await pilot.pause()
        check("manual refresh re-runs expensive checks",
              expensive_calls["n"] == 2)

        # Debounce: no second worker while one is (flagged) in flight.
        app._expensive_running = True
        app._kick_expensive()
        check("kick is debounced while running",
              expensive_calls["n"] == 2)
        app._expensive_running = False

        # Worker failure keeps the previous cache and surfaces an error.
        expensive_calls["raise"] = True
        app.action_refresh()
        await app.workers.wait_for_complete()
        await pilot.pause()
        text = str(panel.render())
        check("failed probe attempted", expensive_calls["n"] == 3)
        check("failure keeps cached expensive rows",
              "✓ docker binary present" in text)
        check("failure surfaces error line",
              "expensive checks failed — press r to retry" in text)
        await app.action_quit()

    print(f"\nPASS: {PASS}, FAIL: 0")


asyncio.run(main())
PYEOF

echo
echo "PASS: test_chatlink_tui.sh"
