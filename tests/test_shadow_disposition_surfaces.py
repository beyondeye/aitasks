#!/usr/bin/env python3
"""Guard: every shadow impl-review surface enumerates the SAME disposition set.

The shadow's implementation review classifies each finding with a *disposition*
(``blocking`` / ``follow-up`` / ``informational``). That vocabulary is written out
independently at five prose sites across three files, with **no single source of
truth** and no derivation between them:

  * ``impl-review-angles.md`` — the rubric that defines the values
  * ``impl-review-angles.md`` — the partition order and cap-cut order
  * ``impl-challenge.md``     — the per-finding presentation bullet
  * ``impl-challenge.md``     — the ``Disposition: …`` concern-block trailer
  * the website workflow doc  — the user-facing description

A surface that misses an update silently contradicts the others, and the shadow
follows whichever one it happened to read. t1200 added the third value
(``informational``) and this guard with it.

**Why site granularity, not file granularity.** Two of the files carry two sites
each. A file-level check passes vacuously when one site lists all three values
while a second site in the same file still says only blocking/follow-up — which
is exactly the shape those files have. So each site is anchored to its markdown
heading and checked on its own.

**Why a proximity rule, not a list of stale phrasings.** The two-value
enumeration appears in several shapes (``\\`blocking\\` or \\`follow-up\\```; "blocking
first, then follow-up"; "(``Disposition: blocking.`` or ``Disposition:
follow-up.``)"). Matching literal phrasings would miss the next shape someone
writes, so instead: wherever ``blocking`` and ``follow-up`` occur close together,
``informational`` must occur there too.

Adding a **fourth** disposition means updating ``DISPOSITIONS`` *and* every site
in ``SITES`` — this guard will tell you which ones you missed.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ANGLES = ".claude/skills/aitask-shadow/impl-review-angles.md"
CHALLENGE = ".claude/skills/aitask-shadow/impl-challenge.md"
SHADOW_SKILL = ".claude/skills/aitask-shadow/SKILL.md"
WEBSITE = "website/content/docs/workflows/shadow-agent.md"

DISPOSITIONS = ("blocking", "follow-up", "informational")

# (file, heading prefix) — one entry per site that ENUMERATES the dispositions.
# The prefix is matched against the start of the heading line, so a
# parenthetical suffix can still be reworded without breaking the guard.
SITES = [
    (ANGLES, "## Disposition rubric"),
    (ANGLES, "## Ordering, caps, and the no-silent-omission"),
    (CHALLENGE, "## Findings presentation"),
    (CHALLENGE, "## Also emit the structured concern block"),
    (WEBSITE, "### Review the implementation"),
]

# Every shadow surface that mentions dispositions at all. SKILL.md is checked for
# stale two-value enumerations but is deliberately NOT required to list all three
# values — it describes review *tiers*, not dispositions.
ALL_SURFACES = [ANGLES, CHALLENGE, SHADOW_SKILL, WEBSITE]

#: Half-width, in normalized characters, of the co-occurrence window. Wide enough
#: to span a sentence or a bulleted clause, narrow enough that two unrelated
#: paragraphs do not bleed into each other.
WINDOW = 160


def normalize(text: str) -> str:
    """Collapse all whitespace so line-wrapped prose matches like any other.

    Load-bearing: the rubric's own enumeration is wrapped across two source
    lines, so a line-oriented search (``grep``) structurally cannot see it.
    """
    return re.sub(r"\s+", " ", text)


def stale_enumerations(text: str, window: int = WINDOW) -> list[str]:
    """Return the windows where ``blocking`` and ``follow-up`` co-occur without
    ``informational`` — i.e. a disposition enumeration that lost the third value.
    """
    norm = normalize(text)
    offenders = []
    for match in re.finditer(r"blocking", norm, re.IGNORECASE):
        lo = max(0, match.start() - window)
        hi = min(len(norm), match.end() + window)
        chunk = norm[lo:hi]
        if re.search(r"follow-up", chunk, re.IGNORECASE) and not re.search(
            r"informational", chunk, re.IGNORECASE
        ):
            offenders.append(chunk)
    return offenders


def extract_section(path: Path, heading_prefix: str) -> str:
    """Return the text under the heading starting with ``heading_prefix``.

    The slice runs to the next heading of the same-or-shallower level. Raises
    ``AssertionError`` when the anchor does not match exactly one heading — the
    tripwire that stops a renamed heading from silently reducing this guard to
    checking nothing.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines) if line.startswith(heading_prefix)]
    if len(hits) != 1:
        raise AssertionError(
            f"{path}: heading anchor {heading_prefix!r} matched {len(hits)} lines "
            f"(expected exactly 1). A heading was renamed, removed, or duplicated "
            f"— update SITES in {Path(__file__).name}."
        )
    start = hits[0]
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip("#")
        depth = len(lines[i]) - len(stripped)
        if 0 < depth <= level and stripped.startswith(" "):
            end = i
            break
    return "\n".join(lines[start + 1 : end])


