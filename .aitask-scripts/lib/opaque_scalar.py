"""Comparison normalizer for opaque frontmatter scalars (t1663_2).

An *opaque* scalar is a frontmatter field whose value has no vocabulary of its
own and no tombstone: clearing it removes the key. The sync merge driver
(``board/aitask_merge.py``) resolves these fields by comparing each side with the
merge base (``_BASE_AWARE_FIELDS``), and it needs one equality rule for them:
:func:`normalize_opaque_scalar`. Its users are ``verification_baseline``,
``plan_approved_at`` and ``premise_baseline``.

This module exists so that a field which needs the rule imports it. The rule
used to be a private helper inside the merge driver, with a note that the third
field to need it should promote it rather than copy it.

Two near-identical functions deliberately stay where they are:

- ``followup_kinds.normalize_followup_kind`` is part of the follow-up-kind
  vocabulary module, and its contract is about that vocabulary.
- ``board_groups.normalize_group_slug`` does the same for ``boardgroup``'s slug
  vocabulary and its ``""`` tombstone.

Their bodies match today, but each answers a question about its own
vocabulary, so they may diverge from this one.

Stdlib-only leaf: no imports, safe to load from any ``lib/`` consumer.
"""
from __future__ import annotations

__all__ = ["normalize_opaque_scalar"]


def normalize_opaque_scalar(raw) -> str:
    """Canonicalise an opaque scalar for *comparison only*, never for storage.

    An absent key, an explicit ``None``, a non-string (a hand-edited list) and an
    empty or whitespace-only string all read as *absent*, so a side that deleted
    the key and a side that never had it compare equal.

    A real value is returned **verbatim, not stripped**. It is an identity key,
    and trimming it would make two genuinely different values compare equal.
    Validation rejects a bad value at the write seams; this only decides
    equality.
    """
    if isinstance(raw, str):
        return raw if raw.strip() else ""
    return ""
