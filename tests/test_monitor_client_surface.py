"""Tripwire: every monitor attribute the apps use is served by MonitorClient (t2037_2).

`MonitorClient` stands in for `TmuxMonitor` in `ait monitor`, `ait minimonitor`
and applink. In server mode it answers producer reads from the subscription and
delegates only an explicit gateway allowlist (`GATEWAY_NAMES`) to its local
`TmuxMonitor`; any other name raises `AttributeError`, loudly, rather than
silently returning the empty local state. That makes the set of names the apps
reach on their monitor an implicit contract — a new call site that is neither
defined on the client nor allowlisted would crash a TUI in server mode only.

This test makes the contract explicit. It extracts, with `ast` (comments and
strings never count):

- every attribute read on `self._monitor`;
- every attribute read on a local alias bound from `self._monitor` or from
  `getattr(self, "_monitor", …)` in the same function;
- every `getattr(<monitor>, "<name>", …)` probe;

in the files below, and asserts each name is defined on `MonitorClient` or listed
in `GATEWAY_NAMES`. A completeness cross-check requires names known to be used,
so a broken extractor fails instead of passing vacuously, and every gateway name
must exist on `TmuxMonitor` so the allowlist cannot carry a typo.

Run:
  python3 tests/test_monitor_client_surface.py
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

#: Files whose monitor attribute is `self._monitor`.
SCANNED = (
    "monitor/monitor_app.py",
    "monitor/minimonitor_app.py",
    "monitor/monitor_shared.py",
    "applink/router.py",
    "applink/pusher.py",
    "applink/server.py",
)

#: Names known to be used (see the t2037_2 plan's "Read surface" inventory). If
#: the extractor stops finding any of these it is broken, not the apps clean.
KNOWN_USED = frozenset({
    "capture_all_async",              # minimonitor, applink pusher
    "capture_all_classified_async",   # monitor
    "commit_snapshots",               # monitor
    "capture_generation",             # monitor
    "get_shadow_snapshot",            # monitor, minimonitor
    "get_session_to_project_mapping_async",
    "kill_agent_pane_smart",          # monitor apps, applink router
    "last_discovered_agents",         # minimonitor alias `monitor = self._monitor`
    "last_enumerated_sessions",       # monitor_shared getattr probe
    "set_parked_agents",              # monitor_shared getattr probe
    "send_enter",                     # applink router
    "capture_cursor_async",           # applink router
})


def _is_self_monitor(node) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "_monitor"
            and isinstance(node.value, ast.Name) and node.value.id == "self")


def _is_getattr_self_monitor(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "getattr" and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name) and node.args[0].id == "self"
            and isinstance(node.args[1], ast.Constant) and node.args[1].value == "_monitor")


def _aliases(func) -> set[str]:
    names = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and (
                _is_self_monitor(node.value) or _is_getattr_self_monitor(node.value)):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _is_monitor_expr(node, aliases: set[str]) -> bool:
    if _is_self_monitor(node):
        return True
    return isinstance(node, ast.Name) and node.id in aliases


def _names_in(scope, aliases: set[str]) -> set[str]:
    found = set()
    for node in ast.walk(scope):
        if isinstance(node, ast.Attribute) and _is_monitor_expr(node.value, aliases):
            found.add(node.attr)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id in ("getattr", "hasattr") and len(node.args) >= 2
              and _is_monitor_expr(node.args[0], aliases)
              and isinstance(node.args[1], ast.Constant)
              and isinstance(node.args[1].value, str)):
            found.add(node.args[1].value)
    return found


def extract_monitor_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names = _names_in(tree, set())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            aliases = _aliases(node)
            if aliases:
                names |= _names_in(node, aliases)
    return names


def used_names() -> dict[str, set[str]]:
    """``name -> {files}`` over every scanned file."""
    out: dict[str, set[str]] = {}
    for rel in SCANNED:
        path = SCRIPTS / rel
        for name in extract_monitor_names(path.read_text(encoding="utf-8")):
            out.setdefault(name, set()).add(rel)
    return out


class ExtractorTests(unittest.TestCase):
    """The extractor itself, on a synthetic source."""

    def test_extracts_every_access_form_and_ignores_text(self):
        src = (
            "class A:\n"
            "    def f(self):\n"
            "        self._monitor.direct()\n"
            "        monitor = self._monitor\n"
            "        monitor.via_alias\n"
            "        m2 = getattr(self, '_monitor', None)\n"
            "        getattr(m2, 'probed', None)\n"
            "        # self._monitor.in_comment\n"
            "        s = 'self._monitor.in_string'\n"
            "    def g(self):\n"
            "        monitor.not_an_alias_here\n"
        )
        self.assertEqual(extract_monitor_names(src), {"direct", "via_alias", "probed"})


class SurfaceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from monitor import status_client  # noqa: PLC0415 - the module under test
        cls.sc = status_client
        cls.used = used_names()

    def test_known_names_are_extracted(self):
        missing = sorted(KNOWN_USED - set(self.used))
        self.assertEqual(missing, [], "the extractor no longer finds names the apps "
                         "are known to use — fix the extractor, do not edit the list")

    def test_every_used_name_is_served_or_gateway(self):
        client = self.sc.MonitorClient
        unserved = {
            name: sorted(files) for name, files in self.used.items()
            if not hasattr(client, name) and name not in self.sc.GATEWAY_NAMES
        }
        self.assertEqual(
            unserved, {},
            "monitor attributes the apps use that MonitorClient neither defines nor "
            "delegates as gateway — in server mode they would raise AttributeError")

    def test_gateway_names_exist_on_tmux_monitor(self):
        from monitor.monitor_core import TmuxMonitor  # noqa: PLC0415
        instance = TmuxMonitor(session="s")
        missing = sorted(n for n in self.sc.GATEWAY_NAMES if not hasattr(instance, n))
        self.assertEqual(missing, [], "GATEWAY_NAMES lists names TmuxMonitor lacks")

    def test_gateway_and_read_surface_are_disjoint(self):
        both = sorted(self.sc.GATEWAY_NAMES & self.sc.READ_SURFACE_NAMES)
        self.assertEqual(both, [])

    def test_read_surface_is_defined_on_the_client(self):
        missing = sorted(n for n in self.sc.READ_SURFACE_NAMES
                         if not hasattr(self.sc.MonitorClient, n))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
