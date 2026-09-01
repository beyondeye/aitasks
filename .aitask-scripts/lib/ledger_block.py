#!/usr/bin/env python3
"""Generic marker-block ledger substrate (t1657_1).

An *append-only marker-block ledger* is a ``##`` section of a task file holding
blockquote records of the form::

    > **<icon> <namespace>:<name>** key=value key=value
    >
    > <body line>
    > <body line>

``## Gate Runs`` (namespace ``gate``) was the first such ledger; ``## Inbox``
(namespace ``note``, t1657_2) is the second. This module owns the parts that are
genuinely common to both — the marker grammar, the block envelope, section
ensure-and-append, and the atomic write — so a second consumer is built ON this
seam rather than beside it.

**What deliberately does NOT live here.** Everything a *particular* ledger means
by its records stays with that ledger: the key vocabulary, status/icon mapping,
attempt arithmetic, body label tables, and any derivation over the parsed
blocks. ``gate_ledger`` keeps ``ICONS``, ``TERMINAL_STATUSES``, ``next_attempt``,
``BODY_KEYS`` and the whole derive/registry half. Moving those here would invert
the dependency (this module would import its own consumer) and would be
speculative abstraction besides.

The division shows up in the two rendering entry points:

* :func:`render_block` resolves **nothing**. It is handed a namespace, a name, an
  icon, an already-ordered ``(key, value)`` sequence and already-rendered body
  lines, and concatenates them. Every default, lookup and label mapping belongs
  to the caller.
* :func:`parse_blocks` takes the namespace as a parameter and an optional record
  factory, so ``gate_ledger`` can keep returning its own ``GateRun`` type with the
  gate-specific accessors it has always had.

Stdlib only, matching ``gate_ledger``'s constraint: this substrate has to work
where PyYAML is unavailable.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
import os
import re

# Namespace and record-name charsets. The name charset is what makes both
# `gate:review_approved` and `note:t349` valid.
_NAMESPACE_CHARS = r"[A-Za-z0-9_]+"
_NAME_CHARS = r"[A-Za-z0-9_]+"

#: ``key=value`` pairs on a marker line. Values are whitespace-delimited.
KV_RE = re.compile(r"(\w+)=(\S+)")

#: ``> Label: value`` body lines. Shared by every namespace; what the labels
#: *mean* is the consumer's business.
BODY_FIELD_RE = re.compile(r"^>\s*([^:>\n][^:\n]*):\s*(.*?)\s*$")

#: A markdown section header, used to bound a section during append.
SECTION_HEADER_RE = re.compile(r"^##\s+")


def build_marker_re(namespace: str) -> re.Pattern:
    """Full marker matcher for ``namespace``: groups are (icon, name, tail)."""
    return re.compile(
        rf"^>\s*\*\*(\S+)\s+{namespace}:({_NAME_CHARS})\*\*(.*)$")


def build_marker_search_re(namespace: str) -> re.Pattern:
    """Cheap multiline prefilter for ``namespace`` markers anywhere in a text."""
    return re.compile(
        rf"(?m)^>\s*\*\*\S+\s+{namespace}:{_NAME_CHARS}\*\*")


def _normalize_body_key(label: str) -> str:
    """Normalize a rendered blockquote label to a stable dict key."""
    return re.sub(r"[^A-Za-z0-9]+", "_", label.strip().lower()).strip("_")


def _strip_wrapping_backticks(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
        return value[1:-1]
    return value


def iso_now() -> str:
    """Current UTC timestamp as ISO-8601-Z (second precision)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class LedgerBlock:
    """One parsed marker block, namespace-agnostic.

    Field order and names match ``gate_ledger.GateRun`` exactly: that type is a
    consumer-side specialization adding gate vocabulary (``status``, ``run_id``,
    ``attempt``), and :func:`parse_blocks` builds whichever the caller asks for.
    """

    name: str
    icon: str
    fields: dict[str, str]
    body_fields: dict[str, str] = field(default_factory=dict)
    line_number: int = 0
    raw_marker: str = ""
    raw_body_lines: tuple[str, ...] = ()


def has_markers(text: str, namespace: str, search_re: re.Pattern | None = None) -> bool:
    """Cheap prefilter: does ``text`` contain any ``namespace`` marker?

    Pass ``search_re`` to reuse a module-level compiled pattern.
    """
    pattern = search_re if search_re is not None else build_marker_search_re(namespace)
    return bool(pattern.search(text))


