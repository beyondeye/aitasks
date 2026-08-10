"""board_groups.py - in-column task groups derived from the `boardgroup` field.

Extracted as a pure module (t1243_8) so the grouping derivation is
import-testable without Textual, mirroring how lib/topic_semantics.py and
lib/board_ordering.py were extracted. The board imports these functions back and
remains the SEMANTIC OWNER of the grouping rules: any change here must keep
tests/test_board_groups.py green in the same commit.

Functions are duck-typed over task objects exposing ``.filename`` (the task
file's basename) and ``.metadata`` (parsed frontmatter dict) -- the board's
``Task`` and lib/trail_gather.py's row type both qualify.

What a group is
---------------
A group is ``(column, slug)``: tasks in the same column sharing a non-empty
``boardgroup`` slug. There is no registry, no ids and no title/colour store --
identity IS the slug, and the display title is the slug rendered for humans
(``perf_work`` -> "perf work"). A single-member group renders as a plain card,
mirroring how ``_build_topic_lanes`` collapses singleton lanes into "Ungrouped".

INV-R (render determinism)
--------------------------
A column's rendered order is a **pure, total function of the persisted state of
that column's tasks**. Two checkouts holding identical task files render
identical order, and reloading after any operation reproduces the order that was
on screen.

Contiguity of ``boardidx`` is explicitly **NOT** an invariant, and cannot be:
``boardgroup`` is shared across checkouts while ``boardidx`` stays per-checkout
(local-wins). After a sync a remotely-added member arrives carrying the group but
keeping its own scattered index, and a remotely-removed member arrives with the
tombstone but not the sender's repositioning write. Repairing that on load would
rewrite task files every time the board opens after a sync, and two checkouts
could ping-pong repairs forever. So **grouping never writes an index** (forming a
group of K is K ``boardgroup`` writes; ungrouping one task is 1), a non-member
whose index falls between two members renders *outside* the block at its own key
position, and **no post-sync reconciliation exists or is needed**.

Totality is not automatic
-------------------------
``boardgroup`` is persisted YAML that a user may hand-edit and that arrives from
other checkouts, so ``parse_frontmatter`` can legally hand us ``None``, a list, a
dict, an int or a bool -- and ``lib/task_yaml.py`` deliberately leaves malformed
input "type-honest" for the consumer rather than sanitizing it (see
``_normalize_task_ids``). ``boardgroup: []`` is both non-empty and **unhashable**,
so using a raw value as a bucket key raises ``TypeError`` and takes the whole
board down. :func:`normalize_group_slug` is that boundary, and every consumer of
``boardgroup`` -- here, in the merge driver, and in t1243_9/10/11/12 -- must read
through it rather than touching the raw metadata value.

Reuse
-----
The **filter match predicate already exists** and is NOT re-exported here:
``aitask_board.task_matches_filter(task, visible, search)`` (t1243_4) is
module-level, app-free and per-task, so t1243_10 can evaluate a collapsed
group's members that mount no widget, and can *count* matches rather than only
ask a boolean. Do not reimplement it.
"""

from task_yaml import normalize_board_idx


def normalize_group_slug(raw):
    """Coerce a persisted ``boardgroup`` value into a group key (``""`` = none).

    Mirrors :func:`task_yaml.normalize_board_idx`'s contract: coerce junk
    deterministically, never raise. Only ``str`` values can become keys, which
    is what keeps the bucket map from ever being handed an unhashable key and
    keeps the derivation **total**.

    - a ``str`` with any non-whitespace content -> **returned verbatim**;
    - everything else -- ``None``, ``""``, whitespace-only, ``list``, ``dict``,
      ``int``, ``bool`` -> ``""`` (ungrouped).

    A string that does not match the CLI's ``^[a-z0-9_]+$`` slug shape (e.g. a
    hand-edited ``Perf Work``) is deliberately **kept** as its own group rather
    than discarded: it is hashable and sortable, so grouping still works, and
    silently dropping a user's hand edit would be worse than honouring it.
    ``aitask_update.sh --boardgroup`` rejects such input at the CLI, which is
    where shape is enforced; this function's job is only totality.

    **Whitespace is content, not noise -- do NOT ``.strip()`` here.** A quoted
    ``boardgroup: "perf_work "`` survives the YAML loader with its trailing
    space intact (only *unquoted* plain scalars are stripped by YAML itself), so
    stripping would make it collide with ``perf_work``: the task would silently
    join that group, and the merge driver would read it as UNCHANGED from an
    unspaced base and discard the user's edit. Both outcomes are exactly the
    silent coalescing the design forbids -- group merges must be confirmed,
    never inferred. Two near-identical groups are a *visible*, recoverable
    annoyance; a silent join is neither.

    ``int`` / ``bool`` are treated as typos rather than keys -- a group named
    ``42`` or ``True`` is far more likely a mistake than an intent, and coercing
    them with ``str()`` would let ``42`` and ``"42"`` silently collide.
    """
    if isinstance(raw, str):
        # Whitespace-only is semantically empty; anything else is verbatim.
        return raw if raw.strip() else ""
    return ""


