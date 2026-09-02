"""Drift guard + codepoint policy for the t1638 mark-glyph extraction.

`lib/mark_glyphs.py` exists because the repo-wide multi-select mark (t1004) had
grown FOUR independent definitions in three different expression forms — a
Textual CSS rule, two Rich-markup string literals, and a `rich.style.Style` —
which is how the checked and unchecked marks ended up with different colour
authorities and, in the DAG's case, a different colour entirely (Rich resolves
`yellow` to #808000, Textual to #FFFF00). Extracting it fixed that once; this
file is what stops it coming back.

## Detection scope (documented on purpose — a guard that overclaims is worse
## than one with a known boundary)

Scanned: the declared `CONSUMERS` only, via `ast`. Deliberately NOT repo-wide —
see `QuestionDetectorPinTests` for a file that must KEEP its `☐`.

  * Rule 1 — a re-declaration of a mark name bound to a *literal*. An alias or
    derivation (`X = rich_mark_style(True)`) is allowed: consumers must be able
    to re-export.
  * Rule 2 — a mark glyph appearing in any string constant in consumer code,
    docstrings excluded, unless waived in `ALLOWED_LITERALS` with a reason.
    Catches the two shapes that actually shipped — `widgets.py` and
    `_RejectedRow.render` were both literals nested inside methods, invisible to
    a module-level scan.
  * Rule 3 — the positive half: each consumer imports from `mark_glyphs`, every
    imported name is actually *used*, and at least one is a rendering helper. A
    bare "does it import" check would accept a decorative unused import sitting
    above hand-rolled rendering, leaving the guard green while the defect is
    present.
  * Rule 4 — the bare glyph constants may not appear inside an f-string or a
    string-building `BinOp`. Without it, Rules 1-3 still permit
    `f"[bold #FF0000]{MARK_CHECKED}[/]"` — glyph correctly sourced, colour
    hand-rolled — which is exactly the drift this guard exists to forbid, and it
    is unreachable by a glyph scan or an import check. Rule 4 is also why colour
    literals need no separate scan: `#6272A4` legitimately appears ~8 times in
    `brainstorm_dag_display.py` for unrelated things, so a hex ban would be
    unworkable, but with Rule 4 a consumer has no way to attach a colour of its
    own to a mark.
  * NOT detected: a glyph built at runtime (`chr(0x2611)`), pinned by
    `test_a_computed_glyph_is_outside_the_documented_scope`. A re-fork under a
    different name is caught by Rule 2 but not Rule 1. `"\\u2611"` IS caught —
    Python resolves the escape at parse time, so it is the same `ast.Constant`.

`CodepointPolicyTests` enforces the admissibility policy itself, offline and
with no font installed; `ManifestFreshnessTests` validates the checked-in
evidence against the real fonts wherever they exist.

Run: `python tests/test_mark_glyphs_single_source.py`
(also collected by `tests/run_all_python_tests.sh`).
"""

from __future__ import annotations

import ast
import json
import shutil
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from typing import List

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_DIR / ".aitask-scripts"
MANIFEST_PATH = PROJECT_DIR / "tests" / "data" / "font_coverage.json"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

from mark_glyphs import (  # noqa: E402
    GLYPH_EVIDENCE,
    MARK_CHECKED,
    MARK_CHECKED_COLOUR,
    MARK_UNCHECKED,
    MARK_UNCHECKED_COLOUR,
    SUPPORTED_FONTS,
)

#: Every surface that renders the multi-select mark, relative to `.aitask-scripts/`.
CONSUMERS = (
    "board/aitask_board.py",
    "brainstorm/brainstorm_dag_display.py",
    "brainstorm/widgets.py",
    "monitor/monitor_shared.py",
)

#: Names `mark_glyphs` owns. A consumer binding one of these to a LITERAL has
#: re-forked the authority; binding it to a name or a call is a re-export.
OWNED_NAMES = (
    "MARK_CHECKED", "MARK_UNCHECKED",
    "MARK_CHECKED_COLOUR", "MARK_UNCHECKED_COLOUR",
    "MARK_CHECKED_STYLE", "MARK_UNCHECKED_STYLE",
)

#: The bare glyph constants. Rule 4 forbids these inside string building.
GLYPH_NAMES = ("MARK_CHECKED", "MARK_UNCHECKED")

