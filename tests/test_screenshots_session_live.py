"""Live tests for the docs-screenshot session primitives (t2278_2, t2278_3).

These boot the REAL `ait board` in an isolated tmux session on the sample
project, through `website/screenshots/cli.py`, exactly as an agent drives it.

Isolation: every session uses its own `-L ait_shots_<id>` socket through
`TmuxClient`, started with `-f /dev/null`. The staging, scenes, content and
static directories are scratch directories, so nothing under `website/` is
read or written (the one exception is the shipped recipes, which are replayed
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

    def start(self, size="126x44", window=None):
        extra = ["--window", window] if window else []
        return self.value(self.ok("session", "start", "--size", size, *extra), "SESSION")

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
        self.assertEqual(rc.load(path).steps[-1], ("wait", EXPANDED, None, None))
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
            rc.load(path), steps=(("wait", "3 children", None, None), ("wait", "╔", None, None),
                                  ("keys", ("z",), None, None), ("wait", EXPANDED, None, None)))
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
        self.assertIn(("keys", ("x",), None, None), repaired.steps)
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
                         (("wait", "SLOW_STATE", 120.0, None),))

        # Honoured: the text appears after 6 s. The replay default is patched
        # to 4 s here, so only the step's own 20 s budget lets it pass ...
        late = "sleep 6; printf 'LATE_%s\\n' STATE"       # not literal on the command line
        rc.write(self.shell_recipe("late", late, ["LATE_STATE"],
                                   steps=[("wait", "LATE_STATE", 20.0, None)]), self.scenes)
        self.ok("replay", "--scene", "late", "--no-keep")
        # ... and the same route without it fails (control).
        rc.write(self.shell_recipe("late", late, ["LATE_STATE"],
                                   steps=[("wait", "LATE_STATE", None, None)]), self.scenes,
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


RENDERERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
             "rsvg-convert")
LAYOUT = "board_layout_annotated"
CARD = "board_card_annotated"


class AnnotatedSceneTests(LiveCase):
    """Crop and overlays (t2278_3), on the real board."""

    def replay_shipped(self, scene, *extra):
        out = self.ok("replay", "--scene", scene, "--no-keep", *extra, scenes=SHIPPED_SCENES)
        return out, Path(self.value(out, "STAGED").split("|", 1)[1])

    def test_the_shipped_annotated_recipes_replay(self):
        _, layout = self.replay_shipped(LAYOUT)
        svg = layout.read_text(encoding="utf-8")
        self.assertIn('<g class="shot-overlay">', svg)
        self.assertEqual(svg.count('class="shot-box"'), 4)
        self.assertEqual(svg.count('class="shot-callout"'), 4)
        self.assertIn('stroke="rgba(255,255,255,0.35)"', svg)     # uncropped: chrome kept

        _, card = self.replay_shipped(CARD)
        svg = card.read_text(encoding="utf-8")
        recipe = rc.load(SHIPPED_SCENES / f"{CARD}.yaml")
        x, y, _, _ = sx.viewbox(svg)
        cx, cy, _, _ = sx_px(recipe.crop["cells"])
        self.assertLessEqual((x, y), (cx - 8, cy - 8))
        self.assertNotIn('stroke="rgba(255,255,255,0.35)"', svg)  # cropped: no chrome
        self.assertEqual(svg.count('class="shot-label"'), len(recipe.overlays))
        self.assertIn("t12 add checkout page", sx.svg_plain_text(svg))

    def test_find_box_shot_and_save_with_crop_and_overlays(self):
        sid = self.start()
        self.board(sid)
        box = self.value(self.ok("find", sid, "--text", "t12 add checkout page", "--box"), "BOX")
        self.assertEqual(box, "2,6,38,6")
        status, out = self.cli("find", sid, "--text", "Ready", "--box")
        self.assertEqual(status, 1, out)
        self.assertIn("times", out)                 # several cards: not unique
        self.ok("shot", sid, "--scene", "card", "--output", "card.svg", "--crop", box,
                "--overlay", "{type: anchor, target: {cells: [3, 10, 37, 1], "
                             "holds: 3 children}, label: Children count}")
        out = self.ok("recipe", "save", sid, "--scene", "card", "--expect", "3 children",
                      "--illustrates", "One card with a label.")
        recipe = rc.load(Path(self.value(out, "RECIPE_SAVED")))
        self.assertEqual(recipe.crop, {"cells": [2, 6, 38, 6]})
        self.assertEqual(recipe.overlays[0]["label"], "Children count")
        # A shot whose overlay leaves the crop is refused before anything is taken.
        before = self.batches()
        status, out = self.cli("shot", sid, "--scene", "card2", "--output", "card2.svg",
                               "--crop", box, "--overlay",
                               "{type: box, target: {cells: [60, 6, 4, 1]}}")
        self.assertEqual(status, 1, out)
        self.assertIn("REFUSED:", out)
        self.assertEqual(self.batches(), before)

    def test_a_holds_text_outside_its_rectangle_fails_the_replay(self):
        text = (SHIPPED_SCENES / f"{LAYOUT}.yaml").read_text(encoding="utf-8")
        (self.scenes / f"{LAYOUT}.yaml").write_text(text, encoding="utf-8")
        # Control first: the unmodified copy passes.
        self.ok("replay", "--scene", LAYOUT, "--no-keep")
        moved = text.replace("holds: aitasks board", "holds: q Quit", 1)
        self.assertNotEqual(moved, text)
        (self.scenes / f"{LAYOUT}.yaml").write_text(moved, encoding="utf-8")
        status, out = self.cli("replay", "--scene", LAYOUT, "--no-keep")
        self.assertEqual(status, 1, out)
        self.assertIn(f"FAILED:{LAYOUT}|overlay|", out)
        self.assertIn("'q Quit' not inside [0, 0, 126, 1]", out)
        batch = self.staging / self.value(out, "BATCH")
        self.assertFalse((batch / "aitasks_board_layout_annotated.svg").exists())

    @unittest.skipUnless(any(shutil.which(r) for r in RENDERERS), "no SVG renderer installed")
    def test_a_cropped_preview_is_produced(self):
        out, card = self.replay_shipped(CARD, "--png")
        png = Path(self.value(out, "PNG").split(" (", 1)[0])
        self.assertTrue(png.is_file(), out)
        self.assertEqual(png.read_bytes()[:4], b"\x89PNG")

    def test_a_requested_preview_that_cannot_be_made_fails_the_verb(self):
        import types

        no_renderer = types.SimpleNamespace(which=lambda name: None)
        with mock.patch.object(sx, "shutil", no_renderer):
            status, out = self.cli("replay", "--scene", CARD, "--no-keep", "--png",
                                   scenes=SHIPPED_SCENES)
        self.assertEqual(status, 1, out)
        self.assertIn("PNG_UNAVAILABLE:", out)
        self.assertNotIn("\nPNG:", "\n" + out)
        # The SVG itself is still staged.
        self.assertTrue(Path(self.value(out, "STAGED").split("|", 1)[1]).is_file())


# --- multi-pane windows (t2278_4) ---------------------------------------------


def tmux_render(sess, window=None):
    """What a REAL tmux client draws for ``window``: the oracle for stitch.py.

    A second private server (started only through ``start_server``, with
    ``-f /dev/null``) opens a pane exactly the window's size, and in it a
    client attaches to the screenshot session; ``capture-pane -e -N`` of that
    pane is tmux's own rendering, borders and their colours included. Returns
    ``(rows, close)``; ``rows`` are decoded ``rich.text.Text`` lines.
    """
    from rich.ansi import AnsiDecoder

    size, _ = sessions.window_layout(sess, window)
    target = sessions.window_id(sess, window)
    sess.client.run(["select-window", "-t", target])
    ref = sessions.TmuxClient(socket_args=["-L", sess.socket + "_ref"])
    pane = sessions.start_server(ref, [
        "new-session", "-d", "-s", "ref", "-x", str(size[0]), "-y", str(size[1]),
        "-P", "-F", "#{pane_id}", "-e", "TERM=tmux-256color",
        "env", "-u", "TMUX", "-u", "COLUMNS", "-u", "LINES", "bash", "--noprofile", "--norc"])

    def close():
        ref.run(["kill-server"])

    try:
        for option in (["set-option", "-g", "status", "off"],
                       ["set-option", "-g", "default-terminal", "tmux-256color"]):
            ref.run(option)
        ref.run(["send-keys", "-t", pane, "-l",
                 f"exec tmux -u -L {sess.socket} attach -t ={sessions.TMUX_SESSION}"])
        ref.run(["send-keys", "-t", pane, "Enter"])
        deadline = time.monotonic() + 10
        previous = None
        while time.monotonic() < deadline:
            time.sleep(0.3)
            _, command = ref.run(["display-message", "-p", "-t", pane,
                                  "#{pane_current_command}"])
            rc_, out = ref.run(["capture-pane", "-p", "-e", "-N", "-t", pane])
            # The shell has exec'd the client, and two captures agree.
            if rc_ == 0 and command.strip() == "tmux" and out == previous:
                return list(AnsiDecoder().decode(out))[:size[1]], close
            previous = out
        raise AssertionError("the reference client never settled")
    except BaseException:
        close()
        raise


def stitch_required(name):
    from screenshots import stitch

    return stitch.REQUIRED_OPTIONS[name]


def is_green(style) -> bool:
    color = style.color if style is not None else None
    return color is not None and (color.name == "green" or color.number == 2)


def style_at(text, x):
    """The style of cell ``x`` of a decoded row (the layouts tested here hold
    one-cell characters only, so a cell is a character offset)."""
    from rich.console import Console

    return text.get_style_at_offset(Console(), x)


class MultiPaneTests(LiveCase):
    """Panes, windows and the stitched window image."""

    def two_panes(self, size="100x20"):
        sid = self.start(size, window="split")
        self.ok("run", sid, "--", "printf 'LEFT_PANE_TEXT\\n'")
        self.ok("wait", sid, "--text", "LEFT_PANE_TEXT")
        self.ok("pane", "split", sid, "--name", "right", "-l", "40", "--",
                "printf 'RIGHT_PANE_TEXT\\n'")
        self.ok("wait", sid, "--pane", "right", "--text", "RIGHT_PANE_TEXT")
        return sid

    def sitrep_layout(self):
        """Agent above, a pane below at 40%, a full-height pane on the right:
        the sitrep window's geometry."""
        sid = self.start("100x30")
        self.ok("run", sid, "--", "printf 'TOP_PANE\\n'")
        self.ok("pane", "split", sid, "--name", "below", "-v", "-l", "40%", "--",
                "printf 'BELOW_PANE\\n'")
        self.ok("pane", "split", sid, "--name", "side", "-l", "40", "--full", "--",
                "printf 'SIDE_PANE\\n'")
        self.ok("wait", sid, "--pane", "side", "--text", "SIDE_PANE")
        self.ok("wait", sid, "--pane", "below", "--text", "BELOW_PANE")
        return sid

    def test_a_two_pane_window_is_one_image_with_both_panes(self):
        sid = self.two_panes()
        out = self.ok("shot", sid, "--scene", "two", "--output", "two.svg", "--window")
        svg = Path(self.value(out, "SHOT")).read_text(encoding="utf-8")
        text = sx.svg_plain_text(svg)
        self.assertIn("LEFT_PANE_TEXT", text)
        self.assertIn("RIGHT_PANE_TEXT", text)
        self.assertIn("│", text)                      # the border between them
        # The whole window, not one pane: 100 columns wide.
        reference = sx.ansi_to_svg("", 100, 20, title="aitasks", scene_id="two")
        self.assertEqual(sx.viewbox(svg), sx.viewbox(reference))

    def test_stitched_borders_match_a_real_tmux_client(self):
        from screenshots import stitch

        for build in (self.two_panes, self.sitrep_layout):
            sid = build()
            sess = sessions.load(self.staging, sid)
            _, panes = sessions.window_layout(sess)
            self.assertEqual(sessions.window_options(sess, panes), stitch.REQUIRED_OPTIONS)
            for active in panes:
                with self.subTest(layout=build.__name__, active=active.id):
                    sess.client.run(["select-pane", "-t", active.id])
                    frame = cli.stable_capture(sess, {"window": None})
                    reference, close = tmux_render(sess)
                    try:
                        self.assertEqual(frame.plain, [r.plain.rstrip() for r in reference])
                        borders = stitch.border_cells(frame.width, frame.height, [
                            stitch.Pane(p.left, p.top, p.width, p.height, p.id == active.id, "")
                            for p in panes])
                        # Non-vacuous: the active pane's border really is green.
                        self.assertTrue(any(g for _, g in borders.values()))
                        self.assertTrue(any(is_green(style_at(reference[y], x))
                                            for (x, y) in borders))
                        for (x, y), (glyph, green) in borders.items():
                            self.assertEqual(reference[y].plain[x], glyph, (x, y))
                            self.assertEqual(is_green(style_at(reference[y], x)), green,
                                             (x, y))
                            self.assertEqual(is_green(style_at(frame.rows[y], x)), green,
                                             (x, y))
                    finally:
                        close()
            self.ok("session", "stop", sid)

    def test_a_pane_is_captured_at_its_current_size(self):
        sid = self.two_panes()
        out = self.ok("screen", sid, "--pane", "main")
        self.assertIn("PANE:59x20|", out)              # 100 - 40 - 1 border
        out = self.ok("shot", sid, "--scene", "left", "--output", "left.svg", "--pane", "main")
        svg = Path(self.value(out, "SHOT")).read_text(encoding="utf-8")
        reference = sx.ansi_to_svg("", 59, 20, title="aitasks", scene_id="left")
        self.assertEqual(sx.viewbox(svg), sx.viewbox(reference))
        self.assertTrue(all(len(row) <= 59 for row in sx.svg_plain_text(svg).splitlines()))
        self.assertNotIn("RIGHT_PANE_TEXT", sx.svg_plain_text(svg))
        # An overlay inside the window but outside the shrunken pane fails ...
        status, out = self.cli("shot", sid, "--scene", "left2", "--output", "left2.svg",
                               "--pane", "main", "--overlay",
                               "{type: box, target: {cells: [62, 0, 10, 1]}}")
        self.assertEqual(status, 1, out)
        self.assertIn("FAILED:overlay|", out)
        self.assertIn("outside the captured 59x20 frame", out)
        # ... and the same rectangle inside the pane passes (control).
        self.ok("shot", sid, "--scene", "left3", "--output", "left3.svg", "--pane", "main",
                "--overlay", "{type: box, target: {cells: [0, 1, 20, 1], "
                             "holds: LEFT_PANE_TEXT}}")

    def test_a_locator_must_match_exactly_one_pane(self):
        sid = self.start("80x12")
        self.ok("run", sid, "--", "true")
        self.ok("window", "new", sid, "--name", "dup", "--role", "one", "--", "true")
        self.ok("window", "new", sid, "--name", "dup", "--role", "two", "--", "true")
        status, out = self.cli("screen", sid, "--pane", "dup.0")
        self.assertEqual(status, 1, out)
        self.assertIn("matches 2 panes", out)
        status, out = self.cli("screen", sid, "--pane", "%0")
        self.assertEqual(status, 1, out)
        self.assertIn("never by tmux id", out)
        self.ok("screen", sid, "--pane", "one")         # control: a role resolves

    def test_a_locator_never_resolves_into_another_session(self):
        """``list-panes -s`` takes a whole-session target ``=lumen:``: a bare
        ``=lumen`` is looked up as a WINDOW name first, and another session
        with a window called ``lumen`` would answer (tmux_gateway.md, 2)."""
        sid = self.start("80x12")
        self.ok("run", sid, "--", "true")
        self.ok("window", "new", sid, "--name", "target", "--role", "mine", "--", "true")
        sess = sessions.load(self.staging, sid)
        rc_, _ = sess.client.run(["new-session", "-d", "-s", "other", "-n", "lumen"])
        self.assertEqual(rc_, 0)
        rc_, _ = sess.client.run(["new-window", "-d", "-t", "=other:", "-n", "target"])
        self.assertEqual(rc_, 0)
        self.assertEqual(sessions.resolve_pane(sess, "target.0"), sess.panes["mine"])

    def test_a_wait_never_mistakes_an_unreadable_pane_for_a_gone_text(self):
        sid = self.start("80x12")
        self.ok("run", sid, "--", "true")
        self.ok("window", "new", sid, "--name", "dup", "--role", "one", "--", "true")
        self.ok("window", "new", sid, "--name", "dup", "--role", "two", "--", "true")
        # An ambiguous locator is a failed step, journaled as one ...
        status, out = self.cli("wait", sid, "--gone", "Loading", "--pane", "dup.0",
                               "--timeout", "2")
        self.assertEqual(status, 1, out)
        self.assertIn("matches 2 panes", out)
        last = sessions.load(self.staging, sid).journal[-1]
        self.assertEqual((last["kind"], last["ok"]), ("wait_gone", False))
        # ... and a pane that does not exist yet proves nothing gone.
        status, out = self.cli("wait", sid, "--gone", "Loading", "--pane", "later.0",
                               "--timeout", "1")
        self.assertEqual(status, 1, out)
        self.assertIn("never went away", out)
        # Control: a readable pane without the text is "gone".
        self.ok("wait", sid, "--gone", "Loading", "--pane", "one", "--timeout", "2")

    def test_border_options_set_on_the_window_or_a_pane_are_refused(self):
        for scope in ("-w", "-p"):
            with self.subTest(scope=scope):
                sid = self.two_panes()
                sess = sessions.load(self.staging, sid)
                # Control: the pinned configuration exports.
                self.ok("shot", sid, "--scene", "ctl", "--output", "ctl.svg", "--window")
                target = (sessions.window_id(sess) if scope == "-w"
                          else sess.panes["right"])
                name, value = (("pane-border-indicators", "colour") if scope == "-w"
                               else ("pane-active-border-style", "fg=red"))
                rc_, _ = sess.client.run(["set-option", scope, "-t", target, name, value])
                self.assertEqual(rc_, 0)
                self.assertEqual(sess.client.run(["show-options", "-gv", name])[1].strip(),
                                 stitch_required(name))      # the global is untouched
                status, out = self.cli("shot", sid, "--scene", "bad", "--output", "bad.svg",
                                       "--window")
                self.assertEqual(status, 1, out)
                self.assertIn(name, out)
                self.ok("session", "stop", sid)

    def test_a_failed_command_send_is_journaled_and_blocks_the_save(self):
        sid = self.two_panes()
        real_run = sessions.TmuxClient.run

        def failing_send(client, args, *a, **k):
            if args[:1] == ["send-keys"] and "-l" in args and "NEVER_TYPED" in args[-1]:
                return 1, ""
            return real_run(client, args, *a, **k)

        with mock.patch.object(sessions.TmuxClient, "run", failing_send):
            status, out = self.cli("pane", "split", sid, "--name", "third", "--target", "right",
                                   "-v", "--", "echo NEVER_TYPED")
        self.assertEqual(status, 1, out)
        sess = sessions.load(self.staging, sid)
        last = sess.journal[-1]
        self.assertEqual((last["kind"], last["ok"], last["name"]), ("pane_split", False, "third"))
        self.assertIn("third", sess.panes)            # the pane exists; it stays addressable
        self.ok("screen", sid, "--pane", "third")
        self.ok("shot", sid, "--scene", "split", "--output", "split.svg", "--window")
        status, out = self.cli("recipe", "save", sid, "--scene", "split", "--expect",
                               "LEFT_PANE_TEXT", "--illustrates", "Two panes.")
        self.assertEqual(status, 1, out)
        self.assertIn("failed step", out)

    def test_a_recipe_with_pane_steps_records_and_replays(self):
        sid = self.two_panes()
        self.ok("shot", sid, "--scene", "split", "--output", "split.svg", "--window")
        out = self.ok("recipe", "save", sid, "--scene", "split", "--expect", "LEFT_PANE_TEXT",
                      "--expect", "RIGHT_PANE_TEXT", "--illustrates", "Two panes.")
        recipe = rc.load(Path(self.value(out, "RECIPE_SAVED")))
        self.assertIn(("pane_split", {"name": "right", "command": "printf 'RIGHT_PANE_TEXT\\n'",
                                      "direction": "h", "size": "40"}, None, None),
                      recipe.steps)
        self.assertIn(("wait", "RIGHT_PANE_TEXT", None, "right"), recipe.steps)
        self.assertEqual(recipe.capture, {"window": "split"})
        self.assertEqual(recipe.window, "split")
        self.ok("session", "stop", sid)
        out = self.ok("replay", "--scene", "split", "--no-keep")
        svg = Path(self.value(out, "STAGED").split("|", 1)[1]).read_text(encoding="utf-8")
        self.assertIn("RIGHT_PANE_TEXT", sx.svg_plain_text(svg))
        self.assertEqual(sessions.list_sessions(self.staging), [])

    def test_stop_leaves_no_server_socket_or_runtime_files(self):
        sid = self.two_panes()
        sess = sessions.load(self.staging, sid)
        tmp, socket_path = Path(sess.tmp), Path(sess.socket_path)
        self.assertTrue((tmp / "run").is_dir())
        self.ok("session", "stop", sid)
        self.assertEqual(sess.client.run_checked(["list-sessions"]).outcome, "no_server")
        self.assertFalse(socket_path.exists())
        self.assertFalse(tmp.exists())


