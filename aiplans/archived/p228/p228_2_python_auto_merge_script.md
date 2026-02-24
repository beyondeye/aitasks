---
Task: t228_2_python_auto_merge_script.md
Parent Task: aitasks/t228_improved_task_merge_for_board.md
Sibling Tasks: aitasks/t228/t228_1_*.md, aitasks/t228/t228_3_*.md, aitasks/t228/t228_4_*.md, aitasks/t228/t228_5_*.md
Branch: (current branch - no worktree)
Base branch: main
---

# Plan: t228_2 — Python Auto-Merge Script

## Goal

Create `aiscripts/board/aitask_merge.py` — a CLI tool that parses git conflict markers in task files and applies auto-merge rules to resolve frontmatter conflicts.

## Steps

### 1. Conflict Marker Parser

```python
import re
import sys
from task_yaml import parse_frontmatter, serialize_frontmatter, _TaskSafeLoader

CONFLICT_START = re.compile(r'^<{7}\s+(.*)$', re.MULTILINE)
CONFLICT_MID = re.compile(r'^={7}$', re.MULTILINE)
CONFLICT_END = re.compile(r'^>{7}\s+(.*)$', re.MULTILINE)

def parse_conflict_file(content: str) -> tuple[str, str] | None:
    """Extract LOCAL and REMOTE full-document versions from conflict markers.

    For task files, typically the entire file is one conflict hunk.
    For multi-hunk files, reconstructs complete LOCAL and REMOTE documents
    by taking LOCAL side of each hunk for the local doc, REMOTE for the remote doc.

    Returns (local_content, remote_content) or None if no conflict markers.
    """
```

Key considerations:
- Handle entire-file-is-one-hunk case (most common for task files)
- Handle multi-hunk case by reconstructing both complete documents
- Handle `diff3` conflict style (3-way markers with `|||||||` base section)

### 2. Merge Logic

```python
def merge_frontmatter(local_meta: dict, remote_meta: dict,
                      local_updated: str, remote_updated: str,
                      batch: bool = False) -> tuple[dict, list[str]]:
    """Apply auto-merge rules to two frontmatter dicts.

    Returns (merged_metadata, list_of_unresolved_field_names).
    """
```

Rules implementation:
- **All keys union first**: Combine keys from both sides
- **Same value**: No conflict, keep as-is
- **`boardcol`, `boardidx`**: `merged[field] = local_meta[field]`
- **`updated_at`**: Parse both as `datetime`, keep newer
- **`labels`**: `sorted(set(local_labels) | set(remote_labels))`
- **`depends`**: `sorted(set(local_deps) | set(remote_deps))`
- **`priority`, `effort`**: In batch → keep REMOTE. In interactive → prompt user via stdin with newest hint
- **`status`**: If either is `"Implementing"` and the other isn't → keep `"Implementing"`. If both differ and neither is Implementing → unresolved
- **Other fields with different values**: Add to unresolved list

### 3. Body Merge

```python
def merge_body(local_body: str, remote_body: str) -> tuple[str, bool]:
    """Try to merge body content.

    Returns (merged_body, is_resolved).
    If bodies differ, returns body with conflict markers preserved and is_resolved=False.
    """
```

