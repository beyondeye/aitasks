"""The By-Trail App half and its host contract (t1794_5).

`board_trail_screen.TrailScreenMixin` carries the By-Trail view's state,
workers, actions and launch; an App hosts it by providing the `TrailHost`
surface. `KanbanApp` is the first host and the stand-alone trails app (t1794_6)
the second, so the contract is pinned per host here rather than assumed:

* **Host surface.** Every `TrailHost` member is present on the host instance,
  every `MANAGER_MEMBERS` entry on its manager, every `REQUIRED_WIDGETS`
  selector resolves once the App is mounted, and the board-only capabilities
  answer as the host intends. `HOSTS` is the parametrisation point child 6
  extends.
* **One owner for the trail keys (C10).** The trail `Binding` objects the board
  declares ARE `TRAIL_BINDINGS` — identity, not equality — so a shortcut
  override resolves once for every host.
* **The `T` policy seam.** `action_trail_task` launches exactly what the host's
  `_trail_task_target` returns. The board's resolution (focused card, By-Topic
  lane root, gated views) is exercised end to end on a real board with only the
  outward launch seam stubbed.
* **`run_dialog_command` hook.** The shared dispatcher hands its post-run
  refresh to `_after_dialog_command(refocus_filename)`.
* **Inert-patch guard (C3).** The trail paths read their callees from
  `board_trail_screen`; the board still re-exports several of them. A test that
  stubs one of those on the board instead is green for the wrong reason, so the
  names only the mixin reads are computed from the two module ASTs and any such
  patch in `tests/` is a finding.

Every checker is a pure function with a negative control that feeds a synthetic
offender through the same function. Reaches the board only through the fixture
harness (`self.ab`), never by a canonical import.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_trail_screen_host_protocol.py -q
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

BOARD_DIR = REPO_ROOT / ".aitask-scripts" / "board"
TESTS_DIR = REPO_ROOT / "tests"

#: The hosts held to the contract: `(label, factory over the board module ->
#: zero-arg App constructor, the board-only capabilities the host CLAIMS)`.
#: The board provides every capability; the stand-alone trails app (t1794_6)
#: provides none — its `M` / `S` keys are declared for shortcut ownership and
#: refused by the mixin's capability guard. Both answers are asserted, so a
#: host that grew a capability member by accident is a finding, not a pass.
HOSTS = [
    ("KanbanApp", lambda ab: ab.KanbanApp,
     {"trail_move_wave", "trail_sync"}),
    ("TrailsApp", lambda ab: bf.make_trails_app, set()),
]

#: The `TrailHost` surface as reviewed for t1794_5. Pinned so an emptied or
#: truncated Protocol cannot make every host conform.
EXPECTED_MEMBERS = {
    "manager", "tasks_dir", "base_filter", "sub_title", "title",
    "refresh_board", "_focused_card", "_modal_is_active", "_get_focused_col_id",
    "_queue_refocus", "apply_filter", "refresh_bindings", "_banner_budget",
    "_after_dialog_command", "_trail_task_target", "notify", "push_screen",
    "pop_screen", "set_interval", "call_after_refresh", "query_one", "query",
    "suspend",
}


# --- pure checkers ------------------------------------------------------------


def _protocol_members(protocol) -> set[str]:
    """Instance attributes and methods a `typing.Protocol` declares.

    Unlike `test_board_widgets._protocol_members`, private (`_name`) members
    count — most of the trail host surface is private. Class-level constants
    (`ClassVar`) and dunders do not."""
    members = {name for name, ann in inspect.get_annotations(protocol).items()
               if "ClassVar" not in str(ann)}
    members |= {name for name, value in vars(protocol).items()
                if inspect.isfunction(value) and not name.startswith("__")}
    return members


def _missing_members(names, obj) -> list[str]:
    return sorted(n for n in names if not hasattr(obj, n))


def _claimed_capabilities(ts, app) -> set[str]:
    """The board-only trail actions `app` answers for, per the mixin's guard."""
    return {action for action in ts.TRAIL_ACTION_CAPABILITIES
            if app._has_trail_capability(action)}


def _missing_widgets(app, selectors) -> list[str]:
    missing = []
    for selector in selectors:
        try:
            app.query_one(selector)
        except Exception:
            missing.append(selector)
    return missing


