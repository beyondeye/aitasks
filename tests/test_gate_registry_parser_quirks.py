#!/usr/bin/env python3
"""Characterization tests for gate_ledger's registry parser (t635_34).

These pin the parser's ACTUAL behaviour — quirks included — against the
implementation that existed before t635_34 extracted the shared line-walk
(`_walk_registry`) used by both `read_registry_text` and `registry_layout`.

They exist because `read_registry` sits under every gate consumer
(`format_list`, `required_unblock_gates`, `dependents_status`,
`unmet_procedure_gates`, `read_task_gate_state`, `gate_orchestrator`,
`aitask_gate_pass.sh`, `aitask_board.py`), and the refactor's safety argument
was otherwise inspection-only. Each case below is a behaviour a careless
re-implementation silently loses.

**These are characterization tests, not specifications.** Several pinned
behaviours are arguably wrong (quirk 3 wipes a duplicated gate's earlier
fields; quirk 6 lets a `#` truncate the mapping). They are pinned so a change
to them is DELIBERATE and visible, not accidental. `ait gates sync-registry`
refuses to write in exactly the cases quirks 3 and 6 describe, precisely
because the parse is untrustworthy there.

Run: python3 tests/test_gate_registry_parser_quirks.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".aitask-scripts", "lib"))

import gate_ledger as gl  # noqa: E402

PASS = 0
FAIL = 0


def check(desc, expected, actual):
    global PASS, FAIL
    if expected == actual:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {desc}\n  expected: {expected!r}\n  actual:   {actual!r}")


def parse(text):
    """Parse registry TEXT.

    Uses the text-level entry point when present (post-refactor) and falls back
    to a tempfile through `read_registry` (pre-refactor), so this file is
    runnable on BOTH sides of the extraction — which is what makes it a real
    characterization net rather than a test written against the new code.
    """
    fn = getattr(gl, "read_registry_text", None)
    if fn is not None:
        return fn(text)
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".yaml")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        return gl.read_registry(path)
    finally:
        os.unlink(path)


# --- Quirk 1: gate_indent is STICKY across a dedent ------------------------

def quirk1_gate_indent_sticky():
    """The first gate's indent governs a LATER re-activation of the mapping.

    `gate_indent` is set once and never reset when `in_gates` goes False, so
    the second `gates:` block's 4-space entries are compared against the FIRST
    block's 2-space gate_indent -> 4 > 2 -> they are read as FIELDS of a gate
    that no longer exists (`cur` was reset), and are therefore DROPPED.
    """
    text = (
        "gates:\n"
        "  a:\n"
        "    type: machine\n"
        "other: x\n"
        "gates:\n"
        "    b:\n"
        "      type: human\n"
    )
    reg = parse(text)
    check("quirk1: sticky gate_indent drops the deeper second block",
          ["a"], sorted(reg.keys()))


# --- Quirk 2: `cur` IS reset on dedent -------------------------------------

def quirk2_cur_reset_on_dedent():
    """Fields appearing after the mapping closed and reopened are orphaned.

    Same indent as the first block this time, so `b` IS a gate; the point is
    that the intervening dedent cleared `cur`, so a field line arriving before
    any new gate header has no owner and is dropped rather than attaching to
    the previous gate.
    """
    text = (
        "gates:\n"
        "  a:\n"
        "    type: machine\n"
        "other: x\n"
        "gates:\n"
        "    verifier: orphaned\n"
        "  b:\n"
        "    type: human\n"
    )
    reg = parse(text)
    check("quirk2: gate set after dedent", ["a", "b"], sorted(reg.keys()))
    check("quirk2: orphan field did not attach to the previous gate",
          "", reg["a"]["verifier"])


# --- Quirk 3: duplicate gate header WIPES the earlier block ----------------

def quirk3_duplicate_gate_wipes_earlier():
    """Last duplicate wins WHOLESALE — not field-wise merged.

    `sync-registry` refuses to write on a duplicate for exactly this reason:
    the fill/conflict decision would be computed against a half-read file.
    """
    text = (
        "gates:\n"
        "  a:\n"
        "    type: machine\n"
        "    verifier: first\n"
        "    max_retries: 3\n"
        "  a:\n"
        "    type: human\n"
    )
    reg = parse(text)
    check("quirk3: duplicate keeps only the last block's type",
          "human", reg["a"]["type"])
    check("quirk3: earlier block's verifier is WIPED, not merged",
          "", reg["a"]["verifier"])
    check("quirk3: earlier block's max_retries is WIPED, not merged",
          0, reg["a"]["max_retries"])


# --- Quirk 4: blank lines inside a block-form `unlocks` do NOT end it ------

def quirk4_blank_inside_unlocks_block():
    """The block-list walk skips blank lines rather than terminating.

    Note this DIFFERS from `_read_frontmatter_list_from_text`, whose readers
    stop at the first blank (see t635_33 CR5) — the two list parsers in this
    module genuinely disagree, and that disagreement is load-bearing here.
    """
    text = (
        "gates:\n"
        "  a:\n"
        "    type: machine\n"
        "    unlocks:\n"
        "      - x\n"
        "\n"
        "      - y\n"
    )
    reg = parse(text)
    check("quirk4: blank line does not split a block-form unlocks",
          ["x", "y"], reg["a"]["unlocks"])


def quirk4b_unlocks_absent_vs_empty():
    """ABSENT (None, linear default) and `[]` (terminal) stay distinct."""
    absent = parse("gates:\n  a:\n    type: machine\n")
    check("quirk4b: absent unlocks is None", None, absent["a"]["unlocks"])
    empty = parse("gates:\n  a:\n    type: machine\n    unlocks: []\n")
    check("quirk4b: explicit empty unlocks is []", [], empty["a"]["unlocks"])


# --- Quirk 5: `gates: {}` never activates the parser -----------------------

def quirk5_flow_empty_never_activates():
    """The activation regex is `^gates:\\s*$`, so a flow mapping is invisible.

    Several existing tests rely on `gates: {}` producing an EMPTY registry.
    """
    check("quirk5: gates: {} yields no gates",
          {}, parse("gates: {}\n  a:\n    type: machine\n"))
    check("quirk5: gates: {} alone yields no gates", {}, parse("gates: {}\n"))


# --- Quirk 6: ANY column-0 line ends the mapping, including a comment ------

def quirk6_column_zero_comment_terminates():
    """A column-0 `#` truncates the registry — `#` matches `^\\S`.

    This is the failure mode `sync-registry` must refuse to write through: a
    project with `# --- local gates ---` mid-mapping parses as ONLY the gates
    above the comment, so a naive sync would append duplicates of gates that
    are already in the file.
    """
    text = (
        "gates:\n"
        "  a:\n"
        "    type: machine\n"
        "# --- local gates below ---\n"
        "  b:\n"
        "    type: human\n"
    )
    reg = parse(text)
    check("quirk6: column-0 comment truncates the mapping",
          ["a"], sorted(reg.keys()))

    indented = text.replace("# --- local gates below ---",
                            "  # --- local gates below ---")
    check("quirk6: an INDENTED comment does not truncate",
          ["a", "b"], sorted(parse(indented).keys()))


# --- Quirk 7: `.strip("'\\"")` strips any quote chars, mismatched included --

def quirk7_quote_stripping_is_loose():
    text = (
        "gates:\n"
        "  a:\n"
        "    verifier: 'quoted'\n"
        "  b:\n"
        "    verifier: \"mismatched'\n"
        "  c:\n"
        "    description: has # not a comment\n"
    )
    reg = parse(text)
    check("quirk7: matched quotes stripped", "quoted", reg["a"]["verifier"])
    check("quirk7: MISMATCHED quote pair also stripped",
          "mismatched", reg["b"]["verifier"])
    check("quirk7: '#' in a value is NOT treated as an inline comment",
          "has # not a comment", reg["c"]["description"])


# --- Presence is NOT recoverable from the parsed dict ---------------------

def presence_is_not_recoverable_from_parsed_values():
    """The reason `sync-registry` needs a raw-text presence oracle.

    An explicitly-empty value and an absent key are INDISTINGUISHABLE after
    parsing, so a fill-vs-conflict decision keyed off the parsed dict alone
    cannot tell "never configured" from "deliberately disabled".
    """
    absent = parse("gates:\n  a:\n    type: machine\n")
    empty = parse("gates:\n  a:\n    type: machine\n    verifier: \"\"\n")
    check("presence: absent verifier and empty verifier parse identically",
          absent["a"]["verifier"], empty["a"]["verifier"])
    zero = parse("gates:\n  a:\n    max_retries: 0\n")
    noretry = parse("gates:\n  a:\n    type: machine\n")
    check("presence: absent max_retries and 0 parse identically",
          noretry["a"]["max_retries"], zero["a"]["max_retries"])


# --- Unknown keys are ignored (the schema-growth asymmetry's root) --------

def unknown_keys_are_ignored():
    reg = parse("gates:\n  a:\n    type: machine\n    future_key: v\n")
    check("unknown key does not appear in the parsed record",
          False, "future_key" in reg["a"])
    check("unknown key does not disturb known ones", "machine", reg["a"]["type"])


# --- Structural: the real reference still parses as expected --------------

def reference_still_parses():
    ref = os.path.join(HERE, "..", ".aitask-scripts", "gates_reference.yaml")
    reg = gl.read_registry(ref)
    check("reference: all 8 framework gates present", 8, len(reg))
    check("reference: risk_evaluated verifier",
          "aitask-gate-risk", reg["risk_evaluated"]["verifier"])
    check("reference: docs_updated is procedure-kind",
          "procedure", reg["docs_updated"]["kind"])
    check("reference: no gate declares unlocks (all linear-default)",
          [], [g for g, m in reg.items() if m["unlocks"] is not None])


_CHECKS = [
    quirk1_gate_indent_sticky,
    quirk2_cur_reset_on_dedent,
    quirk3_duplicate_gate_wipes_earlier,
    quirk4_blank_inside_unlocks_block,
    quirk4b_unlocks_absent_vs_empty,
    quirk5_flow_empty_never_activates,
    quirk6_column_zero_comment_terminates,
    quirk7_quote_stripping_is_loose,
    presence_is_not_recoverable_from_parsed_values,
    unknown_keys_are_ignored,
    reference_still_parses,
]


def main():
    for fn in _CHECKS:
        fn()
    print(f"\nResults: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery."""

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
