"""Local `depends:` resolution — one decision core, three agreeing surfaces (t1527).

`ait ls`, the minimonitor task picker and the board used to resolve `depends:`
independently, with three different policies, so they could disagree about the
same task. This module drives all three over **one** fixture set and asserts
their verdicts are identical *to each other* — surface against surface, not each
against a private expectation, which is the only shape that can catch a drift
neither side's own test would notice.

What is covered here:

1. parity over the six discriminating dep shapes, including the two that used to
   split the surfaces (an unresolvable id, and a gate-released upstream);
2. negative controls in BOTH languages — a mutated `ait ls` and a mutated board
   — proving the comparison can fail and naming the surface that broke;
3. render-level assertions for the `(UNRESOLVED)` marker at the minimonitor's
   ~40-column width and in the board detail pane;
4. unit tests for the core's tri-state table and id canonicalization;
5. an instrumented fan-out proving the shared gate evaluator really hoists the
   registry parse and the code digest (the t1472 amortization this must not
   regress), with a negative control that drives the counters to N;
6. the two cache-freshness transitions a file-identity key cannot see;
7. the evaluator-lifetime contract — a new cycle re-decides, within one cycle it
   does not (the t1416 hazard);
8. `find_ready_siblings`, which gained the gate-release rule while keeping its
   deliberate sibling-only scope.

cwd note: the board module must be imported with cwd inside its fixture tree
(`board_fixture` explains why), so this module chdirs. Run it with
`--test-dir`/whole-suite (`--dist loadfile`), never with a path selector that
would split it across workers.

Run: bash tests/run_all_python_tests.sh --test-dir tests
  or: python3 -m unittest tests.test_local_dep_parity -v
"""

from __future__ import annotations

