#!/usr/bin/env python3
"""Behavioural pins for the sitrep TUI's read views (`ait sitrep tui`, t2211_1).

The fixture store is built ONCE per run through the REAL writer
(`aitask_sitrep_todo.sh` add / set-state / dismiss / retain / retain-raw /
retain-case / upsert-context / situation / qa) inside a scratch git repository,
then copied per test. The writer runs with ``cwd=<root>`` and without
``AITASK_SITREP_DIR`` -- the TUI reads ``<canonical root>/.aitask-sitrep``,
the location every read-side consumer uses.

Groups worth naming:

``PointerTests``
    Store text is agent-written, so the followers re-validate every pointer.
    The symlink-escape refusal carries a negative control: with the realpath
    containment patched out, the same assertion must fail.

``AgeTests`` / ``AgeRefreshTests``
    The store grammar accepts timestamps that are no calendar date
    (``2026-02-31T12:00:00Z``), and the clock seam is syntax-checked only, so
    rendering must never raise; an idle store must still age its labels on the
    poll tick, without reparsing.

``ScrollTests``
    Detail and Q&A-entry screens split a focusable text pane from the links
    list; a long context and a long Q&A body are both readable to the end, and
    the last link reachable, with keys only, in a 100x16 pane.

Run: python3 -m unittest tests.test_sitrep_tui_app
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / ".aitask-scripts"
for _p in (str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sitrep_corpus as C  # noqa: E402
import sitrep_harvest as H  # noqa: E402
import sitrep_todo as st  # noqa: E402
from sitrep_tui import sitrep_tui_app as appmod  # noqa: E402
from sitrep_tui import sitrep_tui_model as model  # noqa: E402
from textual.widgets import OptionList, Static, TextArea  # noqa: E402

WRITER = SCRIPTS / "aitask_sitrep_todo.sh"
SITREP_SH = SCRIPTS / "aitask_sitrep.sh"
NOW = "2026-11-05T12:00:00Z"
HOSTILE = "[bold]x[/] $x [link=y]z"
IMPOSSIBLE = "2026-02-31T12:00:00Z"
SIZE = (100, 16)


def _env(now: str = NOW) -> dict:
    env = dict(os.environ)
    env.pop("AITASK_SITREP_DIR", None)
    env["AITASK_SITREP_NOW"] = now
    env["AIT_SKIP_TERMINAL_CHECK"] = "1"
    return env


def writer(root, *args, stdin: str = "", now: str = NOW) -> str:
    p = subprocess.run([str(WRITER), *args], cwd=str(root), input=stdin,
                       capture_output=True, text=True, env=_env(now), timeout=60)
    if p.returncode != 0:
        raise AssertionError(f"writer {args} exit {p.returncode}: {p.stdout}{p.stderr}")
    return p.stdout.strip()


def _git(root, *args) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _ptr(out: str, prefix: str) -> str:
    line = next(ln for ln in out.splitlines() if ln.startswith(prefix))
    return line[len(prefix):]


def _added(out: str) -> int:
    return int(_ptr(out, "ADDED:c"))


def _context(background: str, sources: list, related: str = "", theme: str = "") -> str:
    lines = [f"- background: {background}", "- origin: agent=agent-pick-10 date=2026-11-01"]
    if theme:
        lines.append(f"- theme: {theme}")
    if sources:
        lines.append("- sources:")
        lines.extend(f"  - {t}: {p}" for t, p in sources)
    if related:
        lines.append(f"- related: {related}")
    return "\n".join(lines) + "\n"


def build_fixture(base: Path) -> dict:
    """The scratch repo + store. Returns the facts the tests assert against."""
    root = base / "repo"
    outside = base / "outside"
    (root / "aitasks").mkdir(parents=True)
    (root / "aiplans").mkdir()
    (root / "docs").mkdir()
    outside.mkdir()
    (root / "aitasks" / "t10_demo.md").write_text("# t10 demo task\nbody\n")
    (root / "aiplans" / "p10_demo.md").write_text("# p10 demo plan\n")
    (root / "docs" / "notes.md").write_text("".join(f"note line {i}\n" for i in range(1, 6)))
    (outside / "secret.txt").write_text("SECRET OUTSIDE THE REPO\n")
    os.symlink(outside / "secret.txt", root / "escape.md")
    _git(root, "init", "-q")
    _git(root, "-c", "user.email=t@example.com", "-c", "user.name=t", "add", "-A")
    _git(root, "-c", "user.email=t@example.com", "-c", "user.name=t",
         "commit", "-qm", "fixture")
    sha = _git(root, "rev-parse", "HEAD")

    passage = _ptr(writer(root, "retain", stdin="line one\nline two\nline three\n"),
                   "RETAINED:")
    raw_out = _ptr(writer(root, "retain-raw", stdin="raw agent output\nmore\n"),
                   "RETAINED_RAW:")
    raw_rel, raw_sha, _n = raw_out.split("|")
    origin = (f"{st.CASE_ORIGIN_HEADER}\ninput={raw_rel}\ninput_sha256={raw_sha}\n")
    writer(root, "retain-case", stdin=origin)
    origin_ptr = _ptr(writer(root, "retain", stdin=origin), "RETAINED:")
    analysis = C.render_analysis("ab" * 8, "cases/x.txt", "review",
                                 [H.Reason("banner_unparsed", "L6", 6, 6)], [], [])
    writer(root, "retain-case", stdin=analysis)
    analysis_ptr = _ptr(writer(root, "retain", stdin=analysis), "RETAINED:")

    ids = {}
    ids["task"] = _added(writer(root, "add", "--kind", "task", "--title", "Harvest parser",
                                "--ref", "t10", "--group", "now"))
    ids["push"] = _added(writer(root, "add", "--kind", "action", "--title", "Push main",
                                "--group", "now", "--derived", "agent"))
    ids["question"] = _added(writer(root, "add", "--kind", "question", "--title",
                                    "Should refresh run?", "--group", "waiting",
                                    "--state", "unknown"))
    ids["watch"] = _added(writer(root, "add", "--kind", "watch", "--title", "CI on sitrep",
                                 "--group", "next"))
    ids["dismissed"] = _added(writer(root, "add", "--kind", "task", "--title",
                                     "Old follow-up", "--group", "next"))
    writer(root, "dismiss", f"c{ids['dismissed']}", "--outcome", "user: duplicate")
    ids["done"] = _added(writer(root, "add", "--kind", "action", "--title", "Deployed",
                                "--group", "next"))
    writer(root, "set-state", f"c{ids['done']}", "done", "--checked-at",
           "2026-11-05T09:00:00Z", "--outcome", "pushed and deployed")
    ids["review"] = _added(writer(root, "add", "--kind", "question", "--title",
                                  "Analyze unparsed agent output", "--group", "now"))
    ids["hostile"] = _added(writer(root, "add", "--kind", "task", "--title", HOSTILE,
                                   "--group", "next"))
    ids["baddate"] = _added(writer(root, "add", "--kind", "watch", "--title", "Odd clock",
                                   "--group", "waiting"))
    writer(root, "set-state", f"c{ids['baddate']}", "open", "--checked-at", IMPOSSIBLE)
    ids["long"] = _added(writer(root, "add", "--kind", "task", "--title",
                                "Long context " + "with a title wider than the pane " * 4,
                                "--group", "next"))

    c1_sources = [
        ("task", "aitasks/t10_demo.md"), ("plan", "aiplans/p10_demo.md"),
        ("file", "docs/notes.md#L3"), ("capture", passage), ("commit", sha),
        ("url", "https://example.com/x"), ("file", "escape.md"),
    ]
    writer(root, "upsert-context", f"c{ids['task']}", stdin=_context(
        "Turns finished-agent output into items.", c1_sources,
        related=f"c{ids['question']}, c{ids['push']}", theme="sitrep"))
    writer(root, "upsert-context", f"c{ids['review']}", stdin=_context(
        "An unparsed capture kept for review.",
        [("capture", passage), ("capture", origin_ptr), ("capture", analysis_ptr)]))
    long_sources = [("file", f"docs/notes.md#L{i}") for i in range(1, 51)]
    writer(root, "upsert-context", f"c{ids['long']}", stdin=_context(
        "Long background. " * 22, long_sources))
    writer(root, "situation", "sitrep", stdin="Harvest is next.\n")
    writer(root, "situation", "board", stdin="Board work is idle.\n")
    writer(root, "qa", "--items", f"c{ids['task']}",
           stdin="Q: why harvest first?\nA: refresh needs its items.\n",
           now="2026-11-05T11:00:00Z")
    writer(root, "qa", "--items", f"c{ids['question']},c{ids['task']}",
           stdin="".join(f"answer line {i} of a long answer\n" for i in range(1, 61)),
           now="2026-11-05T12:00:00Z")
    return {"ids": ids, "sha": sha, "passage": passage, "origin_ptr": origin_ptr,
            "analysis_ptr": analysis_ptr, "raw_rel": raw_rel, "raw_sha": raw_sha}


class _Fixture:
    _template: "tempfile.TemporaryDirectory | None" = None
    facts: dict = {}

    @classmethod
    def template(cls) -> Path:
        if _Fixture._template is None:
            _Fixture._template = tempfile.TemporaryDirectory(prefix="sitrep_tui_fx_")
            _Fixture.facts = build_fixture(Path(_Fixture._template.name))
        return Path(_Fixture._template.name)


def setUpModule():  # noqa: N802
    _Fixture.template()


def tearDownModule():  # noqa: N802
    if _Fixture._template is not None:
        _Fixture._template.cleanup()


class _Case:
    """Per-test copy of the fixture (symlinks kept as symlinks)."""

    def make_copy(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="sitrep_tui_")
        base = Path(self._tmp.name)
        shutil.copytree(_Fixture.template(), base, symlinks=True, dirs_exist_ok=True)
        # The escape symlink points at the TEMPLATE's outside/ -- re-point it
        # at this copy's so each test is self-contained.
        link = base / "repo" / "escape.md"
        link.unlink()
        os.symlink(base / "outside" / "secret.txt", link)
        self.root = str(base / "repo")
        self.store_dir = os.path.join(self.root, ".aitask-sitrep")
        self.ids = _Fixture.facts["ids"]
        self.facts = _Fixture.facts

    def drop_copy(self) -> None:
        self._tmp.cleanup()


# -- the model -------------------------------------------------------------------

class SnapshotTests(_Case, unittest.TestCase):
    def setUp(self):
        self.make_copy()
        self.addCleanup(self.drop_copy)

    def test_groups_hide_closed_slots_until_asked(self):
        snap = model.load_snapshot(self.store_dir)
        self.assertEqual(snap.todo_error, "")
        slots = [s for s, _h, _i in model.group_items(snap.store, False)]
        self.assertEqual(slots, ["now", "next", "waiting"])
        groups = {s: [it.num for it in items]
                  for s, _h, items in model.group_items(snap.store, True)}
        self.assertEqual(groups["done"], [self.ids["done"]])
        self.assertEqual(groups["dismissed"], [self.ids["dismissed"]])
        self.assertIn(self.ids["task"], groups["now"])

    def test_unchanged_digest_skips_the_parse(self):
        snap = model.load_snapshot(self.store_dir)
        with mock.patch.object(st, "parse_todo", wraps=st.parse_todo) as spy:
            self.assertIsNone(model.load_snapshot(self.store_dir, snap.digest))
            self.assertEqual(spy.call_count, 0)
            writer(self.root, "add", "--kind", "task", "--title", "New", "--group", "now")
            again = model.load_snapshot(self.store_dir, snap.digest)
            self.assertEqual(spy.call_count, 1)
        self.assertIsNotNone(again)
        self.assertEqual(len(again.store.items), len(snap.store.items) + 1)

    def test_a_damaged_todo_is_an_error_string_not_an_exception(self):
        Path(self.store_dir, "todo.md").write_text("garbage\n")
        snap = model.load_snapshot(self.store_dir)
        self.assertIsNone(snap.store)
        self.assertIn("todo.md", snap.todo_error)
        self.assertIsNotNone(snap.qa)

    def test_a_never_initialized_store_is_empty(self):
        snap = model.load_snapshot(os.path.join(self.root, "no-store-here"))
        self.assertEqual((snap.todo_error, snap.qa_error), ("", ""))
        self.assertEqual(snap.store.items, {})
        self.assertEqual(snap.qa.entries, [])

    def test_qa_newest_first_and_backlinks(self):
        snap = model.load_snapshot(self.store_dir)
        order = [e.ts for _i, e in model.qa_newest_first(snap.qa)]
        self.assertEqual(order, ["2026-11-05T12:00:00Z", "2026-11-05T11:00:00Z"])
        back = [e.ts for _i, e in model.qa_backlinks(snap.qa, self.ids["question"])]
        self.assertEqual(back, ["2026-11-05T12:00:00Z"])
        self.assertEqual(model.referenced_by(snap.store, self.ids["question"]),
                         [self.ids["task"]])


class AgeTests(unittest.TestCase):
    def test_age_table(self):
        now = model._parse_ts("2026-11-05T12:00:00Z")
        cases = {
            "never": "never",
            "": "never",
            "2026-11-05T11:59:30Z": "just now",
            "2026-11-05T11:55:00Z": "5m ago",
            "2026-11-05T09:00:00Z": "3h ago",
            "2026-11-03T12:00:00Z": "2d ago",
            "2026-11-06T12:00:00Z": "in the future",
            IMPOSSIBLE: f"at {IMPOSSIBLE} (invalid date)",
        }
        for value, want in cases.items():
            with self.subTest(value=value):
                self.assertEqual(model.age_text(value, now), want)

    def test_the_store_grammar_accepts_an_impossible_date(self):
        # The premise of the fallback: the writer's normalizer is syntax-only.
        self.assertEqual(st.normalize_ts(IMPOSSIBLE, True), IMPOSSIBLE)

    def test_resolve_now_never_raises(self):
        for seam in (IMPOSSIBLE, "not-a-time", ""):
            with self.subTest(seam=seam), \
                    mock.patch.dict(os.environ, {"AITASK_SITREP_NOW": seam}):
                got = model.resolve_now()
                self.assertGreater(got.year, 2000)
        with mock.patch.dict(os.environ, {"AITASK_SITREP_NOW": NOW}):
            self.assertEqual(model.resolve_now(), model._parse_ts(NOW))


class PointerTests(_Case, unittest.TestCase):
    def setUp(self):
        self.make_copy()
        self.addCleanup(self.drop_copy)

    def follow(self, stype, ptr, **kw):
        return model.follow_pointer(self.root, self.store_dir, stype, ptr, **kw)

    def test_path_refusals(self):
        for ptr, why in (("../outside/secret.txt", "'..'"),
                         ("docs/../../outside/secret.txt", "'..'"),
                         ("/etc/passwd", "repo-relative"),
                         ("~/x", "repo-relative"),
                         ("docs\\notes.md", "repo-relative"),
                         ("docs/missing.md", "not a file"),
                         ("", "empty")):
            with self.subTest(ptr=ptr):
                with self.assertRaises(model.PointerRefused) as cm:
                    model.safe_repo_path(self.root, ptr)
                self.assertIn(why, str(cm.exception))

    def _assert_symlink_escape_refused(self):
        with self.assertRaises(model.PointerRefused) as cm:
            model.safe_repo_path(self.root, "escape.md")
        self.assertIn("outside the repository", str(cm.exception))

    def test_symlink_escape_is_refused(self):
        self._assert_symlink_escape_refused()
        view = self.follow("file", "escape.md")
        self.assertIn("outside the repository", view.error)
        self.assertNotIn("SECRET", view.text)

    def test_negative_control_the_containment_check_is_what_refuses(self):
        with mock.patch.object(model, "_inside", lambda _root, _path: True):
            with self.assertRaises(AssertionError):
                self._assert_symlink_escape_refused()

    def test_a_path_with_a_fragment_focuses_its_line(self):
        full, a, b = model.safe_repo_path(self.root, "docs/notes.md#L3")
        self.assertEqual((a, b), (3, 3))
        view = self.follow("file", "docs/notes.md#L3")
        self.assertEqual(view.error, "")
        self.assertEqual(view.focus_line, 3)
        self.assertIn("note line 3", view.text)

    def test_task_and_plan(self):
        self.assertIn("t10 demo task", self.follow("task", "aitasks/t10_demo.md").text)
        self.assertIn("p10 demo plan", self.follow("plan", "aiplans/p10_demo.md").text)

    def test_capture_slices_the_retained_lines(self):
        hexname = self.facts["passage"].split("/")[1].split(".")[0]
        view = self.follow("capture", f"sources/{hexname}.txt#L2-L3")
        self.assertEqual(view.text, "line two\nline three")
        self.assertEqual(view.first_line, 2)
        self.assertIn("[CAPTURE]", view.title)
        self.assertIn("Not followed", self.follow("capture", "sources/zz.txt#L1").error)
        self.assertIn("no retained file",
                      self.follow("capture", f"sources/{'0' * 16}.txt#L1").error)

    def test_case_records_are_labelled_only_with_their_trusted_twin(self):
        self.assertEqual(model.capture_label(self.store_dir, self.facts["origin_ptr"]), "CASE")
        self.assertEqual(model.capture_label(self.store_dir, self.facts["analysis_ptr"]),
                         "ANALYSIS")
        os.remove(os.path.join(self.store_dir, "cases",
                               os.path.basename(self.facts["origin_ptr"].split("#")[0])))
        self.assertEqual(model.capture_label(self.store_dir, self.facts["origin_ptr"]),
                         "CAPTURE")

    def test_commit_shows_the_stat(self):
        view = self.follow("commit", self.facts["sha"])
        self.assertEqual(view.error, "")
        self.assertIn("docs/notes.md", view.text)
        self.assertIn("Not followed", self.follow("commit", "--all").error)

    def test_url_is_shown_not_opened(self):
        view = self.follow("url", "https://example.com/x")
        self.assertEqual(view.text, "https://example.com/x")
        self.assertIn("never opened", view.note)

    def _stub_scripts(self) -> Path:
        d = Path(self._tmp.name) / "stub_scripts"
        d.mkdir()
        log = d / "calls.log"
        for name, body in (("aitask_artifact.sh", 'echo "ARTIFACT BODY $*"'),
                           ("aitask_trail_gather.sh", 'echo "CURRENT"')):
            p = d / name
            p.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "{name} $*" >> "{log}"\n{body}\n')
            p.chmod(0o755)
        return d

    def test_trail_and_artifact_argv_and_refusals(self):
        stub = self._stub_scripts()
        log = stub / "calls.log"
        view = self.follow("trail", "art:trail-x", scripts_dir=stub)
        self.assertIn("CURRENT", view.text)
        self.assertIn("ARTIFACT BODY get art:trail-x", view.text)
        self.assertEqual(log.read_text().splitlines(),
                         ["aitask_artifact.sh get art:trail-x",
                          "aitask_trail_gather.sh drift --trail art:trail-x"])
        log.unlink()
        self.assertIn("ARTIFACT BODY get art:a1",
                      self.follow("artifact", "art:a1", scripts_dir=stub).text)
        log.unlink()
        for stype, ptr, why in (("trail", "-rf", "must not start with '-'"),
                                ("artifact", "--out=/tmp/x", "must not start with '-'"),
                                ("trail", "../x", "'..'"),
                                ("artifact", "a b", "one word")):
            with self.subTest(stype=stype, ptr=ptr):
                self.assertIn(why, self.follow(stype, ptr, scripts_dir=stub).error)
        self.assertFalse(log.exists(), "a refused pointer must never reach a CLI")

    def test_a_failing_cli_is_shown_not_raised(self):
        stub = self._stub_scripts()
        (stub / "aitask_artifact.sh").write_text("#!/usr/bin/env bash\necho boom >&2\nexit 3\n")
        view = self.follow("artifact", "art:a1", scripts_dir=stub)
        self.assertIn("exit 3", view.error)
        self.assertIn("boom", view.error)

    def test_case_raw_input_is_verified_before_it_is_shown(self):
        extras = model.case_extras(self.store_dir, self.facts["origin_ptr"])
        self.assertEqual(extras, (self.facts["raw_rel"], self.facts["raw_sha"]))
        self.assertIsNone(model.case_extras(self.store_dir, self.facts["passage"]))
        view = model.follow_raw(self.store_dir, *extras)
        self.assertEqual((view.error, view.text), ("", "raw agent output\nmore\n"))
        raw = Path(self.store_dir, self.facts["raw_rel"])
        raw.chmod(0o644)
        raw.write_text("tampered\n")
        self.assertIn("sha256", model.follow_raw(self.store_dir, *extras).error)

    def test_review_line_names_the_case(self):
        snap = model.load_snapshot(self.store_dir)
        line = model.review_line(self.store_dir, snap.store.contexts[self.ids["review"]])
        self.assertIn(f"Review case {'ab' * 8} (banner_unparsed)", line)
        self.assertEqual(model.review_line(self.store_dir, None), "")


# -- the app ---------------------------------------------------------------------

class _AppCase(_Case, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.make_copy()
        self.addCleanup(self.drop_copy)
        patcher = mock.patch.dict(os.environ, {"AITASK_SITREP_NOW": NOW})
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_app(self, interval: float = 3600.0) -> appmod.SitrepTuiApp:
        return appmod.SitrepTuiApp(self.root, self.store_dir, reload_interval=interval)

    @staticmethod
    def main_list(app) -> OptionList:
        return app.screen_stack[0].query_one("#st-list", OptionList)

    def select(self, app, cid: str) -> None:
        ol = self.main_list(app)
        ol.highlighted = ol.get_option_index(cid)

    @staticmethod
    def label(ol: OptionList, oid: str) -> str:
        return str(ol.get_option(oid).prompt)

    async def open_details(self, app, pilot, num: int):
        self.select(app, f"c{num}")
        await pilot.press("enter")
        await pilot.pause()
        self.assertIsInstance(app.screen, appmod.ItemDetailScreen)
        return app.screen

    async def choose_link(self, app, pilot, oid: str) -> None:
        links = app.screen.query_one(".sp-links", OptionList)
        links.highlighted = links.get_option_index(oid)
        await pilot.press("enter")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()

    async def assert_no_workers(self, app) -> None:
        await app.workers.wait_for_complete()
        self.assertEqual(len(app.workers), 0)


class MainScreenTests(_AppCase):
    async def test_groups_rows_and_the_closed_toggle(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            ol = self.main_list(app)
            ids = [ol.get_option_at_index(i).id for i in range(ol.option_count)]
            self.assertEqual([i for i in ids if i.startswith("hdr:")],
                             ["hdr:now", "hdr:next", "hdr:waiting"])
            self.assertNotIn(f"c{self.ids['done']}", ids)
            self.assertIn("Pick now (3)", self.label(ol, "hdr:now"))
            row = self.label(ol, f"c{self.ids['task']}")
            self.assertIn("task", row)
            self.assertIn("Harvest parser", row)
            self.assertIn(" never ", row)
            # Rendered, not just configured: the long-title row is wider than
            # the pane, and every option still takes exactly one line.
            self.assertGreater(len(self.label(ol, f"c{self.ids['long']}")), SIZE[0])
            self.assertEqual(ol.virtual_size.height, ol.option_count,
                             "rows are one line, cut with an ellipsis")
            self.assertLess(row.index("never"), row.index("Harvest parser"),
                            "the age precedes the title, so truncation spares it")
            self.assertIs(app.focused, ol)
            enter = app.screen.active_bindings.get("enter")
            self.assertIsNotNone(enter)
            self.assertEqual(enter.binding.action, "open_item")
            self.assertTrue(enter.binding.show)
            await pilot.press("d")
            await pilot.pause()
            ids = [ol.get_option_at_index(i).id for i in range(ol.option_count)]
            self.assertIn("hdr:done", ids)
            self.assertIn("hdr:dismissed", ids)
            self.assertIn("pushed and deployed", self.label(ol, f"c{self.ids['done']}"))
            header = str(app.screen_stack[0].query_one("#st-header", Static).content)
            self.assertIn("open in Pick now", header)
            situation = str(app.screen_stack[0].query_one("#st-situation-text", Static).content)
            self.assertIn("#### sitrep", situation)
            self.assertIn("Board work is idle.", situation)
            await self.assert_no_workers(app)

    async def test_hostile_markup_and_an_impossible_date_render_literally(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            ol = self.main_list(app)
            self.assertIn(HOSTILE, self.label(ol, f"c{self.ids['hostile']}"))
            self.assertIn("(invalid date)", self.label(ol, f"c{self.ids['baddate']}"))
            screen = await self.open_details(app, pilot, self.ids["hostile"])
            self.assertIn(HOSTILE, str(screen.query_one("#sd-title", Static).content))
            await pilot.press("escape")
            await pilot.pause()
            screen = await self.open_details(app, pilot, self.ids["baddate"])
            body = str(screen.query_one("#sd-body", Static).content)
            self.assertIn(f"checked: {IMPOSSIBLE} (at {IMPOSSIBLE} (invalid date))", body)
            self.assertTrue(app.is_running)


class DetailTests(_AppCase):
    async def test_details_fields_context_and_links(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            screen = await self.open_details(app, pilot, self.ids["task"])
            body = str(screen.query_one("#sd-body", Static).content)
            for want in ("kind: task", "ref: t10", "checked: never\n",
                         "background: Turns finished-agent",
                         "origin: agent=agent-pick-10 date=2026-11-01", "theme: sitrep"):
                self.assertIn(want, body)
            links = screen.query_one("#sd-links", OptionList)
            labels = [str(links.get_option_at_index(i).prompt)
                      for i in range(links.option_count)]
            self.assertIn(f"capture [CAPTURE]: {self.facts['passage']}", labels)
            self.assertIn("url: https://example.com/x", labels)
            self.assertTrue(any(lb.startswith(f"related c{self.ids['question']}:")
                                for lb in labels))
            self.assertIn("asked about in Q&A 2026-11-05T12:00:00Z", labels)
            self.assertIs(app.focused, links)
            await self.assert_no_workers(app)

    async def test_a_source_opens_the_viewer_and_the_escape_is_refused(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await self.open_details(app, pilot, self.ids["task"])
            await self.choose_link(app, pilot, "src:2")   # file: docs/notes.md#L3
            self.assertIsInstance(app.screen, appmod.PointerViewerScreen)
            area = app.screen.query_one("#pv-text", TextArea)
            self.assertIn("note line 3", area.text)
            self.assertEqual(area.cursor_location[0], 2)
            await pilot.press("escape")
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.ItemDetailScreen)
            await self.choose_link(app, pilot, "src:6")   # file: escape.md
            self.assertIsInstance(app.screen, appmod.PointerViewerScreen)
            note = str(app.screen.query_one("#pv-note", Static).content)
            self.assertIn("outside the repository", note)
            self.assertNotIn("SECRET", app.screen.query_one("#pv-text", TextArea).text)
            await self.assert_no_workers(app)

    async def test_related_and_referenced_by_link_both_ways(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await self.open_details(app, pilot, self.ids["task"])
            await self.choose_link(app, pilot, f"rel:{self.ids['question']}")
            self.assertIsInstance(app.screen, appmod.ItemDetailScreen)
            links = app.screen.query_one("#sd-links", OptionList)
            self.assertIsNotNone(links.get_option(f"ref:{self.ids['task']}"))
            await self.assert_no_workers(app)

    async def test_review_item_offers_the_verified_raw_input(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            screen = await self.open_details(app, pilot, self.ids["review"])
            body = str(screen.query_one("#sd-body", Static).content)
            self.assertIn(f"Review case {'ab' * 8}", body)
            links = screen.query_one("#sd-links", OptionList)
            self.assertIn("[CASE]", str(links.get_option("src:1").prompt))
            await self.choose_link(app, pilot, "raw:1")
            self.assertIsInstance(app.screen, appmod.PointerViewerScreen)
            self.assertEqual(app.screen.query_one("#pv-text", TextArea).text,
                             "raw agent output\nmore\n")
            await self.assert_no_workers(app)


class QaTests(_AppCase):
    async def test_qa_log_entry_item_and_back(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.QaLogScreen)
            ql = app.screen.query_one("#ql-list", OptionList)
            self.assertTrue(str(ql.get_option_at_index(0).prompt)
                            .startswith("2026-11-05T12:00:00Z"))
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.QaEntryScreen)
            links = app.screen.query_one("#qe-links", OptionList)
            links.highlighted = links.get_option_index(f"item:{self.ids['question']}")
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.ItemDetailScreen)
            self.assertIsNotNone(app.screen.query_one("#sd-links", OptionList)
                                 .get_option("qa:1"))
            await self.choose_link(app, pilot, "qa:1")
            self.assertIsInstance(app.screen, appmod.QaEntryScreen)
            await self.assert_no_workers(app)


class QaIdentityTests(_AppCase):
    """Q&A entries have no id; a restore + append reuses a position. A listed
    entry must open as itself, never as whatever now sits at its position."""

    LONG = "answer line 1 of a long answer"

    def restore_and_append(self) -> None:
        out = writer(self.root, "restore", "qa")
        self.assertIn("RESTORED:", out)
        writer(self.root, "qa", "--items", f"c{self.ids['question']}",
               stdin="Replacement answer\n", now="2026-11-05T13:00:00Z")
        log = st.load_qa(self.store_dir)
        # The premise: the listed 12:00 entry's position now holds 13:00.
        self.assertEqual(log.entries[1].ts, "2026-11-05T13:00:00Z")

    def assert_opened_the_listed_entry(self, app) -> None:
        self.assertIsInstance(app.screen, appmod.QaEntryScreen)
        body = str(app.screen.query_one("#qe-body", Static).content)
        self.assertIn(self.LONG, body)
        self.assertNotIn("Replacement answer", body)
        title = str(app.screen.query_one("#qe-title", Static).content)
        self.assertIn("2026-11-05T12:00:00Z", title)
        self.assertIn("no longer in the current log", title)

    async def test_the_log_listing_opens_the_entry_it_showed(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            ql = app.screen.query_one("#ql-list", OptionList)
            self.assertEqual(ql.highlighted_option.id, "qa:1")
            self.restore_and_append()
            await app._poll_store()
            await pilot.pause()
            self.assertEqual(app.qa.entries[1].ts, "2026-11-05T13:00:00Z")
            await pilot.press("enter")
            await pilot.pause()
            self.assert_opened_the_listed_entry(app)

    async def test_an_item_backlink_opens_the_entry_it_showed(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await self.open_details(app, pilot, self.ids["question"])
            self.restore_and_append()
            await app._poll_store()
            await pilot.pause()
            await self.choose_link(app, pilot, "qa:1")
            self.assert_opened_the_listed_entry(app)

    async def test_an_unchanged_entry_carries_no_stale_note(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            title = str(app.screen.query_one("#qe-title", Static).content)
            self.assertNotIn("no longer", title)


class FooterTests(_AppCase):
    """Every browsing screen surfaces its Enter in the footer, and that Enter
    is live only over the links list."""

    def assert_open_shown(self, app) -> None:
        active = app.screen.active_bindings.get("enter")
        self.assertIsNotNone(active)
        self.assertEqual(active.binding.action, "open_link")
        self.assertTrue(active.binding.show)
        self.assertTrue(active.enabled)

    async def test_details_qa_log_and_entry_show_open(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await self.open_details(app, pilot, self.ids["task"])
            self.assert_open_shown(app)
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.QaLogScreen)
            self.assert_open_shown(app)
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.QaEntryScreen)
            self.assert_open_shown(app)
            await self.assert_no_workers(app)

    async def test_enter_over_the_text_pane_falls_through(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            screen = await self.open_details(app, pilot, self.ids["long"])
            await pilot.press("tab")
            await pilot.pause()
            self.assertIs(app.focused, screen.query_one("#sd-text"))
            active = app.screen.active_bindings.get("enter")
            self.assertFalse(active is not None and active.binding.action == "open_link"
                             and active.enabled)
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            self.assertIs(app.screen, screen, "Enter on the text pane opens nothing")
            await self.assert_no_workers(app)


class ReloadTests(_AppCase):
    async def test_a_digest_change_reloads_and_keeps_the_selection(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.select(app, f"c{self.ids['question']}")
            new = _added(writer(self.root, "add", "--kind", "task", "--title", "Brand new",
                                "--group", "now"))
            await app._poll_store()
            await pilot.pause()
            ol = self.main_list(app)
            self.assertIn("Brand new", self.label(ol, f"c{new}"))
            self.assertEqual(ol.highlighted_option.id, f"c{self.ids['question']}")

    async def test_a_vanished_selection_moves_to_the_nearest_row(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            cid = f"c{self.ids['question']}"
            self.select(app, cid)
            pos = app._order.index(cid)
            expected = app._order[pos + 1]
            writer(self.root, "dismiss", cid, "--outcome", "user: gone")
            await app._poll_store()
            await pilot.pause()
            self.assertNotIn(cid, app._order)
            self.assertEqual(self.main_list(app).highlighted_option.id, expected)

    async def test_the_real_timer_tick_picks_up_a_change(self):
        app = self.make_app(interval=0.2)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            new = _added(writer(self.root, "add", "--kind", "task", "--title", "Ticked",
                                "--group", "now"))
            for _ in range(50):
                await pilot.pause(0.1)
                if f"c{new}" in app._order:
                    break
            self.assertIn(f"c{new}", app._order)

    async def test_damage_keeps_the_last_good_view_under_a_banner(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            before = list(app._order)
            Path(self.store_dir, "todo.md").write_text("garbage\n")
            await app._poll_store()
            await pilot.pause()
            banner = app.screen_stack[0].query_one("#st-banner", Static)
            self.assertTrue(banner.has_class("visible"))
            self.assertIn("Store unusable", str(banner.content))
            self.assertIn("Showing the last good view", str(banner.content))
            self.assertEqual(app._order, before)

    async def test_a_store_damaged_before_start_shows_the_banner(self):
        Path(self.store_dir, "todo.md").write_text("garbage\n")
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            banner = app.screen_stack[0].query_one("#st-banner", Static)
            self.assertTrue(banner.has_class("visible"))
            self.assertNotIn("last good view", str(banner.content))
            self.assertEqual(app._order, [])
            header = str(app.screen_stack[0].query_one("#st-header", Static).content)
            self.assertIn("store unusable", header)


class AgeRefreshTests(_AppCase):
    async def test_ages_follow_the_clock_without_a_reparse(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            cid = f"c{self.ids['done']}"
            ol = self.main_list(app)
            self.assertIn("3h ago", self.label(ol, cid))
            self.select(app, cid)
            await pilot.press("enter")
            await pilot.pause()
            body = app.screen.query_one("#sd-body", Static)
            self.assertIn("(3h ago)", str(body.content))
            with mock.patch.dict(os.environ, {"AITASK_SITREP_NOW": "2026-11-05T14:00:00Z"}), \
                    mock.patch.object(st, "parse_todo", wraps=st.parse_todo) as spy:
                await app._poll_store()
                await pilot.pause()
                self.assertEqual(spy.call_count, 0)
            self.assertIn("5h ago", self.label(ol, cid))
            self.assertIn("(5h ago)", str(body.content))
            self.assertEqual(ol.highlighted_option.id, cid)


class ScrollTests(_AppCase):
    async def _scroll_then_last_link(self, app, pilot, text_id: str, links_id: str):
        text = app.screen.query_one(text_id)
        links = app.screen.query_one(links_id, OptionList)
        self.assertIs(app.focused, links)
        await pilot.press("tab")
        await pilot.pause()
        self.assertIs(app.focused, text)
        self.assertGreater(text.max_scroll_y, 0, "the fixture must overflow the pane")
        await pilot.press("end")
        await pilot.pause()
        self.assertEqual(text.scroll_y, text.max_scroll_y)
        self.assertGreater(text.region.height, 0)
        await pilot.press("tab")
        await pilot.pause()
        self.assertIs(app.focused, links)
        await pilot.press("end")
        await pilot.pause()
        last = links.get_option_at_index(links.option_count - 1)
        self.assertEqual(links.highlighted_option.id, last.id)
        self.assertEqual(text.scroll_y, text.max_scroll_y, "the text kept its place")

    async def test_long_context_and_last_source_reachable_by_keys(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await self.open_details(app, pilot, self.ids["long"])
            await self._scroll_then_last_link(app, pilot, "#sd-text", "#sd-links")
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.PointerViewerScreen)
            self.assertIn("docs/notes.md#L50", str(app.screen.query_one("#pv-title",
                                                                        Static).content))
            await self.assert_no_workers(app)

    async def test_long_qa_body_and_its_last_item_reachable_by_keys(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            await pilot.press("enter")    # the newest entry is the long one
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.QaEntryScreen)
            await self._scroll_then_last_link(app, pilot, "#qe-text", "#qe-links")
            await pilot.press("enter")
            await pilot.pause()
            self.assertIsInstance(app.screen, appmod.ItemDetailScreen)


# -- the launcher ----------------------------------------------------------------

class LauncherTests(unittest.TestCase):
    def run_tui(self, *args):
        return subprocess.run([str(SITREP_SH), "tui", *args], capture_output=True,
                              text=True, env=_env(), timeout=60,
                              stdin=subprocess.DEVNULL)

    def test_usage_and_root_errors_exit_before_textual_starts(self):
        p = self.run_tui("--help")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("--root", p.stdout)
        p = self.run_tui("--root", "")
        self.assertEqual(p.returncode, 2, p.stderr)
        p = self.run_tui("--root", "a/../b")
        self.assertEqual(p.returncode, 2, p.stderr)
        p = self.run_tui("--root", "/nonexistent/sitrep/root")
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("ROOT_FAILED:", p.stderr)


if __name__ == "__main__":
    unittest.main()
