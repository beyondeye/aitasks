"""Tests for `preview` and `apply` of the docs screenshot tool (t2278_5).

`apply` turns one reviewed batch into images under `static/imgs/` and
`static-img` shortcodes on the pages. It must apply only what was reviewed and
only where nothing changed since; a scene that cannot be applied is left
exactly as it was. No tmux here: batches are staged with the tool's own
`new_batch` / `stage` over scratch content, static and staging trees.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_apply.py -v
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

from screenshots import cli, markers  # noqa: E402


def marker(scene, alt="Board with the detail dialog", caption="The dialog."):
    cap = f' caption="{caption}"' if caption is not None else ""
    return f'<!-- screenshot: scene={scene} file=aitasks_{scene}.svg alt="{alt}"{cap} -->'


def shortcode(scene, alt="Board with the detail dialog", caption="The dialog."):
    cap = f' caption="{caption}"' if caption is not None else ""
    return f'{{{{< static-img src="imgs/aitasks_{scene}.svg" alt="{alt}"{cap} >}}}}'


def svg(label):
    return f'<svg xmlns="http://www.w3.org/2000/svg"><text>{label}</text></svg>\n'


class ApplyCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.content = self.root / "content"
        self.static = self.root / "static"
        self.staging = self.root / "staging"
        self.scenes = self.root / "scenes"
        for directory in (self.content / "docs", self.static / "imgs", self.staging, self.scenes):
            directory.mkdir(parents=True)

    # -- fixture helpers ------------------------------------------------------

    @property
    def paths(self):
        class Args:
            content, static = str(self.content), str(self.static)
            scenes, staging = str(self.scenes), str(self.staging)
        return cli.Paths(Args)

    def page(self, name, *lines):
        path = self.content / "docs" / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def stage(self, batch, scene, label=None):
        """Stage ``scene`` exactly as a capture does (`cli.stage`)."""
        return cli.stage(batch, self.paths, scene, f"aitasks_{scene}.svg", svg(label or scene))

    def batch(self, *scenes):
        batch = cli.new_batch(self.staging)
        for scene in scenes:
            self.stage(batch, scene)
        return batch

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                status = cli.main(["--content", str(self.content), "--static", str(self.static),
                                   "--scenes", str(self.scenes), "--staging", str(self.staging),
                                   *argv])
            except SystemExit as exc:
                status = exc.code
        return status, out.getvalue()

    def apply(self, batch):
        return self.run_cli("apply", "--batch", batch.name)

    def dest(self, scene):
        return self.static / "imgs" / f"aitasks_{scene}.svg"

    def snapshot(self):
        """Every file under content/ and static/, by relative path."""
        found = {}
        for base in (self.content, self.static):
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    found[path.relative_to(self.root).as_posix()] = path.read_bytes()
        return found


class AppliedTests(ApplyCase):
    def test_image_is_copied_and_the_marker_becomes_the_shortcode(self):
        page = self.page("a.md", "# Title", "", marker("scene_a"), "", "After.")
        batch = self.batch("scene_a")
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertIn("APPLIED:scene_a|aitasks_scene_a.svg|pages=1", out)
        self.assertIn(f"APPLY:applied=1 refused=0 batch={batch.name}", out)
        self.assertEqual(self.dest("scene_a").read_text(encoding="utf-8"), svg("scene_a"))
        self.assertEqual(page.read_text(encoding="utf-8"),
                         "\n".join(["# Title", "", shortcode("scene_a"), "", "After."]) + "\n")

    def test_the_shortcode_is_the_one_the_marker_grammar_renders(self):
        text = marker("scene_a", alt="It's the board", caption=None)
        page = self.page("a.md", text)
        batch = self.batch("scene_a")
        self.assertEqual(self.apply(batch)[0], 0)
        expected = markers.render_static_img(markers.parse_marker(text))
        self.assertEqual(page.read_text(encoding="utf-8"), expected + "\n")

    def test_an_edit_elsewhere_in_the_page_after_capture_survives(self):
        page = self.page("a.md", "Intro.", marker("scene_a"), "Outro.")
        batch = self.batch("scene_a")
        page.write_text("Intro, rewritten during review.\n" + marker("scene_a")
                        + "\nOutro.\nA new paragraph.\n", encoding="utf-8")
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertEqual(page.read_text(encoding="utf-8"),
                         "Intro, rewritten during review.\n" + shortcode("scene_a")
                         + "\nOutro.\nA new paragraph.\n")

    def test_a_scene_shared_by_several_pages_rewrites_each(self):
        pages = [self.page(f"p{n}.md", f"Page {n}", marker("scene_a")) for n in range(3)]
        batch = self.batch("scene_a")
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertIn("pages=3", out)
        for n, page in enumerate(pages):
            self.assertEqual(page.read_text(encoding="utf-8"),
                             f"Page {n}\n{shortcode('scene_a')}\n")

    def test_two_scenes_on_one_page_both_apply(self):
        page = self.page("a.md", marker("scene_a"), "Between.", marker("scene_b"))
        batch = self.batch("scene_a", "scene_b")
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertEqual(page.read_text(encoding="utf-8"),
                         f"{shortcode('scene_a')}\nBetween.\n{shortcode('scene_b')}\n")

    def test_a_scene_without_markers_copies_only_the_image(self):
        page = self.page("a.md", "No marker here.")
        batch = self.batch("scene_a")
        before = page.read_bytes()
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertIn("APPLIED:scene_a|aitasks_scene_a.svg|pages=0", out)
        self.assertTrue(self.dest("scene_a").is_file())
        self.assertEqual(page.read_bytes(), before)

    def test_an_existing_image_in_the_recorded_state_is_replaced(self):
        self.dest("scene_a").write_text(svg("old"), encoding="utf-8")
        self.page("a.md", marker("scene_a"))
        batch = self.batch("scene_a")
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertEqual(self.dest("scene_a").read_text(encoding="utf-8"), svg("scene_a"))

    def test_an_output_in_a_subdirectory_creates_it(self):
        batch = cli.new_batch(self.staging)
        cli.stage(batch, self.paths, "scene_a", "home/board.svg", svg("a"))
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertEqual((self.static / "imgs" / "home" / "board.svg").read_text(), svg("a"))

    def test_a_page_name_with_spaces_or_non_ascii_letters_is_applied(self):
        """A page is named by its author; the image filename alphabet does not
        apply to it. `markers.scan` records such a page, so apply takes it."""
        for name in ("User Guide.md", "Übersicht (neu).md"):
            with self.subTest(name):
                page = self.page(name, "Intro.", marker("scene_a"))
                found, _ = markers.scan(self.content)
                self.assertIn(f"docs/{name}", [m.path for m in found])
                batch = self.batch("scene_a")
                status, out = self.apply(batch)
                self.assertEqual(status, 0, out)
                self.assertIn("APPLIED:scene_a|aitasks_scene_a.svg|pages=1", out)
                self.assertEqual(page.read_text(encoding="utf-8"),
                                 f"Intro.\n{shortcode('scene_a')}\n")
                page.unlink()
                self.dest("scene_a").unlink()

    def test_only_the_named_batch_is_applied(self):
        self.page("a.md", marker("scene_a"))
        reviewed = cli.new_batch(self.staging)
        self.stage(reviewed, "scene_a", "reviewed")
        later = cli.new_batch(self.staging)
        self.stage(later, "scene_a", "captured later, never reviewed")
        status, out = self.apply(reviewed)
        self.assertEqual(status, 0, out)
        self.assertEqual(self.dest("scene_a").read_text(encoding="utf-8"), svg("reviewed"))

    def test_failed_scenes_of_the_batch_are_listed_and_do_not_fail_apply(self):
        self.page("a.md", marker("scene_a"))
        batch = self.batch("scene_a")
        cli.record_failure(batch, "scene_z", "step 2|never appeared")
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertIn("SKIPPED:scene_z|not staged (step 2|never appeared)", out)


class RefusedTests(ApplyCase):
    """Each refusal leaves the scene's image destination and pages untouched."""

    def refuse(self, batch, scene, reason):
        before = self.snapshot()
        status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assertIn(f"REFUSED:{scene}|{reason}", out)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.root.rglob("*.apply-tmp")), [])
        return out

    def one_scene(self):
        self.page("a.md", "Intro.", marker("scene_a"), "Outro.")
        return self.batch("scene_a")

    def test_a_staged_image_changed_after_capture(self):
        batch = self.one_scene()
        (batch / "aitasks_scene_a.svg").write_text(svg("swapped"), encoding="utf-8")
        self.refuse(batch, "scene_a", "image_changed")

    def test_a_staged_image_removed_after_capture(self):
        batch = self.one_scene()
        (batch / "aitasks_scene_a.svg").unlink()
        self.refuse(batch, "scene_a", "image_missing")

    def test_a_destination_created_after_capture(self):
        batch = self.one_scene()
        self.dest("scene_a").write_text(svg("someone else's"), encoding="utf-8")
        self.refuse(batch, "scene_a", "destination_created")

    def test_a_destination_modified_after_capture(self):
        self.dest("scene_a").write_text(svg("old"), encoding="utf-8")
        batch = self.one_scene()
        self.dest("scene_a").write_text(svg("edited since"), encoding="utf-8")
        self.refuse(batch, "scene_a", "destination_modified")

    def test_a_destination_removed_after_capture(self):
        self.dest("scene_a").write_text(svg("old"), encoding="utf-8")
        batch = self.one_scene()
        self.dest("scene_a").unlink()
        self.refuse(batch, "scene_a", "destination_removed")

    def test_a_marker_edited_after_capture(self):
        batch = self.one_scene()
        page = self.content / "docs" / "a.md"
        page.write_text(page.read_text(encoding="utf-8").replace("detail dialog", "lock dialog"),
                        encoding="utf-8")
        self.refuse(batch, "scene_a", "marker_missing:docs/a.md")

    def test_a_marker_removed_with_its_page(self):
        batch = self.one_scene()
        (self.content / "docs" / "a.md").unlink()
        self.refuse(batch, "scene_a", "marker_missing:docs/a.md")

    def test_a_marker_that_now_occurs_twice(self):
        batch = self.one_scene()
        page = self.content / "docs" / "a.md"
        page.write_text(page.read_text(encoding="utf-8") + marker("scene_a") + "\n",
                        encoding="utf-8")
        self.refuse(batch, "scene_a", "marker_ambiguous:docs/a.md")

    def edit_manifest(self, batch, change):
        manifest = cli.read_manifest(batch)
        change(manifest["scenes"][0])
        cli.write_manifest(batch, manifest)

    def test_a_recorded_marker_with_a_forbidden_value_is_refused_not_a_crash(self):
        # A hand-built record: the text is on the page, but no shortcode can
        # be rendered from it.
        bad = '<!-- screenshot: scene=scene_a file=aitasks_scene_a.svg alt="a\\b" -->'
        self.page("a.md", bad)
        batch = self.batch()
        self.stage(batch, "scene_a")
        self.edit_manifest(batch, lambda s: s.__setitem__(
            "markers", [{"page": "docs/a.md", "text": bad}]))
        self.refuse(batch, "scene_a", "marker_invalid:docs/a.md")

    def test_a_recorded_marker_of_another_scene_is_refused(self):
        self.page("a.md", marker("scene_b"))
        batch = self.batch("scene_a")
        self.edit_manifest(batch, lambda s: s.__setitem__(
            "markers", [{"page": "docs/a.md", "text": marker("scene_b")}]))
        self.refuse(batch, "scene_a", "marker_mismatch:docs/a.md")

    def test_a_recorded_page_outside_the_content_tree_is_refused(self):
        outside = self.root / "outside.md"
        outside.write_text(marker("scene_a") + "\n", encoding="utf-8")
        self.page("a.md", "x")
        batch = self.batch("scene_a")
        self.edit_manifest(batch, lambda s: s.__setitem__(
            "markers", [{"page": "../outside.md", "text": marker("scene_a")}]))
        self.refuse(batch, "scene_a", "marker_invalid:../outside.md")
        self.assertEqual(outside.read_text(encoding="utf-8"), marker("scene_a") + "\n")

    def test_no_recorded_page_reaches_outside_the_content_tree(self):
        outside = self.root / "outside.md"
        outside.write_text(marker("scene_a") + "\n", encoding="utf-8")
        (self.content / "docs" / "link.md").symlink_to(outside)
        (self.content / "escape").symlink_to(self.root)
        self.page("a.md", "x")
        for recorded in (str(outside), "docs/../../outside.md", "docs/./../../outside.md",
                         "escape/outside.md", "docs/link.md", "docs//a.md", "docs/a.txt"):
            with self.subTest(recorded):
                batch = self.batch("scene_a")
                self.edit_manifest(batch, lambda s: s.__setitem__(
                    "markers", [{"page": recorded, "text": marker("scene_a")}]))
                self.refuse(batch, "scene_a", f"marker_invalid:{recorded}")
                self.assertEqual(outside.read_text(encoding="utf-8"), marker("scene_a") + "\n")

    def test_a_mixed_batch_applies_the_good_scene_and_refuses_the_other(self):
        good = self.page("good.md", marker("scene_a"))
        bad = self.page("bad.md", marker("scene_b"))
        batch = self.batch("scene_a", "scene_b")
        bad.write_text("The marker was rewritten.\n", encoding="utf-8")
        status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assertIn("APPLIED:scene_a|", out)
        self.assertIn("REFUSED:scene_b|marker_missing:docs/bad.md", out)
        self.assertIn("APPLY:applied=1 refused=1", out)
        self.assertEqual(good.read_text(encoding="utf-8"), shortcode("scene_a") + "\n")
        self.assertTrue(self.dest("scene_a").is_file())
        self.assertFalse(self.dest("scene_b").exists())
        self.assertEqual(bad.read_text(encoding="utf-8"), "The marker was rewritten.\n")


