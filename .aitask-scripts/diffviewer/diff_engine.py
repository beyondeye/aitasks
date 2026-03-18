"""Core diff engine for classical (line-by-line) diff computation."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from .plan_loader import load_plan


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
        mode: Diff mode ('classical' or 'structural'). Currently only
              'classical' is implemented.

    Returns:
        MultiDiffResult with pairwise comparisons and unique content.
    """
    _main_meta, _main_body, main_lines = load_plan(main_path)

    result = MultiDiffResult(main_path=main_path)

    for other_path in other_paths:
        _other_meta, _other_body, other_lines = load_plan(other_path)
        hunks = compute_classical_diff(main_lines, other_lines, source_plan=other_path)
        result.comparisons.append(PairwiseDiff(
            main_path=main_path,
            other_path=other_path,
            mode=mode,
            hunks=hunks,
        ))

    _compute_unique_content(result)
    return result
