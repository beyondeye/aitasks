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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable  # noqa: F401  -- used in SectionSpec annotations

# Both the frontmatter parser (t1217) and the canonical gate-ledger parser
# (t635_8 owns it — do not fork) live under lib/. Mirror the lib/ import idiom
# used by board/aitask_board.py so this works both under PYTHONPATH=board (the
# argv aitask_sync.sh uses) and when a test imports this module directly.
# These imports MUST stay below the insert — task_yaml is no longer a
# same-package sibling.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from task_yaml import (  # noqa: E402
    parse_frontmatter, serialize_frontmatter, BOARD_LAYOUT_KEYS,
)
from board_groups import normalize_group_slug  # noqa: E402
from followup_kinds import normalize_followup_kind  # noqa: E402
# gate_ledger supplies this merger's ONE registered section spec (header,
# comment, namespace). It is no longer a leaf module — it imports
# lib/ledger_block.py (t1657_1) — but both are still stdlib-only, and the
# sys.path set up just above covers the sibling import.
import gate_ledger  # noqa: E402
import ledger_block  # noqa: E402  -- the generic marker-block substrate
from atomic_write import atomic_write_text  # noqa: E402

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

# `attachments` (t1030) and `artifacts` (t1076_2) are DELIBERATELY absent from
# _LIST_UNION_FIELDS: they are lists of mappings, not scalars, and a concurrent
# edit falls through to the generic unresolved/PARTIAL path — degrading to a
# manual conflict beats a silent union guess for structured entries.
_LIST_UNION_FIELDS = frozenset({"labels", "depends"})
# Deliberately BOARD_LAYOUT_KEYS, not BOARD_KEYS: local-wins is correct only for
# per-checkout layout. A *shared* board key resolved local-wins would silently
# discard another checkout's change to it, so a key added to BOARD_KEYS must opt
# in to its own merge rule rather than inherit this one.
_KEEP_LOCAL_FIELDS = frozenset(BOARD_LAYOUT_KEYS)
_PROMPTABLE_FIELDS = frozenset({"priority", "effort"})
# Active-gates tuple (t635_33): derived, profile-filtered enforcement state
# written atomically at claim time. Deliberately NOT in _LIST_UNION_FIELDS
# (like `gates`, it is computed replace-all — a union would fabricate a set no
# profile ever produced) and resolved as ONE group in merge_frontmatter.
_ACTIVE_TUPLE_FIELDS = ("active_gates", "active_gates_filtered",
                        "active_gates_profile", "active_gates_digest")


def _normalize_opaque_scalar(raw) -> str:
    """Comparison-only normalizer for a scalar with no vocabulary of its own.

    An absent key, an explicit ``None``, a non-string (a hand-edited list) and an
    empty string all read as *absent*, so a side that deleted the key and a side
    that never had it compare equal. A real value is returned **verbatim, not
    stripped** — it is an identity key, and trimming would make two genuinely
    different values compare equal.

    Deliberately not ``normalize_followup_kind`` despite an identical body: that
    one lives in the follow-up-kind *vocabulary* module and its contract is about
    that vocabulary. A third such field should promote this helper rather than
    add a fourth copy.
    """
    if isinstance(raw, str):
        return raw if raw.strip() else ""
    return ""