class BatchIdTests(ApplyCase):
    def test_apply_without_a_batch_is_a_usage_error(self):
        self.page("a.md", marker("scene_a"))
        self.batch("scene_a")
        before = self.snapshot()
        status, _ = self.run_cli("apply")
        self.assertEqual(status, 2)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_and_path_like_batch_ids_are_refused(self):
        self.page("a.md", marker("scene_a"))
        batch = self.batch("scene_a")
        before = self.snapshot()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "manifest.json").write_text((batch / "manifest.json").read_text())
        for bad in ("20260101T000000Z-nosuch", "../elsewhere", str(elsewhere), "", "."):
            for verb in ("apply", "preview"):
                status, out = self.run_cli(verb, "--batch", bad)
                self.assertEqual(status, 1, (verb, bad, out))
                self.assertIn("REFUSED:", out)
        self.assertEqual(self.snapshot(), before)

    def test_a_manifest_naming_another_batch_is_refused(self):
        self.page("a.md", marker("scene_a"))
        batch = self.batch("scene_a")
        manifest = cli.read_manifest(batch)
        manifest["batch"] = "some-other-batch"
        cli.write_manifest(batch, manifest)
        status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assertIn("REFUSED:", out)
        self.assertFalse(self.dest("scene_a").exists())


class BetweenValidationAndWritingTests(ApplyCase):
    """A scene is checked again right before ITS writes: what changes while an
    earlier scene of the same batch is being applied is caught."""

    def two_scenes(self):
        self.page_a = self.page("a.md", marker("scene_a"))
        self.page_b = self.page("b.md", marker("scene_b"))
        return self.batch("scene_a", "scene_b")

    def apply_with(self, batch, interfere):
        """Run apply; ``interfere()`` runs once scene_a has been written,
        which is after every scene passed the first validation."""
        real = cli._apply_scene

        def wrapped(scene, batch_dir, paths):
            result = real(scene, batch_dir, paths)
            if scene["id"] == "scene_a":
                interfere()
            return result

        with mock.patch.object(cli, "_apply_scene", wrapped):
            return self.apply(batch)

    def test_control_without_interference_both_scenes_apply(self):
        batch = self.two_scenes()
        status, out = self.apply_with(batch, lambda: None)
        self.assertEqual(status, 0, out)
        self.assertIn("APPLY:applied=2 refused=0", out)

    def test_a_destination_created_meanwhile_is_never_overwritten(self):
        batch = self.two_scenes()
        newer = svg("written by someone else, after validation")
        status, out = self.apply_with(
            batch, lambda: self.dest("scene_b").write_text(newer, encoding="utf-8"))
        self.assertEqual(status, 1, out)
        self.assertIn("APPLIED:scene_a|", out)
        self.assertIn("REFUSED:scene_b|destination_created", out)
        self.assertEqual(self.dest("scene_b").read_text(encoding="utf-8"), newer)
        self.assertEqual(self.page_b.read_text(encoding="utf-8"), marker("scene_b") + "\n")

    def test_a_destination_modified_meanwhile_is_never_overwritten(self):
        self.dest("scene_b").write_text(svg("old"), encoding="utf-8")
        batch = self.two_scenes()
        newer = svg("edited after validation")
        status, out = self.apply_with(
            batch, lambda: self.dest("scene_b").write_text(newer, encoding="utf-8"))
        self.assertEqual(status, 1, out)
        self.assertIn("REFUSED:scene_b|destination_modified", out)
        self.assertEqual(self.dest("scene_b").read_text(encoding="utf-8"), newer)
        self.assertEqual(self.page_b.read_text(encoding="utf-8"), marker("scene_b") + "\n")

    def test_a_staged_image_swapped_meanwhile_is_never_copied(self):
        batch = self.two_scenes()
        status, out = self.apply_with(
            batch, lambda: (batch / "aitasks_scene_b.svg").write_text(
                svg("not the reviewed image"), encoding="utf-8"))
        self.assertEqual(status, 1, out)
        self.assertIn("REFUSED:scene_b|image_changed", out)
        self.assertFalse(self.dest("scene_b").exists())
        self.assertEqual(self.page_b.read_text(encoding="utf-8"), marker("scene_b") + "\n")

    def test_a_marker_edited_meanwhile_is_refused(self):
        batch = self.two_scenes()
        status, out = self.apply_with(
            batch, lambda: self.page_b.write_text("No marker any more.\n", encoding="utf-8"))
        self.assertEqual(status, 1, out)
        self.assertIn("REFUSED:scene_b|marker_missing:docs/b.md", out)
        self.assertFalse(self.dest("scene_b").exists())

    def test_the_bytes_that_were_hashed_are_the_bytes_written(self):
        # The staged file is swapped right after apply read it: the reviewed
        # bytes are written, never the swapped file.
        self.page("a.md", marker("scene_a"))
        batch = self.batch("scene_a")
        staged = batch / "aitasks_scene_a.svg"
        real = cli._page_edits

        def swap_then_continue(scene, paths):
            staged.write_text(svg("swapped after the hash"), encoding="utf-8")
            return real(scene, paths)

        # _page_edits runs after _image_state inside _apply_scene (and in the
        # first validation, where the swap makes phase two the refusing one).
        calls = []

        def once(scene, paths):
            calls.append(1)
            return swap_then_continue(scene, paths) if len(calls) == 2 else real(scene, paths)

        with mock.patch.object(cli, "_page_edits", once):
            status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertEqual(self.dest("scene_a").read_text(encoding="utf-8"), svg("scene_a"))


