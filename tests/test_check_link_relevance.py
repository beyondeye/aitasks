"""Tests for the source-side link-relevance detector (t1759).

`website/check_link_relevance.py` reports internal links whose target page
*exists* but contains none of the subject the link text names -- the class t1707
found by hand and that neither `hugo build` nor `website/check_links.py` can see.

Every assertion runs against a **synthetic fixture content tree** built in a
temporary directory. Never against `website/content/`, whose link counts move
with every docs commit: an acceptance criterion that is a corpus statistic goes
stale the moment someone edits a page.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_check_link_relevance.py -v
"""
import ast
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

import check_link_relevance as clr  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class FixtureSite:
    """A throwaway Hugo-shaped content tree.

    `page("docs/commands/task-management", "body")` writes a leaf page;
    a path ending in `/_index` writes a section index.
    """

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.content = Path(self._tmp.name) / "content"
        self.content.mkdir(parents=True)

    def page(self, rel: str, body: str) -> Path:
        path = self.content / (rel + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    def scan(self):
        return clr.scan(self.content)

    def record_for(self, source: str):
        """The single record extracted from `source` (fails if not exactly one)."""
        matches = [r for r in self.scan().records if r.source == source]
        assert len(matches) == 1, f"expected 1 record in {source}, got {matches}"
        return matches[0]

    def close(self):
        self._tmp.cleanup()


class SiteTestCase(unittest.TestCase):
    def setUp(self):
        self.site = FixtureSite()
        self.addCleanup(self.site.close)

    def assertReported(self, result, source, token):
        hit = [m for m in result.misses if m.source == source and m.token == token]
        self.assertEqual(len(hit), 1, f"expected {source} `{token}` reported; "
                                      f"got {result.misses}")
        return hit[0]

    def assertNotReported(self, result, source, token):
        hit = [m for m in result.misses if m.source == source and m.token == token]
        self.assertEqual(hit, [], f"expected {source} `{token}` NOT reported")


# --- 1-2: the known class -------------------------------------------------
class KnownClassControlTests(SiteTestCase):
    """The t1707 defect class, reconstructed.

    Written before the detector existed (the `known_class_control_first`
    pre-phase mitigation): the detector's ability to catch the class it was
    commissioned for is a precondition, not a claim made afterwards.

    Both cases are load-bearing together. Case 1 alone passes for a detector
    that reports every link; case 2 is what makes it discriminate.
    """

    def setUp(self):
        super().setUp()
        # The real target page: documents other commands, never `ait artifact`.
        self.site.page(
            "docs/commands/task-management",
            "# Task Management\n\n"
            "Use `ait create` to make a task and `ait ls` to list them.\n",
        )
        # A target page that does document it.
        self.site.page(
            "docs/commands/artifacts",
            "# Artifacts\n\n"
            "`ait artifact put` stores a blob under a stable handle.\n",
        )

    def test_dead_end_link_is_reported(self):
        """Case 1 -- the exact t1707 shape: real page, wrong subject."""
        self.site.page(
            "docs/skills/aitask-trail",
            "# Trails\n\n"
            "Trails are stored via "
            '[`ait artifact`]({{< relref "/docs/commands/task-management" >}}).\n',
        )
        result = self.site.scan()

        self.assertEqual(len(result.misses), 1, result.misses)
        miss = result.misses[0]
        self.assertEqual(miss.source, "docs/skills/aitask-trail.md")
        self.assertEqual(miss.line, 3)
        self.assertEqual(miss.token, "ait artifact")
        self.assertEqual(miss.url, "/docs/commands/task-management/")

    def test_same_link_text_against_a_correct_target_is_not_reported(self):
        """Case 2 -- the negative control for case 1."""
        self.site.page(
            "docs/skills/aitask-trail",
            "# Trails\n\n"
            "Trails are stored via "
            '[`ait artifact`]({{< relref "/docs/commands/artifacts" >}}).\n',
        )
        result = self.site.scan()

        self.assertEqual(result.misses, [])
        self.assertEqual(result.hits, 1)

    def test_the_two_fixtures_differ_only_in_the_target(self):
        """Guard the discriminating power of the pair itself.

        If both fixtures ever drift to the same target page, cases 1 and 2 stop
        being a positive/negative pair and start being two spellings of one
        assertion -- which no other test here would notice.
        """
        broken = self.site.page(
            "docs/a",
            '[`ait artifact`]({{< relref "/docs/commands/task-management" >}})\n',
        )
        fixed = self.site.page(
            "docs/b",
            '[`ait artifact`]({{< relref "/docs/commands/artifacts" >}})\n',
        )
        self.assertNotEqual(broken.read_text(), fixed.read_text())
        result = self.site.scan()
        reported = {m.source for m in result.misses}
        self.assertIn("docs/a.md", reported)
        self.assertNotIn("docs/b.md", reported)


# --- 3: stem normalization ------------------------------------------------
class StemNormalizationTests(SiteTestCase):
    """Flags and placeholders must not turn a documented command into a miss.

    The mutant half matters as much as the passing half: normalization that
    narrowed the token so far that nothing could ever miss would pass the first
    assertion alone.
    """

    def setUp(self):
        super().setUp()
        self.site.page(
            "docs/commands/pr-import",
            "# PR import\n\nRun `ait pr-import` to import a pull request.\n",
        )
        self.site.page("docs/commands/empty", "# Nothing\n\nNo commands here.\n")

    def test_flagged_token_hits_the_page_documenting_the_command(self):
        self.site.page(
            "docs/a",
            '[`ait pr-import --list`]({{< relref "/docs/commands/pr-import" >}})\n',
        )
        self.assertNotReported(self.site.scan(), "docs/a.md", "ait pr-import")

    def test_flagged_token_still_misses_an_unrelated_page(self):
        self.site.page(
            "docs/b",
            '[`ait pr-import --list`]({{< relref "/docs/commands/empty" >}})\n',
        )
        self.assertReported(self.site.scan(), "docs/b.md", "ait pr-import")

    def test_placeholders_are_stripped(self):
        self.assertEqual(clr.stem("ait gate pass <task-id> <name>"),
                         "ait gate pass")
        self.assertEqual(clr.stem("/aitask-pick <id>"), "/aitask-pick")
        self.assertEqual(clr.stem("ait pr-import --data-only"), "ait pr-import")


# --- 4: anchor scoping ----------------------------------------------------
class AnchorScopingTests(SiteTestCase):
    """An anchor narrows the search to that section -- proven in both directions."""

    TARGET = (
        "# Reference\n\n"
        "## Task metadata fields\n\n"
        "The `boardidx` field orders rows.\n\n"
        "## Launching\n\n"
        "Start it with `ait board`.\n"
    )

    def setUp(self):
        super().setUp()
        self.site.page("docs/tuis/board/reference", self.TARGET)

    def test_token_present_elsewhere_on_the_page_still_misses(self):
        """`ait board` is on the page, but not in the named section."""
        self.site.page(
            "docs/a",
            '[`ait board`]({{< relref "/docs/tuis/board/reference" >}}'
            "#task-metadata-fields)\n",
        )
        result = self.site.scan()
        miss = self.assertReported(result, "docs/a.md", "ait board")
        self.assertEqual(miss.scope, "#task-metadata-fields")

    def test_token_present_in_the_named_section_hits(self):
        self.site.page(
            "docs/b",
            '[`ait board`]({{< relref "/docs/tuis/board/reference" >}}#launching)\n',
        )
        self.assertNotReported(self.site.scan(), "docs/b.md", "ait board")

    def test_without_an_anchor_the_whole_page_is_searched(self):
        self.site.page(
            "docs/c",
            '[`ait board`]({{< relref "/docs/tuis/board/reference" >}})\n',
        )
        self.assertNotReported(self.site.scan(), "docs/c.md", "ait board")


# --- 5: slugification -----------------------------------------------------
class HeadingSlugTests(SiteTestCase):
    """Hugo does not collapse repeated hyphens; neither may we.

    `## Minimal / non-tmux workflow` is `#minimal--non-tmux-workflow`. Collapsing
    loses the anchor, silently widening every such check to the whole page.
    """

    def test_repeated_hyphens_are_preserved(self):
        self.assertEqual(clr.heading_slug("Minimal / non-tmux workflow"),
                         "minimal--non-tmux-workflow")
        self.assertEqual(clr.heading_slug("Debian / Ubuntu / WSL (.deb)"),
                         "debian--ubuntu--wsl-deb")

    def test_backticks_in_a_heading_are_stripped(self):
        self.assertEqual(clr.heading_slug("Nested fields: `artifacts`"),
                         "nested-fields-artifacts")

    def test_double_hyphen_anchor_resolves_and_is_not_counted_as_missing(self):
        self.site.page(
            "docs/target",
            "# T\n\n## Minimal / non-tmux workflow\n\nUse `ait ide` here.\n",
        )
        self.site.page(
            "docs/a",
            '[`ait ide`]({{< relref "/docs/target" >}}#minimal--non-tmux-workflow)\n',
        )
        result = self.site.scan()
        self.assertEqual(result.counters["anchor_not_found"], 0)
        self.assertNotReported(result, "docs/a.md", "ait ide")


# --- 6: unresolved targets ------------------------------------------------
class UnresolvedTargetTests(SiteTestCase):
    """An unresolved target is counted, never scored as a hit or a miss.

    Folding it into either would let a broken resolver read as a clean sweep --
    the failure mode this whole counter exists to make visible.
    """

    def test_missing_target_is_counted_and_not_scored(self):
        self.site.page(
            "docs/a",
            '[`ait artifact`]({{< relref "/docs/does-not-exist" >}})\n',
        )
        result = self.site.scan()
        self.assertEqual(result.counters["unresolved_target"], 1)
        self.assertEqual(result.counters["checked"], 1)
        self.assertEqual(result.hits, 0)
        self.assertEqual(result.misses, [])

    def test_resolved_and_unresolved_are_tallied_separately(self):
        self.site.page("docs/real", "# Real\n\n`ait artifact` lives here.\n")
        self.site.page(
            "docs/a",
            '[`ait artifact`]({{< relref "/docs/real" >}})\n'
            '[`ait artifact`]({{< relref "/docs/ghost" >}})\n',
        )
        result = self.site.scan()
        self.assertEqual(result.counters["unresolved_target"], 1)
        self.assertEqual(result.hits, 1)
        self.assertEqual(result.misses, [])


# --- 7: hand-written relative paths ---------------------------------------
class RelativePathTests(SiteTestCase):
    """A hand-written path must land on the same page the relref would."""

    def setUp(self):
        super().setUp()
        self.site.page(
            "docs/commands/pr-import",
            "# PR import\n\n## ait pr-import\n\nRun `ait pr-import`.\n",
        )

    def test_relative_path_resolves_like_the_equivalent_relref(self):
        self.site.page(
            "docs/skills/aitask-pr-import",
            "[`ait pr-import`](../../commands/pr-import/#ait-pr-import)\n",
        )
        self.site.page(
            "docs/skills/other",
            '[`ait pr-import`]({{< relref "/docs/commands/pr-import" >}}'
            "#ait-pr-import)\n",
        )
        by_path = self.site.record_for("docs/skills/aitask-pr-import.md")
        by_relref = self.site.record_for("docs/skills/other.md")

        self.assertEqual(by_path.url, by_relref.url)
        self.assertEqual(by_path.anchor, by_relref.anchor)
        self.assertEqual(by_path.status, "ok")
        self.assertEqual(by_path.kind, "path")
        self.assertEqual(by_relref.kind, "relref")

    def test_external_and_bare_fragment_links_are_skipped(self):
        self.site.page(
            "docs/a",
            "[`ait pr-import`](https://example.org/x)\n"
            "[`ait pr-import`](#local-heading)\n",
        )
        self.assertEqual(
            [r for r in self.site.scan().records if r.source == "docs/a.md"], []
        )


# --- 8: coverage boundary -------------------------------------------------
class CoverageBoundaryTests(SiteTestCase):
    """Prose link text is deliberately out of scope; pin it so it stays explicit.

    Decided, not deferred (t1768), on measurement rather than intuition. Over the
    ~620 internal links whose text carries no backticked token, "any content word
    appears on the target" reported 1 link -- vacuous -- and "every content word
    appears" reported 20, or 16 after excusing words present in the target's URL
    or title, almost all generic nouns ('Board documentation', 'Workflows index',
    'installation troubleshooting notes'). No formulation in between carried a
    usable signal. Re-open it with `website/check_link_relevance_history.py`.
    """

    def test_link_text_without_backticks_is_not_checked(self):
        self.site.page("docs/target", "# Target\n\nNothing relevant here.\n")
        self.site.page(
            "docs/a", '[Terminal Setup]({{< relref "/docs/target" >}})\n'
        )
        result = self.site.scan()
        self.assertEqual(result.misses, [])
        self.assertEqual(result.counters["checked"], 0)
        # It is still extracted -- the boundary is on scoring, not on parsing.
        self.assertEqual(len(result.records), 1)


# --- 9-13: relref resolution ----------------------------------------------
class RelrefResolutionTests(SiteTestCase):
    """Hugo resolves a relref by page lookup, not by URL path.

    Each case asserts BOTH that the target resolved and that the record was
    actually relevance-checked. Asserting resolution alone would pass for an
    implementation that resolves the page and then drops the record.
    """

    def setUp(self):
        super().setUp()
        self.site.page(
            "docs/installation/terminal-setup",
            "# Terminal Setup\n\nConfigure `ait ide` here.\n",
        )
        self.site.page(
            "docs/installation/known-issues",
            "# Known Issues\n\nSee `ait doctor` output.\n",
        )
        self.site.page(
            "docs/getting-started", "# Getting Started\n\nRun `ait setup`.\n"
        )
        self.site.page("docs/development/_index", "# Development\n\n`ait test` runs.\n")

    def test_page_relative_relref_from_a_section_index(self):
        """Case 9 -- `{{< relref "terminal-setup" >}}` inside `_index.md`."""
        self.site.page(
            "docs/installation/_index",
            '# Installation\n\n[`ait ide`]({{< relref "terminal-setup" >}})\n',
        )
        result = self.site.scan()
        record = self.site.record_for("docs/installation/_index.md")
        self.assertEqual(record.url, "/docs/installation/terminal-setup/")
        self.assertEqual(record.status, "ok")
        self.assertEqual(result.counters["unresolved_target"], 0)
        self.assertEqual(result.counters["checked"], 1)
        self.assertNotReported(result, "docs/installation/_index.md", "ait ide")

    def test_page_relative_relref_from_a_leaf_page(self):
        """Case 10 -- same form, resolved from a sibling leaf page."""
        self.site.page(
            "docs/installation/pypy",
            '# PyPy\n\n[`ait doctor`]({{< relref "known-issues" >}})\n',
        )
        result = self.site.scan()
        record = self.site.record_for("docs/installation/pypy.md")
        self.assertEqual(record.url, "/docs/installation/known-issues/")
        self.assertEqual(record.status, "ok")
        self.assertEqual(result.counters["unresolved_target"], 0)
        self.assertEqual(result.counters["checked"], 1)

    def test_site_wide_unique_name_fallback_for_a_leaf_page(self):
        """Case 11a -- not directory-relative, but unique across the site."""
        self.site.page(
            "docs/installation/_index",
            '# Installation\n\n[`ait setup`]({{< relref "getting-started" >}})\n',
        )
        result = self.site.scan()
        record = self.site.record_for("docs/installation/_index.md")
        self.assertEqual(record.url, "/docs/getting-started/")
        self.assertEqual(record.status, "ok")
        self.assertNotReported(result, "docs/installation/_index.md", "ait setup")

    def test_site_wide_fallback_finds_a_section_by_directory_name(self):
        """Case 11b -- fails outright if the name index keys on the stem `_index`."""
        self.site.page(
            "docs/commands/_index",
            '# Commands\n\n[`ait test`]({{< relref "development" >}})\n',
        )
        result = self.site.scan()
        record = self.site.record_for("docs/commands/_index.md")
        self.assertEqual(record.url, "/docs/development/")
        self.assertEqual(record.status, "ok")
        self.assertEqual(result.counters["unresolved_target"], 0)

    def test_ambiguous_name_is_reported_not_guessed(self):
        """Case 12 -- two candidates must conflict, never silently pick one."""
        self.site.page("docs/tuis/board/reference", "# Board ref\n")
        self.site.page("docs/tuis/monitor/reference", "# Monitor ref\n")
        self.site.page(
            "docs/workflows/a",
            '[`ait board`]({{< relref "reference" >}})\n',
        )
        result = self.site.scan()
        record = self.site.record_for("docs/workflows/a.md")
        self.assertEqual(record.status, "ambiguous")
        self.assertEqual(result.counters["unresolved_target"], 1)
        self.assertEqual(result.hits, 0)
        self.assertEqual(result.misses, [])

    def test_bare_index_relref_resolves_to_the_own_section(self):
        """Case 13."""
        self.site.page(
            "docs/installation/_index",
            "# Installation\n\nInstall with `ait setup`.\n",
        )
        self.site.page(
            "docs/installation/macos",
            '# macOS\n\n[`ait setup`]({{< relref "_index" >}})\n',
        )
        record = self.site.record_for("docs/installation/macos.md")
        self.assertEqual(record.url, "/docs/installation/")
        self.assertEqual(record.status, "ok")


# --- 14-15: anchor forms --------------------------------------------------
class AnchorFormTests(SiteTestCase):
    """The anchor may live inside the relref argument or be appended after it."""

    TARGET = (
        "# Gates\n\n"
        "## ait gates run\n\nInvoke `ait gates run` to dispatch.\n\n"
        "## Other\n\nUnrelated prose.\n"
    )

    def setUp(self):
        super().setUp()
        self.site.page("docs/commands/gates", self.TARGET)

    def test_inside_and_outside_anchor_forms_agree(self):
        """Case 14 -- both spellings must yield the same target, anchor and verdict."""
        self.site.page(
            "docs/inside",
            '[`ait gates run`]({{< relref "/docs/commands/gates#ait-gates-run" >}})\n',
        )
        self.site.page(
            "docs/outside",
            '[`ait gates run`]({{< relref "/docs/commands/gates" >}}#ait-gates-run)\n',
        )
        inside = self.site.record_for("docs/inside.md")
        outside = self.site.record_for("docs/outside.md")

        self.assertEqual(inside.url, outside.url)
        self.assertEqual(inside.anchor, "ait-gates-run")
        self.assertEqual(outside.anchor, "ait-gates-run")
        self.assertEqual(inside.status, outside.status)

        result = self.site.scan()
        self.assertNotReported(result, "docs/inside.md", "ait gates run")
        self.assertNotReported(result, "docs/outside.md", "ait gates run")

    def test_inside_anchor_actually_scopes_the_check(self):
        """A parsed-but-ignored anchor would pass the agreement test above."""
        self.site.page(
            "docs/a",
            '[`ait gates run`]({{< relref "/docs/commands/gates#other" >}})\n',
        )
        miss = self.assertReported(self.site.scan(), "docs/a.md", "ait gates run")
        self.assertEqual(miss.scope, "#other")

    def test_both_anchor_forms_on_one_link_is_ambiguous(self):
        """Case 15 -- no corpus precedent, so refuse rather than invent one."""
        self.site.page(
            "docs/b",
            '[`ait gates run`]({{< relref "/docs/commands/gates#other" >}}'
            "#ait-gates-run)\n",
        )
        result = self.site.scan()
        record = self.site.record_for("docs/b.md")
        self.assertEqual(record.status, "ambiguous")
        self.assertEqual(result.counters["unresolved_target"], 1)
        self.assertEqual(result.misses, [])


# --- 16: control failure --------------------------------------------------
class ControlFailureTests(SiteTestCase):
    """Any single failing control must fail the CLI -- `any`, never `all`.

    A run whose extractor collapsed while the stem control still passes is
    exactly the silently-stopped-looking case the controls exist to catch. Each
    position is flipped independently so no single control can be the only one
    actually load-bearing.
    """

    CONTROL_NAMES = [
        "extractor captured the control link",
        "relevance check reports a hit",
        "stem normalization strips a flag",
        "anchor scoping narrowed the check",
        "page-relative relref resolved",
        "subject-of-page label discriminates",
    ]

    def _run_cli(self, controls, *extra_args):
        """Run main() over the fixture with `controls`; return (rc, out, err)."""
        self.site.page("docs/x", "# X\n\nnothing\n")
        out, err = io.StringIO(), io.StringIO()
        argv = ["check_link_relevance.py", "--content", str(self.site.content),
                *extra_args]
        with patch.object(clr, "CONTROLS", controls), patch.object(sys, "argv", argv):
            with redirect_stdout(out), redirect_stderr(err):
                rc = clr.main()
        return rc, out.getvalue(), err.getvalue()

    def test_all_controls_true_exits_zero(self):
        controls = [(name, lambda r: True) for name in self.CONTROL_NAMES]
        rc, _, err = self._run_cli(controls)
        self.assertEqual(rc, 0, err)

    def test_each_control_failing_alone_fails_the_cli(self):
        for index, failing in enumerate(self.CONTROL_NAMES):
            with self.subTest(control=failing):
                controls = [
                    (name, (lambda r: False) if i == index else (lambda r: True))
                    for i, name in enumerate(self.CONTROL_NAMES)
                ]
                rc, out, err = self._run_cli(controls)
                self.assertEqual(rc, 1, f"{failing} should have failed the run")
                self.assertIn(failing, err)
                # The passing controls must not be blamed.
                for other in self.CONTROL_NAMES:
                    if other != failing:
                        self.assertNotIn(f"  - {other}", err)

    def test_every_named_control_is_reported_when_all_fail(self):
        controls = [(name, lambda r: False) for name in self.CONTROL_NAMES]
        rc, _, err = self._run_cli(controls)
        self.assertEqual(rc, 1)
        for name in self.CONTROL_NAMES:
            self.assertIn(name, err)

    def test_normal_mode_prints_every_control_verdict_exactly_once(self):
        """The full run's half of the display contract; `--report` is the other.

        Mixed verdicts, so a hard-coded `True` cannot pass, and an exact count, so
        a duplicated or dropped line cannot either. A regression pin: without it,
        a refactor that made `--report` fail closed by bypassing the full-mode
        display would pass every other test here.
        """
        verdicts = {name: index != 0
                    for index, name in enumerate(self.CONTROL_NAMES)}
        controls = [(name, (lambda ok: lambda r: ok)(ok))
                    for name, ok in verdicts.items()]
        rc, out, _ = self._run_cli(controls)
        self.assertEqual(rc, 1)
        lines = out.splitlines()
        for name, ok in verdicts.items():
            self.assertEqual(
                lines.count(f"control       : {name}: {ok}"), 1, name)
        self.assertEqual(
            len([line for line in lines if line.startswith("control")]),
            len(self.CONTROL_NAMES))

    def test_real_control_list_is_wired_and_named(self):
        """The shipped list must be non-empty and carry callables.

        Without this, `CONTROLS = []` would satisfy every test above -- an empty
        control set trivially has no failing member.
        """
        self.assertEqual(len(clr.CONTROLS), len(self.CONTROL_NAMES))
        self.assertEqual([n for n, _ in clr.CONTROLS], self.CONTROL_NAMES)
        for _, predicate in clr.CONTROLS:
            self.assertTrue(callable(predicate))


# --- misses never gate ----------------------------------------------------
class ExitStatusTests(SiteTestCase):
    """Reported links are for triage; only a failed control is an error."""

    def test_reported_misses_do_not_change_the_exit_status(self):
        self.site.page("docs/target", "# Target\n\nUnrelated prose.\n")
        self.site.page(
            "docs/a", '[`ait artifact`]({{< relref "/docs/target" >}})\n'
        )
        out, err = io.StringIO(), io.StringIO()
        argv = ["check_link_relevance.py", "--content", str(self.site.content)]
        controls = [("always ok", lambda r: True)]
        with patch.object(clr, "CONTROLS", controls), patch.object(sys, "argv", argv):
            with redirect_stdout(out), redirect_stderr(err):
                rc = clr.main()
        self.assertEqual(rc, 0)
        self.assertIn("`ait artifact`", out.getvalue())

    def test_labelled_misses_do_not_change_the_exit_status(self):
        """A `[subject-of-page]` record is still a report, never an error."""
        self.site.page("docs/commands/lock", "# Lock\n\nAtomic locking.\n")
        self.site.page(
            "docs/a", '[`aitask_lock.sh`]({{< relref "/docs/commands/lock" >}})\n'
        )
        out, err = io.StringIO(), io.StringIO()
        argv = ["check_link_relevance.py", "--content", str(self.site.content)]
        controls = [("always ok", lambda r: True)]
        with patch.object(clr, "CONTROLS", controls), patch.object(sys, "argv", argv):
            with redirect_stdout(out), redirect_stderr(err):
                rc = clr.main()
        self.assertEqual(rc, 0)
        self.assertIn("[subject-of-page]", out.getvalue())


# --- frontmatter override warning ----------------------------------------
class SlugOverrideWarningTests(SiteTestCase):
    """The filename->URL assumption is guarded, not merely documented."""

    def test_slug_declaration_produces_a_warning(self):
        self.site.page(
            "docs/a", "---\ntitle: A\nslug: elsewhere\n---\n\n# A\n"
        )
        warnings = self.site.scan().warnings
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("docs/a.md", warnings[0])

    def test_clean_tree_warns_nothing(self):
        self.site.page("docs/a", "---\ntitle: A\n---\n\n# A\n")
        self.assertEqual(self.site.scan().warnings, [])


# --- subject-of-page label (t1768) ------------------------------------------
class SubjectOfPageKeyTests(unittest.TestCase):
    """`subject_of_page` in isolation -- each discriminator pinned by a case."""

    def test_extension_is_stripped_before_slugging(self):
        """Invert the order and the key is `aitask-lock-sh`: nothing matches."""
        self.assertIn("lock", clr.subject_keys("aitask_lock.sh"))
        self.assertTrue(
            clr.subject_of_page("aitask_lock.sh", "/docs/commands/lock/"))

    def test_a_final_command_word_is_never_an_extension(self):
        """Only a dotted suffix is an extension -- never a bare last word."""
        self.assertIn("gate-pass", clr.subject_keys("ait gate pass"))
        self.assertFalse(
            clr.subject_of_page("ait gate pass", "/docs/commands/gates/"))
        # `sh` IS in the extension set: stripping it as a bare word would turn
        # `ait lock sh` into a `lock` key and label it.
        self.assertFalse(
            clr.subject_of_page("ait lock sh", "/docs/commands/lock/"))

    def test_framework_prefix_is_dropped(self):
        self.assertTrue(clr.subject_of_page("ait board", "/docs/tuis/board/"))
        self.assertTrue(clr.subject_of_page(
            "/aitask-pick", "/docs/skills/aitask-pick/parallel-admission/"))

    def test_a_segment_sub_word_does_not_match(self):
        """The refinement itself: `board-stats` is not the `board` page."""
        self.assertFalse(
            clr.subject_of_page("ait board", "/docs/commands/board-stats/"))
        self.assertFalse(clr.subject_of_page(
            "ait setup", "/docs/installation/terminal-setup/"))

    def test_a_substring_does_not_match(self):
        """Vacuous under segment matching -- it can only fail if matching
        regresses to substrings (`tools` contains `ls`)."""
        self.assertFalse(clr.subject_of_page("ait ls", "/docs/tools/"))

    def test_section_directories_are_not_subjects(self):
        self.assertFalse(
            clr.subject_of_page("ait commands", "/docs/commands/lock/"))
        self.assertFalse(clr.subject_of_page("ait docs", "/docs/commands/lock/"))

    def test_the_t1707_shape_does_not_match(self):
        self.assertFalse(clr.subject_of_page(
            "ait artifact", "/docs/commands/task-management/"))
        self.assertFalse(clr.subject_of_page(
            "ait artifact", "/docs/workflows/implementation-trails/"))


class SubjectOfPageLabelTests(SiteTestCase):
    """The label on real `scan()` output: reported, tagged, counted -- never hidden."""

    def setUp(self):
        super().setUp()
        # A page about `lock` that never repeats the script's name.
        self.site.page(
            "docs/commands/lock",
            "# Lock\n\nAtomic task locking.\n\n## Usage\n\nRun it.\n",
        )

    def test_labelled_miss_is_still_reported(self):
        self.site.page(
            "docs/a", '[`aitask_lock.sh`]({{< relref "/docs/commands/lock" >}})\n'
        )
        result = self.site.scan()
        miss = self.assertReported(result, "docs/a.md", "aitask_lock.sh")
        self.assertTrue(miss.subject)
        self.assertEqual(result.counters["subject_of_page"], 1)

    def test_anchored_miss_is_never_labelled(self):
        """Same token, same page: only the anchor differs, and only the label."""
        self.site.page(
            "docs/a", '[`aitask_lock.sh`]({{< relref "/docs/commands/lock" >}})\n'
        )
        self.site.page(
            "docs/b",
            '[`aitask_lock.sh`]({{< relref "/docs/commands/lock" >}}#usage)\n',
        )
        result = self.site.scan()
        self.assertTrue(
            self.assertReported(result, "docs/a.md", "aitask_lock.sh").subject)
        self.assertFalse(
            self.assertReported(result, "docs/b.md", "aitask_lock.sh").subject)
        self.assertEqual(result.counters["subject_of_page"], 1)

    def test_known_class_miss_is_not_labelled(self):
        """The t1707 case-1 fixture, reproduced: still a miss, and unlabelled."""
        self.site.page(
            "docs/commands/task-management",
            "# Task Management\n\n"
            "Use `ait create` to make a task and `ait ls` to list them.\n",
        )
        self.site.page(
            "docs/skills/aitask-trail",
            "# Trails\n\nTrails are stored via "
            '[`ait artifact`]({{< relref "/docs/commands/task-management" >}}).\n',
        )
        result = self.site.scan()
        miss = self.assertReported(
            result, "docs/skills/aitask-trail.md", "ait artifact")
        self.assertFalse(miss.subject)
        self.assertEqual(result.counters["subject_of_page"], 0)

    def test_counter_does_not_fire_for_an_unrelated_target(self):
        self.site.page("docs/target", "# Target\n\nUnrelated prose.\n")
        self.site.page(
            "docs/a", '[`ait artifact`]({{< relref "/docs/target" >}})\n'
        )
        result = self.site.scan()
        self.assertReported(result, "docs/a.md", "ait artifact")
        self.assertEqual(result.counters["subject_of_page"], 0)

    def test_base_rate_counts_hits_as_well_as_misses(self):
        """The base rate covers every page-scoped scoring, so a hit raises it."""
        self.site.page("docs/commands/grep", "# Grep\n\nRun `ait grep` here.\n")
        self.site.page(
            "docs/a", '[`ait grep`]({{< relref "/docs/commands/grep" >}})\n'
        )
        result = self.site.scan()
        self.assertEqual(result.misses, [])
        self.assertEqual(result.counters["subject_base_matches"], 1)
        self.assertEqual(result.counters["subject_base_total"], 1)

    def test_control_passes_on_a_corpus_with_nothing_to_label(self):
        """The control is a probe, so a corpus with no labelled miss still passes."""
        self.site.page(
            "docs/a", '[`ait artifact`]({{< relref "/docs/commands/lock" >}})\n'
        )
        result = self.site.scan()
        self.assertEqual(result.counters["subject_of_page"], 0)
        predicate = dict(clr.CONTROLS)["subject-of-page label discriminates"]
        self.assertTrue(predicate(result))


class SubjectOfPageOutputTests(SiteTestCase):
    """The record line and the summary line are load-bearing; pin their shape."""

    def test_unlabelled_records_print_first_and_the_base_rate_is_shown(self):
        self.site.page("docs/commands/lock", "# Lock\n\nAtomic.\n")
        self.site.page("docs/target", "# Target\n\nUnrelated.\n")
        # Source order puts the labelled record first; output must not.
        self.site.page(
            "docs/a", '[`aitask_lock.sh`]({{< relref "/docs/commands/lock" >}})\n'
        )
        self.site.page(
            "docs/z", '[`ait artifact`]({{< relref "/docs/target" >}})\n'
        )
        out, err = io.StringIO(), io.StringIO()
        argv = ["check_link_relevance.py", "--content", str(self.site.content)]
        controls = [("always ok", lambda r: True)]
        with patch.object(clr, "CONTROLS", controls), patch.object(sys, "argv", argv):
            with redirect_stdout(out), redirect_stderr(err):
                rc = clr.main()
        self.assertEqual(rc, 0)
        records = [l for l in out.getvalue().splitlines() if "  ->  " in l]
        self.assertEqual(records, [
            "docs/z.md:1  `ait artifact`  ->  /docs/target/ [page]",
            "docs/a.md:1  `aitask_lock.sh`  ->  /docs/commands/lock/ [page]"
            "  [subject-of-page]",
        ])
        self.assertIn(
            "subject-of-page: 1  (label matches 1 of 2 page-scoped token links)",
            out.getvalue(),
        )


class SubjectProbeControlTests(unittest.TestCase):
    """The probe checks both directions, so neither failure mode passes it."""

    def test_probe_passes_against_the_shipped_implementation(self):
        self.assertTrue(clr._probe_subject_classification())

    def test_probe_fails_if_everything_is_labelled(self):
        with patch.object(clr, "subject_of_page", lambda *_: True):
            self.assertFalse(clr._probe_subject_classification())

    def test_probe_fails_if_nothing_is_labelled(self):
        with patch.object(clr, "subject_of_page", lambda *_: False):
            self.assertFalse(clr._probe_subject_classification())


class ControlSplitTests(unittest.TestCase):
    """Historical replay runs ENGINE_CONTROLS only; the split must stay honest."""

    EMPTY = clr.Result([], 0, [], {}, [])

    def test_every_engine_name_is_a_real_control(self):
        """A renamed probe would otherwise fall silently into CORPUS."""
        names = {n for n, _ in clr.CONTROLS}
        self.assertTrue(clr.ENGINE_CONTROL_NAMES)
        self.assertLessEqual(clr.ENGINE_CONTROL_NAMES, names)

    def test_engine_and_corpus_partition_the_controls(self):
        engine = [n for n, _ in clr.ENGINE_CONTROLS]
        corpus = [n for n, _ in clr.CORPUS_CONTROLS]
        self.assertFalse(set(engine) & set(corpus))
        self.assertEqual(sorted(engine + corpus),
                         sorted(n for n, _ in clr.CONTROLS))

    def test_engine_controls_hold_against_an_empty_tree(self):
        """What makes them safe to run against any historical tree."""
        verdicts = clr.evaluate_controls(self.EMPTY, clr.ENGINE_CONTROLS)
        self.assertTrue(verdicts)
        self.assertTrue(all(verdicts.values()), verdicts)

    def test_corpus_controls_fail_against_an_empty_tree(self):
        """...and why the corpus ones must not be: they key on live pages."""
        verdicts = clr.evaluate_controls(self.EMPTY, clr.CORPUS_CONTROLS)
        self.assertTrue(verdicts)
        self.assertFalse(any(verdicts.values()), verdicts)


class ControlVacuityTests(SiteTestCase):
    """A control must not pass because its subject disappeared.

    `_is_hit` originally asked only "was no miss reported for this token?" --
    which is trivially true when the control link stops resolving, loses its
    backticks, or is deleted outright. A control that goes green when the thing
    it watches vanishes is worse than no control.
    """

    def _result_for(self, body):
        self.site.page("docs/target", "# Target\n\nRun `ait codeagent` here.\n")
        self.site.page("docs/src", body)
        return self.site.scan()

    def test_hit_control_passes_when_the_link_is_present_and_relevant(self):
        result = self._result_for(
            '[`ait codeagent`]({{< relref "/docs/target" >}})\n'
        )
        self.assertTrue(clr._is_hit(result, "docs/src.md", "ait codeagent"))

    def test_hit_control_fails_when_the_link_is_deleted(self):
        result = self._result_for("Nothing here any more.\n")
        self.assertFalse(clr._is_hit(result, "docs/src.md", "ait codeagent"))

    def test_hit_control_fails_when_the_target_stops_resolving(self):
        result = self._result_for(
            '[`ait codeagent`]({{< relref "/docs/gone" >}})\n'
        )
        self.assertEqual(result.counters["unresolved_target"], 1)
        self.assertFalse(clr._is_hit(result, "docs/src.md", "ait codeagent"))

    def test_hit_control_fails_when_the_token_loses_its_backticks(self):
        result = self._result_for(
            '[ait codeagent]({{< relref "/docs/target" >}})\n'
        )
        self.assertFalse(clr._is_hit(result, "docs/src.md", "ait codeagent"))

    def test_hit_control_still_fails_on_a_genuine_miss(self):
        self.site.page("docs/unrelated", "# Unrelated\n\nNo commands.\n")
        self.site.page(
            "docs/src2", '[`ait codeagent`]({{< relref "/docs/unrelated" >}})\n'
        )
        result = self.site.scan()
        self.assertFalse(clr._is_hit(result, "docs/src2.md", "ait codeagent"))


class AnchorHeadingIsPartOfTheSectionTests(SiteTestCase):
    """The heading line is inside the section it names, not a label outside it.

    A body-only slice throws away the one line that often states the subject
    exactly: a link to `#ait-gates-run` landing on `## ait gates run` would be
    reported as a miss for pointing at precisely the right heading.
    """

    TARGET = (
        "# Commands\n\n"
        "## ait board\n\n"
        "It shows the columns.\n\n"
        "## Other\n\n"
        "Unrelated prose.\n"
    )

    def setUp(self):
        super().setUp()
        self.site.page("docs/target", self.TARGET)

    def test_token_named_only_by_the_heading_is_a_hit(self):
        self.site.page(
            "docs/a", '[`ait board`]({{< relref "/docs/target" >}}#ait-board)\n'
        )
        self.assertNotReported(self.site.scan(), "docs/a.md", "ait board")

    def test_anchor_section_includes_the_heading_line(self):
        section = clr.anchor_section(self.TARGET, "ait-board")
        self.assertIsNotNone(section)
        self.assertIn("## ait board", section)
        self.assertIn("It shows the columns.", section)
        # Still bounded by the next same-level heading.
        self.assertNotIn("Unrelated prose.", section)

    def test_a_different_section_still_misses(self):
        """Including the heading must not widen the scope to the whole page."""
        self.site.page(
            "docs/b", '[`ait board`]({{< relref "/docs/target" >}}#other)\n'
        )
        miss = self.assertReported(self.site.scan(), "docs/b.md", "ait board")
        self.assertEqual(miss.scope, "#other")


class ScopeNarrowedVerdictCounterTests(SiteTestCase):
    """`scope_narrowed_verdict` is what makes the anchor control discriminating.

    It counts misses that exist *only because* an anchor narrowed the search --
    the token is on the target page, just not in the named section. An
    implementation that computed the scope and then searched the whole page
    could never produce one, which is exactly why the control asserts it.
    """

    TARGET = (
        "# Page\n\n"
        "## Alpha\n\nNothing here.\n\n"
        "## Beta\n\nRun `ait demo` in this section.\n"
    )

    def setUp(self):
        super().setUp()
        self.site.page("docs/target", self.TARGET)

    def test_counter_fires_when_the_token_is_elsewhere_on_the_page(self):
        self.site.page(
            "docs/a", '[`ait demo`]({{< relref "/docs/target" >}}#alpha)\n'
        )
        result = self.site.scan()
        self.assertEqual(result.counters["scope_narrowed_verdict"], 1)

    def test_counter_does_not_fire_for_a_page_scoped_miss(self):
        """A whole-page miss is not evidence that scoping works."""
        self.site.page("docs/empty", "# Empty\n\nNothing.\n")
        self.site.page(
            "docs/b", '[`ait demo`]({{< relref "/docs/empty" >}})\n'
        )
        result = self.site.scan()
        self.assertEqual(len(result.misses), 1)
        self.assertEqual(result.counters["scope_narrowed_verdict"], 0)

    def test_counter_does_not_fire_when_the_token_is_absent_page_wide(self):
        """An anchored miss whose token is nowhere on the page proves nothing.

        It would be a miss with or without scoping, so it must not be counted.
        """
        self.site.page(
            "docs/c", '[`ait absent`]({{< relref "/docs/target" >}}#alpha)\n'
        )
        result = self.site.scan()
        self.assertEqual(len(result.misses), 1)
        self.assertEqual(result.counters["scope_narrowed_verdict"], 0)

    def test_counter_is_corpus_evidence_not_the_control(self):
        """A corpus with no scope-narrowed miss must still pass the control.

        The control is a self-probe precisely so that repointing the last
        scope-narrowed link cannot make the script fail for everyone.
        """
        self.site.page(
            "docs/d", '[`ait demo`]({{< relref "/docs/target" >}}#beta)\n'
        )
        result = self.site.scan()
        self.assertEqual(result.counters["scope_narrowed_verdict"], 0)
        predicate = dict(clr.CONTROLS)["anchor scoping narrowed the check"]
        self.assertTrue(predicate(result))


class ScopeProbeControlTests(unittest.TestCase):
    """The anchor control drives the real scoring path, not a corpus accident."""

    def test_probe_passes_against_the_shipped_implementation(self):
        self.assertTrue(clr._probe_scope_narrowing())

    def test_probe_fails_if_scoping_is_ignored(self):
        """Force `anchor_section` to return the whole page: the probe must fail."""
        with patch.object(clr, "anchor_section", lambda body, anchor: body):
            self.assertFalse(clr._probe_scope_narrowing())

    def test_probe_fails_if_the_scope_label_is_wrong(self):
        """A right verdict reached with a wrong label is still caught."""
        with patch.object(clr, "anchor_section", lambda body, anchor: None):
            self.assertFalse(clr._probe_scope_narrowing())


# --- report mode fails closed (t1770) ---------------------------------------
class ReportModeControlTests(SiteTestCase):
    """`--report` keeps stdout to the records alone, but still obeys the controls.

    Its exit status is the same contract as a full run's: only a failed control
    is an error. A report mode that skipped the controls would turn a collapsed
    extractor into an empty report that reads as success.
    """

    CONTROL_NAMES = ControlFailureTests.CONTROL_NAMES

    def _run_report(self, controls):
        """Run `main() --report` with `controls`; return (rc, out, err)."""
        # One reported miss, so "stdout is records only" is never vacuously true.
        self.site.page("docs/target", "# Target\n\nUnrelated prose.\n")
        self.site.page(
            "docs/a", '[`ait artifact`]({{< relref "/docs/target" >}})\n'
        )
        out, err = io.StringIO(), io.StringIO()
        argv = ["check_link_relevance.py", "--content", str(self.site.content),
                "--report"]
        with patch.object(clr, "CONTROLS", controls), patch.object(sys, "argv", argv):
            with redirect_stdout(out), redirect_stderr(err):
                rc = clr.main()
        return rc, out.getvalue(), err.getvalue()

    def assertRecordsOnly(self, out):
        lines = [line for line in out.splitlines() if line.strip()]
        self.assertTrue(lines, "report mode printed no records at all")
        for line in lines:
            self.assertIn("  ->  ", line, f"non-record line on stdout: {line!r}")
        self.assertNotIn("links checked", out)
        self.assertFalse([l for l in lines if l.startswith("control")])

    def test_each_control_failing_alone_fails_report_mode(self):
        for index, failing in enumerate(self.CONTROL_NAMES):
            with self.subTest(control=failing):
                controls = [
                    (name, (lambda r: False) if i == index else (lambda r: True))
                    for i, name in enumerate(self.CONTROL_NAMES)
                ]
                rc, out, err = self._run_report(controls)
                self.assertEqual(rc, 1, f"{failing} should have failed --report")
                self.assertIn(f"  - {failing}", err)
                # The passing controls must not be blamed.
                for other in self.CONTROL_NAMES:
                    if other != failing:
                        self.assertNotIn(f"  - {other}", err)
                self.assertRecordsOnly(out)

    def test_all_controls_passing_exits_zero_with_records_only(self):
        controls = [(name, lambda r: True) for name in self.CONTROL_NAMES]
        rc, out, err = self._run_report(controls)
        self.assertEqual(rc, 0, err)
        self.assertRecordsOnly(out)
        self.assertIn("`ait artifact`", out)

    def test_report_mode_evaluates_every_control(self):
        """Each control is called exactly once -- report mode used to call none."""
        calls = []

        def spy(name):
            def predicate(result):
                calls.append(name)
                return True
            return predicate

        rc, _, _ = self._run_report([(n, spy(n)) for n in self.CONTROL_NAMES])
        self.assertEqual(rc, 0)
        self.assertEqual(calls, self.CONTROL_NAMES)

    def test_misses_alone_do_not_fail_report_mode(self):
        """It fails closed on a control, never on a reported link."""
        rc, out, _ = self._run_report([("always ok", lambda r: True)])
        self.assertEqual(rc, 0)
        self.assertIn("`ait artifact`", out)


# --- entry points agree (t1770) ---------------------------------------------
def _defs_after_main_guard(source):
    """Top-level names defined after `if __name__ == "__main__":`, or None.

    `unittest.main()` calls sys.exit(), so direct execution never defines
    anything below the guard, while discovery imports the whole module. An empty
    list is therefore exactly "both entry points collect the same tests".
    """
    tree = ast.parse(source)
    for index, node in enumerate(tree.body):
        if isinstance(node, ast.If) and ast.unparse(node.test) in (
                "__name__ == '__main__'", '__name__ == "__main__"'):
            return [n.name for n in tree.body[index + 1:]
                    if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                      ast.AsyncFunctionDef))]
    return None


