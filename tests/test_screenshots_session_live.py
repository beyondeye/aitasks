"""Live tests for the docs-screenshot session primitives (t2278_2).

These boot the REAL `ait board` in an isolated tmux session on the sample
project, through `website/screenshots/cli.py`, exactly as an agent drives it.

Isolation: every session uses its own `-L ait_shots_<id>` socket through
`TmuxClient`, started with `-f /dev/null`. The staging, scenes, content and
static directories are scratch directories, so nothing under `website/` is
read or written (the one exception is the shipped recipe, which is replayed
read-only).

Skip-vs-fail: the module skips only when the `tmux` binary is missing
(`shutil.which`, which does not run the code under test). Once tmux exists, a
board that does not boot or a recipe that does not replay is a FAILURE.

It boots a real TUI under a wall-clock budget, so it sits in the serial
carve-out of `tests/run_all_python_tests.sh`.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_session_live.py -v
"""
import dataclasses
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "website"))

from screenshots import cli, recipe as rc, session as sessions  # noqa: E402
from screenshots import svg_export as sx  # noqa: E402

SHIPPED_SCENES = REPO_ROOT / "website" / "screenshots" / "scenes"
SCENE = "board_child_tasks"
OUTPUT = "aitasks_board_child_tasks.svg"
MARKER = (f'<!-- screenshot: scene={SCENE} file={OUTPUT} '
          'alt="Board with a parent task expanded to show its child tasks" -->')
EXPANDED = "t12_3 order confirmation email"
UPDATE_14 = ("./.aitask-scripts/aitask_update.sh --batch 14 --status Implementing "
             "--assigned-to alex@example.com")


@unittest.skipUnless(shutil.which("tmux"), "tmux is not installed")
class LiveCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ait_shots_test_")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.staging = self.root / "staging"
        self.scenes = self.root / "scenes"
        self.content = self.root / "content"
        self.static = self.root / "static"
        for d in (self.scenes, self.content, self.static / "imgs"):
            d.mkdir(parents=True)
        (self.content / "page.md").write_text(f"# Page\n\n{MARKER}\n", encoding="utf-8")
        # Registered after the tmpdir cleanup, so it runs BEFORE it: every
        # session is stopped while its state directory still exists.
        self.addCleanup(self._stop_all)
        # Failing waits are part of what is tested; keep them short.
        for name, value in (("STEP_TIMEOUT", 4.0), ("EXPECT_TIMEOUT", 3.0)):
            patcher = mock.patch.object(cli, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _stop_all(self):
        for sess in sessions.list_sessions(self.staging):
            sessions.stop(sess)

    def cli(self, *args, scenes=None):
        out = io.StringIO()
        argv = ["--staging", str(self.staging), "--scenes", str(scenes or self.scenes),
                "--content", str(self.content), "--static", str(self.static), *args]
        with redirect_stdout(out):
            status = cli.main(argv)
        return status, out.getvalue()

    def ok(self, *args, **kwargs):
        status, out = self.cli(*args, **kwargs)
        self.assertEqual(status, 0, out)
        return out

    @staticmethod
    def value(out, key):
        for line in out.splitlines():
            if line.startswith(key + ":"):
                return line[len(key) + 1:]
        raise AssertionError(f"no {key}: line in:\n{out}")

    def start(self, size="126x44"):
        return self.value(self.ok("session", "start", "--size", size), "SESSION")

    def board(self, sid):
        self.ok("run", sid, "--", "./ait", "board")
        self.ok("wait", sid, "--text", "3 children")
        self.ok("wait", sid, "--text", "╔")     # a card holds focus

    def expand(self, sid):
        self.ok("keys", sid, "x")
        self.ok("wait", sid, "--text", EXPANDED)

    def batches(self):
        if not self.staging.is_dir():
            return []
        return sorted(p for p in self.staging.iterdir() if (p / "manifest.json").is_file())

    def save_args(self, sid, scene=SCENE, expect=(EXPANDED, "↳")):
        args = ["recipe", "save", sid, "--scene", scene,
                "--illustrates", "A parent task expanded to show its child cards."]
        for text in expect:
            args += ["--expect", text]
        return args

    def record(self):
        """A clean discovery walk of the example scene, saved as a recipe."""
        sid = self.start()
        self.board(sid)
        self.expand(sid)
        self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT, "--title", "aitasks board")
        out = self.ok(*self.save_args(sid))
        self.ok("session", "stop", sid)
        return Path(self.value(out, "RECIPE_SAVED"))