class WriteFailureTests(ApplyCase):
    """A scene is all or nothing: a failure while its files are being replaced
    restores the ones already replaced."""

    def three_pages(self):
        self.pages = [self.page(f"p{n}.md", f"Page {n}", marker("scene_a")) for n in range(3)]
        return self.batch("scene_a")

    def failing_replace(self, fail_on):
        """`cli._replace` that raises on its ``fail_on``-th call (1-based)."""
        real, calls = cli._replace, []

        def replace(tmp, target):
            calls.append(target)
            if len(calls) == fail_on:
                raise OSError(28, "No space left on device")
            real(tmp, target)
        return replace

    def assert_untouched(self, before, out):
        self.assertIn("REFUSED:scene_a|write_failed:content/docs/p1.md", out)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.root.rglob("*.apply-tmp")), [])

    def test_a_later_page_failure_restores_the_image_and_earlier_pages(self):
        batch = self.three_pages()
        before = self.snapshot()
        # Call 1 = the image, 2 = p0.md, 3 = p1.md.
        with mock.patch.object(cli, "_replace", self.failing_replace(3)):
            status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assert_untouched(before, out)
        self.assertFalse(self.dest("scene_a").exists())

    def test_the_same_failure_restores_an_image_that_existed(self):
        self.dest("scene_a").write_text(svg("old"), encoding="utf-8")
        batch = self.three_pages()
        before = self.snapshot()
        with mock.patch.object(cli, "_replace", self.failing_replace(3)):
            status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assert_untouched(before, out)
        self.assertEqual(self.dest("scene_a").read_text(encoding="utf-8"), svg("old"))

    def test_control_the_same_batch_applies_without_the_failure(self):
        batch = self.three_pages()
        status, out = self.apply(batch)
        self.assertEqual(status, 0, out)
        self.assertIn("pages=3", out)

    def test_a_directory_created_for_the_scene_is_removed_again(self):
        self.page("a.md", "x")
        batch = cli.new_batch(self.staging)
        cli.stage(batch, self.paths, "scene_a", "home/board.svg", svg("a"))
        with mock.patch.object(cli, "_replace", self.failing_replace(1)):
            status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assertIn("REFUSED:scene_a|write_failed:static/imgs/home/board.svg", out)
        self.assertFalse((self.static / "imgs" / "home").exists())

    def test_a_failure_while_preparing_replaces_nothing(self):
        batch = self.three_pages()
        before = self.snapshot()
        real, calls = Path.write_bytes, []

        def write_bytes(path, data):
            if path.name.endswith(".apply-tmp"):
                calls.append(path)
                if len(calls) == 3:
                    raise OSError(28, "No space left on device")
            return real(path, data)

        with mock.patch.object(Path, "write_bytes", write_bytes):
            status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assertIn("REFUSED:scene_a|write_failed:", out)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.root.rglob("*.apply-tmp")), [])

    def test_a_failed_restore_is_reported_as_partial_with_the_paths(self):
        batch = self.three_pages()
        real_replace = os.replace

        def no_restore(src, dst):
            # The restore writes its own temp and replaces; refuse p0.md's.
            if Path(dst).name == "p0.md":
                raise OSError(5, "Input/output error")
            return real_replace(src, dst)

        def replace(tmp, target):
            # Commit through the real os.replace so p0.md IS replaced first.
            if target.name == "p1.md":
                raise OSError(28, "No space left on device")
            real_replace(tmp, target)

        with mock.patch.object(cli, "_replace", replace), \
                mock.patch.object(cli.os, "replace", no_restore):
            status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assertIn("PARTIAL:scene_a|content/docs/p0.md|", out)
        self.assertNotIn("APPLIED:scene_a", out)
        self.assertIn("APPLY:applied=0 refused=1", out)
        # What could be restored was: the image is gone again, p2 never changed.
        self.assertFalse(self.dest("scene_a").exists())
        self.assertEqual(self.pages[2].read_text(encoding="utf-8"),
                         f"Page 2\n{marker('scene_a')}\n")

    def test_a_refused_scene_does_not_stop_the_next_one(self):
        self.three_pages()
        other = self.page("other.md", marker("scene_b"))
        batch = cli.new_batch(self.staging)
        self.stage(batch, "scene_a")
        self.stage(batch, "scene_b")
        with mock.patch.object(cli, "_replace", self.failing_replace(3)):
            status, out = self.apply(batch)
        self.assertEqual(status, 1, out)
        self.assertIn("REFUSED:scene_a|write_failed", out)
        self.assertIn("APPLIED:scene_b|", out)
        self.assertEqual(other.read_text(encoding="utf-8"), shortcode("scene_b") + "\n")


