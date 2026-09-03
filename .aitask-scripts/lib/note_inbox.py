#!/usr/bin/env python3
"""The ``## Inbox`` schema and the unread derivation (t1657_3).

Two consumers read a task's ``## Inbox``, and they must agree on exactly one
question: **is this block trustworthy?**

* ``board/aitask_merge.py`` asks it to decide whether a section can be unioned
  across PCs.
* the pick / task-workflow surfaces ask it, through
  ``aitask_query_files.sh inbox``, to decide what to show a code agent.

The schema below used to live only in the merger, where it ran **only inside
``merge_body``**. Nothing validated an ``## Inbox`` on any *read* path. A reader
that trusted block shape alone would let a malformed local receipt
(``mode=sideways``, a stray ``base=``, an unknown key) still carry ``ids=`` and
hide a real note -- with no merge ever involved to reject it. That is the
silently-vanished-note failure arriving by the one route the merger cannot see,
so the predicate moved here and both callers now share it.

**What is shared is the per-block predicate, NOT the disposition.** The two
callers must treat a bad block differently, and conflating them would break one
of them:

* merger -- "reject, never repair": one bad block bails the whole body to
  conflict markers rather than guessing.
* reader -- **per-block**: bailing the body here would hide every note in the
  file, the exact opposite of fail-safe. A bad receipt is discarded (so its
  ``ids=`` acknowledge nothing and the note stays *unread*); a bad note is not
  returned as a trustworthy claim but is reported separately, never silently
  dropped.

Stdlib only, matching ``ledger_block`` / ``gate_ledger``: this has to work where
PyYAML is unavailable.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger_block  # noqa: E402
from ledger_block import ISO_INSTANT_RE  # noqa: E402

#: The marker namespace both notes and receipts live in.
NAMESPACE = "note"

#: The block name that makes a block a **read receipt** rather than a note.
#:
#: This is the whole note/receipt discriminator, and it is a reserved name
#: rather than a collision risk: a note's marker name must equal its sender
#: (``t<id>``), which can never be the bare word ``read``.
RECEIPT_NAME = "read"

SECTION_HEADER = "## Inbox"
SECTION_COMMENT = ("<!-- Appended by the note framework. Do not edit by hand; "
                   "use `./ait note`. -->")

# --- Identity and provenance value shapes ----------------------------------
#
# Note ids are "<iso-utc>.<24-hex>"; every entry also carries an ISO "at=".
_NOTE_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\.[0-9a-f]{24}$")
_LOCAL_TASK_RE = re.compile(r"^t[0-9]+(_[0-9]+)?$")
# aidocs/framework/cross_repo_references.md: the 't' after '#' is tolerated.
_XREPO_TASK_RE = re.compile(r"^[a-z0-9_-]+#t?([0-9]+(?:_[0-9]+)?)$")
# A full object id, never an abbreviation. Both widths are accepted because the
# merge may run in a fixture or a format-less context, where binding to
# `git rev-parse --show-object-format` would leave NO rule at all; it degrades
# to weaker-but-never-absent, never to accepting a short value. The WRITER pins
# the exact width at the write site, which stays the stronger check.
_FULL_OID_RE = re.compile(r"^([0-9a-f]{40}|[0-9a-f]{64})$")
_BASE_SENTINELS = ("none", "unknown")
# claimed_at carries the original note's own precision: a date, or an instant.
_ISO_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$")


def _valid_oid(value: str) -> bool:
    return bool(_FULL_OID_RE.match(value))


# Allowed marker keys, per variant. An unknown key is REJECTED, not ignored
# (t1657_2 F20): the contract is "reject, never repair", and a permissive
# validator silently accepts exactly the blocks it exists to catch --
# `migrated=no` (claiming the migration variant without taking it),
# `claimed_at=<garbage>` on an ordinary note, or any future writer's key this
# version cannot interpret. Ignoring those would union a block whose meaning
# this code does not actually understand.
NOTE_KEYS_REQUIRED = {"id", "from", "at", "base", "dirty", "host"}
NOTE_KEYS_OPTIONAL = {"from_verified", "base_branch", "base_mergebase"}
MIGRATED_KEYS_REQUIRED = {"id", "from", "at", "base", "claimed_at", "migrated"}
MIGRATED_KEYS_OPTIONAL = {"base_branch", "base_mergebase"}
RECEIPT_KEYS_REQUIRED = {"id", "by", "at", "mode", "ids"}
RECEIPT_KEYS_OPTIONAL: set = set()

#: The acknowledgement modes a receipt may claim. `explicit` is a human choosing
#: "Acknowledge"; `auto` is a headless run acknowledging on their behalf, and is
#: recorded distinctly so the difference stays auditable rather than invisible.
RECEIPT_MODES = ("auto", "explicit")


def _keys_allowed(f, required: set, optional: set) -> bool:
    """Exact key-set membership: every required key present, no extras."""
    keys = set(f.keys())
    return required <= keys and not (keys - required - optional)


def _validate_provenance(f) -> bool:
    """Provenance rules for a note block.

    Checking only id/at/sender would let a block carrying an ABBREVIATED
    ``base=451dd3af7`` pass and union -- exactly the ambiguity the full-oid
    invariant exists to prevent, arriving by the one route writer-side tests
    structurally cannot see: a block written on another PC.
    """
    base = f.get("base", "")
    if not base:
        return False
    base_is_sentinel = base in _BASE_SENTINELS
    if not base_is_sentinel and not _valid_oid(base):
        return False

    # No repo / no HEAD => no branch. Required with a real oid, forbidden with
    # a sentinel -- either way the field and the base agree or the block is
    # malformed.
    has_branch = "base_branch" in f
    if base_is_sentinel and has_branch:
        return False
    if not base_is_sentinel and not has_branch:
        return False

    if "base_mergebase" in f:
        if base_is_sentinel or not _valid_oid(f["base_mergebase"]):
            return False

    if "migrated" in f:
        # Migration variant: provenance is CLAIMED, not observed. dirty/host/
        # from_verified are forbidden -- none of the three was ever measured,
        # and writing dirty=no on a historical note would fabricate an
        # observation. Absence here is the contract, not an omission.
        #
        # Keyed on PRESENCE, not on == "yes": `migrated=no` is not an ordinary
        # note, it is a malformed one. Falling through to the ordinary branch
        # would accept a block claiming a variant it does not satisfy.
        if f["migrated"] != "yes":
            return False
        if not _ISO_DATE_RE.match(f.get("claimed_at", "")):
            return False
        return _keys_allowed(f, MIGRATED_KEYS_REQUIRED, MIGRATED_KEYS_OPTIONAL)

    # 'unknown' IFF base=none, fail-closed in BOTH directions: yes/no with no
    # repository is a fabricated observation, and 'unknown' with a real base is
    # a refusal to measure something measurable. On an unborn branch
    # (base=unknown) `git status` still reports, so dirty is measured there.
    dirty = f.get("dirty", "")
    if dirty not in ("yes", "no", "unknown"):
        return False
    if (dirty == "unknown") != (base == "none"):
        return False

    host = f.get("host", "")
    if not host or any(c.isspace() for c in host):
        return False
    return _keys_allowed(f, NOTE_KEYS_REQUIRED, NOTE_KEYS_OPTIONAL)


def is_receipt(b) -> bool:
    """True if this block claims to be a read receipt rather than a note.

    Claims only -- shape, not trustworthiness. A block can be a receipt by name
    and still fail :func:`validate_block`, and the two callers need to tell
    those apart: a malformed *receipt* acknowledges nothing, which is different
    from it being a malformed *note*.
    """
    return b.name == RECEIPT_NAME


def validate_block(b) -> bool:
    """Is this ``## Inbox`` block trustworthy?

    The single predicate shared by the merger (which bails the whole body on a
    False) and the inbox reader (which drops just this block). Disposition is
    the caller's; the judgement is here.

    ``identity`` on the merge side is ``(id,)``, so a block with a missing
    ``id`` would key on ``("",)`` and two unrelated malformed blocks would
    collide as one entry.
    """
    f = b.fields
    if not _NOTE_ID_RE.match(f.get("id", "")):
        return False
    if not ISO_INSTANT_RE.match(f.get("at", "")):
        return False

    if is_receipt(b):
        # A read receipt. Receipts are not tree-relative claims, so a receipt
        # bearing provenance is malformed.
        if {"base", "base_branch", "base_mergebase", "dirty", "host"} & f.keys():
            return False
        if not _LOCAL_TASK_RE.match(f.get("by", "")):
            return False
        if f.get("mode") not in RECEIPT_MODES:
            return False
        ids = f.get("ids", "")
        parts = ids.split(",") if ids else []
        if not parts or not all(_NOTE_ID_RE.match(p) for p in parts):
            return False
        return _keys_allowed(f, RECEIPT_KEYS_REQUIRED, RECEIPT_KEYS_OPTIONAL)

    # A note. The marker name IS the sender, so the two must agree -- for a
    # cross-repo sender the name is the local 't<id>' part, since '#' is not a
    # legal marker-name character.
    sender = f.get("from", "")
    if _LOCAL_TASK_RE.match(sender):
        if b.name != sender:
            return False
    else:
        m = _XREPO_TASK_RE.match(sender)
        if not m or b.name != "t" + m.group(1):
            return False
    if "from_verified" in f and f["from_verified"] != "yes":
        return False
    return _validate_provenance(f)


# --- The unread derivation --------------------------------------------------


def parse(text: str) -> list:
    """Every ``note``-namespace block in ``text``, in file order.

    One parse, shared with the writer: ``ledger_block.parse_blocks`` is the
    t1657_1 seam, so reader and writer cannot drift into two grammars.
    """
    return ledger_block.parse_blocks(text, NAMESPACE)


def acknowledged_ids(blocks) -> set:
    """The note ids covered by every **valid** receipt in ``blocks``.

    Invalid receipts are skipped deliberately: a malformed receipt must not
    suppress a real acknowledgement, or a block the merger would reject could
    hide a note locally forever.
    """
    seen: set = set()
    for b in blocks:
        if is_receipt(b) and validate_block(b):
            ids = b.fields.get("ids", "")
            seen.update(p for p in ids.split(",") if p)
    return seen


def split(text: str):
    """``(unread, malformed)`` for one task body.

    ``unread`` -- valid note blocks whose ``id`` appears in no valid receipt's
    ``ids=``, in file order. ``malformed`` -- every block, note or receipt, that
    fails :func:`validate_block`.

    Set-union semantics on the receipt side: order-free, same-second-safe and
    merge-friendly, needing **no** frontmatter field. This mirrors the
    ``## Gate Runs`` precedent -- derive current state from an append-only log
    rather than mutating a stored value.
    """
    blocks = parse(text)
    acked = acknowledged_ids(blocks)
    unread, malformed = [], []
    for b in blocks:
        if not validate_block(b):
            malformed.append(b)
            continue
        if is_receipt(b):
            continue
        if b.fields.get("id", "") not in acked:
            unread.append(b)
    return unread, malformed


def unread(text: str) -> list:
    """Valid, unacknowledged note blocks in file order."""
    return split(text)[0]


def has_section(text: str) -> bool:
    """True if ``text`` carries an ``## Inbox`` section header."""
    return bool(re.search(r"(?m)^##\s+Inbox\s*$", text))