def _binding_identity_findings(trail_bindings, host_bindings) -> list[str]:
    """Every trail binding declared by the host as the SAME object, exactly once,
    and no host binding carrying a trail action that is not one of them."""
    findings = []
    trail_actions = {b.action for b in trail_bindings}
    for b in trail_bindings:
        count = sum(1 for h in host_bindings if h is b)
        if count != 1:
            findings.append(f"{b.action}: declared {count} time(s) by identity")
    for h in host_bindings:
        if (getattr(h, "action", None) in trail_actions
                and not any(h is b for b in trail_bindings)):
            findings.append(f"{h.action}: a copy, not the shared Binding")
    return findings


_BOARD_ALIASES = {"ab", "self.ab", "cls.ab", "B", "board", "aitask_board"}


def _module_bindings(tree: ast.Module) -> set[str]:
    """Names a module binds at top level (imports, defs, classes, assignments)."""
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _loaded_names(tree: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _mixin_only_names(screen_source: str, board_source: str) -> set[str]:
    """Globals the trail screen reads that the board never reads itself.

    The board's re-export of such a name is not on any board code path, so a
    stub placed on the board cannot affect the trail path that reads it."""
    screen = ast.parse(screen_source)
    return ((_loaded_names(screen) & _module_bindings(screen))
            - _loaded_names(ast.parse(board_source)))


def _inert_board_patches(sources: dict[str, str], names: set[str]) -> list[str]:
    """`patch.object(<board>, "<name>")`, `<board>.<name> = …` and
    `setattr(<board>, "<name>", …)` (incl. via `addCleanup`) for `names`."""
    findings = []
    for label, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            target = attr = None
            if isinstance(node, ast.Call):
                func = ast.unparse(node.func)
                args = node.args
                if func.endswith("patch.object") and len(args) >= 2:
                    target, attr = args[0], args[1]
                elif func == "setattr" and len(args) >= 2:
                    target, attr = args[0], args[1]
                elif (func.endswith("addCleanup") and len(args) >= 3
                      and ast.unparse(args[0]) == "setattr"):
                    target, attr = args[1], args[2]
                if not (isinstance(attr, ast.Constant)
                        and isinstance(attr.value, str)):
                    continue
                name = attr.value
            elif isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = (node.targets if isinstance(node, ast.Assign)
                           else [node.target])
                hit = next((t for t in targets if isinstance(t, ast.Attribute)
                            and ast.unparse(t.value) in _BOARD_ALIASES), None)
                if hit is None:
                    continue
                target, name = hit.value, hit.attr
            else:
                continue
            if ast.unparse(target) in _BOARD_ALIASES and name in names:
                findings.append(f"{label}:{node.lineno}: {name} stubbed on "
                                f"{ast.unparse(target)}")
    return findings


def _mixin_host_reads(source: str) -> set[str]:
    """Every `self.<name>` the mixin READS without defining it itself.

    Definitions are the class's own methods and every `self.<name> = …`
    assignment anywhere in its body (`_init_trail_state` and the workers).
    Everything else the mixin reads off `self` is host surface — whether or not
    `TrailHost` lists it — and is what the sweep holds a host to. `self.app`
    is Textual's own and excluded."""
    tree = ast.parse(source)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "TrailScreenMixin")
    defined = {n.name for n in cls.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    reads: set[str] = set()
    for node in ast.walk(cls):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "self":
            if isinstance(node.ctx, ast.Store):
                defined.add(node.attr)
            else:
                reads.add(node.attr)
    return {r for r in reads if r not in defined and r != "app"}


def _answers(host, name: str) -> bool:
    """Whether `host` has `name` — on its class (a property that raises before
    the App is mounted, e.g. `screen`, still counts) or on the instance."""
    if hasattr(type(host), name):
        return True
    try:
        return hasattr(host, name)
    except Exception:
        return True


def _guarded_capability_reads(source: str, capabilities: dict) -> tuple[set[str], list[str]]:
    """Split the mixin's capability-member reads into guarded and unguarded.

    A read of `self.<member>` is GUARDED when the method it sits in opens with
    `if not self._has_trail_capability("<action>"): return …` for an action
    whose capability tuple names that member — the guard the mixin promises
    (`_has_trail_capability`'s docstring) and the reason a host may leave the
    member undefined. Anything else — a read in a method with no such guard,
    or guarded by the wrong action, or before the guard — is reported as
    `"<method>: <member>"`. Returns `(guarded_members, findings)`."""
    tree = ast.parse(source)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "TrailScreenMixin")
    member_actions = {m: a for a, members in capabilities.items() for m in members}
    guarded: set[str] = set()
    findings: list[str] = []
    for fn in cls.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # The actions this method's leading guard(s) establish: `if not
        # self._has_trail_capability("x"): return` statements before any read.
        established: set[str] = set()
        for stmt in fn.body:
            test = getattr(stmt, "test", None)
            if (isinstance(stmt, ast.If) and isinstance(test, ast.UnaryOp)
                    and isinstance(test.op, ast.Not)
                    and isinstance(test.operand, ast.Call)
                    and isinstance(test.operand.func, ast.Attribute)
                    and test.operand.func.attr == "_has_trail_capability"
                    and test.operand.args
                    and isinstance(test.operand.args[0], ast.Constant)
                    and not stmt.orelse
                    and len(stmt.body) == 1
                    and isinstance(stmt.body[0], ast.Return)
                    and (stmt.body[0].value is None
                         or (isinstance(stmt.body[0].value, ast.Constant)
                             and stmt.body[0].value.value is None))):
                # Exactly the safe early-return shape: `if not
                # self._has_trail_capability("x"): return` (or `return None`).
                # A guard whose body returns an EXPRESSION is not skipped —
                # `return self._run_sync()` runs on the unsupported host — so
                # it falls through to the read scan below like any statement.
                established.add(test.operand.args[0].value)
                continue
            for node in ast.walk(stmt):
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and node.value.id == "self" and isinstance(node.ctx, ast.Load)
                        and node.attr in member_actions):
                    if member_actions[node.attr] in established:
                        guarded.add(node.attr)
                    else:
                        findings.append(f"{fn.name}: {node.attr}")
    return guarded, sorted(findings)


