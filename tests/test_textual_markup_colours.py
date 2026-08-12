"""Guard: no silently-inert style token in Textual markup (t1453).

Textual's markup parser resolves **CSS colour names only**. It does not know
Rich's xterm palette names (`dodger_blue1`, `bright_cyan`, `medium_purple1`) or
Rich's spellings of style keywords (`strikethrough` vs Textual's `strike`). An
unknown token does **not** raise: ``textual/widget.py`` does
``try: return VisualStyle.parse(style) / except Exception: return NULL_STYLE``,
so the span keeps the unresolved string verbatim and the compositor paints the
widget's default foreground, dropping every attribute in that span.

That verbatim span is why the defect class is invisible to the repo's usual
colour tier: ``render().spans`` assertions all pass while the pixel is wrong.
Four styles shipped inert for months before t1453 (the DONE badge in both
monitors, two in the TUI switcher, one disabled-row style in brainstorm).

Rules A and B guard a token's style *vocabulary*. Rule C (t1486) guards markup
*structure* — a closing tag that matches no opening tag. That is a different
failure mode: it does not go inert, it raises ``MarkupError`` and takes the
compositor down. Two shipped that way (both GitLab indicators on the board),
reachable from any task whose ``issue:`` frontmatter points at a GitLab host.

Scope
-----
Three rules over ``.aitask-scripts/**/*.py`` and ``tests/**/*.py``, all AST-based
(a text grep would flag colour names appearing in comments and prose):

- **Rule A — bracketed markup tokens.** Oracle: ``textual.markup.parse_style``,
  Textual's own decision procedure. No vocabulary to maintain, and it tracks
  Textual version by version. Catches Rich-only names *and* plain typos
  (``[bold blu]``, ``[bodl cyan]``, ``[bold $acent]``).
- **Rule B — bare style strings.** Oracle: the Rich-only name blocklist. Catches
  a style assembled at runtime, where the tag itself is dynamic
  (``style = "bright_green"`` ... ``f"[{style}]"``).
- **Rule C — tag pairing.** Oracle: ``textual.content.Content.from_markup``,
  again Textual's own parser. Catches ``[#e24329]GL[/e24329]`` — a closing tag
  that names something no opening tag opened.

**Why two oracles for A/B.** A bracketed token carries a syntactic marker of
intent, so it can be handed to the exact oracle. A bare string has no such marker
— running ``parse_style`` over every short string produces 44 prose false
positives in this repo alone (``'not found'``, ``'Sync on refresh'``,
``'Monitor not ready'``). The conservative blocklist is what keeps Rule B silent
on prose.

Rule C's unit and gate
----------------------
The scanned unit is the **whole markup expression**, not the individual
``ast.Constant``: an f-string is reconstructed from its literal parts with
``_PLACEHOLDER_STYLE`` standing in for each interpolation, and its sub-nodes are
not scanned separately. Without that, ``f"[bold]{n}[/bold] [dim]("`` reads as a
mismatched close, because the AST splits it into fragments (3 false positives
measured: ``settings_app.py``, ``stats/panes/overview.py``,
``stats/panes/pipeline.py``).

An expression is scanned only when it carries **both** a *named* closing tag
(``[/x]``, not the auto-close ``[/]``) **and** ≥1 Rule-A *candidate* opening tag.
The first requirement drops the bare-``[/]`` fragment noise — a ``[/]`` with
nothing to close is how a runtime-assembled string legitimately looks in
isolation. The second drops CLI usage grammars (``create <handle>
[backend=<name>]``), protocol docs, and concern-parser fixtures. Measured over
the scanned tree: no gate at all → 61 findings, 2 real; gate but per-constant →
5 findings, 2 real; gate + reconstruction → 2 findings, 2 real.

What Rule C reaches, probed rather than assumed (the "missed" rows are pinned by
``ScannerDiscriminationTests`` too, so this table cannot drift from the code)::

    "[#e24329]GL[/e24329]"          caught   (the shipped defect)
    f"[{color}]GL[/e24329]"         caught   (placeholder supplies the open)
    f"[{color}]GL[/color]"          caught   (close names the variable)
    f"[bold]{n}[/bold] [dim]("      quiet    (correct: reconstruction)
    ")[/dim]"                       quiet    (correct: a fragment)
    "[bold]" + name + "[/bolt]"     MISSED   (assembled across expressions)
    "[@click=app.foo]x[/bolt]"      MISSED   (action-link open)
    f"[{a}]x[/{b}]"                 MISSED   (both names dynamic)
    "  [bold yellow][AUTO][/]"      MISSED   (literal-bracket class)

Not in scope (each for a stated reason, not by oversight):

- **Markup assembled across expressions or statements** (``"[bold]" + x``, a
  variable holding the open tag). The scanned unit is one expression; joining
  them needs dataflow analysis. Repo instances of a tag pair split that way: 1
  (``monitor/desync_summary.py``, and it is correct).
- **Action-link opening tags** (``[@click=…]``). ``_is_candidate`` rejects
  ``@``-prefixed tokens deliberately — see
  ``test_prose_in_brackets_is_not_a_finding`` — so a bad close paired only with
  one of those is invisible. Real ``[@click=…]`` markup sites in the repo: 0.
- **Both tag names dynamic** (``f"[{a}]x[/{b}]"``) — the placeholder makes them
  agree. Same undecidability as fully-dynamic tags below.
- **The literal-bracket class** — text meant literally that Textual eats as a
  tag (``[AUTO]``, ``[live]``, ``[raw]``; t1486 defects 2 and 3). These are
  *syntactically valid* unknown tags, statically indistinguishable from an
  intentional dynamic style, so no scan can separate them from intent. The
  answer is the escaping convention (``\\[``, as at ``tui_switcher.py`` and
  ``codebrowser/history_list.py``) plus behavioural pins: the three fixed sites
  are held by ``tests/test_textual_markup_structure.py``, which asserts the
  rendered plain text through the live widget.

- **Textual CSS / ``DEFAULT_CSS`` / ``.tcss``** — a bad colour there raises
  ``StylesheetParseError`` at app construction. Already fails loud; every TUI
  smoke test catches it.
- **Fully dynamic tags** (``f"[{x}]"``) — undecidable statically. Rule B is the
  compensating control: it pins the *value*. See
  ``monitor_shared.format_state_dot`` / ``format_shadow_glyph`` for the shape.
- **Colour names from JSON/YAML config** — ``lib/board_columns.py``'s
  ``_COLOR_RE`` deliberately accepts colour *names* such as ``bright_blue``.
  ``monitor_shared._safe_column_color`` is the runtime answer for those; all
  shipped values are hex today.
- **Names both libraries parse to *different* colours** (``purple``, ``orchid``,
  ``tan``, ``violet``; Rich ``purple`` is ``#af00ff``, CSS ``#800080``). Wrong
  shade, but not *inert*, so not this defect class.
- **Docstrings**, which are never rendered. Excluding them is what lets the
  monitor tests keep naming ``[bold medium_purple1]`` in prose as the record of
  the original defect.

Run: python3 tests/test_textual_markup_colours.py
"""

