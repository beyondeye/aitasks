"""Merge engine: selective hunk acceptance, conflict detection, and merge application."""
from __future__ import annotations

import os
from pathlib import Path

from .diff_engine import DiffHunk, MultiDiffResult


class MergeSession:
    """Tracks which hunks are accepted/rejected for a selective merge."""

    def __init__(self, main_lines: list[str], multi_diff: MultiDiffResult):
        self.main_lines = main_lines
        self.multi_diff = multi_diff
        # Keyed by (plan_path, hunk_index) → accepted bool
        self.accepted: dict[tuple[str, int], bool] = {}
        self._init_hunks()

    def _init_hunks(self) -> None:
        """Initialize all non-equal hunks as rejected (False)."""
        for comp in self.multi_diff.comparisons:
            for i, hunk in enumerate(comp.hunks):
                if hunk.tag != "equal":
                    self.accepted[(comp.other_path, i)] = False

    def accept_hunk(self, plan_path: str, idx: int) -> None:
        """Accept a hunk."""
        key = (plan_path, idx)
        if key in self.accepted:
            self.accepted[key] = True

    def reject_hunk(self, plan_path: str, idx: int) -> None:
        """Reject a hunk."""
        key = (plan_path, idx)
        if key in self.accepted:
            self.accepted[key] = False

    def toggle_hunk(self, plan_path: str, idx: int) -> None:
        """Toggle a hunk's accepted state."""
        key = (plan_path, idx)
        if key in self.accepted:
            self.accepted[key] = not self.accepted[key]

    def accept_all_from(self, plan_path: str) -> None:
        """Accept all hunks from a specific comparison plan."""
        for key in self.accepted:
            if key[0] == plan_path:
                self.accepted[key] = True

    def get_accepted_hunks(self) -> list[tuple[str, int, DiffHunk]]:
        """Return list of (plan_path, hunk_idx, hunk) for all accepted hunks."""
        result: list[tuple[str, int, DiffHunk]] = []
        for comp in self.multi_diff.comparisons:
            for i, hunk in enumerate(comp.hunks):
                if self.accepted.get((comp.other_path, i), False):
                    result.append((comp.other_path, i, hunk))
        return result

    def get_conflicts(self) -> list[tuple[str, int, str, int]]:
        """Detect overlapping main_ranges from different plans that are both accepted.

        Returns list of (plan_a, idx_a, plan_b, idx_b) conflict pairs.
        """
        accepted = self.get_accepted_hunks()
        conflicts: list[tuple[str, int, str, int]] = []

        for ai in range(len(accepted)):
            plan_a, idx_a, hunk_a = accepted[ai]
            for bi in range(ai + 1, len(accepted)):
                plan_b, idx_b, hunk_b = accepted[bi]
                if plan_a == plan_b:
                    continue  # Same plan can't conflict with itself
                # Check for main_range overlap
                a_start, a_end = hunk_a.main_range
                b_start, b_end = hunk_b.main_range
                if a_start < b_end and b_start < a_end:
                    conflicts.append((plan_a, idx_a, plan_b, idx_b))

        return conflicts

    def get_accepted_plans(self) -> list[str]:
        """Return list of plan paths that have at least one accepted hunk."""
        plans: list[str] = []
        seen: set[str] = set()
        for (plan_path, _idx), accepted in self.accepted.items():
            if accepted and plan_path not in seen:
                plans.append(plan_path)
                seen.add(plan_path)
        return plans

    def accepted_count(self) -> int:
        """Return count of accepted hunks."""
        return sum(1 for v in self.accepted.values() if v)


def apply_merge(session: MergeSession) -> list[str]:
    """Apply accepted hunks to the main plan and return merged lines.

    Hunks are applied in reverse order (descending by main_range start)
    to preserve line indices during modification.
    """
    output = list(session.main_lines)
    accepted = session.get_accepted_hunks()

    if not accepted:
        return output

    # Sort by main_range start descending — apply from end to preserve indices
    accepted.sort(key=lambda x: x[2].main_range[0], reverse=True)

    for _plan_path, _idx, hunk in accepted:
        start, end = hunk.main_range
        if hunk.tag == "delete":
            del output[start:end]
        elif hunk.tag == "insert":
            for j, line in enumerate(hunk.other_lines):
                output.insert(start + j, line)
        elif hunk.tag == "replace":
            output[start:end] = hunk.other_lines
        # 'moved' hunks are skipped — they don't change content

    return output