def _unanswered_reads(reads: set[str], host, guarded_members: set[str]) -> list[str]:
    """Reads the host does not answer and that are not PROVEN guarded."""
    return sorted(r for r in reads
                  if not _answers(host, r) and r not in guarded_members)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- host surface ---------------------------------------------------------------


class HostSurfaceTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """Each host in `HOSTS` provides the whole `TrailHost` surface."""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_the_protocol_names_the_reviewed_surface(self):
        """Anti-vacuity: an empty or truncated Protocol would make any host conform."""
        ts = self.ab.board_trail_screen
        self.assertEqual(_protocol_members(ts.TrailHost), EXPECTED_MEMBERS)
        self.assertEqual(ts.TrailHost.REQUIRED_WIDGETS,
                         ("HeaderTitle", "#trail_summary", "#trail_summary_body",
                          "#board_container"))
        self.assertIn("settings", ts.TrailHost.MANAGER_MEMBERS)
        self.assertEqual(set(ts.TRAIL_ACTION_CAPABILITIES),
                         {"trail_move_wave", "trail_sync"})

    def test_every_host_provides_members_manager_and_capabilities(self):
        ts = self.ab.board_trail_screen
        members = _protocol_members(ts.TrailHost)
        for label, host_of, capabilities in HOSTS:
            with self.subTest(host=label):
                app = host_of(self.ab)()
                self.assertIsInstance(app, ts.TrailScreenMixin)
                self.assertEqual(_missing_members(members, app), [])
                self.assertEqual(
                    _missing_members(ts.TrailHost.MANAGER_MEMBERS, app.manager), [])
                self.assertEqual(_claimed_capabilities(ts, app), capabilities)

    def test_every_host_composes_the_required_widgets(self):
        ts = self.ab.board_trail_screen

        async def go(host_cls):
            app = host_cls()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                return _missing_widgets(app, ts.TrailHost.REQUIRED_WIDGETS)

        for label, host_of, _capabilities in HOSTS:
            with self.subTest(host=label):
                self.assertEqual(self._run(go(host_of(self.ab))), [])

    def test_a_host_claiming_a_capability_it_lacks_is_reported(self):
        """Negative control for the capability half of the row: one member of
        the chain is enough for `hasattr`-style claims to be wrong, and the
        checker reads the mixin's own guard so it cannot drift from it."""
        ts = self.ab.board_trail_screen
        app = bf.make_trails_app()
        self.assertEqual(_claimed_capabilities(ts, app), set())
        app._run_sync = lambda **kw: None
        self.assertEqual(_claimed_capabilities(ts, app), {"trail_sync"})

    def test_a_host_missing_a_member_or_manager_member_is_reported(self):
        ts = self.ab.board_trail_screen
        members = _protocol_members(ts.TrailHost)
        host = types.SimpleNamespace(**{m: None for m in members})
        self.assertEqual(_missing_members(members, host), [],
                         "control: a complete host must pass")
        del host._trail_task_target
        self.assertEqual(_missing_members(members, host), ["_trail_task_target"])
        manager = types.SimpleNamespace(
            **{m: None for m in ts.TrailHost.MANAGER_MEMBERS if m != "settings"})
        self.assertEqual(
            _missing_members(ts.TrailHost.MANAGER_MEMBERS, manager), ["settings"])

    def test_an_app_without_a_required_widget_is_reported(self):
        from textual.app import App
        from textual.containers import Container
        from textual.widgets import Header, Static
        ts = self.ab.board_trail_screen

        class PartialHost(App):
            def compose(self):
                yield Header()
                yield Static(id="trail_summary_body")
                yield Container(id="board_container")

        async def go():
            app = PartialHost()
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                return _missing_widgets(app, ts.TrailHost.REQUIRED_WIDGETS)

        self.assertEqual(self._run(go()), ["#trail_summary"])

    def _stub_host(self, **attrs):
        """A bare `TrailScreenMixin` instance carrying only `attrs`."""
        stub = type("StubHost", (self.ab.board_trail_screen.TrailScreenMixin,),
                    {})()
        for name, value in attrs.items():
            setattr(stub, name, value)
        return stub

    def test_a_host_without_a_capability_neither_answers_nor_runs_it(self):
        ts = self.ab.board_trail_screen
        stub = self._stub_host(
            _modal_is_active=lambda: False, push_screen=MagicMock(),
            _run_sync=MagicMock())
        mixin = ts.TrailScreenMixin
        # Liveness in the same test: with `_run_sync` the action runs.
        self.assertTrue(mixin._has_trail_capability(stub, "trail_sync"))
        mixin.action_trail_sync(stub)
        self.assertEqual(stub.push_screen.call_count, 1)
        stub._run_sync.assert_called_once_with(show_notification=True,
                                               show_overlay=True)
        del stub._run_sync
        stub.push_screen.reset_mock()
        self.assertFalse(mixin._has_trail_capability(stub, "trail_sync"))
        mixin.action_trail_sync(stub)
        stub.push_screen.assert_not_called()
        # Move-wave: one missing member of its chain is enough to refuse.
        caps = ts.TRAIL_ACTION_CAPABILITIES["trail_move_wave"]
        partial = self._stub_host(**{c: None for c in caps[:-1]})
        self.assertFalse(partial._has_trail_capability("trail_move_wave"))
        whole = self._stub_host(**{c: None for c in caps})
        self.assertTrue(whole._has_trail_capability("trail_move_wave"))

    def test_move_wave_refuses_before_reading_any_board_state(self):
        stub = self._stub_host(_modal_is_active=MagicMock(return_value=False),
                               base_filter="bytrail",
                               _focused_card=MagicMock(return_value=None))
        stub.action_trail_move_wave()
        stub._modal_is_active.assert_not_called()
        stub._focused_card.assert_not_called()
        # Liveness in the same test: with the chain present the action proceeds
        # to its own guards.
        caps = self.ab.board_trail_screen.TRAIL_ACTION_CAPABILITIES
        for name in caps["trail_move_wave"]:
            setattr(stub, name, None)
        stub.action_trail_move_wave()
        stub._modal_is_active.assert_called_once_with()
        stub._focused_card.assert_called_once_with()