def task_group_slug(task):
    """Normalized group slug of a task (``""`` when ungrouped)."""
    return normalize_group_slug(task.metadata.get("boardgroup"))


def column_sort_key(task):
    """The within-column ordering key: ``(normalize_board_idx, filename)``.

    The SAME key ``TaskManager.get_column_tasks`` sorts by, exported so a caller
    cannot accidentally derive a different one. Read from ``metadata`` rather
    than a board-specific property so non-board consumers can use it too.
    """
    return (normalize_board_idx(task.metadata.get("boardidx", 0)), task.filename)


def build_column_units(tasks):
    """Bucket one column's tasks into render units. Returns ``(slug, members)``.

    A **unit** is either a group (non-empty ``slug``, one or more members) or a
    singleton (``slug == ""``, exactly one member). Units are returned in render
    order; members are in walk order within their unit.

    The derivation, per INV-R:

    1. Walk the column's tasks sorted by :func:`column_sort_key`. A task with a
       non-empty normalized slug joins that slug's group unit; every other task
       is its own singleton unit.
    2. A unit's sort key is the key of its **first** member in that walk.
    3. Units are emitted in sort-key order.

    Because the walk is already in sort-key order, emitting units in
    **first-seen** order *is* emitting them in sort-key order -- so no second
    sort is needed, exactly as ``_build_topic_lanes`` builds lanes in first-seen
    order. The sort happens here rather than being assumed of the caller, so the
    result is a function of the persisted state alone and INV-R holds however
    the caller ordered its input.

    A single-member group keeps its slug (the caller decides to render it as a
    plain card); it is NOT downgraded to a singleton unit, so a group the user
    created is never silently dissolved by a member moving away.
    """
    buckets = {}
    units = []
    for task in sorted(tasks, key=column_sort_key):
        slug = task_group_slug(task)
        if not slug:
            units.append(("", [task]))
            continue
        members = buckets.get(slug)
        if members is None:
            members = []
            buckets[slug] = members
            units.append((slug, members))
        members.append(task)
    return units


def group_display_title(slug):
    """Human-readable title for a group slug (``perf_work`` -> ``perf work``)."""
    return normalize_group_slug(slug).replace("_", " ")


def group_members(tasks, slug):
    """Members of ``slug`` within ``tasks``, in walk order (``[]`` if none).

    Convenience for the collapsed-group paths in t1243_10, which need a group's
    members as **data** because none of them mount a widget.
    """
    target = normalize_group_slug(slug)
    if not target:
        return []
    return [t for t in sorted(tasks, key=column_sort_key)
            if task_group_slug(t) == target]


# --- Collapse-key algebra (t1243_10) -----------------------------------------
#
# A group's *view* state (collapsed / expanded) is per-user, so it lives in the
# USER layer of board_config as a list of ``"<col_id>/<slug>"`` keys. The key is
# composite, which means it goes stale whenever EITHER half changes -- hence the
# lifecycle owners in aitask_board.TaskManager. Everything about the key's
# shape, parsing and rewriting lives here, pure and unit-testable.

#: Separator between the two halves of a collapse key. The COLUMN half is
#: written first and contains no ``/`` for any id this framework generates
#: (``board_columns.generate_col_id`` emits ``^[a-z0-9_]+$``), while a
#: hand-edited ``boardgroup`` legitimately can -- so a key is split ONCE, from
#: the left, and never with ``str.split("/")``.
GROUP_KEY_SEP = "/"