import gzip
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
for _p in (REPO_ROOT / "tests" / "lib", SCRIPTS / "board", SCRIPTS / "lib",
           SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import board_fixture as bf  # noqa: E402
import dep_resolution  # noqa: E402
import gate_ledger  # noqa: E402
from monitor.monitor_core import TaskInfoCache  # noqa: E402

GATES_REFERENCE = SCRIPTS / "gates_reference.yaml"
LS = SCRIPTS / "aitask_ls.sh"

PASS_MARK = "> **✅ gate:{gate}** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human"
PEND_MARK = "> **⏸ gate:{gate}** run=2026-01-01T00:00:00Z status=pending type=human"


# --- fixture construction --------------------------------------------------

def _task_text(status: str, *, depends=(), gates=(), marks=()) -> str:
    fm = ["---", "priority: high", "effort: low",
          "depends: [" + ", ".join(str(d) for d in depends) + "]",
          "issue_type: feature", f"status: {status}"]
    if gates:
        fm.append("gates: [" + ", ".join(gates) + "]")
    fm.append("---")
    body = ["", "# body", ""]
    if marks:
        body += ["## Gate Runs", ""] + list(marks)
    return "\n".join(fm + body) + "\n"


def write_task(tasks: Path, task_id: str, status: str, *, depends=(), gates=(),
               marks=(), archived: bool = False) -> Path:
    base = tasks / "archived" if archived else tasks
    if "_" in task_id:
        parent, child = task_id.split("_", 1)
        d = base / f"t{parent}"
        name = f"t{parent}_{child}_x.md"
    else:
        d = base
        name = f"t{task_id}_x.md"
    d.mkdir(parents=True, exist_ok=True)
    path = d / name
    path.write_text(_task_text(status, depends=depends, gates=gates, marks=marks),
                    encoding="utf-8")
    return path


def make_tree(root: Path) -> Path:
    """A minimal but production-shaped task tree: metadata + the real registry."""
    tree = root / "tree"
    tasks = tree / "aitasks"
    (tasks / "metadata").mkdir(parents=True)
    (tasks / "metadata" / "gates.yaml").write_text(
        GATES_REFERENCE.read_text(encoding="utf-8"), encoding="utf-8")
    (tasks / "metadata" / "labels.txt").write_text("", encoding="utf-8")
    (tasks / "metadata" / "task_types.txt").write_text(
        "feature\nbug\nchore\n", encoding="utf-8")
    (tasks / "metadata" / "board_config.json").write_text(
        '{"columns": [], "column_order": []}\n', encoding="utf-8")
    (tasks / "metadata" / "project_config.yaml").write_text(
        "project:\n  name: fixture\n", encoding="utf-8")
    return tree


#: Dependents keyed by their own id -> the expected verdict of their single dep.
#: The *expectation* is asserted only in the core unit test; the parity test
#: compares surfaces to each other and never to this map, so a wrong expectation
#: here cannot make a real disagreement pass.
DEPENDENTS = {
    "200": ("100", dep_resolution.SATISFIED),     # Done
    "201": ("101", dep_resolution.BLOCKING),      # Ready
    "202": ("102", dep_resolution.SATISFIED),     # archived (Done)
    "203": ("999", dep_resolution.UNRESOLVABLE),  # no file anywhere
    "204": ("103", dep_resolution.SATISFIED),     # Implementing, gates SATISFIED
    "205": ("104", dep_resolution.BLOCKING),      # Implementing, gate pending
    "206": ("50", dep_resolution.UNRESOLVABLE),   # only inside an archive bundle
}


def populate(tasks: Path) -> None:
    """The six discriminating dep shapes, plus their dependents."""
    write_task(tasks, "100", "Done")
    write_task(tasks, "101", "Ready")
    write_task(tasks, "102", "Done", archived=True)
    write_task(tasks, "103", "Implementing",
               gates=["review_approved"],
               marks=[PASS_MARK.format(gate="review_approved")])
    write_task(tasks, "104", "Implementing",
               gates=["review_approved", "merge_approved"],
               marks=[PASS_MARK.format(gate="review_approved"),
                      PEND_MARK.format(gate="merge_approved")])
    _write_bundle(tasks, "50")
    for dependent, (dep, _verdict) in DEPENDENTS.items():
        write_task(tasks, dependent, "Ready", depends=[dep])


def _write_bundle(tasks: Path, task_id: str) -> Path:
    """A REAL archive bundle holding a real Done task, which must stay invisible.

    Deliberately not an empty placeholder: the decision under test is "bundles
    are never extracted", and a fixture whose bundle could not have resolved
    anyway would pass whether or not the code honours it. `archive_iter` would
    find this task; `dep_resolution` must not.
    """
    d = tasks / "archived" / "_b0"
    d.mkdir(parents=True, exist_ok=True)
    payload = _task_text("Done").encode("utf-8")
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        info = tarfile.TarInfo(f"t{task_id}_bundled.md")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    path = d / "old0.tar.gz"
    path.write_bytes(gzip.compress(raw.getvalue()))
    return path


# --- the three surfaces, reduced to one comparable shape --------------------

def _canon(raw: str) -> str:
    return raw.strip().lstrip("t")


class Verdicts(dict):
    """``{dependent_id: (blocked, frozenset(blocking), frozenset(unresolved))}``."""


def surface_ait_ls(tree: Path, script: Path = LS) -> Verdicts:
    """Drive the REAL `ait ls` and read its real `Status:` output."""
    out = subprocess.run(
        [str(script), "-v", "-s", "all", "--all-levels", "999"],
        cwd=tree, capture_output=True, text=True,
        env={**os.environ, "TASK_DIR": "aitasks"},
    )
    verdicts = Verdicts()
    for line in out.stdout.splitlines():
        if not line.startswith("t"):
            continue
        name, _, rest = line.partition(" ")
        task_id = _canon(name.split("_")[0])
        if "Status: Blocked (by " not in rest:
            verdicts[task_id] = (False, frozenset(), frozenset())
            continue
        listed = rest.split("Status: Blocked (by ", 1)[1]
        # Cut at the metadata that follows, NOT at the first ")": the
        # `(UNRESOLVED)` marker contains one, and splitting on it silently
        # truncated the id list to `999 (UNRESOLVED` — which then "disagreed"
        # with the other two surfaces for a purely cosmetic reason.
        listed = listed.split(", Priority:", 1)[0].rstrip()
        self_close = listed.rfind(")")
        listed = listed[:self_close] if self_close != -1 else listed
        blocking, unresolved = set(), set()
        for entry in listed.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if entry.endswith(dep_resolution.UNRESOLVED_MARKER):
                # Strip the SUFFIX, do not split on the first space: the
                # malformed-field token is itself multi-word, and splitting
                # reduced it to "<malformed" — a harness artifact that looked
                # exactly like a real cross-surface disagreement.
                unresolved.add(_canon(
                    entry[:-len(dep_resolution.UNRESOLVED_MARKER)].strip()))
            else:
                blocking.add(_canon(entry))
        verdicts[task_id] = (True, frozenset(blocking), frozenset(unresolved))
    return verdicts


def surface_minimonitor(tree: Path, ids) -> Verdicts:
    cache = TaskInfoCache(tree)
    verdicts = Verdicts()
    for task_id in ids:
        info = cache.get_task_info(task_id)
        assert info is not None, f"t{task_id} must resolve for the minimonitor"
        rows = cache.blocking_dependencies(info)
        verdicts[task_id] = (
            bool(rows),
            frozenset(_canon(v.raw) for v in rows if not v.unresolvable),
            frozenset(_canon(v.raw) for v in rows if v.unresolvable),
        )
    return verdicts


def board_manager(ab):
    """A TaskManager holding every active task, the way a real load leaves it."""
    mgr = ab.TaskManager.__new__(ab.TaskManager)
    mgr.task_datas = {}
    mgr.child_task_datas = {}
    mgr.archived_task_cache = {}
    mgr.gate_state_cache = {}
    mgr.gate_registry_cache = None
    mgr.gate_registry_error = ""
    mgr.gate_digest_cache = ab._DIGEST_UNSET
    for path in sorted(ab.TASKS_DIR.glob("t[0-9]*_*.md")):
        task = ab.Task(path)
        mgr.task_datas[task.filename] = task
    return mgr


def surface_board(ab, ids) -> Verdicts:
    mgr = board_manager(ab)
    by_id = {}
    for filename, task in mgr.task_datas.items():
        by_id[_canon(filename.split("_")[0])] = task
    verdicts = Verdicts()
    for task_id in ids:
        rows = mgr.local_dep_verdicts(by_id[task_id])
        verdicts[task_id] = (
            bool(rows),
            frozenset(_canon(v.raw) for v in rows if not v.unresolvable),
            frozenset(_canon(v.raw) for v in rows if v.unresolvable),
        )
    return verdicts


def disagreements(named_surfaces: dict[str, Verdicts]) -> list[str]:
    """Every (task, surface) that differs from the others — surface NAMED.

    Compares each surface against the first one only for reporting; the
    assertion is that ALL are equal, so any pairwise difference shows up.
    """
    names = list(named_surfaces)
    reference_name, reference = names[0], named_surfaces[names[0]]
    findings = []
    for name in names[1:]:
        other = named_surfaces[name]
        for task_id in sorted(set(reference) | set(other)):
            a, b = reference.get(task_id), other.get(task_id)
            if a != b:
                findings.append(
                    f"t{task_id}: {reference_name}={a} but {name}={b}")
    return findings


class _TreeCase(unittest.TestCase):
    """Builds the fixture tree, chdirs into it, and loads a bound board module."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="dep_parity_")
        self.addCleanup(self._tmp.cleanup)
        self.tree = make_tree(Path(self._tmp.name))
        self.tasks = self.tree / "aitasks"
        populate(self.tasks)
        self._cwd = os.getcwd()
        os.chdir(self.tree)
        self.addCleanup(os.chdir, self._cwd)
        self.ab = bf.load_board_module("aitasks", tag=f"depparity{id(self)}")


# --- 1 + 2: parity and its negative controls -------------------------------

class ParityTests(_TreeCase):

    def _all(self, ls_script: Path = LS, board_module=None):
        ids = list(DEPENDENTS)
        return {
            "ait ls": surface_ait_ls(self.tree, ls_script),
            "minimonitor": surface_minimonitor(self.tree, ids),
            "board": surface_board(board_module or self.ab, ids),
        }

    def _restrict(self, surfaces):
        """`ait ls` reports every task; keep only the dependents under test."""
        ids = set(DEPENDENTS)
        return {name: Verdicts({k: v for k, v in s.items() if k in ids})
                for name, s in surfaces.items()}

    def test_three_surfaces_agree_on_every_dep_shape(self):
        surfaces = self._restrict(self._all())
        for name, s in surfaces.items():
            self.assertEqual(set(s), set(DEPENDENTS),
                             f"{name} did not report every dependent")
        self.assertEqual(disagreements(surfaces), [])

    def test_the_two_historically_splitting_shapes(self):
        """Pins WHICH verdict the agreement settled on, not just that it exists.

        Agreement alone is satisfiable by three surfaces that are wrong the same
        way, and these are the exact two shapes that used to split them: a
        gate-released upstream (minimonitor said blocking, the other two did not)
        and an unresolvable id (minimonitor said blocking, the other two silently
        passed it).
        """
        surfaces = self._restrict(self._all())
        for name, s in surfaces.items():
            self.assertEqual(s["204"], (False, frozenset(), frozenset()),
                             f"{name}: gate-released upstream must not block")
            self.assertEqual(s["203"], (True, frozenset(), frozenset({"999"})),
                             f"{name}: an unresolvable id must block, marked")
            self.assertEqual(s["206"], (True, frozenset(), frozenset({"50"})),
                             f"{name}: a bundled-only id stays unresolvable")

    def test_negative_control_bash_surface_names_itself(self):
        """Mutate `ait ls` back to fail-open; the comparison must fail, naming it."""
        mutated_dir = Path(self._tmp.name) / "scripts"
        mutated_dir.mkdir()
        for entry in SCRIPTS.iterdir():
            (mutated_dir / entry.name).symlink_to(entry)
        mutated = mutated_dir / "aitask_ls.sh"
        mutated.unlink()
        source = LS.read_text(encoding="utf-8")
        assert "lookup_dep_blocking() {" in source
        mutated.write_text(
            source.replace("lookup_dep_blocking() {",
                           "lookup_dep_blocking() { return 1;  # MUTATED", 1),
            encoding="utf-8")
        mutated.chmod(0o755)

        findings = disagreements(self._restrict(self._all(ls_script=mutated)))
        self.assertTrue(findings, "the mutated surface was not detected")
        self.assertTrue(all("ait ls" in f for f in findings), findings)

    def test_negative_control_board_surface_names_itself(self):
        """Restore the board's pre-t1527 fail-open body; same requirement."""
        def fail_open(mgr, task):
            out = []
            for d in task.metadata.get("depends", []) or []:
                dep_id = str(d) if str(d).startswith("t") else f"t{d}"
                dep_task = mgr.find_task_by_id(dep_id)
                if dep_task and dep_task.metadata.get("status") != "Done":
                    out.append(dep_resolution.DepVerdict(
                        raw=dep_id, canonical=_canon(dep_id),
                        verdict=dep_resolution.BLOCKING))
            return out

        with patch.object(self.ab.TaskManager, "local_dep_verdicts", fail_open):
            findings = disagreements(self._restrict(self._all()))
        self.assertTrue(findings, "the mutated surface was not detected")
        self.assertTrue(all("board" in f for f in findings), findings)


class ScanFailureTests(_TreeCase):
    """`ait ls` when the scan cannot run: a third state, never "nothing blocked".

    The scan is a subprocess boundary in the most-used command. Its total failure
    used to be indistinguishable from an empty result, and an empty result means
    "no task is blocked" — so a dead scan would have listed every dependent as
    Ready. That is fail-OPEN, the exact defect class t1527 removes, which is why
    `deps-blocking-scan` ends with a `SCAN_OK` trailer and `ait ls` requires it.
    """

    def _ls_with_broken_gate_script(self, body: str):
        """Run the real `ait ls` against a sabotaged `aitask_gate.sh`.

        Everything else in `.aitask-scripts` is symlinked, so this exercises the
        production `aitask_ls.sh` verbatim — only the verb it shells out to is
        replaced.
        """
        d = Path(self._tmp.name) / f"scripts{abs(hash(body))}"
        d.mkdir()
        for entry in SCRIPTS.iterdir():
            (d / entry.name).symlink_to(entry)
        (d / "aitask_gate.sh").unlink()
        (d / "aitask_gate.sh").write_text(body, encoding="utf-8")
        (d / "aitask_gate.sh").chmod(0o755)
        return subprocess.run(
            [str(d / "aitask_ls.sh"), "-v", "-s", "all", "--all-levels", "999"],
            cwd=self.tree, capture_output=True, text=True,
            env={**os.environ, "TASK_DIR": "aitasks"},
        )

    def _assert_fails_closed(self, proc):
        # Half one: the failure is SURFACED, naming the verb — a diagnostic that
        # is computed but never shown is not a diagnostic.
        self.assertIn("deps-blocking-scan", proc.stderr)
        self.assertIn("unverified", proc.stderr)
        # Half two: and it fails CLOSED. Every dependent under test carries a
        # `depends:` entry, so none of them may read as Ready.
        for task_id in DEPENDENTS:
            line = next(ln for ln in proc.stdout.splitlines()
                        if ln.startswith(f"t{task_id}_"))
            self.assertIn("Blocked", line, line)
            self.assertIn("[unverified]", line, line)

    def test_a_nonzero_exit_is_its_own_state(self):
        self._assert_fails_closed(self._ls_with_broken_gate_script(
            "#!/usr/bin/env bash\nexit 3\n"))

    def test_silent_success_without_the_trailer_is_also_a_failure(self):
        """The case a bare exit-status check misses: exit 0, plausible-looking
        empty output, no trailer. Without the trailer requirement this reads as
        "nothing is blocked" and every dependent silently unblocks."""
        self._assert_fails_closed(self._ls_with_broken_gate_script(
            "#!/usr/bin/env bash\nexit 0\n"))

    def test_a_nonterminal_marker_is_not_a_trailer(self):
        """The marker must be the FINAL LINE, not merely present.

        A damaged scanner that printed the marker and then kept going — or died
        partway after printing it — exits 0 with the marker in its output. A
        substring test accepts that, contributes no rows for the tasks the scan
        never reached, and those dependents silently read as Ready.
        """
        self._assert_fails_closed(self._ls_with_broken_gate_script(
            "#!/usr/bin/env bash\nprintf 'SCAN_OK\\nsome/late/row.md\\tt1\\n'\n"))

    def test_a_decorated_marker_is_not_a_trailer(self):
        """`SCAN_OK: nothing to do` is a diagnostic, not the contract's marker."""
        self._assert_fails_closed(self._ls_with_broken_gate_script(
            "#!/usr/bin/env bash\nprintf 'SCAN_OK: nothing to do\\n'\n"))

    def test_positive_control_the_real_verb_does_not_trip_the_guard(self):
        """Proves the two above detect a real failure rather than always firing."""
        proc = subprocess.run(
            [str(LS), "-v", "-s", "all", "--all-levels", "999"],
            cwd=self.tree, capture_output=True, text=True,
            env={**os.environ, "TASK_DIR": "aitasks"},
        )
        self.assertNotIn("unverified", proc.stderr)
        self.assertNotIn("[unverified]", proc.stdout)


# --- 3: render-level -------------------------------------------------------

class MarkerRenderTests(_TreeCase):

    def test_minimonitor_dialog_shows_the_marker_at_40_columns(self):
        from monitor.monitor_shared import TaskPickConfirmDialog
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        import asyncio

        cache = TaskInfoCache(self.tree)
        info = cache.get_task_info("203")
        blocking = cache.blocking_dependencies(info)
        self.assertTrue(blocking[0].unresolvable)

        class Host(App):
            def compose(self) -> ComposeResult:
                yield Static("host")

            def on_mount(self) -> None:
                self.push_screen(TaskPickConfirmDialog(
                    info, blocking=blocking, narrow=True))

        async def run():
            app = Host()
            async with app.run_test(size=(40, 24)) as pilot:
                await pilot.pause()
                node = app.screen.query_one("#pick-eligibility", Static)
                # render().plain, not the source string: this is what the pane
                # actually paints, so a marker clipped by the 40-column width
                # would fail here rather than pass on the widget's input.
                return node.render().plain

        painted = asyncio.run(run())
        self.assertIn("(UNRESOLVED)", painted)
        self.assertIn("t999", painted)

    def test_board_detail_label_carries_the_marker(self):
        mgr = board_manager(self.ab)
        by_id = {f.split("_")[0]: t for f, t in mgr.task_datas.items()}
        self.assertEqual(mgr.unresolved_local_deps(by_id["t203"]),
                         ["t999 (UNRESOLVED)"])
        # The detail pane joins that list straight into its 🔗 label.
        self.assertEqual(mgr.unresolved_local_deps(by_id["t201"]), ["t101"])


# --- 4: the core itself ----------------------------------------------------

class CoreTests(_TreeCase):

    def resolver(self):
        r = dep_resolution.LocalDepResolver(
            str(self.tasks), str(self.tasks / "metadata" / "gates.yaml"))
        r.begin_cycle()
        return r

    def test_tri_state_table(self):
        r = self.resolver()
        for dependent, (dep, expected) in DEPENDENTS.items():
            [v] = r.classify([dep])
            self.assertEqual(v.verdict, expected,
                             f"dep {dep} (of t{dependent}) misclassified")

    def test_canonicalization(self):
        c = dep_resolution.canonical_dep_id
        self.assertEqual(c("t423_6"), "423_6")
        self.assertEqual(c("423_6"), "423_6")
        self.assertEqual(c("423"), "423")
        self.assertEqual(c(423), "423")
        # 4236 is what an UNQUOTED `423_6` becomes if it is ever read with a
        # plain YAML loader; it is a different, valid id and must not be
        # "recovered" into 423_6 — the ambiguity is unrecoverable, which is why
        # t1528 validates at write time instead.
        self.assertEqual(c(4236), "4236")
        for bad in ("", None, "t", "abc", "1_2_3", True):
            self.assertIsNone(c(bad), f"{bad!r} must not canonicalize")

    def test_unresolvable_blocks_and_renders(self):
        [v] = self.resolver().classify(["999"])
        self.assertTrue(v.blocking)
        self.assertTrue(v.unresolvable)
        self.assertEqual(v.display(), "999 (UNRESOLVED)")
        self.assertEqual(v.display(prefix="t"), "t999 (UNRESOLVED)")

    def test_scan_emits_the_terminal_marker(self):
        buf = io.StringIO()
        dep_resolution.scan(str(self.tasks),
                            str(self.tasks / "metadata" / "gates.yaml"), buf)
        lines = buf.getvalue().splitlines()
        self.assertEqual(lines[-1], "SCAN_OK")
        rows = {ln.split("\t")[0].rsplit("/", 1)[1].split("_")[0]: ln.split("\t")[1]
                for ln in lines[:-1]}
        # Only the blocked dependents appear; satisfied ones produce no row.
        self.assertNotIn("t200", rows)
        self.assertEqual(rows["t203"], "999 (UNRESOLVED)")


class MalformedDependsTests(_TreeCase):
    """A `depends:` field that is not a list must fail CLOSED on every surface.

    `task_yaml._normalize_task_ids` deliberately passes a non-list value through
    untouched so consumers can detect it. Before t1527 no consumer did: the core
    returned `[]` (no blockers) for a scalar, and the minimonitor's `_resolve`
    was worse — `depends: 999` raised `TypeError` mid-resolve and
    `depends: "999"` iterated the string into `['9', '9', '9']`, three bogus
    dependencies. t1528 stops such values being WRITTEN; this keeps them visible
    in files that already carry one, and in hand-edited files afterwards.
    """

    MALFORMED = {"210": "999", "211": '"999"', "212": "{a: 1}"}

    def setUp(self):
        super().setUp()
        for task_id, raw in self.MALFORMED.items():
            path = self.tasks / f"t{task_id}_x.md"
            path.write_text(
                "---\npriority: high\neffort: low\n"
                f"depends: {raw}\nissue_type: feature\nstatus: Ready\n---\n\n# body\n",
                encoding="utf-8")

    def test_core_emits_one_unresolvable_verdict(self):
        r = dep_resolution.LocalDepResolver(
            str(self.tasks), str(self.tasks / "metadata" / "gates.yaml"))
        r.begin_cycle()
        for raw in (999, "999", {"a": 1}):
            [v] = r.classify(raw)
            self.assertEqual(v.verdict, dep_resolution.UNRESOLVABLE, raw)
            self.assertIsNone(v.canonical)
            # Rendered verbatim, never id-prefixed: `t<malformed depends>` would
            # read as a task that does not exist rather than an unreadable field.
            self.assertEqual(v.display(prefix="t"),
                             f"{dep_resolution.MALFORMED_TOKEN} (UNRESOLVED)")

    def test_an_absent_or_blank_field_is_still_no_dependencies(self):
        """The negative control: this must not turn every task into a blocker."""
        for benign in (None, [], "", "   "):
            self.assertEqual(dep_resolution.read_depends(benign), ([], False),
                             benign)

    def test_all_three_surfaces_agree_and_block(self):
        ids = list(self.MALFORMED)
        surfaces = {
            "ait ls": Verdicts({k: v for k, v in
                                surface_ait_ls(self.tree).items() if k in ids}),
            "minimonitor": surface_minimonitor(self.tree, ids),
            "board": surface_board(self.ab, ids),
        }
        self.assertEqual(disagreements(surfaces), [])
        for name, s in surfaces.items():
            for task_id in ids:
                blocked, blocking, unresolved = s[task_id]
                self.assertTrue(blocked, f"{name}: t{task_id} must be blocked")
                self.assertEqual(blocking, frozenset(), f"{name}/{task_id}")
                self.assertEqual(len(unresolved), 1, f"{name}/{task_id}")

    def test_the_minimonitor_resolve_no_longer_crashes_or_invents_deps(self):
        """Both pre-t1527 failure modes, pinned directly."""
        cache = TaskInfoCache(self.tree)
        info = cache.get_task_info("210")          # depends: 999 -> used to raise
        self.assertIsNotNone(info)
        self.assertEqual(info.depends, [])
        self.assertTrue(info.depends_malformed)

        info = cache.get_task_info("211")          # depends: "999" -> used to be 9,9,9
        self.assertEqual(info.depends, [])
        self.assertTrue(info.depends_malformed)

        ok = cache.get_task_info("201")            # a well-formed control
        self.assertEqual(ok.depends, ["101"])
        self.assertFalse(ok.depends_malformed)


class BlockListDependsTests(_TreeCase):
    """YAML **block-list** `depends:` must reach every surface identically.

    The scan's `may_have_depends()` pre-filter exists to skip the PyYAML parse
    for tasks that carry no dependency. Its first version treated a *bare*
    `depends:` key as dep-free because nothing followed the colon — but that is
    the head of a valid block list, so `ait ls` skipped a task the board and the
    minimonitor both blocked. An optimisation that reintroduces the very
    disagreement this module removes is a correctness bug, so the pre-filter is
    pinned here on the surfaces, not only in a unit test.
    """

    #: The frontmatter shapes the pre-filter has to get right. `dep` is the
    #: dependency the file really declares, or None for "genuinely none".
    SHAPES = {
        "220": ("depends:\n  - 101", "101"),
        "221": ("depends:\n  - t101\n  - 100", "101"),
        "222": ("depends:", None),
        "223": ("depends:  # none yet", None),
        "224": ("depends: []", None),
        "225": ("depends: [ ]", None),
    }

    def setUp(self):
        super().setUp()
        for task_id, (field, _dep) in self.SHAPES.items():
            (self.tasks / f"t{task_id}_x.md").write_text(
                "---\npriority: high\neffort: low\n"
                f"{field}\nissue_type: feature\nstatus: Ready\n---\n\n# body\n",
                encoding="utf-8")

    def test_the_prefilter_only_skips_a_certainty(self):
        for task_id, (field, dep) in self.SHAPES.items():
            text = (self.tasks / f"t{task_id}_x.md").read_text(encoding="utf-8")
            skipped = not dep_resolution.may_have_depends(text)
            if dep is not None:
                self.assertFalse(skipped,
                                 f"{field!r} declares t{dep} and must be parsed")
            # The converse is deliberately NOT asserted: the pre-filter is
            # allowed to parse a dep-free file (a wasted parse is not a bug), it
            # is only forbidden to skip one that has deps.

    def test_all_three_surfaces_agree_on_every_shape(self):
        ids = list(self.SHAPES)
        surfaces = {
            "ait ls": Verdicts({k: v for k, v in
                                surface_ait_ls(self.tree).items() if k in ids}),
            "minimonitor": surface_minimonitor(self.tree, ids),
            "board": surface_board(self.ab, ids),
        }
        self.assertEqual(disagreements(surfaces), [])
        for name, s in surfaces.items():
            # t101 is Ready -> a real blocker; the dep-free shapes must not block.
            self.assertEqual(s["220"], (True, frozenset({"101"}), frozenset()),
                             f"{name}: a block-list dep must block")
            self.assertEqual(s["221"], (True, frozenset({"101"}), frozenset()),
                             f"{name}: a multi-entry block list must block")
            for dep_free in ("222", "223", "224", "225"):
                self.assertEqual(s[dep_free], (False, frozenset(), frozenset()),
                                 f"{name}: t{dep_free} declares no dependency")


# --- 5: the evaluator really hoists ---------------------------------------

class EvaluatorFanOutTests(_TreeCase):

    def _sign(self, task_id: str, gate: str, digest: str) -> None:
        """A stamped witness — the only shape that reaches `code_digest()`."""
        target = self.tree / ".aitask-gates" / f"t{task_id}" / f"{gate}.signed"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"code_digest={digest}\n", encoding="utf-8")

    def _fixture(self, n: int = 20, signed: int = 3):
        for i in range(n):
            task_id = str(300 + i)
            gates, marks = ["review_approved"], [
                PASS_MARK.format(gate="review_approved")]
            write_task(self.tasks, task_id, "Implementing", gates=gates,
                       marks=marks)
            write_task(self.tasks, str(400 + i), "Ready", depends=[task_id])
            if i < signed:
                self._sign(task_id, "review_approved", "deadbeef")

    def _counted_scan(self, resolver_per_dep: bool):
        counts = {"registry": 0, "digest": 0}
        real_registry = dep_resolution.gate_ledger.read_registry
        real_digest = dep_resolution.gate_ledger.code_digest

        def registry(*a, **k):
            counts["registry"] += 1
            return real_registry(*a, **k)

        def digest(*a, **k):
            counts["digest"] += 1
            return real_digest(*a, **k)

        registry_file = str(self.tasks / "metadata" / "gates.yaml")
        # Patch the module object `dep_resolution` ACTUALLY HOLDS, not this
        # module's own `gate_ledger` import. Measured in the full suite: those
        # are two DIFFERENT module objects loaded from the same file path —
        # something else imports `.aitask-scripts/lib/gate_ledger.py` under a
        # second key — so patching the local name intercepted nothing and both
        # counters read 0, which silently satisfies the `<= 1` assertion below.
        # The `== 1` assertion is what makes that failure loud rather than
        # vacuous; keep it exact, never `<=`.
        with patch.object(dep_resolution.gate_ledger, "read_registry", registry), \
                patch.object(dep_resolution.gate_ledger, "code_digest", digest):
            if resolver_per_dep:
                # The shape the plan REJECTED: a fresh evaluator per dependency.
                for i in range(20):
                    r = dep_resolution.LocalDepResolver(str(self.tasks),
                                                        registry_file)
                    r.begin_cycle()
                    r.classify([str(300 + i)])
            else:
                dep_resolution.scan(str(self.tasks), registry_file, io.StringIO())
        return counts

    def test_one_registry_parse_and_at_most_one_digest_for_a_whole_scan(self):
        self._fixture()
        counts = self._counted_scan(resolver_per_dep=False)
        self.assertEqual(counts["registry"], 1, counts)
        self.assertLessEqual(counts["digest"], 1, counts)

    def test_negative_control_per_dep_evaluators_pay_per_edge(self):
        """Proves the fixture reaches the expensive path at all.

        Without it, `digest <= 1` above would also hold for a fixture where no
        task carries a stamped witness — a vacuous pass.
        """
        self._fixture()
        counts = self._counted_scan(resolver_per_dep=True)
        self.assertEqual(counts["registry"], 20, counts)
        self.assertGreater(counts["digest"], 1, counts)


