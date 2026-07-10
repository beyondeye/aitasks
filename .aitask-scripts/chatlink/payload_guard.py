"""Gateway-side payload validation (t1120_6 — pinned contract 7).

The agent's ``payload.json`` is **untrusted input** (prompt-influenced
agent). This module is the single validation sink the flow runs before any
``aitask_create.sh`` call. Ownership split pinned in ``relay.py``
(``TaskPayload`` docstring): the shared schema class owns shape (required
fields, no extra keys, types, size limits, level enums); this guard layers
the **repo-authoritative** checks the sandboxed producer must not own:

- ``issue_type`` ∈ ``aitasks/metadata/task_types.txt``
- ``labels`` ⊆ ``aitasks/metadata/labels.txt`` (``aitask_create.sh``
  auto-adds unknown labels rather than rejecting — so subset enforcement
  MUST happen here)
- control characters: **detect-and-reject, never sanitize** — the gateway
  only ever creates a task from the byte-identical submitted values.
  ``title`` allows no Cc code point and none of the zero-width/bidi
  formatting chars (U+200B–U+200F, U+202A–U+202E, U+2066–U+2069);
  ``description`` allows exactly ``\\n`` and ``\\t`` of that set.

**Reject fail-closed**: any violation raises :class:`PayloadRejected` with
a machine-readable reason (thread + audit) — never partial creation, never
"fix-up".
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

from .relay import TaskPayload, ValidationError

#: Zero-width / bidi-control formatting code points rejected everywhere.
_FORMAT_FORBIDDEN = frozenset(
    [chr(c) for c in range(0x200B, 0x2010)]  # U+200B–U+200F
    + [chr(c) for c in range(0x202A, 0x202F)]  # U+202A–U+202E
    + [chr(c) for c in range(0x2066, 0x206A)]  # U+2066–U+2069
)


class PayloadRejected(Exception):
    """Fail-closed rejection; ``reason`` is machine-readable for
    thread + audit."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _forbidden_chars(text: str, *, allow: frozenset = frozenset()) -> bool:
    """True if ``text`` contains a Cc control or forbidden formatting
    char not in ``allow``."""
    for ch in text:
        if ch in allow:
            continue
        if unicodedata.category(ch) == "Cc" or ch in _FORMAT_FORBIDDEN:
            return True
    return False


def _read_allowlist(path: Path) -> frozenset:
    """Non-empty, non-comment lines of a metadata allowlist file."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        # Fail-closed: an unreadable allowlist validates nothing.
        raise PayloadRejected(f"allowlist unreadable: {path.name}") from exc
    return frozenset(
        line.strip() for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    )


def validate_payload(raw: dict | None, metadata_dir: str | Path) -> TaskPayload:
    """Validate an untrusted payload dict; return the typed payload.

    Raises :class:`PayloadRejected` on any violation. ``metadata_dir`` is
    the repo's ``aitasks/metadata`` directory (test seam).
    """
    if raw is None:
        raise PayloadRejected("payload missing or unreadable")
    try:
        payload = TaskPayload.from_dict(raw)
    except ValidationError as exc:
        raise PayloadRejected(f"schema: {exc}") from exc

    metadata_dir = Path(metadata_dir)
    issue_types = _read_allowlist(metadata_dir / "task_types.txt")
    if payload.issue_type not in issue_types:
        raise PayloadRejected(f"issue_type not allowed: {payload.issue_type!r}")
    labels = _read_allowlist(metadata_dir / "labels.txt")
    unknown = [l for l in payload.labels if l not in labels]
    if unknown:
        raise PayloadRejected(f"labels not allowed: {unknown!r}")

    if _forbidden_chars(payload.title):
        raise PayloadRejected("control characters in title")
    if _forbidden_chars(payload.description, allow=frozenset("\n\t")):
        raise PayloadRejected("control characters in description")
    return payload
