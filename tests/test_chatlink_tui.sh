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
#    leaves config + token untouched but persists a token-free draft to the
#    gitignored sessions dir (t1190) — relaunch offers resume/start-fresh,
#    resume caps at the token step, a successful save deletes the draft;
#    Save writes the merged YAML + 0600
#    token (failure-aware: a raising token writer keeps the config write,
#    renders the per-item FAILED state, and a later Save retries); the
#    summary renders injected preflight results + the ./ait git commit hint.
#    Step order (t1186_3): intake → token → live check → allowlist →
#    deny/repo → ceilings → summary, with the "Step N/7" title DERIVED from
#    the _STEPS index (asserted at two different positions).
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
import json
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
from chatlink import wizard_draft  # noqa: E402
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
    from textual.widgets import Button, Input, SelectionList

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

    # Allowlist picker seam spy (t1186_4): the wizard must never fetch on
    # its own — only an explicit "Fetch from Discord" press calls this.
    from chatlink.allowlist_fetch import AllowlistFetchResult
    ALICE, BOB, CAROL = ("100000000000000001", "100000000000000002",
                         "100000000000000003")
    MODS, DEVS = "200000000000000001", "200000000000000002"

    def canned(**kw):
        base = dict(members=[(ALICE, "alice"), (BOB, "bob"),
                             (CAROL, "carol")],
                    roles=[(MODS, "mods"), (DEVS, "devs")])
        base.update(kw)
        return AllowlistFetchResult(**base)

    wiz_fetch = {"n": 0, "args": None, "result": None, "raise": False}
    fetch_block = threading.Event()
    fetch_mode = {"block": False}

    def wiz_spy_fetch(token, workspace_id, conversation_id, thread_id=None,
                      **_kw):
        wiz_fetch["n"] += 1
        wiz_fetch["args"] = (token, workspace_id, conversation_id, thread_id)
        if fetch_mode["block"]:
            fetch_block.wait(timeout=10)
        if wiz_fetch["raise"]:
            raise RuntimeError("fetch exploded")
        return wiz_fetch["result"] if wiz_fetch["result"] else canned()

    def make_wizard_app():
        return ChatlinkApp(
            sessions_dir=wtmp / "sessions", clock=lambda: now,
            cheap_runner=fake_cheap, expensive_runner=wiz_spy_expensive,
            wizard_config_path=config_path, token_writer=token_writer,
            live_runner=wiz_spy_live,
            allowlist_fetch_runner=wiz_spy_fetch)

    # Drift guard: the draft allowlist must track initial_state exactly
    # (a future wizard key silently missing from drafts is a bug).
    check("draft allowlist == initial_state keys minus the token",
          set(wizard_draft.DRAFT_STATE_KEYS)
          == set(wiz.initial_state(wiz.resolve_seams(
              wiz.WizardSeams(config_path=wtmp / "no-config.yaml"))))
          - {"token"})

    # --- abort mid-wizard: config/token untouched, draft persisted ---
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
        check("intake advances to token",
              isinstance(app2.screen, wiz.TokenScreen))
        app2.screen.query_one("#wiz_token", Input).value = "secret-token-123"
        app2.screen.query_one("#wiz_token", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("token advances to live check",
              isinstance(app2.screen, wiz.LiveCheckScreen))
        await pilot.press("escape")
        await pilot.pause()
        check("escape aborts the wizard",
              not isinstance(app2.screen, wiz._WizardStep))
        check("abort leaves config file untouched", not config_path.exists())
        check("abort leaves token file untouched",
              not paths.token_file().exists())
        # t1190: the abort persisted a token-free draft (the amended
        # contract — config/token still summary-only; drafts are separate).
        draft_file = wizard_draft.draft_path()  # under wtmp via the
        check("abort persists a draft", draft_file.exists())  # root patch
        draft_raw = draft_file.read_text(encoding="utf-8")
        check("token provably absent from the draft",
              "secret-token-123" not in draft_raw)
        draft_data = json.loads(draft_raw)
        check("draft carries entered values + step name + token metadata",
              draft_data["state"]["workspace_id"] == "111"
              and draft_data["step_name"] == wiz.LiveCheckScreen.step_name
              and draft_data["token_entered"] is True)
        await app2.action_quit()

    # --- resume offer: accept restores values, caps at the token step ---
    app_res = make_wizard_app()
    async with app_res.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        check("relaunch with a draft offers resume",
              isinstance(app_res.screen, wiz._ResumeDraftScreen))
        check("resume offer names the recorded step",
              wiz.LiveCheckScreen.step_name
              in str(app_res.screen.query_one("#wizard_dialog Label")
                     .render()))
        await pilot.click("#btn_wiz_resume")
        await pilot.pause()
        # Draft recorded the live-check step with token_entered=True and
        # no token on disk — both cap conditions hold independently.
        check("resume caps at the token step (typed token unrecoverable)",
              isinstance(app_res.screen, wiz.TokenScreen))
        check("resume restores the drafted values",
              app_res.screen.state["workspace_id"] == "111")
        await pilot.press("escape")
        await pilot.pause()
        check("aborting a resumed session keeps the draft",
              wizard_draft.draft_path().exists())
        await app_res.action_quit()

    # --- full walk: validation, Back state retention, save, preflight ---
    app3 = make_wizard_app()
    async with app3.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        check("relaunch offers resume before the step chain",
              isinstance(app3.screen, wiz._ResumeDraftScreen))
        await pilot.click("#btn_wiz_fresh")
        await pilot.pause()
        scr = app3.screen
        check("start fresh deletes the draft",
              not wizard_draft.draft_path().exists())
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
        check("valid intake advances to token",
              isinstance(app3.screen, wiz.TokenScreen))
        # Numbering is DERIVED from the _STEPS index, not a literal.
        check("token title numbered from the _STEPS index (2/7)",
              "Step 2/7" in str(
                  app3.screen.query_one("#wizard_title").render()))

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

        # Token: required when none stored yet (app2 aborted without
        # writing one).
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
        check("continue skips live validation into allowlist",
              isinstance(app3.screen, wiz.AllowlistScreen)
              and wiz_live["n"] == 0)
        # Second index: proves the title tracks position rather than a
        # relabeled per-class constant.
        check("allowlist title numbered from the _STEPS index (4/7)",
              "Step 4/7" in str(
                  app3.screen.query_one("#wizard_title").render()))

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
        check("continue after a FAILING live validation advances "
              "(advisory-only)",
              isinstance(app3.screen, wiz.AllowlistScreen))

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
        check("valid ceilings advance to summary",
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
        check("successful save deletes the draft",
              not wizard_draft.draft_path().exists())
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
    # t1190 hygiene: escape-mid-wizard leaves a draft; clear so `w`
    # opens the step chain directly, not the resume offer.
    wizard_draft.clear_draft()
    app4 = make_wizard_app()
    async with app4.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        # Config + token exist from the walk above, so every step is
        # pre-filled/kept — Enter through to the live step (which the
        # reorder puts third, right after intake and token).
        scr = app4.screen
        scr.query_one("#wiz_conversation", Input).focus()
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
        check("continue mid-run reaches allowlist",
              isinstance(app4.screen, wiz.AllowlistScreen))
        live_block.set()                     # release the worker late
        await app4.workers.wait_for_complete()
        await pilot.pause()
        check("late live result did not disturb the allowlist screen",
              isinstance(app4.screen, wiz.AllowlistScreen)
              and wiz_live["n"] == 1)
        await pilot.press("escape")          # abort — no writes intended
        await pilot.pause()
        await app4.action_quit()
    live_mode["block"] = False

    # ---- allowlist picker UI (t1186_4) ---------------------------------
    # Per-dimension modes + live Discord pickers. The pinned invariant is
    # that a picker's ticked set is ALWAYS `active list ∩ visible rows`
    # with the Input as the source of truth; several cases below fail
    # against designs that only reconcile at rebuild time.
    check("fetch seam untouched by walks that never pressed Fetch",
          wiz_fetch["n"] == 0)

    def opt_prompts(picker):
        return [str(picker.get_option_at_index(i).prompt)
                for i in range(picker.option_count)]

    async def goto_allowlist(app, pilot, *, workspace="111",
                             conversation="222"):
        """Walk the real wizard chain to the allowlist step."""
        # t1190 hygiene: an earlier block's escape-mid-wizard leaves a
        # draft that would turn `w` into the resume offer.
        wizard_draft.clear_draft()
        await pilot.press("w")
        await pilot.pause()
        scr = app.screen
        scr.query_one("#wiz_provider", Input).value = "discord"
        scr.query_one("#wiz_workspace", Input).value = workspace
        scr.query_one("#wiz_conversation", Input).value = conversation
        scr.query_one("#wiz_conversation", Input).focus()
        await pilot.press("enter")            # -> token
        await pilot.pause()
        app.screen.query_one("#wiz_token", Input).focus()
        await pilot.press("enter")            # keep stored token -> live
        await pilot.pause()
        await pilot.click("#btn_wiz_next")    # Continue -> allowlist
        await pilot.pause()
        return app.screen

    TYPED = "900000000000000009"              # never in the fetched set

    # --- picker basics, the Input<->ticks invariant, filter, mode toggle ---
    app5 = make_wizard_app()
    async with app5.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app5, pilot)
        check("walk reaches the allowlist step",
              isinstance(scr, wiz.AllowlistScreen))
        check("fetch seam not called before pressing Fetch",
              wiz_fetch["n"] == 0)

        # One typed id that IS among the fetched rows, one that is not.
        scr.query_one("#wiz_user_ids", Input).value = f"{ALICE}, {TYPED}"
        await pilot.pause()
        await pilot.click("#btn_wiz_fetch")
        await app5.workers.wait_for_complete()
        await pilot.pause()
        check("fetch runner received the stored token + entered intake ids",
              wiz_fetch["n"] == 1
              and wiz_fetch["args"] == ("secret-token-123", "111", "222",
                                        None))

        members = scr.query_one("#wiz_member_list", SelectionList)
        roles = scr.query_one("#wiz_role_list", SelectionList)
        check("member rows render as '<name> (<id>)'",
              opt_prompts(members) == [f"alice ({ALICE})", f"bob ({BOB})",
                                       f"carol ({CAROL})"])
        check("role rows populated from the same result",
              opt_prompts(roles) == [f"mods ({MODS})", f"devs ({DEVS})"])
        # INVARIANT: a typed id that is among the fetched rows starts ticked
        # — otherwise the next selection would read it as "deselected".
        check("typed id present in the fetched set starts selected",
              set(members.selected) == {ALICE})
        check("typed id outside the fetched set is left alone",
              TYPED in scr._working["allowed_user_ids"])

        # Keyboard path: highlight bob and toggle with the real binding.
        members.focus()
        members.highlighted = 1
        await pilot.press("space")
        await pilot.pause()
        ids = scr.query_one("#wiz_user_ids", Input).value
        check("selecting a fetched row rewrites the Input",
              BOB in ids)
        check("manually typed ids survive fetch + selection",
              ALICE in ids and TYPED in ids)

        # Type an id AFTER the rows were built, with NO rebuild in between,
        # then change a selection: the typed id must survive.
        scr.query_one("#wiz_user_ids", Input).value = f"{ids}, {CAROL}"
        await pilot.pause()
        check("id typed after the rebuild ticks its row",
              CAROL in set(members.selected))
        members.toggle(ALICE)                 # deselect
        await pilot.pause()
        ids = scr.query_one("#wiz_user_ids", Input).value
        check("deselecting a visible row removes exactly that id",
              ALICE not in ids)
        check("id typed after the rebuild survives a later selection change",
              CAROL in ids and BOB in ids and TYPED in ids)

        # Filtering narrows rows only.
        before_working = {k: list(v) for k, v in scr._working.items()}
        scr.query_one("#wiz_fetch_filter", Input).value = "bob"
        await pilot.pause()
        check("filter narrows the visible member rows",
              opt_prompts(members) == [f"bob ({BOB})"])
        check("filtering mutates neither the Input nor the working lists",
              scr.query_one("#wiz_user_ids", Input).value == ids
              and {k: list(v) for k, v in scr._working.items()}
              == before_working)
        check("a selected id filtered out of view is still kept",
              CAROL in scr._working["allowed_user_ids"])
        # Change a VISIBLE row's state while another selected id is hidden
        # by the filter: the hidden one must survive. This is the reason
        # `preserved` is computed against the VISIBLE set rather than the
        # whole fetched set — `sl.selected` only ever reports visible rows.
        members.toggle(BOB)
        await pilot.pause()
        check("a hidden-but-selected id survives a selection change",
              CAROL in scr._working["allowed_user_ids"]
              and TYPED in scr._working["allowed_user_ids"]
              and BOB not in scr._working["allowed_user_ids"])
        members.toggle(BOB)                   # restore
        await pilot.pause()
        scr.query_one("#wiz_fetch_filter", Input).value = ""
        await pilot.pause()

        # Mode toggle after a selection.
        allowed_before = list(scr._working["allowed_user_ids"])
        scr.query_one("#wiz_user_mode", wiz.CycleField).cycle_next()
        await pilot.pause()
        check("mode toggle switches the user dimension to denylist",
              scr._modes["user"] == "denylist")
        check("the selection landed only in the previously active list",
              scr._working["allowed_user_ids"] == allowed_before
              and scr._working["denied_user_ids"] == [])
        check("the Input now shows the incoming (denied) list",
              scr.query_one("#wiz_user_ids", Input).value == "")
        check("the ids label relabels with the mode",
              "Denied user ids"
              in str(scr.query_one("#wiz_user_ids_label").render()))
        check("picker ticks recomputed from the newly active list",
              set(members.selected) == set())

        members.toggle(BOB)
        await pilot.pause()
        check("a selection after the toggle writes to the NOW-active list",
              scr._working["denied_user_ids"] == [BOB]
              and scr._working["allowed_user_ids"] == allowed_before)

        scr.query_one("#wiz_user_mode", wiz.CycleField).cycle_next()
        await pilot.pause()
        check("allowed -> denied -> allowed preserves both lists exactly",
              scr._working["allowed_user_ids"] == allowed_before
              and scr._working["denied_user_ids"] == [BOB])
        check("the Input is restored to the allowed list",
              set(scr._parse_ids(
                  scr.query_one("#wiz_user_ids", Input).value))
              == set(allowed_before))
        check("a populated inactive list is disclosed on the screen",
              "denied_user_ids is kept but ignored"
              in str(scr.query_one("#wiz_user_inactive").render()))

        # Rebuild echo: Textual posts SelectedChanged for every
        # initial_state=True option and post_message QUEUES, so drain the
        # pump and prove no rebuild ever looked like an operator action.
        snapshot = {k: list(v) for k, v in scr._working.items()}
        inputs_before = {d.input_id:
                         scr.query_one(f"#{d.input_id}", Input).value
                         for d in wiz._DIMENSIONS}
        scr.query_one("#wiz_fetch_filter", Input).value = "o"
        await pilot.pause()
        scr.query_one("#wiz_fetch_filter", Input).value = ""
        await pilot.pause()
        await pilot.click("#btn_wiz_fetch")
        await app5.workers.wait_for_complete()
        await pilot.pause()
        await pilot.pause()
        check("fetch/filter/toggle rebuilds never write back (lists)",
              {k: list(v) for k, v in scr._working.items()} == snapshot)
        check("fetch/filter/toggle rebuilds never write back (Inputs)",
              {d.input_id: scr.query_one(f"#{d.input_id}", Input).value
               for d in wiz._DIMENSIONS} == inputs_before)

        # Enter while narrowing must not advance the step.
        scr.query_one("#wiz_fetch_filter", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("Enter in the picker filter does not advance the step",
              app5.screen is scr)

        scr.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("a restricted posture advances silently",
              isinstance(app5.screen, wiz.DenyRepoScreen))

        app5.screen.query_one("#wiz_repo_name", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        app5.screen.query_one("#wiz_sandbox_pids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("ceilings advance to summary",
              isinstance(app5.screen, wiz.SummaryScreen))
        summary = str(app5.screen.query_one("#wiz_summary").render())
        check("summary renders one line per authorization dimension",
              "users: allowlist:" in summary
              and "roles: allowlist: (none)" in summary)
        check("summary discloses the non-empty inactive list",
              f"denied_user_ids kept but ignored: {BOB}" in summary)

        edits = wiz.build_edits(app5.screen.state)
        check("build_edits omits the transient picker cache",
              "_fetched" not in edits)
        check("the cache key stores a token digest, never the raw token",
              "secret-token-123" not in str(app5.screen.state["_fetched"]))

        await pilot.click("#btn_wiz_next")
        await app5.workers.wait_for_complete()
        await pilot.pause()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        check("saved config round-trips both modes and all four lists",
              data["user_authorization_mode"] == "allowlist"
              and data["role_authorization_mode"] == "allowlist"
              and data["allowed_user_ids"] == allowed_before
              and data["denied_user_ids"] == [BOB]
              and data["allowed_role_ids"] == []
              and data["denied_role_ids"] == [])
        check("the transient picker cache never reaches the config file",
              "_fetched" not in data)
        await app5.action_quit()

    # --- validation: snowflake shape + dedupe ---
    app6 = make_wizard_app()
    async with app6.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app6, pilot)
        scr.query_one("#wiz_user_ids", Input).value = f"12345, {ALICE}"
        await pilot.pause()
        scr.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        err = str(scr.query_one("#wizard_error").render())
        check("an invalid snowflake blocks advance and names the bad token",
              app6.screen is scr
              and "not valid Discord ids" in err and "12345" in err)
        scr.query_one("#wiz_user_ids", Input).value = \
            f"{ALICE}, {ALICE}, {BOB}"
        await pilot.pause()
        scr.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("duplicate ids are deduped on accept",
              isinstance(app6.screen, wiz.DenyRepoScreen)
              and scr.state["allowed_user_ids"] == [ALICE, BOB])
        await app6.action_quit()

    # --- posture warnings: keyed to the exact configuration warned about ---
    app7 = make_wizard_app()
    async with app7.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app7, pilot)
        scr.query_one("#wiz_user_ids", Input).value = ""
        scr.query_one("#wiz_role_ids", Input).value = ""
        await pilot.pause()

        def err():
            return str(scr.query_one("#wizard_error").render())

        scr.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("deny_all on both dimensions warns without advancing",
              app7.screen is scr
              and "deny-by-default" in err()
              and "nobody will be able to open a bug report" in err())

        # Mixed degenerate posture: roles denylist, users allowlist-but-empty.
        scr.query_one("#wiz_role_mode", wiz.CycleField).cycle_next()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        check("a mixed degenerate posture re-warns with its own copy",
              app7.screen is scr
              and "the empty users allowlist denies everyone" in err())

        # A DIFFERENT risky posture: a one-shot flag would accept silently.
        scr.query_one("#wiz_user_mode", wiz.CycleField).cycle_next()
        await pilot.pause()
        # The config saved earlier carried a denied_user_ids entry that was
        # inactive under allowlist mode; switching modes must surface it
        # verbatim (round-tripped through a real save + reload).
        check("switching to denylist surfaces the preserved denied list",
              scr.query_one("#wiz_user_ids", Input).value == BOB)
        scr.query_one("#wiz_user_ids", Input).value = ""
        await pilot.pause()
        scr.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("flipping into open_members re-warns instead of advancing",
              app7.screen is scr
              and "any channel member will be able to open a bug report"
              in err())

        await pilot.press("enter")
        await pilot.pause()
        check("a second press on the SAME posture advances",
              isinstance(app7.screen, wiz.DenyRepoScreen))
        await app7.action_quit()

    # --- Back retention, and stale-context cache invalidation ---
    app8 = make_wizard_app()
    async with app8.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app8, pilot)
        # Start from a known state (the saved config prefills these), while
        # leaving the inactive denied_user_ids entry in place — the removal
        # below must reach BOTH of a dimension's lists.
        scr.query_one("#wiz_user_ids", Input).value = ""
        scr.query_one("#wiz_role_ids", Input).value = ""
        await pilot.pause()
        check("the saved config prefilled the inactive denied list",
              scr._working["denied_user_ids"] == [BOB])
        fetches_before = wiz_fetch["n"]
        await pilot.click("#btn_wiz_fetch")
        await app8.workers.wait_for_complete()
        await pilot.pause()
        scr.query_one("#wiz_member_list", SelectionList).toggle(ALICE)
        scr.query_one("#wiz_role_list", SelectionList).toggle(MODS)
        await pilot.pause()
        # BOB is typed by hand but IS in the fetched set (the ambiguous
        # case); TYPED is not fetched and is the operator's own assertion.
        user_input = scr.query_one("#wiz_user_ids", Input)
        user_input.value = f"{user_input.value}, {BOB}, {TYPED}"
        await pilot.pause()

        await pilot.click("#btn_wiz_back")
        await pilot.pause()
        check("Back from the allowlist step lands on the live step",
              isinstance(app8.screen, wiz.LiveCheckScreen))
        await asyncio.sleep(0.4)
        await pilot.click("#btn_wiz_next")
        await pilot.pause()
        scr2 = app8.screen
        check("Back-then-forward retains all four lists and both modes",
              isinstance(scr2, wiz.AllowlistScreen)
              and set(scr2._working["allowed_user_ids"])
              == {ALICE, BOB, TYPED}
              and scr2._working["allowed_role_ids"] == [MODS]
              and scr2._modes == {"user": "allowlist", "role": "allowlist"})
        check("re-entry reuses the cached rows without refetching",
              wiz_fetch["n"] == fetches_before + 1
              and scr2.query_one("#wiz_member_list",
                                 SelectionList).option_count == 3)

        # Change the Discord context on an earlier step.
        for _ in range(3):                     # allowlist -> live -> token
            await pilot.click("#btn_wiz_back")  # -> intake
            await pilot.pause()
            await asyncio.sleep(0.4)
        check("Back reaches the intake step",
              isinstance(app8.screen, wiz.IntakeChannelScreen))
        app8.screen.query_one("#wiz_conversation", Input).value = "333"
        app8.screen.query_one("#wiz_conversation", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        app8.screen.query_one("#wiz_token", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#btn_wiz_next")
        await pilot.pause()
        scr3 = app8.screen
        check("a changed intake context empties the picker",
              isinstance(scr3, wiz.AllowlistScreen)
              and scr3.query_one("#wiz_member_list",
                                 SelectionList).option_count == 0)
        notice = str(scr3.query_one("#wiz_fetch_status").render())
        check("the stale-context notice names every removed id",
              "intake channel or token changed" in notice
              and ALICE in notice and BOB in notice and MODS in notice)
        check("picker-origin ids are removed from BOTH of a dimension's "
              "lists (a denied role from the old guild is meaningless too)",
              ALICE not in scr3._working["allowed_user_ids"]
              and scr3._working["denied_user_ids"] == []
              and scr3._working["allowed_role_ids"] == [])
        check("an id both typed AND fetched counts as picker-origin",
              BOB not in scr3._working["allowed_user_ids"])
        check("a manually typed id is kept across the context change",
              scr3._working["allowed_user_ids"] == [TYPED]
              and scr3.query_one("#wiz_user_ids", Input).value == TYPED)
        await app8.action_quit()

    # --- the removal is fail-closed, and its result is surfaced ---
    app9 = make_wizard_app()
    async with app9.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app9, pilot, conversation="444")
        scr.query_one("#wiz_user_ids", Input).value = ""
        scr.query_one("#wiz_role_ids", Input).value = ""
        await pilot.pause()
        await pilot.click("#btn_wiz_fetch")
        await app9.workers.wait_for_complete()
        await pilot.pause()
        scr.query_one("#wiz_member_list", SelectionList).toggle(ALICE)
        await pilot.pause()
        check("only the picker-selected id is authorized",
              scr._working["allowed_user_ids"] == [ALICE])
        for _ in range(3):
            await pilot.click("#btn_wiz_back")
            await pilot.pause()
            await asyncio.sleep(0.4)
        app9.screen.query_one("#wiz_conversation", Input).value = "555"
        app9.screen.query_one("#wiz_conversation", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        app9.screen.query_one("#wiz_token", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.click("#btn_wiz_next")
        await pilot.pause()
        scr4 = app9.screen
        check("removing the only authorized id empties the allowlists",
              scr4._working["allowed_user_ids"] == []
              and scr4._working["allowed_role_ids"] == [])
        scr4.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("the degenerate result of removal is caught by the posture "
              "warning (fail-closed, never silent)",
              app9.screen is scr4
              and "nobody will be able to open a bug report"
              in str(scr4.query_one("#wizard_error").render()))
        await app9.action_quit()

    # --- advisory failures: per-stage errors, truncation, raising runner ---
    app10 = make_wizard_app()
    wiz_fetch["result"] = canned(roles=[],
                                 roles_error="role fetch failed (Forbidden)",
                                 members_truncated=True)
    async with app10.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app10, pilot, conversation="666")
        await pilot.click("#btn_wiz_fetch")
        await app10.workers.wait_for_complete()
        await pilot.pause()
        status = str(scr.query_one("#wiz_fetch_status").render())
        check("a per-stage error is surfaced without blanking the other "
              "stage (partial results)",
              "! roles: role fetch failed (Forbidden)" in status
              and scr.query_one("#wiz_member_list",
                                SelectionList).option_count == 3)
        check("the truncation notice is shown",
              "showing the first 500 members" in status)
        # t1204 negative control: roles had no PRIOR rows, so a first-fetch
        # stage failure must not claim staleness for anything.
        check("a first-fetch stage failure never claims staleness",
              "showing the EARLIER" not in status
              and not scr.query_one("#wiz_role_list",
                                    SelectionList).has_class("stale"))
        await app10.action_quit()

    wiz_fetch["result"] = None
    wiz_fetch["raise"] = True
    app11 = make_wizard_app()
    async with app11.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app11, pilot, conversation="777")
        await pilot.click("#btn_wiz_fetch")
        await app11.workers.wait_for_complete()
        await pilot.pause()
        status = str(scr.query_one("#wiz_fetch_status").render())
        check("a raising fetch runner degrades to manual entry",
              "fetch failed" in status
              and "enter ids manually above" in status
              and not scr.query_one("#wiz_member_list", SelectionList).display)
        # t1204 negative control: nothing was ever revealed, so there is no
        # earlier fetch to qualify — the two failure copies must not merge.
        check("a first-fetch failure never claims an EARLIER fetch",
              "EARLIER" not in status and scr._fetch_key is None)
        scr.query_one("#wiz_user_ids", Input).value = ALICE
        await pilot.pause()
        scr.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("a failed fetch never blocks Next",
              isinstance(app11.screen, wiz.DenyRepoScreen))
        await app11.action_quit()
    wiz_fetch["raise"] = False

    # ---- failed-refresh staleness (t1204) -------------------------------
    # `run_allowlist_fetch` NEVER raises: production failures arrive as
    # per-stage members_error/roles_error on a RETURNED result, so the
    # raising-runner case above is the exceptional shape, not the common
    # one. Both must classify identically, per dimension.
    OUTAGE = dict(members=[], roles=[],
                  members_error="connection failed (OSError)",
                  roles_error="connection failed (OSError)")

    async def back_then_forward(app, pilot):
        """allowlist -> live -> allowlist, returning the NEW screen."""
        await pilot.click("#btn_wiz_back")
        await pilot.pause()
        await asyncio.sleep(0.4)
        await pilot.click("#btn_wiz_next")
        await pilot.pause()
        return app.screen

    async def press_fetch(app, pilot):
        """Press Fetch and settle. The sleep steps past the Button's ~0.3s
        active-effect window, which swallows a same-instant second click —
        a Pilot artifact (see the token-retry note above), and these blocks
        press Fetch repeatedly on one screen."""
        await asyncio.sleep(0.4)
        await pilot.click("#btn_wiz_fetch")
        await app.workers.wait_for_complete()
        await pilot.pause()

    # --- A: FIRST fetch where every stage failed (the outage shape) ---
    wiz_fetch["result"] = canned(**OUTAGE)
    app11b = make_wizard_app()
    async with app11b.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app11b, pilot, conversation="779")
        await press_fetch(app11b, pilot)
        status = str(scr.query_one("#wiz_fetch_status").render())
        check("an all-stages-failed FIRST fetch degrades to manual entry "
              "(not an empty picker presented as a clean result)",
              "! members: connection failed (OSError)" in status
              and "enter ids manually above" in status
              and scr._fetch_key is None
              and not scr.query_one("#wiz_member_list",
                                    SelectionList).display)
        scr.query_one("#wiz_user_ids", Input).value = ALICE
        await pilot.pause()
        scr2 = await back_then_forward(app11b, pilot)
        check("a produced-nothing first fetch caches nothing to resurrect",
              isinstance(scr2, wiz.AllowlistScreen)
              and "_fetched" not in scr2.state
              and scr2._fetch_key is None
              and not scr2.query_one("#wiz_member_list",
                                     SelectionList).display)
        scr2.query_one("#wiz_user_ids", Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        check("an all-stages-failed fetch never blocks Next",
              isinstance(app11b.screen, wiz.DenyRepoScreen))
        await app11b.action_quit()

    # --- A2: produced-nothing REFRESH after a legitimately empty fetch ---
    # The only route by which a produced-nothing run finds _fetch_key already
    # set — it must clear the cache, not just the key.
    wiz_fetch["result"] = canned(members=[], roles=[])
    app11c = make_wizard_app()
    async with app11c.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app11c, pilot, conversation="781")
        await press_fetch(app11c, pilot)
        check("a fetch that legitimately returns no rows still reveals",
              "fetched 0 member(s) and 0 role(s)"
              in str(scr.query_one("#wiz_fetch_status").render())
              and scr._fetch_key is not None
              and scr.query_one("#wiz_member_list", SelectionList).display)
        scr2 = await back_then_forward(app11c, pilot)
        check("the empty-but-successful fetch round-trips through the cache",
              "_fetched" in scr2.state and scr2._fetch_key is not None)

        wiz_fetch["result"] = canned(**OUTAGE)
        await press_fetch(app11c, pilot)
        check("a produced-nothing refresh clears BOTH the key and the cache",
              scr2._fetch_key is None
              and "_fetched" not in scr2.state
              and not scr2.query_one("#wiz_member_list",
                                     SelectionList).display)
        scr3 = await back_then_forward(app11c, pilot)
        check("the cleared cache cannot resurrect an empty picker with a "
              "blank status line",
              scr3._fetch_key is None
              and not scr3.query_one("#wiz_member_list",
                                     SelectionList).display)
        await app11c.action_quit()

    # --- B: PARTIAL refresh failure marks only the failed dimension ---
    wiz_fetch["result"] = None            # canned() default: 3 members, 2 roles
    app11d = make_wizard_app()
    async with app11d.run_test(size=(110, 80)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app11d, pilot, conversation="783")
        scr.query_one("#wiz_user_ids", Input).value = ""
        scr.query_one("#wiz_role_ids", Input).value = ""
        await pilot.pause()
        await press_fetch(app11d, pilot)
        members = scr.query_one("#wiz_member_list", SelectionList)
        roles = scr.query_one("#wiz_role_list", SelectionList)
        members.toggle(ALICE)
        roles.toggle(MODS)
        await pilot.pause()
        fresh_border = members.styles.border_top
        check("a successful fetch marks nothing stale",
              scr._stale == {"user": False, "role": False}
              and not members.has_class("stale")
              and not roles.has_class("stale"))

        wiz_fetch["result"] = canned(
            roles=[], roles_error="role fetch failed (Forbidden)")
        await press_fetch(app11d, pilot)
        status = str(scr.query_one("#wiz_fetch_status").render())
        check("a failed stage keeps ITS rows and marks only that dimension",
              scr._stale == {"user": False, "role": True}
              and roles.option_count == 2 and roles.has_class("stale")
              and members.option_count == 3
              and not members.has_class("stale")
              and scr._working["allowed_role_ids"] == [MODS]
              and scr._working["allowed_user_ids"] == [ALICE])
        check("the status names the failed stage AND the earlier rows",
              "! roles: role fetch failed (Forbidden)" in status
              and "showing the EARLIER fetch for: roles" in status)
        # Render-level: prove the CSS rule actually resolved (a class alone
        # would pass even if `.stale` lost to the base specificity), and
        # that the border title really reaches the screen.
        svg = (app11d.export_screenshot()
               .replace("&#160;", " ").replace("\u00a0", " "))
        check("the stale marking renders (warning border + border title)",
              roles.styles.border_top != fresh_border
              and members.styles.border_top == fresh_border
              and "previous fetch" in svg and "may be out of date" in svg)
        await app11d.action_quit()

    # --- C: TOTAL refresh failure retains both, and survives Back ---
    wiz_fetch["result"] = None
    app11e = make_wizard_app()
    async with app11e.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app11e, pilot, conversation="785")
        scr.query_one("#wiz_user_ids", Input).value = ""
        scr.query_one("#wiz_role_ids", Input).value = ""
        await pilot.pause()
        await press_fetch(app11e, pilot)
        scr.query_one("#wiz_member_list", SelectionList).toggle(ALICE)
        await pilot.pause()

        wiz_fetch["result"] = canned(**OUTAGE)
        await press_fetch(app11e, pilot)
        check("a total refresh failure retains both dimensions' rows "
              "instead of wiping them",
              scr._stale == {"user": True, "role": True}
              and scr.query_one("#wiz_member_list",
                                SelectionList).option_count == 3
              and scr.query_one("#wiz_role_list",
                                SelectionList).option_count == 2
              and scr._working["allowed_user_ids"] == [ALICE])

        scr2 = await back_then_forward(app11e, pilot)
        check("staleness rides in the cache — re-entry never re-presents "
              "the rows as current",
              scr2._stale == {"user": True, "role": True}
              and scr2.query_one("#wiz_member_list",
                                 SelectionList).option_count == 3
              and scr2.query_one("#wiz_member_list",
                                 SelectionList).has_class("stale")
              and "showing the EARLIER fetch for: users, roles"
              in str(scr2.query_one("#wiz_fetch_status").render()))

        # A raising runner on a refresh classifies exactly like the outage.
        wiz_fetch["result"] = None
        wiz_fetch["raise"] = True
        await press_fetch(app11e, pilot)
        status = str(scr2.query_one("#wiz_fetch_status").render())
        check("a raising runner on a REFRESH marks stale, never wipes",
              "! fetch failed" in status
              and "showing the EARLIER fetch for: users, roles" in status
              and scr2.query_one("#wiz_member_list",
                                 SelectionList).option_count == 3)

        wiz_fetch["raise"] = False
        await press_fetch(app11e, pilot)
        members2 = scr2.query_one("#wiz_member_list", SelectionList)
        check("a successful refetch clears the stale marking everywhere",
              scr2._stale == {"user": False, "role": False}
              and not members2.has_class("stale")
              and not members2.border_title
              and "fetched 3 member(s) and 2 role(s)"
              in str(scr2.query_one("#wiz_fetch_status").render()))
        await app11e.action_quit()

    # --- mid-run Back: a late fetch result must not touch a dead screen ---
    fetch_mode["block"] = True
    app12 = make_wizard_app()
    async with app12.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        scr = await goto_allowlist(app12, pilot, conversation="888")
        fetches_before = wiz_fetch["n"]
        await pilot.click("#btn_wiz_fetch")
        await pilot.pause()
        check("the fetch progress line is shown while the worker runs",
              "fetching members and roles"
              in str(scr.query_one("#wiz_fetch_status").render()))
        await pilot.click("#btn_wiz_back")      # leave mid-run
        await pilot.pause()
        check("Back mid-fetch reaches the live step",
              isinstance(app12.screen, wiz.LiveCheckScreen))
        fetch_block.set()                       # release the worker late
        await app12.workers.wait_for_complete()
        await pilot.pause()
        check("a late fetch result did not disturb the dismissed screen",
              isinstance(app12.screen, wiz.LiveCheckScreen)
              and wiz_fetch["n"] == fetches_before + 1)
        await pilot.press("escape")
        await pilot.pause()
        await app12.action_quit()
    fetch_mode["block"] = False

    print(f"\nPASS: {PASS}, FAIL: 0")


asyncio.run(main())
PYEOF

echo
echo "PASS: test_chatlink_tui.sh"
