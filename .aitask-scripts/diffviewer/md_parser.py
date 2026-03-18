"""Markdown section parser for structural diff mode."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Section:
    """A section of a markdown document delimited by headings."""
    heading: str  # Original heading text (e.g., "## Step 1: Setup")
    level: int  # 0=preamble, 1=#, 2=##, etc.
    content_lines: list[str] = field(default_factory=list)
    original_line_range: tuple[int, int] = (0, 0)  # (start, end) in source


_ATX_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)')
_CODE_FENCE_RE = re.compile(r'^\s*```')


def parse_sections(lines: list[str]) -> list[Section]:
    """Parse markdown lines into Section objects, splitting on ATX headings.

    Content before the first heading becomes a preamble Section (level=0).
    Lines inside code fences are never treated as headings.
    """
    sections: list[Section] = []
    current_heading = ""
    current_level = 0
    current_lines: list[str] = []
    start_line = 0
    in_code_fence = False

    for i, line in enumerate(lines):
        stripped = line.rstrip('\n').rstrip('\r')

        # Toggle code fence state
        if _CODE_FENCE_RE.match(stripped):
            in_code_fence = not in_code_fence
            current_lines.append(line)
            continue

        if in_code_fence:
            current_lines.append(line)
            continue

        m = _ATX_HEADING_RE.match(stripped)
        if m:
            # Flush current section
            sections.append(Section(
                heading=current_heading,
                level=current_level,
                content_lines=list(current_lines),
                original_line_range=(start_line, i),
            ))
            # Start new section
            current_heading = line.rstrip('\n').rstrip('\r')
            current_level = len(m.group(1))
            current_lines = []
            start_line = i
        else:
            current_lines.append(line)

    # Flush final section
    sections.append(Section(
        heading=current_heading,
        level=current_level,
        content_lines=list(current_lines),
        original_line_range=(start_line, len(lines)),
    ))

    return sections


def normalize_section(section: Section) -> Section:
    """Return a normalized copy of a Section for matching purposes.

    Heading: strip leading '#' and whitespace, lowercase.
    Content: strip trailing whitespace per line, collapse consecutive
    blank lines to one, strip leading/trailing blank lines.
    """
    # Normalize heading
    heading = re.sub(r'^#+\s*', '', section.heading).strip().lower()

    # Normalize content lines
    normalized: list[str] = []
    prev_blank = False
    for line in section.content_lines:
        stripped = line.rstrip()
        if stripped == '':
            if not prev_blank:
                normalized.append('\n')
            prev_blank = True
        else:
            normalized.append(stripped + '\n')
            prev_blank = False

    # Strip leading blank lines
    while normalized and normalized[0].strip() == '':
        normalized.pop(0)

    # Strip trailing blank lines
    while normalized and normalized[-1].strip() == '':
        normalized.pop()

    return Section(
        heading=heading,
        level=section.level,
        content_lines=normalized,
        original_line_range=section.original_line_range,
    )