def apply_merge_annotated(
    session: MergeSession,
) -> tuple[list[str], list[tuple[str, int] | None]]:
    """Apply merge and return (merged_lines, annotations).

    Each annotation is either (plan_path, hunk_idx) for lines contributed
    by an accepted hunk, or None for original main lines.
    """
    # Build list of (main_range_start, plan_path, hunk_idx, hunk) for accepted hunks
    accepted = session.get_accepted_hunks()
    if not accepted:
        return list(session.main_lines), [None] * len(session.main_lines)

    # Sort ascending by main_range start for forward annotation
    accepted_asc = sorted(accepted, key=lambda x: x[2].main_range[0])

    # Build output by walking through main_lines, applying hunks in order
    output: list[str] = []
    annotations: list[tuple[str, int] | None] = []
    main_pos = 0

    for plan_path, hunk_idx, hunk in accepted_asc:
        start, end = hunk.main_range

        # Copy original lines before this hunk
        while main_pos < start:
            if main_pos < len(session.main_lines):
                output.append(session.main_lines[main_pos])
                annotations.append(None)
            main_pos += 1

        # Apply the hunk
        if hunk.tag == "delete":
            # Skip the deleted lines
            main_pos = end
        elif hunk.tag == "insert":
            # Insert new lines (main_pos stays at start — no lines consumed)
            for line in hunk.other_lines:
                output.append(line)
                annotations.append((plan_path, hunk_idx))
        elif hunk.tag == "replace":
            # Replace: skip main lines, insert other lines
            for line in hunk.other_lines:
                output.append(line)
                annotations.append((plan_path, hunk_idx))
            main_pos = end
        else:
            # 'moved' or unknown — keep original
            while main_pos < end:
                if main_pos < len(session.main_lines):
                    output.append(session.main_lines[main_pos])
                    annotations.append(None)
                main_pos += 1

    # Copy remaining original lines
    while main_pos < len(session.main_lines):
        output.append(session.main_lines[main_pos])
        annotations.append(None)
        main_pos += 1

    return output, annotations


def compute_hunk_preview_range(
    session: MergeSession,
    target_plan: str,
    target_idx: int,
) -> tuple[int, int]:
    """Compute the line range in the merged output where a hunk's effect appears.

    Returns (start_line, end_line) as 0-based indices in the merged output.
    For accepted hunks: the range of inserted/replaced lines.
    For rejected hunks: the range of original main lines that would be affected.
    """
    accepted = session.get_accepted_hunks()
    accepted_asc = sorted(accepted, key=lambda x: x[2].main_range[0])

    # Find the target hunk
    target_hunk = None
    for comp in session.multi_diff.comparisons:
        if comp.other_path == target_plan:
            if target_idx < len(comp.hunks):
                target_hunk = comp.hunks[target_idx]
            break
    if target_hunk is None:
        return (0, 0)

    target_main_start, target_main_end = target_hunk.main_range
    is_accepted = session.accepted.get((target_plan, target_idx), False)

    # Walk through main_lines tracking position in merged output
    merged_pos = 0
    main_pos = 0
    result_start = 0
    result_end = 0

    for plan_path, hunk_idx, hunk in accepted_asc:
        start, end = hunk.main_range

        # Advance through original lines before this hunk
        if main_pos < start:
            advance = start - main_pos
            # Check if target falls in this original region
            if target_main_start >= main_pos and target_main_start < start:
                result_start = merged_pos + (target_main_start - main_pos)
            merged_pos += advance
            main_pos = start

        # Check if this is our target hunk
        if plan_path == target_plan and hunk_idx == target_idx:
            result_start = merged_pos
            if hunk.tag == "delete":
                result_end = merged_pos  # Deletion point
            elif hunk.tag in ("insert", "replace"):
                result_end = merged_pos + len(hunk.other_lines)
            else:
                result_end = merged_pos + (end - start)
            return (result_start, max(result_start + 1, result_end))

        # Account for this accepted hunk's effect on position
        if hunk.tag == "delete":
            main_pos = end
        elif hunk.tag == "insert":
            merged_pos += len(hunk.other_lines)
        elif hunk.tag == "replace":
            merged_pos += len(hunk.other_lines)
            main_pos = end
        else:
            merged_pos += end - start
            main_pos = end

    # Target hunk was not among accepted — find its position in the merged output
    # Advance remaining original lines
    if target_main_start >= main_pos:
        result_start = merged_pos + (target_main_start - main_pos)
        if target_hunk.tag == "insert":
            # Insert point — highlight the line at the insertion position
            result_end = result_start + 1
        else:
            # Show the range of original lines that would be affected
            span = target_main_end - target_main_start
            result_end = result_start + max(1, span)
    else:
        result_start = merged_pos
        result_end = result_start + 1

    return (result_start, result_end)


def suggest_filename(main_path: str, accepted_plans: list[str]) -> str:
    """Generate a merged filename from the main plan and accepted plan names.

    Example: main="plan_alpha.md", accepted=["plan_beta.md", "plan_gamma.md"]
    → "plan_alpha_merged_beta_gamma.md"
    """
    main_stem = Path(main_path).stem
    if not accepted_plans:
        return f"{main_stem}_merged.md"

    other_stems: list[str] = []
    for p in accepted_plans:
        stem = Path(p).stem
        # Try to strip common prefix for brevity
        if stem.startswith("plan_"):
            stem = stem[5:]
        other_stems.append(stem)

    return f"{main_stem}_merged_{'_'.join(other_stems)}.md"


def suggest_directory(main_path: str) -> str:
    """Return the directory of the main plan as the default save location."""
    return os.path.dirname(main_path) or "."