# --- 6: cache freshness ----------------------------------------------------

class CacheFreshnessTests(_TreeCase):
    """The two stale answers a resolved-file identity key structurally cannot see.

    Both call the resolver TWICE with no explicit invalidation, so a resolver
    that only checked file identity fails them.
    """

    def resolver(self):
        r = dep_resolution.LocalDepResolver(
            str(self.tasks), str(self.tasks / "metadata" / "gates.yaml"))
        r.begin_cycle()
        return r

    def test_a_created_task_stops_being_unresolvable(self):
        r = self.resolver()
        self.assertEqual(r.classify(["777"])[0].verdict,
                         dep_resolution.UNRESOLVABLE)
        write_task(self.tasks, "777", "Ready")
        self.assertEqual(r.classify(["777"])[0].verdict,
                         dep_resolution.BLOCKING)

    def test_an_active_copy_shadows_the_archived_one(self):
        r = self.resolver()
        # t102 exists only under archived/ and is Done -> satisfied.
        self.assertEqual(r.classify(["102"])[0].verdict,
                         dep_resolution.SATISFIED)
        write_task(self.tasks, "102", "Ready")   # an active copy appears
        self.assertEqual(r.classify(["102"])[0].verdict,
                         dep_resolution.BLOCKING)

    def test_an_edit_to_an_indexed_file_is_seen(self):
        """Level 2's job: an in-place edit leaves the directory mtime alone."""
        r = self.resolver()
        self.assertEqual(r.classify(["101"])[0].verdict,
                         dep_resolution.BLOCKING)
        write_task(self.tasks, "101", "Done")
        self.assertEqual(r.classify(["101"])[0].verdict,
                         dep_resolution.SATISFIED)


