"""Parser for structured sections in brainstorm proposals and plans.

Extracts sections delimited by HTML comment markers:
    <!-- section: name [dimensions: dim1, dim2] -->
    ... content ...
    <!-- /section: name -->
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .brainstorm_schemas import DIMENSION_PREFIXES, is_dimension_field

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ContentSection:
    """A named section extracted from a proposal or plan.

    Sections may nest: a catch-all wrapper (e.g. ``components``) can contain
    leaf subsections (e.g. ``component_auth``). ``depth`` is 0 for a top-level
    section and increases by one per nesting level; ``parent`` is the enclosing
    section's name (``None`` at the top level). The fields default so callers
    constructing a flat section by keyword stay source-compatible.
    """

    name: str
    dimensions: list[str]
    content: str
    start_line: int  # 1-based
    end_line: int    # 1-based
    depth: int = 0
    parent: str | None = None


@dataclass
class ParsedContent:
    """Result of parsing a markdown document for section markers."""

    sections: list[ContentSection]
    preamble: str
    epilogue: str
    raw: str


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_OPEN_RE = re.compile(
    r"<!--\s*section:\s*(\S+)(?:\s*\[dimensions?:\s*([^\]]+)\])?\s*-->"
)
_CLOSE_RE = re.compile(r"<!--\s*/section:\s*(\S+)\s*-->")


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------


@dataclass
class _OpenFrame:
    """A section whose open marker has been seen but not yet closed."""

    name: str
    dimensions: list[str]
    start_line: int
    content: list[str]
    depth: int
    parent: str | None


def parse_sections(text: str) -> ParsedContent:
    """Parse *text* and return structured :class:`ParsedContent`.

    Section markers may **nest**: a wrapper section can contain leaf
    subsections, each of which becomes its own :class:`ContentSection` with a
    ``depth``/``parent`` tag. A frame stack tracks the open sections; content
    lines accumulate into the innermost open frame only (a wrapper's ``content``
    therefore excludes its subsections' bodies, keeping its first heading the
    one used for navigation). Completed sections are returned in document
    (open-marker) order.
    """
    lines = text.split("\n")
    sections: list[ContentSection] = []
    preamble_lines: list[str] = []
    epilogue_lines: list[str] = []

    # Stack of open section frames (empty when outside any section).
    stack: list[_OpenFrame] = []
    last_close_idx: int = -1  # index of the last close-tag line

    for idx, line in enumerate(lines):
        lineno = idx + 1  # 1-based

        open_m = _OPEN_RE.search(line)
        if open_m:
            raw_dims = open_m.group(2)
            dims = (
                [d.strip() for d in raw_dims.split(",") if d.strip()]
                if raw_dims
                else []
            )
            stack.append(
                _OpenFrame(
                    name=open_m.group(1),
                    dimensions=dims,
                    start_line=lineno,
                    content=[],
                    depth=len(stack),
                    parent=stack[-1].name if stack else None,
                )
            )
            continue

        close_m = _CLOSE_RE.search(line)
        if close_m and stack and close_m.group(1) == stack[-1].name:
            frame = stack.pop()
            sections.append(
                ContentSection(
                    name=frame.name,
                    dimensions=frame.dimensions,
                    content="\n".join(frame.content),
                    start_line=frame.start_line,
                    end_line=lineno,
                    depth=frame.depth,
                    parent=frame.parent,
                )
            )
            last_close_idx = idx
            continue

        # Accumulate into the right bucket. A close marker that does not match
        # the innermost open frame (malformed / misordered) falls through here
        # and is treated as content; validate_sections() flags the imbalance.
        if stack:
            stack[-1].content.append(line)
        elif not sections and last_close_idx == -1:
            preamble_lines.append(line)
        else:
            epilogue_lines.append(line)

    # Sections complete in close order (children before parents); re-order by
    # start line so callers see them in document order.
    sections.sort(key=lambda s: s.start_line)

    return ParsedContent(
        sections=sections,
        preamble="\n".join(preamble_lines),
        epilogue="\n".join(epilogue_lines),
        raw=text,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_sections(
    parsed: ParsedContent, node_keys: list[str] | None = None
) -> list[str]:
    """Return a list of error messages (empty means valid).

    When *node_keys* (the node's real dimension keys) is provided, each non-glob
    dimension tag that does not match any real key is flagged. Glob tags
    (``component_*``) are always accepted — they are expanded at lookup time. The
    ``node_keys=None`` default preserves the prior, node-agnostic behavior.
    """
    errors: list[str] = []

    # Duplicate names.
    seen: set[str] = set()
    for sec in parsed.sections:
        if sec.name in seen:
            errors.append(f"Duplicate section name: {sec.name}")
        seen.add(sec.name)

    # Invalid dimension prefixes.
    for sec in parsed.sections:
        for dim in sec.dimensions:
            if not is_dimension_field(dim):
                errors.append(
                    f"Invalid dimension '{dim}' in section '{sec.name}': "
                    f"must start with one of {DIMENSION_PREFIXES}"
                )

    # Invented dimension tags — non-glob keys that match no real node key.
    if node_keys is not None:
        key_set = set(node_keys)
        for sec in parsed.sections:
            for dim in sec.dimensions:
                if (
                    is_dimension_field(dim)
                    and not dim.endswith("*")
                    and dim not in key_set
                ):
                    errors.append(
                        f"Section '{sec.name}' references unknown dimension "
                        f"key '{dim}'"
                    )

    # Unclosed sections — re-scan raw text for opens without matching closes.
    open_names: list[str] = [m.group(1) for m in _OPEN_RE.finditer(parsed.raw)]
    close_names: list[str] = [m.group(1) for m in _CLOSE_RE.finditer(parsed.raw)]
    close_set = set(close_names)
    for name in open_names:
        if name not in close_set:
            errors.append(f"Unclosed section: {name}")

    return errors


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def get_section_by_name(
    parsed: ParsedContent, name: str
) -> ContentSection | None:
    """Return the first section matching *name*, or ``None``."""
    for sec in parsed.sections:
        if sec.name == name:
            return sec
    return None


def dimension_matches_tag(dim_key: str, tag: str) -> bool:
    """Return True if real dimension *dim_key* is covered by a section *tag*.

    A section's ``[dimensions: ...]`` tag may be an exact key
    (``component_foo``) or a **prefix glob** (``component_*``). A glob matches
    any key sharing the literal prefix that precedes the trailing ``*``; an
    exact tag matches only an identical key. Purely string-based — no node data
    required.
    """
    if tag.endswith("*"):
        return dim_key.startswith(tag[:-1])
    return dim_key == tag


def get_sections_for_dimension(
    parsed: ParsedContent, dimension: str
) -> list[ContentSection]:
    """Return all sections linked to *dimension*.

    Section tags may be exact keys or prefix globs (e.g. ``component_*``); both
    are expanded via :func:`dimension_matches_tag`, so a dimension covered only
    by a glob section is still linked.
    """
    return [
        sec
        for sec in parsed.sections
        if any(dimension_matches_tag(dimension, t) for t in sec.dimensions)
    ]


def best_section_for_dimension(
    parsed: ParsedContent, dimension: str
) -> ContentSection | None:
    """Return the most-specific section linked to *dimension*, or ``None``.

    When a dimension is covered by both a wrapper (via a glob tag like
    ``component_*``) and its own leaf subsection (via an exact tag), navigation
    should land on the leaf. Ranking, best last: an **exact** tag match beats a
    glob-only match, then **deeper** nesting beats shallower. Ties keep the
    earliest section in document order (``max`` returns the first of equal keys).
    """
    matches = get_sections_for_dimension(parsed, dimension)
    if not matches:
        return None

    def rank(sec: ContentSection) -> tuple[bool, int]:
        exact = any(t == dimension for t in sec.dimensions)
        return (exact, sec.depth)

    return max(matches, key=rank)


def section_names(parsed: ParsedContent) -> list[str]:
    """Return the ordered list of section names."""
    return [sec.name for sec in parsed.sections]


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------


def format_section_header(
    name: str, dimensions: list[str] | None = None
) -> str:
    """Generate an opening section tag."""
    if dimensions:
        dims = ", ".join(dimensions)
        return f"<!-- section: {name} [dimensions: {dims}] -->"
    return f"<!-- section: {name} -->"


def format_section_footer(name: str) -> str:
    """Generate a closing section tag."""
    return f"<!-- /section: {name} -->"