# --- C10 binding identity ---------------------------------------------------------


class BindingIdentityTests(bf.FixtureBoardTestBase, unittest.TestCase):

    def test_board_declares_the_shared_trail_binding_objects(self):
        ts = self.ab.board_trail_screen
        self.assertEqual(len(ts.TRAIL_BINDINGS), 9)
        self.assertIs(ts.TRAIL_BINDING["trail_select"],
                      next(b for b in ts.TRAIL_BINDINGS
                           if b.action == "trail_select"))
        self.assertEqual(
            _binding_identity_findings(ts.TRAIL_BINDINGS,
                                       self.ab.KanbanApp.BINDINGS), [])

    def test_an_equal_copy_is_reported(self):
        from textual.binding import Binding
        ts = self.ab.board_trail_screen
        shared = ts.TRAIL_BINDING["trail_select"]
        copy = Binding(shared.key, shared.action, shared.description)
        host = [copy if b is shared else b for b in self.ab.KanbanApp.BINDINGS]
        self.assertEqual(
            _binding_identity_findings(ts.TRAIL_BINDINGS, host),
            ["trail_select: declared 0 time(s) by identity",
             "trail_select: a copy, not the shared Binding"])
        doubled = list(self.ab.KanbanApp.BINDINGS) + [shared]
        self.assertEqual(
            _binding_identity_findings(ts.TRAIL_BINDINGS, doubled),
            ["trail_select: declared 2 time(s) by identity"])