#: The helpers that actually render. Rule 3 requires each consumer to import at
#: least one, so "imports the module" cannot be satisfied decoratively.
RENDER_HELPERS = ("mark_markup", "rich_mark_style")

RATIFIED = (MARK_CHECKED, MARK_UNCHECKED)

#: Names a consumer imports purely to RE-EXPORT, with the reason. Rule 3
#: otherwise requires every imported name to be used, because a decorative
#: import is exactly how a consumer can look compliant while hand-rolling its
#: rendering beside it. A re-export is the one legitimate exception, so it is
#: declared here rather than silently tolerated — and `test_no_reexport_waiver_
#: has_gone_stale` fails once the name stops being importable from the consumer.
#:
#: NOTE this is deliberately NOT an escape hatch for the rendering helpers: the
#: "at least one render helper, and it must be USED" check below does not consult
#: this table, so no consumer can satisfy Rule 3 without actually rendering
#: through the authority.
RE_EXPORTS = {
    "board/aitask_board.py": {
        "MARK_CHECKED": ("re-exported for tests and callers that read the bare "
                         "glyph off the board module (test_board_marking.py); "
                         "the board itself renders via mark_markup()."),
        "MARK_UNCHECKED": ("as MARK_CHECKED above."),
    },
}

#: Pre-existing, unrelated uses of a ratified codepoint. Each is a DIFFERENT
#: vocabulary that happens to share a character; a blanket ban would fail for
#: innocent reasons, which is how a guard gets weakened rather than fixed (cf.
#: tests/test_plan_paths_seam.sh's "a guard that fails for innocent reasons
#: trains people to weaken it"). Every entry is re-checked for staleness by
#: `test_no_waiver_has_gone_stale`.
ALLOWED_LITERALS = {
    "board/aitask_board.py": {
        "✓": ("by-trail freshness ('✓ current (recorded)') and the follow-up-kind "
              "picker's current-selection tick. Both are SINGLE-select 'this one "
              "is current', not multi-select 'this one is marked' — semantically "
              "adjacent, deliberately not unified."),
    },
}