# Base-aware fields (t1243_8): resolved by comparing each side against the MERGE
# BASE rather than by presence or timestamp, and resolved BEFORE the loop so the
# unconditional one-sided-presence branch never sees them.
#
# `boardgroup` is in-column group membership -- shared task organization, so
# keep-local is wrong for it -- and neither of the generic rules can decide it:
#   * one-sided presence resolves FIRST and unconditionally, so a side that
#     clears the field loses to a side that still carries it: membership
#     RESURRECTS on sync;
#   * `updated_at` is task-wide and minute-resolution, so an unrelated `status`
#     edit on a stale checkout can win a field it never touched, and bulk group
#     operations tie constantly. A timestamp is a proxy for causality, not
#     causality.
# Comparing against the base decides on *who actually edited the field*, and
# fails closed to unresolved/PARTIAL when both sides changed it differently or
# when no base is available.
#
# `followup_kind` (t1468_1) needs the same base comparison for the same reason —
# a misclassification must be correctable, including by CLEARING the field, and
# only base comparison lets a clear survive sync. It differs from `boardgroup`
# in two ways that the resolver has to be told about:
#   * it has NO tombstone. `boardgroup` persists `""` to mean "deliberately
#     ungrouped", so it is always *present*; clearing `followup_kind` removes the
#     key. A resolver that only reports "some side had it" would hand back
#     ``None`` and `serialize_frontmatter` — which gates on key membership, not
#     truthiness — would write a literal `followup_kind: null` instead of
#     dropping the line. `deletion_aware` makes the winning side's *absence* win.
#   * it must not compare through `normalize_group_slug`: that is boardgroup's
#     tombstone vocabulary, not this field's.
#
# `verification_baseline` (t1555_1) is shape-identical to `followup_kind`: a
# semantic scalar with NO tombstone, so it needs the same two properties for the
# same two reasons.
#   * Base comparison, not presence: clearing it REMOVES the key, so the
#     unconditional one-sided-presence branch below would let a stale checkout
#     still carrying the old value beat a checkout that deliberately cleared it
#     -- the baseline would resurrect on sync, and with it a staleness dismissal
#     the user had revoked.
#   * Base comparison, not `updated_at`: the baseline advances when a user
#     reviews a staleness prompt, while `updated_at` moves on every unrelated
#     edit -- so a newer-timestamp rule would let a stale checkout's `--status`
#     edit win a field it never touched.
# `deletion_aware=True` for the tombstone-less reason spelled out above.
#
# `plan_approved_at` (t1595) is the same shape once more: the marker meaning "an
# approved plan whose implementation was deliberately deferred", cleared by key
# removal the moment that stops being true (implementation starts, the plan is
# replanned or aborted, a drift stop demands re-verification).
#   * Base comparison, not presence: the one-sided branch would let a stale
#     checkout still carrying the marker beat a checkout that cleared it, so a
#     consumed or invalidated marker would resurrect on sync -- and every
#     surface would then advertise an approved plan that is not awaiting
#     implementation, which is worse than showing nothing.
#   * Base comparison, not `updated_at`: the marker moves on approve-and-stop
#     and on consumption, while `updated_at` moves on every unrelated edit.
# `deletion_aware=True`: clearing removes the key, as above.
#
# field -> (comparison normalizer, deletion_aware). Membership (`key in
# _BASE_AWARE_FIELDS`) and iteration both still yield the field names.
_BASE_AWARE_FIELDS = {
    "boardgroup": (normalize_group_slug, False),
    "followup_kind": (normalize_followup_kind, True),
    "verification_baseline": (_normalize_opaque_scalar, True),
    "plan_approved_at": (_normalize_opaque_scalar, True),
}


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


def _resolve_base_aware(key, local_meta, remote_meta, base_meta,
                        normalize=normalize_group_slug, deletion_aware=False):
    """Resolve one base-aware field. Returns ``(present, value, is_unresolved)``.

    ``present`` is False when neither side carries the key at all, in which case
    the merged result must not invent it (mirroring the active-tuple block).

    Values are compared through ``normalize`` — for ``boardgroup`` that is
    ``normalize_group_slug``, so an absent key, an explicit ``None`` and the
    ``""`` tombstone all read as *ungrouped*. Without that, a side that deletes
    the key and a side that writes the tombstone would look like two different
    changes and a decidable merge would fail closed for no reason. (The
    tombstone itself is written by ``aitask_update.sh``; this normalization is
    defence in depth, not the persisted contract.) A field with a different
    vocabulary passes its own normalizer.

    ``deletion_aware`` (t1468_1) additionally reports the *winning side's*
    presence rather than "either side had it". For a field with no tombstone,
    a resolved-empty value means the key must be **absent**, not written as
    ``None`` — ``serialize_frontmatter`` gates on key membership, so a ``None``
    would land in the file as a literal ``<key>: null``. Left False, the
    boardgroup behaviour is byte-identical to before.
    """
    def _resolved(value, is_unresolved):
        """Package a decided value, collapsing empty to absent when asked."""
        if deletion_aware and normalize(value) == "":
            return (False, None, is_unresolved)
        return (True, value, is_unresolved)

    in_local = key in local_meta
    in_remote = key in remote_meta
    if not in_local and not in_remote:
        return (False, None, False)

    local_val = normalize(local_meta.get(key))
    remote_val = normalize(remote_meta.get(key))
    if local_val == remote_val:
        return _resolved(local_meta.get(key) if in_local else remote_meta.get(key),
                         False)

    # Sides differ. Only the base can say which of them actually changed it.
    if base_meta is None:
        return _resolved(local_meta.get(key), True)   # fail closed -> PARTIAL

    base_val = normalize(base_meta.get(key))
    local_changed = local_val != base_val
    remote_changed = remote_val != base_val
    if local_changed and not remote_changed:
        return _resolved(local_meta.get(key), False)
    if remote_changed and not local_changed:
        return _resolved(remote_meta.get(key), False)
    # Both changed to different values (they differ, checked above), or neither
    # differs from a base that somehow differs from both -- genuinely concurrent
    # regrouping. Surface it rather than guess.
    return _resolved(local_meta.get(key), True)


