"""Every tmux session-name resolver must agree on `tmux.default_session` (t1800).

`seed/project_config.yaml` ships `default_session:` with no value. Five code
paths turn that key into the tmux session a project runs in, from two reader
families:

  YAML-backed   load_tmux_defaults()          board, agent-command, agentcrew
                minimonitor_app.main()         (via load_tmux_defaults)
                monitor_app.main()             (via load_tmux_defaults)
  line parsers  _read_default_session()        registry discovery
                _tmux_bootstrap_resolve_session (bash)   `ait ide`

Before t1800 a blank value resolved to the string ``'None'`` (a tmux session
agentcrew would actually create), a comment-only value to ``# note``, and an
option-like name such as ``-n`` to nothing at all (bash ``echo`` ate it).

The contract pinned here, and its deliberate limits:

* ``ResolverParityTests`` — on every blank/null form and every single-line
  plain or quoted string scalar that is a direct child of a column-0 ``tmux:``
  block (any LF/CRLF/CR line endings), all five paths return the same name.
  ``test_parity_rows_match_yaml`` proves each expected value is what YAML
  itself reads, with a test-local normalizer rather than the code under test.
* ``LegacyYamlFormsPreservedTests`` — flow mappings, block scalars and typed
  scalars keep exactly the value the YAML-backed readers returned before
  t1800. The line parsers never could read those shapes and are deliberately
  NOT asserted there: pinning a known divergence would make its fix look like
  a regression.
* ``LineParserTwinTests`` — on invalid YAML the two line parsers still agree.

The monitors' ``main()`` is driven for real — not re-implemented, not grepped —
through its module-level seams, and the assertion is on the kwargs its
production call site hands the App.

Run: python3 tests/test_tmux_default_session_resolvers.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "monitor"))

import minimonitor_app as mm  # noqa: E402
import monitor_app as ma  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    DEFAULT_TMUX_SESSION,
    _read_default_session,
    load_tmux_defaults,
)

BOOTSTRAP = REPO_ROOT / ".aitask-scripts" / "lib" / "tmux_bootstrap.sh"
SEED = (REPO_ROOT / "seed" / "project_config.yaml").read_bytes()
D = DEFAULT_TMUX_SESSION


def _row(value: str) -> bytes:
    """A minimal config whose `default_session:` line carries ``value``."""
    return (
        f"tmux:\n  default_session:{value}\n  default_split: horizontal\n"
    ).encode()


# (fixture name, config bytes — None means "no config file", expected session)
PARITY_ROWS: list[tuple[str, bytes | None, str]] = [
    # blank / null -> default
    ("blank (seed shape)", _row(""), D),
    ("comment only", _row(" # note"), D),
    ('empty ""', _row(' ""'), D),
    ("empty ''", _row(" ''"), D),
    ('quoted whitespace "   "', _row(' "   "'), D),
    ("quoted whitespace '   '", _row(" '   '"), D),
    ("trailing spaces only", _row("   "), D),
    ("null", _row(" null"), D),
    ("Null", _row(" Null"), D),
    ("NULL", _row(" NULL"), D),
    ("tilde", _row(" ~"), D),
    ("null + comment", _row(" null # c"), D),
    # strings, verbatim
    ("nULL is a string", _row(" nULL"), "nULL"),
    ('quoted "null" is a string', _row(' "null"'), "null"),
    ("quoted '~' is a string", _row(" '~'"), "~"),
    ("plain", _row(" mysess"), "mysess"),
    ("plain + comment", _row(" mysess  # team"), "mysess"),
    ("hash inside plain", _row(" my#sess"), "my#sess"),
    ("hash inside quoted", _row(' "my#sess"'), "my#sess"),
    ("quoted + comment", _row(' "x" # c'), "x"),
    ("quoted padding kept", _row(' "  x  "'), "  x  "),
    # option-like names must survive bash output
    ("-n", _row(" -n"), "-n"),
    ('quoted "-n"', _row(' "-n"'), "-n"),
    ("-e", _row(" -e"), "-e"),
    ("-neE", _row(" -neE"), "-neE"),
    # structure
    ("4-space block",
     b"tmux:\n    default_split: horizontal\n    default_session: four\n",
     "four"),
    ("nested key only",
     b"tmux:\n  syncer:\n    default_session: nested\n"
     b"  default_split: horizontal\n",
     D),
    ("nested + direct",
     b"tmux:\n  syncer:\n    default_session: nested\n"
     b"  default_session: direct\n",
     "direct"),
    ("comment banner first",
     b"tmux:\n  # banner\n  default_session: bannered\n", "bannered"),
    ("whitespace-only line first",
     b"tmux:\n     \n  default_session: wsline\n", "wsline"),
    ("blank line first",
     b"tmux:\n\n  default_session: blankline\n", "blankline"),
    # line endings
    ("CRLF",
     b"tmux:\r\n  default_session: crlf\r\n  default_split: horizontal\r\n",
     "crlf"),
    ("CRLF + blank line first",
     b"tmux:\r\n\r\n  default_session: crlfblank\r\n", "crlfblank"),
    ("CRLF + whitespace-only line first",
     b"tmux:\r\n     \r\n  default_session: crlfws\r\n", "crlfws"),
    ("CRLF + comment then blank",
     b"tmux:\r\n  # banner\r\n\r\n  default_session: crlfmix\r\n", "crlfmix"),
    ("CR-only",
     b"tmux:\r  default_session: cronly\r  default_split: horizontal\r",
     "cronly"),
    ("CR-only + blank line first",
     b"tmux:\r\r  default_session: crblank\r", "crblank"),
    ("CRLF blank value", b"tmux:\r\n  default_session:\r\n", D),
    ("shipped seed converted to CRLF", SEED.replace(b"\n", b"\r\n"), D),
    # more structure
    ("key absent", b"tmux:\n  default_split: horizontal\n", D),
    ("key under a later top-level block",
     b"tmux:\n  default_split: h\nother:\n  default_session: wrong\n", D),
    ("no config file", None, D),
    # The real seed: if someone gives it a value this fails loudly, instead of
    # the "blank-value seed shape" pin silently going stale.
    ("shipped seed, verbatim", SEED, D),
]

# YAML-only shapes: the value each YAML-backed reader returned BEFORE t1800.
LEGACY_ROWS: list[tuple[str, bytes, str]] = [
    ("flow mapping", b"tmux: {default_session: flowsess}\n", "flowsess"),
    ("folded block scalar",
     b"tmux:\n  default_session: >-\n    blocksess\n", "blocksess"),
    ("literal block scalar",
     b"tmux:\n  default_session: |\n    blocksess\n", "blocksess\n"),
    ("typed bool", _row(" yes"), "True"),
    ("typed octal int", _row(" 0123"), "83"),
]

# Invalid YAML (tab indentation): only the two line parsers are compared.
TWIN_ROWS: list[tuple[str, bytes, str]] = [
    ("tab-indented line in block",
     b"tmux:\n\tfoo: 1\n  default_session: tabbed\n", "tabbed"),
]


@contextlib.contextmanager
def _project(data: bytes | None):
    """A throwaway project root holding ``data`` as its project_config.yaml."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        if data is not None:
            meta = root / "aitasks" / "metadata"
            meta.mkdir(parents=True)
            # Bytes, so CRLF and CR-only line endings reach the readers intact.
            (meta / "project_config.yaml").write_bytes(data)
        yield root