def group_key(col_id, slug):
    """The collapse key for one group identity: ``"<col_id>/<slug>"``.

    The single construction site for the key that ``KanbanApp.collapsed_groups``,
    ``KanbanColumn.is_group_collapsed`` and ``settings["collapsed_groups"]`` all
    share. Build it here, never with a local f-string -- a second spelling is
    exactly how the runtime set and the persisted list drift apart.
    """
    return f"{col_id}{GROUP_KEY_SEP}{slug}"


def parse_group_key(key):
    """Inverse of :func:`group_key`: ``(col_id, slug)``, or ``None`` if unusable.

    Total over junk, for the same reason :func:`normalize_group_slug` is: this
    list is persisted JSON in a per-user file a user may hand-edit, and board
    versions before t1243_10 never wrote it at all. A non-``str`` entry, a
    missing separator, an empty column half or a whitespace-only slug half all
    degrade to "not a group identity" rather than raising inside a load path.

    The slug half goes through :func:`normalize_group_slug`, so a parsed key can
    only ever name an identity :func:`build_column_units` is able to produce --
    including the no-``.strip()`` rule, which keeps ``"perf_work "`` a DIFFERENT
    group from ``"perf_work"`` here exactly as it is on disk.
    """
    if not isinstance(key, str):
        return None
    col, sep, raw_slug = key.partition(GROUP_KEY_SEP)
    slug = normalize_group_slug(raw_slug)
    if not sep or not col or not slug:
        return None
    return col, slug


def remap_group_keys(keys, remap=None):
    """Re-point / drop collapse keys through ONE rule. Returns a sorted list.

    ``keys``  -- any iterable of ``"<col>/<slug>"``; unparseable entries are
                 dropped (see :func:`parse_group_key`).
    ``remap`` -- ``(col_id, slug) -> (col_id, slug) | None``. Returning ``None``
                 DROPS the group (dissolve). ``remap=None`` is the identity
                 rule, i.e. pure normalization -- which is what the load path
                 uses, so key hygiene has exactly one implementation shared with
                 every lifecycle remap.

    **The coalesce rule is a set union, in both of its named directions.**
    Collapse state is a PRESENCE set, so "the destination key wins if it already
    exists" and "otherwise the arriving key's state is adopted under the
    destination key" describe the same operation -- inserting the re-pointed key
    into a set:

    ======================  =====================  ========================
    arriving                destination            union of re-pointed keys
    ======================  =====================  ========================
    collapsed               collapsed              present (deduped)
    expanded                collapsed              present -- arriving added nothing
    collapsed               expanded               present -- adopted
    expanded                expanded               absent
    ======================  =====================  ========================

    The vacated key is dropped for free, because a re-point REWRITES it rather
    than adding beside it. That equivalence holds **only** because the key
    carries no value; a future value-carrying view key (a per-group sort mode, a
    colour) must revisit this rather than inherit the coincidence.

    Returns a SORTED list, not a set: it is the persisted form (JSON has no
    set), sorting keeps ``board_config.local.json`` byte-stable across saves, and
    the sort is what makes the de-duplication observable to a test.

    The four rule shapes the lifecycle owners need, all through this one
    function -- a COLUMN-half remap is :func:`column_remap` (``update_column``,
    ``delete_column``, ``merge_columns``); a SLUG-half rename is
    ``lambda c, s: (c, new) if (c, s) == (col, old) else (c, s)`` (t1243_12); a
    single group's MOVE between columns is
    ``lambda c, s: (dest, s) if (c, s) == (src, moved) else (c, s)`` (t1243_11);
    a DISSOLVE returns ``None`` for the target identity (t1243_12).
    """
    out = set()
    for key in keys:
        ident = parse_group_key(key)
        if ident is None:
            continue
        moved = ident if remap is None else remap(*ident)
        if moved is None:
            continue
        col, slug = moved
        slug = normalize_group_slug(slug)
        if not col or not slug:
            continue
        out.add(group_key(col, slug))
    return sorted(out)


def column_remap(mapping):
    """A :func:`remap_group_keys` rule re-pointing the COLUMN half via a map.

    ``{old_col: new_col}``; a column absent from the mapping is left alone. The
    one rule shape with more than one call site (column rename, column delete,
    column merge), so it is derived once here instead of three lambdas that
    could disagree. Slug-half and single-identity rules stay inline at their
    single call sites -- a helper per shape with one caller would be
    speculative.
    """
    def remap(col_id, slug):
        return mapping.get(col_id, col_id), slug
    return remap