class PreviewTests(ApplyCase):
    def test_one_contact_sheet_for_the_batch_and_nothing_else(self):
        self.dest("scene_b").write_text(svg("old"), encoding="utf-8")
        self.page("a.md", marker("scene_a", alt="Alt <one> & two", caption="Caption A."))
        self.page("b.md", marker("scene_b", alt="Alt B", caption=None))
        batch = self.batch("scene_a", "scene_b", "scene_c")
        cli.record_failure(batch, "scene_z", "step 2|never appeared")
        outside = self.snapshot()
        inside = sorted(p.name for p in batch.iterdir())
        status, out = self.run_cli("preview", "--batch", batch.name)
        self.assertEqual(status, 0, out)
        sheet = batch / "preview.html"
        self.assertIn(f"PREVIEW:{sheet}", out)
        self.assertEqual(sorted(p.name for p in batch.iterdir()), sorted(inside + ["preview.html"]))
        self.assertEqual(self.snapshot(), outside)
        text = sheet.read_text(encoding="utf-8")
        self.assertIn(batch.name, text)
        for expected in ('src="aitasks_scene_a.svg"', 'src="aitasks_scene_b.svg"',
                         "content/docs/a.md", "content/docs/b.md",
                         "Alt &lt;one&gt; &amp; two", "Caption A.", "Alt B",
                         "new file", "replaces the existing image",
                         self.dest("scene_b").as_uri(),
                         "No markers — image only.", "scene_z", "never appeared"):
            self.assertIn(expected, text)
        self.assertNotIn("<one>", text)

    def test_preview_of_a_changed_manifest_is_still_only_that_batch(self):
        self.page("a.md", marker("scene_a"))
        first = self.batch("scene_a")
        second = cli.new_batch(self.staging)
        self.stage(second, "scene_a", "second")
        self.run_cli("preview", "--batch", first.name)
        self.assertFalse((second / "preview.html").exists())
        self.assertNotIn(second.name, (first / "preview.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
