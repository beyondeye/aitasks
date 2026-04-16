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
    """A named section extracted from a proposal or plan."""

    name: str
    dimensions: list[str]
    content: str
    start_line: int  # 1-based
    end_line: int    # 1-based


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


def parse_sections(text: str) -> ParsedContent:
    """Parse *text* and return structured :class:`ParsedContent`."""
    lines = text.split("\n")
    sections: list[ContentSection] = []
    preamble_lines: list[str] = []
    epilogue_lines: list[str] = []

    # State for the currently-open section (None when outside a section).
    cur_name: str | None = None
    cur_dims: list[str] = []
    cur_start: int = 0
    cur_content: list[str] = []
    last_close_idx: int = -1  # index of the last close-tag line

    for idx, line in enumerate(lines):
        lineno = idx + 1  # 1-based

        open_m = _OPEN_RE.search(line)
        if open_m and cur_name is None:
            cur_name = open_m.group(1)
            raw_dims = open_m.group(2)
            cur_dims = (
                [d.strip() for d in raw_dims.split(",") if d.strip()]
                if raw_dims
                else []
            )
            cur_start = lineno
            cur_content = []
            continue

        close_m = _CLOSE_RE.search(line)
        if close_m and cur_name is not None and close_m.group(1) == cur_name:
            sections.append(
                ContentSection(
                    name=cur_name,
                    dimensions=cur_dims,
                    content="\n".join(cur_content),
                    start_line=cur_start,
                    end_line=lineno,
                )
            )
            last_close_idx = idx
            cur_name = None
            cur_dims = []
            cur_content = []
            continue

        # Accumulate into the right bucket.
        if cur_name is not None:
            cur_content.append(line)
        elif not sections and last_close_idx == -1:
            preamble_lines.append(line)
        else:
            epilogue_lines.append(line)

    return ParsedContent(
        sections=sections,
        preamble="\n".join(preamble_lines),
        epilogue="\n".join(epilogue_lines),
        raw=text,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_sections(parsed: ParsedContent) -> list[str]:
    """Return a list of error messages (empty means valid)."""
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


def get_sections_for_dimension(
    parsed: ParsedContent, dimension: str
) -> list[ContentSection]:
    """Return all sections linked to *dimension*."""
    return [sec for sec in parsed.sections if dimension in sec.dimensions]


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