class TestDispositionSites(unittest.TestCase):
    """Each enumerating site lists all three dispositions, three-way everywhere."""

    def test_every_site_lists_all_three_dispositions(self):
        for rel, anchor in SITES:
            with self.subTest(file=rel, site=anchor):
                section = normalize(extract_section(REPO_ROOT / rel, anchor))
                self.assertTrue(
                    section.strip(),
                    f"{rel}: section {anchor!r} is empty — the anchor matched a "
                    f"heading with no body, so this site is not really checked.",
                )
                for value in DISPOSITIONS:
                    self.assertIn(
                        value,
                        section,
                        f"{rel}: site {anchor!r} never mentions the "
                        f"{value!r} disposition. Every site that enumerates "
                        f"dispositions must list all of {DISPOSITIONS}.",
                    )

    def test_no_site_carries_a_two_value_enumeration(self):
        for rel, anchor in SITES:
            with self.subTest(file=rel, site=anchor):
                offenders = stale_enumerations(extract_section(REPO_ROOT / rel, anchor))
                self.assertEqual(
                    offenders,
                    [],
                    f"{rel}: site {anchor!r} names 'blocking' and 'follow-up' "
                    f"together without 'informational'. First offending window:\n"
                    f"  …{offenders[0] if offenders else ''}…",
                )


class TestWholeSurfaceSweep(unittest.TestCase):
    """Catch a stale enumeration living outside any anchored site."""

    def test_no_surface_carries_a_two_value_enumeration_anywhere(self):
        for rel in ALL_SURFACES:
            with self.subTest(file=rel):
                text = (REPO_ROOT / rel).read_text(encoding="utf-8")
                offenders = stale_enumerations(text)
                self.assertEqual(
                    offenders,
                    [],
                    f"{rel}: names 'blocking' and 'follow-up' together without "
                    f"'informational' somewhere outside the anchored sites. "
                    f"First offending window:\n"
                    f"  …{offenders[0] if offenders else ''}…",
                )


class TestGuardNegativeControls(unittest.TestCase):
    """Prove the guard can actually fail, rather than passing vacuously."""

    def test_flags_the_or_form(self):
        self.assertTrue(
            stale_enumerations("its disposition — `blocking` or `follow-up`, per the rubric"),
            "the guard must flag the plain `blocking` or `follow-up` enumeration",
        )

    def test_flags_the_disposition_trailer_form(self):
        self.assertTrue(
            stale_enumerations(
                "End the body with the disposition as prose (`Disposition: "
                "blocking.` or `Disposition: follow-up.`) and, in Advanced/Deep, "
                "its verdict."
            ),
            "the guard must flag the `Disposition: …` trailer enumeration",
        )

    def test_flags_the_partition_order_form(self):
        self.assertTrue(
            stale_enumerations("Partition findings `blocking` first, then `follow-up`."),
            "the guard must flag the partition-order enumeration",
        )

    def test_flags_a_line_wrapped_enumeration(self):
        """The case a line-based grep misses — the reason normalize() exists."""
        self.assertTrue(
            stale_enumerations("carries a disposition: `blocking` or\n`follow-up`."),
            "the guard must flag an enumeration split across source lines",
        )

    def test_accepts_the_three_way_form(self):
        self.assertEqual(
            stale_enumerations(
                "its disposition — `blocking`, `follow-up`, or `informational`."
            ),
            [],
            "the guard must NOT flag a correct three-way enumeration",
        )

    def test_unrelated_distant_mentions_do_not_trip_the_guard(self):
        """`blocking` and `follow-up` far apart are not an enumeration."""
        far = "the blocking partition. " + ("filler text. " * 40) + "a follow-up task."
        self.assertEqual(stale_enumerations(far), [])

    def test_missing_anchor_raises(self):
        with self.assertRaises(AssertionError):
            extract_section(REPO_ROOT / ANGLES, "## No Such Heading Exists")


if __name__ == "__main__":
    unittest.main()