# --- 7: evaluator lifetime -------------------------------------------------

class EvaluatorLifetimeTests(_TreeCase):
    """A new cycle re-decides; within one cycle it does not (t1416).

    The hazard the cycle boundary exists for: `DependentsEvaluator` memoizes the
    registry AND the code digest, both of which are re-validation inputs. Held
    for a process lifetime they freeze every signature verdict until restart.
    """

    def setUp(self):
        super().setUp()
        self.registry = self.tasks / "metadata" / "gates.yaml"
        self.resolver = dep_resolution.LocalDepResolver(
            str(self.tasks), str(self.registry))

    def test_a_new_cycle_sees_an_edited_registry(self):
        self.resolver.begin_cycle()
        self.assertEqual(self.resolver.classify(["103"])[0].verdict,
                         dep_resolution.SATISFIED)

        # Negative control FIRST: the same edit inside one cycle must not move.
        text = self.registry.read_text(encoding="utf-8")
        edited = text.replace(
            '  review_approved:\n    type: human\n'
            '    description: "Implemented changes reviewed and approved before commit"\n'
            '    blocks_dependents: true',
            '  review_approved:\n    type: human\n'
            '    description: "Implemented changes reviewed and approved before commit"\n'
            '    blocks_dependents: false')
        self.assertNotEqual(edited, text, "registry edit did not apply")
        self.registry.write_text(edited, encoding="utf-8")
        self.assertEqual(self.resolver.classify(["103"])[0].verdict,
                         dep_resolution.SATISFIED,
                         "within one cycle the memoized registry must stand")

        # New cycle -> re-read. With review_approved no longer blocking
        # dependents, t103 declares no required-to-unblock gate at all, so it is
        # NO_GATES and falls back to file existence: active and not Done.
        self.resolver.begin_cycle()
        self.assertEqual(self.resolver.classify(["103"])[0].verdict,
                         dep_resolution.BLOCKING)

    def test_a_new_cycle_sees_a_changed_code_digest(self):
        witness = self.tree / ".aitask-gates" / "t103" / "review_approved.signed"
        witness.parent.mkdir(parents=True, exist_ok=True)
        witness.write_text("code_digest=aaaa\n", encoding="utf-8")

        digest = {"value": "aaaa"}
        self.resolver.begin_cycle(digest_provider=lambda: digest["value"])
        self.assertEqual(self.resolver.classify(["103"])[0].verdict,
                         dep_resolution.SATISFIED,
                         "a fresh signature releases dependents")

        digest["value"] = "bbbb"   # the code moved under the signature
        self.assertEqual(self.resolver.classify(["103"])[0].verdict,
                         dep_resolution.SATISFIED,
                         "within one cycle the memoized digest must stand")

        self.resolver.begin_cycle(digest_provider=lambda: digest["value"])
        self.assertEqual(self.resolver.classify(["103"])[0].verdict,
                         dep_resolution.BLOCKING,
                         "a stale signature must re-pend on the next cycle")

    def test_the_board_starts_a_new_cycle_every_refresh(self):
        """Structural guard: the boundary sits on the line that already renews
        `gate_digest_cache`, so the two cannot drift apart."""
        mgr = board_manager(self.ab)
        built = []
        real = dep_resolution.LocalDepResolver.begin_cycle

        def counting(inner_self, **k):
            built.append(1)
            return real(inner_self, **k)

        with patch.object(dep_resolution.LocalDepResolver, "begin_cycle",
                          counting):
            mgr.dep_resolver()               # lazy build -> cycle 1
            self.assertEqual(len(built), 1)
            mgr.clear_gate_cache()           # a refresh -> cycle 2
            self.assertEqual(len(built), 2)
            mgr.clear_gate_cache()           # and again
            self.assertEqual(len(built), 3)