def drop_block_by_id(text: str, block_id: str):
    """Remove the ONE block whose ``id=`` is ``block_id``. -> (text, removed).

    This is the commit-failure rollback for ``ait note read`` (t1657_3), and its
    shape is the whole point: the task file is a **shared multi-writer surface**.
    Between our append and this call another writer may legitimately have
    appended to the same file, so restoring a pre-append snapshot would silently
    destroy their work. Removing exactly our own block by its minted id leaves
    every other block byte-identical.

    Refuses (returns ``removed=False``) when the id is absent **or ambiguous**:
    deleting one of two same-id blocks would be a guess, and ids are minted
    unique inside the append lock precisely so this cannot happen.
    """
    target = None
    for b in parse(text):
        if b.fields.get("id", "") == block_id:
            if target is not None:
                return text, False
            target = b
    if target is None:
        return text, False

    lines = text.splitlines(keepends=True)
    start = target.line_number - 1
    marker_re = ledger_block.build_marker_re(NAMESPACE)

    # The block ends at its LAST '>' line -- not at the first thing that
    # terminates parsing. parse_blocks walks *through* blank lines, so ending
    # the range there would swallow the blank separator that belongs to
    # whatever comes next.
    last = start
    i = start + 1
    while i < len(lines):
        stripped = lines[i].rstrip("\n")
        if marker_re.match(stripped) or ledger_block.SECTION_HEADER_RE.match(stripped):
            break
        if lines[i].startswith(">"):
            last = i
            i += 1
            continue
        if not lines[i].strip():
            i += 1
            continue
        break

    # Blocks are written as "\n\n{block}\n", so one blank line ahead of the
    # marker is this block's own separator and goes with it.
    head = start
    if head > 0 and not lines[head - 1].strip():
        head -= 1
    return "".join(lines[:head] + lines[last + 1:]), True