from __future__ import annotations

import ast
import re
import sys
import textwrap
import unittest
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".aitask-scripts"
TESTS_DIR = REPO_ROOT / "tests"

# Imported at module scope, deliberately: these are Textual internals, and an
# upstream rename must surface as a loud ImportError rather than let the guard
# degrade into a vacuously-green scan (t1453).
from rich.color import ANSI_COLOR_NAMES  # noqa: E402
from textual.color import Color  # noqa: E402
from textual.content import Content  # noqa: E402
from textual.markup import STYLES, parse_style  # noqa: E402
from textual.theme import BUILTIN_THEMES  # noqa: E402

#: Design-token variables (`$accent`, ...) resolved from a real theme. Without
#: these, `parse_style` consults the non-existent active app and every
#: `$variable` raises UnresolvedVariableError — 9 false positives in brainstorm.
THEME_VARIABLES = BUILTIN_THEMES["textual-dark"].to_color_system().generate()

def _parses(name: str) -> bool:
    """Whether Textual's colour parser accepts *name*."""
    try:
        Color.parse(name)
    except Exception:
        return False
    return True


#: Rich palette names Textual rejects — the vocabulary of this defect class.
#: Derived, not hand-listed, so it tracks both libraries. 223 of Rich's 235.
RICH_ONLY = frozenset(n for n in ANSI_COLOR_NAMES if not _parses(n))

#: Attribute keywords. These make a token a *candidate*, because they appear
#: only in style position.
STYLE_KEYWORDS = frozenset(STYLES)

#: Modifiers that are legal inside a style token but must NOT by themselves make
#: one a candidate: `not` and `on` are ordinary English words, and treating them
#: as triggers turns `[not a marker]` into a finding.
MODIFIERS = frozenset({"on", "not", "auto", "link"})

# Single-letter abbreviations (b, i, d, u, ...) are deliberately absent from both
# sets above. They are legal Textual markup but nobody in this repo uses them,
# and admitting them makes `[a All | l Locked]`, `[press b for full text]`,
# `[a, b]` and `[i - 2]` into findings.

#: An opening tag, skipping backslash-escaped brackets (`\\[Up/Down]` is a
#: literal bracket, not a tag).
_TOKEN_RE = re.compile(r"(?<!\\)\[([^\[\]\n]*)\]")
#: Every word in a style token has this shape.
_WORD_RE = re.compile(r"^[A-Za-z_$#][A-Za-z0-9_$#%.\-]*$")
#: A NAMED closing tag (Rule C). The auto-close `[/]` is excluded on purpose:
#: in isolation it is the normal shape of a runtime-assembled fragment, and
#: admitting it makes every such fragment a finding.
_CLOSE_RE = re.compile(r"(?<!\\)\[/([^\[\]\n]+)\]")
#: Stands in for an f-string interpolation when Rule C reconstructs an
#: expression. It must be a valid style so `[{color}]` reconstructs to a real
#: opening tag; `red` is the shortest such name.
_PLACEHOLDER_STYLE = "red"

