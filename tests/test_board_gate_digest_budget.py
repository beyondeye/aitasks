"""Board code-digest budget AND invalidation contract (t1416).

The board re-validates code-bound gate signatures per task on every refresh. The
digest that check needs is **repo-global**, so it is memoised once per refresh
cycle on `TaskManager` rather than computed per task.

A memo like that has two failure modes, and only one of them is visible in a
single refresh:

* **Too many computations** — a per-task digest would put N git subprocess
  triples on the refresh path. Pinned by the exact call counts below.
* **Too few** — a memo that outlives its refresh cycle freezes every signature
  verdict for the life of the process, so a stale approval keeps reading valid
  (or a fresh one keeps reading stale) until the board is restarted. A
  single-refresh count cannot see this at all: it looks *better* the more broken
  it is. Pinned by the two-refresh tests, which mutate code **between** refreshes
  and require the verdict to flip, and flip back on re-signing.

Scope boundary: these drive `TaskManager` (where the memo lives) rather than a
booted Textual app. The App-level path is covered structurally instead — the
frozen registry in `ClearGateCacheCallersTest` pins exactly which methods drop
the cache, which is what stops the digest acquiring a second lifetime.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_board_gate_digest_budget -v
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(REPO_ROOT / "tests" / "lib"),
           str(REPO_ROOT / ".aitask-scripts"),
           str(REPO_ROOT / ".aitask-scripts" / "board"),
           str(REPO_ROOT / ".aitask-scripts" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import board_fixture as bf  # noqa: E402
import gate_ledger as gl  # noqa: E402

BOARD_SRC = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"

GATED_TASK = """---
priority: medium
effort: low
status: Implementing
issue_type: feature
gates: [review_approved]
active_gates: [review_approved]
boardcol: c1
boardidx: 10
---

## Context

Synthetic gated task.

## Gate Runs

