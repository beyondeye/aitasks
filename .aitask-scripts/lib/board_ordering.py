"""board_ordering.py - gap-indexing arithmetic for the board's `boardidx` field.

Extracted as a pure module (t1243_3) so the board's ordering arithmetic is
import-testable without Textual, mirroring how lib/topic_semantics.py was
extracted. The board imports these functions back and remains the SEMANTIC
OWNER of the ordering rules: any change here must keep
tests/test_board_ordering.py, tests/test_board_manager_moves.py AND
tests/test_board_movement.py's flip table green in the same commit.

Why this exists
---------------
`TaskManager.normalize_indices` used to renumber a whole column to 10/20/30
after every move, so moving one card rewrote frontmatter in up to two columns
the user never touched -- pure git churn on the shared `aitask-data` branch,
where `boardidx` is resolved silently local-wins. Gap indexing places a card
*between* its neighbours instead, so a move writes exactly one file.

Contract
--------
Every argument is an **already-coerced int** -- callers pass values through
`task_yaml.normalize_board_idx` first; this module never sees a raw frontmatter
value and does no coercion of its own.

`int` stays the on-disk type and **negative values are legal**: readers only
sort (`TaskManager.get_column_tasks` orders by
`(normalize_board_idx(idx), filename)`), and `normalize_board_idx` returns an
int unchanged. That is exactly what lets "move to top" be one write rather than
a renumber.

`indices_between` has **no production caller in this child** -- every board
operation today places either one task into a bounded interval
(`index_between`) or a run past a column extremum (`index_for_append` /
`index_for_prepend`). Its consumer is t1243_11's K-wide block insert. It lands
here because this module is the arithmetic home and splitting it from
`stride_for` would leave that guarantee unexpressible; it is covered by
pure-module unit tests. This note exists so its absence from the call graph is
not mistaken for dead code.
"""

STEP = 1024  # power of two -> ~10 midpoint halvings before a gap exhausts


def index_for_append(indices):
    """Index that sorts after every value in ``indices`` (``STEP`` when empty).

    ``indices`` must exclude the task being moved, so a card already holding
    the column maximum still lands strictly below it.
    """
    values = list(indices)
    return (max(values) + STEP) if values else STEP


def index_for_prepend(indices):
    """Index that sorts before every value in ``indices`` (``STEP`` when empty).

    Returns a negative value for a column starting below ``STEP`` -- that is
    intended, and is what makes "move to top" a single write. ``indices`` must
    exclude the task being moved.
    """
    values = list(indices)
    return (min(values) - STEP) if values else STEP


def index_between(lo, hi):
    """Midpoint strictly between ``lo`` and ``hi``, or ``None`` when none exists.

    ``None`` means the interval is exhausted (``hi - lo < 2``, including ties
    and inversions) and the caller must respace the column before retrying.
    """
    if hi - lo < 2:
        return None
    return (lo + hi) // 2


def indices_between(lo, hi, k):
    """``k`` distinct ascending ints strictly between ``lo`` and ``hi``.

    ``None`` when the interval cannot hold ``k`` interior values
    (``hi - lo < k + 1``). With ``hi - lo >= k + 1`` the step is at least 1 and
    ``lo + step * k <= hi - step < hi``, so the results are distinct and
    strictly interior.
    """
    if k <= 0:
        return []
    if hi - lo < k + 1:
        return None
    step = (hi - lo) // (k + 1)
    return [lo + step * (j + 1) for j in range(k)]


def respace_indices(n, stride=STEP):
    """Canonical ``stride``-spaced indices for a column of ``n`` tasks.

    Every adjacent gap is exactly ``stride``, which is what makes a
    ``stride_for(k)``-strided respace guarantee that a following
    ``indices_between(.., k)`` succeeds.
    """
    return [(i + 1) * stride for i in range(n)]


def _next_pow2(n):
    """Smallest power of two >= ``n`` (1 for ``n <= 1``)."""
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def stride_for(k):
    """Respace stride guaranteeing room for ``k`` interior values per gap.

    A fixed ``STEP`` would only guarantee the post-respace retry for
    ``k <= STEP - 1``; deriving the stride from the pending insert size removes
    that unstated cap, so the retry is guaranteed for **any** ``k`` and there is
    never a second compaction.
    """
    return max(STEP, _next_pow2(k + 1))
