"""Every tmux session-name resolver must agree on `tmux.default_session` (t1800, t1811).

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
Before t1811 the line parsers also read YAML-only shapes wrongly and silently:
``>-`` became a session named ``>-``, ``yes`` stayed ``yes`` while YAML read
``True``, and the Python twin cut ``team\\xa0#1`` at the NBSP.

The contract pinned here, and its deliberate limits:

* ``ResolverParityTests`` — on every blank/null form and every single-line
  plain or quoted string scalar that is a direct child of a column-0 ``tmux:``
  block (any LF/CRLF/CR line endings), all five paths return the same name.
  ``test_parity_rows_match_yaml`` proves each expected value is what YAML
  itself reads, with a test-local normalizer rather than the code under test.
  ``RoundTripTypedTests`` covers the typed values whose ``str()`` is their own
  text (canonical ints, True, False), which still agree.
* **The line parsers read a value only if YAML reads back the same string.**
  Anything else is *unreadable*: both twins return the default and report a
  shape — Python through ``read_default_session_status``, bash through exit 2
  and a ``DEFAULT_SESSION_UNREADABLE:<shape>:<cfg>`` stderr sentinel.
  ``LegacyYamlFormsPreservedTests`` pins that for the flow-mapping, block and
  typed rows (the YAML-backed values there are unchanged), and
  ``UnreadableScalarTests`` for every other shape, each row oracle-proven to be
  a real divergence. ``AnnouncedRoundTripTests`` pins the deliberate
  over-approximation: floats and timestamps are announced even when ``str()``
  happens to round-trip.
* ``GeneratedCorpusInvariantTests`` — over a seeded, unfiltered corpus: every
  value is read the same as YAML or announced, and the two twins agree on value
  and shape.
* ``LineParserTwinTests`` — on invalid YAML the two line parsers still agree.

The monitors' ``main()`` is driven for real — not re-implemented, not grepped —
through its module-level seams, and the assertion is on the kwargs its
production call site hands the App.

Run: python3 tests/test_tmux_default_session_resolvers.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import contextlib
import random
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
    DEFAULT_SESSION_PROBLEM_SHAPES,
    DEFAULT_TMUX_SESSION,
    _read_default_session,
    load_tmux_defaults,
    parse_default_session_unreadable,
    read_default_session_status,
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
    # t1811 readable positive controls — `#` is a comment only first or after a
    # space, and only a space separates (NBSP is content). The NBSP rows were
    # red on the pre-t1811 Python twin, which cut and trimmed at any `\s`.
    ("hash kept: team#1", _row(" team#1"), "team#1"),
    ("hash kept: a#b#c", _row(" a#b#c"), "a#b#c"),
    ("hash kept: x#", _row(" x#"), "x#"),
    ("hash kept: a##b", _row(" a##b"), "a##b"),
    ("hash kept, then a real comment", _row(" team#1 # note"), "team#1"),
    ("tab inside a comment", _row(" x # a\tb"), "x"),
    ("colon without a following space", _row(" a:b"), "a:b"),
    ("space before a colon", _row(" a :b"), "a :b"),
    ("non-ascii", _row(" xé"), "xé"),
    ("NBSP before a hash is content", _row(" team #1"), "team #1"),
    ("trailing NBSP is content", _row(" team#1 "), "team#1 "),
    ("NBSP-only value is blank", _row("  "), D),
    ("quoted, comment with no space", _row(' "x"#c'), "x"),
    ("quoted, comment after a space", _row(' "x" #c'), "x"),
    ("literal tab inside quotes", _row(' "a\tb"'), "a\tb"),
    ("single-quoted backslash is literal", _row(" 'a\\tb'"), "a\\tb"),
    ("indicator char not followed by space", _row(" ?x"), "?x"),
    ("lookalike yes_proj", _row(" yes_proj"), "yes_proj"),
    ("lookalike 2024proj", _row(" 2024proj"), "2024proj"),
    ("lookalike 2024-1-1", _row(" 2024-1-1"), "2024-1-1"),
    ("x-y", _row(" x-y"), "x-y"),
    # t1811 structure the line parsers now follow like YAML
    ("quoted key", b'tmux:\n  "default_session": qk\n', "qk"),
    ("space before the key colon", b"tmux:\n  default_session : sp\n", "sp"),
    ("BOM", "﻿tmux:\n  default_session: bom\n".encode(), "bom"),
    ("tmux block with an anchor", b"tmux: &t\n  default_session: anc\n", "anc"),
    ("tmux block with the !!map tag", b"tmux: !!map\n  default_session: tagged\n", "tagged"),
    ("tmux header with a comment", b"tmux: # c\n  default_session: cm\n", "cm"),
    ("deeper comment after the value",
     b"tmux:\n  default_session: foo\n    # c\n  default_split: h\n", "foo"),
    ("later tmux block holds the key",
     b"tmux:\n  default_split: h\ntmux:\n  default_session: b\n", "b"),
    ("flow tmux block without the key", b"tmux: {default_split: h}\n", D),
]

# Typed by YAML, but `str()` is the source text, so every resolver still agrees.
ROUND_TRIP_ROWS: list[tuple[str, bytes, str]] = [
    ("canonical int 5", _row(" 5"), "5"),
    ("canonical int 0", _row(" 0"), "0"),
    ("canonical int -7", _row(" -7"), "-7"),
    ("True", _row(" True"), "True"),
    ("False", _row(" False"), "False"),
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

LEGACY_SHAPES = {
    "flow mapping": "flow_mapping",
    "folded block scalar": "block_scalar",
    "literal block scalar": "block_scalar",
    "typed bool": "typed_scalar",
    "typed octal int": "typed_scalar",
}

# Values the line parsers cannot read faithfully: (fixture, config, expected
# shape, what a pre-t1811 line parser returned). The last column is what
# `test_every_row_is_a_real_divergence` checks YAML disagrees with.
UNREADABLE_ROWS: list[tuple[str, bytes, str, str]] = [
    ("tab before a comment", _row(" mysess\t# c"), "tab_or_control", "mysess"),
    ("trailing tab", _row(" mysess\t"), "tab_or_control", "mysess"),
    ("tab inside a plain value", _row(" my\tsess"), "tab_or_control", "my\tsess"),
    ("tab after the separator", _row(" \tmysess"), "tab_or_control", "mysess"),
    ("tab right after the colon", _row("\tx"), "tab_or_control", "x"),
    ("tab after a closing quote", _row(' "x"\t'), "tab_or_control", "x"),
    ("DEL", _row(" x\x7f"), "tab_or_control", "x\x7f"),
    ("NEL", _row(" a\x85b"), "tab_or_control", "a\x85b"),
    ("line separator", _row(" a b"), "tab_or_control", "a b"),
    ("content after a closing quote", _row(' "x" y'), "trailing_content", "x"),
    ("backslash escape", _row(' "a\\tb"'), "quoted_escape", "a\\tb"),
    ("doubled single quote", _row(" 'it''s'"), "quoted_escape", "it"),
    ("unclosed quote", _row(' "x'), "continuation", "x"),
    ("missing separator", _row("mysess"), "missing_separator", "mysess"),
    ("missing separator, quoted", _row('"x"'), "missing_separator", "x"),
    ("mapping indicator", _row(" a: b"), "mapping_indicator", "a: b"),
    ("trailing colon", _row(" a:"), "mapping_indicator", "a:"),
    ("anchor", _row(" &a x"), "node_property", "&a x"),
    ("alias", _row(" *a"), "node_property", "*a"),
    ("tag", _row(" !!str 0123"), "node_property", "!!str 0123"),
    ("flow sequence value", _row(" [a]"), "flow_collection", "[a]"),
    ("flow mapping value", _row(" {a: b}"), "flow_collection", "{a: b}"),
    ("block scalar with indicators", _row(" >2-"), "block_scalar", ">2-"),
    ("dash and space", _row(" - x"), "indicator", "- x"),
    ("leading comma", _row(" ,x"), "indicator", ",x"),
    ("hex int", _row(" 0x1F"), "typed_scalar", "0x1F"),
    ("underscore int", _row(" 1_000"), "typed_scalar", "1_000"),
    ("signed int", _row(" +5"), "typed_scalar", "+5"),
    ("negative zero", _row(" -0"), "typed_scalar", "-0"),
    ("non-canonical float", _row(" 1.50"), "typed_scalar", "1.50"),
    ("inf", _row(" .inf"), "typed_scalar", ".inf"),
    ("sexagesimal", _row(" 1:30"), "typed_scalar", "1:30"),
    ("merge key", _row(" <<"), "typed_scalar", "<<"),
    ("value key", _row(" ="), "typed_scalar", "="),
    ("bool on", _row(" on"), "typed_scalar", "on"),
    ("bool OFF", _row(" OFF"), "typed_scalar", "OFF"),
    ("plain value continued",
     b"tmux:\n  default_session: foo\n    bar\n", "continuation", "foo"),
    ("empty value continued",
     b"tmux:\n  default_session:\n    bar\n", "continuation", D),
    ("quoted value, then a deeper line",
     b'tmux:\n  default_session: "foo"\n    bar\n', "continuation", "foo"),
    ("comment-only value continued",
     b"tmux:\n  default_session: # c\n    bar\n", "continuation", D),
    ("line shallower than the key",
     b"tmux:\n    default_session: foo\n  bar\n", "continuation", "foo"),
    ("duplicate key (YAML keeps the last)",
     b"tmux:\n  default_session: first\n  default_session: second\n",
     "duplicate_key", "first"),
    ("later tmux block without the key",
     b"tmux:\n  default_session: a\ntmux:\n  default_split: h\n",
     "duplicate_key", "a"),
    ("multi-line flow mapping",
     b"tmux: {\n  default_session: flow2, default_split: h\n}\n",
     "flow_mapping", "flow2, default_split: h"),
    ("flow sequence tmux block",
     b"tmux: [\n  default_session: fs\n]\n", "flow_mapping", "fs"),
    ("non-mapping tmux block",
     b"tmux: foo\n  default_session: hf\n", "invalid_block", "hf"),
    # Tags on the tmux header: only `!!map` is supported (see PARITY_ROWS).
    ("unknown tag on the tmux header",
     b"tmux: !foo\n  default_session: x\n", "invalid_block", "x"),
    ("!!omap tag on the tmux header",
     b"tmux: !!omap\n  default_session: x\n", "invalid_block", "x"),
    ("!!set tag on the tmux header",
     b"tmux: !!set\n  default_session: x\n", "invalid_block", "x"),
    ("bare anchor indicator on the tmux header",
     b"tmux: &\n  default_session: x\n", "invalid_block", "x"),
]

# Node properties and other inline content after `tmux:`, each followed by an
# indented `default_session: x`. Not expectations: HeaderInvariantTests lets
# PyYAML decide and requires the twins to agree with it or announce.
HEADER_TOKENS = [
    "!foo", "! foo", "!", "!!map", "!!omap", "!!set", "!!pairs", "!!str",
    "!!seq", "!!Map", "!!mapx", "!<tag:yaml.org,2002:map>", "!<!foo>",
    "!!python/dict", "&a", "&a-b_9", "&a:b", "&", "&a !!map", "!!map &a",
    "!!map # c", "&a # c", "# c", "~", "null", "x", "{", "[",
]

# Announced although `str()` of the YAML value happens to equal the text: the
# rule exempts only canonical ints and True/False, so floats and timestamps are
# always reported rather than guessed at.
ANNOUNCED_ROUND_TRIP_ROWS: list[tuple[str, bytes]] = [
    ("float that round-trips", _row(" 1.0")),
    ("date", _row(" 2024-01-01")),
    ("datetime", _row(" 2001-12-14 21:59:43")),
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


def _bash_raw(root: Path) -> subprocess.CompletedProcess:
    """The bash raw reader: stdout value, exit 2 + stderr sentinel when unreadable."""
    return subprocess.run(
        ["bash", "-c", 'source "$1"; _tmux_bootstrap_default_session_raw "$2"',
         "_", str(BOOTSTRAP), str(root)],
        capture_output=True, text=True,
    )


def _sentinel_shape(stderr: str) -> str | None:
    """Test-local parse of the first stderr line — NOT the parser under test."""
    first = stderr.splitlines()[0] if stderr else ""
    m = re.match(r"^DEFAULT_SESSION_UNREADABLE:([a-z_]+):(.+)$", first)
    return m.group(1) if m else None


def _yaml_backed(root: Path) -> str:
    return load_tmux_defaults(root)["default_session"]


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


    def test_line_parsers_fall_back_on_yaml_only_shapes(self):
        """t1811: the line parsers announce these shapes and use the default."""
        self.assertEqual(set(LEGACY_SHAPES), {name for name, _d, _e in LEGACY_ROWS})
        for name, data, _expected in LEGACY_ROWS:
            shape = LEGACY_SHAPES[name]
            with _project(data) as root, self.subTest(fixture=name):
                self.assertEqual(read_default_session_status(root), (D, shape))
                self.assertEqual(_read_default_session(root), D)
                raw = _bash_raw(root)
                self.assertEqual((raw.returncode, raw.stdout), (2, ""))
                self.assertEqual(_sentinel_shape(raw.stderr), shape)
                self.assertEqual(_bash(root), D)


class RoundTripTypedTests(unittest.TestCase):
    def test_every_resolver_returns_the_text(self):
        for name, data, expected in ROUND_TRIP_ROWS:
            with _project(data) as root:
                for resolver, resolve in RESOLVERS.items():
                    with self.subTest(fixture=name, resolver=resolver):
                        self.assertEqual(resolve(root), expected)
                with self.subTest(fixture=name, check="no problem reported"):
                    self.assertIsNone(read_default_session_status(root)[1])
                    self.assertEqual(_bash_raw(root).stderr, "")

    def test_rows_are_typed_and_round_trip(self):
        for name, data, expected in ROUND_TRIP_ROWS:
            with self.subTest(fixture=name):
                value = _yaml_value(data)
                self.assertNotIsInstance(value, str)
                self.assertEqual(str(value), expected)


class ReadableRowsReportNoProblemTests(unittest.TestCase):
    def test_parity_rows_carry_no_sentinel(self):
        """Negative control for the unreadable rows: a readable value is silent."""
        for name, data, _expected in PARITY_ROWS:
            with _project(data) as root, self.subTest(fixture=name):
                self.assertIsNone(read_default_session_status(root)[1])
                raw = _bash_raw(root)
                self.assertEqual(raw.returncode, 0)
                self.assertEqual(raw.stderr, "")


class UnreadableScalarTests(unittest.TestCase):
    def test_both_twins_report_the_shape_and_use_the_default(self):
        for name, data, shape, _naive in UNREADABLE_ROWS:
            with _project(data) as root, self.subTest(fixture=name):
                self.assertIn(shape, DEFAULT_SESSION_PROBLEM_SHAPES)
                self.assertEqual(read_default_session_status(root), (D, shape))
                raw = _bash_raw(root)
                self.assertEqual((raw.returncode, raw.stdout), (2, ""))
                self.assertEqual(_sentinel_shape(raw.stderr), shape)
                self.assertEqual(_bash(root), D)

    def test_every_row_is_a_real_divergence(self):
        """ORACLE CONTROL: YAML disagrees with what a line parser used to read.

        So no row can be a readable value filed here to hide a parity failure.
        A YAML error counts: `load_tmux_defaults` then returns the default.
        """
        for name, data, _shape, naive in UNREADABLE_ROWS:
            with _project(data) as root, self.subTest(fixture=name):
                self.assertNotEqual(_yaml_backed(root), naive)


class HeaderInvariantTests(unittest.TestCase):
    """Whatever follows `tmux:`, the twins match YAML or announce — and agree."""

    def test_header_tokens(self):
        for token in HEADER_TOKENS:
            data = f"tmux: {token}\n  default_session: x\n".encode()
            with _project(data) as root, self.subTest(header=token):
                session, shape = read_default_session_status(root)
                raw = _bash_raw(root)
                b_shape = _sentinel_shape(raw.stderr)
                b_session = D if raw.returncode != 0 or not raw.stdout.strip() \
                    else raw.stdout.rstrip("\n")
                self.assertEqual((b_session, b_shape), (session, shape), "twins disagree")
                if shape is None:
                    self.assertEqual(_yaml_backed(root), session, "silent divergence")
                else:
                    self.assertEqual((session, raw.returncode), (D, 2))


class AnnouncedRoundTripTests(unittest.TestCase):
    def test_floats_and_timestamps_are_announced(self):
        for name, data in ANNOUNCED_ROUND_TRIP_ROWS:
            with _project(data) as root, self.subTest(fixture=name):
                value = _yaml_value(data)
                self.assertNotIsInstance(value, (str, int, bool))
                self.assertEqual(read_default_session_status(root), (D, "typed_scalar"))
                self.assertEqual(_sentinel_shape(_bash_raw(root).stderr), "typed_scalar")


class StatusApiTests(unittest.TestCase):
    def test_sentinel_parser_round_trips_real_bash_stderr(self):
        with _project(_row(" >-\n    x")) as root:
            stderr = _bash_raw(root).stderr
        self.assertEqual(parse_default_session_unreadable(stderr), "block_scalar")

    def test_sentinel_parser_ignores_other_stderr(self):
        self.assertIsNone(parse_default_session_unreadable(""))
        self.assertIsNone(parse_default_session_unreadable(
            "BOOTSTRAP_FAILED:stale_path\nspawn_session_detached: not an aitasks project\n"))

    def test_invalid_utf8_is_reported_not_raised(self):
        """The pre-t1811 reader raised UnicodeDecodeError out of discovery."""
        with _project(b"tmux:\n  default_session: ok\n  note: \xff\xfe\n") as root:
            self.assertEqual(read_default_session_status(root), (D, "encoding"))
            self.assertEqual(_yaml_backed(root), D)

    def test_missing_config_is_not_a_problem(self):
        with _project(None) as root:
            self.assertEqual(read_default_session_status(root), (D, None))


# --- generated corpus (t1811 post-phase: twin_regex_generated_corpus) ---------

_CORPUS_SEED = 1811
_CORPUS_SIZE = 2000
_CORPUS_CHARS = list("0123456789_.:-+xboeE#azAZnulTr\"' ") + [
    "\t", " ", "\x7f", "é"]
_CORPUS_WORDS = [
    "yes", "Yes", "YES", "no", "No", "NO", "true", "True", "TRUE", "false",
    "False", "FALSE", "on", "On", "ON", "off", "Off", "OFF", "y", "n",
    "~", "null", "Null", "NULL", "nULL", "inf", ".inf", "-.Inf", ".NaN", "nan",
    "2024-01-01", "2024-1-1", "2001-12-14 21:59:43", "12:30", "1:60", "0x", "0b",
    "0o", "<<", "=", "1e5", "1.0e+5", "#", " #", "a#", "#b", " # c", "team",
    "\\", "''", "|", ">", "[", "{", "&", "*", "!", ",", "%", "@", "`",
    "- ", "? ", ": ", " ", "\x85",
]


def _corpus_values() -> list[str]:
    rng = random.Random(_CORPUS_SEED)
    values = []
    for _ in range(_CORPUS_SIZE):
        parts = []
        for _p in range(rng.randint(1, 4)):
            if rng.random() < 0.4:
                parts.append(rng.choice(_CORPUS_WORDS))
            else:
                parts.append("".join(rng.choice(_CORPUS_CHARS)
                                     for _c in range(rng.randint(1, 4))))
        token = "".join(parts)
        roll = rng.random()
        if roll < 0.12:
            token = '"' + token + '"' + rng.choice(["", " # c", "#c", " y", "  "])
        elif roll < 0.2:
            token = "'" + token + "'" + rng.choice(["", " # c", "#c", " y"])
        values.append((" " if rng.random() < 0.92 else "") + token)
    return values


class GeneratedCorpusInvariantTests(unittest.TestCase):
    """Both twins against PyYAML over a seeded, unfiltered corpus.

    No character class is dropped — hashes, spaces, tabs, NBSP, DEL and quotes
    all reach the readers, and the oracle decides. One bash process scans every
    fixture so the corpus stays fast.
    """

    def test_every_value_is_read_like_yaml_or_announced_and_twins_agree(self):
        values = _corpus_values()
        with tempfile.TemporaryDirectory() as tmp:
            roots = []
            for i, value in enumerate(values):
                root = Path(tmp) / f"c{i}"
                (root / "aitasks" / "metadata").mkdir(parents=True)
                (root / "aitasks" / "metadata" / "project_config.yaml").write_bytes(
                    _row(value))
                roots.append(str(root))
            script = (
                'source "$1"; shift; err=$(mktemp); '
                'for r in "$@"; do '
                '  rc=0; out=$(_tmux_bootstrap_default_session_raw "$r" 2>"$err") || rc=$?; '
                '  printf "%s\\t%s\\t%s\\0" "$rc" "$(head -n1 "$err")" "$out"; '
                'done; rm -f "$err"'
            )
            done = subprocess.run(["bash", "-c", script, "_", str(BOOTSTRAP), *roots],
                                  capture_output=True, check=True)
            records = done.stdout.split(b"\0")[:-1]
            self.assertEqual(len(records), len(values))

            failures = []
            kept_hash = cut_comment = fell_back = agreed = 0
            for value, root, rec in zip(values, roots, records):
                rc_s, sentinel, out = rec.decode("utf-8").split("\t", 2)
                rc, b_shape = int(rc_s), _sentinel_shape(sentinel)
                b_session = D if rc != 0 or not out.strip() else out
                p_session, p_shape = read_default_session_status(Path(root))
                yaml_session = _yaml_backed(Path(root))

                if (b_session, b_shape) != (p_session, p_shape):
                    failures.append(("twin", value, (b_session, b_shape), (p_session, p_shape)))
                if p_shape is None:
                    if yaml_session != p_session:
                        failures.append(("silent divergence", value, yaml_session, p_session))
                    if rc != 0:
                        failures.append(("readable but bash rc", value, rc))
                else:
                    if not (p_session == D and rc == 2 and b_shape == p_shape):
                        failures.append(("announcement", value, rc, b_shape, p_shape))

                if p_shape is None and p_session != D:
                    agreed += 1
                    if "#" in p_session:
                        kept_hash += 1
                    if " #" in value.lstrip(" ") and "#" not in p_session:
                        cut_comment += 1
                if p_shape is not None:
                    fell_back += 1

        self.assertFalse(failures, f"{len(failures)} failures, first: {failures[:5]}")
        for label, count in (("kept hash", kept_hash), ("cut comment", cut_comment),
                             ("fell back", fell_back), ("agreed with YAML", agreed)):
            with self.subTest(floor=label):
                self.assertGreaterEqual(count, 50, f"generator produced only {count}")


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