# --- scanning ---------------------------------------------------------------


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """`id()` of every string constant that is a docstring.

    Compared by identity rather than by value: a module that legitimately holds
    the same text in code and in a docstring must not have the code copy
    excused by the docstring one.
    """
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _is_literal(node: ast.AST) -> bool:
    """True for an RHS built only from constants (a fork), False for a name,
    attribute or call (a re-export or derivation, which is the intended form)."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.JoinedStr):
        return all(
            isinstance(v, ast.Constant)
            for v in node.values
            if not isinstance(v, ast.FormattedValue)
        ) and not any(isinstance(v, ast.FormattedValue) for v in node.values)
    if isinstance(node, ast.BinOp):
        return _is_literal(node.left) and _is_literal(node.right)
    return False


def _string_building_parents(tree: ast.AST) -> List[ast.AST]:
    """Every f-string and string-concatenating BinOp in the tree."""
    out: List[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            out.append(node)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            out.append(node)
    return out


def scan_file(rel: str, path: Path) -> List[str]:
    """Violations in one consumer, as `<rule>:<detail>` strings."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: List[str] = []
    waived = ALLOWED_LITERALS.get(rel, {})

    # Rule 1 — re-declaration bound to a literal.
    for node in ast.walk(tree):
        targets: List[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if node.value is None or not _is_literal(node.value):
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in OWNED_NAMES:
                found.append(f"rule1:{target.id}")

    # Rule 2 — a ratified glyph in a string constant (docstrings excluded).
    docstrings = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in docstrings:
            continue
        for glyph in RATIFIED:
            if glyph in node.value and glyph not in waived:
                found.append(f"rule2:{glyph}:line{node.lineno}")

    # Rule 4 — a bare glyph constant inside string building.
    for parent in _string_building_parents(tree):
        for node in ast.walk(parent):
            if isinstance(node, ast.Name) and node.id in GLYPH_NAMES:
                found.append(f"rule4:{node.id}:line{node.lineno}")

    return sorted(set(found))


def scan_tree(root: Path) -> List[str]:
    """`<file>:<violation>` for every consumer under `root`."""
    out: List[str] = []
    for rel in CONSUMERS:
        path = root / rel
        if not path.exists():
            continue
        out.extend(f"{rel}:{v}" for v in scan_file(rel, path))
    return sorted(out)


def mark_glyphs_imports(path: Path) -> List[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "mark_glyphs":
            names.extend(a.asname or a.name for a in node.names)
    return names


def loaded_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        n.id for n in ast.walk(tree)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }


# --- the guard --------------------------------------------------------------


class MarkGlyphsSingleSourceTests(unittest.TestCase):
    def test_no_consumer_reforks_the_mark(self):
        self.assertEqual(
            scan_tree(SCRIPTS), [],
            msg=("a mark surface re-declares, hard-codes or self-composes the "
                 "glyph/colour that lives in lib/mark_glyphs.py — import "
                 "mark_markup()/rich_mark_style() instead of re-forking it"),
        )

    def test_scanner_sees_every_consumer(self):
        """Guards against the whole file going vacuous on a rename."""
        for rel in CONSUMERS:
            self.assertTrue((SCRIPTS / rel).exists(), rel)

    def test_no_waiver_has_gone_stale(self):
        """A waiver whose literal no longer occurs is an exception quietly
        accumulating. Each must still be earning its place."""
        for rel, glyphs in ALLOWED_LITERALS.items():
            text = (SCRIPTS / rel).read_text(encoding="utf-8")
            for glyph in glyphs:
                self.assertIn(
                    glyph, text,
                    f"{rel} no longer contains {glyph!r}; drop the waiver",
                )

    def test_no_reexport_waiver_has_gone_stale(self):
        """A re-export waiver must name something the consumer really imports,
        or it is an exception outliving its reason."""
        for rel, names in RE_EXPORTS.items():
            imported = mark_glyphs_imports(SCRIPTS / rel)
            for name in names:
                self.assertIn(
                    name, imported,
                    f"{rel} no longer imports {name}; drop the RE_EXPORTS entry",
                )

    def test_every_consumer_imports_and_uses_the_authority(self):
        """Rule 3, the positive half. Absence of a local copy is not enough —
        the names must be imported AND actually used, or a consumer could
        satisfy the negative half by rendering nothing at all."""
        for rel in CONSUMERS:
            path = SCRIPTS / rel
            imported = mark_glyphs_imports(path)
            self.assertTrue(imported, f"{rel} imports nothing from mark_glyphs")
            used = loaded_names(path)
            self.assertTrue(
                any(h in imported and h in used for h in RENDER_HELPERS),
                f"{rel} imports from mark_glyphs but never USES a rendering "
                f"helper ({', '.join(RENDER_HELPERS)}) — whatever paints its "
                f"mark, it is not the authority",
            )
            reexports = RE_EXPORTS.get(rel, {})
            for name in imported:
                if name in reexports:
                    continue
                self.assertIn(
                    name, used,
                    f"{rel} imports {name} from mark_glyphs but never uses it; "
                    f"an unused import satisfies no contract. If it is a "
                    f"deliberate re-export, declare it in RE_EXPORTS.",
                )

    # --- Negative controls: prove each rule can actually fire ---------------

    def _temp_copy(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for rel in CONSUMERS:
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS / rel, dest)
        return tmp

    def _append(self, tmp: Path, rel: str, text: str) -> None:
        with (tmp / rel).open("a", encoding="utf-8") as fh:
            fh.write(text)

    def test_negative_a_literal_redeclaration_is_flagged(self):
        tmp = self._temp_copy()
        self._append(tmp, "board/aitask_board.py", '\n\nMARK_CHECKED = "☑"\n')
        violations = scan_tree(tmp)
        self.assertIn("board/aitask_board.py:rule1:MARK_CHECKED", violations)
        # Exactly one file flagged — the scanner is not matching indiscriminately.
        self.assertEqual(
            1, len({v.split(":", 1)[0] for v in violations}), violations
        )

    def test_negative_an_alias_redeclaration_is_not_flagged(self):
        """The re-export form MUST stay legal, or Rule 1 fails for the wrong
        reason and the fix would be to delete the guard."""
        tmp = self._temp_copy()
        self._append(tmp, "board/aitask_board.py",
                     "\n\nMARK_CHECKED_STYLE = mark_markup(True)\n")
        self.assertEqual(scan_tree(tmp), [])

    def test_negative_a_glyph_literal_nested_in_a_function_is_flagged(self):
        """The shape that actually shipped in widgets.py and _RejectedRow."""
        tmp = self._temp_copy()
        self._append(tmp, "brainstorm/widgets.py",
                     '\n\ndef _rogue(marked):\n'
                     '    return "[bold yellow]✓[/]" if marked else "□"\n')
        violations = scan_tree(tmp)
        self.assertTrue(
            any(v.startswith("brainstorm/widgets.py:rule2:") for v in violations),
            violations,
        )

    def test_negative_a_commented_out_glyph_is_not_flagged(self):
        """AST, not grep."""
        tmp = self._temp_copy()
        self._append(tmp, "brainstorm/widgets.py", '\n\n# MARK_CHECKED = "✓"\n')
        self.assertEqual(scan_tree(tmp), [])

    def test_negative_self_composed_markup_is_flagged(self):
        """Rule 4 — the colour hole. The glyph is sourced correctly from the
        authority here; only the colour is hand-rolled, so neither the glyph
        scan nor the import check can see it."""
        tmp = self._temp_copy()
        self._append(tmp, "brainstorm/widgets.py",
                     '\n\ndef _rogue():\n'
                     '    return f"[bold #FF0000]{MARK_CHECKED}[/]"\n')
        violations = scan_tree(tmp)
        self.assertIn("brainstorm/widgets.py:rule4:MARK_CHECKED:line" +
                      str(len((tmp / "brainstorm/widgets.py")
                              .read_text(encoding="utf-8").splitlines())),
                      violations)

    def test_negative_calling_the_helper_in_an_fstring_is_not_flagged(self):
        """`f"{mark_markup(x)} "` is the INTENDED form — Rule 4 must not trip on
        it, or the guard forbids the very thing it is steering people toward."""
        tmp = self._temp_copy()
        self._append(tmp, "brainstorm/widgets.py",
                     '\n\ndef _ok(marked):\n'
                     '    return f"{mark_markup(marked)} "\n')
        self.assertEqual(scan_tree(tmp), [])

    def test_negative_a_missing_import_fails_rule_three(self):
        tmp = self._temp_copy()
        path = tmp / "brainstorm/widgets.py"
        text = path.read_text(encoding="utf-8").replace(
            "from mark_glyphs import mark_markup  # noqa: E402", "", 1)
        path.write_text(text, encoding="utf-8")
        self.assertEqual(mark_glyphs_imports(path), [])

    def test_negative_an_unused_import_is_detectable(self):
        """Rule 3's 'used' half. An import nobody references satisfies a naive
        import check while the rendering beside it is hand-rolled."""
        tmp = self._temp_copy()
        path = tmp / "brainstorm/widgets.py"
        self._append(tmp, "brainstorm/widgets.py",
                     "\nfrom mark_glyphs import GLYPH_EVIDENCE  # noqa: E402,F401\n")
        self.assertIn("GLYPH_EVIDENCE", mark_glyphs_imports(path))
        self.assertNotIn("GLYPH_EVIDENCE", loaded_names(path))

    def test_a_computed_glyph_is_outside_the_documented_scope(self):
        """The boundary, asserted rather than merely claimed. A runtime-built
        glyph is NOT detected; `"\\u2611"` would be, because Python resolves the
        escape at parse time into the same constant a literal produces."""
        tmp = self._temp_copy()
        self._append(tmp, "brainstorm/widgets.py",
                     "\n\ndef _sneaky():\n    return chr(0x2713)\n")
        self.assertEqual(scan_tree(tmp), [])


# --- the codepoint policy ---------------------------------------------------

#: Emoji-capable codepoints in U+2190..U+2BFF — the symbol blocks this repo
#: draws glyphs from. Derived from Unicode's `emoji-data.txt` (`Emoji=Yes`) and
#: restricted to that range. A stable literal: Unicode does not retract the
#: Emoji property, so this only ever grows, and a glyph outside the range is
#: outside the vocabulary anyway.
#:
#: Regenerate with:
#:   curl -s https://unicode.org/Public/UNIDATA/emoji/emoji-data.txt \
#:     | awk -F';' '/; Emoji /{print $1}' | tr -d ' ' \
#:     | awk -F'..' '{print $1, ($2==""?$1:$2)}' \
#:     | awk '{ for (i=strtonum("0x"$1); i<=strtonum("0x"$2); i++) \
#:              if (i>=0x2190 && i<=0x2BFF) printf "0x%04X,\n", i }'
_EMOJI_CAPABLE = frozenset({
    0x2194, 0x2195, 0x2196, 0x2197, 0x2198, 0x2199, 0x21A9, 0x21AA,
    0x231A, 0x231B, 0x2328, 0x23CF,
    0x23E9, 0x23EA, 0x23EB, 0x23EC, 0x23ED, 0x23EE, 0x23EF, 0x23F0,
    0x23F1, 0x23F2, 0x23F3, 0x23F8, 0x23F9, 0x23FA,
    0x24C2, 0x25AA, 0x25AB, 0x25B6, 0x25C0,
    0x25FB, 0x25FC, 0x25FD, 0x25FE,
    0x2600, 0x2601, 0x2602, 0x2603, 0x2604, 0x260E, 0x2611, 0x2614, 0x2615,
    0x2618, 0x261D, 0x2620, 0x2622, 0x2623, 0x2626, 0x262A, 0x262E, 0x262F,
    0x2638, 0x2639, 0x263A, 0x2640, 0x2642,
    0x2648, 0x2649, 0x264A, 0x264B, 0x264C, 0x264D, 0x264E, 0x264F,
    0x2650, 0x2651, 0x2652, 0x2653, 0x265F, 0x2660, 0x2663, 0x2665, 0x2666,
    0x2668, 0x267B, 0x267E, 0x267F,
    0x2692, 0x2693, 0x2694, 0x2695, 0x2696, 0x2697, 0x2699, 0x269B, 0x269C,
    0x26A0, 0x26A1, 0x26A7, 0x26AA, 0x26AB, 0x26B0, 0x26B1, 0x26BD, 0x26BE,
    0x26C4, 0x26C5, 0x26C8, 0x26CE, 0x26CF, 0x26D1, 0x26D3, 0x26D4,
    0x26E9, 0x26EA, 0x26F0, 0x26F1, 0x26F2, 0x26F3, 0x26F4, 0x26F5,
    0x26F7, 0x26F8, 0x26F9, 0x26FA, 0x26FD,
    0x2702, 0x2705, 0x2708, 0x2709, 0x270A, 0x270B, 0x270C, 0x270D, 0x270F,
    0x2712, 0x2714, 0x2716, 0x271D, 0x2721, 0x2728, 0x2733, 0x2734,
    0x2744, 0x2747, 0x274C, 0x274E, 0x2753, 0x2754, 0x2755, 0x2757,
    0x2763, 0x2764, 0x2795, 0x2796, 0x2797, 0x27A1, 0x27B0, 0x27BF,
    0x2934, 0x2935, 0x2B05, 0x2B06, 0x2B07, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55,
})


class CodepointPolicyTests(unittest.TestCase):
    """Both halves of the admissibility policy, offline and font-free.

    This is the executable form of "a future change cannot silently reintroduce
    an uncovered codepoint". Nothing here needs a font installed, so it runs in
    CI; `ManifestFreshnessTests` below is the tier that validates the evidence
    against reality wherever the fonts exist.
    """

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.coverage = cls.manifest["coverage"]

    def test_ratified_glyphs_are_the_chosen_codepoints(self):
        """The one place the codepoints appear as literals."""
        self.assertEqual(ord(MARK_CHECKED), 0x2713)
        self.assertEqual(ord(MARK_UNCHECKED), 0x25A1)

    # --- rule (a): every supported font covers it ---------------------------

    def test_every_ratified_glyph_is_covered_by_every_supported_font(self):
        """A MISSING entry is a failure, not a pass: adding a glyph without
        regenerating the manifest must fail rather than go unmeasured."""
        for glyph in RATIFIED:
            key = f"{ord(glyph):04X}"
            self.assertIn(
                key, self.coverage,
                f"{glyph!r} (U+{key}) has no coverage entry — run "
                f"tests/tools/regen_font_coverage.py",
            )
            for family in SUPPORTED_FONTS:
                self.assertIn(family, self.coverage[key], f"{key}/{family}")
                self.assertTrue(
                    self.coverage[key][family],
                    f"{glyph!r} (U+{key}) is NOT covered by {family}, so it "
                    f"will be resolved by system font fallback — the t1638 "
                    f"defect. Pick a covered codepoint.",
                )

    def test_the_manifest_is_not_vacuous(self):
        """Proves the manifest can express 'not covered' and that the generator
        discriminates rather than emitting `true` for everything."""
        for cp in (0x2610, 0x2611, 0x2605, 0x2606, 0x23F8):
            key = f"{cp:04X}"
            self.assertIn(key, self.coverage, key)
            for family in SUPPORTED_FONTS:
                self.assertFalse(
                    self.coverage[key][family],
                    f"U+{key} is recorded as covered by {family}; the whole "
                    f"coverage claim is suspect",
                )
        # U+2714 is the discriminating case: covered by one family, not the
        # other. A generator emitting a constant could not produce this.
        by_family = self.coverage["2714"]
        self.assertIn(True, by_family.values())
        self.assertIn(False, by_family.values())

    def test_the_parked_mark_evidence_is_recorded(self):
        """The t1685 park-glyph decision, kept machine-checked.

        `P` U+0050 is the monitor's parked mark (``monitor_shared.PARK_GLYPH``).
        It is not part of ``RATIFIED`` — that tuple is the multi-select pair this
        module owns — so its evidence would otherwise live only in prose, and the
        two alternatives it beat would stop being measured at all.

        The three verdicts together are what make the choice reviewable: `P` is
        covered everywhere and claimed by no emoji font; `⏸` is covered nowhere
        AND emoji-capable (the exact t1638 defect); `■` is covered everywhere but
        was rejected on legibility, not coverage — which is why it is asserted
        covered rather than assumed absent.
        """
        for family in SUPPORTED_FONTS:
            self.assertTrue(
                self.coverage["0050"][family],
                f"U+0050 (P, the parked mark) is not covered by {family} — "
                f"monitor_shared.PARK_GLYPH would resolve by fallback",
            )
            self.assertFalse(
                self.coverage["23F8"][family],
                f"U+23F8 was recorded as covered by {family}; the recorded "
                f"reason for rejecting it no longer holds",
            )
            self.assertTrue(
                self.coverage["25A0"][family],
                f"U+25A0 was recorded as uncovered by {family}; it was rejected "
                f"for colliding with the state dot, not for coverage",
            )
        self.assertIn(
            0x23F8, _EMOJI_CAPABLE,
            "U+23F8 is no longer emoji-capable, so the recorded rejection "
            "reason has gone stale",
        )
        self.assertNotIn(
            0x0050, _EMOJI_CAPABLE,
            "U+0050 became emoji-capable — the parked mark needs re-deciding",
        )

    def test_the_manifest_covers_exactly_the_supported_fonts(self):
        self.assertEqual(set(self.manifest["fonts"]), set(SUPPORTED_FONTS))
        for key, families in self.coverage.items():
            self.assertEqual(set(families), set(SUPPORTED_FONTS), key)

    # --- rule (b): no emoji font claims it ----------------------------------

    def test_no_ratified_glyph_is_emoji_capable(self):
        """The second half of the policy, and the one that would have caught
        `✔`. An emoji-capable codepoint can be resolved to a colour-bitmap font,
        which ignores the requested foreground entirely."""
        for glyph in RATIFIED:
            self.assertNotIn(
                ord(glyph), _EMOJI_CAPABLE,
                f"{glyph!r} (U+{ord(glyph):04X}) is emoji-capable: a fontconfig "
                f"change can route it to a colour-bitmap font, which paints its "
                f"own colours and ignores the mark's. This is the t1638 defect.",
            )

    def test_the_emoji_table_is_not_vacuous(self):
        """Without this the frozenset could go empty and pass forever."""
        for cp in (0x2611, 0x2714, 0x26A0):
            self.assertIn(cp, _EMOJI_CAPABLE, f"U+{cp:04X}")
        self.assertGreater(len(_EMOJI_CAPABLE), 100)

    # --- layout -------------------------------------------------------------

    def test_every_ratified_glyph_is_single_cell(self):
        from rich.cells import cell_len

        for glyph in RATIFIED:
            self.assertEqual(len(glyph), 1, f"{glyph!r} is not one codepoint")
            self.assertEqual(cell_len(glyph), 1, f"{glyph!r} is not one cell")
            self.assertNotIn(
                unicodedata.east_asian_width(glyph), ("W", "F"),
                f"{glyph!r} is double-width",
            )

    def test_the_ambiguous_width_residual_is_recorded_not_overlooked(self):
        """`□` U+25A1 is EAW *Ambiguous*, where the `☐` it replaced was
        *Neutral* — in a wide-ambiguous terminal it takes two cells while Rich
        budgets one, against the `_NARROW_PREFIX_COLS` and `BOX_WIDTH` budgets.

        This was chosen knowingly, over the narrow-safe `▫` U+25AB (which turns
        out to be emoji-capable anyway, so rule (b) would have rejected it). The
        assertion exists so the residual is a recorded decision that a future
        reader meets head-on, rather than a surprise found in a bug report.
        """
        self.assertEqual(unicodedata.east_asian_width(MARK_UNCHECKED), "A")
        self.assertEqual(unicodedata.east_asian_width(MARK_CHECKED), "N")
        self.assertIn(0x25AB, _EMOJI_CAPABLE)  # the rejected alternative

    # --- the recorded evidence ----------------------------------------------

    def test_glyph_evidence_is_recorded(self):
        """AC 5, executable: a codepoint change without a stated reason fails."""
        for glyph in RATIFIED:
            self.assertIn(glyph, GLYPH_EVIDENCE, f"{glyph!r} has no evidence")
            self.assertTrue(GLYPH_EVIDENCE[glyph].strip(), f"{glyph!r}")
            self.assertIn(f"U+{ord(glyph):04X}", GLYPH_EVIDENCE[glyph])

    def test_the_colours_are_hex_not_palette_names(self):
        """Rich resolves `yellow` to #808000 and Textual to #FFFF00, so a bare
        name meant the DAG painted a different colour from every other mark."""
        for value in (MARK_CHECKED_COLOUR, MARK_UNCHECKED_COLOUR):
            self.assertTrue(value.startswith("#"), value)
            self.assertNotIn("ansi", value.lower())


class ManifestFreshnessTests(unittest.TestCase):
    """Validate the checked-in evidence against the real fonts.

    This tier VALIDATES the manifest; it does not substitute for it. The
    unconditional per-family assertions above are what enforce the policy, so
    skipping here costs nothing — but wherever the fonts do exist, a stale or
    hand-edited manifest is caught.
    """

    def test_the_manifest_matches_the_installed_fonts(self):
        sys.path.insert(0, str(PROJECT_DIR / "tests" / "tools"))
        import regen_font_coverage as regen

        files = {}
        for family in SUPPORTED_FONTS:
            path = regen.locate(family)
            if path is None:
                self.skipTest(f"{family} is not installed on this machine")
            files[family] = path

        rebuilt = regen.build(files)
        current = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            current["coverage"], rebuilt["coverage"],
            "tests/data/font_coverage.json disagrees with the fonts on this "
            "machine — regenerate it with tests/tools/regen_font_coverage.py, "
            "and do not hand-edit it",
        )


