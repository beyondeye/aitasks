"""Persistence-seam contract for `Task.reload_and_save_board_fields` (t1243_2).

The board's only disk-write path for board fields. Before t1243_2 it snapshotted
`boardcol`/`boardidx` by name, reloaded, re-applied both, and saved — which drops
any board key it does not name (blocking t1243_8's `boardgroup`) and writes back
keys the caller never mutated. This file pins the replacement contract:

    a call persists exactly the fields it names, and it must name them.

Three write-back hazards are guarded, each with its own negative control:

  A  a layout op re-applying a stale *shared* field, overwriting another
     checkout's membership change;
  B  a semantic write re-applying a stale `boardidx`, discarding a newer move;
  C  a single-key layout op re-applying the *other* layout key — live before
     this task, e.g. `respace_column` (`normalize_indices` before t1243_3
     renamed it) yanking a card back out of the column another writer just
     moved it to.

Why no subprocess (unlike tests/test_board_movement.py)
-------------------------------------------------------
t1243_1 needs a child interpreter because setting the **environment variable**
`TASK_DIR` is a no-op against `aitask_board.TASKS_DIR = task_dir()`, already
evaluated at import in a suite that shares one process. That does not apply here:

* `Task` takes an explicit `filepath` and touches no directory constant at all;
* `TaskManager.__init__` is dict setup plus `_ensure_paths` / `load_metadata` /
  `load_tasks`, all of which read the module globals `TASKS_DIR` /
  `METADATA_FILE` **at call time** — so patching the module *attribute* (a
  different seam from the env var) redirects them, with no app, no Pilot, no git.

`mock.patch.object` is used for every patch so the globals are restored even on
failure; the suite shares one interpreter and t1243_1's isolation control asserts
`aitask_board.TASKS_DIR == Path("aitasks")`.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_board_persistence_seam -v
"""

from __future__ import annotations