# --- CLI --------------------------------------------------------------------
#
# `aitask_query_files.sh inbox` delegates here rather than re-deriving anything
# in bash. It takes (task-id, path) PAIRS and answers for all of them in ONE
# interpreter start: the pick surfaces summarise up to 15 candidates, and a
# per-task invocation would put 15 python startups on every pick.


def _emit(task_id: str, path: str, out) -> None:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:  # unreadable is not "empty" -- say so
        print(f"INBOX_ERROR:{task_id}|{exc.__class__.__name__}", file=out)
        return

    if not has_section(text):
        print(f"NO_INBOX:{task_id}", file=out)
        return

    pending, malformed = split(text)

    # Malformed blocks are reported BEFORE the verdict line, never instead of
    # it. A discarded receipt makes a note keep re-surfacing and a discarded
    # note is one nobody sees; without this either would be indistinguishable
    # from "there was nothing there".
    for b in malformed:
        print(f"INBOX_MALFORMED:{task_id}|{b.line_number}|{b.name}", file=out)

    if not pending:
        print(f"NO_UNREAD:{task_id}", file=out)
        return

    for b in pending:
        f = b.fields
        # from_verified is carried EXPLICITLY: the consumer must render `from=`
        # as claimed, and `from_verified=yes` as the only verified variant.
        # Re-reading the file to recover it would be a second parse.
        # `base` is the FULL object id as stored -- this is a machine channel
        # and must never abbreviate; only human-facing display may.
        print("INBOX_UNREAD:{}|{}|{}|{}|{}|{}|{}".format(
            task_id,
            f.get("id", ""),
            f.get("from", ""),
            f.get("from_verified", ""),
            f.get("at", ""),
            f.get("base", ""),
            f.get("dirty", "")), file=out)