REMEDIES = textwrap.dedent(
    """
    A style token that Textual cannot parse is SILENTLY INERT: the span keeps
    the unresolved string (so render().spans assertions still pass) while the
    compositor paints the default foreground and drops bold/dim/strike.

    To fix:
      * Rich xterm colour name  -> use a CSS name or a hex literal.
        dodger_blue1 -> #1e90ff   bright_cyan -> cyan   bright_green -> #00ff00
        Prefer hex where the exact shade matters, and record why at the call
        site (see monitor_shared.STATE_STYLE_DONE).
      * Rich keyword spelling   -> Textual's is `strike`, not `strikethrough`.
      * A typo                  -> the error message suggests the near match.

    Do NOT reach for `ansi_<name>`: it parses, but carries an ANSI flag that
    remaps through the *theme's* palette at render time, so the painted colour
    varies by theme and cannot be pinned.

    If a flagged site is genuinely consumed by RICH rather than Textual (a Rich
    Style object, or a Text nested inside a Rich container such as a Table),
    add it to RICH_RENDERER_WAIVERS below with a reason naming the consumer as
    file:function and a pinned_by= composited test.
    """
).strip()

STRUCTURE_REMEDIES = textwrap.dedent(
    """
    A closing tag that matches no open tag is NOT silently inert: Textual raises
    MarkupError and the compositor crashes on the path that renders it. This is
    the t1486 defect class.

    To fix:
      * Mismatched close  -> close with the auto-close `[/]`, or repeat the
        opening tag EXACTLY. `[#e24329]x[/e24329]` is wrong: the closing tag
        drops the `#`, so it names a tag that was never opened.
      * Literal bracket   -> if the bracket is text, escape it as `\\[`. See
        tui_switcher.py and codebrowser/history_list.py. Note this rule does
        NOT catch that case (see "Not in scope" in the module docstring) —
        it is listed here because it is the other half of the same fix.

    A finding here is reported against the RECONSTRUCTED expression, with each
    f-string interpolation shown as `{_PLACEHOLDER_STYLE}`, so the text may not
    match the source verbatim. The file and line locate the real site.
    """
).strip()


# ---------------------------------------------------------------------------
# Waivers (Rule B only — Rule A currently needs none)
# ---------------------------------------------------------------------------
# Keyed (repo-relative path, enclosing qualname or "MODULE", token). Not per
# line: line numbers drift on every edit above the site. Not per file: that
# would blanket-exempt a file that later grows a real Textual markup site.
#
# Each reason must name the consumer as file:function AND a pinned_by= test, so
# the claim is checkable rather than prose. That matters here specifically: the
# fact that makes code_viewer correct lives in a DIFFERENT file, so a refactor
# could invalidate the reason without touching the waived file.
RICH_RENDERER_WAIVERS: dict[tuple[str, str, str], str] = {
    (".aitask-scripts/codebrowser/code_viewer.py", "MODULE", "bright_cyan"): (
        "Rich-consumed: an ANNOTATION_COLORS entry, applied as rich Text cell "
        "style in code_viewer.py:_build_annotation_gutter and rendered inside "
        "the boxless rich.table.Table built by "
        "lib/numbered_source_view.py:_rebuild_display, so Rich resolves it and "
        "the Textual parser never sees it. "
        "pinned_by=test_rich_table_cells_resolve_rich_only_names"
    ),
    (".aitask-scripts/codebrowser/code_viewer.py", "MODULE", "bright_green"): (
        "Rich-consumed: second ANNOTATION_COLORS entry on the same path as "
        "bright_cyan above (code_viewer.py:_build_annotation_gutter into "
        "lib/numbered_source_view.py:_rebuild_display). "
        "pinned_by=test_rich_table_cells_resolve_rich_only_names"
    ),
    (".aitask-scripts/codebrowser/code_viewer.py", "MODULE", "grey27"): (
        "Rich-consumed: CURSOR_STYLE is a rich.style.Style object, which "
        "resolves the name eagerly at construction (it would raise here if "
        "wrong) and is returned from code_viewer.py:_row_style. "
        "pinned_by=test_rich_style_objects_resolve_rich_only_names"
    ),
    (".aitask-scripts/codebrowser/code_viewer.py", "MODULE", "dark_blue"): (
        "Rich-consumed: SELECTION_STYLE is a rich.style.Style object on the "
        "same path as grey27 above (code_viewer.py:_row_style). "
        "pinned_by=test_rich_style_objects_resolve_rich_only_names"
    ),
    ("tests/test_board_columns_seam.py", "ColorPolicyTests", "bright_blue"): (
        "Not markup: a deliberate fixture value proving the validator "
        "lib/board_columns.py:_validate_color accepts colour NAMES as well as "
        "hex. Never rendered as markup; the runtime answer for a named column "
        "colour is monitor_shared.py:_safe_column_color. "
        "pinned_by=test_board_columns_seam"
    ),
}

