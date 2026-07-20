#!/usr/bin/env bash
# test_chatlink_tui.sh — chatlink status TUI tests (t1120_6).
#
# 1. `--smoke`: construct the app + exit 0 without the event loop or I/O.
# 2. Textual run_test() Pilot: render-level assertions on the session table
#    and status line against a seeded SessionsStore + audit log.
# 3. Guard: importing chatlink.daemon must NOT load textual (the TUI is the
#    only chatlink module allowed to).
# 4. Config wizard walk (t1149_3): `w` opens the step chain; per-step inline
#    validation keeps the modal open; Back retains state; abort mid-wizard
#    leaves config + token untouched; Save writes the merged YAML + 0600
#    token (failure-aware: a raising token writer keeps the config write,
#    renders the per-item FAILED state, and a later Save retries); the
#    summary renders injected preflight results + the ./ait git commit hint.
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

from chatlink import paths  # noqa: E402
from chatlink import wizard as wiz  # noqa: E402
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

    # ---- config wizard walk (t1149_3) ------------------------------------
    import stat
    import yaml
    from textual.widgets import Button, Input

    wtmp = Path(tempfile.mkdtemp(prefix="chatlink-wizard-tui-test-"))
    (wtmp / "sessions").mkdir()
    config_path = wtmp / "chatlink_config.yaml"
    # Redirect the default token writer/reader to the tmp root so the REAL
    # paths.write_token (0700 dir / 0600 file) is exercised without ever
    # touching the repo's metadata dir.
    paths.project_root = lambda: wtmp
    token_calls = {"fail": False}

    def token_writer(tok):
        if token_calls["fail"]:
            raise RuntimeError("disk full")
        return paths.write_token(tok)

    wiz_expensive = {"n": 0}

    def wiz_spy_expensive():
        wiz_expensive["n"] += 1
        return [
            CheckResult(id="explore_relay_agent_command",
                        category="operation", severity="pass",
                        message="agent command: fake-agent … (5 words)"),
            CheckResult(id="docker_binary", category="runtime",
                        severity="pass", message="docker binary present"),
        ]

    # Live-validation seam spy (t1149_5): returns a deliberately FAILING
    # row so the walk proves the step is advisory-only (save unaffected).
    import threading
    wiz_live = {"n": 0, "args": None}
    live_block = threading.Event()
    live_mode = {"block": False}

    def wiz_spy_live(token, workspace_id, conversation_id,
                     thread_id=None, **_kw):
        wiz_live["n"] += 1
        wiz_live["args"] = (token, workspace_id, conversation_id,
                            thread_id)
        if live_mode["block"]:
            live_block.wait(timeout=10)
        return [
            CheckResult(id="live_login", category="transport",
                        severity="pass", message="token accepted"),
            CheckResult(id="live_permissions", category="transport",
                        severity="fail",
                        message="missing required channel permission(s): "
                                "manage_threads",
                        fix_hint="re-invite the bot"),
        ]

    def make_wizard_app():
        return ChatlinkApp(
            sessions_dir=wtmp / "sessions", clock=lambda: now,
            cheap_runner=fake_cheap, expensive_runner=wiz_spy_expensive,
            wizard_config_path=config_path, token_writer=token_writer,
            live_runner=wiz_spy_live)

    # --- abort mid-wizard: zero writes ---
    app2 = make_wizard_app()
    async with app2.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        check("w opens the intake step",
              isinstance(app2.screen, wiz.IntakeChannelScreen))
        app2.screen.query_one("#wiz_workspace", Input).value = "111"
        app2.screen.query_one("#wiz_conversation", Input).value = "222"
        app2.screen.query_one("#wiz_conversation", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("intake advances to allowlist",
              isinstance(app2.screen, wiz.AllowlistScreen))
        await pilot.press("escape")
        await pilot.pause()
        check("escape aborts the wizard",
              not isinstance(app2.screen, wiz._WizardStep))
        check("abort leaves config file untouched", not config_path.exists())
        check("abort leaves token file untouched",
              not paths.token_file().exists())
        await app2.action_quit()

    # --- full walk: validation, Back state retention, save, preflight ---
    app3 = make_wizard_app()
    async with app3.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        scr = app3.screen
        check("wizard restarts at intake",
              isinstance(scr, wiz.IntakeChannelScreen))

        # Inline validation: required field missing keeps the modal open.
        scr.query_one("#wiz_workspace", Input).value = ""
        scr.query_one("#wiz_workspace", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("missing workspace_id keeps intake open with inline error",
              app3.screen is scr
              and "workspace_id is required"
              in str(scr.query_one("#wizard_error").render()))

        scr.query_one("#wiz_provider", Input).value = "discord"
        scr.query_one("#wiz_workspace", Input).value = "111"
        scr.query_one("#wiz_conversation", Input).value = "222"
        await pilot.press("enter")
        await pilot.pause()
        check("valid intake advances",
              isinstance(app3.screen, wiz.AllowlistScreen))

        # Back retains the entered intake values.
        await pilot.click("#btn_wiz_back")
        await pilot.pause()
        check("back returns to intake with state retained",
              isinstance(app3.screen, wiz.IntakeChannelScreen)
              and app3.screen.query_one("#wiz_workspace", Input).value
              == "111")
        app3.screen.query_one("#wiz_workspace", Input).focus()
        await pilot.press("enter")
        await pilot.pause()

        # Allowlist: empty-empty warns once, advances on the second Next.
        scr = app3.screen
        scr.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("empty allowlists warn without advancing",
              app3.screen is scr
              and "deny-by-default"
              in str(scr.query_one("#wizard_error").render()))
        await pilot.press("enter")
        await pilot.pause()
        check("second Next accepts empty allowlists",
              isinstance(app3.screen, wiz.DenyRepoScreen))

        app3.screen.query_one("#wiz_repo_name", Input).value = "testrepo"
        app3.screen.query_one("#wiz_repo_name", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("deny/repo advances to ceilings",
              isinstance(app3.screen, wiz.CeilingsScreen))

        # Ceilings: out-of-range value keeps the modal open, then fix.
        scr = app3.screen
        scr.query_one("#wiz_sandbox_pids", Input).value = "99999"
        scr.query_one("#wiz_sandbox_pids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("out-of-range ceiling keeps modal open with range error",
              app3.screen is scr
              and "outside [16, 4096]"
              in str(scr.query_one("#wizard_error").render()))
        scr.query_one("#wiz_sandbox_pids", Input).value = "1024"
        await pilot.press("enter")
        await pilot.pause()
        check("valid ceilings advance to token",
              isinstance(app3.screen, wiz.TokenScreen))

        # Token: required when none stored yet.
        scr = app3.screen
        scr.query_one("#wiz_token", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("empty token without a stored one keeps modal open",
              app3.screen is scr
              and "no token stored yet"
              in str(scr.query_one("#wizard_error").render()))
        scr.query_one("#wiz_token", Input).value = "secret-token-123"
        await pilot.press("enter")
        await pilot.pause()
        check("token advances to live validation",
              isinstance(app3.screen, wiz.LiveCheckScreen))

        # Skip path: Continue without validating — the live seam is
        # never called and the wizard proceeds normally.
        check("live seam not called before validate", wiz_live["n"] == 0)
        await pilot.click("#btn_wiz_next")
        await pilot.pause()
        check("continue skips live validation into summary",
              isinstance(app3.screen, wiz.SummaryScreen)
              and wiz_live["n"] == 0)

        # Back into the live step and validate with the injected runner.
        await pilot.click("#btn_wiz_back")
        await pilot.pause()
        check("back returns to live validation",
              isinstance(app3.screen, wiz.LiveCheckScreen))
        await pilot.click("#btn_wiz_live_run")
        await app3.workers.wait_for_complete()
        await pilot.pause()
        live_text = str(
            app3.screen.query_one("#wiz_live_results").render())
        check("live results rendered via format_row",
              "✓ token accepted" in live_text
              and "✗ missing required channel permission(s)" in live_text)
        check("live runner received the entered values",
              wiz_live["n"] == 1
              and wiz_live["args"]
              == ("secret-token-123", "111", "222", None))
        await asyncio.sleep(0.4)  # Button active-effect window (see below)
        await pilot.click("#btn_wiz_next")
        await pilot.pause()
        check("continue after a FAILING live validation reaches summary "
              "(advisory-only)",
              isinstance(app3.screen, wiz.SummaryScreen))

        summary = str(
            app3.screen.query_one("#wiz_summary").render())
        check("summary shows token as will-write, never the value",
              "(will write)" in summary
              and "secret-token-123" not in summary)

        # Failure-aware save: token writer raises AFTER the config landed.
        # (Baseline the expensive-probe spy: the panel's on_mount kick also
        # runs it; only the summary preflight should add one more call.)
        probes_before = wiz_expensive["n"]
        token_calls["fail"] = True
        await pilot.click("#btn_wiz_next")
        await pilot.pause()
        state_text = str(
            app3.screen.query_one("#wiz_save_state").render())
        check("config write persisted despite token failure",
              config_path.exists()
              and "config: written" in state_text)
        check("token failure rendered per-item, modal stays open",
              isinstance(app3.screen, wiz.SummaryScreen)
              and "token: FAILED — disk full" in state_text)
        check("token file not written on failure",
              not paths.token_file().exists())

        # Retry with the writer fixed: save completes end-to-end. (The
        # sleep steps past the Button's ~0.3s active-effect window, which
        # swallows a same-instant second click — a Pilot artifact, not a
        # user-facing behavior.)
        token_calls["fail"] = False
        await asyncio.sleep(0.4)
        await pilot.click("#btn_wiz_next")
        await app3.workers.wait_for_complete()
        await pilot.pause()
        state_text = str(
            app3.screen.query_one("#wiz_save_state").render())
        check("retry completes both writes",
              "config: written" in state_text
              and "token: written" in state_text)
        check("token file written with 0600",
              stat.S_IMODE(paths.token_file().stat().st_mode) == 0o600)
        check("token file holds the entered value",
              paths.token_file().read_text(encoding="utf-8")
              == "secret-token-123")

        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        check("saved config carries the wizard values",
              data["intake_channel"]["workspace_id"] == "111"
              and data["intake_channel"]["conversation_id"] == "222"
              and data["allowed_user_ids"] == []
              and data["repo_name"] == "testrepo"
              and data["sandbox_pids"] == 1024)

        # Clearing an exposed optional field must DELETE it, not let the
        # merge writer preserve the stale value (regression: repo_name).
        from chatlink import config_write
        cleared = dict(app3.screen.state)
        cleared["repo_name"] = ""
        check("emptied repo_name maps to DELETE in build_edits",
              wiz.build_edits(cleared)["repo_name"]
              is config_write.DELETE)
        config_write.write_config(config_path, wiz.build_edits(cleared))
        check("cleared repo_name removed from a saved config",
              "repo_name" not in yaml.safe_load(
                  config_path.read_text(encoding="utf-8")))
        # Restore the config the earlier assertions wrote (harmless).
        config_write.write_config(config_path,
                                  wiz.build_edits(app3.screen.state))

        pf_text = str(app3.screen.query_one("#wiz_preflight").render())
        check("summary renders cheap preflight rows",
              "✗ bot token missing" in pf_text)
        check("summary renders expensive preflight results",
              wiz_expensive["n"] == probes_before + 1
              and "agent command: fake-agent" in pf_text)
        check("summary shows the ait git commit hint",
              "./ait git add" in pf_text
              and "never commits" in pf_text)

        # Save became Close; it dismisses the wizard.
        check("save button relabeled to Close",
              str(app3.screen.query_one(
                  "#btn_wiz_next", Button).label) == "Close")
        await asyncio.sleep(0.4)
        await pilot.click("#btn_wiz_next")
        await pilot.pause()
        check("close dismisses the wizard",
              not isinstance(app3.screen, wiz._WizardStep))
        await app3.action_quit()

    # --- live step, mid-run Continue: a late worker result must not touch
    # the dismissed screen (generation + is_attached guard, t1149_5) ---
    live_mode["block"] = True
    wiz_live["n"] = 0
    app4 = make_wizard_app()
    async with app4.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        # Config + token exist from the walk above, so every step is
        # pre-filled/kept — Enter through to the live step.
        scr = app4.screen
        scr.query_one("#wiz_conversation", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        app4.screen.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")   # deny-by-default warn
        await pilot.pause()
        await pilot.press("enter")   # second Next advances
        await pilot.pause()
        app4.screen.query_one("#wiz_repo_name", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        app4.screen.query_one("#wiz_sandbox_pids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        app4.screen.query_one("#wiz_token", Input).focus()
        await pilot.press("enter")   # empty keeps the stored token
        await pilot.pause()
        check("mid-run walk reaches the live step",
              isinstance(app4.screen, wiz.LiveCheckScreen))
        await pilot.click("#btn_wiz_live_run")
        await pilot.pause()
        check("live progress line shown while the worker runs",
              "validating live" in str(
                  app4.screen.query_one("#wiz_live_results").render()))
        await pilot.click("#btn_wiz_next")   # Continue mid-run
        await pilot.pause()
        check("continue mid-run reaches summary",
              isinstance(app4.screen, wiz.SummaryScreen))
        live_block.set()                     # release the worker late
        await app4.workers.wait_for_complete()
        await pilot.pause()
        check("late live result did not disturb the summary screen",
              isinstance(app4.screen, wiz.SummaryScreen)
              and wiz_live["n"] == 1)
        await pilot.press("escape")          # abort — no writes intended
        await pilot.pause()
        await app4.action_quit()
    live_mode["block"] = False

    print(f"\nPASS: {PASS}, FAIL: 0")


asyncio.run(main())
PYEOF

echo
echo "PASS: test_chatlink_tui.sh"