### 4. Main Entry Point

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', help='Path to conflicted file')
    parser.add_argument('--batch', action='store_true', help='Batch mode (no prompts)')
    args = parser.parse_args()

    content = Path(args.file).read_text()

    # 1. Parse conflict markers
    result = parse_conflict_file(content)
    if result is None:
        print("SKIPPED")
        sys.exit(1)

    local_content, remote_content = result

    # 2. Parse frontmatter from both sides
    local_parsed = parse_frontmatter(local_content)
    remote_parsed = parse_frontmatter(remote_content)
    if not local_parsed or not remote_parsed:
        print("SKIPPED")
        sys.exit(1)

    local_meta, local_body, local_keys = local_parsed
    remote_meta, remote_body, remote_keys = remote_parsed

    # 3. Merge frontmatter
    merged_meta, unresolved = merge_frontmatter(
        local_meta, remote_meta,
        local_meta.get("updated_at", ""), remote_meta.get("updated_at", ""),
        batch=args.batch
    )

    # 4. Merge body
    merged_body, body_resolved = merge_body(local_body, remote_body)
    if not body_resolved:
        unresolved.append("body")

    # 5. Determine key order (union of both sides' key orders)
    merged_keys = list(dict.fromkeys(local_keys + remote_keys))

    # 6. Write result
    merged_content = serialize_frontmatter(merged_meta, merged_body, merged_keys)
    Path(args.file).write_text(merged_content)

    # 7. Output status
    if unresolved:
        print(f"PARTIAL:{','.join(unresolved)}")
        # Print newest hints to stderr
        local_ts = local_meta.get("updated_at", "unknown")
        remote_ts = remote_meta.get("updated_at", "unknown")
        newer = "LOCAL" if local_ts > remote_ts else "REMOTE"
        for field in unresolved:
            if field != "body":
                local_val = local_meta.get(field, "<absent>")
                remote_val = remote_meta.get(field, "<absent>")
                print(f'{field} conflict: LOCAL="{local_val}" vs REMOTE="{remote_val}" ({newer} is newer: {max(local_ts, remote_ts)})',
                      file=sys.stderr)
        sys.exit(2)
    else:
        print("RESOLVED")
        sys.exit(0)
```

### 5. Interactive Priority/Effort Prompt

In non-batch mode, for `priority` and `effort` conflicts:

```python
def prompt_field_choice(field: str, local_val, remote_val, newer_side: str) -> str:
    """Prompt user to choose between local and remote values."""
    print(f"\n{field} conflict ({newer_side} is newer):", file=sys.stderr)
    print(f"  [l] LOCAL:  {local_val}", file=sys.stderr)
    print(f"  [r] REMOTE: {remote_val} (default)", file=sys.stderr)
    choice = input("  Keep [l/r]? ").strip().lower()
    return local_val if choice == "l" else remote_val
```

## Key Design Decisions

- Exit code 2 (not 1) for partial resolution so the caller can distinguish "skip entirely" from "partially resolved"
- Newest hints go to stderr so stdout remains clean for the protocol
- Key order merging: union of both sides preserving order, with local order taking priority
- The script writes the merged file in-place (replacing the conflicted version)
- `diff3` conflict style support ensures compatibility with various git configs

## Final Implementation Notes

- **Actual work done:** Created `aiscripts/board/aitask_merge.py` (230 LOC) implementing all planned merge rules and CLI interface. Created `tests/test_aitask_merge.sh` with 10 test cases (43 assertions) covering all merge rules and edge cases.
- **Deviations from plan:** The conflict marker parser was rewritten from a regex-based approach to a line-by-line state machine. The original regex approach using non-greedy `(.*?)` with `re.MULTILINE | re.DOTALL` had a bug where the LOCAL capture group matched an empty string. The line-by-line parser is more robust and handles all conflict styles (2-way, diff3) correctly. Also simplified `merge_frontmatter` signature — removed separate `local_updated`/`remote_updated` params since timestamps are extracted from the metadata dicts internally.
- **Issues encountered:** Python regex non-greedy quantifier `(.*?)` combined with `re.MULTILINE | re.DOTALL` produces incorrect results when anchored patterns like `^={7}` follow — the regex engine finds unexpected zero-length matches. Solved by switching to a line-by-line parser.
- **Key decisions:** Used `str` comparison for `updated_at` timestamps (ISO format sorts correctly as strings). Interactive prompt defaults to REMOTE value on empty/EOF input. List union fields (`labels`, `depends`) convert all values to strings for dedup via `set()`.
- **Notes for sibling tasks:** The script is ready for integration by t228_3 (`aitask_sync.sh`). Call pattern: `python3 aiscripts/board/aitask_merge.py <file> --batch` — check exit code (0=resolved, 1=skip, 2=partial) and parse stdout (`RESOLVED`, `PARTIAL:<fields>`, `SKIPPED`). The script must be run from `aiscripts/board/` directory (or have it on `PYTHONPATH`) for the `task_yaml` import to work. Test suite: `bash tests/test_aitask_merge.sh`.
