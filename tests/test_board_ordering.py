"""Unit tests for lib/board_ordering.py -- the board's gap-indexing arithmetic (t1243_3).

Pure and fast: no board import, no Textual, no temp tree. The module under test
imports nothing but stdlib, so this file only needs `.aitask-scripts/lib` on
`sys.path`.

The load-bearing test here is `StrideForTests.test_respace_then_insert_always_fits`:
it expresses the compaction *guarantee* as a property rather than as prose --
after `respace_indices(n, stride_for(k))` every adjacent gap admits `k` interior
values, which is why `TaskManager`'s post-respace retry can never fail and why
there is never a second compaction.

Run: python3 -m unittest tests.test_board_ordering -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_LIB = REPO_ROOT / ".aitask-scripts" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import board_ordering as BO  # noqa: E402


class StepTests(unittest.TestCase):
    def test_step_is_a_power_of_two(self):
        """Halving a power-of-two gap reaches width 1 in exactly log2(STEP) steps,
        which is what the documented '~10 inserts into the same gap' bound means."""
        self.assertEqual(BO.STEP & (BO.STEP - 1), 0)
        self.assertEqual(BO.STEP, 1024)


class AppendPrependTests(unittest.TestCase):
    def test_append_to_empty_column(self):
        self.assertEqual(BO.index_for_append([]), BO.STEP)

    def test_prepend_to_empty_column(self):
        self.assertEqual(BO.index_for_prepend([]), BO.STEP)

    def test_append_is_past_the_maximum(self):
        self.assertEqual(BO.index_for_append([10, 20, 30]), 30 + BO.STEP)

    def test_prepend_is_below_the_minimum(self):
        self.assertEqual(BO.index_for_prepend([10, 20, 30]), 10 - BO.STEP)

    def test_prepend_goes_negative_and_that_is_legal(self):
        """Readers only sort and normalize_board_idx passes ints through, so a
        negative index is what makes 'move to top' a single write."""
        self.assertEqual(BO.index_for_prepend([10]), -1014)
        self.assertLess(BO.index_for_prepend([10]), 10)

    def test_repeated_prepend_keeps_descending(self):
        col = [10, 20]
        for _ in range(3):
            new = BO.index_for_prepend(col)
            self.assertLess(new, min(col))
            col.append(new)

    def test_unordered_input_is_not_assumed_sorted(self):
        self.assertEqual(BO.index_for_append([30, 10, 20]), 30 + BO.STEP)
        self.assertEqual(BO.index_for_prepend([30, 10, 20]), 10 - BO.STEP)

    def test_accepts_any_iterable(self):
        self.assertEqual(BO.index_for_append(iter([10, 20])), 20 + BO.STEP)
        self.assertEqual(BO.index_for_prepend(iter([10, 20])), 10 - BO.STEP)

    def test_negative_column_appends_and_prepends(self):
        self.assertEqual(BO.index_for_append([-30, -20]), -20 + BO.STEP)
        self.assertEqual(BO.index_for_prepend([-30, -20]), -30 - BO.STEP)


class IndexBetweenTests(unittest.TestCase):
    def test_wide_gap(self):
        self.assertEqual(BO.index_between(0, 1024), 512)

    def test_gap_of_three(self):
        self.assertEqual(BO.index_between(10, 13), 11)

    def test_at_bound_gap_of_two_still_fits(self):
        """hi - lo == 2 is the tightest interval that still has an interior
        value; it must NOT trigger compaction."""
        self.assertEqual(BO.index_between(10, 12), 11)

    def test_gap_of_one_is_exhausted(self):
        self.assertIsNone(BO.index_between(10, 11))

    def test_tie_is_exhausted(self):
        """Equal indices are reachable in production -- delete_column assigns
        board_idx = 0 to every evicted task."""
        self.assertIsNone(BO.index_between(10, 10))

    def test_inverted_interval_is_exhausted(self):
        self.assertIsNone(BO.index_between(20, 10))

    def test_result_is_strictly_interior(self):
        for lo, hi in ((0, 1024), (10, 12), (-1024, 0), (-50, 50), (7, 9)):
            with self.subTest(lo=lo, hi=hi):
                mid = BO.index_between(lo, hi)
                self.assertIsNotNone(mid)
                self.assertLess(lo, mid)
                self.assertLess(mid, hi)

    def test_negative_interval(self):
        self.assertEqual(BO.index_between(-2048, -1024), -1536)

    def test_interval_spanning_zero(self):
        self.assertEqual(BO.index_between(-1024, 1024), 0)

    def test_floor_division_does_not_round_toward_zero_on_negatives(self):
        """`(lo + hi) // 2` floors, so a negative interval still lands strictly
        inside rather than colliding with `hi`."""
        mid = BO.index_between(-5, -2)
        self.assertEqual(mid, -4)
        self.assertLess(-5, mid)
        self.assertLess(mid, -2)


class IndicesBetweenTests(unittest.TestCase):
    def test_zero_and_negative_k_return_empty(self):
        self.assertEqual(BO.indices_between(0, 10, 0), [])
        self.assertEqual(BO.indices_between(0, 10, -1), [])

    def test_single_value_matches_the_interval_bound(self):
        self.assertIsNone(BO.indices_between(10, 11, 1))
        self.assertEqual(BO.indices_between(10, 12, 1), [11])

    def test_exhausted_when_gap_is_too_narrow(self):
        self.assertIsNone(BO.indices_between(10, 13, 3))
        self.assertIsNone(BO.indices_between(0, 3, 5))

    def test_at_bound_exactly_fits(self):
        """hi - lo == k + 1 is the tightest interval that holds k values."""
        for k in range(1, 6):
            with self.subTest(k=k):
                got = BO.indices_between(0, k + 1, k)
                self.assertEqual(got, list(range(1, k + 1)))

    def test_results_are_distinct_interior_and_ascending(self):
        for k in range(1, 6):
            for lo, hi in ((0, 1024), (-1024, 0), (-50, 50), (10, 10 + k + 1)):
                with self.subTest(k=k, lo=lo, hi=hi):
                    got = BO.indices_between(lo, hi, k)
                    self.assertIsNotNone(got)
                    self.assertEqual(len(got), k)
                    self.assertEqual(len(set(got)), k, "values must be distinct")
                    self.assertEqual(got, sorted(got), "values must ascend")
                    self.assertTrue(all(lo < v < hi for v in got),
                                    f"values must be strictly interior: {got}")

    def test_tie_and_inversion_are_exhausted(self):
        self.assertIsNone(BO.indices_between(10, 10, 1))
        self.assertIsNone(BO.indices_between(20, 10, 1))


class RespaceIndicesTests(unittest.TestCase):
    def test_empty_column(self):
        self.assertEqual(BO.respace_indices(0), [])

    def test_default_stride(self):
        self.assertEqual(BO.respace_indices(3), [1024, 2048, 3072])

    def test_explicit_stride(self):
        self.assertEqual(BO.respace_indices(3, stride=10), [10, 20, 30])

    def test_every_gap_equals_the_stride(self):
        for stride in (10, 1024, 2048):
            with self.subTest(stride=stride):
                out = BO.respace_indices(5, stride=stride)
                gaps = {b - a for a, b in zip(out, out[1:])}
                self.assertEqual(gaps, {stride})

    def test_first_value_is_the_stride_not_zero(self):
        """Starting at `stride` rather than 0 leaves room for one prepend that
        does not need to go negative, and keeps legacy 10/20/30 recognisable."""
        self.assertEqual(BO.respace_indices(1, stride=10), [10])


class StrideForTests(unittest.TestCase):
    def test_small_k_uses_step(self):
        for k in (0, 1, 2, 500, 1022, 1023):
            with self.subTest(k=k):
                self.assertEqual(BO.stride_for(k), BO.STEP)

    def test_boundary_trio(self):
        """K = 1023/1024/1025 is where a fixed STEP would silently stop
        guaranteeing the retry -- the unstated cap stride_for removes."""
        self.assertEqual(BO.stride_for(1023), 1024)
        self.assertEqual(BO.stride_for(1024), 2048)
        self.assertEqual(BO.stride_for(1025), 2048)

    def test_result_is_always_a_power_of_two(self):
        for k in (0, 1, 7, 1023, 1024, 1025, 4095, 4096):
            with self.subTest(k=k):
                s = BO.stride_for(k)
                self.assertEqual(s & (s - 1), 0, f"{s} is not a power of two")

    def test_stride_always_exceeds_k(self):
        for k in (0, 1, 1023, 1024, 1025, 5000):
            with self.subTest(k=k):
                self.assertGreaterEqual(BO.stride_for(k), k + 1)

    def test_respace_then_insert_always_fits(self):
        """THE compaction guarantee, as a property.

        After one respace at `stride_for(k)`, every adjacent gap admits k
        interior values -- so the retry cannot fail and there is never a second
        compaction. This is the exact invariant t1243_11's block insert relies
        on, and the reason TaskManager can assert (rather than handle) a failed
        retry.
        """
        for k in (1, 2, 1022, 1023, 1024, 1025, 2047, 2048):
            stride = BO.stride_for(k)
            col = BO.respace_indices(4, stride=stride)
            for lo, hi in zip(col, col[1:]):
                with self.subTest(k=k, lo=lo, hi=hi):
                    self.assertIsNotNone(
                        BO.indices_between(lo, hi, k),
                        f"gap {hi - lo} at stride {stride} must hold k={k}")
            # The single-insert form used by reposition_task must fit too.
            self.assertIsNotNone(BO.index_between(col[0], col[1]))

    def test_step_stride_would_not_suffice_above_the_cap(self):
        """Negative control for the previous test: a fixed STEP genuinely fails
        at k = STEP, so stride_for is load-bearing rather than decorative."""
        col = BO.respace_indices(2, stride=BO.STEP)
        self.assertIsNone(BO.indices_between(col[0], col[1], BO.STEP))
        self.assertIsNotNone(BO.indices_between(col[0], col[1], BO.STEP - 1))


if __name__ == "__main__":
    unittest.main()