class EntryPointAgreementTests(unittest.TestCase):
    """Direct execution and discovery must collect the same tests.

    Asserted on the source rather than by comparing two subprocess runs: a
    direct-run subprocess would execute this very test and recurse.
    """

    def test_guard_is_the_last_statement_of_this_module(self):
        source = Path(__file__).resolve().read_text()
        self.assertEqual(_defs_after_main_guard(source), [])
        last = ast.parse(source).body[-1]
        self.assertIsInstance(last, ast.If)
        self.assertIn("__main__", ast.unparse(last.test))

    def test_helper_detects_a_stranded_class(self):
        source = (
            "import unittest\n"
            "class A(unittest.TestCase):\n    pass\n"
            "if __name__ == '__main__':\n    unittest.main()\n"
            "class B(unittest.TestCase):\n    pass\n"
        )
        self.assertEqual(_defs_after_main_guard(source), ["B"])

    def test_helper_reports_a_missing_guard(self):
        self.assertIsNone(_defs_after_main_guard("import unittest\n"))


# MUST stay at the very END of the file (t1770; t1518 fixed the same defect in
# tests/test_minimonitor_concern_action.py). `unittest.main()` calls sys.exit(),
# so a guard placed mid-file stops the interpreter there: every class below it
# is never defined, and a direct run reports a green partial count. Discovery
# imports the module instead and is unaffected, which is why it goes unnoticed.
# EntryPointAgreementTests fails if anything is defined after it.
if __name__ == "__main__":
    unittest.main()
