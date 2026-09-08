#!/usr/bin/env python3
"""Tests for tests/lib/shell_startup_closure.py.

Two halves, deliberately separate:

(a) **Helper behavior** against a synthetic mini-tree — never the real repo — so
    these assertions cannot drift as the framework's own source chain grows.
(b) **Format contract** against the real tree — the convention the derivation
    relies on, checked where it actually has to hold.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_DIR / ".aitask-scripts"
LIB_SRC = SCRIPTS / "lib"

sys.path.insert(0, str(PROJECT_DIR / "tests" / "lib"))
from shell_startup_closure import (  # noqa: E402
    copy_startup_closure,
    nonconforming_column0_sources,
    startup_closure,
    startup_sources,
)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class StartupClosureTests(unittest.TestCase):
    """(a) Helper behavior, against a synthetic tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.lib = self.root / "lib"
        self.lib.mkdir()

    def test_all_three_spellings_resolve_transitively(self) -> None:
        write(self.lib / "leaf.sh", "echo leaf\n")
        write(
            self.lib / "mid_b.sh",
            'source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/leaf.sh"\n',
        )
        write(
            self.lib / "mid_a.sh",
            'source "$(dirname "${BASH_SOURCE[0]}")/mid_b.sh"\n',
        )
        root = write(self.root / "entry.sh", 'source "${SCRIPT_DIR}/lib/mid_a.sh"\n')

        self.assertEqual(startup_sources(root), ["mid_a.sh"])
        self.assertEqual(
            startup_closure(self.lib, [root]), ["leaf.sh", "mid_a.sh", "mid_b.sh"]
        )

    def test_indented_source_excluded_column0_included(self) -> None:
        """Negative control: the recognised shape, pinned in both directions.

        Both lines target a real file and differ ONLY in leading whitespace, so
        a failure here can mean nothing except that the shape stopped
        discriminating.
        """
        write(self.lib / "eager.sh", "echo eager\n")
        write(self.lib / "lazy.sh", "echo lazy\n")
        root = write(
            self.root / "entry.sh",
            'source "${SCRIPT_DIR}/lib/eager.sh"\n'
            "_helper() {\n"
            '    source "${SCRIPT_DIR}/lib/lazy.sh"\n'
            "}\n",
        )

        self.assertEqual(startup_closure(self.lib, [root]), ["eager.sh"])

    def test_cycle_terminates(self) -> None:
        write(self.lib / "a.sh", 'source "${SCRIPT_DIR}/lib/b.sh"\n')
        write(self.lib / "b.sh", 'source "${SCRIPT_DIR}/lib/a.sh"\n')
        root = write(self.root / "entry.sh", 'source "${SCRIPT_DIR}/lib/a.sh"\n')

        self.assertEqual(startup_closure(self.lib, [root]), ["a.sh", "b.sh"])

    def test_empty_closure_raises(self) -> None:
        """A pattern that stops matching must fail loudly, not copy nothing."""
        root = write(self.root / "entry.sh", "echo 'no sources here'\n")

        with self.assertRaises(AssertionError) as ctx:
            startup_closure(self.lib, [root])
        self.assertIn("empty", str(ctx.exception))

    def test_missing_referenced_lib_raises(self) -> None:
        root = write(self.root / "entry.sh", 'source "${SCRIPT_DIR}/lib/gone.sh"\n')

        with self.assertRaises(AssertionError) as ctx:
            startup_closure(self.lib, [root])
        self.assertIn("gone.sh", str(ctx.exception))

    def test_copy_puts_exactly_the_returned_names_on_disk(self) -> None:
        write(self.lib / "leaf.sh", "echo leaf\n")
        write(self.lib / "mid.sh", 'source "${SCRIPT_DIR}/lib/leaf.sh"\n')
        write(self.lib / "unrelated.sh", "echo unrelated\n")
        root = write(self.root / "entry.sh", 'source "${SCRIPT_DIR}/lib/mid.sh"\n')
        dst = self.root / "dst"
        dst.mkdir()

        copied = copy_startup_closure(self.lib, dst, roots=[root])

        self.assertEqual(copied, ["leaf.sh", "mid.sh"])
        self.assertEqual(sorted(p.name for p in dst.iterdir()), ["leaf.sh", "mid.sh"])

    def test_nonconforming_column0_source_is_reported(self) -> None:
        script = write(
            self.root / "entry.sh",
            'source "${SCRIPT_DIR}/lib/ok.sh"\n'
            'source "$some_dir/sneaky.sh"\n'
            '    source "$other_dir/indented.sh"\n',
        )

        bad = nonconforming_column0_sources(script)

        # Only the column-0 variable-path line: the indented one is out of
        # scope (lazy by convention), the recognised one conforms.
        self.assertEqual(bad, [(2, 'source "$some_dir/sneaky.sh"')])


class RealTreeContractTests(unittest.TestCase):
    """(b) The format contract, checked where it must actually hold."""

    ROOT_SCRIPT = SCRIPTS / "aitask_changelog.sh"

    def scanned_files(self) -> list[Path]:
        names = startup_closure(LIB_SRC, [self.ROOT_SCRIPT])
        return [self.ROOT_SCRIPT, *(LIB_SRC / name for name in names)]

    def test_every_column0_source_uses_a_recognised_spelling(self) -> None:
        """The convention the derivation rests on, across every scanned file.

        This is what catches the one hole a pure-regex derivation would
        otherwise have: a startup source written at column 0 through a variable
        path would be invisible to STARTUP_SOURCE_RE and silently omitted from
        the fixture.
        """
        offenders = [
            f"{path.relative_to(PROJECT_DIR)}:{number}  {text}"
            for path in self.scanned_files()
            for number, text in nonconforming_column0_sources(path)
        ]

        self.assertEqual(
            offenders,
            [],
            "column-0 source line(s) outside the recognised startup shape — see "
            "the source-on-startup bullet in "
            "aidocs/framework/shell_conventions.md:\n" + "\n".join(offenders),
        )

    def test_closure_contains_stale_lock(self) -> None:
        """Regression pin for t1745: the entry a hand list dropped."""
        self.assertIn(
            "stale_lock.sh", startup_closure(LIB_SRC, [self.ROOT_SCRIPT])
        )


if __name__ == "__main__":
    unittest.main()