_USAGE = """usage:
  note_inbox.py unread <task-id> <path> [<task-id> <path>...]
  note_inbox.py acked <path>                 # ids covered by valid receipts
  note_inbox.py note-ids <path>              # ids of valid notes present
  note_inbox.py drop <path> <block-id>       # rollback: remove one block
"""


def _cmd_unread(rest) -> int:
    if not rest or len(rest) % 2:
        print("note_inbox.py: expects (task-id, path) pairs", file=sys.stderr)
        return 2
    for i in range(0, len(rest), 2):
        _emit(rest[i], rest[i + 1], sys.stdout)
    return 0


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def main(argv) -> int:
    if not argv:
        print(_USAGE, file=sys.stderr)
        return 2
    verb, rest = argv[0], argv[1:]

    if verb == "unread":
        return _cmd_unread(rest)

    if verb == "acked":
        if len(rest) != 1:
            print(_USAGE, file=sys.stderr)
            return 2
        for i in sorted(acknowledged_ids(parse(_read(rest[0])))):
            print(i)
        return 0

    if verb == "note-ids":
        # Valid NOTE ids present in the file. `ait note read` uses this to
        # refuse acknowledging an id that names no note here.
        if len(rest) != 1:
            print(_USAGE, file=sys.stderr)
            return 2
        for b in parse(_read(rest[0])):
            if not is_receipt(b) and validate_block(b):
                print(b.fields.get("id", ""))
        return 0

    if verb == "drop":
        if len(rest) != 2:
            print(_USAGE, file=sys.stderr)
            return 2
        path, block_id = rest
        new, removed = drop_block_by_id(_read(path), block_id)
        if not removed:
            print("DROP_FAILED", file=sys.stderr)
            return 1
        ledger_block.atomic_write(path, new)
        print("DROPPED")
        return 0

    print(_USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
