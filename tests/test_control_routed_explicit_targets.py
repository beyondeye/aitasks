"""Every tmux command routed through the control client names its target (t2051).

The monitor's control client lives in the framework's helper session
(`_ait_control`), not in the project session. A command sent through it that
relies on "the current session" therefore acts on the helper: `display-message
-p '#S'` answers the helper's name, `run-shell` starts in the helper's cwd
(`/`). Two such calls existed when the client moved; both got an explicit `-t`.
This test is that audit made permanent, so the next one cannot slip in quietly.

It walks the AST of every Python file under `.aitask-scripts/` for calls that
hand an argv to the control route, and fails on:

- **untargeted** — an argv written as a list literal (directly, or assigned to a
  local name in the same function) that carries no ``"-t"`` and is not one of
  the target-free commands allowlisted below, each with its reason;
- **unreviewed** — an argv built some other way (a helper call, a parameter)
  at a site that is not in the reviewed list. A static scan cannot see inside
  those, so each one is pinned by file, function and expression after a human
  (or agent) looked at what it builds. A new site fails until it is added here.

Self-control: the same scanner is run over synthetic sources and must flag an
untargeted literal and an unreviewed builder, and pass a targeted one.

Run:
  python3 tests/test_control_routed_explicit_targets.py
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"

#: Callables that send an argv down the control route, and the position of the
#: argv among their positional arguments.
ROUTED = {
    "tmux_run": 0,
    "tmux_run_async": 0,
    "_tmux_async": 0,
    "request_sync": 0,
    "request_async": 0,
    "run_via_control": 1,          # (backend, args)
    "run_async_via_control": 1,
}
#: The parameter every routed callable names its argv.
ARGV_KEYWORD = "args"

#: `TmuxControlClient.request` — the client's own queries. The bare name is too
#: common to scan for everywhere, so it is scanned only where the client lives.
CLIENT_REQUEST_FILE = "monitor/monitor_core.py"

#: Commands that need no target: ``verb -> (required flag or None, reason)``.
TARGET_FREE = {
    "list-sessions": (None, "server-wide: lists every session"),
    "list-panes": ("-a", "server-wide with -a: lists every pane of every session"),
    "list-clients": (None, "server-wide: lists every client (the sitrep jump "
                           "re-checks its initiator by name and pid, t2338)"),
    "delete-buffer": ("-b", "names a paste buffer, which belongs to the server"),
}

#: Functions whose target-free commands are deliberate: they ask the control
#: client about the session IT is in. ``(file, function) -> reason``.
SELF_QUERIES = {
    ("monitor/monitor_core.py", "_verify_attach"):
        "post-attach check: where is this client, and is that session's own "
        "marker ours — the helper is the subject, so there is no target to name",
}

#: Reviewed sites whose argv is not a literal: ``(file, function, expression)``.
#: Each was read to confirm what it builds carries a target (or is target-free
#: by the table above). Add a site only after doing the same.
REVIEWED = {
    # The dispatchers themselves: they forward a caller's argv unchanged.
    ("lib/tmux_exec.py", "run_via_control", "args"),
    ("lib/tmux_exec.py", "run_async_via_control", "args"),
    ("monitor/monitor_core.py", "tmux_run", "args"),
    ("monitor/monitor_core.py", "_tmux_async", "args"),
    ("monitor/monitor_core.py", "tmux_run_async", "args"),
    ("monitor/monitor_core.py", "request_sync", "args"),
    ("monitor/monitor_core.py", "request_async", "args"),
    # `list-panes -a` builders (server-wide).
    ("monitor/monitor_core.py", "find_shadow_pane_status", "shadow_query_args()"),
    ("monitor/monitor_core.py", "find_shadow_pane_info_async", "shadow_query_args()"),
    ("monitor/monitor_core.py", "find_scratchpad_pane_status", "scratchpad_query_args()"),
    ("monitor/monitor_core.py", "find_sitrep_roles", "sitrep_query_args()"),
    # `capture-pane ... -t <pane>` builder (`_capture_args`).
    ("monitor/monitor_core.py", "capture_pane",
     "self._capture_args(pane_id, capture_lines, pane.session_name)"),
    ("monitor/monitor_core.py", "capture_pane_async",
     "self._capture_args(pane_id, capture_lines, pane.session_name)"),
    ("monitor/monitor_core.py", "capture_pane_content_async",
     "self._capture_args(pane_id, capture_lines, pane.session_name)"),
    # `set-option -p -t <pane>` builder (`_shadow_phase_stamp_args`).
    ("monitor/monitor_core.py", "refresh_shadow_phase_stamp", "args"),
    ("monitor/monitor_core.py", "refresh_shadow_phase_stamp_async", "args"),
    # The two calls t2051 gave an explicit target, now behind builders.
    ("monitor/monitor_app.py", "_read_attached_session",
     "self._attached_session_args()"),
    ("monitor/monitor_shared.py", "_run_frozen_detached",
     "self._frozen_detached_args(argv)"),
    # The client's own project check is a literal; nothing to pin for it.
}


def _constants(node: ast.List) -> list[str]:
    return [e.value for e in node.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def _literal_problem(node: ast.List) -> str | None:
    """Why this argv literal is untargeted, or None when it is fine."""
    consts = _constants(node)
    if "-t" in consts:
        return None
    verb = consts[0] if consts else ""
    if verb in TARGET_FREE:
        flag, _reason = TARGET_FREE[verb]
        if flag is None or flag in consts:
            return None
    return f"no -t in {ast.unparse(node)}"


class _Scanner(ast.NodeVisitor):
    def __init__(self, rel: str, scan_request: bool):
        self.rel = rel
        self.scan_request = scan_request
        self.stack: list[ast.AST] = []
        self.findings: list[tuple[str, str, int, str]] = []

    def _visit_function(self, node):
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def _function(self):
        return self.stack[-1] if self.stack else None

    def _local_literals(self, name: str) -> list[ast.List]:
        """List literals assigned to ``name`` in the enclosing function."""
        func = self._function()
        if func is None:
            return []
        found = []
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
                if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                    found.append(node.value)
        return found

    def visit_Call(self, node: ast.Call):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        index = ROUTED.get(name)
        if index is None and name == "request" and self.scan_request:
            index = 0
        if index is not None:
            # The argv may be passed by keyword. Every routed callable names
            # that parameter `args`; a call that passes it neither way is not
            # sending an argv this scanner can see.
            by_keyword = [k.value for k in node.keywords if k.arg == ARGV_KEYWORD]
            if len(node.args) > index:
                self._check(node, node.args[index])
            elif by_keyword:
                self._check(node, by_keyword[0])
        self.generic_visit(node)

    def _check(self, call: ast.Call, argv: ast.AST):
        func = self._function()
        func_name = func.name if func is not None else "<module>"
        literals = [argv] if isinstance(argv, ast.List) else []
        if not literals and isinstance(argv, ast.Name):
            literals = self._local_literals(argv.id)
        if (self.rel, func_name) in SELF_QUERIES:
            return
        if literals:
            for lit in literals:
                problem = _literal_problem(lit)
                if problem:
                    self.findings.append(("untargeted", self.rel, call.lineno,
                                          f"{func_name}: {problem}"))
            return
        site = (self.rel, func_name, ast.unparse(argv))
        if site not in REVIEWED:
            self.findings.append(("unreviewed", self.rel, call.lineno,
                                  f"{func_name}: argv is {site[2]!r}"))


def scan(root: Path) -> list[tuple[str, str, int, str]]:
    findings = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(), filename=str(path))
        scanner = _Scanner(rel, scan_request=(rel == CLIENT_REQUEST_FILE))
        scanner.visit(tree)
        findings += scanner.findings
    return findings


def reviewed_sites_present(root: Path) -> set[tuple[str, str, str]]:
    """The REVIEWED entries that still match a real call site."""
    present = set()
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(), filename=str(path))

        class Collect(_Scanner):
            def _check(inner, call, argv):  # noqa: N805
                func = inner._function()
                name = func.name if func is not None else "<module>"
                present.add((inner.rel, name, ast.unparse(argv)))

        Collect(rel, scan_request=(rel == CLIENT_REQUEST_FILE)).visit(tree)
    return present


class ControlRoutedTargetsTest(unittest.TestCase):

    def test_every_control_routed_command_names_its_target(self):
        findings = scan(SCRIPTS)
        self.assertEqual(
            findings, [],
            "control-routed tmux commands without an explicit target, or built "
            "at a site nobody reviewed:\n" + "\n".join(
                f"  [{kind}] {rel}:{line}  {what}" for kind, rel, line, what in findings))

    def test_reviewed_list_has_no_dead_entries(self):
        # A stale entry would silently pre-approve a future site that happens
        # to reuse the same function name and expression.
        dead = REVIEWED - reviewed_sites_present(SCRIPTS)
        self.assertEqual(dead, set(), f"REVIEWED entries matching no call site: {dead}")

    def test_scan_covers_the_known_sites(self):
        # The scanner must actually be looking at the files that matter.
        present = reviewed_sites_present(SCRIPTS)
        files = {rel for rel, _, _ in present}
        for rel in ("monitor/monitor_core.py", "monitor/monitor_app.py",
                    "monitor/monitor_shared.py", "lib/tmux_exec.py"):
            self.assertIn(rel, files)
        self.assertGreater(len(present), 40)


class ScannerSelfControlTest(unittest.TestCase):
    """The scanner flags what it should, on planted sources."""

    def run_on(self, source: str, rel: str = "planted.py"):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source)
            return [(kind, what) for kind, _, _, what in scan(Path(tmp))]

    def test_untargeted_literal_is_flagged(self):
        found = self.run_on(
            "def f(m):\n    return m.tmux_run(['display-message', '-p', '#S'])\n")
        self.assertEqual([k for k, _ in found], ["untargeted"])
        self.assertIn("display-message", found[0][1])

    def test_untargeted_local_assignment_is_flagged(self):
        found = self.run_on(
            "async def f(m):\n    cmd = ['run-shell', '-b', 'x']\n"
            "    return await m.tmux_run_async(cmd)\n")
        self.assertEqual([k for k, _ in found], ["untargeted"])

    def test_backend_argv_position(self):
        found = self.run_on(
            "def f(t, b):\n    return t.run_via_control(b, ['kill-pane'])\n")
        self.assertEqual([k for k, _ in found], ["untargeted"])

    def test_keyword_argv_is_scanned_like_a_positional_one(self):
        cases = {
            "def f(m):\n    return m.tmux_run(args=['display-message', '-p', '#S'])\n":
                ["untargeted"],
            "def f(m):\n    return m.tmux_run(timeout=2, args=['kill-pane'])\n":
                ["untargeted"],
            # the gateway wrapper: backend positional, argv by keyword
            "def f(t, b):\n    return t.run_via_control(b, args=['kill-pane'])\n":
                ["untargeted"],
            "def f(t, b):\n    return t.run_via_control(backend=b, args=['kill-pane'])\n":
                ["untargeted"],
            "def f(m):\n    return m.request_sync(args=build())\n": ["unreviewed"],
            "def f(m, p):\n    return m.tmux_run(args=['kill-pane', '-t', p])\n": [],
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual([k for k, _ in self.run_on(source)], expected)

    def test_unreviewed_builder_is_flagged(self):
        found = self.run_on("def f(m):\n    return m.tmux_run(build_it())\n")
        self.assertEqual([k for k, _ in found], ["unreviewed"])

    def test_targeted_and_target_free_pass(self):
        found = self.run_on(
            "def f(m, p):\n"
            "    m.tmux_run(['send-keys', '-t', p, '--', 'Enter'])\n"
            "    m.tmux_run(['list-panes', '-a', '-F', '#{pane_id}'])\n"
            "    m.tmux_run(['delete-buffer', '-b', 'x'])\n"
            "    m.request_sync(['list-sessions', '-F', '#S'])\n")
        self.assertEqual(found, [])

    def test_list_panes_without_dash_a_is_flagged(self):
        found = self.run_on("def f(m):\n    m.tmux_run(['list-panes', '-F', 'x'])\n")
        self.assertEqual([k for k, _ in found], ["untargeted"])

    def test_bare_request_is_scanned_only_in_the_client_file(self):
        src = "def f(c):\n    return c.request(['display-message', '-p', '#S'])\n"
        self.assertEqual(self.run_on(src), [])
        self.assertEqual([k for k, _ in self.run_on(src, CLIENT_REQUEST_FILE)],
                         ["untargeted"])


if __name__ == "__main__":
    unittest.main()
