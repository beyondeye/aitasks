"""Core diff engine for classical and structural diff computation."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .plan_loader import load_plan
from .md_parser import parse_sections, normalize_section


@dataclass
class DiffHunk:
    """One contiguous region of change between two plan files."""
    tag: str  # 'equal', 'insert', 'delete', 'replace', 'moved'
    main_lines: list[str] = field(default_factory=list)
    other_lines: list[str] = field(default_factory=list)
    source_plans: list[str] = field(default_factory=list)
    main_range: tuple[int, int] = (0, 0)   # line numbers in main
    other_range: tuple[int, int] = (0, 0)  # line numbers in other


@dataclass
class PairwiseDiff:
    """Diff result between two plan files."""
    main_path: str
    other_path: str
    mode: str  # 'classical' or 'structural'
    hunks: list[DiffHunk] = field(default_factory=list)


@dataclass
class MultiDiffResult:
    """Collection of pairwise diffs plus unique content summaries."""
    main_path: str
    comparisons: list[PairwiseDiff] = field(default_factory=list)
    unique_to_main: list[DiffHunk] = field(default_factory=list)
    unique_to_others: dict[str, list[DiffHunk]] = field(default_factory=dict)


def _is_junk(line: str) -> bool:
    """Lines treated as low-priority for matching."""
    stripped = line.strip()
    return stripped == '' or stripped == '---'


def compute_classical_diff(
    main_lines: list[str],
    other_lines: list[str],
    source_plan: str = ""
) -> list[DiffHunk]:
    """Compute a classical line-by-line diff between two sets of lines.

    Uses difflib.SequenceMatcher with junk filtering for blank lines
    and frontmatter delimiters.
    """
    matcher = difflib.SequenceMatcher(_is_junk, main_lines, other_lines)
    hunks: list[DiffHunk] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        hunk = DiffHunk(
            tag=tag,
            main_lines=list(main_lines[i1:i2]),
            other_lines=list(other_lines[j1:j2]),
            source_plans=[source_plan] if source_plan else [],
            main_range=(i1, i2),
            other_range=(j1, j2),
        )
        hunks.append(hunk)

    return hunks


def compute_structural_diff(
    main_lines: list[str],
    other_lines: list[str],
    source_plan: str = "",
    similarity_threshold: float = 0.6,
) -> list[DiffHunk]:
    """Compute a structural diff by parsing markdown into sections.

    Sections are matched by heading first, then by content similarity.
    Sections that appear at different positions are tagged as 'moved'.
    """
    # Phase 1: Parse and normalize
    main_sections = parse_sections(main_lines)
    other_sections = parse_sections(other_lines)
    main_norm = [normalize_section(s) for s in main_sections]
    other_norm = [normalize_section(s) for s in other_sections]

    # Phase 2: Heading-based matching
    matched_main: set[int] = set()
    matched_other: set[int] = set()
    matches: list[tuple[int, int]] = []  # (main_idx, other_idx)

    for mi, mn in enumerate(main_norm):
        if mi in matched_main:
            continue
        for oi, on in enumerate(other_norm):
            if oi in matched_other:
                continue
            if mn.heading == on.heading:
                matches.append((mi, oi))
                matched_main.add(mi)
                matched_other.add(oi)
                break

    # Phase 3: Content similarity matching for unmatched sections
    unmatched_main = [i for i in range(len(main_norm)) if i not in matched_main]
    unmatched_other = [i for i in range(len(other_norm)) if i not in matched_other]

    if unmatched_main and unmatched_other:
        # Compute all similarity pairs
        candidates: list[tuple[float, int, int]] = []
        for mi in unmatched_main:
            mc = ''.join(main_norm[mi].content_lines)
            for oi in unmatched_other:
                oc = ''.join(other_norm[oi].content_lines)
                if not mc and not oc:
                    continue
                ratio = difflib.SequenceMatcher(None, mc, oc).ratio()
                if ratio > similarity_threshold:
                    candidates.append((ratio, mi, oi))

        # Greedy matching: pick highest ratio first
        candidates.sort(key=lambda x: x[0], reverse=True)
        for _ratio, mi, oi in candidates:
            if mi not in matched_main and oi not in matched_other:
                matches.append((mi, oi))
                matched_main.add(mi)
                matched_other.add(oi)

    # Phase 4: Classify and generate hunks
    source = [source_plan] if source_plan else []
    hunks: list[DiffHunk] = []

    # Process matched pairs
    for mi, oi in matches:
        ms = main_sections[mi]
        os_ = other_sections[oi]
        is_same_position = (mi == oi)

        # Compare content (include heading line for full comparison)
        main_all = ([ms.heading + '\n'] if ms.heading else []) + ms.content_lines
        other_all = ([os_.heading + '\n'] if os_.heading else []) + os_.content_lines
        content_identical = (main_all == other_all)

        if is_same_position and content_identical:
            tag = 'equal'
        elif is_same_position:
            tag = 'replace'
        else:
            tag = 'moved'

        if tag == 'equal' or (tag == 'moved' and content_identical):
            # Equal sections or moved sections with identical content:
            # emit a single hunk
            hunks.append(DiffHunk(
                tag=tag,
                main_lines=main_all,
                other_lines=other_all,
                source_plans=source,
                main_range=ms.original_line_range,
                other_range=os_.original_line_range,
            ))
        else:
            # Replace or moved-with-changes: run classical diff within section
            sub_hunks = compute_classical_diff(main_all, other_all, source_plan=source_plan)
            for sh in sub_hunks:
                # Offset sub-hunk ranges to absolute positions
                sh_main_start = ms.original_line_range[0] + sh.main_range[0]
                sh_main_end = ms.original_line_range[0] + sh.main_range[1]
                sh_other_start = os_.original_line_range[0] + sh.other_range[0]
                sh_other_end = os_.original_line_range[0] + sh.other_range[1]
                hunks.append(DiffHunk(
                    tag=tag if sh.tag != 'equal' else 'equal',
                    main_lines=sh.main_lines,
                    other_lines=sh.other_lines,
                    source_plans=source,
                    main_range=(sh_main_start, sh_main_end),
                    other_range=(sh_other_start, sh_other_end),
                ))

    # Unmatched main sections → delete
    for mi in range(len(main_sections)):
        if mi not in matched_main:
            ms = main_sections[mi]
            all_lines = ([ms.heading + '\n'] if ms.heading else []) + ms.content_lines
            hunks.append(DiffHunk(
                tag='delete',
                main_lines=all_lines,
                source_plans=source,
                main_range=ms.original_line_range,
            ))

    # Unmatched other sections → insert
    for oi in range(len(other_sections)):
        if oi not in matched_other:
            os_ = other_sections[oi]
            all_lines = ([os_.heading + '\n'] if os_.heading else []) + os_.content_lines
            hunks.append(DiffHunk(
                tag='insert',
                other_lines=all_lines,
                source_plans=source,
                other_range=os_.original_line_range,
            ))

    # Phase 5: Sort by main_range for consistent ordering
    hunks.sort(key=lambda h: (h.main_range[0], h.other_range[0]))

    return hunks


def _compute_unique_content(result: MultiDiffResult) -> None:
    """Populate unique_to_main and unique_to_others on a MultiDiffResult.

    A main line is "unique to main" if it is NOT equal in ANY comparison.
    A line in other is "unique to other X" if it was inserted or in a
    replace hunk in that comparison.
    """
    if not result.comparisons:
        return

    # Gather the set of main-line indices that are 'equal' in each comparison
    equal_indices_per_comp: list[set[int]] = []
    for comp in result.comparisons:
        equal_set: set[int] = set()
        for hunk in comp.hunks:
            if hunk.tag == 'equal':
                for idx in range(hunk.main_range[0], hunk.main_range[1]):
                    equal_set.add(idx)
        equal_indices_per_comp.append(equal_set)

    # Union of all equal indices across comparisons
    all_equal = set()
    for eq in equal_indices_per_comp:
        all_equal |= eq

    # Load main lines from the first comparison's hunks
    max_main_idx = 0
    for comp in result.comparisons:
        for hunk in comp.hunks:
            if hunk.main_range[1] > max_main_idx:
                max_main_idx = hunk.main_range[1]

    # Build main_lines array from hunks
    main_lines: list[str] = [''] * max_main_idx
    for hunk in result.comparisons[0].hunks:
        for i, idx in enumerate(range(hunk.main_range[0], hunk.main_range[1])):
            if i < len(hunk.main_lines):
                main_lines[idx] = hunk.main_lines[i]

    # unique_to_main: lines not equal in ANY comparison
    unique_main_indices: set[int] = set()
    for idx in range(max_main_idx):
        if idx not in all_equal:
            unique_main_indices.add(idx)

    # Group consecutive unique-to-main indices into DiffHunks
    if unique_main_indices:
        sorted_indices = sorted(unique_main_indices)
        runs: list[list[int]] = []
        current_run = [sorted_indices[0]]
        for idx in sorted_indices[1:]:
            if idx == current_run[-1] + 1:
                current_run.append(idx)
            else:
                runs.append(current_run)
                current_run = [idx]
        runs.append(current_run)

        for run in runs:
            result.unique_to_main.append(DiffHunk(
                tag='delete',
                main_lines=[main_lines[i] for i in run],
                main_range=(run[0], run[-1] + 1),
            ))

    # unique_to_others: lines inserted or in replace hunks per comparison
    for comp in result.comparisons:
        unique_hunks: list[DiffHunk] = []
        for hunk in comp.hunks:
            if hunk.tag in ('insert', 'replace') and hunk.other_lines:
                unique_hunks.append(DiffHunk(
                    tag=hunk.tag,
                    other_lines=list(hunk.other_lines),
                    source_plans=[comp.other_path],
                    other_range=hunk.other_range,
                ))
        if unique_hunks:
            result.unique_to_others[comp.other_path] = unique_hunks


def compute_multi_diff(
    main_path: str,
    other_paths: list[str],
    mode: str = 'classical'
) -> MultiDiffResult:
    """Compute diffs between a main plan and multiple other plans.

    Args:
        main_path: Path to the main plan file.
        other_paths: Paths to other plan files to compare against.
        mode: Diff mode ('classical' or 'structural').

    Returns:
        MultiDiffResult with pairwise comparisons and unique content.
    """
    _main_meta, _main_body, main_lines = load_plan(main_path)

    result = MultiDiffResult(main_path=main_path)

    for other_path in other_paths:
        _other_meta, _other_body, other_lines = load_plan(other_path)
        if mode == 'structural':
            hunks = compute_structural_diff(main_lines, other_lines, source_plan=other_path)
        else:
            hunks = compute_classical_diff(main_lines, other_lines, source_plan=other_path)
        result.comparisons.append(PairwiseDiff(
            main_path=main_path,
            other_path=other_path,
            mode=mode,
            hunks=hunks,
        ))

    _compute_unique_content(result)
    return result
