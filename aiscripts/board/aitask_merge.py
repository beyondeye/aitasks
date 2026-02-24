#!/usr/bin/env python3
"""Auto-merge git conflict markers in aitask files.

Parses conflict markers, applies deterministic merge rules to frontmatter
fields, and writes the resolved (or partially resolved) file back.

Usage:
    python3 aitask_merge.py <conflicted_file> [--batch]

Exit codes:
    0 — Fully resolved (RESOLVED)
    1 — Not a task file, parse error, or IO error (SKIPPED / ERROR)
    2 — Partial resolution, some fields need manual attention (PARTIAL)

Stdout protocol:
    RESOLVED
    PARTIAL:<field1>,<field2>
    SKIPPED
    ERROR:<message>

Stderr: Informational messages (what was auto-merged, newest hints).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from task_yaml import parse_frontmatter, serialize_frontmatter, BOARD_KEYS

# ---------------------------------------------------------------------------
# Conflict marker parser
# ---------------------------------------------------------------------------

_MARKER_START = re.compile(r'^<{7}\s', re.MULTILINE)
_MARKER_BASE = re.compile(r'^\|{7}', re.MULTILINE)
_MARKER_MID = re.compile(r'^={7}$', re.MULTILINE)
_MARKER_END = re.compile(r'^>{7}\s', re.MULTILINE)


def parse_conflict_file(content: str) -> tuple[str, str] | None:
    """Extract LOCAL and REMOTE full-document versions from conflict markers.

    Handles both standard 2-way and diff3 3-way conflict styles.
    For multi-hunk files, reconstructs complete LOCAL and REMOTE documents
    by taking the LOCAL side of each hunk for the local doc, REMOTE for remote.

    Returns (local_content, remote_content) or None if no conflict markers.
    """
    lines = content.split("\n")
    hunks: list[tuple[list[str], list[str]]] = []
    hunk_ranges: list[tuple[int, int]] = []  # (start_line, end_line) inclusive

    i = 0
    while i < len(lines):
        if _MARKER_START.match(lines[i]):
            # Found start of a conflict hunk
            hunk_start = i
            local_lines: list[str] = []
            base_lines: list[str] | None = None
            remote_lines: list[str] = []
            section = "local"
            i += 1  # skip <<<<<<< line

            while i < len(lines):
                if _MARKER_BASE.match(lines[i]):
                    section = "base"
                    base_lines = []
                    i += 1
                elif _MARKER_MID.match(lines[i]):
                    section = "remote"
                    i += 1
                elif _MARKER_END.match(lines[i]):
                    hunk_ranges.append((hunk_start, i))
                    hunks.append((local_lines, remote_lines))
                    i += 1
                    break
                else:
                    if section == "local":
                        local_lines.append(lines[i])
                    elif section == "base":
                        pass  # discard base content (diff3)
                    elif section == "remote":
                        remote_lines.append(lines[i])
                    i += 1
        else:
            i += 1

    if not hunks:
        return None

    # Reconstruct LOCAL and REMOTE documents
    local_parts: list[str] = []
    remote_parts: list[str] = []
    prev_line = 0

    for (local_h, remote_h), (start, end) in zip(hunks, hunk_ranges):
        # Lines before this hunk are shared
        shared = lines[prev_line:start]
        local_parts.extend(shared)
        remote_parts.extend(shared)
        # Hunk content
        local_parts.extend(local_h)
        remote_parts.extend(remote_h)
        prev_line = end + 1

    # Lines after the last hunk
    local_parts.extend(lines[prev_line:])
    remote_parts.extend(lines[prev_line:])

    return ("\n".join(local_parts), "\n".join(remote_parts))


# ---------------------------------------------------------------------------
# Merge rules
# ---------------------------------------------------------------------------

_LIST_UNION_FIELDS = frozenset({"labels", "depends"})
_KEEP_LOCAL_FIELDS = frozenset(BOARD_KEYS)
_PROMPTABLE_FIELDS = frozenset({"priority", "effort"})


def _parse_timestamp(ts) -> str:
    """Normalise a timestamp value to a comparable string."""
    return str(ts).strip() if ts else ""


def _newer_side(local_ts: str, remote_ts: str) -> str:
    """Return 'LOCAL' or 'REMOTE' based on which timestamp is newer."""
    return "LOCAL" if local_ts >= remote_ts else "REMOTE"


def _prompt_field_choice(field: str, local_val, remote_val, newer: str):
    """Interactive prompt for priority/effort conflicts."""
    print(f"\n{field} conflict ({newer} is newer):", file=sys.stderr)
    print(f"  [l] LOCAL:  {local_val}", file=sys.stderr)
    print(f"  [r] REMOTE: {remote_val} (default)", file=sys.stderr)
    try:
        choice = input("  Keep [l/r]? ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = ""
    return local_val if choice == "l" else remote_val


def merge_frontmatter(
    local_meta: dict,
    remote_meta: dict,
    batch: bool = False,
) -> tuple[dict, list[str]]:
    """Apply auto-merge rules to two frontmatter dicts.

    Returns (merged_metadata, list_of_unresolved_field_names).
    """
    merged: dict = {}
    unresolved: list[str] = []

    local_ts = _parse_timestamp(local_meta.get("updated_at"))
    remote_ts = _parse_timestamp(remote_meta.get("updated_at"))
    newer = _newer_side(local_ts, remote_ts)

    all_keys = list(dict.fromkeys(list(local_meta.keys()) + list(remote_meta.keys())))

    for key in all_keys:
        in_local = key in local_meta
        in_remote = key in remote_meta

        # Field on one side only — no conflict, just include
        if in_local and not in_remote:
            merged[key] = local_meta[key]
            continue
        if in_remote and not in_local:
            merged[key] = remote_meta[key]
            continue

        local_val = local_meta[key]
        remote_val = remote_meta[key]

        # Same value — no conflict
        if local_val == remote_val:
            merged[key] = local_val
            continue

        # --- Field-specific rules ---

        if key in _KEEP_LOCAL_FIELDS:
            merged[key] = local_val

        elif key == "updated_at":
            merged[key] = local_val if local_ts >= remote_ts else remote_val

        elif key in _LIST_UNION_FIELDS:
            local_list = local_val if isinstance(local_val, list) else []
            remote_list = remote_val if isinstance(remote_val, list) else []
            merged[key] = sorted(set(str(x) for x in local_list) | set(str(x) for x in remote_list))

        elif key in _PROMPTABLE_FIELDS:
            if batch:
                merged[key] = remote_val
            else:
                merged[key] = _prompt_field_choice(key, local_val, remote_val, newer)

        elif key == "status":
            if local_val == "Implementing" or remote_val == "Implementing":
                merged[key] = "Implementing"
            else:
                unresolved.append(key)
                merged[key] = local_val  # placeholder

        else:
            unresolved.append(key)
            merged[key] = local_val  # placeholder

    return merged, unresolved


# ---------------------------------------------------------------------------
# Body merge
# ---------------------------------------------------------------------------

def merge_body(local_body: str, remote_body: str) -> tuple[str, bool]:
    """Try to merge body content.

    Returns (merged_body, is_resolved).
    If bodies differ, wraps them in conflict markers and returns is_resolved=False.
    """
    if local_body == remote_body:
        return local_body, True

    conflict_body = (
        "<<<<<<< LOCAL\n"
        f"{local_body}"
        "=======\n"
        f"{remote_body}"
        ">>>>>>> REMOTE\n"
    )
    return conflict_body, False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-merge git conflict markers in aitask files.",
    )
    parser.add_argument("file", help="Path to conflicted file")
    parser.add_argument(
        "--batch", action="store_true",
        help="Batch mode: no interactive prompts, use deterministic defaults",
    )
    args = parser.parse_args()

    filepath = Path(args.file)
    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR:{exc}", flush=True)
        return 1

    # 1. Parse conflict markers
    result = parse_conflict_file(content)
    if result is None:
        print("SKIPPED", flush=True)
        return 1

    local_content, remote_content = result

    # 2. Parse frontmatter from both sides
    local_parsed = parse_frontmatter(local_content)
    remote_parsed = parse_frontmatter(remote_content)
    if not local_parsed or not remote_parsed:
        print("SKIPPED", flush=True)
        return 1

    local_meta, local_body, local_keys = local_parsed
    remote_meta, remote_body, remote_keys = remote_parsed

    # 3. Merge frontmatter
    merged_meta, unresolved = merge_frontmatter(
        local_meta, remote_meta,
        batch=args.batch,
    )

    # 4. Merge body
    merged_body, body_resolved = merge_body(local_body, remote_body)
    if not body_resolved:
        unresolved.append("body")

    # 5. Determine key order (union of both sides, local order priority)
    merged_keys = list(dict.fromkeys(local_keys + remote_keys))

    # 6. Write result
    merged_content = serialize_frontmatter(merged_meta, merged_body, merged_keys)
    filepath.write_text(merged_content, encoding="utf-8")

    # 7. Output status
    if unresolved:
        print(f"PARTIAL:{','.join(unresolved)}", flush=True)
        # Print newest hints to stderr
        local_ts = _parse_timestamp(local_meta.get("updated_at"))
        remote_ts = _parse_timestamp(remote_meta.get("updated_at"))
        newer = _newer_side(local_ts, remote_ts)
        for field in unresolved:
            if field != "body":
                local_val = local_meta.get(field, "<absent>")
                remote_val = remote_meta.get(field, "<absent>")
                print(
                    f'{field} conflict: LOCAL="{local_val}" vs REMOTE="{remote_val}" '
                    f'({newer} is newer: {max(local_ts, remote_ts)})',
                    file=sys.stderr,
                )
        return 2

    print("RESOLVED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