def merge_frontmatter(
    local_meta: dict,
    remote_meta: dict,
    batch: bool = False,
    base_meta: dict | None = None,
) -> tuple[dict, list[str]]:
    """Apply auto-merge rules to two frontmatter dicts.

    ``base_meta`` is the MERGE BASE's frontmatter (git stage 1), supplied by
    ``aitask_sync.sh`` via ``--base-file``. It is used only by
    ``_BASE_AWARE_FIELDS``; every other rule is unchanged, and passing ``None``
    (the default) is behaviour-identical to the pre-t1243_8 three-argument call
    for every field except those.

    Returns (merged_metadata, list_of_unresolved_field_names).
    """
    merged: dict = {}
    unresolved: list[str] = []

    local_ts = _parse_timestamp(local_meta.get("updated_at"))
    remote_ts = _parse_timestamp(remote_meta.get("updated_at"))
    newer = _newer_side(local_ts, remote_ts)

    all_keys = list(dict.fromkeys(list(local_meta.keys()) + list(remote_meta.keys())))

    # Active-gates tuple (t635_33): grouped presence/deletion semantics. The
    # four fields move as a UNIT, taken wholesale from the newer-updated_at
    # side's STATE — including absence: if the newer side legitimately has no
    # tuple, the merged result has NO tuple (the generic one-side-only rule
    # below would resurrect the older side's obsolete snapshot). Never mixes
    # sides — a mixed tuple has inconsistent provenance and would only be
    # caught later as digest corruption.
    if any(k in local_meta or k in remote_meta for k in _ACTIVE_TUPLE_FIELDS):
        tuple_src = local_meta if newer == "LOCAL" else remote_meta
        for k in _ACTIVE_TUPLE_FIELDS:
            if k in tuple_src:
                merged[k] = tuple_src[k]

    # Base-aware fields (t1243_8). Resolved HERE, ahead of the loop, because the
    # loop's one-sided-presence branch is unconditional and would resurrect a
    # value the other side deliberately cleared.
    for key, (normalize, deletion_aware) in _BASE_AWARE_FIELDS.items():
        present, value, is_unresolved = _resolve_base_aware(
            key, local_meta, remote_meta, base_meta, normalize, deletion_aware)
        # `unresolved` is recorded independently of presence: a deletion-aware
        # field can fail closed to PARTIAL *and* resolve to absent, and skipping
        # the append on `not present` would silently drop that PARTIAL. (For a
        # non-deletion-aware field the two orders are equivalent -- `present` is
        # False only when neither side had the key, which is never unresolved.)
        if is_unresolved:
            unresolved.append(key)
        if present:
            merged[key] = value

    for key in all_keys:
        if key in _ACTIVE_TUPLE_FIELDS:
            continue  # resolved as a group above
        if key in _BASE_AWARE_FIELDS:
            continue  # resolved against the merge base above
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


