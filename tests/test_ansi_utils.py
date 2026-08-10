"""Unit test for the shared ANSI stripper in monitor/ansi_utils.py (t1474).

`strip_ansi` is the single normalisation every pane-text consumer goes through
(idle detection's `compare_value`, prompt matching, the concern parser), so its
two failure directions matter equally: leaving markup in pollutes every match
built on it, and eating visible text turns a blocked pane into a silent idle one.
Both are asserted here.

Covers:
  1. CSI sequences are still stripped (regression guard — unchanged behaviour).
  2. OSC 8 hyperlink with ST (ESC \\) terminator: markup gone, link text kept.
  3. OSC with BEL terminator (window-title set) is stripped.
  4. An unterminated OSC is left INTACT and does not eat the text after it.
  5. The real `tmux capture-pane -p -e` bytes in tests/fixtures/ strip to plain text.
  6. Escape-free text is returned byte-identical.

Run:
  python3 tests/test_ansi_utils.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))

from monitor.ansi_utils import strip_ansi  # noqa: E402

# The recorded capture is the shared fixture: tests/test_shadow_strip_ansi.sh
# feeds the same file to the bash mirror, so both implementations are proven
# against one artifact rather than two hand-copied strings.
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "osc8_capture_pane.txt"

ESC = "\x1b"
BEL = "\x07"


def _check_csi_still_stripped() -> None:
    got = strip_ansi(f"{ESC}[31mRED{ESC}[0m plain {ESC}[1;32mGREEN{ESC}[m")
    assert got == "RED plain GREEN", f"CSI strip regressed: {got!r}"


def _check_osc8_st_terminator() -> None:
    s = f"{ESC}]8;;https://example.com/x{ESC}\\LINKTEXT{ESC}]8;;{ESC}\\"
    got = strip_ansi(s)
    assert got == "LINKTEXT", f"OSC 8 (ST) not stripped to link text: {got!r}"


def _check_osc_bel_terminator() -> None:
    got = strip_ansi(f"{ESC}]0;window title{BEL}after")
    assert got == "after", f"BEL-terminated OSC not stripped: {got!r}"


def _check_unterminated_osc_is_left_intact() -> None:
    """Fail-safe: a truncated OSC must never swallow the text after it.

    A bounded body (`[^\\x07\\x1b]*`) plus a REQUIRED terminator is what buys
    this. A non-greedy `.*?` body would reach forward to the next escape's
    terminator and delete every visible character in between — and the text most
    likely to sit there is the prompt footer whose absence reads as "idle".
    """
    s = f"{ESC}]8;;http://truncated"
    got = strip_ansi(s)
    assert got == s, f"unterminated OSC must be left intact, got {got!r}"

    # The same, followed by real text and a LATER well-formed sequence.
    s2 = f"{ESC}]8;;http://truncated VISIBLE {ESC}[31mRED{ESC}[0m"
    got2 = strip_ansi(s2)
    assert "VISIBLE" in got2, f"text after an unterminated OSC was eaten: {got2!r}"
    assert "RED" in got2, f"text after an unterminated OSC was eaten: {got2!r}"


def _check_real_tmux_capture_fixture() -> None:
    assert FIXTURE.is_file(), f"missing fixture {FIXTURE}"
    raw = FIXTURE.read_text(encoding="utf-8", errors="surrogateescape")
    got = strip_ansi(raw).rstrip("\n")
    # Both directions on real bytes: markup gone AND visible text survived.
    assert got == "LINKTEXT", f"real capture did not strip to link text: {got!r}"
    assert ESC not in got, f"escape byte survived the strip: {got!r}"
    assert "example.com" not in got, f"hyperlink URL survived the strip: {got!r}"


def _check_plain_text_unchanged() -> None:
    s = "no escapes here — ❯ 1. Yes\n  2. No\n"
    got = strip_ansi(s)
    assert got == s, f"escape-free text was modified: {got!r}"


def main() -> int:
    tests = [
        ("_check_csi_still_stripped", _check_csi_still_stripped),
        ("_check_osc8_st_terminator", _check_osc8_st_terminator),
        ("_check_osc_bel_terminator", _check_osc_bel_terminator),
        ("_check_unterminated_osc_is_left_intact",
         _check_unterminated_osc_is_left_intact),
        ("_check_real_tmux_capture_fixture", _check_real_tmux_capture_fixture),
        ("_check_plain_text_unchanged", _check_plain_text_unchanged),
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS: {name}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL: {name}: {e}")
        except Exception as e:
            failures += 1
            print(f"  ERROR: {name}: {e!r}")
    print()
    if failures:
        print(f"FAIL: {failures}/{len(tests)} tests failed")
        return 1
    print(f"PASS: all {len(tests)} tests passed")
    return 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211).

    ``main()`` catches each check's AssertionError to print a per-check tally,
    so the assertion here is on its return code; detail goes to stdout.
    """

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
