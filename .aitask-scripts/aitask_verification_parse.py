#!/usr/bin/env python3
"""Parse and mutate the ``## Verification Checklist`` section of a task file.

Foundational state primitive for the manual-verification module (t583). All
mutations write atomically via a temp file + os.replace().
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

STATE_BY_MARKER = {
    " ": "pending",
    "x": "pass",
    "fail": "fail",
    "skip": "skip",
    "defer": "defer",
}

MARKER_BY_STATE = {v: k for k, v in STATE_BY_MARKER.items()}

TERMINAL_STATES = {"pass", "fail", "skip"}
VALID_SET_STATES = {"pass", "fail", "skip", "defer", "pending"}

SECTION_RE = re.compile(r"^## (verification( checklist)?|checklist)\s*$", re.IGNORECASE)
ITEM_RE = re.compile(r"^([ \t]*)- \[([ x]|fail|skip|defer)\][ \t]+(.*)$")
H2_RE = re.compile(r"^## ")
SUFFIX_SPLIT = " \u2014 "


def _die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _read_task_file(path: Path) -> Tuple[List[str], List[str]]:
    """Return (frontmatter_lines, body_lines). Both lists include no trailing newlines.

    frontmatter_lines includes the opening and closing ``---`` delimiters. If the
    file has no frontmatter, frontmatter_lines is empty and body_lines is the
    entire file.
    """
    if not path.is_file():
        _die(f"task file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    lines = raw.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines or lines[0].strip() != "---":
        return [], lines
    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close_idx = i
            break
    if close_idx is None:
        _die("frontmatter missing closing '---'")
    return lines[: close_idx + 1], lines[close_idx + 1 :]


def _write_task_file(path: Path, frontmatter: List[str], body: List[str]) -> None:
    parts = list(frontmatter) + list(body)
    text = "\n".join(parts) + "\n"
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".", dir=str(path.parent)
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _update_updated_at(frontmatter: List[str]) -> List[str]:
    """Set ``updated_at`` in frontmatter to the current local time."""
    if not frontmatter:
        return frontmatter
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = list(frontmatter)
    found = False
    for i in range(1, len(out) - 1):
        if re.match(r"^updated_at:\s*", out[i]):
            out[i] = f"updated_at: {stamp}"
            found = True
            break
    if not found:
        out.insert(len(out) - 1, f"updated_at: {stamp}")
    return out


def _locate_section(body: List[str]) -> Optional[Tuple[int, int]]:
    """Return (start_idx_after_header, end_idx_exclusive) of first matching section, or None."""
    start = None
    for i, line in enumerate(body):
        if SECTION_RE.match(line):
            start = i + 1
            break
    if start is None:
        return None
    end = len(body)
    for j in range(start, len(body)):
        if H2_RE.match(body[j]):
            end = j
            break
    return start, end


def _strip_annotation(text: str) -> str:
    if SUFFIX_SPLIT in text:
        return text.split(SUFFIX_SPLIT, 1)[0].rstrip()
    return text


def _is_section_header(body: List[str], line_no: int, end: int, indent: str) -> bool:
    """A checklist line is a section header when its text ends with ``:`` and the
    next non-blank line inside the section is another item at a strictly deeper
    indent. Used by ``_iter_items`` to skip category bullets that only exist to
    group their nested children.
    """
    m = ITEM_RE.match(body[line_no])
    if m is None:
        return False
    text = _strip_annotation(m.group(3)).rstrip()
    if not text.endswith(":"):
        return False
    j = line_no + 1
    while j < end and body[j].strip() == "":
        j += 1
    if j >= end:
        return False
    nxt = ITEM_RE.match(body[j])
    if nxt is None:
        return False
    return len(nxt.group(1)) > len(indent)


def _iter_items(body: List[str]) -> List[Tuple[int, str, int, str]]:
    """Return list of (index, state, line_number, text) for each item in the first matching section.

    line_number is 1-indexed within the full body (matching original file line semantics:
    frontmatter lines are included in the count so the number maps to file lines when
    frontmatter_line_count is added by the caller).

    Section-header bullets (text ends with ``:`` and the next non-blank line is
    a deeper-indented item) are filtered out — they exist only to group their
    nested children and are not independently verifiable.
    """
    section = _locate_section(body)
    if section is None:
        return []
    start, end = section
    items: List[Tuple[int, str, int, str]] = []
    idx = 0
    for line_no in range(start, end):
        m = ITEM_RE.match(body[line_no])
        if not m:
            continue
        if _is_section_header(body, line_no, end, m.group(1)):
            continue
        idx += 1
        marker = m.group(2)
        state = STATE_BY_MARKER[marker]
        text = m.group(3)
        items.append((idx, state, line_no, text))
    return items


def cmd_parse(args: argparse.Namespace) -> int:
    path = Path(args.task_file)
    frontmatter, body = _read_task_file(path)
    fm_lines = len(frontmatter)
    items = _iter_items(body)
    for idx, state, body_line, text in items:
        file_line = fm_lines + body_line + 1
        print(f"ITEM:{idx}:{state}:{file_line}:{text}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    path = Path(args.task_file)
    _, body = _read_task_file(path)
    items = _iter_items(body)
    counts = {"pending": 0, "pass": 0, "fail": 0, "skip": 0, "defer": 0}
    for _, state, _, _ in items:
        counts[state] += 1
    total = len(items)
    print(
        f"TOTAL:{total} PENDING:{counts['pending']} PASS:{counts['pass']} "
        f"FAIL:{counts['fail']} SKIP:{counts['skip']} DEFER:{counts['defer']}"
    )
    return 0


def cmd_terminal_only(args: argparse.Namespace) -> int:
    path = Path(args.task_file)
    _, body = _read_task_file(path)
    items = _iter_items(body)
    pending = sum(1 for _, s, _, _ in items if s == "pending")
    deferred = sum(1 for _, s, _, _ in items if s == "defer")
    if pending == 0 and deferred == 0:
        return 0
    if pending:
        print(f"PENDING:{pending}")
    if deferred:
        print(f"DEFERRED:{deferred}")
    return 2


def cmd_set(args: argparse.Namespace) -> int:
    state = args.state
    if state not in VALID_SET_STATES:
        _die(f"invalid state: {state} (expected one of: {sorted(VALID_SET_STATES)})")
    path = Path(args.task_file)
    frontmatter, body = _read_task_file(path)
    items = _iter_items(body)
    if not items:
        _die("no verification checklist items found")
    target = None
    for item in items:
        if item[0] == args.index:
            target = item
            break
    if target is None:
        _die(f"item index out of range: {args.index} (have {len(items)})")
    idx, _, body_line, _ = target
    original = body[body_line]
    m = ITEM_RE.match(original)
    assert m is not None  # by construction
    indent = m.group(1)
    text = m.group(3)
    new_text = _strip_annotation(text).rstrip()
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    note = f" {args.note}" if args.note else ""
    annotation = f"{SUFFIX_SPLIT}{state.upper()} {stamp}{note}"
    new_marker = MARKER_BY_STATE[state]
    new_line = f"{indent}- [{new_marker}] {new_text}{annotation}"
    new_body = list(body)
    new_body[body_line] = new_line
    new_frontmatter = _update_updated_at(frontmatter)
    _write_task_file(path, new_frontmatter, new_body)
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    path = Path(args.task_file)
    frontmatter, body = _read_task_file(path)
    if _locate_section(body) is not None:
        _die("verification checklist section already exists")
    items_path = Path(args.items)
    if not items_path.is_file():
        _die(f"items file not found: {items_path}")
    raw_items = [
        ln.rstrip("\r") for ln in items_path.read_text(encoding="utf-8").split("\n")
    ]
    entries = [f"- [ ] {ln.strip()}" for ln in raw_items if ln.strip()]
    if not entries:
        _die("items file is empty (after skipping blank lines)")

    new_body = list(body)
    while new_body and new_body[-1] == "":
        new_body.pop()
    if new_body:
        new_body.append("")
    new_body.append("## Verification Checklist")
    new_body.append("")
    new_body.extend(entries)
    new_frontmatter = _update_updated_at(frontmatter)
    _write_task_file(path, new_frontmatter, new_body)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aitask_verification_parse",
        description="Parse and mutate verification checklist items in a task file.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="emit ITEM:<idx>:<state>:<line>:<text> per item")
    p_parse.add_argument("task_file")
    p_parse.set_defaults(func=cmd_parse)

    p_set = sub.add_parser("set", help="mutate a single item's state (with optional note)")
    p_set.add_argument("task_file")
    p_set.add_argument("index", type=int)
    p_set.add_argument("state", choices=sorted(VALID_SET_STATES))
    p_set.add_argument("--note", default=None)
    p_set.set_defaults(func=cmd_set)

    p_summary = sub.add_parser("summary", help="one-line TOTAL/PENDING/PASS/... counts")
    p_summary.add_argument("task_file")
    p_summary.set_defaults(func=cmd_summary)

    p_term = sub.add_parser(
        "terminal_only",
        help="exit 0 if all terminal (pass/fail/skip); else exit 2 with PENDING:/DEFERRED: lines",
    )
    p_term.add_argument("task_file")
    p_term.set_defaults(func=cmd_terminal_only)

    p_seed = sub.add_parser("seed", help="insert a fresh ## Verification Checklist section")
    p_seed.add_argument("task_file")
    p_seed.add_argument("--items", required=True, help="path to a file with one item per line")
    p_seed.set_defaults(func=cmd_seed)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