@dataclass(frozen=True)
class SectionSpec:
    """How to union ONE append-only marker-block section (t1657_1).

    Four of these six are the gate semantics that used to be hardcoded in
    ``_union_gate_runs``, and none of them transfers to another ledger — which
    is exactly why they had to become spec members rather than stay literals.
    A ``## Inbox`` block (t1657_2) carries ``id=``/``at=`` and neither ``run=``
    nor ``attempt=``, so with the gate rules applied to it: ``validate`` would
    reject every block, ``identity`` would collapse every note from one sender
    onto one key, and ``order_key`` would degenerate to alphabetical.

    ``order_key`` is a callable rather than a tuple of field names because
    ``attempt`` sorts NUMERICALLY (10 after 2), which no field-name list can say.
    """

    header: str
    comment: str
    namespace: str
    #: True if the block is trustworthy enough to union. Any False bails the
    #: whole body to conflict markers rather than guessing.
    validate: "Callable[[object], bool]"
    #: Append-only identity. Two DISTINCT texts sharing one identity is a
    #: contract violation.
    identity: "Callable[[object], tuple]"
    #: Total, side-order-independent sort key, called as (block_text, block).
    order_key: "Callable[[str, object], tuple]"
    #: What to do when two distinct blocks share an identity. Only "conflict"
    #: is implemented; it is a named field so a future ledger that can safely
    #: keep both has somewhere to say so, rather than this being an unstated
    #: assumption baked into the loop.
    on_collision: str = "conflict"


def _attempt_int(block) -> int:
    """attempt as an int; 0 for missing or non-numeric."""
    a = block.fields.get("attempt", "")
    return int(a) if a.isdigit() else 0


GATE_SPEC = SectionSpec(
    header=gate_ledger.SECTION_HEADER,
    comment=gate_ledger.SECTION_COMMENT,
    namespace=gate_ledger.NAMESPACE,
    validate=lambda b: bool(_ISO_RUN_RE.match(b.fields.get("run", ""))),
    identity=lambda b: (b.name, b.fields.get("run", ""),
                        b.fields.get("attempt", "")),
    # run is valid ISO ⇒ chronological; then name; then attempt NUMERICALLY;
    # then full text as the final tie-break.
    order_key=lambda text, b: (b.fields.get("run", ""), b.name,
                               _attempt_int(b), text),
)

# --- '## Inbox' — the task-note mailbox (t1657_2) ---------------------------
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
_NOTE_KEYS_REQUIRED = {"id", "from", "at", "base", "dirty", "host"}
_NOTE_KEYS_OPTIONAL = {"from_verified", "base_branch", "base_mergebase"}
_MIGRATED_KEYS_REQUIRED = {"id", "from", "at", "base", "claimed_at", "migrated"}
_MIGRATED_KEYS_OPTIONAL = {"base_branch", "base_mergebase"}
_RECEIPT_KEYS_REQUIRED = {"id", "by", "at", "mode", "ids"}
_RECEIPT_KEYS_OPTIONAL: set = set()


def _keys_allowed(f, required: set, optional: set) -> bool:
    """Exact key-set membership: every required key present, no extras."""
    keys = set(f.keys())
    return required <= keys and not (keys - required - optional)


def _validate_inbox_provenance(f) -> bool:
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
        return _keys_allowed(f, _MIGRATED_KEYS_REQUIRED, _MIGRATED_KEYS_OPTIONAL)

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
    return _keys_allowed(f, _NOTE_KEYS_REQUIRED, _NOTE_KEYS_OPTIONAL)


def _validate_inbox(b) -> bool:
    """Reject, never repair -- a non-conforming block bails the whole body.

    ``identity`` is ``(id,)``, so a block with a missing ``id`` would key on
    ``("",)`` and two unrelated malformed blocks would collide as one entry.
    """
    f = b.fields
    if not _NOTE_ID_RE.match(f.get("id", "")):
        return False
    if not _ISO_RUN_RE.match(f.get("at", "")):
        return False

    if b.name == "read":
        # A read receipt (t1657_3). Receipts are not tree-relative claims, so
        # a receipt bearing provenance is malformed.
        if {"base", "base_branch", "base_mergebase", "dirty", "host"} & f.keys():
            return False
        if not _LOCAL_TASK_RE.match(f.get("by", "")):
            return False
        if f.get("mode") not in ("auto", "explicit"):
            return False
        ids = f.get("ids", "")
        parts = ids.split(",") if ids else []
        if not parts or not all(_NOTE_ID_RE.match(p) for p in parts):
            return False
        return _keys_allowed(f, _RECEIPT_KEYS_REQUIRED, _RECEIPT_KEYS_OPTIONAL)

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
    return _validate_inbox_provenance(f)