# --- the T policy seam ---------------------------------------------------------------


class TrailTaskSeamTests(bf.FixtureBoardTestBase, unittest.TestCase):

    def test_action_launches_exactly_the_host_target(self):
        mixin = self.ab.board_trail_screen.TrailScreenMixin
        stub = types.SimpleNamespace(_trail_task_target=lambda: "42",
                                     _launch_trail=MagicMock())
        mixin.action_trail_task(stub)
        stub._launch_trail.assert_called_once_with(["42"], "42")
        stub._launch_trail.reset_mock()
        stub._trail_task_target = lambda: None
        mixin.action_trail_task(stub)
        stub._launch_trail.assert_not_called()


class TrailTaskRealPathTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """`T` on a real board: the board's `_trail_task_target`, not a stub.

    RICH_TOPOLOGY: t9003 / t9005 carry `anchor: 9002`, t9000_1 / t9000_2 are
    children of t9000, t9004 is a singleton. Only the outward launch seam is
    stubbed (the dialog, the command resolvers and `push_screen`), recording
    what `_launch_trail` would have launched."""

    FIXTURE_TASKS = bf.RICH_TOPOLOGY

    def _run(self, coro):
        return asyncio.run(coro)

    def _seam(self, app):
        ts = self.ab.board_trail_screen
        launches = []

        class FakeScreen:
            def __init__(self, title, full_command, prompt_str, **kwargs):
                launches.append({"prompt_str": prompt_str, **kwargs})
                self.full_command = full_command

        patches = [
            patch.object(ts, "AgentCommandScreen", FakeScreen),
            patch.object(ts, "resolve_dry_run_command",
                         lambda root, op, *a, **k: f"CMD {op}"),
            patch.object(ts, "resolve_agent_string",
                         lambda root, op: "claudecode/test"),
            patch.object(app, "push_screen", lambda screen, cb=None: None),
        ]
        return launches, patches

    async def _focus(self, app, pilot, filename):
        card = next((c for c in app.query(self.ab.TaskCard)
                     if c.task_data.filename == filename), None)
        if card is None:
            self.fail(f"{filename} is not rendered in the {app.base_filter} view")
        card.focus()
        await pilot.pause()
        self.assertIs(app._focused_card(), card)

    async def _press_t(self, app, pilot, launches, patches):
        for ctx in patches:
            ctx.start()
        try:
            await pilot.press("T")
            await pilot.pause()
        finally:
            for ctx in reversed(patches):
                ctx.stop()

    def _call_t(self, app, patches):
        for ctx in patches:
            ctx.start()
        try:
            app.action_trail_task()
        finally:
            for ctx in reversed(patches):
                ctx.stop()

    def _args(self, launches):
        return [launch["operation_args"] for launch in launches]

    def test_all_view_launches_the_focused_task(self):
        async def go():
            app = self.ab.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                await self._focus(app, pilot, "t9003_gamma.md")
                launches, patches = self._seam(app)
                await self._press_t(app, pilot, launches, patches)
                self.assertEqual(self._args(launches), [["9003"]])
                self.assertEqual(launches[0]["prompt_str"], "/aitask-trail 9003")

        self._run(go())

    def test_bytopic_launches_the_lane_root(self):
        async def go():
            app = self.ab.KanbanApp()
            async with app.run_test(size=(220, 60)) as pilot:
                await pilot.pause()
                await pilot.press("y")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.base_filter, "bytopic")
                cases = [("t9003_gamma.md", ["9002"]),      # anchor root
                         ("t9004_delta.md", ["9004"]),      # singleton: own id
                         ("t9000_parent.md", ["9000"])]     # cluster parent
                for filename, expected in cases:
                    with self.subTest(card=filename):
                        await self._focus(app, pilot, filename)
                        launches, patches = self._seam(app)
                        await self._press_t(app, pilot, launches, patches)
                        self.assertEqual(self._args(launches), [expected])

                # A child card: expand its parent so it is rendered, then focus.
                app.expanded_tasks.add("t9000_parent.md")
                app.refresh_board()
                await pilot.pause()
                await pilot.pause()
                await self._focus(app, pilot, "t9000_1_childone.md")
                launches, patches = self._seam(app)
                await self._press_t(app, pilot, launches, patches)
                self.assertEqual(self._args(launches), [["9000"]])

        self._run(go())

    def test_bytopic_root_resolution_is_the_boards_topic_key(self):
        """Mutant, in-process: the board's own `topic_key` decides the root.

        With it neutralised the anchored card falls back to its own id — so the
        test above exercises the board's resolution, not a copy of it."""
        async def go():
            app = self.ab.KanbanApp()
            async with app.run_test(size=(220, 60)) as pilot:
                await pilot.pause()
                await pilot.press("y")
                await pilot.pause()
                await pilot.pause()
                await self._focus(app, pilot, "t9003_gamma.md")
                launches, patches = self._seam(app)
                with patch.object(self.ab, "topic_key", lambda *a: None):
                    self._call_t(app, patches)
                self.assertEqual(self._args(launches), [["9003"]])
                launches.clear()
                self._call_t(app, patches)
                self.assertEqual(self._args(launches), [["9002"]])

        self._run(go())

    def test_gated_views_and_an_open_modal_launch_nothing(self):
        async def go():
            app = self.ab.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                await self._focus(app, pilot, "t9003_gamma.md")
                launches, patches = self._seam(app)

                for view in ("inflight", "bytrail"):
                    with self.subTest(view=view):
                        app.base_filter = view
                        self._call_t(app, patches)
                        self.assertEqual(launches, [])
                        app.base_filter = "all"
                        # Liveness in the same test: the same seam records a
                        # launch once the gate is lifted.
                        self._call_t(app, patches)
                        self.assertEqual(self._args(launches), [["9003"]])
                        launches.clear()

                await app.push_screen(self.ab.LoadingOverlay("busy"))
                await pilot.pause()
                self.assertTrue(app._modal_is_active())
                self._call_t(app, patches)
                self.assertEqual(launches, [])
                app.pop_screen()
                await pilot.pause()
                await self._focus(app, pilot, "t9003_gamma.md")
                self._call_t(app, patches)
                self.assertEqual(self._args(launches), [["9003"]])

        self._run(go())


