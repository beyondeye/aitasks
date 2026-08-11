"""Group collapse persistence, the lifecycle owners and unit-level filtering (t1243_10).

t1243_9 landed the filtering half — `_group_header_matches` already evaluates a
collapsed group from member `Task` DATA, is already child-aware, already counts a
visible header as column content, and is already in the focus-rescue tuple. What
this module owns is everything that was still missing:

* **persistence** — `settings["collapsed_groups"]` in the USER layer, and the
  guarantee that a runtime collapse never writes the git-tracked project file;
* **the six lifecycle owners** of the composite `"<col>/<slug>"` key, three of
  which exist today (`update_column`, `delete_column`, `merge_columns`) and
  three of which are seams t1243_11 / t1243_12 will call;
* **the coalesce rule** and the **prune-on-load** sweep;
* the **`· N match` badge**;
* and the filtering cases the t1243_9 suite does not reach.

**What this does NOT duplicate.** `test_board_group_focus.py::GroupFilteringTests`
already covers header visibility from member matches, a child-only match, focus
rescue off a hidden header, and a scoped pass — but every one of those runs
against an **expanded** group and uses **search only**. None collapses a group
first, and none touches a base filter (`locked`/`free`) or an add-on
(`git`/`type`). Those are the gaps below.

**Scoped variants are deliberately partial, not forgotten.** `cols` enters
`apply_filter` only through `_filter_units` / `_filter_group_headers` /
`_filter_placeholders` and the focus-rescue guard — all *downstream* of both the
`visible`-set composition and the shared child index. So `scoped x base-filter`,
`scoped x add-on` and `scoped x child-only` are orthogonal products with no
interaction term: they cannot fail unless the unscoped case or the scoping case
already fails. `ScopedGroupPassTests` covers the scoping itself; the products are
not padded in.

**By-Topic / By-Trail / In-Flight are out of scope by construction**, not by
oversight: they mount `TopicColumn` / trail widgets rather than `KanbanColumn`,
so no `GroupHeader` exists at all and any assertion would query an empty set and
pass forever.

House style: every class opens with a `test_fixture_facts` precondition case, and
every positive assertion is paired with a **discriminating negative control** —
a guard whose control also passes is testing nothing.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_group_filtering.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

PERF = "perf_work"
ALPHA = "alpha_grp"
BUSY = "busy_grp"
FREE = "free_grp"
RESCUE = "rescue_grp"
SOLO = "solo_grp"
ONLY_C0 = "only_c0"

#: Pilot topology. `GROUP_TOPOLOGY` in `test_board_group_focus.py` is reused for
#: NOTHING here: it is pinned by exact-count assertions ("▾ perf work (2)", DOM
#: unit lists, a positional index) and carries no metadata that makes
#: `locked`/`free`/`git`/`type` discriminate. Per `board_fixture`'s own
#: additive-names rule, this is a separate tree.
#:
#:   c0  the BADGE column. `perf_work` has THREE members of which exactly TWO
#:       match "zeta" — t9100 through its own filename, t9101 only through its
#:       CHILD, t9102 not at all. 2 differs from the member total (3), from 1 and
#:       from 0, which kills `len(members)`, a hardcoded 1, member-only counting
#:       and an off-by-one with one assertion. `boardgroup: perf_work` is part of
#:       every member's metadata (and so of its `search_haystack`), which is what
#:       makes "perf" the all-members-match control. Plus a SINGLE-member group
#:       (renders as a plain card, keeps its slug) and one ungrouped card that
#:       does not match "zeta", so under that search the column's only visible
#:       content is the header.
#:   c1  ONLY a group, 2 members, childless, carrying the ADD-ON discriminators:
#:       member one has `issue:` and `issue_type: feature`, member two neither.
#:       Both add-ons therefore land 1-of-2 — a partial match in a column with no
#:       other content, so badge and placeholder are exercised in one shape.
#:   c2  TWO childless groups, all-Implementing and all-Ready. Under `free` one
#:       header hides and the other stays, so the placeholder must stay hidden —
#:       a single-group column cannot express that. Childless is load-bearing:
#:       `_any_child_matches` re-admits a parent the base set excluded, so a busy
#:       group with a Ready child would silently stop discriminating.
#:   c3  ungrouped only, all Ready / chore / no issue — the negative-control
#:       column for every grouped claim and for both add-ons.
#:   c4  the deliberate OPPOSITE of c2: a group whose members are all busy but
#:       whose first member has a FREE child, after an ungrouped busy card. Under
#:       `free` every card in the column is excluded and the header survives ONLY
#:       through the child — base filter x child-aware x badge(1 of 2) in one case.
FILTER_TOPOLOGY = (
    bf.FixtureTask(task_id="9100", col="c0", idx=10, slug="zetaone",
                   extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9101", col="c0", idx=20, slug="perftwo",
                   extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9101_1", col="c0", idx=10, slug="zetachild"),
    bf.FixtureTask(task_id="9102", col="c0", idx=30, slug="perfthree",
                   extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9104", col="c0", idx=40, slug="lonely",
                   extra={"boardgroup": SOLO}),
    bf.FixtureTask(task_id="9103", col="c0", idx=50, slug="cplain"),

    bf.FixtureTask(task_id="9110", col="c1", idx=10, slug="alphaone",
                   extra={"boardgroup": ALPHA, "issue_type": "feature",
                          "issue": "https://example.invalid/issues/1"}),
    bf.FixtureTask(task_id="9111", col="c1", idx=20, slug="alphatwo",
                   extra={"boardgroup": ALPHA}),

    bf.FixtureTask(task_id="9120", col="c2", idx=10, slug="busyone",
                   status="Implementing", extra={"boardgroup": BUSY}),
    bf.FixtureTask(task_id="9121", col="c2", idx=20, slug="busytwo",
                   status="Implementing", extra={"boardgroup": BUSY}),
    bf.FixtureTask(task_id="9122", col="c2", idx=30, slug="freeone",
                   extra={"boardgroup": FREE}),
    bf.FixtureTask(task_id="9123", col="c2", idx=40, slug="freetwo",
                   extra={"boardgroup": FREE}),

    bf.FixtureTask(task_id="9130", col="c3", idx=10, slug="plainone"),
    bf.FixtureTask(task_id="9131", col="c3", idx=20, slug="plaintwo"),

    bf.FixtureTask(task_id="9140", col="c4", idx=10, slug="cfourplain",
                   status="Implementing"),
    bf.FixtureTask(task_id="9141", col="c4", idx=20, slug="rescueone",
                   status="Implementing", extra={"boardgroup": RESCUE}),
    bf.FixtureTask(task_id="9141_1", col="c4", idx=10, slug="rescuechild"),
    bf.FixtureTask(task_id="9142", col="c4", idx=30, slug="rescuetwo",
                   status="Implementing", extra={"boardgroup": RESCUE}),
)

#: The `t` add-on's input. Every other fixture task is `issue_type: chore`
#: (`bf._META_BASE`), so this selects exactly one task board-wide.
FILTER_SETTINGS = {"filter_issue_types": ["feature"]}

#: Manager-level topology. The same slug sits in FOUR columns on purpose: c0 and
#: c1 are the coalesce pair, c2 is the untouched control proving a re-point is
#: keyed on the COLUMN half and not on the slug, and `unordered` pre-holds a
#: `perf_work` group so `delete_column`'s re-point lands on an EXISTING identity
#: — a real collision rather than a rename. c0 also holds a SECOND group, so an
#: owner that re-points only the first key it finds fails. c3's single-member
#: group is the prune boundary.
LIFECYCLE_TOPOLOGY = (
    bf.FixtureTask(task_id="9200", col="c0", idx=10, slug="a", extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9201", col="c0", idx=20, slug="b", extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9202", col="c0", idx=30, slug="c", extra={"boardgroup": ONLY_C0}),
    bf.FixtureTask(task_id="9203", col="c0", idx=40, slug="d", extra={"boardgroup": ONLY_C0}),
    bf.FixtureTask(task_id="9210", col="c1", idx=10, slug="e", extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9211", col="c1", idx=20, slug="f", extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9220", col="c2", idx=10, slug="g", extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9221", col="c2", idx=20, slug="h", extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9230", col="c3", idx=10, slug="i", extra={"boardgroup": SOLO}),
    bf.FixtureTask(task_id="9240", col="unordered", idx=10, slug="j", extra={"boardgroup": PERF}),
    bf.FixtureTask(task_id="9241", col="unordered", idx=20, slug="k", extra={"boardgroup": PERF}),
)

P_9100 = "t9100_zetaone.md"
P_9101 = "t9101_perftwo.md"
C_9101_1 = "t9101_1_zetachild.md"
P_9102 = "t9102_perfthree.md"
P_9103 = "t9103_cplain.md"
P_9104 = "t9104_lonely.md"
P_9110 = "t9110_alphaone.md"
P_9111 = "t9111_alphatwo.md"
P_9140 = "t9140_cfourplain.md"
P_9141 = "t9141_rescueone.md"

NO_MATCH = "zzz_no_such_task_zzz"


# --- shared bases ------------------------------------------------------------


class _FilterBase(bf.FixtureBoardTestBase, bf.PristineTreeMixin):
    """Pilot scaffold. `PristineTreeMixin` restores board config too (t1243_10),
    which is what stops a persisted collapse leaking into the next test."""

    FIXTURE_TASKS = FILTER_TOPOLOGY
    FIXTURE_SETTINGS = FILTER_SETTINGS

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.KanbanColumn = cls.ab.KanbanColumn
        cls.TaskCard = cls.ab.TaskCard
        cls.GroupHeader = cls.ab.GroupHeader
        cls.EmptyColumnPlaceholder = cls.ab.EmptyColumnPlaceholder
        cls._snapshot_pristine()

    def _run(self, coro):
        return asyncio.run(coro)

    async def _settle(self, pilot, times=4):
        for _ in range(times):
            await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    # --- oracles ---------------------------------------------------------

    def _header(self, app, col_id, slug):
        return next((h for h in app.query(self.GroupHeader)
                     if h.column_id == col_id and h.slug == slug), None)

    def _placeholder(self, app, col_id):
        return next((p for p in app.query(self.EmptyColumnPlaceholder)
                     if p.column_id == col_id), None)

    def _card(self, app, filename):
        return next((c for c in app.query(self.TaskCard)
                     if not c.is_child and c.task_data.filename == filename), None)

    def _child_card(self, app, filename):
        return next((c for c in app.query(self.TaskCard)
                     if c.is_child and c.task_data.filename == filename), None)

    def _mounted_cards(self, app, col_id):
        return sorted(c.task_data.filename for c in app.query(self.TaskCard)
                      if c.column_id == col_id)

    def _label(self, app, col_id, slug):
        """The header's RENDERED text — never `match_count`.

        `Static.render()` returns a `Content` whose `.plain` strips markup, so a
        badge wrapped in `[dim]…[/dim]` asserts identically to a bare one.
        """
        return self._header(app, col_id, slug).render().plain

    def _focus_id(self, app):
        f = app.screen.focused
        if isinstance(f, self.GroupHeader):
            return ("group", f.column_id, f.slug)
        if isinstance(f, self.TaskCard):
            return ("card", f.task_data.filename)
        if isinstance(f, self.EmptyColumnPlaceholder):
            return ("placeholder", f.column_id)
        return ("other", type(f).__name__)

    async def _collapse(self, app, pilot, *keys):
        """Collapse `(col, slug)` pairs through the MODEL, then recompose.

        Deliberately not `pilot.press("x")` here: these classes are about the
        filter pass, and driving the key would also drag in focus movement. The
        real keystroke path is exercised by `CollapsePersistenceTests` and
        `ScopedGroupPassTests`.
        """
        for col_id, slug in keys:
            app.manager.toggle_group_collapsed(col_id, slug)
        app.refresh_board()
        await self._settle(pilot)


class _LifecycleBase(bf.FixtureBoardTestBase, bf.PristineTreeMixin):
    """Manager scaffold — no app. Two of the three landed owners
    (`update_column`'s rename branch, `merge_columns`) have no UI path that can
    reach them today, so a manager-level call IS the production entry point."""

    FIXTURE_TASKS = LIFECYCLE_TOPOLOGY

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._snapshot_pristine()

    @property
    def _local_path(self) -> Path:
        return self.tasks_dir / "metadata" / "board_config.local.json"

    def _seed(self, keys):
        """Seed `collapsed_groups` on disk and return a manager that loaded it.

        Per-test seeding rather than a `FIXTURE_SETTINGS` subclass per case: the
        tree is built once per class, and one class per seed would multiply the
        (slow) fixture builds without adding coverage.
        """
        payload = json.loads(self._local_path.read_text(encoding="utf-8"))
        payload.setdefault("settings", {})["collapsed_groups"] = list(keys)
        self._local_path.write_text(json.dumps(payload, indent=2) + "\n",
                                    encoding="utf-8")
        return self.ab.TaskManager()

    def _fresh(self):
        """A second manager reading the same tree — the disk round-trip."""
        return self.ab.TaskManager()

    def _persisted(self):
        settings = json.loads(self._local_path.read_text(encoding="utf-8"))["settings"]
        return settings.get("collapsed_groups")


# --- 1. collapsed + search ---------------------------------------------------


class CollapsedSearchMatrixTests(_FilterBase, unittest.TestCase):
    """The collapsed half of the filtering matrix — no mounted member widgets."""

    def test_fixture_facts(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                m = app.manager
                seen["parent_has_zeta"] = "zeta" in m.task_datas[P_9101].search_haystack
                seen["child_has_zeta"] = "zeta" in m.child_task_datas[C_9101_1].search_haystack
                seen["own_has_zeta"] = "zeta" in m.task_datas[P_9100].search_haystack
                seen["third_has_zeta"] = "zeta" in m.task_datas[P_9102].search_haystack
                seen["all_have_perf"] = all(
                    "perf" in m.task_datas[f].search_haystack
                    for f in (P_9100, P_9101, P_9102))
                seen["members"] = len(self._header(app, "c0", PERF).members)
                seen["collapsed"] = set(app.collapsed_groups)

        self._run(go())
        self.assertFalse(seen["parent_has_zeta"],
                         "t9101's OWN corpus must not contain 'zeta' — that is "
                         "what makes the child-only cases discriminate")
        self.assertTrue(seen["child_has_zeta"])
        self.assertTrue(seen["own_has_zeta"], "t9100 must match 'zeta' directly")
        self.assertFalse(seen["third_has_zeta"], "t9102 must not match at all")
        self.assertTrue(seen["all_have_perf"],
                        "'perf' must match every member (via `boardgroup` in the "
                        "haystack) — it is the all-match control for the badge")
        self.assertEqual(seen["members"], 3)
        self.assertEqual(seen["collapsed"], set(), "tree must start uncollapsed")

    def test_collapsed_group_is_kept_by_a_member_that_matches(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c0", PERF))
                seen["mounted"] = self._mounted_cards(app, "c0")
                app.search_filter = "zeta"
                app.apply_filter()
                await self._settle(pilot)
                seen["header"] = self._header(app, "c0", PERF).styles.display
                seen["placeholder"] = self._placeholder(app, "c0").styles.display

                app.search_filter = NO_MATCH
                app.apply_filter()
                await self._settle(pilot)
                seen["nomatch_header"] = self._header(app, "c0", PERF).styles.display

        self._run(go())
        for member in (P_9100, P_9101, P_9102):
            self.assertNotIn(member, seen["mounted"],
                             "a collapsed group must mount NO member cards — "
                             "otherwise the data path is not what was tested")
        self.assertNotEqual(seen["header"], "none",
                            "the header must be kept by member DATA alone")
        self.assertEqual(seen["placeholder"], "none",
                         "a visible header counts as column content")
        self.assertEqual(seen["nomatch_header"], "none",
                         "control: with nothing matching, the header hides")

    def test_collapsed_group_is_kept_by_a_members_child_alone(self):
        """The case only a collapsed group can prove.

        `test_board_group_focus.py:783` covers a child-only match on an EXPANDED
        group, where a mounted `↳` row could be carrying the decision. Here no
        member card and no child card is mounted at all, so the header can only
        have survived by reading the members' children as DATA.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            app.expanded_tasks.add(P_9101)     # would mount the child if expanded
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c0", PERF))
                app.search_filter = "zetachild"
                app.apply_filter()
                await self._settle(pilot)
                seen["header"] = self._header(app, "c0", PERF).styles.display
                seen["child_mounted"] = self._child_card(app, C_9101_1) is not None
                seen["parent_mounted"] = self._card(app, P_9101) is not None

                app.search_filter = NO_MATCH
                app.apply_filter()
                await self._settle(pilot)
                seen["control"] = self._header(app, "c0", PERF).styles.display

        self._run(go())
        self.assertFalse(seen["child_mounted"],
                         "no child card may be mounted — otherwise the decision "
                         "could have come from a widget, not from data")
        self.assertFalse(seen["parent_mounted"])
        self.assertNotEqual(seen["header"], "none",
                            "the header must survive on its member's CHILD text")
        self.assertEqual(seen["control"], "none",
                         "control: an unmatchable search hides the same header")

    def test_a_column_of_only_collapsed_groups_keeps_its_placeholder_hidden(self):
        """The loop-ordering case, under an active filter.

        `test_collapsed_group_column_keeps_its_placeholder_hidden` (t1243_9) runs
        with NO filter active. The header loop must run before the placeholder
        loop, and that only bites once a pass can actually hide things.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c1", ALPHA))
                app.search_filter = "alphaone"
                app.apply_filter()
                await self._settle(pilot)
                seen["header"] = self._header(app, "c1", ALPHA).styles.display
                seen["placeholder"] = self._placeholder(app, "c1").styles.display
                seen["cards"] = self._mounted_cards(app, "c1")

                app.search_filter = NO_MATCH
                app.apply_filter()
                await self._settle(pilot)
                seen["ctl_header"] = self._header(app, "c1", ALPHA).styles.display
                seen["ctl_placeholder"] = self._placeholder(app, "c1").styles.display

        self._run(go())
        self.assertEqual(seen["cards"], [], "c1 holds only the collapsed group")
        self.assertNotEqual(seen["header"], "none")
        self.assertEqual(seen["placeholder"], "none",
                         "the placeholder must stay hidden behind a visible header")
        self.assertEqual(seen["ctl_header"], "none")
        self.assertNotEqual(seen["ctl_placeholder"], "none",
                            "control: only with the header hidden does the "
                            "placeholder appear")

    def test_focus_is_rescued_off_a_hidden_collapsed_header(self):
        """Rescue when the column has no cards to fall back to.

        The t1243_9 rescue case uses an expanded group, so `_column_focus_target`
        still had member cards to choose from. Here the only focusable widgets in
        the column are the header and the placeholder.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c1", ALPHA))
                self._header(app, "c1", ALPHA).focus()
                await self._settle(pilot)
                seen["before"] = self._focus_id(app)

                app.search_filter = "alphaone"      # still matches -> stays put
                app.apply_filter()
                await self._settle(pilot)
                seen["still_matching"] = self._focus_id(app)

                app.search_filter = NO_MATCH
                app.apply_filter()
                await self._settle(pilot)
                seen["after"] = self._focus_id(app)

        self._run(go())
        self.assertEqual(seen["before"], ("group", "c1", ALPHA))
        self.assertEqual(seen["still_matching"], ("group", "c1", ALPHA),
                         "control: a pass that hides nothing must not move focus")
        self.assertEqual(seen["after"], ("placeholder", "c1"),
                         "focus must not rest on a header the pass just hid")


# --- 2. base filters and add-ons ---------------------------------------------


class BaseFilterAndAddOnGroupTests(_FilterBase, unittest.TestCase):
    """Nothing in the t1243_9 suite touches `base_filter` or the add-ons."""

    def test_fixture_facts(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["free"] = app._free_visible_set()
                seen["git"] = app._git_visible_set()
                seen["type"] = app._type_visible_set()
                seen["types_setting"] = app.manager.settings.get("filter_issue_types")

        self._run(go())
        free = seen["free"]
        self.assertNotIn("t9120_busyone.md", free)
        self.assertNotIn("t9121_busytwo.md", free)
        self.assertIn("t9122_freeone.md", free)
        self.assertIn("t9123_freetwo.md", free)
        self.assertNotIn(P_9141, free, "c4's group members must all be busy")
        self.assertIn("t9141_1_rescuechild.md", free,
                      "…while its child is free — that is the rescue path")
        self.assertEqual(seen["git"], {P_9110},
                         "exactly one task carries `issue:`")
        self.assertEqual(seen["type"], {P_9110},
                         "exactly one task is issue_type: feature")
        self.assertEqual(seen["types_setting"], ["feature"])

    def test_free_and_locked_invert_two_collapsed_groups_in_one_column(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c2", BUSY), ("c2", FREE))
                for mode in ("free", "locked"):
                    app.base_filter = mode
                    app.apply_filter()
                    await self._settle(pilot)
                    seen[mode] = (
                        self._header(app, "c2", BUSY).styles.display,
                        self._header(app, "c2", FREE).styles.display,
                        self._placeholder(app, "c2").styles.display,
                    )

        self._run(go())
        busy_free, free_free, ph_free = seen["free"]
        busy_locked, free_locked, ph_locked = seen["locked"]
        self.assertEqual(busy_free, "none", "an all-busy group hides under `free`")
        self.assertNotEqual(free_free, "none")
        self.assertEqual(ph_free, "none",
                         "the surviving header keeps the placeholder hidden")
        self.assertNotEqual(busy_locked, "none",
                            "control: `locked` inverts it exactly…")
        self.assertEqual(free_locked, "none", "…and hides the other")
        self.assertEqual(ph_locked, "none")

    def test_free_rescues_an_all_busy_collapsed_group_through_a_free_child(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c4", RESCUE))
                app.base_filter = "free"
                app.apply_filter()
                await self._settle(pilot)
                seen["header"] = self._header(app, "c4", RESCUE).styles.display
                seen["plain_card"] = self._card(app, P_9140).styles.display
                seen["placeholder"] = self._placeholder(app, "c4").styles.display

                # Compose a search on top: the rescue must be an INTERSECTION,
                # not "free never hides a header".
                app.search_filter = NO_MATCH
                app.apply_filter()
                await self._settle(pilot)
                seen["composed"] = self._header(app, "c4", RESCUE).styles.display

        self._run(go())
        self.assertNotEqual(seen["header"], "none",
                            "every member is busy — only the free CHILD can "
                            "keep this header visible")
        self.assertEqual(seen["plain_card"], "none",
                         "the ungrouped busy card is still hidden")
        self.assertEqual(seen["placeholder"], "none")
        self.assertEqual(seen["composed"], "none",
                         "control: composing an unmatchable search hides it, so "
                         "the rescue rests on the composed predicate")

    def test_add_ons_keep_a_partially_matching_collapsed_group(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c1", ALPHA),
                                     ("c2", BUSY), ("c2", FREE))
                for attr in ("git_filter_active", "type_filter_active"):
                    setattr(app, attr, True)
                    app.apply_filter()
                    await self._settle(pilot)
                    seen[attr] = (
                        self._header(app, "c1", ALPHA).styles.display,
                        self._header(app, "c2", BUSY).styles.display,
                        self._placeholder(app, "c1").styles.display,
                        self._placeholder(app, "c2").styles.display,
                    )
                    setattr(app, attr, False)

                # Control for the type add-on specifically: an empty selection
                # yields an empty visible set, so even c1 must hide.
                app.manager.settings["filter_issue_types"] = []
                app.type_filter_active = True
                app.apply_filter()
                await self._settle(pilot)
                seen["empty_selection"] = self._header(app, "c1", ALPHA).styles.display

        self._run(go())
        for attr in ("git_filter_active", "type_filter_active"):
            c1_header, c2_header, c1_ph, c2_ph = seen[attr]
            self.assertNotEqual(c1_header, "none",
                                f"{attr}: one of the two members qualifies")
            self.assertEqual(c2_header, "none",
                             f"{attr}: control — c2 has no qualifying member")
            self.assertEqual(c1_ph, "none")
            self.assertNotEqual(c2_ph, "none",
                                f"{attr}: …so c2 falls back to its placeholder")
        self.assertEqual(seen["empty_selection"], "none",
                         "control: an empty type selection excludes everything")

    def test_an_add_on_intersects_with_search_rather_than_replacing_it(self):
        """Fails if `visible` is recomputed per unit instead of composed once."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c1", ALPHA))

                app.git_filter_active = True          # -> {t9110}
                app.search_filter = "alphatwo"        # -> {t9111}
                app.apply_filter()
                await self._settle(pilot)
                seen["intersection"] = self._header(app, "c1", ALPHA).styles.display

                app.git_filter_active = False         # search alone
                app.apply_filter()
                await self._settle(pilot)
                seen["search_only"] = self._header(app, "c1", ALPHA).styles.display

                app.git_filter_active = True          # add-on alone
                app.search_filter = ""
                app.apply_filter()
                await self._settle(pilot)
                seen["addon_only"] = self._header(app, "c1", ALPHA).styles.display

        self._run(go())
        self.assertEqual(seen["intersection"], "none",
                         "no member is BOTH issue-bearing and named 'alphatwo'")
        self.assertNotEqual(seen["search_only"], "none",
                            "control: the search alone keeps it")
        self.assertNotEqual(seen["addon_only"], "none",
                            "control: the add-on alone keeps it")


# --- 3. the scoped pass ------------------------------------------------------


class ScopedGroupPassTests(_FilterBase, unittest.TestCase):

    def test_fixture_facts(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c0", PERF), ("c1", ALPHA))
                seen["headers"] = sorted(
                    (h.column_id, h.slug) for h in app.query(self.GroupHeader))
                seen["collapsed"] = set(app.collapsed_groups)

        self._run(go())
        self.assertIn(("c0", PERF), seen["headers"])
        self.assertIn(("c1", ALPHA), seen["headers"])
        self.assertEqual(seen["collapsed"], {f"c0/{PERF}", f"c1/{ALPHA}"})

    def test_a_scoped_pass_flips_only_the_named_columns_header(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c0", PERF), ("c1", ALPHA))
                app.search_filter = NO_MATCH
                app.apply_filter({"c0"})
                await self._settle(pilot)
                seen["scoped"] = self._header(app, "c0", PERF).styles.display
                seen["scoped_ph"] = self._placeholder(app, "c0").styles.display
                seen["untouched"] = self._header(app, "c1", ALPHA).styles.display
                seen["untouched_ph"] = self._placeholder(app, "c1").styles.display

        self._run(go())
        self.assertEqual(seen["scoped"], "none")
        self.assertNotEqual(seen["scoped_ph"], "none")
        self.assertNotEqual(seen["untouched"], "none",
                            "an unscoped query(GroupHeader) would hide this too")
        self.assertEqual(seen["untouched_ph"], "none",
                         "and its placeholder must not be flipped either")

    def test_pressing_x_reaches_the_column_through_the_real_scoped_pass(self):
        """The production path: `refresh_column` -> `call_after_refresh(apply_filter, {col})`.

        This is the only place in the feature where a scoped pass is issued by
        production code rather than by a test, so it is driven by the keystroke.
        """
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                app.search_filter = "zeta"
                app.apply_filter()
                await self._settle(pilot)
                seen["c1_before"] = self._label(app, "c1", ALPHA)

                self._header(app, "c0", PERF).focus()
                await self._settle(pilot)
                await pilot.press("x")
                await self._settle(pilot)

                seen["c0_label"] = self._label(app, "c0", PERF)
                seen["c0_cards"] = self._mounted_cards(app, "c0")
                seen["c1_after"] = self._label(app, "c1", ALPHA)
                seen["focus"] = self._focus_id(app)

        self._run(go())
        for member in (P_9100, P_9101, P_9102):
            self.assertNotIn(member, seen["c0_cards"],
                             "collapsing under a live filter unmounts every "
                             "member of THAT group")
        self.assertIn(P_9103, seen["c0_cards"],
                      "control: the column's ungrouped card is still mounted, "
                      "so the assertion above is about the group, not the column")
        self.assertEqual(seen["c0_label"], "▸ perf work (3) · 2 match",
                         "the deferred scoped pass must have set the badge")
        self.assertEqual(seen["c1_after"], seen["c1_before"],
                         "an untouched column's header must be byte-identical — "
                         "the pass was scoped, not board-wide")
        self.assertEqual(seen["focus"], ("group", "c0", PERF),
                         "focus lands back on the header, never on an unmounted "
                         "member")


# --- 4. the badge ------------------------------------------------------------


class GroupHeaderLabelTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """The label formatter, app-free. `GroupHeader` needs no running app."""

    FIXTURE_TASKS = FILTER_TOPOLOGY

    class _Member:
        # Stands in for a `Task`. `metadata` is required, not optional:
        # `_label()` reads it for the t1468_3 follow-up roll-up, and production
        # deliberately has no `getattr` fallback (that would mask a real Task
        # arriving without metadata). Pass `extra` to make a member a follow-up.
        def __init__(self, **extra):
            self.metadata = dict(extra)

    def _header(self, *, collapsed=True, members=3, count=None):
        h = self.ab.GroupHeader("c0", PERF, [self._Member() for _ in range(members)],
                                collapsed)
        if count is not None:
            h.set_match_count(count)
        return h

    def test_fixture_facts(self):
        """The pre-badge baseline every case below perturbs."""
        self.assertEqual(self._header().render().plain, "▸ perf work (3)")
        self.assertEqual(self._header(collapsed=False).render().plain,
                         "▾ perf work (3)")

    def test_badge_is_appended_after_the_member_count(self):
        self.assertEqual(self._header(count=2).render().plain,
                         "▸ perf work (3) · 2 match")

    def test_no_badge_when_the_count_is_cleared(self):
        h = self._header(count=2)
        self.assertIn("· 2 match", h.render().plain)     # control: it was there
        h.set_match_count(None)
        self.assertEqual(h.render().plain, "▸ perf work (3)")

    def test_set_collapsed_repaint_preserves_the_badge(self):
        """The trap: `set_collapsed` repaints via `_label()`.

        A badge appended by whoever sets it — rather than built inside
        `_label()` — is silently erased by an unrelated glyph flip.
        """
        h = self._header(collapsed=False, count=2)
        h.set_collapsed(True)
        self.assertEqual(h.render().plain, "▸ perf work (3) · 2 match")

        control = self._header(collapsed=False)
        control.set_collapsed(True)
        self.assertEqual(control.render().plain, "▸ perf work (3)",
                         "control: with no count, the flip adds no badge")

    def test_a_count_of_one_reads_correctly(self):
        self.assertEqual(self._header(count=1).render().plain,
                         "▸ perf work (3) · 1 match")


class MatchBadgeWiringTests(_FilterBase, unittest.TestCase):
    """The badge as `apply_filter` actually sets it — render-level only."""

    def test_fixture_facts(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c0", PERF))
                seen["label"] = self._label(app, "c0", PERF)

        self._run(go())
        self.assertEqual(seen["label"], "▸ perf work (3)",
                         "with no filter active a collapsed header carries no badge")

    def test_partial_match_renders_a_count_that_is_neither_the_total_nor_one(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c0", PERF))
                for name, term in (("two", "zeta"), ("all", "perf"),
                                   ("one", "zetaone")):
                    app.search_filter = term
                    app.apply_filter()
                    await self._settle(pilot)
                    seen[name] = self._label(app, "c0", PERF)

        self._run(go())
        self.assertEqual(seen["two"], "▸ perf work (3) · 2 match",
                         "2 of 3 — child-aware, and different from the total")
        self.assertEqual(seen["all"], "▸ perf work (3)",
                         "control: when every member matches the badge is noise")
        self.assertEqual(seen["one"], "▸ perf work (3) · 1 match",
                         "control: a third distinct count off the same group")

    def test_the_count_is_child_aware(self):
        """`zeta` matches t9100 itself and t9101 only via its child -> 2, not 1."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c0", PERF))
                app.search_filter = "zeta"
                app.apply_filter()
                await self._settle(pilot)
                seen["child_aware"] = self._label(app, "c0", PERF)

                app.search_filter = "zetachild"
                app.apply_filter()
                await self._settle(pilot)
                seen["child_only"] = self._label(app, "c0", PERF)

        self._run(go())
        self.assertEqual(seen["child_aware"], "▸ perf work (3) · 2 match",
                         "a member-only count would read 1 here")
        self.assertEqual(seen["child_only"], "▸ perf work (3) · 1 match",
                         "control: only the child-carrying member matches")

    def test_an_expanded_group_never_shows_a_badge(self):
        """Its non-matching members are hidden individually and countable."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                app.search_filter = "zeta"
                app.apply_filter()
                await self._settle(pilot)
                seen["expanded"] = self._label(app, "c0", PERF)
                seen["hidden_member"] = self._card(app, P_9102).styles.display
                seen["shown_member"] = self._card(app, P_9100).styles.display

                await self._collapse(app, pilot, ("c0", PERF))
                app.apply_filter()
                await self._settle(pilot)
                seen["collapsed"] = self._label(app, "c0", PERF)

        self._run(go())
        self.assertEqual(seen["expanded"], "▾ perf work (3)")
        self.assertEqual(seen["hidden_member"], "none",
                         "the non-matching member is hidden individually…")
        self.assertNotEqual(seen["shown_member"], "none", "…and the matching one is not")
        self.assertEqual(seen["collapsed"], "▸ perf work (3) · 2 match",
                         "control: collapsing the SAME state produces the badge")

    def test_clearing_the_filter_removes_the_badge(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c0", PERF))
                app.search_filter = "zeta"
                app.apply_filter()
                await self._settle(pilot)
                seen["with"] = self._label(app, "c0", PERF)
                app.search_filter = ""
                app.apply_filter()
                await self._settle(pilot)
                seen["without"] = self._label(app, "c0", PERF)

        self._run(go())
        self.assertIn("· 2 match", seen["with"])
        self.assertEqual(seen["without"], "▸ perf work (3)")

    def test_a_base_filter_alone_can_produce_a_badge(self):
        """`narrowing` must consider the visible SET, not only the search text."""
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                await self._collapse(app, pilot, ("c4", RESCUE))
                app.base_filter = "free"
                app.apply_filter()
                await self._settle(pilot)
                seen["free"] = self._label(app, "c4", RESCUE)

                app.base_filter = "all"
                app.apply_filter()
                await self._settle(pilot)
                seen["all"] = self._label(app, "c4", RESCUE)

        self._run(go())
        self.assertEqual(seen["free"], "▸ rescue grp (2) · 1 match",
                         "only the child-bearing member survives `free`")
        self.assertEqual(seen["all"], "▸ rescue grp (2)",
                         "control: with no filter narrowing, no badge")


# --- 5. persistence ----------------------------------------------------------


class CollapsePersistenceTests(_FilterBase, unittest.TestCase):

    def _local(self):
        path = self.tasks_dir / "metadata" / "board_config.local.json"
        return json.loads(path.read_text(encoding="utf-8"))["settings"]

    def _project_text(self):
        return (self.tasks_dir / "metadata" / "board_config.json").read_text(
            encoding="utf-8")

    def test_fixture_facts(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["type"] = type(app.collapsed_groups)
                seen["alias"] = app.collapsed_groups is app.manager.collapsed_groups
                seen["empty"] = set(app.collapsed_groups)

        self._run(go())
        self.assertEqual(seen["empty"], set())
        self.assertIs(seen["type"], set,
                      "must stay a mutable set — KanbanColumn holds it by reference")
        self.assertTrue(seen["alias"],
                        "the app must ALIAS the manager's set, not copy it: a "
                        "lifecycle remap has to be visible to every column")
        self.assertNotIn("collapsed_groups", self._local(),
                         "the tree starts with no persisted collapse")

    def test_x_persists_into_the_user_layer_only(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                self._header(app, "c0", PERF).focus()
                await self._settle(pilot)
                await pilot.press("x")
                await self._settle(pilot)

        self._run(go())
        self.assertEqual(self._local().get("collapsed_groups"), [f"c0/{PERF}"])
        self.assertNotIn("collapsed_groups", self._project_text(),
                         "an unlisted key falls to the PROJECT layer via "
                         "split_config — collapse state must be nested under "
                         "`settings`, or it lands in the git-tracked file")

    def test_expanding_again_removes_the_key_entirely(self):
        """Absence, not `[]` — that is what makes a round-trip byte-identical."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                self._header(app, "c0", PERF).focus()
                await self._settle(pilot)
                await pilot.press("x")
                await self._settle(pilot)
                self.assertEqual(self._local().get("collapsed_groups"),
                                 [f"c0/{PERF}"])          # control: it was set
                self._header(app, "c0", PERF).focus()
                await self._settle(pilot)
                await pilot.press("x")
                await self._settle(pilot)

        self._run(go())
        self.assertNotIn("collapsed_groups", self._local())

    def test_a_restart_reproduces_the_collapse(self):
        seen = {}

        async def collapse_it():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                self._header(app, "c0", PERF).focus()
                await self._settle(pilot)
                await pilot.press("x")
                await self._settle(pilot)

        async def restart():
            app = self.KanbanApp()                 # the RESTART
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["mounted"] = self._mounted_cards(app, "c0")
                seen["label"] = self._label(app, "c0", PERF)
                seen["control"] = self._label(app, "c1", ALPHA)

        self._run(collapse_it())
        self._run(restart())
        for member in (P_9100, P_9101, P_9102):
            self.assertNotIn(member, seen["mounted"])
        self.assertIn(P_9103, seen["mounted"],
                      "the ungrouped card in the same column still renders")
        self.assertTrue(seen["label"].startswith("▸"),
                        "the collapsed group came back collapsed")
        self.assertTrue(seen["control"].startswith("▾"),
                        "control: a group that was never collapsed comes back "
                        "EXPANDED — otherwise 'everything renders collapsed' "
                        "would pass this test")

    def test_hydration_happens_before_the_first_compose(self):
        """Catches hydration placed after `refresh_board`, which would leave the
        first frame expanded forever."""
        path = self.tasks_dir / "metadata" / "board_config.local.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["settings"]["collapsed_groups"] = [f"c1/{ALPHA}"]
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["c1"] = self._mounted_cards(app, "c1")
                seen["c0"] = self._mounted_cards(app, "c0")

        self._run(go())
        self.assertEqual(seen["c1"], [],
                         "the seeded group must be collapsed on the FIRST frame")
        for member in (P_9100, P_9101, P_9102):
            self.assertIn(member, seen["c0"],
                          "control: a group absent from the setting mounts its "
                          "members")

    def test_unusable_persisted_keys_do_not_crash_the_board(self):
        path = self.tasks_dir / "metadata" / "board_config.local.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["settings"]["collapsed_groups"] = [
            "c9/ghost", "noslash", "c0/", "/perf_work", 7, None, f"c0/{PERF}"]
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                seen["keys"] = set(app.collapsed_groups)
                seen["c0"] = self._mounted_cards(app, "c0")

        self._run(go())
        self.assertEqual(seen["keys"], {f"c0/{PERF}"},
                         "junk is dropped and the one real key survives; "
                         "`c9/ghost` is pruned as memberless")
        self.assertEqual(seen["c0"], [P_9103, P_9104],
                         "the board still renders, with the real group collapsed")


class ProjectLayerIsNeverWrittenTests(_FilterBase, unittest.TestCase):
    """Byte-identity alone is VACUOUS here.

    `save_project_config` re-renders identical JSON through an atomic
    `os.replace`, so a stray `save_metadata()` during a collapse reproduces
    byte-identical content and would pass a naive diff. Three independent oracles
    are used instead — a call-through spy, an unlisted canary key that any
    `save_metadata()` destroys (it round-trips only `columns`/`column_order`/
    `settings`), and inode/mtime identity — plus a POSITIVE CONTROL issuing a
    real project write, without which all three could be dead and this test would
    pass green forever.
    """

    CANARY = "canary_unlisted_project_key"

    def _arm(self):
        path = self.tasks_dir / "metadata" / "board_config.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw[self.CANARY] = {"proof": "no project write"}
        path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        st = path.stat()
        return path, (st.st_ino, st.st_mtime_ns)

    def _probe(self, path, ident):
        st = path.stat()
        return {
            "canary": self.CANARY in json.loads(path.read_text(encoding="utf-8")),
            "fs": (st.st_ino, st.st_mtime_ns) == ident,
        }

    def _spy_project_writes(self):
        calls: list[str] = []
        original = self.ab.save_project_config

        def spy(p, d):                      # call THROUGH, never stub — a stub
            calls.append(str(p))            # would disable the positive control
            return original(p, d)

        patcher = mock.patch.object(self.ab, "save_project_config", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def test_fixture_facts(self):
        """The three oracles are live — proven by a REAL project write.

        Without this, `test_collapse_issues_no_project_layer_write` could pass
        with all three oracles dead, forever.
        """
        path, ident = self._arm()
        calls = self._spy_project_writes()
        before = self._probe(path, ident)
        self.assertTrue(before["canary"] and before["fs"], "armed")

        self.ab.TaskManager().save_metadata()

        after = self._probe(path, ident)
        self.assertEqual(len(calls), 1, f"the write was issued: {calls}")
        self.assertFalse(after["canary"],
                         "a real project write drops an unlisted key — "
                         "`save_metadata` round-trips only columns/order/settings")
        self.assertFalse(after["fs"], "…and atomic replace changes the inode")

    def test_collapse_issues_no_project_layer_write(self):
        path, ident = self._arm()
        calls = self._spy_project_writes()
        local = self.tasks_dir / "metadata" / "board_config.local.json"
        before_local = local.read_bytes()

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(200, 60)) as pilot:
                await self._settle(pilot)
                self._header(app, "c0", PERF).focus()
                await self._settle(pilot)
                await pilot.press("x")
                await self._settle(pilot)

        self._run(go())
        after = self._probe(path, ident)
        self.assertEqual(calls, [], "no project-layer write may be issued")
        self.assertTrue(after["canary"], "the project file was not rewritten…")
        self.assertTrue(after["fs"], "…and its inode/mtime are unchanged")
        self.assertNotEqual(local.read_bytes(), before_local,
                            "…while the USER layer DID change — so the zero-write "
                            "claim is not merely 'nothing happened at all'")


# --- 6. the lifecycle owners -------------------------------------------------


class CollapseKeyLifecycleTests(_LifecycleBase, unittest.TestCase):
    """`update_column` / `delete_column` / `merge_columns` re-point the key.

    All three are driven by direct manager calls. That is the production entry
    point, not a shortcut: `update_column`'s rename branch is dormant by decision
    (t1377_5 — both the dialog and the headless writer pass the id unchanged),
    and `merge_columns` is headless-first. Group rename / move / dissolve are
    NOT driven here — they are t1243_11 / t1243_12 seams, and calling a helper
    this task just wrote and then asserting what it wrote would be testing the
    test. Their contract is stated by `CoalesceRuleTests` instead.
    """

    def test_fixture_facts(self):
        m = self._seed([f"c0/{PERF}", f"c0/{ONLY_C0}", f"c1/{PERF}", f"c2/{PERF}"])
        self.assertEqual(
            m.collapsed_groups,
            {f"c0/{PERF}", f"c0/{ONLY_C0}", f"c1/{PERF}", f"c2/{PERF}"},
            "all four seeded keys must survive load — otherwise every case "
            "below could pass by pruning everything")
        for col, slug, n in (("c0", PERF, 2), ("c0", ONLY_C0, 2),
                             ("c1", PERF, 2), ("c2", PERF, 2)):
            members = [t for t in m.get_column_tasks(col)
                       if t.metadata.get("boardgroup") == slug]
            self.assertEqual(len(members), n, f"{col}/{slug} must have {n} members")

    def test_delete_column_repoints_every_key_to_unordered(self):
        m = self._seed([f"c0/{PERF}", f"c0/{ONLY_C0}", f"c1/{PERF}"])
        m.delete_column("c0")
        for source in (m, self._fresh()):
            keys = set(source.collapsed_groups)
            self.assertIn(f"unordered/{ONLY_C0}", keys,
                          "an owner that re-points only the first key it finds "
                          "would drop this one")
            self.assertNotIn(f"c0/{PERF}", keys)
            self.assertNotIn(f"c0/{ONLY_C0}", keys)
            self.assertIn(f"c1/{PERF}", keys,
                          "control: an untouched column keeps its key")

    def test_rename_repoints_the_column_half(self):
        m = self._seed([f"c0/{PERF}", f"c0/{ONLY_C0}", f"c1/{PERF}"])
        m.update_column("c0", "c0new", "Renamed", "blue")
        for source in (m, self._fresh()):
            keys = set(source.collapsed_groups)
            self.assertIn(f"c0new/{PERF}", keys)
            self.assertIn(f"c0new/{ONLY_C0}", keys)
            self.assertNotIn(f"c0/{PERF}", keys)
            self.assertIn(f"c1/{PERF}", keys, "control: c1 untouched")

    def test_merge_repoints_every_source_key_to_the_destination(self):
        m = self._seed([f"c0/{PERF}", f"c0/{ONLY_C0}", f"c2/{PERF}"])
        result = m.merge_columns(["c0"], "c1")
        self.assertTrue(result.complete, f"merge did not complete: {result}")
        for source in (m, self._fresh()):
            keys = set(source.collapsed_groups)
            self.assertIn(f"c1/{ONLY_C0}", keys)
            self.assertNotIn(f"c0/{PERF}", keys)
            self.assertNotIn(f"c0/{ONLY_C0}", keys)
            self.assertIn(f"c2/{PERF}", keys, "control: c2 untouched")

    def test_a_refused_merge_leaves_the_keys_untouched(self):
        seeded = [f"c0/{PERF}", f"c1/{PERF}"]
        m = self._seed(seeded)
        before = self._local_path.read_bytes()
        result = m.merge_columns([], "c1")
        self.assertTrue(result.refused, "the merge must have been refused")
        self.assertEqual(set(m.collapsed_groups), set(seeded))
        self.assertEqual(self._local_path.read_bytes(), before,
                         "a refused merge writes nothing at all")

    def test_a_source_that_did_not_drain_keeps_its_key(self):
        """Separates "iterate source_ids" from "iterate drained".

        It must be a PARTIAL merge. When nothing drains at all, `merge_columns`
        returns at `if not drained:` before the remap runs, so the two spellings
        are indistinguishable and the case proves nothing. Here c0 drains and c2
        does not, so `drained == ["c0"]` while `source_ids == ["c0", "c2"]`: an
        implementation keyed on the latter re-points c2's key to a column c2's
        members never left.
        """
        m = self._seed([f"c0/{PERF}", f"c2/{PERF}"])
        blocked = {"t9220_g.md", "t9221_h.md"}          # c2's members
        original = self.ab.Task.reload_and_save_board_fields

        def selective(task, fields):
            if task.filename in blocked:
                raise OSError(28, "No space left on device")
            return original(task, fields)

        with mock.patch.object(self.ab.Task, "reload_and_save_board_fields",
                               selective):
            result = m.merge_columns(["c0", "c2"], "c1")

        self.assertEqual(set(result.sources_removed), {"c0"},
                         "control: exactly one source drained — without that "
                         "asymmetry this case cannot discriminate")
        keys = set(m.collapsed_groups)
        self.assertIn(f"c1/{PERF}", keys, "the drained source was re-pointed")
        self.assertIn(f"c2/{PERF}", keys,
                      "the source that did NOT drain still holds its members, "
                      "so its key is still true and must be left alone")

    def test_a_failed_user_layer_write_is_healed_by_the_next_load(self):
        """The project half lands, the local half does not — the stale key on
        disk is pruned by any later session (the `collapsed_columns` contract)."""
        m = self._seed([f"c0/{PERF}", f"c0/{ONLY_C0}"])
        with mock.patch.object(self.ab, "save_local_config",
                               side_effect=OSError(28, "No space")):
            m.merge_columns(["c0"], "c1")
        self.assertIn(f"c0/{PERF}", self._persisted(),
                      "control: the stale key is still on disk")
        fresh = self._fresh()
        self.assertNotIn(f"c0/{PERF}", fresh.collapsed_groups,
                         "…and a fresh manager prunes it (c0 no longer exists, "
                         "so nothing claims that key)")


class CoalesceRuleTests(_LifecycleBase, unittest.TestCase):
    """The rule, in the only directions that can discriminate.

    Both-collapsed is NOT discriminating: "destination wins" and "arriving is
    adopted" are indistinguishable when the two states are equal. The
    asymmetric pair below is what separates them.
    """

    def test_fixture_facts(self):
        m = self._seed([])
        c0 = {t.metadata.get("boardgroup") for t in m.get_column_tasks("c0")}
        c1 = {t.metadata.get("boardgroup") for t in m.get_column_tasks("c1")}
        un = {t.metadata.get("boardgroup") for t in m.get_column_tasks("unordered")}
        self.assertIn(PERF, c0)
        self.assertIn(PERF, c1, "c0 and c1 must SHARE a slug — the collision")
        self.assertIn(PERF, un, "`unordered` pre-holds the same slug")

    def test_destination_key_wins_when_it_already_exists(self):
        """Arriving is EXPANDED, destination COLLAPSED.

        **A specification pin, NOT a discriminating guard — deliberately kept
        and deliberately labelled.** Under a presence-set representation an
        expanded arriving group has no key at all, so there is nothing a
        key-remapping implementation could overwrite the destination with: this
        direction of the rule cannot be violated, and a negative control
        (re-pointing keyed on `source_ids`, and dropping source keys instead of
        re-pointing them) leaves it green. It is here because the design states
        the rule in two directions and the outcome is worth asserting; the
        direction that CAN fail is `test_the_arriving_state_is_adopted_*`, and
        the duplicate-key risk is covered by `test_the_vacated_key_*`.
        """
        m = self._seed([f"c1/{PERF}"])
        m.merge_columns(["c0"], "c1")
        self.assertIn(f"c1/{PERF}", self._fresh().collapsed_groups)

    def test_the_arriving_state_is_adopted_when_the_destination_has_none(self):
        """Arriving is COLLAPSED, destination EXPANDED.

        A "destination always wins, drop the arrival" implementation loses the
        collapse here.
        """
        m = self._seed([f"c0/{PERF}"])
        m.merge_columns(["c0"], "c1")
        keys = set(self._fresh().collapsed_groups)
        self.assertIn(f"c1/{PERF}", keys)
        self.assertNotIn(f"c0/{PERF}", keys)

    def test_the_vacated_key_is_dropped_and_never_duplicated(self):
        """Asserted on the LIST: a naive append yields two identical entries,
        which a set-based assertion cannot see."""
        m = self._seed([f"c0/{PERF}", f"c1/{PERF}"])
        m.merge_columns(["c0"], "c1")
        persisted = self._persisted()
        self.assertEqual(persisted.count(f"c1/{PERF}"), 1, persisted)
        self.assertNotIn(f"c0/{PERF}", persisted)

    def test_a_same_slug_group_in_an_untouched_column_is_unaffected(self):
        m = self._seed([f"c2/{PERF}"])
        m.merge_columns(["c0"], "c1")
        self.assertIn(f"c2/{PERF}", self._fresh().collapsed_groups,
                      "the rule keys on (col, slug), not on slug")

    def test_delete_column_coalesces_onto_an_existing_unordered_identity(self):
        """The same rule through the second real owner — a genuine collision,
        because `unordered` already holds a `perf_work` group."""
        m = self._seed([f"unordered/{PERF}"])
        m.delete_column("c0")
        persisted = self._persisted()
        self.assertEqual(persisted.count(f"unordered/{PERF}"), 1, persisted)
        members = [t.filename for t in self._fresh().get_column_tasks("unordered")
                   if t.metadata.get("boardgroup") == PERF]
        self.assertIn("t9200_a.md", members,
                      "c0's members really did join the unordered group")
        self.assertIn("t9240_j.md", members, "…alongside the residents")

    def test_the_full_key_combination_table(self):
        """All four cells, stated independently of any owner.

        This is the contract t1243_11 / t1243_12 build on, which is why it is
        asserted directly against the pure rule rather than only through a
        column operation.
        """
        from board_groups import column_remap, remap_group_keys
        rule = column_remap({"c0": "c1"})
        cases = {
            "both collapsed": ([f"c0/{PERF}", f"c1/{PERF}"], [f"c1/{PERF}"]),
            "dest only": ([f"c1/{PERF}"], [f"c1/{PERF}"]),
            "arriving only": ([f"c0/{PERF}"], [f"c1/{PERF}"]),
            "neither": ([], []),
        }
        for name, (given, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(remap_group_keys(given, rule), expected)


# --- 7. prune on load --------------------------------------------------------


class PruneOnLoadTests(_LifecycleBase, unittest.TestCase):

    def _rewrite_group(self, filename, value):
        """Change a member's `boardgroup` ON DISK — the external-edit path the
        sweep exists to backstop."""
        path = self.tasks_dir / filename
        text = path.read_text(encoding="utf-8")
        if value is None:
            text = "\n".join(l for l in text.splitlines()
                             if not l.startswith("boardgroup:")) + "\n"
        else:
            text = text.replace(f"boardgroup: {PERF}", f"boardgroup: {value}")
        path.write_text(text, encoding="utf-8")

    def test_fixture_facts(self):
        """THE load-order guard.

        If the sweep ran inside `load_metadata` — where the COLUMN prune lives —
        `task_datas` would still be empty, every key would look memberless, and
        the whole list would be wiped on every boot. Every other case in this
        class would still pass. This one would not.
        """
        m = self._seed([f"c0/{PERF}"])
        self.assertEqual(set(m.collapsed_groups), {f"c0/{PERF}"},
                         "a VALID key must survive a fresh manager")

    def test_a_key_with_no_members_is_dropped(self):
        m = self._seed([f"c0/ghost_grp", f"c0/{PERF}"])
        keys = set(m.collapsed_groups)
        self.assertNotIn("c0/ghost_grp", keys)
        self.assertIn(f"c0/{PERF}", keys, "control: the real key survives")

    def test_a_group_that_dropped_to_one_member_is_kept(self):
        """`build_column_units` keeps a single member's slug, so the key is inert
        (no header is drawn) rather than stale. Pruning here would silently
        discard the collapse the first time a sync moved a member out."""
        self._rewrite_group("t9201_b.md", None)          # c0/perf_work -> 1 member
        m = self._seed([f"c0/{PERF}"])
        self.assertIn(f"c0/{PERF}", m.collapsed_groups)

    def test_a_group_that_dropped_to_zero_members_is_dropped(self):
        """Paired with the case above: the two differ by exactly ONE member and
        must differ in outcome, so any `< 2` or off-by-one fails one of them."""
        for name in ("t9200_a.md", "t9201_b.md"):
            self._rewrite_group(name, None)
        m = self._seed([f"c0/{PERF}", f"c0/{ONLY_C0}"])
        self.assertNotIn(f"c0/{PERF}", m.collapsed_groups)
        self.assertIn(f"c0/{ONLY_C0}", m.collapsed_groups,
                      "control: the other group in the same column survives")

    def test_a_single_member_group_from_the_fixture_is_kept(self):
        m = self._seed([f"c3/{SOLO}"])
        self.assertIn(f"c3/{SOLO}", m.collapsed_groups,
                      "c3's group has exactly one member by construction")

    def test_an_unordered_key_survives_the_sweep(self):
        """`unordered` is collapsible but absent from `columns` — the exact trap
        `_prune_orphan_collapsed_columns` whitelists against. Membership-based
        pruning gets it right without a whitelist."""
        m = self._seed([f"unordered/{PERF}"])
        self.assertIn(f"unordered/{PERF}", m.collapsed_groups)

    def test_a_key_naming_a_dead_column_is_dropped_once_nothing_claims_it(self):
        m = self._seed([f"c9/{PERF}", f"c0/{PERF}"])
        self.assertNotIn(f"c9/{PERF}", m.collapsed_groups,
                         "no task claims column c9, so nothing has that identity")
        self.assertIn(f"c0/{PERF}", m.collapsed_groups)

    def test_a_trailing_space_slug_is_a_different_identity(self):
        """`normalize_group_slug` deliberately does NOT strip — a `.strip()` in
        the key parser would silently fuse two distinct groups."""
        m = self._seed([f"c0/{PERF} "])
        self.assertNotIn(f"c0/{PERF} ", m.collapsed_groups)
        self.assertNotIn(f"c0/{PERF}", m.collapsed_groups,
                         "and it must NOT be normalised onto the real group")

    def test_a_non_list_value_is_tolerated(self):
        payload = json.loads(self._local_path.read_text(encoding="utf-8"))
        payload["settings"]["collapsed_groups"] = f"c0/{PERF}"     # a bare string
        self._local_path.write_text(json.dumps(payload, indent=2) + "\n",
                                    encoding="utf-8")
        m = self.ab.TaskManager()
        self.assertEqual(set(m.collapsed_groups), set(),
                         "a scalar is treated as absent, never iterated as chars")

    def test_the_prune_is_in_memory_until_the_next_save(self):
        """The `collapsed_columns` contract, so a reader learns one rule."""
        m = self._seed(["c0/ghost_grp", f"c0/{PERF}"])
        self.assertNotIn("c0/ghost_grp", m.collapsed_groups)
        self.assertIn("c0/ghost_grp", self._persisted(),
                      "…but the on-disk list still holds it")
        m.save_settings()
        self.assertNotIn("c0/ghost_grp", self._persisted())
        self.assertIn(f"c0/{PERF}", self._persisted())

    def test_the_sweep_is_skipped_while_a_task_file_is_unreadable(self):
        """"Cannot verify" is its own state — the same rule `merge_columns` uses.

        A failed `Task.load()` wipes that task's metadata, so its membership is
        invisible; sweeping then would prune a live group on a transient error.
        """
        # Invalid UTF-8 is what actually makes `Task.load()` return False; a
        # merely malformed YAML body still parses to `metadata == {}`, which is
        # indistinguishable from a phantom stub (t1377_4).
        (self.tasks_dir / "t9200_a.md").write_bytes(b"\xff\xfe not valid utf-8")
        m = self._seed([f"c0/{PERF}", "c0/ghost_grp"])
        self.assertTrue(m.unreadable_files, "control: the file must be unreadable")
        self.assertIn(f"c0/{PERF}", m.collapsed_groups)
        self.assertIn("c0/ghost_grp", m.collapsed_groups,
                      "even a genuinely orphaned key is left alone while the "
                      "tree cannot be trusted")


if __name__ == "__main__":
    unittest.main()