# ---------------------------------------------------------------------------
# Modules excluded wholesale, for the same reason docstrings are: every
# occurrence in them is *data about* this defect class, not markup that renders.
# Kept to an explicit, tiny set with reasons — a file-level exclusion is
# otherwise exactly the blanket exemption the (path, qualname, token) waiver key
# exists to avoid.
SELF_REFERENTIAL_MODULES: dict[str, str] = {
    "tests/test_textual_markup_colours.py": (
        "This guard itself. Its waiver reasons and negative-control fixtures "
        "quote the bad tokens verbatim; scanning them would make the scanner "
        "its own largest finding."
    ),
    "tests/test_markup_colour_contract.py": (
        "Ratifies the chosen styles and asserts the OLD inert spellings are "
        "absent, so it necessarily names them (e.g. `strikethrough`)."
    ),
}


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------
class Finding(NamedTuple):
    """One unparsable token.

    ``key`` is the waiver identity — path, enclosing qualname, token. ``line``
    is diagnostics only and deliberately NOT part of it: line numbers drift on
    every edit above the site, and a waiver that goes stale on an unrelated
    commit trains people to re-bless it without reading.
    """

    relpath: str
    qualname: str
    token: str
    line: int

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.relpath, self.qualname, self.token)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"{self.relpath}:{self.line} [{self.token}] in {self.qualname}"


def _is_style_word(word: str) -> bool:
    """A word that can only be style vocabulary."""
    if word in STYLE_KEYWORDS or word.startswith(("#", "$")):
        return True
    return _parses(word)


def _is_candidate(token: str) -> bool:
    """Whether a bracketed token is plausibly a style tag rather than prose.

    Requires every word to be word-shaped AND at least one word to be
    *triggering* — style vocabulary or a known Rich-only colour. Without the
    triggering requirement, prose like ``[applink]``, ``[READ ONLY]``, ``[str]``
    and ``[enter details]`` floods in (39 false positives, measured).
    Modifiers (`on`, `not`) are legal but never trigger.
    """
    if not token or token[0] in "/@":
        return False
    words = token.split()
    if not words or not all(_WORD_RE.match(w) for w in words):
        return False
    return any(_is_style_word(w) or w in RICH_ONLY for w in words)


def _bare_style_offenders(text: str) -> list[str]:
    """Rich-only names in a whole string that is entirely style vocabulary.

    No word cap: measured with caps of 4, 8 and unbounded, the result over this
    repo is identical. All the discriminating power is in the "every other word
    is style vocabulary" test — any prose word fails it immediately.
    """
    words = text.split()
    if not words:
        return []
    offenders = [w for w in words if w in RICH_ONLY]
    if not offenders:
        return []
    for word in words:
        if word in RICH_ONLY or word in STYLE_KEYWORDS or word in MODIFIERS:
            continue
        if not _is_style_word(word):
            return []
    return offenders