def parse_blocks(text: str, namespace: str, factory=LedgerBlock,
                 marker_re: re.Pattern | None = None) -> list:
    """Return every ``namespace`` marker block in file order.

    ``factory`` is called with the seven keyword fields of :class:`LedgerBlock`,
    so a consumer can receive its own record type. ``marker_re`` lets a consumer
    pass a pattern it already compiled at module level.

    A block runs from its marker line to the next marker, the next ``##``
    section header, or a non-blockquote non-blank line — whichever comes first.
    Blank lines inside a block are skipped rather than terminating it.
    """
    pattern = marker_re if marker_re is not None else build_marker_re(namespace)
    blocks: list = []
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        m = pattern.match(line)
        if not m:
            idx += 1
            continue

        marker_line_number = idx + 1
        raw_body: list[str] = []
        body_fields: dict[str, str] = {}
        idx += 1
        while idx < len(lines):
            nxt = lines[idx]
            if pattern.match(nxt) or SECTION_HEADER_RE.match(nxt):
                break
            if nxt.startswith(">"):
                raw_body.append(nxt)
                bm = BODY_FIELD_RE.match(nxt)
                if bm:
                    key = _normalize_body_key(bm.group(1))
                    if key:
                        body_fields[key] = _strip_wrapping_backticks(bm.group(2))
                idx += 1
                continue
            if not nxt.strip():
                idx += 1
                continue
            break

        blocks.append(factory(
            name=m.group(2),
            icon=m.group(1),
            fields=dict(KV_RE.findall(m.group(3))),
            body_fields=body_fields,
            line_number=marker_line_number,
            raw_marker=line,
            raw_body_lines=tuple(raw_body),
        ))
    return blocks


def render_block(namespace: str, name: str, icon: str, marker_kv, body_lines) -> str:
    """Render one marker block (no trailing newline).

    Resolves nothing: ``marker_kv`` is an already-ordered sequence of
    ``(key, value)`` pairs and ``body_lines`` are already-rendered ``>``-prefixed
    strings. Defaults, icon lookup, attempt arithmetic and label mapping are the
    caller's, which is what keeps this module free of any consumer's vocabulary.
    """
    marker = f"> **{icon} {namespace}:{name}**"
    for key, value in marker_kv:
        marker += f" {key}={value}"

    block = marker
    if body_lines:
        block += "\n>\n" + "\n".join(body_lines)
    return block


def append_to_section(text: str, block: str, *, header: str, comment: str,
                      create_before: str | None = None,
                      append_at: str = "eof") -> str:
    """Return ``text`` with ``block`` appended to the ``header`` section.

    The section is created when absent. Two placement knobs, because a ledger
    that is not the file's last section needs different answers than one that is:

    ``create_before``
        Header text (e.g. ``"## Gate Runs"``) before which a *newly created*
        section is inserted. ``None`` creates it at EOF. This is what lets
        ``## Inbox`` land above ``## Gate Runs``.

    ``append_at``
        ``"eof"`` appends the block at end of file — the gate ledger's historical
        behaviour, correct because it is the terminal section, and preserved
        exactly so this extraction changes no bytes. ``"section_end"`` appends at
        the end of the section itself (before the next ``##`` header), which is
        what a non-terminal ledger requires.
    """
    if append_at not in ("eof", "section_end"):
        raise ValueError(f"append_at must be 'eof' or 'section_end', got {append_at!r}")

    out = text
    if not out.endswith("\n"):
        out += "\n"

    header_re = re.compile(rf"(?m)^{re.escape(header)}\s*$")
    m = header_re.search(out)

    if not m:
        section = f"\n{header}\n{comment}\n"
        if create_before is None:
            return out + section + f"\n{block}\n"
        anchor = re.compile(rf"(?m)^{re.escape(create_before)}\s*$").search(out)
        if anchor is None:
            return out + section + f"\n{block}\n"
        at = anchor.start()
        return out[:at] + section.lstrip("\n") + f"\n{block}\n\n" + out[at:]

    if append_at == "eof":
        return out + f"\n{block}\n"

    # section_end: insert before the next '##' header after this one, else EOF.
    nxt = re.compile(r"(?m)^##\s+").search(out, m.end())
    at = nxt.start() if nxt else len(out)
    return out[:at].rstrip("\n") + f"\n\n{block}\n" + ("\n" + out[at:] if nxt else "")


def atomic_write(path: str, content: str) -> None:
    """Write content to path atomically via an adjacent tempfile + os.replace.

    The task file lives under the ``aitasks/`` *directory* symlink but is itself
    a regular file, so replacing it in place keeps the data-worktree layout
    intact. The tempfile is created in the same directory to keep the rename on
    one filesystem (truly atomic).
    """
    d = os.path.dirname(path) or "."
    tmp = os.path.join(d, f".aitask_gate.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


#: Historical name. ``gate_ledger`` re-exports it, and ``gate_registry_sync.py``
#: calls ``gl._atomic_write`` directly, so the private spelling must resolve to
#: the same object here.
_atomic_write = atomic_write
