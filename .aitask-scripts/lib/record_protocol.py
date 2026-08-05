"""record_protocol.py - the `|`-delimited line-protocol safety policy (t1433).

Several `lib/` modules emit a line-oriented `KEY:value` protocol whose fields are
separated by `|` and whose records are separated by newlines. There is **no
escaping engine**, so a value carrying `|`, CR or LF would make the record
boundary undecidable. This module owns the one policy that keeps it decidable;
its consumers own their own *reactions* to a violation.

Why it exists
-------------
The policy used to live in three private copies: `lib/work_report_gather.py` and
`lib/trail_gather.py` carried a byte-identical six-symbol block, and t1377_1
added a third partial copy to `lib/board_columns.py` rather than importing the
second. The objection to importing was **ownership**, and it was a fair one: a
`|`-delimited protocol predicate does not belong in a board-column module, and
`trail_gather.py` should not import from a board module to get it. The answer is
a neutral home, which is this file.

Drift here is unlikely — the reserved set is fixed by the wire protocol — but the
failure mode is silent: a protocol change would have to find every copy, and a
missed one lets a record-breaking character into a `|`-delimited stream where no
reader can tell it from a separator.

**Not a public API.** These names are generic and this is an internal
deduplication, not a declared seam: there is no compatibility policy and no
promise to callers outside `lib/`. Deliberately no `__all__` — advertising one
would imply a stability commitment this module does not make. (Contrast
`board_columns.py`, which does declare `__all__` because it *is* a seam with
headless callers.)

Dependency-free, on purpose
---------------------------
This module imports **nothing** — not even stdlib. `board_columns.py` imports it
and is itself imported by `board/aitask_board.py` at module scope, so anything
reachable from here lands on the board's startup path.
`tests/test_record_protocol.py` asserts the zero-import property structurally
(via `ast`), because a future import would otherwise be invisible until someone
measured board startup. `lib/board_ordering.py` is the precedent.

The last-field / middle-field asymmetry is load bearing
-------------------------------------------------------
:func:`sanitize_last_field` deliberately **preserves** `|`; only
:func:`sanitize_middle_field` strips it. That is not an oversight:

* Consumers split each record with a **fixed maxsplit**, so everything after the
  final separator is one field no matter how many `|` it contains. Putting the
  free-text value last is exactly what buys that.
* Column *titles* and file *paths* legitimately contain `|`. Stripping it from
  them would silently corrupt real data and make the field ordering pointless.

So the field's **position** decides its policy, and the two function names say
which position they are for. Getting this backwards was a real defect caught
during t1377_1 review.

Sanitize at the **write** site
------------------------------
A delimited encoding is undecidable on read: once a stray `|` is in the stream,
nothing downstream can tell it from a separator. So values are sanitized where
the record is produced, never where it is parsed.

Degrade or refuse — the consumer decides
----------------------------------------
This module only *classifies* and *rewrites*; it never exits. Two reactions
exist in the callers, and the choice is theirs:

* **Degrade** — a cosmetic value (a colour) is rewritten and the run continues.
* **Refuse** — a load-bearing identifier (a column id) is fatal.

`_die` and the module-specific stderr prefixes (`work_report_gather: `,
`trail_gather: `, `board_columns: `) stay in the consumers on purpose. A library
path must not `sys.exit` inside a TUI, and those prefixes are pinned by
characterization tests with negative controls asserting this module's name does
*not* appear in the message.

CRLF is one line break, so it collapses to one space (t1433)
------------------------------------------------------------
The two gatherers' `_free_text` replaced `"\\r\\n"` first and so turned a CRLF
into a single space; `board_columns._line_safe` replaced CR and LF
independently and turned it into two. Both were *safe*, but they were not the
same function, and both behaviours were pinned by tests. :func:`sanitize_last_field`
unifies on the collapsing policy: a CRLF is one line break and becomes one
space. The two-space result was an accident of replacement ordering. This
changed one observable byte sequence — `aitask_board_column.sh list-columns`
renders a CRLF-bearing title with one space instead of two — which is the single
intended behaviour change in t1433.
"""

#: Characters that cannot round-trip a `|`-delimited, newline-terminated record.
RECORD_BREAKING = ("|", "\r", "\n")

#: A fixed-position field whose value is present but cannot round-trip.
INVALID_ENUM = "invalid"

#: A fixed-position field with no value at all.
UNKNOWN_ENUM = "unknown"


def has_record_breaking(value: str) -> bool:
    """True when `value` carries any character that would break a record.

    The classifier only. Callers decide whether that means degrade or refuse.
    """
    return any(ch in value for ch in RECORD_BREAKING)


def sanitize_last_field(value: str) -> str:
    """Sanitize the **last** field of a record: CR/LF only — `|` SURVIVES.

    `|` is preserved because the last field is recovered with a fixed maxsplit,
    so a title or path may legitimately contain one (see the module docstring).
    CR/LF would break the line protocol itself, so they become a space; a CRLF
    pair is one line break and collapses to a single space.
    """
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def sanitize_middle_field(value: str) -> str:
    """Sanitize a **middle** field: `|` as well as CR/LF.

    A middle field is delimited on both sides, so a `|` inside it would shift
    every following field. Middle fields are cosmetic in practice (a colour), so
    a bad value degrades here rather than failing the run — a bad *identifier*
    stays fatal in the caller.
    """
    return sanitize_last_field(value).replace("|", "")


def enum_field(value) -> str:
    """A fixed-position enum-ish field: absent -> `unknown`, unsafe -> `invalid`.

    Distinguishing the two matters to readers: `unknown` means the source had no
    value, `invalid` means it had one that could not be transported. Collapsing
    them would erase that difference at the only point it is still knowable.
    """
    if value is None or value == "":
        return UNKNOWN_ENUM
    text = str(value)
    return INVALID_ENUM if has_record_breaking(text) else text