def _yaml_value(data: bytes):
    """What YAML itself reads for `tmux.default_session` (the oracle)."""
    doc = yaml.safe_load(data.decode("utf-8")) or {}
    tmux = doc.get("tmux") if isinstance(doc, dict) else None
    return tmux.get("default_session") if isinstance(tmux, dict) else None


def _session_from_yaml(value) -> str:
    """Independent statement of the blank rule — NOT the code under test."""
    if value is None or not str(value).strip():
        return D
    return str(value)


def _bash(root: Path) -> str:
    out = subprocess.run(
        ["bash", "-c", 'source "$1"; _tmux_bootstrap_resolve_session "$2"',
         "_", str(BOOTSTRAP), str(root)],
        capture_output=True, text=True, check=True,
    ).stdout
    # Strip only the terminating newline so padding and `-n` compare exactly.
    return out[:-1] if out.endswith("\n") else out


class _AppRecorder:
    """Replaces the App class during main(); records its kwargs."""

    kwargs: dict = {}

    def __init__(self, **kwargs):
        type(self).kwargs = kwargs

    def run(self):
        """Never start a UI — main() is what is under test."""


def _drive_main(module, app_attr: str, root: Path,
                detected: str | None = None) -> dict:
    """Run a monitor's real ``main()`` over ``root``; return its App kwargs.

    ``main()`` derives ``project_root`` from ``__file__``, so both config
    readers are redirected to ``root`` — the real parsers still do the reading.
    ``create=True`` lets this harness drive a ``main()`` that does not yet
    import ``load_tmux_defaults`` (the pre-fix red run).
    """
    real_tmux_config = module.load_project_tmux_config
    _AppRecorder.kwargs = {}
    with patch.object(module, "load_tmux_defaults",
                      lambda _root: load_tmux_defaults(root), create=True), \
         patch.object(module, "load_project_tmux_config",
                      lambda _root: real_tmux_config(root)), \
         patch.object(module, "load_monitor_config", lambda _root: {}), \
         patch.object(module, "_detect_tmux_session", lambda: detected), \
         patch.object(module, app_attr, _AppRecorder), \
         patch.object(sys, "argv", ["app.py"]):
        module.main()
    return dict(_AppRecorder.kwargs)