def _string_constants(tree: ast.AST) -> list[tuple[ast.Constant, str]]:
    """Every string constant outside a docstring, with its enclosing qualname."""
    docstrings: set[int] = set()
    qualname_of: dict[int, str] = {}

    def walk(node: ast.AST, prefix: str) -> None:
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                docstrings.add(id(node.body[0].value))
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                child_prefix = f"{prefix}.{child.name}" if prefix else child.name
                walk(child, child_prefix)
            else:
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        qualname_of.setdefault(id(sub), prefix or "MODULE")
                walk_nested_defs(child, prefix)

    def walk_nested_defs(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                child_prefix = f"{prefix}.{child.name}" if prefix else child.name
                walk(child, child_prefix)
            else:
                walk_nested_defs(child, prefix)

    walk(tree, "")

    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            out.append((node, qualname_of.get(id(node), "MODULE")))
    return out


def scan_source(source: str, relpath: str) -> tuple[list[Finding], int]:
    """Scan one module. Returns (findings, candidate_token_count).

    A SyntaxError is raised, never skipped: a file the scanner cannot parse is
    a file it is not guarding.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise AssertionError(f"{relpath}: could not parse ({exc})") from exc

    findings: list[Finding] = []
    candidates = 0
    for node, qualname in _string_constants(tree):
        text = node.value
        for match in _TOKEN_RE.finditer(text):
            token = match.group(1)
            if not _is_candidate(token):
                continue
            candidates += 1
            try:
                parse_style(token, variables=THEME_VARIABLES)
            except Exception:
                findings.append(Finding(relpath, qualname, token, node.lineno))
        for offender in _bare_style_offenders(text):
            findings.append(Finding(relpath, qualname, offender, node.lineno))
    return findings, candidates


def scan_tree(root: Path) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    candidates = 0
    for path in sorted(root.rglob("*.py")):
        relpath = path.relative_to(REPO_ROOT).as_posix()
        if relpath in SELF_REFERENTIAL_MODULES:
            continue
        found, count = scan_source(path.read_text(encoding="utf-8"), relpath)
        findings.extend(found)
        candidates += count
    return findings, candidates


def scan_repo() -> tuple[list[Finding], int]:
    findings, candidates = scan_tree(SCRIPTS_DIR)
    more, count = scan_tree(TESTS_DIR)
    return findings + more, candidates + count


# ---------------------------------------------------------------------------
# Rule C — tag pairing (t1486)
#
# Kept as a SEPARATE scanner from scan_source() above, deliberately. Rules A/B
# emit a (path, qualname, token) Finding whose key is the RICH_RENDERER_WAIVERS
# identity — "this token is consumed by Rich, not Textual". That waiver has no
# meaning for a broken tag pair: no renderer accepts one. Merging the two would
# make a structural finding waivable by a Rule-B escape hatch.
# ---------------------------------------------------------------------------
class StructureFinding(NamedTuple):
    """One expression whose markup does not parse.

    ``markup`` is the RECONSTRUCTED text (interpolations replaced), not the
    source slice — see STRUCTURE_REMEDIES.
    """

    relpath: str
    markup: str
    error: str
    line: int

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"{self.relpath}:{self.line} {self.markup!r} -> {self.error}"


def _markup_expressions(tree: ast.AST) -> list[tuple[ast.AST, str]]:
    """Every top-level string expression, f-strings reconstructed whole.

    A JoinedStr is returned as one entry with `_PLACEHOLDER_STYLE` substituted
    for each interpolation, and its component nodes are NOT returned separately
    — scanning those fragments is what produces the false positives the module
    docstring records. Docstrings are excluded, as for Rules A/B.
    """
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))

    inner: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for sub in ast.walk(node):
                if sub is not node:
                    inner.add(id(sub))

    out: list[tuple[ast.AST, str]] = []
    for node in ast.walk(tree):
        if id(node) in inner or id(node) in docstrings:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node, node.value))
        elif isinstance(node, ast.JoinedStr):
            parts = [
                value.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
                else _PLACEHOLDER_STYLE
                for value in node.values
            ]
            out.append((node, "".join(parts)))
    return out


def _is_markup_expression(text: str) -> bool:
    """The Rule C gate: a named close AND a Rule-A candidate open."""
    if not _CLOSE_RE.search(text):
        return False
    return any(_is_candidate(m.group(1)) for m in _TOKEN_RE.finditer(text))


def scan_source_structure(
    source: str, relpath: str
) -> tuple[list[StructureFinding], int]:
    """Scan one module for tag-pairing defects. Returns (findings, gated)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise AssertionError(f"{relpath}: could not parse ({exc})") from exc

    findings: list[StructureFinding] = []
    gated = 0
    for node, text in _markup_expressions(tree):
        if not _is_markup_expression(text):
            continue
        gated += 1
        try:
            Content.from_markup(text)
        except Exception as exc:
            findings.append(
                StructureFinding(
                    relpath, text, f"{type(exc).__name__}: {exc}", node.lineno
                )
            )
    return findings, gated


def scan_repo_structure() -> tuple[list[StructureFinding], int]:
    findings: list[StructureFinding] = []
    gated = 0
    for root in (SCRIPTS_DIR, TESTS_DIR):
        for path in sorted(root.rglob("*.py")):
            relpath = path.relative_to(REPO_ROOT).as_posix()
            if relpath in SELF_REFERENTIAL_MODULES:
                continue
            found, count = scan_source_structure(
                path.read_text(encoding="utf-8"), relpath
            )
            findings.extend(found)
            gated += count
    return findings, gated


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------
class MarkupColourScanTests(unittest.TestCase):
    """The live-tree scan."""

    @classmethod
    def setUpClass(cls):
        cls.findings, cls.candidates = scan_repo()

    def test_no_unparsable_style_token_outside_the_waivers(self):
        unwaived = [f for f in self.findings if f.key not in RICH_RENDERER_WAIVERS]
        self.assertEqual(
            [], unwaived,
            "Textual cannot parse these style tokens:\n"
            + "\n".join(f"  {f!r}" for f in unwaived)
            + "\n\n" + REMEDIES,
        )

    def test_the_scan_is_not_vacuous(self):
        """A scanner that stops finding candidates passes for the wrong reason."""
        self.assertGreater(
            self.candidates, 300,
            f"only {self.candidates} candidate tokens found across the tree — "
            "the scanner has probably stopped recognising markup",
        )

    def test_the_rich_only_vocabulary_is_populated(self):
        self.assertGreater(len(RICH_ONLY), 200)
        self.assertIn("bright_cyan", RICH_ONLY)
        self.assertIn("dodger_blue1", RICH_ONLY)

    def test_rule_c_is_not_reachable_through_the_rule_b_waivers(self):
        """The two finding types must not share a waiver identity.

        RICH_RENDERER_WAIVERS means "Rich consumes this token, not Textual".
        No renderer accepts a broken tag pair, so a structural finding must
        never be silenceable that way — hence the separate scanner.
        """
        self.assertFalse(
            hasattr(StructureFinding, "key"),
            "StructureFinding must not grow a waiver key",
        )

    def test_no_rich_only_name_is_a_bare_alphabetic_word(self):
        """The invariant that makes Rule B safe to run over arbitrary strings.

        Every Rich-only name carries an underscore or a digit, so no English
        word can collide with one. A future `rich` release could break this
        silently, at which point Rule B would start flagging prose.
        """
        self.assertEqual([], sorted(n for n in RICH_ONLY if n.isalpha()))


class MarkupStructureScanTests(unittest.TestCase):
    """Rule C over the live tree. No waiver list — see the scanner's comment."""

    @classmethod
    def setUpClass(cls):
        cls.findings, cls.gated = scan_repo_structure()

    def test_every_closing_tag_matches_an_open_tag(self):
        self.assertEqual(
            [], self.findings,
            "Textual cannot parse this markup:\n"
            + "\n".join(f"  {f!r}" for f in self.findings)
            + "\n\n" + STRUCTURE_REMEDIES,
        )

    def test_the_structure_scan_is_not_vacuous(self):
        """A gate that stops matching passes for the wrong reason.

        171 expressions were gated in when Rule C landed. The floor is set well
        below that so ordinary churn does not trip it, but a gate that breaks
        outright (a regex that never matches, a reconstruction that returns
        nothing) drops to ~0 and fails here rather than reporting all-clear.
        """
        self.assertGreater(
            self.gated, 100,
            f"only {self.gated} markup expressions reached the oracle — "
            "the Rule C gate has probably stopped recognising markup",
        )


class WaiverHygieneTests(unittest.TestCase):
    """The waiver list must not rot into a silent exemption."""

    @classmethod
    def setUpClass(cls):
        cls.findings, _ = scan_repo()

    def test_every_waiver_still_matches_a_live_site(self):
        """A waiver matching nothing is a dead exemption, not a harmless one.

        Either the site moved (and the waiver is now a blind spot wherever it
        went) or it was fixed (and the waiver is noise). Both need a human.
        """
        live = {f.key for f in self.findings}
        stale = sorted(k for k in RICH_RENDERER_WAIVERS if k not in live)
        self.assertEqual(
            [], stale,
            "these waivers no longer match any scanned site — remove them or "
            f"retarget them:\n  {stale}",
        )

    def test_every_excluded_module_exists_and_carries_a_reason(self):
        """A whole-file exclusion is the blunt instrument; keep it honest.

        An exclusion naming a file that no longer exists is a silent blind spot
        waiting for someone to recreate that path.
        """
        for relpath, reason in SELF_REFERENTIAL_MODULES.items():
            with self.subTest(module=relpath):
                self.assertTrue(
                    (REPO_ROOT / relpath).is_file(),
                    f"{relpath}: excluded module does not exist",
                )
                self.assertGreater(len(reason), 60, f"{relpath}: reason is a stub")

    def test_the_exclusion_list_stays_small(self):
        """Guards against the exclusion list becoming the escape hatch."""
        self.assertLessEqual(
            len(SELF_REFERENTIAL_MODULES), 3,
            "whole-file exclusions are for modules ABOUT this defect class; "
            "anything else belongs in RICH_RENDERER_WAIVERS with a per-token "
            "reason",
        )

    def test_every_waiver_carries_a_reason(self):
        for key, reason in RICH_RENDERER_WAIVERS.items():
            with self.subTest(key=key):
                self.assertGreater(
                    len(reason), 60,
                    f"{key}: a waiver needs a written justification, not a stub",
                )

    def test_every_waiver_names_its_consumer_and_a_pinning_test(self):
        """Converts an unverifiable prose claim into a checkable one."""
        test_sources = "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(TESTS_DIR.rglob("*.py"))
        )
        for key, reason in RICH_RENDERER_WAIVERS.items():
            with self.subTest(key=key):
                self.assertIn(
                    ".py:", reason,
                    f"{key}: name the consumer as file:function",
                )
                match = re.search(r"pinned_by=([A-Za-z0-9_]+)", reason)
                self.assertIsNotNone(
                    match, f"{key}: reason must carry a pinned_by=<test name>"
                )
                self.assertIn(
                    match.group(1), test_sources,
                    f"{key}: pinned_by names {match.group(1)}, which no test defines",
                )


