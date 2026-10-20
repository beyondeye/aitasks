#!/usr/bin/env python3
"""gate_result_carrier.py - sanitize the gate result carrier (t1859_1, M8.1).

``run_command_gate`` (lib/gate_verifier_lib.sh) exports
``AIT_GATE_RESULT_FILE`` to the project command; whatever one line the command
leaves there becomes the gate-run block's ``result=`` field. That value is
rendered verbatim as a ``> Result: <v>`` body line, so it must be ONE line by
the ledger READERS' rules, not by bash's:

  * the readers split with Python ``str.splitlines()``
    (``ledger_block.parse_blocks``, ``gate_ledger.py``), which also breaks on
    U+0085, U+2028, U+2029, \\v, \\f and \\x1c-\\x1e. A value that is one line
    to ``read``/``tr`` can therefore smuggle a second line that parses as a
    forged ``> **✅ gate:<name>** ... status=pass`` marker;
  * ``aitask_gate.sh append`` writes through bash/awk, byte for byte, and every
    reader opens the task file as strict UTF-8 -- one invalid byte would make
    the whole ledger unreadable.

So the sanitizer decodes with ``errors="replace"`` (the output is always valid
UTF-8), keeps the first line by ``str.splitlines`` itself, and drops every
character the readers could treat as a line boundary -- derived from
``splitlines`` rather than enumerated, so a boundary a future Python adds is
still removed -- plus every control / format / separator character.

CLI:  gate_result_carrier.py <file> <max-chars>
      prints the sanitized value with no trailing newline (empty when there is
      none). Exit 0; 3 on a usage or read error -- the caller then keeps the
      fixed result text.
"""

from __future__ import annotations

import sys
import unicodedata

# Never read more than this from the carrier file: it is one line of status
# text, and a runaway writer must not cost memory or time.
READ_LIMIT = 64 * 1024

_DROP_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})


def _is_line_boundary(ch: str) -> bool:
    return len(("a" + ch + "b").splitlines()) > 1


def _keep(ch: str) -> bool:
    return unicodedata.category(ch) not in _DROP_CATEGORIES and not _is_line_boundary(ch)


def sanitize(raw: bytes, max_len: int) -> str:
    """Return the one-line, reader-safe carrier value ("" when there is none)."""
    text = raw[:READ_LIMIT].decode("utf-8", errors="replace")
    lines = text.splitlines()
    first = lines[0] if lines else ""
    out = "".join(ch for ch in first if _keep(ch)).strip()
    out = out[:max(0, max_len)].strip()
    # The whole point of this module: never hand the ledger more than one line.
    assert len(out.splitlines()) <= 1, "carrier sanitizer produced a line break"
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: gate_result_carrier.py <file> <max-chars>\n")
        return 3
    path, max_arg = argv
    try:
        max_len = int(max_arg)
    except ValueError:
        sys.stderr.write(f"gate_result_carrier.py: invalid max-chars: {max_arg}\n")
        return 3
    try:
        with open(path, "rb") as fh:
            raw = fh.read(READ_LIMIT)
    except OSError as exc:
        sys.stderr.write(f"gate_result_carrier.py: {exc}\n")
        return 3
    # Bytes, not text: under LC_ALL=C sys.stdout is ASCII and would raise on the
    # first non-ASCII character (U+FFFD included).
    sys.stdout.buffer.write(sanitize(raw, max_len).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