# --- 8: find_ready_siblings ------------------------------------------------

class ReadySiblingsTests(_TreeCase):
    """The 4th resolver: it gained the gate-release rule, kept its scope."""

    def setUp(self):
        super().setUp()
        write_task(self.tasks, "600_1", "Implementing",
                   gates=["review_approved"],
                   marks=[PASS_MARK.format(gate="review_approved")])
        write_task(self.tasks, "600_2", "Implementing",
                   gates=["review_approved", "merge_approved"],
                   marks=[PASS_MARK.format(gate="review_approved"),
                          PEND_MARK.format(gate="merge_approved")])
        write_task(self.tasks, "600_3", "Ready", depends=["600_1"])
        write_task(self.tasks, "600_4", "Ready", depends=["600_2"])
        write_task(self.tasks, "600_5", "Ready", depends=["101"])
        self.cache = TaskInfoCache(self.tree)

    def _blocking(self, sib_id: str) -> list[str]:
        rows = {r[0]: r[2] for r in self.cache.find_ready_siblings("600")}
        return rows[sib_id]

    def test_gate_released_sibling_no_longer_blocks(self):
        self.assertEqual(self._blocking("600_3"), [])

    def test_sibling_with_a_pending_required_gate_still_blocks(self):
        self.assertEqual(self._blocking("600_4"), ["600_2"])

    def test_non_sibling_dep_is_still_ignored(self):
        """The scoping control: t101 is Ready and would block anywhere else, but
        this hint is deliberately sibling-only and must not have widened."""
        self.assertEqual(self._blocking("600_5"), [])


if __name__ == "__main__":
    unittest.main()