class CaptureTests(LiveCase):
    def test_real_board_is_captured_staged_and_torn_down(self):
        sid = self.start()
        sess = sessions.load(self.staging, sid)
        project, socket_path = Path(sess.project), Path(sess.socket_path)
        self.assertTrue(socket_path.is_socket())
        self.board(sid)
        self.expand(sid)
        self.assertEqual(self.ok("find", sid, "--text", "↳").count("CELL:"), 3)
        # Every captured row is the full pane width (`capture-pane -N`), or the
        # right part of a row would lose its background in the image.
        from rich.cells import cell_len
        rows = sessions.capture(sess).split("\n")[:44]
        self.assertEqual({cell_len(row) for row in rows}, {126})
        out = self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT,
                      "--title", "aitasks board")

        image = Path(self.value(out, "SHOT"))
        svg = image.read_text(encoding="utf-8")
        text = sx.svg_plain_text(svg)
        for wanted in ("t12 add checkout page", EXPANDED, "↳", "Backlog (2)", "👶"):
            self.assertIn(wanted, text)
        self.assertIn(f"terminal-{SCENE}-", svg)
        self.assertNotIn("9000", text)

        batch = self.staging / self.value(out, "BATCH")
        manifest = json.loads((batch / "manifest.json").read_text())
        (entry,) = manifest["scenes"]
        self.assertEqual(entry["id"], SCENE)
        self.assertEqual(entry["output"], OUTPUT)
        self.assertEqual(entry["sha256"], hashlib.sha256(image.read_bytes()).hexdigest())
        self.assertEqual(entry["destination"], "absent")
        self.assertEqual(entry["markers"], [{"page": "page.md", "text": MARKER}])

        self.ok("session", "stop", sid)
        self.assertEqual(sess.client.run_checked(["list-sessions"]).outcome, "no_server")
        self.assertFalse(project.exists())
        self.assertFalse(socket_path.exists())
        self.assertEqual(self.ok("session", "list"), "")

    def test_destination_state_is_recorded_when_the_image_exists(self):
        existing = self.static / "imgs" / OUTPUT
        existing.write_text("<svg/>")
        sid = self.start()
        self.board(sid)
        out = self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT)
        manifest = json.loads((self.staging / self.value(out, "BATCH") / "manifest.json").read_text())
        self.assertEqual(manifest["scenes"][0]["destination"],
                         {"sha256": hashlib.sha256(b"<svg/>").hexdigest()})
        self.assertEqual(existing.read_text(), "<svg/>")

    def test_a_second_shot_of_a_scene_never_replaces_the_first(self):
        """A batch id names what was reviewed. A recapture goes into a new
        batch; the earlier image and its manifest entry stay as they were."""
        sid = self.start()
        self.board(sid)
        first = self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT)
        first_image = Path(self.value(first, "SHOT"))
        first_batch = self.staging / self.value(first, "BATCH")
        before = first_image.read_bytes()
        manifest_before = (first_batch / "manifest.json").read_bytes()

        self.expand(sid)                                   # the screen changes
        second = self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT)
        second_image = Path(self.value(second, "SHOT"))
        self.assertNotEqual(self.value(second, "BATCH"), first_batch.name)
        self.assertNotEqual(second_image.read_bytes(), before)
        self.assertEqual(first_image.read_bytes(), before)
        self.assertEqual((first_batch / "manifest.json").read_bytes(), manifest_before)

        # A different scene still joins the session's current batch.
        third = self.ok("shot", sid, "--scene", "other_scene", "--output", "other.svg")
        self.assertEqual(self.value(third, "BATCH"), self.value(second, "BATCH"))

        # And the staging primitive itself refuses a rewrite.
        with self.assertRaises(cli.Refused):
            cli.stage(first_batch, self._paths(), SCENE, OUTPUT, "<svg/>")
        self.assertEqual(first_image.read_bytes(), before)

    def _paths(self):
        import types
        return types.SimpleNamespace(staging=self.staging, scenes=self.scenes,
                                     content=self.content, static=self.static)

    def test_a_wait_that_cannot_match_fails_and_stages_nothing(self):
        sid = self.start()
        status, out = self.cli("wait", sid, "--text", "never on screen", "--timeout", "1")
        self.assertEqual(status, 1)
        self.assertIn("FAILED:wait|", out)
        self.assertEqual(self.batches(), [])

    def test_an_output_owned_by_another_scene_is_refused(self):
        shutil.copy(SHIPPED_SCENES / f"{SCENE}.yaml", self.scenes)
        sid = self.start()
        status, out = self.cli("shot", sid, "--scene", "other_scene", "--output", OUTPUT)
        self.assertEqual(status, 1)
        self.assertIn("REFUSED:", out)
        self.assertEqual(self.batches(), [])

    def test_unknown_dataset_starts_nothing(self):
        status, out = self.cli("session", "start", "--dataset", "nowhere")
        self.assertEqual(status, 1)
        self.assertIn("unknown dataset", out)
        self.assertEqual(sessions.list_sessions(self.staging), [])