import ast
import contextlib
import inspect
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS = Path(__file__).resolve().parent
for _p in (str(_TESTS),
           str(REPO_ROOT / "tests" / "lib"),
           str(REPO_ROOT / ".aitask-scripts" / "board"),
           str(REPO_ROOT / ".aitask-scripts" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from task_yaml import (  # noqa: E402
    BOARD_KEYS, BOARD_LAYOUT_KEYS, parse_frontmatter, serialize_frontmatter,
)
# Reuse the shared fixture + differ rather than building a second one. These
# lived in test_board_movement until t1354_1 promoted them to tests/lib/ so the
# migrated board modules build identical trees.
from board_fixture import (  # noqa: E402
    build_tree, diff_snapshots, fixture_name, snapshot,
)
import aitask_board as B  # noqa: E402

BOARD_SRC = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"

# The shared board key: board-owned but NOT per-checkout layout. This was a
# synthetic stand-in until t1243_8 landed `boardgroup` for real; it is now the
# actual key, which is exactly what these tests were written ahead of.
SEM = "boardgroup"
SEM_KEYS = BOARD_LAYOUT_KEYS + (SEM,)

CANONICAL = [(1, "c0", 10), (2, "c0", 20), (3, "c0", 30), (4, "c1", 10)]
GAPPED = [(1, "c0", 5), (2, "c0", 17), (3, "c0", 42)]


def external_edit(path: Path, **changes) -> None:
    """Rewrite a task file through the canonical serializer, as another writer would."""
    meta, body, order = parse_frontmatter(path.read_text(encoding="utf-8"))
    meta.update(changes)
    path.write_text(serialize_frontmatter(meta, body, order), encoding="utf-8")


def read_meta(path: Path) -> dict:
    meta, _body, _order = parse_frontmatter(path.read_text(encoding="utf-8"))
    return meta


def read_body(path: Path) -> str:
    _meta, body, _order = parse_frontmatter(path.read_text(encoding="utf-8"))
    return body


class _FrozenDatetime(datetime):
    """Real datetime subclass with a pinned now() — strftime/strptime intact."""

    _frozen: datetime | None = None

    @classmethod
    def now(cls, tz=None):
        return cls._frozen


@contextlib.contextmanager
def frozen_clock(stamp: str):
    """Pin `aitask_board.datetime.now()`.

    `_update_timestamp` is minute-resolution, so both the "sets the current
    minute" and the "same minute does not advance" assertions would otherwise be
    wall-clock races across a minute boundary.
    """
    cls = type("_FrozenNow", (_FrozenDatetime,),
               {"_frozen": datetime.strptime(stamp, "%Y-%m-%d %H:%M")})
    with mock.patch.object(B, "datetime", cls):
        yield


# --- Rejected implementations, kept executable for the negative controls -----
#
# Each reproduces one design this task rejected. A control runs a real test's
# assertions verbatim under one of these and requires them to FAIL — a guard
# that cannot fail pins nothing.

def _apply(task, keys, semantic):
    snap = {k: task.metadata.get(k) for k in keys}
    if not task.load():
        return
    for k, v in snap.items():
        if v is not None:
            task.metadata[k] = v
    if semantic:
        task._update_timestamp()
    task.save()


def _legacy_two_name_body(self, fields=None):
    """Pre-t1243_2: hardcoded pair, `fields` ignored — drops every other key."""
    _apply(self, ("boardcol", "boardidx"), semantic=False)


def _broad_default_body(self, fields=None):
    """Today's behaviour, and any future convenience default: always both layout keys."""
    _apply(self, tuple(self._BOARD_LAYOUT_KEYS), semantic=False)


def _naive_all_board_keys_body(self, fields=None):
    """The task file's original sketch: iterate the whole board key set."""
    _apply(self, tuple(self._BOARD_KEYS), semantic=False)


def _layout_plus_named_body(self, fields=()):
    """An earlier plan revision: layout keys UNION the named fields."""
    keys = tuple(self._BOARD_LAYOUT_KEYS) + tuple(fields or ())
    semantic = any(k not in self._BOARD_LAYOUT_KEYS for k in keys)
    _apply(self, keys, semantic=semantic)


class _TreeCase(unittest.TestCase):
    """Temp-tree fixture plus the assertion helpers the controls re-run."""

    def make_tree(self, cards=CANONICAL) -> Path:
        root = Path(tempfile.mkdtemp(prefix="aitask-seam-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return build_tree(root, cards)

    def task_path(self, tree: Path, i: int) -> Path:
        return tree / "aitasks" / fixture_name(i)

    def allow_semantic_key(self) -> None:
        """Pin `Task`'s board-key vocabulary for these tests.

        Now that t1243_8 has appended `boardgroup` to the real `BOARD_KEYS`,
        `SEM_KEYS` equals it and this patch is a no-op — kept because it states
        the precondition these tests depend on, and because it keeps them
        meaningful for the NEXT shared key, before that key lands.

        Patched on the CLASS, never on the module. When SEM was still synthetic
        that was load-bearing (the module-level constant is also read by
        `_is_phantom_stub`, `serialize_frontmatter` and
        `aitask_merge._KEEP_LOCAL_FIELDS`, none of which should have seen a
        fictional key). Keep it class-scoped for the same reason next time.
        `_BOARD_LAYOUT_KEYS` is deliberately left alone, which is what makes SEM
        semantic.
        """
        patcher = mock.patch.object(B.Task, "_BOARD_KEYS", SEM_KEYS)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- assertions shared with the negative controls ---

    def _assert_index_only_keeps_remote_column(self, tree: Path) -> None:
        """Hazard C: an index-only call must not write `boardcol` back."""
        path = self.task_path(tree, 1)
        task = B.Task(path)                      # in memory: boardcol c0
        external_edit(path, boardcol="c1")       # another writer moves it
        task.board_idx = 999
        task.reload_and_save_board_fields(("boardidx",))
        meta = read_meta(path)
        self.assertEqual(meta.get("boardcol"), "c1")
        self.assertEqual(meta.get("boardidx"), 999)

    def _assert_layout_call_keeps_remote_shared_field(self, tree: Path) -> None:
        """Hazard A: a layout call must not write a shared field back."""
        self.allow_semantic_key()
        path = self.task_path(tree, 1)
        task = B.Task(path)
        task.metadata[SEM] = "A"
        external_edit(path, **{SEM: "B"})
        task.board_idx = 999
        task.reload_and_save_board_fields(("boardcol", "boardidx"))
        meta = read_meta(path)
        self.assertEqual(meta.get(SEM), "B")
        self.assertIsNone(meta.get("updated_at"))   # a layout write is not semantic

    def _assert_semantic_only_keeps_remote_index(self, tree: Path) -> None:
        """Hazard B: a semantic-only call must not write stale layout back."""
        self.allow_semantic_key()
        path = self.task_path(tree, 1)
        task = B.Task(path)                      # in memory: boardidx 10
        task.metadata[SEM] = "A"
        external_edit(path, boardidx=20)         # another writer moves it
        task.reload_and_save_board_fields((SEM,))
        meta = read_meta(path)
        self.assertEqual(meta.get("boardidx"), 20)
        self.assertEqual(meta.get(SEM), "A")

    def _assert_named_shared_field_persists(self, tree: Path) -> None:
        """The drop bug: a named shared field must survive the reload."""
        self.allow_semantic_key()
        path = self.task_path(tree, 1)
        task = B.Task(path)
        task.metadata[SEM] = "grp"
        external_edit(path, status="Done")
        task.reload_and_save_board_fields((SEM,))
        meta = read_meta(path)
        self.assertEqual(meta.get(SEM), "grp")
        self.assertEqual(meta.get("status"), "Done")


class SeamContractTests(_TreeCase):
    """4A — the seam itself, driven by direct `Task` construction."""

    def test_pre_reload_external_edit_survives(self):
        tree = self.make_tree()
        path = self.task_path(tree, 1)
        task = B.Task(path)
        task.board_idx = 999
        external_edit(path, status="Done")       # lands BEFORE the reload
        task.reload_and_save_board_fields(("boardidx",))
        meta = read_meta(path)
        self.assertEqual(meta["boardidx"], 999)
        self.assertEqual(meta["status"], "Done")

    def test_post_reload_external_edit_is_lost(self):
        """The documented limit of the guard, pinned rather than left as prose.

        The reload and the write are separate opens with no lock between them,
        so an edit landing in that window is overwritten. Deterministic here: the
        edit is driven from a wrapper around this instance's `load`.
        """
        tree = self.make_tree()
        path = self.task_path(tree, 1)
        task = B.Task(path)
        task.board_idx = 999
        real_load = task.load

        def load_then_external_edit():
            ok = real_load()
            external_edit(path, status="Done")   # lands AFTER the reload
            return ok

        task.load = load_then_external_edit
        task.reload_and_save_board_fields(("boardidx",))
        meta = read_meta(path)
        self.assertEqual(meta["boardidx"], 999)
        self.assertEqual(meta["status"], "Ready")   # lost — best-effort, not atomic

    def test_index_only_call_keeps_a_remote_column_move(self):
        self._assert_index_only_keeps_remote_column(self.make_tree())

    def test_column_only_call_keeps_a_remote_index_move(self):
        tree = self.make_tree()
        path = self.task_path(tree, 1)
        task = B.Task(path)                      # in memory: boardidx 10
        external_edit(path, boardidx=777)
        task.board_col = "c2"
        task.reload_and_save_board_fields(("boardcol",))
        meta = read_meta(path)
        self.assertEqual(meta["boardidx"], 777)
        self.assertEqual(meta["boardcol"], "c2")

    def test_layout_call_keeps_a_remote_shared_field(self):
        self._assert_layout_call_keeps_remote_shared_field(self.make_tree())

    def test_semantic_only_call_keeps_a_remote_index_move(self):
        self._assert_semantic_only_keeps_remote_index(self.make_tree())

    def test_named_shared_field_persists(self):
        self._assert_named_shared_field_persists(self.make_tree())

    def test_combined_mutation_persists_both_and_is_semantic(self):
        tree = self.make_tree()
        self.allow_semantic_key()
        path = self.task_path(tree, 1)
        task = B.Task(path)
        task.metadata[SEM] = "grp"
        task.board_idx = 555
        with frozen_clock("2026-01-02 03:04"):
            task.reload_and_save_board_fields((SEM, "boardidx"))
        meta = read_meta(path)
        self.assertEqual(meta[SEM], "grp")
        self.assertEqual(meta["boardidx"], 555)
        self.assertEqual(meta["updated_at"], "2026-01-02 03:04")

    def test_empty_string_tombstone_survives(self):
        """t1243_8 clears membership with `boardgroup: ""` — omit != clear."""
        tree = self.make_tree()
        self.allow_semantic_key()
        path = self.task_path(tree, 1)
        external_edit(path, **{SEM: "grp"})
        task = B.Task(path)
        task.metadata[SEM] = ""
        task.reload_and_save_board_fields((SEM,))
        self.assertEqual(read_meta(path)[SEM], "")

    def test_a_key_absent_from_memory_is_never_invented(self):
        tree = self.make_tree()
        self.allow_semantic_key()
        path = self.task_path(tree, 1)
        task = B.Task(path)                      # no SEM anywhere
        task.reload_and_save_board_fields((SEM,))
        self.assertNotIn(SEM, read_meta(path))

    def test_unknown_or_empty_fields_raise_before_any_write(self):
        tree = self.make_tree()
        path = self.task_path(tree, 1)
        before = path.read_bytes()
        task = B.Task(path)
        task.board_idx = 999
        for bad in (("status",), ("boardgruop",)):
            with self.assertRaises(ValueError) as ctx:
                task.reload_and_save_board_fields(bad)
            self.assertIn(bad[0], str(ctx.exception))
        with self.assertRaises(ValueError):
            task.reload_and_save_board_fields(())
        self.assertEqual(path.read_bytes(), before)

    def test_fields_has_no_default(self):
        """The structural fact that keeps hazard C from returning.

        A convenience default is always plausible and never stated — which is
        exactly how five call sites came to write a key they never mutated.
        """
        sig = inspect.signature(B.Task.reload_and_save_board_fields)
        self.assertIs(sig.parameters["fields"].default, inspect.Parameter.empty)

    def test_a_deleted_file_is_not_recreated(self):
        tree = self.make_tree()
        path = self.task_path(tree, 1)
        task = B.Task(path)
        path.unlink()
        task.board_idx = 999
        task.reload_and_save_board_fields(("boardidx",))
        self.assertFalse(path.exists())


class TimestampDisciplineTests(_TreeCase):
    """4A (cont.) — every assertion under a frozen clock."""

    def test_layout_write_is_byte_neutral_when_nothing_changed(self):
        tree = self.make_tree()
        before = snapshot(tree)
        task = B.Task(self.task_path(tree, 1))
        with frozen_clock("2026-01-02 03:04"):
            task.reload_and_save_board_fields(BOARD_LAYOUT_KEYS)
        self.assertEqual(diff_snapshots(before, snapshot(tree))["changed"], set())

    def test_layout_write_leaves_a_seeded_timestamp_and_the_rest_intact(self):
        tree = self.make_tree()
        path = self.task_path(tree, 1)
        external_edit(path, updated_at="2020-01-01 00:00")
        body_before = read_body(path)
        task = B.Task(path)
        task.board_idx = 999
        with frozen_clock("2026-01-02 03:04"):
            task.reload_and_save_board_fields(("boardidx",))
        meta = read_meta(path)
        self.assertEqual(meta["updated_at"], "2020-01-01 00:00")
        self.assertEqual(meta["boardidx"], 999)
        self.assertEqual(meta["status"], "Ready")
        self.assertEqual(meta["priority"], "medium")
        self.assertEqual(read_body(path), body_before)

    def test_a_layout_subset_is_not_a_semantic_write(self):
        tree = self.make_tree()
        path = self.task_path(tree, 1)
        task = B.Task(path)
        task.board_idx = 999
        with frozen_clock("2026-01-02 03:04"):
            task.reload_and_save_board_fields(("boardidx",))
        self.assertIsNone(read_meta(path).get("updated_at"))

    def test_semantic_write_sets_updated_at_to_the_current_minute(self):
        tree = self.make_tree()
        self.allow_semantic_key()
        path = self.task_path(tree, 1)
        external_edit(path, updated_at="2020-01-01 00:00")
        task = B.Task(path)
        task.metadata[SEM] = "grp"
        with frozen_clock("2026-01-02 03:04"):
            task.reload_and_save_board_fields((SEM,))
        self.assertEqual(read_meta(path)["updated_at"], "2026-01-02 03:04")

    def test_two_semantic_writes_in_one_minute_do_not_advance(self):
        """The contract is "sets the current minute", NOT "advances".

        `_update_timestamp` is `%Y-%m-%d %H:%M`. Pinned so no sibling builds
        ordering on it — t1243_8 already resolves `boardgroup` by base-aware
        change detection for exactly this reason.
        """
        tree = self.make_tree()
        self.allow_semantic_key()
        path = self.task_path(tree, 1)
        task = B.Task(path)
        with frozen_clock("2026-01-02 03:04"):
            task.metadata[SEM] = "one"
            task.reload_and_save_board_fields((SEM,))
            first = read_meta(path)["updated_at"]
            task.metadata[SEM] = "two"
            task.reload_and_save_board_fields((SEM,))
            second = read_meta(path)["updated_at"]
        self.assertEqual(first, second)
        # ...and the assertion is not vacuous: a later minute does change it.
        with frozen_clock("2026-01-02 03:05"):
            task.metadata[SEM] = "three"
            task.reload_and_save_board_fields((SEM,))
        self.assertEqual(read_meta(path)["updated_at"], "2026-01-02 03:05")


class NegativeControlTests(_TreeCase):
    """4B — one control per rejected design; each must make a real test FAIL."""

    def _under(self, body, assertion, expected_message, cards=CANONICAL):
        """`expected_message` pins WHICH assertion failed.

        Without it a control could go green on an unrelated AssertionError and
        report a discriminating test that is not discriminating.
        """
        tree = self.make_tree(cards)
        with mock.patch.object(B.Task, "reload_and_save_board_fields", body):
            with self.assertRaises(AssertionError) as ctx:
                assertion(tree)
        self.assertIn(expected_message, str(ctx.exception))

    def test_legacy_two_name_body_drops_a_named_shared_field(self):
        self._under(_legacy_two_name_body, self._assert_named_shared_field_persists,
                    "None != 'grp'")            # the shared key never reached disk

    def test_broad_default_body_reverts_a_remote_column_move(self):
        self._under(_broad_default_body, self._assert_index_only_keeps_remote_column,
                    "'c0' != 'c1'")             # stale column written back

    def test_all_board_keys_body_resurrects_a_remote_shared_field(self):
        self._under(_naive_all_board_keys_body,
                    self._assert_layout_call_keeps_remote_shared_field,
                    "'A' != 'B'")               # stale membership written back

    def test_layout_plus_named_body_reverts_a_remote_index_move(self):
        self._under(_layout_plus_named_body,
                    self._assert_semantic_only_keeps_remote_index,
                    "10 != 20")                 # stale index written back


# --- 4C: the call-site mapping ----------------------------------------------
#
# 4A calls the seam with the right tuple itself, so it says nothing about what
# the CALLERS pass. t1243_1's FLIP_TABLE does not close the gap either: it
# catches a caller that OMITS a field it genuinely mutated (the mutated value
# differs from disk, so it fails to persist), but an EXTRA field is
# byte-identical in an uncontended harness — `swap_tasks` could pass
# ("boardcol","boardidx"), keep every existing assertion green, and still carry
# hazard C. These two guards are what pin the mapping.
#
# FROZEN, like FLIP_TABLE: a new or changed call site must consciously edit the
# table below. A silent pass after a rewrite is a bug in the table.

# REWRITTEN BY t1243_3 (gap indexing), which is what "frozen" means here: the
# table is edited deliberately, in the same commit as the call sites, and never
# adjusted to match a surprise. Three methods were retired --
# `move_task_col`/`swap_tasks`/`normalize_indices` -- and `_move_task_to_extreme`
# LEFT the table entirely: the action now delegates to `move_task_to_edge`
# instead of writing the seam itself, which is part of the deliverable.
# `swap_tasks` contributed two rows; `reposition_task` replaces it with one.
EXPECTED_CALL_SITES = [
    ("move_tasks_to_column", ("boardcol", "boardidx")),
    ("move_task_to_edge", ("boardidx",)),
    ("reposition_task", ("boardidx",)),
    ("respace_column", ("boardidx",)),
    ("update_column", ("boardcol",)),
    ("delete_column", ("boardcol", "boardidx")),
]


def _parse_call_sites(path: Path):
    """Map every `reload_and_save_board_fields` call to (enclosing_fn, fields).

    Fails CLOSED: a call whose argument is not a literal tuple of strings yields
    a diagnostic string instead of a tuple, so it can never compare equal to an
    expected entry and can never be silently skipped.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "reload_and_save_board_fields"):
            continue
        enclosing = parents.get(node)
        while enclosing is not None and not isinstance(
                enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)):
            enclosing = parents.get(enclosing)
        name = enclosing.name if enclosing is not None else "<module>"

        if len(node.args) != 1 or node.keywords:
            fields = "UNANALYSABLE: expected exactly one positional argument"
        else:
            arg = node.args[0]
            if isinstance(arg, ast.Tuple) and arg.elts and all(
                    isinstance(e, ast.Constant) and isinstance(e.value, str)
                    for e in arg.elts):
                fields = tuple(e.value for e in arg.elts)
            else:
                fields = "UNANALYSABLE: fields must be a literal tuple of strings"
        found.append((node.lineno, name, fields))

    found.sort()
    return [(name, fields) for _lineno, name, fields in found]


class CallSiteMappingTests(_TreeCase):
    """4C — what the real callers pass, structurally and at runtime."""

    def test_ast_maps_every_call_site_to_its_declared_fields(self):
        self.assertEqual(_parse_call_sites(BOARD_SRC), EXPECTED_CALL_SITES)

    def _parse_variant(self, old: str, new: str):
        """Parse a temp copy of the board source with one call site rewritten.

        Proves the guard discriminates without mutating production source, so
        there is nothing to restore if the assertion fails.
        """
        src = BOARD_SRC.read_text(encoding="utf-8")
        self.assertIn(old, src)                       # the anchor still exists
        variant = Path(tempfile.mkdtemp(prefix="aitask-ast-")) / "variant.py"
        self.addCleanup(shutil.rmtree, variant.parent, ignore_errors=True)
        variant.write_text(src.replace(old, new, 1), encoding="utf-8")
        return _parse_call_sites(variant)

    # t1243_3 re-anchored both variants: the old anchor was the `t1.` call
    # inside `swap_tasks`, a method gap indexing removed. `_parse_variant`
    # rewrites the FIRST occurrence, and the first `("boardidx",)` call site in
    # source order is `move_task_to_edge` — asserted by name below, so a future
    # reordering fails loudly instead of silently mutating a different site.
    _IDX_ANCHOR = 'task.reload_and_save_board_fields(("boardidx",))'

    def test_ast_guard_rejects_an_extra_field(self):
        """The failure FLIP_TABLE cannot see: a caller naming a key it never
        mutated is byte-identical uncontended, but still carries hazard C."""
        got = self._parse_variant(
            self._IDX_ANCHOR,
            'task.reload_and_save_board_fields(("boardcol", "boardidx"))')
        self.assertNotEqual(got, EXPECTED_CALL_SITES)
        self.assertIn(("move_task_to_edge", ("boardcol", "boardidx")), got)

    def test_ast_guard_fails_closed_on_a_non_literal_argument(self):
        """A computed tuple must be reported, never silently skipped."""
        got = self._parse_variant(
            self._IDX_ANCHOR,
            'task.reload_and_save_board_fields(tuple(some_keys))')
        self.assertNotEqual(got, EXPECTED_CALL_SITES)
        self.assertTrue(
            any(isinstance(fields, str) and fields.startswith("UNANALYSABLE")
                for _name, fields in got),
            f"non-literal argument was not reported: {got}")

    # --- runtime spy through the real TaskManager methods ---

    def _manager(self, tree: Path):
        tasks_dir = tree / "aitasks"
        for attr, value in (("TASKS_DIR", tasks_dir),
                            ("METADATA_FILE", tasks_dir / "metadata" / "board_config.json")):
            patcher = mock.patch.object(B, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        return B.TaskManager()

    def _spy(self):
        records = []
        original = B.Task.reload_and_save_board_fields

        def wrapper(self_, fields):
            records.append((self_.filename, tuple(fields)))
            return original(self_, fields)

        patcher = mock.patch.object(B.Task, "reload_and_save_board_fields", wrapper)
        patcher.start()
        self.addCleanup(patcher.stop)
        return records

    # t1243_3 retargeted these three: `move_task_col` / `swap_tasks` /
    # `normalize_indices` were replaced by the gap-indexing API.

    def test_move_task_to_column_names_both_layout_keys(self):
        tree = self.make_tree()
        manager = self._manager(tree)
        records = self._spy()
        manager.move_task_to_column(fixture_name(1), "c1")
        self.assertEqual(records, [(fixture_name(1), ("boardcol", "boardidx"))])

    def test_reposition_task_names_the_index_only_once(self):
        """One record, where `swap_tasks` produced two — the halved write count
        expressed at the seam layer rather than only in the flip table."""
        tree = self.make_tree()
        manager = self._manager(tree)
        records = self._spy()
        manager.reposition_task(fixture_name(3),
                                manager.task_datas[fixture_name(1)],
                                manager.task_datas[fixture_name(2)])
        self.assertEqual(records, [(fixture_name(3), ("boardidx",))])

    def test_move_task_to_edge_names_the_index_only(self):
        tree = self.make_tree()
        manager = self._manager(tree)
        records = self._spy()
        manager.move_task_to_edge(fixture_name(3), "c0", to_top=True)
        self.assertEqual(records, [(fixture_name(3), ("boardidx",))])

    def test_respace_column_names_the_index_only(self):
        tree = self.make_tree(GAPPED)   # 5/17/42 -> all three are renumbered
        manager = self._manager(tree)
        records = self._spy()
        manager.respace_column("c0")
        self.assertEqual(records, [(fixture_name(i), ("boardidx",)) for i in (1, 2, 3)])

    def test_update_column_names_the_column_only(self):
        tree = self.make_tree()
        manager = self._manager(tree)
        records = self._spy()
        manager.update_column("c0", "c9", "Col 9", "#FFFFFF")
        self.assertEqual(records, [(fixture_name(i), ("boardcol",)) for i in (1, 2, 3)])

    def test_delete_column_names_both_layout_keys(self):
        tree = self.make_tree()
        manager = self._manager(tree)
        records = self._spy()
        manager.delete_column("c1")
        self.assertEqual(records, [(fixture_name(4), ("boardcol", "boardidx"))])

    # --- hazard C end to end, through production code rather than the seam ---

    def test_respace_column_does_not_revert_a_remote_column_move(self):
        tree = self.make_tree(GAPPED)
        manager = self._manager(tree)            # loads all three into memory
        path = self.task_path(tree, 2)
        external_edit(path, boardcol="c1")       # another writer moves it out
        manager.respace_column("c0")             # this board still believes c0
        self.assertEqual(read_meta(path)["boardcol"], "c1")

    def test_update_column_does_not_revert_a_remote_index_move(self):
        tree = self.make_tree()
        manager = self._manager(tree)
        path = self.task_path(tree, 1)
        external_edit(path, boardidx=777)
        manager.update_column("c0", "c9", "Col 9", "#FFFFFF")
        meta = read_meta(path)
        self.assertEqual(meta["boardidx"], 777)
        self.assertEqual(meta["boardcol"], "c9")

    def test_patched_module_globals_are_restored(self):
        """The suite shares one interpreter; a leak would point later tests —
        including t1243_1's isolation control — at a deleted temp tree."""
        before = (B.TASKS_DIR, B.METADATA_FILE)
        tree = self.make_tree()
        tasks_dir = tree / "aitasks"
        with mock.patch.object(B, "TASKS_DIR", tasks_dir), \
             mock.patch.object(B, "METADATA_FILE",
                               tasks_dir / "metadata" / "board_config.json"):
            B.TaskManager()
        self.assertEqual((B.TASKS_DIR, B.METADATA_FILE), before)


class MergeFieldOwnershipTests(unittest.TestCase):
    """The save path is only half the ownership rule; the merge rule is the other.

    `_KEEP_LOCAL_FIELDS` resolves a conflicted field local-wins *silently*. That
    is right for per-checkout layout and wrong for anything shared — a shared key
    inheriting it would discard another checkout's change with no signal.
    Deriving it from `BOARD_KEYS` would do exactly that. t1243_8 has now
    appended `boardgroup`, so `BOARD_KEYS - BOARD_LAYOUT_KEYS` is non-empty and
    the assertion below is LIVE rather than vacuous — it was written ahead of
    the key precisely so the boundary could never be crossed silently.
    """

    def test_keep_local_fields_is_exactly_the_layout_set(self):
        import aitask_merge
        self.assertEqual(set(aitask_merge._KEEP_LOCAL_FIELDS),
                         set(BOARD_LAYOUT_KEYS))

    def test_no_shared_board_key_is_ever_local_wins(self):
        """Keeps meaning as `BOARD_KEYS` grows — this is the assertion that
        fails if anyone re-points `_KEEP_LOCAL_FIELDS` at `BOARD_KEYS`."""
        import aitask_merge
        shared = set(BOARD_KEYS) - set(BOARD_LAYOUT_KEYS)
        # Guard against silent vacuity: before t1243_8 this set was empty and
        # the assertion below held trivially. If a future refactor collapses the
        # two sets again, fail here rather than pass for no reason.
        self.assertTrue(shared, "no shared board key exists — this test is "
                                "vacuous; re-check the BOARD_KEYS split")
        self.assertEqual(shared & set(aitask_merge._KEEP_LOCAL_FIELDS), set(),
                         "a shared board key must opt in to its own merge rule, "
                         "never inherit silent local-wins")


if __name__ == "__main__":
    unittest.main()
