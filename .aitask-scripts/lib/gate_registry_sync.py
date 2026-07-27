#!/usr/bin/env python3
"""Additive reconcile of an installed gate registry against the canonical
reference (t635_34) — the engine behind `ait gates sync-registry`.

Projects seeded before t1147 carry an `aitasks/metadata/gates.yaml` missing
`verifier` / `kind` / `signal` keys, so their tasks block on
`blocked: no verifier configured (deferred)` and cannot archive.

`ait upgrade --force` already fills absent keys (via PyYAML deep-merge, dest
winning), so this is NOT the only path — but that one destroys the registry's
schema/edit-protocol comment header and every in-block comment, requires a full
framework version upgrade, reports nothing about values that genuinely diverge,
and needs PyYAML, which the rest of the gate system deliberately avoids. This
module is the targeted, comment-preserving, conflict-reporting, stdlib-only
version.

**No PyYAML anywhere in this path** — `gate_ledger.read_registry` is the
semantic oracle and `gate_ledger.registry_layout` the presence/layout oracle,
both regex-based, so the command works where PyYAML is unavailable.

Design invariants (do NOT relax):
  1. Additive only. A key present in the project is NEVER overwritten; a
     differing value is reported as a CONFLICT.
  2. Presence, not value, decides fill-vs-conflict. `verifier: ""` is a
     deliberate opt-out and must never be "filled".
  3. Comments and formatting survive. Edits are line splices into the project's
     own text — never a re-serialization.
  4. Fail closed. Anything that makes the parse untrustworthy (duplicate gates,
     a mapping truncated by a column-0 comment, unobservable indentation)
     writes nothing and exits nonzero.
  5. Verify before writing. The candidate text is re-parsed and diffed against
     the intent; a mismatch aborts the write.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gate_ledger as gl  # noqa: E402

# Exit codes. 0 covers every COMPLETED run (NOOP, applied, or conflicts
# reported) so a caller cannot read "I did work" as failure; a CI-style
# nonzero-on-drift belongs in a future `--check` flag, not overloaded here.
EXIT_OK = 0
EXIT_UNREADABLE = 3    # could not look — must never render as NOOP
EXIT_UNTRUSTWORTHY = 4  # parsed, but the parse cannot be trusted to edit
EXIT_VERIFY = 6        # post-write self-verification mismatch

# Keys eligible for an additive fill. Subset of gl._GATE_FIELD_KEYS by
# construction (asserted in tests): the writer must never emit a key the parser
# cannot consume, or the file would say something the readers cannot see.
#
# `unlocks` is deliberately EXCLUDED: absent (None -> linear default) and `[]`
# (terminal) are semantically distinct, so filling it could only destroy that
# distinction. It is reported instead.
FILL_KEYS = ("type", "kind", "description", "verifier", "signal",
             "signal_target", "blocks_dependents", "max_retries",
             "timeout_seconds")
REPORT_ONLY_KEYS = ("unlocks",)

# `description` has zero machine semantics (its only consumer is the display
# string in `format_list`). A project that reworded it would otherwise emit a
# CONFLICT on every run forever, training people to skim the report — and the
# report is the entire product. Fill when absent; stay silent when present.
NO_CONFLICT_KEYS = ("description",)


class SyncError(RuntimeError):
    """Fail-closed abort. Carries the process exit code."""

    def __init__(self, message: str, code: int = EXIT_UNREADABLE):
        super().__init__(message)
        self.code = code


def _read_text(path: str, what: str) -> str:
    """Read a registry file preserving line terminators exactly.

    ``newline=""`` disables universal-newline translation, so a CRLF file is
    not silently normalised to LF on read and then rewritten wholesale.
    """
    if not path:
        raise SyncError(f"{what}: no path given")
    if not os.path.isfile(path):
        raise SyncError(f"{what} is not a regular file: {path}")
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except UnicodeDecodeError as exc:
        raise SyncError(f"{what} is not valid UTF-8: {path} ({exc})") from exc
    except OSError as exc:
        raise SyncError(f"{what} could not be read: {path} ({exc})") from exc


def _dominant_terminator(raw: list[str]) -> str:
    """The line terminator inserted lines should carry."""
    counts: dict[str, int] = {}
    for line in raw:
        for term in ("\r\n", "\n", "\r"):
            if line.endswith(term):
                counts[term] = counts.get(term, 0) + 1
                break
    if not counts:
        return "\n"
    return max(counts.items(), key=lambda kv: (kv[1], kv[0] == "\n"))[0]


def _validate(layout: gl.RegistryLayout, path: str, *, is_reference: bool) -> None:
    """Refuse to proceed on anything that makes the parse untrustworthy."""
    label = "reference" if is_reference else "registry"
    if layout.open_line is None:
        hint = ""
        if layout.lines and layout.lines[0].lstrip("﻿").startswith("gates:") \
                and layout.lines[0].startswith("﻿"):
            hint = (" — the file starts with a UTF-8 BOM, which prevents the "
                    "`gates:` key from matching")
        elif any(line.strip().startswith("gates:") for line in layout.lines):
            hint = (" — a flow mapping (`gates: {}`) is not supported; use a "
                    "block mapping (`gates:` on its own line)")
        raise SyncError(
            f"{label} has no `gates:` block mapping: {path}{hint}")
    if is_reference:
        return
    if layout.duplicates:
        raise SyncError(
            f"registry has duplicate gate name(s): {', '.join(layout.duplicates)} "
            f"in {path}. The parser keeps only the LAST block and wipes the "
            f"earlier one's fields, so any additive edit would be computed "
            f"against a half-read file. Remove the duplicate and re-run.",
            EXIT_UNTRUSTWORTHY)
    if layout.orphan_field_names:
        raise SyncError(
            f"registry has gate(s) named {', '.join(layout.orphan_field_names)} "
            f"in {path} — these are field names, which means a gate's fields are "
            f"indented at or below the gate level and have already been read as "
            f"sibling gates. Fix the indentation and re-run.",
            EXIT_UNTRUSTWORTHY)
    if layout.close_starts_with_hash and _gates_follow_close(layout):
        raise SyncError(
            f"registry's `gates:` mapping is truncated by a column-0 comment at "
            f"line {layout.close_line + 1} of {path}, with more gate entries "
            f"below it. Everything after that comment is invisible to the "
            f"parser, so a sync would append DUPLICATES of gates already in the "
            f"file. Indent the comment and re-run.",
            EXIT_UNTRUSTWORTHY)
    if not layout.order:
        raise SyncError(
            f"registry's `gates:` mapping is empty in {path} — neither gate nor "
            f"field indentation can be observed, and inventing them risks "
            f"writing lines the parser would read back as sibling gates. "
            f"Populate the registry (`ait setup`) and re-run.",
            EXIT_UNTRUSTWORTHY)


def _gates_follow_close(layout: gl.RegistryLayout) -> bool:
    """Are there indented `name:` lines after the line that closed the mapping?"""
    import re
    for line in layout.lines[layout.close_line + 1:]:
        if re.match(r"^\S", line):
            break
        if re.match(r"^[ \t]+[A-Za-z0-9_]+:", line):
            return True
    return False


def resolve_field_indent(layout: gl.RegistryLayout,
                         block: gl.GateBlock) -> tuple[str, bool]:
    """Field indentation for ``block``. Returns ``(indent, was_derived)``.

    A total function over any layout that passed :func:`_validate`:

    1. the gate has fields  -> its OWN literal indent (YAML only requires
       consistency within a block, so a gate indented unlike its siblings is
       fine and needs no guard);
    2. header-only, but some other gate has fields -> the dominant observed
       delta (the file's house style), ties broken first-in-file-order;
    3. header-only and NO gate in the file has any field -> ``header_ws + "  "``.
       Two spaces deeper than an observed header is *provably* greater than
       ``gate_indent``, so the inserted line can never be re-read as a sibling
       gate — the only property that actually matters.

    (A file with no gate headers at all is rejected by :func:`_validate`; there
    is nothing to observe and inventing both levels is the corruption class.)
    """
    if block.field_ws is not None:
        return block.field_ws, False
    deltas: list[str] = []
    for name in layout.order:
        other = layout.blocks.get(name)
        if other is None or other.field_ws is None:
            continue
        if other.field_ws.startswith(other.header_ws):
            deltas.append(other.field_ws[len(other.header_ws):])
    if deltas:
        best = max(sorted(set(deltas), key=deltas.index),
                   key=lambda d: deltas.count(d))
        return block.header_ws + best, False
    return block.header_ws + "  ", True


def _default_for(key: str):
    return gl._default_gate_meta()[key]


def plan_sync(project_text: str, reference_text: str,
              project_path: str = "<registry>",
              reference_path: str = "<reference>") -> dict:
    """Pure planner: decide fills / conflicts / new gates. No I/O, no writes."""
    ref_layout = gl.registry_layout(reference_text)
    _validate(ref_layout, reference_path, is_reference=True)
    ref_parsed = gl.read_registry_text(reference_text)
    if not ref_parsed:
        raise SyncError(
            f"reference parsed to zero gates: {reference_path} — refusing to "
            f"report a clean sync against an empty or corrupt reference.")

    proj_layout = gl.registry_layout(project_text)
    _validate(proj_layout, project_path, is_reference=False)
    proj_parsed = gl.read_registry_text(project_text)

    fills: list[tuple[str, str, str]] = []      # (gate, key, raw_value)
    conflicts: list[tuple[str, str, str, str]] = []  # (gate, key, proj, ref)
    new_gates: list[str] = []

    for gate in ref_layout.order:
        ref_block = ref_layout.blocks[gate]
        if gate not in proj_layout.blocks:
            new_gates.append(gate)
            continue
        proj_block = proj_layout.blocks[gate]
        for key in ref_block.fields:
            if key in REPORT_ONLY_KEYS:
                # Never filled in either direction — absent and `[]` are
                # distinct and only the human knows which was meant.
                if key not in proj_block.fields:
                    conflicts.append((gate, key, "(absent)",
                                      ref_block.raw_values[key]))
                elif proj_block.raw_values[key] != ref_block.raw_values[key]:
                    conflicts.append((gate, key, proj_block.raw_values[key],
                                      ref_block.raw_values[key]))
                continue
            if key not in FILL_KEYS:
                # A reference key the parser does not know. It rides along in a
                # NEW_GATE copy (lexical extent) but is never filled into an
                # existing gate — the writer must not emit text the readers
                # would drop. The coverage drift guard in
                # tests/test_gates_reference_drift.sh fails when this happens.
                continue
            if key in proj_block.fields:
                if key in NO_CONFLICT_KEYS:
                    continue
                if proj_parsed.get(gate, {}).get(key) != ref_parsed[gate][key]:
                    conflicts.append((gate, key, proj_block.raw_values[key],
                                      ref_block.raw_values[key]))
                continue
            # Absent in the project. Only fill when the reference's value
            # actually differs from the parse default — writing
            # `blocks_dependents: false` or `max_retries: 0` is pure churn.
            if ref_parsed[gate][key] == _default_for(key):
                continue
            fills.append((gate, key, ref_block.raw_values[key]))

    return {
        "fills": fills,
        "conflicts": conflicts,
        "new_gates": new_gates,
        "proj_layout": proj_layout,
        "ref_layout": ref_layout,
        "ref_parsed": ref_parsed,
        "proj_parsed": proj_parsed,
    }


def _reindent(line: str, ref_gate_ws: str, ref_field_ws: str,
              dst_gate_ws: str, dst_field_ws: str) -> str:
    """Re-map one reference line's indentation onto the project's levels.

    Mandatory, not cosmetic: the reference is 2-space gate / 4-space field, so
    pasted verbatim into a 4/8 project the parser sets ``gate_indent = 4``, the
    pasted header at 2 still reads as a gate, and its fields at 4 satisfy
    ``4 <= 4`` and become sibling gates named `type`, `description`, `verifier`.
    """
    import re
    m = re.match(r"^([ \t]*)(.*)$", line)
    ws, rest = m.group(1), m.group(2)
    if not rest:
        return ""
    width = gl._indent_width(ws)
    ref_gate_w = gl._indent_width(ref_gate_ws)
    ref_field_w = gl._indent_width(ref_field_ws)
    if width <= ref_gate_w:
        return dst_gate_ws + rest
    if width <= ref_field_w:
        return dst_field_ws + rest
    return dst_field_ws + " " * (width - ref_field_w) + rest


def apply_sync(project_text: str, plan: dict) -> tuple[str, list[str]]:
    """Splice the planned fills / new gates into the project's own text.

    Returns ``(new_text, notes)``. Never re-joins with ``"\\n"``: the output is
    built from ``splitlines(keepends=True)`` so CRLF, a missing trailing
    newline, and exotic separators all survive untouched.
    """
    proj_layout: gl.RegistryLayout = plan["proj_layout"]
    ref_layout: gl.RegistryLayout = plan["ref_layout"]
    raw = list(proj_layout.raw)
    term = _dominant_terminator(raw)
    notes: list[str] = []

    # insertions: line index -> list of text lines to insert AFTER it
    insertions: dict[int, list[str]] = {}

    # --- fills into existing gate blocks ---------------------------------
    by_gate: dict[str, list[tuple[str, str]]] = {}
    for gate, key, value in plan["fills"]:
        by_gate.setdefault(gate, []).append((key, value))
    for gate, items in by_gate.items():
        block = proj_layout.blocks[gate]
        indent, derived = resolve_field_indent(proj_layout, block)
        if derived:
            notes.append(
                f"field indentation for '{gate}' was derived (no field line "
                f"exists anywhere in the registry); used {len(indent)} columns")
        ref_order = list(ref_layout.blocks[gate].fields)
        items.sort(key=lambda kv: ref_order.index(kv[0])
                   if kv[0] in ref_order else len(ref_order))
        lines = [f"{indent}{key}: {value}" for key, value in items]
        insertions.setdefault(block.last_field_end, []).extend(lines)

    # --- whole new gate blocks -------------------------------------------
    if plan["new_gates"]:
        anchor_name = proj_layout.order[0]
        anchor = proj_layout.blocks[anchor_name]
        dst_gate_ws = anchor.header_ws
        dst_field_ws, derived = resolve_field_indent(proj_layout, anchor)
        if derived:
            notes.append(
                "field indentation for appended gates was derived (no field "
                "line exists anywhere in the registry)")
        # Append after the last gate in the mapping, backing up over trailing
        # blanks so the separator stays between the mapping and the next key.
        stop = (proj_layout.close_line if proj_layout.close_line is not None
                else len(proj_layout.lines))
        append_at = stop - 1
        while append_at > 0 and not proj_layout.lines[append_at].strip():
            append_at -= 1
        block_lines: list[str] = []
        for gate in plan["new_gates"]:
            rb = ref_layout.blocks[gate]
            ref_field_ws = rb.field_ws if rb.field_ws is not None \
                else rb.header_ws + "  "
            # LEXICAL extent, not last_field_end: carries in-block comments,
            # unknown keys and their block-list items, so a reference schema
            # addition is never silently truncated out of the copy.
            for src in proj_or_ref_slice(ref_layout, rb):
                block_lines.append(_reindent(src, rb.header_ws, ref_field_ws,
                                             dst_gate_ws, dst_field_ws))
        insertions.setdefault(append_at, []).extend(block_lines)

    if not insertions:
        return project_text, notes

    # Ensure the anchor line is terminated before anything follows it.
    for idx in insertions:
        if idx == len(raw) - 1 and raw[idx] and not raw[idx].endswith(
                ("\n", "\r")):
            raw[idx] = raw[idx] + term

    out: list[str] = []
    for idx, line in enumerate(raw):
        out.append(line)
        for extra in insertions.get(idx, []):
            out.append(extra + term)
    return "".join(out), notes


def proj_or_ref_slice(layout: gl.RegistryLayout,
                      block: gl.GateBlock) -> list[str]:
    """The gate block's full lexical extent, terminator-free."""
    return layout.lines[block.header_line:block.block_end + 1]


def verify_sync(before_text: str, after_text: str, plan: dict) -> None:
    """Re-parse the candidate before writing. A hand-rolled textual writer earns
    trust exactly one way.

    Checks: the gate set changed only by the intended NEW_GATEs; every intended
    fill now parses equal to the reference; every other (gate, key) is
    unchanged; and the result still parses as a registry with no new duplicates
    or mis-indent orphans.
    """
    before = gl.read_registry_text(before_text)
    after = gl.read_registry_text(after_text)
    ref = plan["ref_parsed"]

    expected_names = set(before) | set(plan["new_gates"])
    if set(after) != expected_names:
        raise SyncError(
            f"self-verification failed: gate set would become "
            f"{sorted(after)}, expected {sorted(expected_names)}",
            EXIT_VERIFY)

    filled = {(g, k) for g, k, _ in plan["fills"]}
    for gate, key, _ in plan["fills"]:
        if after[gate][key] != ref[gate][key]:
            raise SyncError(
                f"self-verification failed: {gate}.{key} would parse as "
                f"{after[gate][key]!r}, expected {ref[gate][key]!r}",
                EXIT_VERIFY)
    for gate in before:
        for key in before[gate]:
            if (gate, key) in filled:
                continue
            if after[gate][key] != before[gate][key]:
                raise SyncError(
                    f"self-verification failed: {gate}.{key} changed from "
                    f"{before[gate][key]!r} to {after[gate][key]!r} but was "
                    f"not part of the plan",
                    EXIT_VERIFY)
    for gate in plan["new_gates"]:
        for key in ref[gate]:
            if after[gate][key] != ref[gate][key]:
                raise SyncError(
                    f"self-verification failed: appended {gate}.{key} parses "
                    f"as {after[gate][key]!r}, expected {ref[gate][key]!r}",
                    EXIT_VERIFY)

    layout = gl.registry_layout(after_text)
    if layout.open_line is None or layout.duplicates or layout.orphan_field_names:
        raise SyncError(
            "self-verification failed: the result would not re-parse cleanly "
            f"(duplicates={layout.duplicates}, "
            f"orphans={layout.orphan_field_names})",
            EXIT_VERIFY)


def scan_profiles(profile_files: list[str],
                  known_gates: set[str]) -> list[tuple[str, str, str]]:
    """Report profile-declared gate names with no registry entry (report-only).

    ``known_gates`` must be the POST-sync name set, so a profile naming a gate
    this very run adds is not reported — otherwise `--dry-run` and the applying
    run would disagree, which would break the idempotence check.

    Never edits a profile: t635_37 owns registry-driven profile editing and
    edit-time rejection in the settings TUI. A malformed profile warns and is
    skipped — it must never block a correct registry fill.
    """
    out: list[tuple[str, str, str]] = []
    for path in profile_files:
        stamp = os.path.basename(path)
        if stamp.endswith(".yaml"):
            stamp = stamp[:-5]
        parent = os.path.basename(os.path.dirname(path))
        if parent == "local":
            stamp = f"local/{stamp}"
        try:
            with open(path, encoding="utf-8") as fh:
                ptext = fh.read()
        except OSError as exc:
            sys.stderr.write(f"Warning: could not read profile {path}: {exc}\n")
            continue
        for key in ("default_gates", "rendered_gates"):
            if not gl._frontmatter_has_key(ptext, key):
                continue
            try:
                gl._validate_profile_gate_list_syntax(ptext, key, path)
            except gl.ProfileReadError as exc:
                sys.stderr.write(f"Warning: {exc}\n")
                continue
            for name in gl._read_frontmatter_list_from_text(ptext, key):
                if name not in known_gates:
                    out.append((stamp, key, name))
    return sorted(set(out))


def sync_registry(registry_file: str, reference_file: str, *,
                  dry_run: bool = False,
                  profile_files: list[str] | None = None,
                  scripts_dir: str | None = None) -> list[str]:
    """Run the reconcile. Returns the report lines; raises :class:`SyncError`.

    Writes only when ``dry_run`` is false AND there is something to write AND
    the post-write self-verification passes.
    """
    reference_text = _read_text(reference_file, "reference")
    project_text = _read_text(registry_file, "registry")

    plan = plan_sync(project_text, reference_text, registry_file, reference_file)

    report: list[str] = []
    for gate, key, value in plan["fills"]:
        report.append(f"FILLED:{gate}.{key}={value}")
    for gate in plan["new_gates"]:
        report.append(f"NEW_GATE:{gate}")
    for gate, key, proj, ref in plan["conflicts"]:
        report.append(f"CONFLICT:{gate}.{key}:{proj}|{ref}")

    known = set(plan["proj_layout"].blocks) | set(plan["new_gates"])
    for stamp, key, name in scan_profiles(profile_files or [], known):
        report.append(f"PROFILE_UNKNOWN:{stamp}.{key}:{name}")

    if plan["fills"] or plan["new_gates"]:
        new_text, notes = apply_sync(project_text, plan)
        for note in notes:
            sys.stderr.write(f"Note: {note}\n")
        verify_sync(project_text, new_text, plan)
        if not dry_run and new_text != project_text:
            # realpath: if gates.yaml is itself a FILE symlink, replacing the
            # link path would destroy the link and leave a regular file —
            # resolving first updates the target and the link survives. It also
            # keeps the adjacent tempfile on the target's filesystem so the
            # rename stays atomic across a cross-device link. (In the common
            # layout only the `aitasks/` DIRECTORY is a symlink, which path
            # traversal already resolves.)
            gl._atomic_write(os.path.realpath(registry_file), new_text)
        if scripts_dir:
            _warn_missing_verifiers(plan, scripts_dir)

    if not report:
        report.append("NOOP")
    return report


def _warn_missing_verifiers(plan: dict, scripts_dir: str) -> None:
    """Warn when a filled verifier names a script this install does not have.

    Filling `aitask-gate-build` into a project whose framework copy predates
    that script arms a gate that hard-fails at run time. Warn; do not fail, and
    do not invent a stdout verb for it.
    """
    for gate, key, value in plan["fills"]:
        if key != "verifier" or not value:
            continue
        name = value.strip("'\"")
        if name.startswith("aitask-gate-"):
            script = os.path.join(scripts_dir,
                                  "aitask_gate_" + name[len("aitask-gate-"):]
                                  .replace("-", "_") + ".sh")
            if not os.path.exists(script):
                sys.stderr.write(
                    f"Warning: filled {gate}.verifier={name} but "
                    f"{os.path.basename(script)} is not present in this "
                    f"install — the gate will error at run time until the "
                    f"framework is upgraded.\n")