class OracleTests(unittest.TestCase):
    """The oracle itself must still discriminate.

    Without this, a Textual API change turns the whole guard vacuously green:
    an oracle that accepts everything reports no findings and looks like a pass.
    """

    def test_the_oracle_accepts_valid_tokens(self):
        for token in (
            "bold cyan", "bold #1e90ff", "#00ff00", "dim", "dim strike",
            "on #202020", "bold $accent", "not bold",
        ):
            with self.subTest(token=token):
                parse_style(token, variables=THEME_VARIABLES)

    def test_the_oracle_rejects_the_defect_class(self):
        for token in (
            "bold bright_cyan", "bright_green", "bold dodger_blue1",
            "dim strikethrough", "bold blu", "bodl cyan", "bold $acent",
        ):
            with self.subTest(token=token):
                with self.assertRaises(Exception):
                    parse_style(token, variables=THEME_VARIABLES)

    def test_theme_variables_are_populated(self):
        self.assertGreater(len(THEME_VARIABLES), 100)
        self.assertIn("accent", THEME_VARIABLES)


class ScannerDiscriminationTests(unittest.TestCase):
    """Negative controls over synthetic sources — never the live tree."""

    def _scan(self, source: str) -> list[Finding]:
        findings, _ = scan_source(textwrap.dedent(source), "synthetic.py")
        return findings

    def _tokens(self, source: str) -> list[str]:
        return [f.token for f in self._scan(source)]

    # --- must be caught -----------------------------------------------------

    def test_a_rich_only_markup_tag_is_caught(self):
        self.assertEqual(
            ["bold bright_cyan"], self._tokens('x = "[bold bright_cyan]hi[/]"')
        )

    def test_a_rich_keyword_spelling_is_caught(self):
        """brainstorm/widgets.py shipped this one inert for months."""
        self.assertEqual(
            ["dim strikethrough"], self._tokens('x = "[dim strikethrough]hi[/]"')
        )

    def test_a_misspelled_colour_is_caught(self):
        self.assertEqual(["bold blu"], self._tokens('x = "[bold blu]hi[/]"'))

    def test_a_transposed_keyword_is_caught(self):
        self.assertEqual(["bodl cyan"], self._tokens('x = "[bodl cyan]hi[/]"'))

    def test_an_unknown_design_token_is_caught(self):
        self.assertEqual(["bold $acent"], self._tokens('x = "[bold $acent]hi[/]"'))

    def test_implicit_concatenation_is_scanned_as_one_token(self):
        """Python folds adjacent literals, so the tag is never split."""
        self.assertEqual(
            ["bold bright_cyan"],
            self._tokens('x = ("[bold "\n     "bright_cyan]hi[/]")'),
        )

    def test_a_bare_rich_only_style_string_is_caught(self):
        self.assertEqual(["bright_green"], self._tokens('style = "bright_green"'))

    def test_a_long_bare_style_string_is_caught(self):
        """Pins the absence of a word cap as deliberate."""
        self.assertEqual(
            ["dark_blue"],
            self._tokens('style = "not blink bold underline on dark_blue"'),
        )

    # --- must NOT be findings ----------------------------------------------

    def test_valid_tags_are_not_findings(self):
        self.assertEqual([], self._tokens(
            '''
            a = "[bold cyan]x[/]"
            b = "[bold #1e90ff]x[/]"
            c = "[#00ff00]x[/]"
            d = "[bold $accent]x[/]"
            e = "[dim]x[/]"
            f = "[on #202020]x[/]"
            g = "[@click=go]x[/]"
            h = "[dim strike]x[/]"
            '''
        ))

    def test_prose_in_brackets_is_not_a_finding(self):
        """Every one of these is a real shape from this repo.

        Each becomes a false positive the moment single-letter style
        abbreviations are admitted to the candidate gate, which is what makes
        them controls rather than decoration.
        """
        self.assertEqual([], self._tokens(
            '''
            a = "[a All | l Locked | f Free | i In-Flight]"
            b = "[press b for full text]"
            c = "[a, b]"
            d = "[i - 2]"
            e = "[not a marker]"
            f = "[filtered] [READ ONLY] [UNAVAIL]"
            g = "value is [%s] and [%d]"
            h = "[applink] [registry] [enter details] [str]"
            '''
        ))

    def test_an_escaped_bracket_is_not_a_tag(self):
        """The real tui_switcher shape: `\\[` renders a literal bracket."""
        self.assertEqual([], self._tokens(
            r'''
            a = "[dim]\\[Up/Down] navigate[/]"
            b = "[bold cyan]\\[group][/]  "
            '''
        ))

    def test_a_closing_tag_is_not_a_tag(self):
        self.assertEqual([], self._tokens('x = "a[/red]b[/]c"'))

    def test_a_docstring_is_not_scanned(self):
        """Docstrings are never rendered; the defect record lives in them."""
        self.assertEqual([], self._tokens('"""Sets [bold medium_purple1] text."""'))

    def test_a_comment_is_not_scanned(self):
        self.assertEqual([], self._tokens('# see [bold medium_purple1]\nx = 1'))

    def test_prose_mentioning_a_colour_name_is_not_a_bare_style_string(self):
        self.assertEqual([], self._tokens('msg = "Uses bright_cyan for hints"'))

    # --- scope boundary -----------------------------------------------------

    def test_a_dynamic_tag_is_out_of_scope_but_rule_b_covers_its_value(self):
        """Pins the hole and its compensating control together.

        The tag `f"[{style}]"` is undecidable; the value it interpolates is not.
        """
        findings = self._scan(
            '''
            style = "bright_green"
            text = f"[{style}]dot[/]"
            '''
        )
        self.assertEqual(["bright_green"], [f.token for f in findings])
        self.assertEqual(1, len(findings), "the dynamic tag must not also fire")

    def test_an_unparsable_file_raises_rather_than_being_skipped(self):
        with self.assertRaises(AssertionError):
            scan_source("def broken(:\n", "synthetic.py")

    # --- structural ---------------------------------------------------------

    def test_findings_carry_the_enclosing_qualname(self):
        """The waiver key needs it, so it must actually be populated."""
        findings = self._scan(
            '''
            class Row:
                def render(self):
                    return "[bold bright_cyan]x[/]"
            '''
        )
        self.assertEqual(["Row.render"], [f.qualname for f in findings])