class QuestionDetectorPinTests(unittest.TestCase):
    """`lib/workflow_phase.py` must KEEP the codepoints this task removes.

    This is the t1638 pre-phase mitigation, and it is why the drift guard above
    is consumer-scoped rather than repo-wide. `_QUESTION_HEADER_RE` matches
    **Claude Code's own terminal chip** (`☐ <Header>`) inside captured pane
    text: it is a detector for a *foreign* glyph, not a renderer of ours. A
    well-meaning repo-wide sweep of U+2610/U+2611 would rewrite it and silently
    disable AskUserQuestion detection in both monitors and the shadow flow —
    with no test failure anywhere near the edit.
    """

    def test_the_question_header_regex_still_names_claude_codes_chip(self):
        """The source spells these as regex escapes inside a raw string, so
        `.pattern` carries the text `\\u2610` rather than the character itself.
        Accept either spelling — the point is that the codepoint is still named,
        however it is written."""
        import workflow_phase

        pattern = workflow_phase._QUESTION_HEADER_RE.pattern
        for cp in ("☐", "☑"):
            spellings = (cp, f"\\u{ord(cp):04x}", f"\\u{ord(cp):04X}")
            self.assertTrue(
                any(s in pattern for s in spellings),
                msg=("workflow_phase._QUESTION_HEADER_RE no longer names "
                     f"U+{ord(cp):04X}. That glyph is Claude Code's question "
                     "chip, NOT this repo's selection mark — restore it. See "
                     "t1638."),
            )

    def test_the_detector_actually_fires_on_a_captured_chip(self):
        """Pin the behaviour, not just the pattern text: a refactor could keep
        the codepoint in a comment-like position and still stop matching."""
        import workflow_phase

        self.assertTrue(workflow_phase._QUESTION_HEADER_RE.match("☐ Approach"))
        self.assertTrue(workflow_phase._QUESTION_HEADER_RE.match("  ☑ Glyph pair"))
        self.assertIsNone(workflow_phase._QUESTION_HEADER_RE.match("☐"))


if __name__ == "__main__":
    unittest.main()
