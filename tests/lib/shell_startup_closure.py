#!/usr/bin/env python3
"""Derive a shell script's startup ``source`` closure from the source itself.

A test fixture that copies framework shell scripts into a synthetic project must
also copy every library those scripts source **at startup**, or the fixture dies
at source time — with a bare ``No such file or directory`` from inside
``task_utils.sh`` — rather than at the assertion the test is actually about.

Hand-maintained copy lists drift. ``stale_lock.sh`` joined
``lib/task_utils.sh``'s startup chain in t1725_1; the shared shell scaffold
(``tests/lib/test_scaffold.sh``) was extended, but ``tests/test_desync_state.py``
kept a private list that was not, and the suite went red (t1745). The fixture's
own comment warned that the list had to be maintained by hand — the warning was
there and was not acted on, which is why this module derives the list instead.

``tests/lib/test_scaffold.sh`` is the shell suites' answer to this problem; this
module is the Python one.

The recognised shape
--------------------
A **startup lib source** is an *unconditional* ``source`` of a sibling library,
written at **column 0**, in one of the three spellings that appear in the tree::

    source "${SCRIPT_DIR}/lib/foo.sh"
    source "$(dirname "${BASH_SOURCE[0]}")/foo.sh"
    source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/foo.sh"

Anything indented is treated as lazy — the framework's lazy sources all live
inside function bodies (``task_utils.sh``'s ``_ait_load_automerge()``,
``terminal_compat.sh``'s tmux helper) and must NOT be copied.

**This is a convention, deliberately, not an inference.** Bash attaches no
meaning to indentation, so column 0 does not *prove* a source runs at startup.
Classifying by lexical function-body depth instead was prototyped and rejected:
it falsely flags a top-level conditional source —
``if [[ -r … ]]; then source "${SCRIPT_DIR}/lib/opt.sh"; fi`` — which is
idiomatic for optional libs and semantically a startup source. A bespoke
shell-depth parser would turn a legitimate future edit into a suite-wide failure
unrelated to the behavior under test.

What this does not buy
----------------------
A startup source written *indented* is outside the recognised shape and will not
be picked up. That case is handled by the documented contract, not by code: a
lib needed at startup is sourced unconditionally at column 0, and anything that
genuinely must be conditional is also added to the consuming fixture's explicit
extras. See the ``source-on-startup`` bullet in
``aidocs/framework/shell_conventions.md``.

``nonconforming_column0_sources()`` backs the contract test that keeps the
convention honest across every scanned file.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable

__all__ = [
    "STARTUP_SOURCE_RE",
    "COLUMN0_SOURCE_RE",
    "startup_sources",
    "startup_closure",
    "copy_startup_closure",
    "nonconforming_column0_sources",
]

#: A startup lib source: column 0, unconditional, one of three spellings.
STARTUP_SOURCE_RE = re.compile(
    r'^source[ \t]+"(?:'
    r"\$\{?SCRIPT_DIR\}?/lib/"
    r'|\$\(dirname "\$\{BASH_SOURCE\[0\]\}"\)/'
    r'|\$\(cd "\$\(dirname "\$\{BASH_SOURCE\[0\]\}"\)" && pwd\)/'
    r')(?P<name>[A-Za-z0-9_]+\.sh)"[ \t]*$'
)

#: Loose shape used ONLY by the contract test: any column-0 ``source``/``.``
#: line, whatever it targets.
COLUMN0_SOURCE_RE = re.compile(r"^(?:source|\.)[ \t]+\S")


def startup_sources(path: Path) -> list[str]:
    """Lib basenames that ``path`` sources at startup, in file order."""
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = STARTUP_SOURCE_RE.match(line)
        if match:
            names.append(match.group("name"))
    return names


def startup_closure(lib_dir: Path, roots: Iterable[Path]) -> list[str]:
    """Names under `lib_dir` that `roots` source at startup, transitively.

    Returns them sorted. Raises `AssertionError` when the closure comes out
    empty (a pattern that has stopped matching must fail loudly, not silently
    copy nothing — that is the very bug this module exists to prevent) or when a
    referenced name is missing under `lib_dir` (so a typo cannot degrade into a
    silent omission either).
    """
    roots = list(roots)
    seen: set[str] = set()
    pending: list[tuple[str, Path]] = []
    for root in roots:
        for name in startup_sources(root):
            pending.append((name, root))

    while pending:
        name, referrer = pending.pop()
        if name in seen:
            continue
        target = lib_dir / name
        if not target.is_file():
            raise AssertionError(
                f"{referrer} sources {name!r} at startup, but "
                f"{target} does not exist"
            )
        seen.add(name)
        for dep in startup_sources(target):
            pending.append((dep, target))

    if not seen:
        raise AssertionError(
            "startup source closure is empty for roots "
            f"{[str(r) for r in roots]} — STARTUP_SOURCE_RE no longer matches "
            "the tree's source lines"
        )
    return sorted(seen)


def copy_startup_closure(
    src_lib: Path, dst_lib: Path, roots: Iterable[Path]
) -> list[str]:
    """Copy the startup closure of `roots` from `src_lib` into `dst_lib`.

    Returns the names copied. `dst_lib` must already exist.
    """
    names = startup_closure(src_lib, roots)
    for name in names:
        shutil.copy2(src_lib / name, dst_lib / name)
    return names


def nonconforming_column0_sources(path: Path) -> list[tuple[int, str]]:
    """Column-0 ``source`` lines in `path` outside the recognised shape.

    A plain line filter, not a parser: it models no bash construct, so it cannot
    misread a conditional, a brace group or a ``case``. Used only by the format
    contract test — never to classify during a fixture build.

    Returns ``(line_number, stripped_line)`` pairs.
    """
    bad: list[tuple[int, str]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if COLUMN0_SOURCE_RE.match(line) and not STARTUP_SOURCE_RE.match(line):
            bad.append((number, line.strip()))
    return bad