class IsolationTests(LiveCase):
    def test_the_users_tmux_config_is_never_loaded(self):
        home = self.root / "userhome"
        sentinel = self.root / "sentinel"
        conf = f"run-shell 'touch {sentinel}'\nset -g status on\n"
        (home / ".config" / "tmux").mkdir(parents=True)
        (home / ".tmux.conf").write_text(conf)
        (home / ".config" / "tmux" / "tmux.conf").write_text(conf)
        env = {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}

        with mock.patch.dict(os.environ, env):
            sid = self.start()
            sess = sessions.load(self.staging, sid)
            self.ok("setup", sid, "--", "true")
            _, status = sess.client.run(["show-options", "-gv", "status"])
            self.assertEqual(status.strip(), "off")
            self.assertFalse(sentinel.exists(), "the user's tmux.conf was executed")
            self.ok("session", "stop", sid)

            # Positive control: the same config DOES create the sentinel when a
            # server loads it, so its absence above means something. Raw tmux
            # is correct in tests/ (tests/test_no_raw_tmux.sh scopes its guard).
            control = f"ait_shots_test_ctl_{os.getpid()}"
            def kill_control():
                subprocess.run(["tmux", "-L", control, "kill-server"], capture_output=True)
                for path in Path(sess.socket_path).parent.glob(control):
                    path.unlink()          # tmux leaves the socket file behind

            self.addCleanup(kill_control)
            subprocess.run(["tmux", "-L", control, "-f", str(home / ".tmux.conf"),
                            "new-session", "-d"], capture_output=True, check=True)
            deadline = time.monotonic() + 10
            while not sentinel.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(sentinel.exists(), "control: a loaded config must run")

    def test_the_pane_runs_under_the_pinned_environment(self):
        sid = self.start()
        sess = sessions.load(self.staging, sid)
        out = self.ok("setup", sid, "--", "echo home=$HOME socket=$AITASKS_TMUX_SOCKET "
                                         "tmux=${TMUX:-unset}; git config user.email")
        self.assertIn(f"home={sess.home}", out)
        self.assertIn(f"socket={sess.socket}", out)
        self.assertIn("tmux=unset", out)
        self.assertIn("alex@example.com", out)
        # `printenv`, not `$COLUMNS`: an interactive bash keeps its own
        # unexported COLUMNS; what matters is what a child process inherits.
        self.ok("run", sid, "--", "echo pane-home=$HOME cols=$(printenv COLUMNS || echo unset)")
        self.ok("wait", sid, "--text", f"pane-home={sess.home} cols=unset")

    def test_box_drawing_survives_a_client_without_a_utf8_locale(self):
        """The whole route (tmux client, decode, SVG) under `LC_ALL=C` with
        Python's UTF-8 mode off keeps box-drawing and accented text.

        The `_` rewrite a non-UTF-8 client suffers applies to tmux *format*
        output, not to `capture-pane` (measured on tmux 3.8), and is covered
        by tests/test_tmux_utf8_client_live.sh. The control here is that the
        subprocess really ran without a UTF-8 locale.
        """
        script = self.root / "probe.py"
        script.write_text(f"""
import locale, sys
sys.path.insert(0, {str(REPO_ROOT / "website")!r})
from pathlib import Path
from screenshots import session as sessions, svg_export
staging = Path({str(self.staging)!r})
sess = sessions.start(staging, size=(60, 10))
try:
    sessions.run(sess, "printf 'box \\\\342\\\\224\\\\214\\\\342\\\\224\\\\200\\\\342\\\\224\\\\220 caf\\\\303\\\\251 done\\\\n'")
    sessions.wait(sess, text=" done", timeout=15)
    svg = svg_export.ansi_to_svg(sessions.capture(sess, ansi=True), 60, 10,
                                 title="t", scene_id="locale")
    Path({str(self.root / "locale.svg")!r}).write_text(svg, encoding="utf-8")
    Path({str(self.root / "control.txt")!r}).write_text(
        locale.getpreferredencoding(False) + " utf8_mode=" + str(sys.flags.utf8_mode))
finally:
    sessions.stop(sess)
""")
        env = {**os.environ, "LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0",
               "PYTHONCOERCECLOCALE": "0"}
        env.pop("LC_CTYPE", None)
        proc = subprocess.run([sys.executable, str(script)], env=env, capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = sx.svg_plain_text((self.root / "locale.svg").read_text(encoding="utf-8"))
        self.assertIn("box ┌─┐ café done", text)
        # Control: the lane was what it claims to be.
        control = (self.root / "control.txt").read_text()
        self.assertNotIn("UTF-8", control.upper().split(" UTF8_MODE=")[0])
        self.assertTrue(control.endswith("utf8_mode=0"), control)


class RecipeLifecycleTests(LiveCase):
    def test_record_replay_break_inspect_and_repair(self):
        path = self.record()
        recorded = path.read_bytes()
        self.assertEqual(rc.load(path).steps[-1], ("wait", EXPANDED, None))
        discovery_batches = self.batches()
        self.assertEqual(len(discovery_batches), 1)

        # A second save without --replace is refused and changes nothing.
        sid = self.start()
        self.board(sid)
        self.expand(sid)
        self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT, "--title", "aitasks board")
        status, out = self.cli(*self.save_args(sid))
        self.assertEqual(status, 1)
        self.assertIn("--replace", out)
        self.assertEqual(path.read_bytes(), recorded)
        self.ok("session", "stop", sid)

        # Replay: a fresh session reaches the expected texts; a NEW batch.
        out = self.ok("replay", "--scene", SCENE)
        staged = Path(self.value(out, "STAGED").split("|", 1)[1])
        self.assertIn(EXPANDED, sx.svg_plain_text(staged.read_text(encoding="utf-8")))
        self.assertEqual(len(self.batches()), 3)
        self.assertEqual(self.ok("session", "list"), "")

        # Break it: a wrong key, so the awaited text never comes.
        broken = dataclasses.replace(
            rc.load(path), steps=(("wait", "3 children", None), ("wait", "╔", None),
                                  ("keys", ("z",), None), ("wait", EXPANDED, None)))
        rc.write(broken, self.scenes, replace=True)
        status, out = self.cli("replay", "--scene", SCENE)
        self.assertEqual(status, 1)
        self.assertIn(f"FAILED:{SCENE}|step 4|", out)
        failed_batch = self.staging / self.value(out, "BATCH")
        manifest = json.loads((failed_batch / "manifest.json").read_text())
        self.assertEqual(manifest["scenes"], [])
        self.assertEqual(manifest["failed"][0]["id"], SCENE)
        self.assertFalse((failed_batch / OUTPUT).exists(), "a failed replay staged an image")

        # The session is kept for inspection: its screen can be read ...
        kept = self.value(out, "SESSION")
        self.assertIn("No implementation trails found", self.ok("screen", kept))
        # ... and driven, but nothing done in it can become a recipe, even
        # after steps that worked.
        self.ok("keys", kept, "a")
        self.ok("wait", kept, "--text", "3 children")
        self.ok("shot", kept, "--scene", SCENE, "--output", OUTPUT)
        before = path.read_bytes()
        status, out = self.cli(*self.save_args(kept, expect=("3 children",)), "--replace")
        self.assertEqual(status, 1)
        self.assertIn("replay session", out)
        self.assertEqual(path.read_bytes(), before)
        self.ok("session", "stop", kept)

        # --no-keep leaves no session behind.
        status, out = self.cli("replay", "--scene", SCENE, "--no-keep")
        self.assertEqual(status, 1)
        self.assertNotIn("SESSION:", out)
        self.assertEqual(self.ok("session", "list"), "")

        # Repair: a clean walk in a fresh discovery session, saved with
        # --replace. The ownership is kept, and the result replays.
        sid = self.start()
        self.board(sid)
        self.expand(sid)
        self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT, "--title", "aitasks board")
        self.ok(*self.save_args(sid), "--replace")
        self.ok("session", "stop", sid)
        repaired = rc.load(path)
        self.assertEqual((repaired.id, repaired.output), (SCENE, OUTPUT))
        self.assertIn(("keys", ("x",), None), repaired.steps)
        self.ok("replay", "--scene", SCENE, "--no-keep")

    def test_a_discovery_session_with_a_failed_wait_cannot_be_saved(self):
        sid = self.start()
        self.board(sid)
        status, _ = self.cli("wait", sid, "--text", "never on screen", "--timeout", "1")
        self.assertEqual(status, 1)
        self.expand(sid)                       # the rest of the walk works
        self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT)
        status, out = self.cli(*self.save_args(sid))
        self.assertEqual(status, 1)
        self.assertIn("failed step", out)
        self.assertEqual(list(self.scenes.iterdir()), [])

    def shell_recipe(self, scene, launch, expect, steps=()):
        return rc.Recipe(id=scene, output=f"{scene}.svg", size=(60, 10), dataset="base",
                         launch=launch, expect=tuple(expect), illustrates="A shell line.",
                         steps=tuple(steps))

    def test_expected_texts_must_all_be_on_the_captured_frame(self):
        """FIRST is shown, cleared, then SECOND is shown. Each text is on
        screen at some moment, but never together: the image would show only
        SECOND, so the replay must fail and stage nothing."""
        # The texts are assembled by printf, so the typed command line (which
        # stays on screen) never contains them.
        flicker = ("clear; printf 'FIRST_%s\\n' FRAME_ONLY; sleep 1.5; clear; "
                   "printf 'SECOND_%s\\n' FRAME_ONLY")
        rc.write(self.shell_recipe("flicker", flicker,
                                   ["FIRST_FRAME_ONLY", "SECOND_FRAME_ONLY"]), self.scenes)
        status, out = self.cli("replay", "--scene", "flicker", "--no-keep")
        self.assertEqual(status, 1, out)
        self.assertIn("FAILED:flicker|expect|", out)
        self.assertIn("FIRST_FRAME_ONLY", out)
        batch = self.staging / self.value(out, "BATCH")
        self.assertFalse((batch / "flicker.svg").exists())

        # Control: the same two texts on one frame pass, and are in the image.
        both = "clear; printf 'FIRST_%s\\nSECOND_%s\\n' FRAME_ONLY FRAME_ONLY"
        rc.write(self.shell_recipe("steady", both,
                                   ["FIRST_FRAME_ONLY", "SECOND_FRAME_ONLY"]), self.scenes)
        out = self.ok("replay", "--scene", "steady", "--no-keep")
        text = sx.svg_plain_text(Path(self.value(out, "STAGED").split("|", 1)[1]).read_text())
        self.assertIn("FIRST_FRAME_ONLY", text)
        self.assertIn("SECOND_FRAME_ONLY", text)

    def test_a_recorded_wait_timeout_is_kept_and_honoured(self):
        # Recorded: a discovery wait allowed 120 s lands in the recipe.
        sid = self.start(size="60x10")
        self.ok("run", sid, "--", "printf 'SLOW_STATE\\n'")
        self.ok("wait", sid, "--text", "SLOW_STATE", "--timeout", "120")
        self.ok("shot", sid, "--scene", "slow", "--output", "slow.svg")
        out = self.ok(*self.save_args(sid, scene="slow", expect=("SLOW_STATE",)))
        self.ok("session", "stop", sid)
        self.assertEqual(rc.load(Path(self.value(out, "RECIPE_SAVED"))).steps,
                         (("wait", "SLOW_STATE", 120.0),))

        # Honoured: the text appears after 6 s. The replay default is patched
        # to 4 s here, so only the step's own 20 s budget lets it pass ...
        late = "sleep 6; printf 'LATE_%s\\n' STATE"       # not literal on the command line
        rc.write(self.shell_recipe("late", late, ["LATE_STATE"],
                                   steps=[("wait", "LATE_STATE", 20.0)]), self.scenes)
        self.ok("replay", "--scene", "late", "--no-keep")
        # ... and the same route without it fails (control).
        rc.write(self.shell_recipe("late", late, ["LATE_STATE"],
                                   steps=[("wait", "LATE_STATE", None)]), self.scenes,
                 replace=True)
        status, out = self.cli("replay", "--scene", "late", "--no-keep")
        self.assertEqual(status, 1)
        self.assertIn("FAILED:late|step 1|", out)

    def test_the_shipped_recipe_replays(self):
        out = self.ok("replay", "--scene", SCENE, "--no-keep", scenes=SHIPPED_SCENES)
        staged = Path(self.value(out, "STAGED").split("|", 1)[1])
        text = sx.svg_plain_text(staged.read_text(encoding="utf-8"))
        for wanted in rc.load(SHIPPED_SCENES / f"{SCENE}.yaml").expect:
            self.assertIn(wanted, text)