# --- run_dialog_command hook -------------------------------------------------------------


class DialogCommandHookTests(bf.FixtureBoardTestBase, unittest.TestCase):

    def _dispatch(self, app, terminal, **kwargs):
        ts = self.ab.board_trail_screen
        with patch.object(ts, "find_terminal", return_value=terminal), \
                patch.object(ts, "spawn_in_terminal") as spawn, \
                patch.object(ts.subprocess, "call", return_value=0) as call:
            asyncio.run(self.ab.KanbanApp.run_dialog_command.__wrapped__(
                app, "run-me", **kwargs))
        return spawn, call

    def test_suspend_path_hands_the_refocus_to_the_host_hook(self):
        app = MagicMock()
        _spawn, call = self._dispatch(app, None, refocus_filename="t1_a.md")
        call.assert_called_once_with(["sh", "-c", "run-me"])
        app._after_dialog_command.assert_called_once_with("t1_a.md")

    def test_terminal_path_leaves_the_refresh_to_the_dialog_callback(self):
        app = MagicMock()
        spawn, call = self._dispatch(app, "footerm", refocus_filename="t1_a.md")
        spawn.assert_called_once_with("footerm", ["sh", "-c", "run-me"])
        call.assert_not_called()
        app._after_dialog_command.assert_not_called()

    def test_board_hook_reloads_then_refreshes_with_the_refocus(self):
        app = MagicMock()
        self.ab.KanbanApp._after_dialog_command(app, "t1_a.md")
        self.assertEqual(
            [c[0] for c in app.mock_calls],
            ["manager.load_tasks", "refresh_board"])
        app.refresh_board.assert_called_once_with(refocus_filename="t1_a.md")