INBOX_SPEC = SectionSpec(
    header="## Inbox",
    comment="<!-- Appended by the note framework. Do not edit by hand; use "
            "`./ait note`. -->",
    namespace="note",
    validate=_validate_inbox,
    # (id,) -- NOT (name, ...): one sender sends many notes, so a name-based
    # identity would collapse them all onto one key and report a false
    # ambiguous winner.
    identity=lambda b: (b.fields.get("id", ""),),
    # Chronological, then the id as a total tie-break. No numeric field here,
    # so unlike the gate spec this is a plain lexicographic tuple.
    order_key=lambda text, b: (b.fields.get("at", ""), b.fields.get("id", "")),
)

#: Sections this merger knows how to union, in the order they are rebuilt.
#: '## Inbox' comes first because that is where the note writer places it --
#: above '## Gate Runs', since both gate-append paths append at EOF and an
#: Inbox below would swallow every future gate block.
REGISTERED_SPECS: tuple[SectionSpec, ...] = (INBOX_SPEC, GATE_SPEC)


def _header_re(header: str) -> re.Pattern:
    return re.compile(rf"(?m)^{re.escape(header)}\s*$")


def _split_sections(body: str, specs=REGISTERED_SPECS):
    """Split ``body`` into (head, {spec: section_text}).

    A section runs from its header to the start of the NEXT REGISTERED header,
    or to end of body when it is the last one. That bound is what keeps this
    generalization byte-compatible with the single-section original: with one
    spec, the section is header..EOF exactly as before, so an unregistered
    ``##`` section trailing the ledger still lands *inside* it and still trips
    the cleanliness guard, rather than being silently absorbed into a tail.
    """
    found = []
    for spec in specs:
        m = _header_re(spec.header).search(body)
        if m:
            found.append((m.start(), spec))
    if not found:
        return body, {}

    found.sort()
    head = body[:found[0][0]]
    sections = {}
    for i, (start, spec) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(body)
        sections[spec] = body[start:end]
    return head, sections


def _split_gate_section(body: str) -> tuple[str, str]:
    """Return (head, section); section starts at the first '## Gate Runs' or ''.

    Compatibility shape over :func:`_split_sections` for the gate ledger.
    """
    head, sections = _split_sections(body, (GATE_SPEC,))
    return head, sections.get(GATE_SPEC, "")


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


def _union_one_section(spec: SectionSpec, local_sec: str, remote_sec: str):
    """Union one section per its spec, or None to bail the whole body.

    Every guard degrades to the conflict path rather than guessing, so no ledger
    data is ever silently reordered or dropped.
    """
    # Guard 3: only union purely machine-owned sections.
    if not _section_is_clean(local_sec) or not _section_is_clean(remote_sec):
        return None

    blocks = (ledger_block.parse_blocks(local_sec, spec.namespace)
              + ledger_block.parse_blocks(remote_sec, spec.namespace))

    # Guard 1: every block must be trustworthy enough to order.
    if any(not spec.validate(b) for b in blocks):
        return None

    # Guard 2: dedup by FULL TEXT only — shared history collapses, divergent kept.
    by_text: dict[str, object] = {}
    for b in blocks:
        by_text.setdefault(_block_text(b), b)

    # Guard 2b: ambiguous winner — >1 distinct block for one identity is an
    # append-only contract violation; let a human pick rather than tiebreak.
    ident: dict[tuple, set] = {}
    for text, b in by_text.items():
        ident.setdefault(spec.identity(b), set()).add(text)
    if any(len(texts) > 1 for texts in ident.values()):
        if spec.on_collision != "conflict":
            raise ValueError(
                f"unsupported on_collision {spec.on_collision!r} for "
                f"{spec.header!r}")
        return None

    ordered = sorted(by_text.items(), key=lambda kv: spec.order_key(kv[0], kv[1]))
    body = "\n\n".join(text for text, _b in ordered)
    return f"{spec.header}\n{spec.comment}\n\n{body}\n"


