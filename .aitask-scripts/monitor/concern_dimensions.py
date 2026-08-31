"""Single source of truth for the shadow concern impact-vector dimensions (t1636_1).

A shadow concern is a **proposed delta in a shared quality space**. Instead of an
undefined `high/medium/low` severity, each concern declares a signed impact
vector whose improve side and worsen side draw from the *same* closed
vocabulary::

    Improves: robustness(high), verification(medium). Worsens: simplicity(low). Effort: low.

This module owns that vocabulary, the magnitude semantics, the obligation core
the disposition rubric grounds in, and the canonical marker-priority mapping.
Every consumer — ``concern_parser.py`` (the trailer grammar), the shadow's
producer procedures, and the concern picker — reads them from here, so there is
no second copy to drift.

The prose definition lives in ``.claude/skills/aitask-shadow/concern-format.md``.
That doc and :data:`CONCERN_DIMENSIONS` are held in lockstep by
``tests/test_concern_dimensions.py``, which compares the doc's table rows to
this table field-by-field.

**The vocabulary is closed, and users must NOT extend it.** Like
``lib/followup_kinds.py`` and unlike ``labels.txt`` / ``task_types.txt``, these
names are *framework-semantic*: the parser builds a regex alternation from them,
so an unknown name is not a new category but a sentence the parser refuses to
match. That refusal is deliberate and visible (the text stays in the concern
body) rather than silent — see ``concern-format.md``.

**Why `maintainability` and `simplicity` are separate.** Extracting a shared
helper *improves* maintainability while *worsening* simplicity. Merged into one
"code health" scalar that trade cancels itself out — and pricing added mechanism
is the entire reason the Worsens side is mandatory.

**Purity contract.** No I/O, no ``sys.path`` insertion, no tmux, no third-party
imports. ``concern_parser.py`` is contractually pure and imports this as a plain
sibling; anything heavier here would break that guarantee.
"""
from __future__ import annotations

#: Dimension name -> (short display label, one-line rubric).
#:
#: **Declaration order is the canonical order.** Producers enumerate entries in
#: it and the picker renders in it, so reordering this dict is a behavioural
#: change, not a cosmetic one.
CONCERN_DIMENSIONS: "dict[str, tuple[str, str]]" = {
    "goal": (
        "goal",
        "the task's AC / the user's stated intent is delivered",
    ),
    "correctness": (
        "corr",
        "right behavior on reachable inputs",
    ),
    "robustness": (
        "robus",
        "stability under failure / concurrency / hostile input (includes security)",
    ),
    "performance": (
        "perf",
        "latency, throughput, resource cost",
    ),
    "verification": (
        "verif",
        "testability; proof the change works",
    ),
    "maintainability": (
        "maint",
        "readability, duplication, conventions; ease of safe change",
    ),
    "simplicity": (
        "simpl",
        "amount of mechanism; the classic worsen-side",
    ),
}

VALID_DIMENSIONS: frozenset = frozenset(CONCERN_DIMENSIONS)

#: The dimensions that are *categorically* obligations: a concern whose improve
#: side touches one of these is `blocking` by the disposition rubric, because
#: failing them means the task did not do what it was asked to do.
#:
#: `robustness` and `performance` become obligation-touching **only when the
#: task's own AC or plan obligates them** — a per-task judgement made by the
#: producing agent against that task's text, which is why it cannot live in a
#: static set. This module records the categorical core; the rubric that applies
#: it per task lives in ``impl-review-angles.md``.
OBLIGATION_DIMENSIONS: frozenset = frozenset({"goal", "correctness"})

#: Magnitude vocabulary, **strongest first** — :func:`derive_priority` walks this
#: tuple in order, so it is the single place the ranking is written down.
#:
#: Magnitudes are *advisory*: LLM calibration of them is noisy, and the named
#: dimension is the load-bearing part of a vector. They refine a concern; they
#: never decide whether it is one.
MAGNITUDES = ("high", "medium", "low")

#: Maximum width of a short label, in terminal cells. See
#: :func:`check_label_widths` for the derivation.
MAX_LABEL_CELLS = 5


