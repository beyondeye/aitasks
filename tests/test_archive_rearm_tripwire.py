#!/usr/bin/env python3
"""Every EXIT-trap re-arm keeps the archive sweep (t2032).

``lib/archive_utils.sh`` sweeps this shell's ``ait-archive.<owner>.*``
extraction dirs from the EXIT trap. bash keeps ONE EXIT trap, so a later
``trap X EXIT`` / ``trap - EXIT`` silently drops the sweep, and every bundled
``$( resolve_task_file … )`` in that process leaks a dir. The fix is a call to
``ait_archive_rearm_exit_trap`` right after each such ``trap``; this tripwire
keeps it that way.

Scope -- the files where the sweep can be armed when the trap runs:
  * top-level ``.aitask-scripts/*.sh`` whose startup source closure (the repo's
    own scanner, ``tests/lib/shell_startup_closure.py``) contains
    ``archive_utils.sh``, or that source task_utils/archive_utils anywhere
    (an indented, lazy source is outside the closure's recognised shape);
  * every ``lib/**/*.sh`` except ``archive_utils.sh`` itself -- a lib loads
    into callers this scan cannot see, so it uses the ``declare -F`` guard.

A site is satisfied by the re-arm as a STATEMENT -- ``; ait_archive_rearm_exit_trap``
ending the trap's own line, alone on the next non-blank code line, or in the
lib ``declare -F`` guard -- or by the per-line comment marker
``# archive-sweep: subshell-local`` (a ``( … )``-local trap with no resolve).
Comments are stripped first, so a comment that merely names the helper is not
a call.

Not matched, deliberately: ``trap -p`` / ``trap -l``, comment lines, and
``eval "trap …"`` (``txn_chain_exit_trap`` prepends to the current trap, so it
keeps the chain). A trap whose text is built in a variable is not seen either.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_DIR / ".aitask-scripts"
LIB = SCRIPTS / "lib"

sys.path.insert(0, str(PROJECT_DIR / "tests" / "lib"))
from shell_startup_closure import startup_closure  # noqa: E402

REARM = "ait_archive_rearm_exit_trap"
MARKER = "# archive-sweep: subshell-local"

# A `trap` COMMAND word (line start, or after ; && || { then do), a handler
# argument -- `-` (clear), a quoted string, or any bare word not starting with
# `-` (so `trap : EXIT` counts and `trap -p EXIT` does not) -- and EXIT in the
# signal list.
TRAP_RE = re.compile(
    r"(?:^|[;&|{]|\bthen\b|\bdo\b)\s*trap\s+(?:--\s+)?"
    r"(?P<handler>-(?=\s)|'[^']*'|\"(?:[^\"\\]|\\.)*\"|[^\s'\"-]\S*)"
    r"(?P<sigs>(?:\s+[A-Z][A-Z0-9]*)+)"
)
# The re-arm as a STATEMENT, not a mention: alone on the (comment-stripped)
# next line, as `; ait_archive_rearm_exit_trap` ending the trap's own line, or
# in the lib guard spelling.
REARM_CALL_RE = re.compile(
    r"^\s*(?:;\s*)?(?:ait_archive_rearm_exit_trap"
    r"|if\s+declare\s+-F\s+ait_archive_rearm_exit_trap\s*>\s*/dev/null\s*;\s*"
    r"then\s+ait_archive_rearm_exit_trap\s*;\s*fi)\s*;?\s*$"
)
DIRECT_SOURCE_RE = re.compile(r"^\s*(?:source|\.)\s+\S*(?:task_utils|archive_utils)\.sh")


def strip_comment(line: str) -> str:
    """The code part of a shell line: drop an unquoted `#` comment."""
    quote = ""
    prev = " "
    for i, ch in enumerate(line):
        if quote:
            if ch == quote and (quote == "'" or prev != "\\"):
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and prev.isspace():
            return line[:i]
        prev = ch
    return line


def _sites(line: str):
    code = strip_comment(line)
    for m in TRAP_RE.finditer(code):
        if "EXIT" in m.group("sigs").split():
            yield code, m


def unpaired_sites(text: str) -> list[tuple[int, str]]:
    """(line number, line) for each EXIT-trap site with no re-arm or marker."""
    lines = text.splitlines()
    bad: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        for code, m in _sites(line):
            if MARKER in line[len(code):]:
                continue
            if REARM_CALL_RE.match(code[m.end():]):
                continue
            nxt = next(
                (strip_comment(l) for l in lines[i + 1:]
                 if strip_comment(l).strip()),
                "",
            )
            if not REARM_CALL_RE.match(nxt):
                bad.append((i + 1, line.strip()))
    return bad


def count_sites(text: str) -> int:
    return sum(1 for line in text.splitlines() for _ in _sites(line))


def archive_loaded(script: Path) -> bool:
    text = script.read_text(encoding="utf-8")
    if any(DIRECT_SOURCE_RE.match(l) for l in text.splitlines()):
        return True
    try:
        return "archive_utils.sh" in startup_closure(LIB, [script])
    except AssertionError:      # no startup sources at all
        return False


def scoped_files() -> list[Path]:
    tops = [p for p in sorted(SCRIPTS.glob("*.sh")) if archive_loaded(p)]
    libs = [p for p in sorted(LIB.rglob("*.sh")) if p.name != "archive_utils.sh"]
    return tops + libs


class ArchiveRearmTripwire(unittest.TestCase):
    def test_every_exit_trap_site_keeps_the_sweep(self):
        report = []
        for path in scoped_files():
            for lineno, line in unpaired_sites(path.read_text(encoding="utf-8")):
                report.append(f"{path.relative_to(PROJECT_DIR)}:{lineno}: {line}")
        self.assertEqual(
            report, [],
            "EXIT trap replaced/cleared without re-arming the archive sweep — add "
            f"`{REARM}` on the next line (libs: guard it with `declare -F`), or "
            f"mark a subshell-local trap with `{MARKER}`:\n" + "\n".join(report),
        )

    def test_scan_is_not_vacuous(self):
        files = scoped_files()
        tops = [p for p in files if p.parent == SCRIPTS]
        self.assertGreaterEqual(len(tops), 40, "archive-loaded script discovery shrank")
        sites = sum(count_sites(p.read_text(encoding="utf-8")) for p in files)
        self.assertGreaterEqual(sites, 42, "EXIT-trap site discovery shrank")
        names = {p.name for p in files}
        for must in ("aitask_gate.sh", "aitask_note.sh", "aitask_create.sh",
                     "aitask_fold_mark.sh", "registry_lock.sh"):
            self.assertIn(must, names)

    def test_discovery_uses_the_closure_for_indirect_loads(self):
        # aitask_attach.sh reaches archive_utils only through task_utils.sh's
        # startup closure; a lib-free script must stay out of scope.
        self.assertTrue(archive_loaded(SCRIPTS / "aitask_note.sh"))
        self.assertFalse(archive_loaded(SCRIPTS / "aitask_syncer.sh"))


class TripwireSelfTest(unittest.TestCase):
    def check(self, text: str) -> list[tuple[int, str]]:
        return unpaired_sites(text)

    def test_unpaired_site_is_flagged(self):
        self.assertEqual(len(self.check("trap 'cleanup' EXIT\necho hi\n")), 1)

    def test_clear_and_one_liner_are_flagged(self):
        self.assertEqual(len(self.check("  rel; trap - EXIT\n  return 0\n")), 1)
        self.assertEqual(len(self.check("trap cleanup EXIT INT TERM\n:\n")), 1)

    def test_next_line_rearm_passes(self):
        self.assertEqual(self.check("trap 'x' EXIT\nait_archive_rearm_exit_trap\n"), [])

    def test_same_line_rearm_passes(self):
        self.assertEqual(self.check("rel; trap - EXIT; ait_archive_rearm_exit_trap\n"), [])

    def test_guarded_rearm_after_comment_passes(self):
        text = ("trap \"rel '$d'\" EXIT\n# keep the sweep\n"
                "if declare -F ait_archive_rearm_exit_trap >/dev/null; then "
                "ait_archive_rearm_exit_trap; fi\n")
        self.assertEqual(self.check(text), [])

    def test_marker_passes(self):
        self.assertEqual(self.check(f"  trap \"rm -rf '$t'\" EXIT   {MARKER}\n  :\n"), [])

    def test_colon_handler_is_a_site(self):
        self.assertEqual(len(self.check("trap : EXIT\necho work\n")), 1)
        self.assertEqual(count_sites("trap : EXIT\n"), 1)

    def test_mention_in_a_comment_is_not_a_call(self):
        self.assertEqual(len(self.check(
            "trap cleanup EXIT # call ait_archive_rearm_exit_trap here\necho work\n")), 1)
        self.assertEqual(len(self.check(
            "trap cleanup EXIT\necho ok  # ait_archive_rearm_exit_trap\n")), 1)

    def test_mention_in_code_is_not_a_call(self):
        self.assertEqual(len(self.check(
            "trap cleanup EXIT\necho ait_archive_rearm_exit_trap\n")), 1)
        self.assertEqual(len(self.check(
            "trap cleanup EXIT; echo ait_archive_rearm_exit_trap\n:\n")), 1)

    def test_marker_must_be_a_comment(self):
        self.assertEqual(len(self.check(
            "trap \"echo '# archive-sweep: subshell-local'\" EXIT\n:\n")), 1)

    def test_non_sites_are_ignored(self):
        text = ("# trap 'x' EXIT\nspec=\"$(trap -p EXIT)\"\n"
                "eval \"trap '$1; '$cur EXIT\"\ntrap 'h' INT TERM\n")
        self.assertEqual(self.check(text), [])
        self.assertEqual(count_sites(text), 0)

    def test_planted_file_is_flagged_by_the_full_scan_logic(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "planted.sh"
            p.write_text('source "${SCRIPT_DIR}/lib/task_utils.sh"\n'
                         "trap 'cleanup' EXIT\nmain\n", encoding="utf-8")
            self.assertTrue(archive_loaded(p))
            self.assertEqual([n for n, _ in unpaired_sites(p.read_text())], [2])


if __name__ == "__main__":
    unittest.main()