> **✅ gate:review_approved** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human
"""


class _DigestFixture(unittest.TestCase):
    """A non-branch-mode fixture tree that is itself a git repo.

    `branch_mode=True` inits git inside `.aitask-data/`, leaving the tree root
    without a repo — `code_digest()` would return None there and every assertion
    below would pass vacuously. `branch_mode=False` puts the repo at the root,
    which is what the board actually runs against.
    """

    N_GATED = 4

    def setUp(self):
        self.tree, self.ab = bf.enter_fixture_tree(
            self.addCleanup, tag=self.id().rsplit(".", 1)[-1], branch_mode=False)
        self.env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

        # The witness dir must be gitignored BEFORE any digest is taken: writing
        # a witness is otherwise an untracked-file change that moves the very
        # digest the witness records, and nothing would ever read "fresh".
        (self.tree / ".gitignore").write_text(".aitask-gates/\n", encoding="utf-8")
        (self.tree / "code.txt").write_text("seed\n", encoding="utf-8")
        self._git("add", "-A", ".")
        self._git("commit", "-q", "--no-verify", "-m", "digest fixture")

        # Gated tasks live under aitasks/, which _DIGEST_EXCLUDES omits — editing
        # them never perturbs the digest, exactly as in a real repo.
        self.gated_ids = []
        for i in range(self.N_GATED):
            tid = f"95{i:02d}"
            (self.tree / "aitasks" / f"t{tid}_gated.md").write_text(
                GATED_TASK, encoding="utf-8")
            self.gated_ids.append(tid)

        # Keep an UNCOUNTED reference for the fixture's own signing, captured
        # before the spy goes in: the fixture computing a digest to stamp a
        # witness is not the board computing one, and folding the two together
        # would make every call-count assertion below ambiguous.
        self._real_digest = gl.code_digest
        self.calls = {"n": 0}

        def counting(*a, **k):
            self.calls["n"] += 1
            return self._real_digest(*a, **k)

        self.ab.gate_ledger.code_digest = counting
        self.addCleanup(setattr, self.ab.gate_ledger, "code_digest",
                        self._real_digest)

    def _git(self, *args):
        subprocess.run(["git", *args], cwd=self.tree, env=self.env, check=True,
                       capture_output=True)

    def _digest(self) -> str:
        # No chdir: `enter_fixture_tree` already made the tree the process cwd,
        # which is what `code_digest()` reads. Reaching for os.chdir here would
        # also trip the live-tree sweep guard in test_board_fixture_harness.
        return self._real_digest()

    def _sign_all(self):
        digest = self._digest()
        self.assertIsNotNone(digest, "fixture must have a computable digest")
        for tid in self.gated_ids:
            d = self.tree / ".aitask-gates" / f"t{tid}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "review_approved.signed").write_text(
                f"signer=tester\ncode_digest={digest}\n", encoding="utf-8")

    def _unsign_all(self):
        for tid in self.gated_ids:
            p = self.tree / ".aitask-gates" / f"t{tid}" / "review_approved.signed"
            if p.exists():
                p.unlink()

    def _mutate_code(self):
        with open(self.tree / "code.txt", "a", encoding="utf-8") as fh:
            fh.write("changed\n")

    # --- one "refresh cycle", the same sequence refresh_board performs -----

    def _refresh(self, manager):
        """Drop the per-cycle caches, then render the surface that reads them."""
        manager.clear_gate_cache()
        return manager.get_inflight_items()

    def _new_manager(self):
        manager = self.ab.TaskManager()
        manager.load_tasks()
        return manager

    def _actions(self, items):
        # InFlightItem.task_id carries the `t` prefix (TaskCard._parse_filename).
        return {it.task_id: it.next_action for it in items}

    @property
    def first_gated(self) -> str:
        return f"t{self.gated_ids[0]}"

    def _gated_items(self, items):
        want = {f"t{t}" for t in self.gated_ids}
        return [it for it in items if it.task_id in want]


class DigestBudgetTest(_DigestFixture):
    def test_no_witness_costs_no_digest_at_all(self):
        """The pre-filter must short-circuit before the memo is ever consulted."""
        manager = self._new_manager()
        self.calls["n"] = 0
        items = self._refresh(manager)
        self.assertTrue(items, "no in-flight items — the budget check would be vacuous")
        self.assertEqual(self.calls["n"], 0)

    def test_many_signed_tasks_cost_exactly_one_digest(self):
        self._sign_all()
        manager = self._new_manager()
        self.calls["n"] = 0
        items = self._refresh(manager)
        gated = self._gated_items(items)
        self.assertEqual(len(gated), self.N_GATED,
                         "all gated tasks must render, or one digest proves nothing")
        # Exactly, never assertLessEqual: a silent drop to 0 would mean the
        # re-validation stopped happening, which this must also catch.
        self.assertEqual(self.calls["n"], 1)


class DigestInvalidationTest(_DigestFixture):
    def test_second_refresh_after_a_code_change_recomputes_and_flips(self):
        self._sign_all()
        manager = self._new_manager()

        self.calls["n"] = 0
        before = self._actions(self._refresh(manager))
        self.assertEqual(self.calls["n"], 1)
        self.assertEqual(before[self.first_gated], "all gates pass — archive/re-enter")

        # The code moves; the task files do not.
        self._mutate_code()

        after = self._actions(self._refresh(manager))
        self.assertEqual(self.calls["n"], 2,
                         "the memo must be dropped per refresh, not per process")
        self.assertEqual(after[self.first_gated],
                         "awaiting re-sign: review_approved")

    def test_re_signing_flips_it_back(self):
        """The memo tracks the digest in BOTH directions rather than latching."""
        self._sign_all()
        manager = self._new_manager()
        self._refresh(manager)
        self._mutate_code()
        self.assertEqual(self._actions(self._refresh(manager))[self.first_gated],
                         "awaiting re-sign: review_approved")
        self._sign_all()                      # re-sign against the NEW code state
        self.assertEqual(self._actions(self._refresh(manager))[self.first_gated],
                         "all gates pass — archive/re-enter")

    def test_load_tasks_also_drops_the_memo(self):
        """`load_tasks` is the other entry point that clears the gate cache."""
        self._sign_all()
        manager = self._new_manager()
        self._refresh(manager)
        self._mutate_code()
        manager.load_tasks()                  # NOT clear_gate_cache directly
        self.assertEqual(self._actions(manager.get_inflight_items())[self.first_gated],
                         "awaiting re-sign: review_approved")

    def test_gate_summary_shows_both_facts(self):
        self._sign_all()
        manager = self._new_manager()
        self._refresh(manager)
        self._mutate_code()
        item = next(it for it in self._refresh(manager)
                    if it.task_id == self.first_gated)
        self.assertIn("review_approved:pass (stale signature)", item.gate_summary)
        self.assertEqual(item.stale_signed, ["review_approved"])

    def test_a_pinned_memo_would_be_caught(self):
        """Negative control for the invalidation tests.

        Simulates the exact defect they exist to catch — a memo that survives the
        refresh — by re-priming it after every clear. If the assertions above
        could pass with a pinned memo, they would be testing nothing.
        """
        self._sign_all()
        manager = self._new_manager()
        self._refresh(manager)
        pinned = manager.gate_digest_cache
        self._mutate_code()
        manager.clear_gate_cache()
        manager.gate_digest_cache = pinned          # the defect, injected
        actions = self._actions(manager.get_inflight_items())
        self.assertEqual(actions[self.first_gated], "all gates pass — archive/re-enter",
                         "a pinned memo must produce the WRONG verdict here; if it "
                         "does not, the two-refresh tests are not discriminating")


class ClearGateCacheCallersTest(unittest.TestCase):
    """FROZEN: exactly which methods drop the per-refresh gate caches.

    The digest memo is invalidated in `clear_gate_cache` and nowhere else, so
    "which methods call it" IS the memo's lifetime. A new caller (or a lost one)
    must be a conscious edit here rather than a silent change in how long a
    signature verdict is trusted.
    """

    EXPECTED_CALLERS = {"load_tasks", "refresh_board"}

    def _callers_of(self, name: str) -> set[str]:
        tree = ast.parse(BOARD_SRC.read_text(encoding="utf-8"))
        found: set[str] = set()
        stack: list[str] = []

        class V(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr == name and stack:
                    found.add(stack[-1])
                self.generic_visit(node)

        V().visit(tree)
        return found

    def test_clear_gate_cache_callers_are_exactly_the_refresh_entry_points(self):
        callers = self._callers_of("clear_gate_cache")
        self.assertTrue(callers, "no callers found — the scan would pass vacuously")
        self.assertEqual(callers, self.EXPECTED_CALLERS)

    def test_digest_memo_is_reset_only_in_clear_gate_cache(self):
        """Assignment sites of `gate_digest_cache = _DIGEST_UNSET`."""
        tree = ast.parse(BOARD_SRC.read_text(encoding="utf-8"))
        sites: set[str] = set()
        stack: list[str] = []

        class V(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def _record(self, targets, value):
                if not (isinstance(value, ast.Name) and value.id == "_DIGEST_UNSET"):
                    return
                for t in targets:
                    if (isinstance(t, ast.Attribute)
                            and t.attr == "gate_digest_cache" and stack):
                        sites.add(stack[-1])

            def visit_Assign(self, node):
                self._record(node.targets, node.value)
                self.generic_visit(node)

            def visit_AnnAssign(self, node):
                # `self.gate_digest_cache: T = _DIGEST_UNSET` is an AnnAssign,
                # not an Assign — missing it would let the __init__ seed silently
                # drop out of the frozen set.
                if node.value is not None:
                    self._record([node.target], node.value)
                self.generic_visit(node)

        V().visit(tree)
        self.assertEqual(sites, {"__init__", "clear_gate_cache"})


if __name__ == "__main__":
    unittest.main()