def check_label_widths(dimensions) -> None:
    """Raise ``ValueError`` unless every short label fits the picker's budget.

    **Where the bound comes from.** The concern picker's narrow layout
    (minimonitor's companion pane) renders a vector-bearing row's trade profile
    on its own line, indented to line up with the body.

    **The budget is the ROW's width, not the screen's** — the row sits inside the
    dialog border, the dialog padding and its own padding, so the two are not the
    same number. This is where the original derivation went wrong (t1636_4): it
    read "24 columns" as the row width and computed ``24 - 3 = 21`` cells at the
    narrowest supported pane. Measured through ``App.run_test``:

    ====== ========= ==========================
    screen row width cells after the 3-space indent
    ====== ========= ==========================
    40     28        25
    30     24        21
    24     18        15
    ====== ========= ==========================

    So 21 cells is really screen **30**; the true floor (24 columns,
    ``concern_parser``'s ``_SENTINEL_SAFE_COLS``) leaves **15** indented, or
    **18** with the indent dropped. The mandatory core is one improve token, one
    worsen token and the effort scalar::

        2 * (1 + W + 1)  arrow + label + optional unspecified '?'
      +  2               the two separating spaces
      +  4               the effort token ('E:hi')
      = 20 cells at W = 5

    20 does not fit 15, and not even 18. ``W <= 5`` therefore holds **only via
    the degradation ladder** in ``monitor_shared.trade_profile``, whose last two
    rungs drop the indent and then the ``?`` markers, giving
    ``▲maint ▼simpl E:hi`` = ``2 * (1 + W) + 2 + 4 = 18`` — an exact fit at the
    floor, and where ``W <= 5`` actually comes from.

    If that geometry ever changes, this is the constant to re-derive — and
    ``ConcernRowVectorPackingTests.test_row_geometry_is_pinned_at_every_supported_width``
    is what makes the change fail loudly instead of silently clipping the effort
    scalar off the end of the line.

    **Two properties, not one.** ``len()`` counts *characters* while the bound is
    stated in *cells*, so the labels are also pinned as ASCII — that is what
    makes ``len()`` an exact cell count here rather than an assumption. A label
    is likewise required to be non-empty: a zero-width label would satisfy the
    numeric bound and render as a bare arrow.

    Called at import time on :data:`CONCERN_DIMENSIONS`. Deliberately a ``raise``
    and **not** an ``assert``: ``python -O`` strips assertions, which would leave
    this guard silently checking nothing.
    """
    for name, (label, _rubric) in dimensions.items():
        if not label:
            raise ValueError(f"concern dimension {name!r} has an empty short label")
        if not label.isascii():
            raise ValueError(
                f"concern dimension {name!r} has a non-ASCII short label {label!r}; "
                f"labels must be ASCII so len() is an exact terminal-cell count"
            )
        if len(label) > MAX_LABEL_CELLS:
            raise ValueError(
                f"concern dimension {name!r} has short label {label!r} "
                f"({len(label)} cells); the narrow picker budget allows at most "
                f"{MAX_LABEL_CELLS} — see check_label_widths.__doc__"
            )


check_label_widths(CONCERN_DIMENSIONS)


def validate_dimension(name) -> bool:
    """True when ``name`` is a member of the closed vocabulary."""
    return name in VALID_DIMENSIONS


def dimensions_pipe() -> str:
    """Sorted pipe-separated alternation, for the parser's regex builder.

    Mirrors ``followup_kinds.followup_kinds_pipe()``. Sorted rather than in
    declaration order because this is a *matcher* input, where a stable string
    matters and the canonical ordering does not.
    """
    return "|".join(sorted(VALID_DIMENSIONS))


def label_for(name) -> str:
    """Short display label, or ``""`` when the dimension is unknown/absent."""
    entry = CONCERN_DIMENSIONS.get(name)
    return entry[0] if entry else ""


def rubric_for(name) -> str:
    """One-line rubric, or ``""`` when the dimension is unknown/absent."""
    entry = CONCERN_DIMENSIONS.get(name)
    return entry[1] if entry else ""


def normalize_magnitude(raw) -> str:
    """Canonicalise a magnitude token; unrecognised or absent becomes ``""``.

    ``""`` means **unspecified**, and it is never silently promoted to ``low``.
    Degrading an unknown magnitude to the weakest real value would understate a
    cost on the *worsen* side — the unsafe direction for a mechanism whose whole
    purpose is to make a reviewer price its own suggestion. Surfaces render the
    unspecified state as ``?`` instead; the dimension itself is never dropped.
    """
    if not isinstance(raw, str):
        return ""
    value = raw.strip().lower()
    return value if value in MAGNITUDES else ""


def derive_priority(improves) -> str:
    """The canonical concern-marker priority for a vector-bearing concern.

    The **max magnitude over the improve entries whose magnitude is known**
    (``high`` > ``medium`` > ``low``). An absent improve sentence (``None``), a
    priced-empty one (``()``), and one whose entries all carry unspecified
    magnitudes each yield ``"low"``.

    This is the *single* mapping from a vector to the ``- [priority | region]``
    marker: producers emit the marker priority equal to it, and the picker badge
    shows it, flagging a disagreeing marker rather than reconciling it silently.
    Keeping it here is what stops the original undefined severity scalar
    surviving as a second, divergent rule.

    ``improves`` is any iterable of ``(dimension, magnitude)`` pairs. Entries are
    read **by index**, which covers both plain tuples and the parser's
    ``ImpactEntry`` NamedTuple.
    """
    if not improves:
        return "low"
    known = {normalize_magnitude(entry[1]) for entry in improves}
    for magnitude in MAGNITUDES:  # strongest first
        if magnitude in known:
            return magnitude
    return "low"