class StandinPathTests(LiveCase):
    """A bare `claude` in a screenshot session is always the stand-in."""

    def setUp(self):
        super().setUp()
        # A decoy `claude` on the DRIVER's PATH: what a user's real agent is.
        self.decoy_dir = self.root / "decoy"
        self.decoy_dir.mkdir()
        self.decoy_log = self.root / "decoy.log"
        decoy = self.decoy_dir / "claude"
        decoy.write_text(f"#!/usr/bin/env bash\necho \"decoy|$TMUX_PANE\" >> {self.decoy_log}\n"
                         "exec sleep 600\n", encoding="utf-8")
        decoy.chmod(0o755)
        patcher = mock.patch.dict(os.environ, {
            "PATH": f"{self.decoy_dir}{os.pathsep}{os.environ.get('PATH', '')}"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def identities(self, sess):
        log = Path(sess.project) / ".standin" / "log"
        lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return {line.split("|")[2]: line for line in lines}

    def wait_for(self, predicate, what, timeout=15.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.2)
        self.fail(f"{what} did not happen within {timeout:g}s")

    def test_panes_created_from_inside_and_from_the_driver_run_the_standin(self):
        sid = self.start("100x20")
        sess = sessions.load(self.staging, sid)
        self.assertEqual(Path(shutil.which("claude")).parent, self.decoy_dir)
        # From inside the session, as a TUI does: an unattached tmux client in
        # the pane creates the window.
        self.ok("run", sid, "--", "tmux -u -L \"$AITASKS_TMUX_SOCKET\" new-window -d -n inner "
                                  "'claude /aitask-pick 14'")
        # From the driver, through the verb.
        self.ok("pane", "split", sid, "--name", "drv", "--", "claude /aitask-pick 12_1")
        sess = sessions.load(self.staging, sid)
        inner = sessions.resolve_pane(sess, "inner.0")
        self.wait_for(lambda: {inner, sess.panes["drv"]} <= set(self.identities(sess)),
                      "both panes logging the stand-in")
        ids = self.identities(sess)
        self.assertTrue(ids[inner].startswith("pick|/aitask-pick 14|"))
        self.assertTrue(ids[sess.panes["drv"]].startswith("pick|/aitask-pick 12_1|"))
        self.assertFalse(self.decoy_log.exists())
        rc_, out = sess.client.run(["show-environment", "-g", "PATH"])
        self.assertEqual(out.strip(), f"PATH={sess.path}")

    def test_desktop_variables_never_reach_the_session(self):
        """A TUI that finds a display opens windows on the user's desktop (the
        board's pick falls back to a terminal emulator)."""
        with mock.patch.dict(os.environ, {"DISPLAY": ":99", "WAYLAND_DISPLAY": "wayland-99"}):
            sid = self.start("80x12")
            sess = sessions.load(self.staging, sid)
            self.ok("run", sid, "--", "echo \"D=[${DISPLAY-unset}] W=[${WAYLAND_DISPLAY-unset}]\"")
            self.ok("wait", sid, "--text", "D=[unset] W=[unset]")
            for name in ("DISPLAY", "WAYLAND_DISPLAY"):
                rc_, out = sess.client.run(["show-environment", "-g", name])
                self.assertNotIn(f"{name}=", out)
        with mock.patch.dict(os.environ, {"DISPLAY": ":99"}):
            sid = self.start("80x12")
            out = self.ok("setup", sid, "--", "echo \"D=[${DISPLAY-unset}]\"")
            self.assertIn("D=[unset]", out)

    def test_desktop_variables_never_reach_a_window_the_framework_creates(self):
        """``new-session`` copies ``update-environment`` variables (DISPLAY,
        WAYLAND_DISPLAY) into the SESSION environment, which a natively created
        window inherits -- as the framework's own launches create them."""
        with mock.patch.dict(os.environ, {"DISPLAY": ":987", "WAYLAND_DISPLAY": "wayland-987"}):
            sid = self.start("80x12")
            sess = sessions.load(self.staging, sid)
            for scope in (["-g"], ["-t", "=lumen"]):
                for name in ("DISPLAY", "WAYLAND_DISPLAY"):
                    _, out = sess.client.run(["show-environment", *scope, name])
                    self.assertNotIn(f"{name}=", out, (scope, name))
            self.assertEqual(sess.client.run(["show-options", "-gv", "update-environment"])[1]
                             .strip(), "")
            # A native window, created by a client whose own env HAS the display.
            probe = Path(sess.tmp) / "native.txt"
            rc_, _ = sess.client.run([
                "new-window", "-d", "-t", "=lumen:", "-n", "native",
                f"sh -c 'echo D=[${{DISPLAY-unset}}] W=[${{WAYLAND_DISPLAY-unset}}] > {probe}'"])
            self.assertEqual(rc_, 0)
            self.wait_for(probe.exists, "the native window's probe")
            self.assertEqual(probe.read_text().strip(), "D=[unset] W=[unset]")

    def test_control_dash_e_alone_does_not_reach_the_pane(self):
        """Why the PATH is pinned on the argv: tmux gives a pane its creating
        client's PATH and ignores ``-e PATH=``."""
        sid = self.start("100x20")
        sess = sessions.load(self.staging, sid)
        self.ok("run", sid, "--", "true")
        rc_, pane = sess.client.run(["split-window", "-d", "-P", "-F", "#{pane_id}",
                                     "-t", sess.pane, "-e", f"PATH={sess.path}",
                                     "bash", "--noprofile", "--norc", "-c",
                                     "claude /aitask-pick 14"])
        self.assertEqual(rc_, 0)
        self.wait_for(self.decoy_log.exists, "the decoy starting")
        self.assertIn(f"decoy|{pane.strip()}", self.decoy_log.read_text(encoding="utf-8"))
        self.assertNotIn(pane.strip(), self.identities(sess))

    def test_a_session_whose_claude_is_not_the_standin_is_refused(self):
        real = sessions.standin_path

        def decoy_first(project, inherited=None):
            return f"{self.decoy_dir}{os.pathsep}{real(project, inherited)}"

        made = []
        real_mkdtemp = sessions.tempfile.mkdtemp

        def mkdtemp(*args, **kwargs):
            made.append(real_mkdtemp(*args, **kwargs))
            return made[-1]

        servers = []
        real_start_server = sessions.start_server

        def start_server(*args, **kwargs):
            servers.append(args)
            return real_start_server(*args, **kwargs)

        with mock.patch.object(sessions, "standin_path", decoy_first), \
                mock.patch.object(sessions.tempfile, "mkdtemp", mkdtemp), \
                mock.patch.object(sessions, "start_server", start_server):
            status, out = self.cli("session", "start", "--size", "80x12")
        self.assertEqual(status, 1, out)
        self.assertIn("refusing the session", out)
        self.assertEqual(servers, [])                   # refused before any server
        self.assertEqual(len(made), 1)
        self.assertFalse(Path(made[0]).exists())        # and nothing left on disk
        self.assertEqual(sessions.list_sessions(self.staging), [])


class AgentsDatasetTests(LiveCase):
    def test_the_real_minimonitor_lists_the_standin_agent(self):
        sid = self.value(self.ok("session", "start", "--size", "126x30", "--dataset", "agents",
                                 "--window", "agent-pick-14"), "SESSION")
        self.ok("run", sid, "--", "claude --model claude-opus-5-5 /aitask-pick 14")
        self.ok("wait", sid, "--text", "Shall I commit the fix?")
        self.ok("pane", "split", sid, "--name", "mini", "-l", "40", "--", "./ait minimonitor")
        self.ok("wait", sid, "--pane", "mini", "--text", "fix login redirect loop",
                "--timeout", "60")
        sess = sessions.load(self.staging, sid)
        log = (Path(sess.project) / ".standin" / "log").read_text(encoding="utf-8")
        self.assertIn(f"|{sess.pane}|", log)
        self.assertEqual(sessions.pane_command(sess), "claude")
        # The session on screen is the invented project's, not the tool's.
        _, name = sess.client.run(["display-message", "-p", "-t", sess.pane,
                                   "#{session_name}"])
        self.assertEqual(name.strip(), "lumen")
        self.ok("wait", sid, "--pane", "mini", "--text", "this agent · lumen")
        # The minimonitor's status server lives in the session's private
        # runtime dir, removed with the session -- never the user's.
        run = Path(sess.tmp) / "run" / "aitasks"
        self.wait_for(lambda: any(run.glob("monitor-*.sock")), "the status server socket")
        user_run = Path(os.environ.get("XDG_RUNTIME_DIR") or "/nonexistent") / "aitasks"
        key = hashlib.sha256(sess.socket_path.encode()).hexdigest()[:16]
        self.assertEqual(list(user_run.glob(f"monitor-{key}-*")), [])

    def wait_for(self, predicate, what, timeout=20.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.2)
        self.fail(f"{what} did not happen within {timeout:g}s")

    def test_the_shipped_multi_pane_recipes_replay(self):
        scenes = ["minimonitor_main_view", "sitrep_window", "ait_ide_startup",
                  "monitor_layout_annotated"]
        pane_environment = sessions.pane_environment

        def fixture_environment(socket, home, python):
            # Recipe setup invokes real gate writers. Keep their lock bases
            # inside the disposable session, with the SAME namespace for setup
            # commands and every pane; each fixture repo gets its own base.
            return {**pane_environment(socket, home, python),
                    "AITASKS_LOCK_DIR": str(home.parent / "locks")}

        with mock.patch.object(cli, "STEP_TIMEOUT", sessions.DEFAULT_TIMEOUT), \
                mock.patch.object(cli, "EXPECT_TIMEOUT", 15.0), \
                mock.patch.object(sessions, "pane_environment", fixture_environment):
            out = self.ok("replay", *[a for s_ in scenes for a in ("--scene", s_)], "--no-keep",
                          scenes=SHIPPED_SCENES)
        staged = {line.split("|")[0][len("STAGED:"):]: Path(line.split("|", 1)[1])
                  for line in out.splitlines() if line.startswith("STAGED:")}
        self.assertEqual(sorted(staged), sorted(scenes))
        layout = staged["monitor_layout_annotated"].read_text(encoding="utf-8")
        self.assertEqual(layout.count('class="shot-callout"'), 5)
        self.assertIn("Worth a test", sx.svg_plain_text(layout))
        self.assertEqual(sessions.list_sessions(self.staging), [])


def sx_px(cells):
    from screenshots import svgpost

    return svgpost.cell_rect_to_px(cells)


if __name__ == "__main__":
    unittest.main()
