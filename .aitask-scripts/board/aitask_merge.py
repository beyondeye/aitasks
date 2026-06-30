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

# The canonical gate-ledger parser lives under lib/ (t635_8 owns it — do not fork).
# Mirror the lib/ import idiom used by board/aitask_board.py so this works both
# under PYTHONPATH=board (sync) and when a test imports this module directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import gate_ledger  # noqa: E402  -- stdlib-only; sys.path set up just above

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

        elif key == "anchor":
            # Scalar topic group key (t1016). Newer side wins so a board/CLI
            # edit is not dropped into the unresolved/PARTIAL path on sync.
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

# Gate-run "run=" stamps are ISO-8601-Z (the exact shape gate_ledger.iso_now()
# emits). Valid ISO strings sort lexicographically == chronologically, which is
# what derive_gate_runs() (last-in-file-order wins) needs for last-run-wins.
_ISO_RUN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _conflict_markers(local: str, remote: str) -> str:
    """Wrap two divergent texts in the standard 2-way conflict markers."""
    return (
        "<<<<<<< LOCAL\n"
        f"{local}"
        "=======\n"
        f"{remote}"
        ">>>>>>> REMOTE\n"
    )


def _split_gate_section(body: str) -> tuple[str, str]:
    """Return (head, section); section starts at the first '## Gate Runs' or ''."""
    m = re.search(r"(?m)^##\s+Gate Runs\s*$", body)
    if not m:
        return body, ""
    return body[:m.start()], body[m.start():]


def _block_text(run) -> str:
    """Reconstruct a gate-run block's exact source text from a parsed GateRun."""
    txt = run.raw_marker
    if run.raw_body_lines:
        txt += "\n" + "\n".join(run.raw_body_lines)
    return txt


def _section_is_clean(section: str) -> bool:
    """True if every non-blank line under the header is a comment or blockquote.

    Guards against silently dropping stray prose/notes/headings a user or later
    tool placed under the ledger header — parse_gate_run_blocks would not
    reconstruct them, so such a section must NOT be union-rebuilt.
    """
    for ln in section.splitlines()[1:]:  # skip the '## Gate Runs' header line
        s = ln.strip()
        if not s or s.startswith("<!--") or ln.startswith(">"):
            continue
        return False
    return True


def _union_gate_runs(local_body: str, remote_body: str):
    """Union the append-only '## Gate Runs' ledger of two bodies.

    Returns (merged_body, head_resolved) when a *provably safe* union is possible,
    else None (the caller then falls back to whole-body conflict markers). The
    safety guards below all degrade to the conflict path rather than guess, so no
    ledger data is ever silently reordered or dropped.
    """
    local_head, local_sec = _split_gate_section(local_body)
    remote_head, remote_sec = _split_gate_section(remote_body)
    if not local_sec and not remote_sec:
        return None  # no ledger anywhere → not our case

    # Guard 3: only union purely machine-owned ledger sections.
    if not _section_is_clean(local_sec) or not _section_is_clean(remote_sec):
        return None

    runs = (gate_ledger.parse_gate_run_blocks(local_sec)
            + gate_ledger.parse_gate_run_blocks(remote_sec))

    # Guard 1: trustworthy ordering requires a valid ISO run on every block.
    if any(not _ISO_RUN_RE.match(r.fields.get("run", "")) for r in runs):
        return None

    # Guard 2: dedup by FULL TEXT only — shared history collapses, divergent kept.
    by_text: dict[str, object] = {}
    for r in runs:
        by_text.setdefault(_block_text(r), r)

    # Guard 2b: ambiguous winner — >1 distinct block for one (name, run, attempt)
    # is an append-only contract violation; let a human pick rather than tiebreak.
    ident: dict[tuple, set] = {}
    for text, r in by_text.items():
        key = (r.name, r.fields.get("run", ""), r.fields.get("attempt", ""))
        ident.setdefault(key, set()).add(text)
    if any(len(texts) > 1 for texts in ident.values()):
        return None

    # Total, side-order-independent ordering. run is valid ISO ⇒ chronological;
    # attempt sorts NUMERICALLY (10 after 2), 0 fallback for missing/non-numeric.
    def _attempt_int(r) -> int:
        a = r.fields.get("attempt", "")
        return int(a) if a.isdigit() else 0

    ordered = sorted(
        by_text.items(),
        key=lambda kv: (kv[1].fields.get("run", ""), kv[1].name,
                        _attempt_int(kv[1]), kv[0]),
    )
    blocks = "\n\n".join(text for text, _r in ordered)
    merged_section = (
        f"{gate_ledger.SECTION_HEADER}\n{gate_ledger.SECTION_COMMENT}\n\n{blocks}\n"
    )

    # Compare heads ignoring trailing blank lines — the side carrying the ledger
    # includes the blank lines that preceded '## Gate Runs' while a side without a
    # ledger does not, yet the prose is identical. Rebuild with one canonical
    # blank line before the section.
    if local_head.rstrip("\n") == remote_head.rstrip("\n"):
        head_norm = local_head.rstrip("\n")
        merged = (head_norm + "\n\n" + merged_section) if head_norm else merged_section
        return merged, True
    # Prose head genuinely conflicts; still union the machine-owned ledger and
    # leave the head on the conflict-marker path for manual resolution.
    return _conflict_markers(local_head, remote_head) + merged_section, False


def merge_body(local_body: str, remote_body: str) -> tuple[str, bool]:
    """Try to merge body content.

    Returns (merged_body, is_resolved).

    Concurrent appends to the append-only ``## Gate Runs`` ledger (a gate passed
    from a different PC than the lock-holder) are union-merged automatically when
    safe. Any other body divergence — or an unsafe ledger — wraps both sides in
    conflict markers and returns is_resolved=False.
    """
    if local_body == remote_body:
        return local_body, True

    union = _union_gate_runs(local_body, remote_body)
    if union is not None:
        return union

    return _conflict_markers(local_body, remote_body), False


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
    parser.add_argument(
        "--rebase", action="store_true",
        help="Swap LOCAL/REMOTE sides (during git rebase, conflict marker "
             "sides are inverted: LOCAL=upstream, REMOTE=our commits)",
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

    # During git rebase, conflict marker sides are inverted:
    # LOCAL (<<<) = upstream/remote, REMOTE (>>>) = our local commits.
    # Swap to restore the intuitive meaning for merge rules.
    if args.rebase:
        local_content, remote_content = remote_content, local_content

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