def _union_sections(local_body: str, remote_body: str,
                    specs=REGISTERED_SPECS):
    """Union every registered append-only section of two bodies.

    Returns (merged_body, head_resolved) when a *provably safe* union is
    possible, else None (the caller then falls back to whole-body conflict
    markers). A bail in ANY registered section bails the whole body, exactly as
    the single-section original did.
    """
    local_head, local_secs = _split_sections(local_body, specs)
    remote_head, remote_secs = _split_sections(remote_body, specs)
    if not local_secs and not remote_secs:
        return None  # no registered section anywhere → not our case

    merged_sections = []
    for spec in specs:                      # registered order is the rebuild order
        local_sec = local_secs.get(spec, "")
        remote_sec = remote_secs.get(spec, "")
        if not local_sec and not remote_sec:
            continue
        merged = _union_one_section(spec, local_sec, remote_sec)
        if merged is None:
            return None
        merged_sections.append(merged)

    merged_body = "\n".join(merged_sections)

    # Compare heads ignoring trailing blank lines — the side carrying a section
    # includes the blank lines that preceded its header while a side without one
    # does not, yet the prose is identical. Rebuild with one canonical blank line
    # before the first section.
    if local_head.rstrip("\n") == remote_head.rstrip("\n"):
        head_norm = local_head.rstrip("\n")
        out = (head_norm + "\n\n" + merged_body) if head_norm else merged_body
        return out, True
    # Prose head genuinely conflicts; still union the machine-owned sections and
    # leave the head on the conflict-marker path for manual resolution.
    return _conflict_markers(local_head, remote_head) + merged_body, False


def _union_gate_runs(local_body: str, remote_body: str):
    """Compatibility shape: union the gate ledger alone."""
    return _union_sections(local_body, remote_body, (GATE_SPEC,))


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

    union = _union_sections(local_body, remote_body)
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
    parser.add_argument(
        "--base-file", dest="base_file", default=None,
        help="Path to the merge base's version of the file (git stage 1). "
             "Used to resolve base-aware fields by detecting which side "
             "actually changed them; omit it and those fields fail closed to "
             "PARTIAL on divergence.",
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

    # 2b. Parse the merge base, when one was supplied (git stage 1).
    #
    # NO rebase swap here: `--rebase` inverts the two CONFLICT-MARKER sides,
    # but stage 1 is the common ancestor of both regardless of which direction
    # the rebase is replaying. Swapping it would be wrong in both directions.
    #
    # Best-effort by design: an add/add conflict genuinely has no stage 1, so
    # `git show :1:` fails and no path is passed. Base-aware fields then fail
    # closed to PARTIAL rather than guessing.
    base_meta = None
    if args.base_file:
        try:
            base_parsed = parse_frontmatter(
                Path(args.base_file).read_text(encoding="utf-8"))
        except OSError:
            base_parsed = None
        if base_parsed:
            base_meta = base_parsed[0]

    # 3. Merge frontmatter
    merged_meta, unresolved = merge_frontmatter(
        local_meta, remote_meta,
        batch=args.batch,
        base_meta=base_meta,
    )

    # 4. Merge body
    merged_body, body_resolved = merge_body(local_body, remote_body)
    if not body_resolved:
        unresolved.append("body")

    # 5. Determine key order (union of both sides, local order priority)
    merged_keys = list(dict.fromkeys(local_keys + remote_keys))

    # 6. Write result
    #
    # Atomic replace, not `write_text` (t1379): this rewrites a live task file
    # during sync conflict resolution, and `write_text` truncates it to zero
    # before writing — a board scan racing the merge would read it empty.
    merged_content = serialize_frontmatter(merged_meta, merged_body, merged_keys)
    atomic_write_text(str(filepath), merged_content)

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