# --- C3 inert-patch guard ------------------------------------------------------------------


class InertPatchGuardTests(unittest.TestCase):
    """No test stubs, on the board, a name only the trail screen reads."""

    @classmethod
    def setUpClass(cls):
        cls.names = _mixin_only_names(_read(BOARD_DIR / "board_trail_screen.py"),
                                      _read(BOARD_DIR / "aitask_board.py"))

    def test_computed_names_cover_the_trail_callees(self):
        """Anti-vacuity: the set is computed, so pin what it must contain."""
        self.assertTrue(
            {"discover_trails", "_trail_versions", "run_trail_drift",
             "load_trail_blob", "build_trail_lanes", "TrailSelectScreen"}
            <= self.names, sorted(self.names))
        # Names the board still calls itself are NOT inert on the board — a
        # board stub of these can be live for a board path (pick / work-report
        # launches), so the guard cannot rule on them; their trail-path stubs
        # are proven by mutants instead (see the t1794_5 plan notes).
        for shared in ("resolve_agent_string", "AgentCommandScreen",
                       "launch_in_tmux", "find_terminal", "spawn_in_terminal",
                       "task_own_id"):
            self.assertNotIn(shared, self.names)

    def test_no_test_stubs_a_mixin_only_name_on_the_board(self):
        sources = {p.name: _read(p) for p in sorted(TESTS_DIR.glob("test_*.py"))}
        self.assertEqual(_inert_board_patches(sources, self.names), [],
                         "stub these on ab.board_trail_screen — the board's "
                         "re-export is not on the trail path")

    def test_every_stub_spelling_is_flagged(self):
        offending = {
            "patch_object": 'patch.object(ab, "discover_trails", lambda: ([], []))\n',
            "self_ab": 'patch.object(self.ab, "_trail_versions", list)\n',
            "assignment": "ab.load_trail_blob = fake\n",
            "setattr": 'setattr(ab, "run_trail_drift", fake)\n',
            "add_cleanup": ('self.addCleanup(setattr, ab, "load_trail_blob", '
                            'ab.load_trail_blob)\n'),
        }
        for label, source in offending.items():
            with self.subTest(form=label):
                self.assertEqual(
                    len(_inert_board_patches({label: source}, self.names)), 1)

    def test_owning_module_and_shared_names_are_not_flagged(self):
        benign = (
            'patch.object(ab.board_trail_screen, "discover_trails", f)\n'
            'patch.object(ab.trail_discovery, "load_trail_blob", f)\n'
            'patch.object(ab, "resolve_agent_string", f)\n'
            'patch.object(app, "_trail_versions", f)\n'
            'ab.discover_trails()\n'
        )
        self.assertEqual(_inert_board_patches({"benign": benign}, self.names), [])

    def test_a_name_the_board_reads_itself_is_excluded(self):
        screen = "from x import helper, other\ndef f():\n    helper(); other()\n"
        board = "from x import helper, other\ndef g():\n    return helper\n"
        self.assertEqual(_mixin_only_names(screen, board), {"other"})


class MixinSelfAttributeSweepTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """Post-phase mitigation (t1794_6): every `self.<name>` the mixin reads is
    answered by the stand-alone host, or is a board-only capability member the
    mixin reads ONLY behind `_has_trail_capability`. `TrailHost` is what the
    protocol *says*; this sweep is what the mixin *does*, so an attribute the
    mixin grew without the Protocol noticing — or a capability member reached
    from an unguarded method — surfaces here rather than as an AttributeError
    in `ait trails`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = _read(BOARD_DIR / "board_trail_screen.py")
        cls.reads = _mixin_host_reads(cls.source)
        cls.guarded, cls.guard_findings = _guarded_capability_reads(
            cls.source, cls.ab.board_trail_screen.TRAIL_ACTION_CAPABILITIES)

    def test_the_sweep_sees_the_host_surface(self):
        # Anti-vacuity: three reads of three different kinds — a plain
        # attribute, a host helper, and the policy seam.
        self.assertLessEqual({"manager", "_banner_budget", "_trail_task_target"},
                             self.reads)
        # And it does not report what the mixin defines for itself.
        self.assertNotIn("_trail_gen", self.reads)
        self.assertNotIn("_rerender_trail", self.reads)

    def test_every_capability_read_sits_behind_its_guard(self):
        self.assertEqual(self.guard_findings, [])
        # Anti-vacuity: the two actions' entry members are read, and guarded.
        self.assertLessEqual({"_run_sync", "_review_then"}, self.guarded)

    def test_every_read_is_answered_by_each_host(self):
        for label, host_of, _capabilities in HOSTS:
            with self.subTest(host=label):
                app = host_of(self.ab)()
                self.assertEqual(_unanswered_reads(self.reads, app, self.guarded), [])

    def test_the_trails_app_leans_on_the_capability_guard_for_the_rest(self):
        """What the stand-alone host does NOT answer is exactly the set of
        capability members the mixin reads behind a guard — nothing else."""
        app = bf.make_trails_app()
        gaps = sorted(r for r in self.reads if not _answers(app, r))
        self.assertTrue(gaps, "the trails app is not expected to answer everything")
        self.assertLessEqual(set(gaps), self.guarded)

    def test_an_unlisted_read_is_reported(self):
        injected = self.source.replace(
            "    def _has_trail_capability(self, action: str) -> bool:",
            "    def _probe(self):\n        return self._unlisted_thing\n\n"
            "    def _has_trail_capability(self, action: str) -> bool:", 1)
        self.assertNotEqual(injected, self.source)
        reads = _mixin_host_reads(injected)
        self.assertIn("_unlisted_thing", reads)
        app = bf.make_trails_app()
        self.assertEqual(_unanswered_reads(reads, app, self.guarded),
                         ["_unlisted_thing"])

    def test_an_unguarded_capability_read_is_reported(self):
        """Negative control for the guard half: a capability member read from
        a method with no `_has_trail_capability` guard is a finding, and the
        member no longer counts as guarded for the host check."""
        caps = self.ab.board_trail_screen.TRAIL_ACTION_CAPABILITIES
        injected = self.source.replace(
            "    def _has_trail_capability(self, action: str) -> bool:",
            "    def _probe(self):\n        return self._run_sync()\n\n"
            "    def _has_trail_capability(self, action: str) -> bool:", 1)
        guarded, findings = _guarded_capability_reads(injected, caps)
        self.assertEqual(findings, ["_probe: _run_sync"])
        # The genuine guarded read in action_trail_sync still counts.
        self.assertIn("_run_sync", guarded)
        # A guard whose body RUNS the member (`return self._run_sync()`) is
        # not a guard: the read is inside the statement the old checker
        # skipped, and it executes on exactly the host that lacks the member.
        unsafe = self.source.replace(
            "    def _has_trail_capability(self, action: str) -> bool:",
            "    def _probe(self):\n"
            "        if not self._has_trail_capability(\"trail_sync\"):\n"
            "            return self._run_sync()\n\n"
            "    def _has_trail_capability(self, action: str) -> bool:", 1)
        self.assertNotEqual(unsafe, self.source)
        guarded, findings = _guarded_capability_reads(unsafe, caps)
        self.assertEqual(findings, ["_probe: _run_sync"])
        # A read guarded by the WRONG action is a finding too.
        wrong = self.source.replace(
            'if not self._has_trail_capability("trail_sync"):',
            'if not self._has_trail_capability("trail_move_wave"):', 1)
        self.assertNotEqual(wrong, self.source)
        guarded, findings = _guarded_capability_reads(wrong, caps)
        self.assertEqual(findings, ["action_trail_sync: _run_sync"])
        self.assertNotIn("_run_sync", guarded)
        app = bf.make_trails_app()
        self.assertIn("_run_sync",
                      _unanswered_reads(_mixin_host_reads(wrong), app, guarded))


if __name__ == "__main__":
    unittest.main()