class SetupContractTests(LiveCase):
    DEMO = "demo_setup"
    SHOWN = "Implementing | 👤 alex"

    def record_with_setup(self):
        sid = self.start()
        self.ok("setup", sid, "--", UPDATE_14)
        self.ok("run", sid, "--", "./ait", "board")
        self.ok("wait", sid, "--text", self.SHOWN)
        self.ok("shot", sid, "--scene", self.DEMO, "--output", "demo_setup.svg")
        out = self.ok(*self.save_args(sid, scene=self.DEMO, expect=(self.SHOWN,)))
        self.ok("session", "stop", sid)
        return Path(self.value(out, "RECIPE_SAVED"))

    def test_setup_is_recorded_replayed_and_is_what_produces_the_state(self):
        path = self.record_with_setup()
        recorded = rc.load(path)
        self.assertEqual(recorded.setup, (UPDATE_14,))
        self.ok("replay", "--scene", self.DEMO, "--no-keep")

        # Control: the same recipe without its setup does not reach the state.
        rc.write(dataclasses.replace(recorded, setup=()), self.scenes, replace=True)
        status, out = self.cli("replay", "--scene", self.DEMO, "--no-keep")
        self.assertEqual(status, 1)
        # It fails at the recorded wait for that very text.
        self.assertIn(f"FAILED:{self.DEMO}|step 1|", out)

        # A failing setup command stops the replay before the TUI is launched.
        rc.write(dataclasses.replace(recorded, setup=("true", "exit 3")), self.scenes,
                 replace=True)
        status, out = self.cli("replay", "--scene", self.DEMO)
        self.assertEqual(status, 1)
        self.assertIn(f"FAILED:{self.DEMO}|setup 2|", out)
        kept = sessions.load(self.staging, self.value(out, "SESSION"))
        self.assertEqual([e["kind"] for e in kept.journal], ["setup", "setup"])
        self.assertFalse(kept.launched)

    def test_state_prepared_outside_the_verbs_is_refused_at_save(self):
        """The agent edits the sample project by hand. The session reaches the
        state, but a fresh replay cannot, so no recipe is written."""
        existing = self.record()
        before = existing.read_bytes()

        sid = self.start()
        project = Path(sessions.load(self.staging, sid).project)
        (project / "aitasks" / "t20_unrecorded_task.md").write_text(
            "---\npriority: high\neffort: low\nissue_type: bug\nstatus: Ready\n"
            "labels: [auth]\nboardcol: next\nboardidx: 5\n---\n\nBy hand.\n")
        self.board(sid)
        self.ok("wait", sid, "--text", "unrecorded task")
        self.ok("shot", sid, "--scene", "by_hand", "--output", "by_hand.svg")
        status, out = self.cli(*self.save_args(sid, scene="by_hand",
                                               expect=("unrecorded task",)))
        self.assertEqual(status, 1)
        self.assertIn("does not replay in a fresh session", out)
        self.assertFalse((self.scenes / "by_hand.yaml").exists())

        # The same holds for --replace: a route that fails its fresh replay
        # leaves the working recipe byte-for-byte.
        self.ok("shot", sid, "--scene", SCENE, "--output", OUTPUT)
        status, out = self.cli(*self.save_args(sid, expect=("unrecorded task",)),
                               "--replace")
        self.assertEqual(status, 1)
        self.assertEqual(existing.read_bytes(), before)

    def test_setup_after_run_is_refused_and_does_not_poison_the_journal(self):
        sid = self.start()
        self.ok("run", sid, "--", "./ait", "board")
        status, out = self.cli("setup", sid, "--", "true")
        self.assertEqual(status, 1)
        self.assertIn("refused after `run`", out)
        status, out = self.cli("run", sid, "--", "./ait", "board")
        self.assertEqual(status, 1)
        journal = sessions.load(self.staging, sid).journal
        self.assertEqual([(e["kind"], e["ok"]) for e in journal], [("launch", True)])

    def test_command_arguments_keep_their_boundaries(self):
        """Several arguments are an argv (quoted back); one is a shell string."""
        sid = self.start(size="60x10")
        out = self.ok("setup", sid, "--", "bash", "-c", 'echo "two  words"')
        self.assertIn("two  words", out)
        out = self.ok("setup", sid, "--", "echo one && echo 'a  b'")
        self.assertIn("one\na  b", out)
        journal = sessions.load(self.staging, sid).journal
        self.assertEqual(journal[0]["command"], """bash -c 'echo "two  words"'""")
        self.assertEqual(journal[1]["command"], "echo one && echo 'a  b'")
        self.ok("run", sid, "--", "printf", "%s\\n", "x  y")
        self.ok("wait", sid, "--text", "x  y")

    def test_a_failing_setup_command_is_reported_and_journaled_as_failed(self):
        sid = self.start()
        status, out = self.cli("setup", sid, "--", "echo oops >&2; exit 4")
        self.assertEqual(status, 1)
        self.assertIn("exited 4", out)
        journal = sessions.load(self.staging, sid).journal
        self.assertEqual([(e["kind"], e["ok"]) for e in journal], [("setup", False)])


if __name__ == "__main__":
    unittest.main()