class StructureScannerDiscriminationTests(unittest.TestCase):
    """Rule C's boundary, one test per row of the docstring's coverage table.

    The "must NOT be caught" half matters as much as the other: each of those
    is a documented gap or a measured false-positive shape, and a test that
    starts failing there means the gate moved and the docstring is now lying.
    """

    def _scan(self, source: str) -> list[StructureFinding]:
        findings, _ = scan_source_structure(textwrap.dedent(source), "synthetic.py")
        return findings

    def _gated(self, source: str) -> int:
        _, gated = scan_source_structure(textwrap.dedent(source), "synthetic.py")
        return gated

    # --- must be caught -----------------------------------------------------

    def test_the_shipped_board_defect_is_caught(self):
        """aitask_board.py:_issue_indicator, verbatim as it shipped."""
        findings = self._scan('x = "[#e24329]GL[/e24329]"')
        self.assertEqual(1, len(findings), findings)
        self.assertIn("does not match any open tag", findings[0].error)

    def test_a_dynamic_open_with_a_mismatched_named_close_is_caught(self):
        """The placeholder supplies the opening tag the AST cannot see."""
        findings = self._scan('x = f"[{color}]GL[/e24329]"')
        self.assertEqual(1, len(findings), findings)

    def test_a_close_naming_the_variable_rather_than_its_value_is_caught(self):
        """`f"[{color}]x[/color]"` closes a tag named `color`, never opened."""
        self.assertEqual(1, len(self._scan('x = f"[{color}]GL[/color]"')))

    def test_nesting_is_understood_and_valid_nesting_is_quiet(self):
        self.assertEqual([], self._scan('x = "[bold][red]a[/red][/bold]"'))

    # --- must NOT be caught (false-positive shapes) -------------------------

    def test_an_fstring_fragment_is_not_a_finding(self):
        """The reconstruction's reason for existing.

        Per-constant scanning splits this into `"[bold]"`, `"[/bold] [dim]("`
        and reads the second as an unmatched close — 3 such sites in the tree.
        """
        source = 'x = f"[bold]{n}[/bold] [dim]("'
        self.assertEqual([], self._scan(source))
        self.assertEqual(1, self._gated(source), "must be scanned, not skipped")

    def test_a_named_close_without_a_candidate_open_is_not_scanned(self):
        """`")[/dim]"` is a fragment of a runtime-assembled string."""
        self.assertEqual(0, self._gated('x = ")[/dim]"'))

    def test_a_bare_auto_close_is_not_scanned(self):
        """`[/]` alone is how half the repo's fragments legitimately look."""
        self.assertEqual(0, self._gated('x = "Backlog [/]"'))

    def test_a_cli_usage_grammar_is_not_scanned(self):
        """lib/artifact_manifest.py shape: brackets, but not markup."""
        self.assertEqual(0, self._gated('x = "create <handle> [backend=<name>]"'))

    def test_a_docstring_is_not_scanned(self):
        self.assertEqual(0, self._gated('"""Renders [#e24329]GL[/e24329] here."""'))

    # --- documented gaps ----------------------------------------------------
    #
    # Each asserts BOTH that Rule C is quiet AND why: either the expression
    # never reaches the oracle (gated out) or it reaches it and parses. Without
    # the second half a "not caught" assertion could pass because the fixture
    # is malformed rather than because the gap is real.

    def test_gap_markup_assembled_across_expressions(self):
        source = 'x = "[bold]" + name + "[/bolt]"'
        self.assertEqual([], self._scan(source))
        self.assertEqual(0, self._gated(source), "neither half carries both tags")

    def test_gap_action_link_opening_tag(self):
        source = 'x = "[@click=app.foo]x[/bolt]"'
        self.assertEqual([], self._scan(source))
        self.assertEqual(
            0, self._gated(source), "_is_candidate rejects @-prefixed tokens"
        )
        with self.assertRaises(Exception):
            Content.from_markup("[@click=app.foo]x[/bolt]")

    def test_gap_both_tag_names_dynamic(self):
        source = 'x = f"[{a}]x[/{b}]"'
        self.assertEqual([], self._scan(source))
        self.assertEqual(1, self._gated(source), "it IS scanned")
        # ...and it is quiet because the placeholder makes the names agree.
        Content.from_markup(f"[{_PLACEHOLDER_STYLE}]x[/{_PLACEHOLDER_STYLE}]")

    def test_gap_the_literal_bracket_class(self):
        """t1486 defects 2 and 3 are invisible to any static rule.

        `[AUTO]` is a syntactically valid unknown tag. Textual drops it and
        renders nothing, without raising — so the oracle cannot object, and
        the only evidence is the rendered text. That is what
        tests/test_textual_markup_structure.py exists to assert.
        """
        source = 'x = "  [bold yellow][AUTO][/]"'
        self.assertEqual([], self._scan(source))
        self.assertEqual("  ", Content.from_markup("  [bold yellow][AUTO][/]").plain)

    # --- structural ---------------------------------------------------------

    def test_an_unparsable_file_raises_rather_than_being_skipped(self):
        with self.assertRaises(AssertionError):
            scan_source_structure("def broken(:\n", "synthetic.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