RESOLVERS = {
    "load_tmux_defaults": lambda root: load_tmux_defaults(root)["default_session"],
    "_read_default_session": _read_default_session,
    "bash _tmux_bootstrap_resolve_session": _bash,
    "minimonitor_app.main": lambda root: _drive_main(mm, "MiniMonitorApp", root)["session"],
    "monitor_app.main": lambda root: _drive_main(ma, "MonitorApp", root)["session"],
}
YAML_BACKED = ("load_tmux_defaults", "minimonitor_app.main", "monitor_app.main")
LINE_PARSERS = ("_read_default_session", "bash _tmux_bootstrap_resolve_session")


class ResolverParityTests(unittest.TestCase):
    def test_every_resolver_returns_the_expected_session(self):
        for name, data, expected in PARITY_ROWS:
            with _project(data) as root:
                for resolver, resolve in RESOLVERS.items():
                    with self.subTest(fixture=name, resolver=resolver):
                        self.assertEqual(resolve(root), expected)

    def test_parity_rows_match_yaml(self):
        """The expected column is YAML's reading, not the parsers' opinion."""
        for name, data, expected in PARITY_ROWS:
            if data is None:
                continue
            with self.subTest(fixture=name):
                value = _yaml_value(data)
                self.assertTrue(
                    value is None or isinstance(value, str),
                    f"YAML types this row as {type(value).__name__}; a typed "
                    "scalar belongs in LEGACY_ROWS, not the parity contract",
                )
                self.assertEqual(_session_from_yaml(value), expected)


class LegacyYamlFormsPreservedTests(unittest.TestCase):
    def test_yaml_backed_readers_keep_the_pre_fix_value(self):
        for name, data, expected in LEGACY_ROWS:
            with _project(data) as root:
                for resolver in YAML_BACKED:
                    with self.subTest(fixture=name, resolver=resolver):
                        self.assertEqual(RESOLVERS[resolver](root), expected)

    def test_expected_values_are_str_of_what_yaml_reads(self):
        """The pinned literals are exactly the pre-fix `str(yaml_value)`."""
        for name, data, expected in LEGACY_ROWS:
            with self.subTest(fixture=name):
                self.assertEqual(str(_yaml_value(data)), expected)

    def test_rows_are_shapes_the_line_parsers_cannot_read(self):
        """A parity failure cannot be hidden by moving its row here.

        A row qualifies only if YAML types the value (non-str), or no line
        carries `default_session:` with a single-line value — a flow mapping
        has no such line, a block scalar carries only its `>`/`|` indicator.
        """
        single_line_key = re.compile(r"^ +default_session:[ \t]*[^\s>|]")
        for name, data, _expected in LEGACY_ROWS:
            with self.subTest(fixture=name):
                value = _yaml_value(data)
                lines = data.decode("utf-8").splitlines()
                readable = any(single_line_key.match(line) for line in lines)
                self.assertTrue(not isinstance(value, str) or not readable)


class LineParserTwinTests(unittest.TestCase):
    def test_line_parsers_agree_on_invalid_yaml(self):
        for name, data, expected in TWIN_ROWS:
            with _project(data) as root:
                for resolver in LINE_PARSERS:
                    with self.subTest(fixture=name, resolver=resolver):
                        self.assertEqual(RESOLVERS[resolver](root), expected)


class MonitorMismatchCheckTests(unittest.TestCase):
    """The monitor compares a detected session against the configured name."""

    ROWS = [("blank (seed shape)", _row("")), ("comment only", _row(" # note"))]

    def test_other_session_is_checked_against_the_default(self):
        for name, data in self.ROWS:
            with _project(data) as root, self.subTest(fixture=name):
                kwargs = _drive_main(ma, "MonitorApp", root, detected="other")
                self.assertEqual(kwargs["session"], "other")
                self.assertEqual(kwargs["expected_session"], D)

    def test_running_in_the_default_session_is_no_mismatch(self):
        for name, data in self.ROWS:
            with _project(data) as root, self.subTest(fixture=name):
                kwargs = _drive_main(ma, "MonitorApp", root, detected=D)
                self.assertEqual(kwargs["session"], D)
                self.assertIsNone(kwargs["expected_session"])


class HarnessControlTests(unittest.TestCase):
    def test_harness_feeds_the_fixture_to_main(self):
        """NEGATIVE CONTROL for every blank row above.

        The default is also the answer for a blank value, so a harness whose
        patched readers ignored the fixture would pass those rows vacuously. A
        configured name must arrive at each App.
        """
        with _project(_row(" mysess")) as root:
            for module, app_attr in ((mm, "MiniMonitorApp"), (ma, "MonitorApp")):
                with self.subTest(app=app_attr):
                    self.assertEqual(
                        _drive_main(module, app_attr, root)["session"], "mysess"
                    )


if __name__ == "__main__":
    unittest.main()
