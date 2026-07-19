#!/usr/bin/env python3
"""Gate ledger parser / derivation / append for the aitasks gate framework.

Phase 1 (t635_1) substrate. This module is the single source of truth for:
  - parsing the marker-first ``## Gate Runs`` blockquotes,
  - deriving current per-gate state (last run wins),
  - appending a new gate-run block.

The bash ``aitask_gate.sh`` is the PRIMARY path (bash + awk). This module is the
documented fallback: ``aitask_gate.sh`` delegates here when ``AIT_GATES_BACKEND``
is ``python`` or when its awk scan fails (the framework doc's escape hatch).
The output format is kept byte-identical to the awk path so the two are
interchangeable (see tests/test_gate_ledger.sh parity checks).

t635_8 (shared TUI gate-ledger parser) EXTENDS this module — TUIs must import
``derive_status`` / ``parse_gate_runs`` from here rather than fork the logic.

Stdlib only: markers and the minimal registry are parsed with ``re``, never
PyYAML, so the fallback works in environments where PyYAML is unavailable.

CLI:
    gate_ledger.py append       <task-file> <gate> <status> [key=value ...]
    gate_ledger.py status       <task-file>
    gate_ledger.py list         <task-file> [registry.yaml]
    gate_ledger.py deps-unblock <task-file> [registry.yaml]
                                 -> SATISFIED | BLOCKED:<csv> | NO_GATES (t635_3)
    gate_ledger.py archive-ready <task-file>
                                 -> ALL_PASS | BLOCKED:<csv> | NO_GATES (t635_4)
    gate_ledger.py resume-point  <task-file>
                                 -> PLAN | IMPLEMENT | POSTIMPL (t635_5)
    gate_ledger.py active        <task-file> <gate>
                                 -> exit 0 iff gate in the enforced active set
                                    (t635_33; python twin of the bash verb)
    gate_ledger.py compute-active <task-file> <profile> [mv_allowlist_csv]
                                 -> ACTIVE:<csv> / FILTERED:<csv> / DIGEST:<d>
    gate_ledger.py active-status <task-file> <profile> <profile-name> [mv_allowlist_csv]
                                 -> ABSENT | FRESH | STALE:<stamped>-><current>

Supported append keys (anything else is ignored with a warning):
    marker line : run, status, attempt, duration, type
    body lines  : verifier, result, log, note
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
import os
import re
import sys

SECTION_HEADER = "## Gate Runs"
SECTION_COMMENT = (
    "<!-- Appended by the gate framework. Do not edit by hand; "
    "use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->"
)

VALID_STATUSES = ("pass", "fail", "pending", "running", "skip", "error")
# Statuses that count a gate as *satisfied* for unlock / archive / dependents
# (t635_11). ``skip`` = "evaluated, not applicable" → terminal-satisfied, kept
# distinct from ``pass`` in history but never blocking.
SATISFIED_STATUSES = frozenset({"pass", "skip"})
ICONS = {
    "pass": "✅",     # ✅
    "fail": "❌",     # ❌
    "pending": "⏸",  # ⏸
    "running": "\U0001f504",  # 🔄
    "skip": "⏭",     # ⏭
    "error": "⚠",    # ⚠
}

# Marker line: "> **<icon> gate:<name>** key=val key=val ..."
MARKER_RE = re.compile(r"^>\s*\*\*(\S+)\s+gate:([A-Za-z0-9_]+)\*\*(.*)$")
MARKER_SEARCH_RE = re.compile(r"(?m)^>\s*\*\*\S+\s+gate:[A-Za-z0-9_]+\*\*")
KV_RE = re.compile(r"(\w+)=(\S+)")
BODY_FIELD_RE = re.compile(r"^>\s*([^:>\n][^:\n]*):\s*(.*?)\s*$")

# Keys that live on the marker line, in this fixed order.
MARKER_KEYS = ("run", "status", "attempt", "duration", "type")
# Keys rendered as blockquote body lines, in this fixed order. The label is the
# display text; backtick=True wraps the value in `code` ticks.
BODY_KEYS = (
    ("verifier", "Verifier", True),
    ("result", "Result", False),
    ("log", "Log", True),
    ("note", "Note", False),
)
SUPPORTED_KEYS = set(MARKER_KEYS) | {k for k, _, _ in BODY_KEYS}


@dataclass(frozen=True)
class GateRun:
    """One parsed gate-run marker block."""

    name: str
    icon: str
    fields: dict[str, str]
    body_fields: dict[str, str] = field(default_factory=dict)
    line_number: int = 0
    raw_marker: str = ""
    raw_body_lines: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return self.fields.get("status", "?")

    @property
    def run_id(self) -> str:
        return self.fields.get("run", "")

    @property
    def attempt(self) -> str:
        return self.fields.get("attempt", "")

    def as_legacy_dict(self) -> dict:
        """Return the historical dict shape used by existing call sites."""
        out = {"name": self.name, "icon": self.icon}
        out.update(self.fields)
        return out


@dataclass(frozen=True)
class TaskGateState:
    """Structured gate state for TUI consumers.

    ``declared_gates`` is the task's raw declared intent (``gates:`` field);
    ``active_gates`` / ``filtered_gates`` are the enforced set and the
    profile-removed remainder from the validated tuple (t635_33; equal to
    declared / ``[]`` when no valid tuple exists). TUI *decision* surfaces
    (failed-gate classification, pending-human-gate detection, compact counts)
    must key off the active set — historical runs of filtered gates stay
    visible in ``status_text`` audit-only, never driving a classification.
    """

    task_file: str
    declared_gates: list[str]
    runs: list[GateRun]
    current: dict[str, GateRun]
    status_text: str
    archive_decision: str
    archive_pending: list[str]
    dependents_decision: str
    dependents_pending: list[str]
    resume_point: str
    active_gates: list[str] = field(default_factory=list)
    filtered_gates: list[str] = field(default_factory=list)


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
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Parsing / derivation -------------------------------------------------

def has_gate_markers(text: str) -> bool:
    """Cheap prefilter for task files that contain gate-run markers."""
    return bool(MARKER_SEARCH_RE.search(text))


def parse_gate_run_blocks(text: str) -> list[GateRun]:
    """Return every gate-run marker block in file order.

    This is the structured parser for Python consumers. It keeps the marker
    metadata and body summary fields together, while preserving the historical
    marker-only behavior through :func:`parse_gate_runs`.
    """
    runs: list[GateRun] = []
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        m = MARKER_RE.match(line)
        if not m:
            idx += 1
            continue

        marker_line_number = idx + 1
        raw_body: list[str] = []
        body_fields: dict[str, str] = {}
        idx += 1
        while idx < len(lines):
            nxt = lines[idx]
            if MARKER_RE.match(nxt) or re.match(r"^##\s+", nxt):
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

        runs.append(GateRun(
            name=m.group(2),
            icon=m.group(1),
            fields=dict(KV_RE.findall(m.group(3))),
            body_fields=body_fields,
            line_number=marker_line_number,
            raw_marker=line,
            raw_body_lines=tuple(raw_body),
        ))
    return runs


def derive_gate_runs(text: str) -> dict[str, GateRun]:
    """Map gate name -> current structured run (last marker wins)."""
    current: dict[str, GateRun] = {}
    for run in parse_gate_run_blocks(text):
        current[run.name] = run
    return current

def parse_gate_runs(text: str) -> list[dict]:
    """Return every gate-run marker in file order as a list of dicts.

    Each dict has at least ``name`` and ``icon`` plus any ``key=value`` pairs
    found on the marker line (notably ``status``, ``attempt``, ``run``).
    Markers are matched anywhere in the file — the pattern is unambiguous and
    does not appear in ordinary task prose — so a missing/renamed section header
    never loses runs.
    """
    return [run.as_legacy_dict() for run in parse_gate_run_blocks(text)]


def derive_status(text: str) -> dict[str, dict]:
    """Map gate name -> its current run (the last marker in file order wins)."""
    return {name: run.as_legacy_dict() for name, run in derive_gate_runs(text).items()}


def _format_status_line(name: str, run: dict) -> str:
    status = run.get("status", "?")
    attempt = run.get("attempt", "")
    run_id = run.get("run", "")
    extras = []
    if attempt:
        extras.append("attempt " + attempt)
    if run_id:
        extras.append("run " + run_id)
    suffix = " (" + ", ".join(extras) + ")" if extras else ""
    return f"{name}: {status}{suffix}"


def _format_gate_run_status_line(name: str, run: GateRun) -> str:
    return _format_status_line(name, run.as_legacy_dict())


def format_status(text: str) -> str:
    """Render derived state, one gate per line, in first-seen order."""
    order: list[str] = []
    seen: set[str] = set()
    for run in parse_gate_run_blocks(text):
        if run.name not in seen:
            seen.add(run.name)
            order.append(run.name)
    current = derive_gate_runs(text)
    return "\n".join(_format_gate_run_status_line(n, current[n]) for n in order)


def compact_gate_summary(state: TaskGateState) -> str:
    """Compact one-line gate summary for monitor TUI columns.

    Derived from the recorded gate runs (``state.current``, i.e. the last run
    per gate) — not ``declared_gates``, which is empty framework-wide today, so
    a declared-based count would read ``0/0`` for every task. Runs of
    profile-filtered gates (``state.filtered_gates``, t635_33) are excluded:
    a failed historical run of a now-inactive gate must not surface as an
    unmet gate in the at-a-glance column. Returns ``""`` when no counted gate
    runs are recorded, so callers can show no column for ungated tasks.
    Example output: ``"3/4 pass, 1 pending"``, ``"2/2 pass"``, or
    ``"1/3 pass, 1 pending, 1 failed"``.
    """
    runs = [r for r in state.current.values() if r.name not in state.filtered_gates]
    if not runs:
        return ""
    total = len(runs)
    n_pass = sum(1 for r in runs if r.status == "pass")
    n_fail = sum(1 for r in runs if r.status in ("fail", "error"))
    n_pending = total - n_pass - n_fail
    parts = [f"{n_pass}/{total} pass"]
    if n_pending:
        parts.append(f"{n_pending} pending")
    if n_fail:
        parts.append(f"{n_fail} failed")
    return ", ".join(parts)


# --- Append ---------------------------------------------------------------

def build_block(text: str, gate: str, status: str, fields: dict) -> str:
    """Build the marker-first blockquote for one gate run (no trailing newline).

    ``attempt`` is taken from ``fields`` if present, else auto-computed for
    pass/fail as (existing runs for this gate) + 1, else omitted. ``run`` is
    taken from ``fields`` if present, else generated as an ISO-8601-Z stamp.
    """
    fields = dict(fields)
    run_id = fields.pop("run", None) or iso_now()

    attempt = fields.pop("attempt", None)
    if attempt is None and status in ("pass", "fail"):
        existing = sum(1 for r in parse_gate_runs(text) if r["name"] == gate)
        attempt = str(existing + 1)

    icon = ICONS.get(status, "⚠")
    marker = f"> **{icon} gate:{gate}** run={run_id} status={status}"
    if attempt is not None:
        marker += f" attempt={attempt}"
    for key in ("duration", "type"):
        if fields.get(key):
            marker += f" {key}={fields[key]}"

    body_lines = []
    for key, label, backtick in BODY_KEYS:
        val = fields.get(key)
        if val:
            val = f"`{val}`" if backtick else val
            body_lines.append(f"> {label}: {val}")

    block = marker
    if body_lines:
        block += "\n>\n" + "\n".join(body_lines)
    return block


def append_block(text: str, gate: str, status: str, fields: dict) -> tuple[str, str]:
    """Return (new_text, rendered_block). Ensures the section exists at EOF."""
    block = build_block(text, gate, status, fields)

    out = text
    if not out.endswith("\n"):
        out += "\n"

    if not re.search(r"(?m)^##\s+Gate Runs\s*$", out):
        out += f"\n{SECTION_HEADER}\n{SECTION_COMMENT}\n"

    out += f"\n{block}\n"
    return out, block


def _atomic_write(path: str, content: str) -> None:
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


# --- Registry (minimal, stdlib-only 2-level parse) ------------------------

def _frontmatter_text(text: str) -> str:
    m = re.match(r"(?s)\A---\n(.*?)\n---\n", text)
    return m.group(1) if m else text


def _read_frontmatter_list_from_text(text: str, field: str) -> list[str]:
    """Read a frontmatter list ``field`` from raw task text.

    Returns ``[]`` when the field is absent or empty. Used for both ``gates:``
    and ``also_blocks_dependents:`` (t635_3).
    """
    fm = _frontmatter_text(text)
    # Inline: field: [a, b]
    inline = re.search(rf"(?m)^{re.escape(field)}:\s*\[(.*?)\]\s*$", fm)
    if inline:
        return [g.strip().strip("'\"") for g in inline.group(1).split(",") if g.strip()]
    # Block: field:\n  - a\n  - b
    block = re.search(rf"(?m)^{re.escape(field)}:\s*$\n((?:[ \t]*-[ \t]*.+\n?)*)", fm)
    if block:
        return [re.sub(r"^[ \t]*-[ \t]*", "", ln).strip().strip("'\"")
                for ln in block.group(1).splitlines() if ln.strip()]
    return []


def _read_frontmatter_list(task_file: str, field: str) -> list[str]:
    """Read a frontmatter list ``field`` (inline ``[a, b]`` or block ``- a``)."""
    with open(task_file, encoding="utf-8") as fh:
        return _read_frontmatter_list_from_text(fh.read(), field)


def read_declared_gates(task_file: str) -> list[str]:
    """Read the task's ``gates:`` frontmatter list (inline or block style)."""
    return _read_frontmatter_list(task_file, "gates")


def read_declared_gates_from_text(text: str) -> list[str]:
    """Read the task's ``gates:`` frontmatter list from raw task text."""
    return _read_frontmatter_list_from_text(text, "gates")


def _frontmatter_has_key(text: str, key: str) -> bool:
    """True iff the frontmatter declares ``key:`` at all (even empty / ``[]``).

    Distinguishes an ABSENT field from a present-but-empty one — e.g. ``gates:``
    absent (eligible for profile backfill) vs an explicit ``gates: []`` opt-out
    (which must be preserved). ``read_declared_gates`` returns ``[]`` for both, so
    it cannot make this distinction; the Step-7 backfill keys off this oracle so a
    deliberate opt-out is never overwritten (t635_14).
    """
    fm = _frontmatter_text(text)
    return re.search(rf"(?m)^{re.escape(key)}:", fm) is not None


def _read_profile_default_gates(profile_file: str) -> list[str]:
    """Read ``default_gates`` from a profile YAML file.

    Profiles are plain YAML (no ``---`` fence); ``_frontmatter_text`` returns the
    whole document when unfenced, so the shared list reader handles both inline
    ``[a, b]`` and block form. Graceful degradation (t635_14): an unreadable or
    missing file warns to stderr and yields ``[]`` — never raises.
    """
    try:
        with open(profile_file, encoding="utf-8") as fh:
            return _read_frontmatter_list_from_text(fh.read(), "default_gates")
    except OSError as exc:
        sys.stderr.write(f"Warning: could not read profile {profile_file!r}: {exc}\n")
        return []


def effective_gates(task_file: str, profile_file: str | None = None) -> list[str]:
    """Resolve the task's *effective* gate set (t635_14).

    If the task's frontmatter declares a ``gates:`` field (present, even ``[]``),
    it is authoritative. Otherwise fall back to the active profile's
    ``default_gates`` (when ``profile_file`` is given and readable). Returns ``[]``
    when neither applies. Used ONLY in the read-only planning window — once Step 7
    backfills ``gates:`` onto the task, the literal field is authoritative
    everywhere (producer + orchestrator + archival all read it).
    """
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    if _frontmatter_has_key(text, "gates"):
        return read_declared_gates_from_text(text)
    if profile_file:
        return _read_profile_default_gates(profile_file)
    return []


def should_self_record(task_file: str, gate: str) -> bool:
    """Whether task-workflow should self-record ``gate`` at Step 7.

    True iff the gate is **not** in the task's enforced active set — the same
    set the Step-9 orchestrator runs and records from (t635_33; previously the
    literal ``gates:`` field, t635_13 req #3 / t635_14). A gate in the active
    set is recorded by the orchestrator, so the Step-7 self-record must skip it.
    Reading the ENFORCED set matters since the Step-7 ``gates:`` backfill was
    replaced by claim-time materialization: a profile-default gate now lives in
    ``active_gates`` (raw ``gates:`` stays absent), and a literal-declared read
    here would self-record it AND let the orchestrator record it — the
    double-record this decision exists to prevent.
    """
    with open(task_file, encoding="utf-8") as fh:
        return gate not in read_active_gates_from_text(fh.read())


# --- Active-gates tuple (t635_33) -----------------------------------------
#
# The execution profile renders a gate-machinery ceiling (`rendered_gates`,
# defaulting to `default_gates`); the task's `gates:` selects within it at
# runtime. The profile-filtered result is persisted on the task as a mandatory
# atomic four-field tuple, written at claim time (task-workflow Step 4 via
# `aitask_gate.sh materialize-active`):
#
#   active_gates:          the enforced set (may be [])
#   active_gates_filtered: gates the profile ceiling removed (declared intent
#                          minus active — consumed by dependency-unblock so
#                          declared-but-filtered `also_blocks_dependents`
#                          entries are dropped while independent ones survive)
#   active_gates_profile:  provenance stamp (producing profile name)
#   active_gates_digest:   <gates>.<profile>.<outputs> — 12-hex sha256 halves
#                          over ALL resolve inputs AND the stored outputs
#
# Every enforcer reads through `read_active_tuple_from_text`, which validates
# the two profileless digest halves (gates + outputs) and fails CLOSED to the
# raw `gates:` field: a stale (edited `gates:`) or corrupt (hand-edited
# outputs) tuple is treated as absent, so declared intent governs — the tuple
# can over-block until the next materialization but never silently
# under-enforce. Raw `gates:` stays the task's declared intent; `active_gates`
# is the enforced set.

ACTIVE_TUPLE_FIELDS = ("active_gates", "active_gates_filtered",
                       "active_gates_profile", "active_gates_digest")


def _hash12(s: str) -> str:
    """First 12 hex chars of sha256 — must stay byte-identical to the bash
    twin `_gate_hash12` in aitask_gate.sh (cross-checked by
    tests/test_gate_active_gates.sh)."""
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def _read_frontmatter_scalar_from_text(text: str, key: str) -> str:
    """Read a scalar frontmatter field's value ('' when absent)."""
    fm = _frontmatter_text(text)
    m = re.search(rf"(?m)^{re.escape(key)}:\s*(.*?)\s*$", fm)
    return m.group(1).strip().strip("'\"") if m else ""


def _gates_half_input(text: str) -> str:
    """Canonical digest input for the raw ``gates:`` field state.

    Covers presence/absence AND content, so a reader WITHOUT a profile can
    detect a same-profile manual ``gates:`` edit. `gates=absent` (no key) is
    distinct from `gates=` (explicit ``[]`` opt-out).
    """
    if _frontmatter_has_key(text, "gates"):
        return "gates=" + ",".join(read_declared_gates_from_text(text))
    return "gates=absent"


def _profile_half_input(default_gates: list[str], rendered_set: list[str]) -> str:
    """Canonical digest input for BOTH profile inputs. ``default_gates`` is a
    resolve input for any task without an explicit ``gates:`` field, so an
    edit to it under an unchanged ``rendered_gates`` must still change the
    digest."""
    return ("default_gates=" + ",".join(default_gates)
            + "|rendered_gates=" + ",".join(rendered_set))


def _outputs_half_input(active: list[str], filtered: list[str]) -> str:
    """Canonical digest input for the stored tuple values themselves, so a
    hand-edited or partially-updated active set is detected as corrupt rather
    than trusted (input-only authentication would let a corrupted output pass
    while ``gates:`` is unchanged, silently under-enforcing)."""
    return "active=" + ",".join(active) + "|filtered=" + ",".join(filtered)


def build_active_digest(text: str, default_gates: list[str], rendered_set: list[str],
                        active: list[str], filtered: list[str]) -> str:
    return ".".join((
        _hash12(_gates_half_input(text)),
        _hash12(_profile_half_input(default_gates, rendered_set)),
        _hash12(_outputs_half_input(active, filtered)),
    ))


def _digest_profileless_halves_match(text: str) -> bool:
    """Validate the two digest halves checkable WITHOUT a profile in scope:
    the gates-half against the current raw ``gates:`` field and the
    outputs-half against the stored tuple values."""
    digest = _read_frontmatter_scalar_from_text(text, "active_gates_digest")
    parts = digest.split(".")
    if len(parts) != 3:
        return False
    active = _read_frontmatter_list_from_text(text, "active_gates")
    filtered = _read_frontmatter_list_from_text(text, "active_gates_filtered")
    return (parts[0] == _hash12(_gates_half_input(text))
            and parts[2] == _hash12(_outputs_half_input(active, filtered)))


def read_active_tuple_from_text(text: str) -> tuple[list[str], list[str], bool]:
    """(active, filtered, tuple_valid). ALL enforcement consumers go through
    this single reader so ``active_gates`` and ``active_gates_filtered`` can
    never be read under different validity conclusions — a stale filtered list
    must not keep removing a newly-declared blocker after ``active_gates``
    already fell back to raw intent.

    Tuple present + both profileless digest halves valid → authoritative (even
    ``[]`` — the safety valve that makes a declared-but-unrendered gate
    invisible). Stale or corrupt → treated as ABSENT: fall back to the raw
    ``gates:`` field (declared intent, today's behavior) with ``filtered=[]``.
    """
    if _frontmatter_has_key(text, "active_gates"):
        if _digest_profileless_halves_match(text):
            return (_read_frontmatter_list_from_text(text, "active_gates"),
                    _read_frontmatter_list_from_text(text, "active_gates_filtered"),
                    True)
        # stale (gates: edited) or corrupt (outputs edited) → tuple ignored
    return (read_declared_gates_from_text(text), [], False)


def read_active_gates_from_text(text: str) -> list[str]:
    """Convenience for set-only enforcement sites."""
    return read_active_tuple_from_text(text)[0]


def _read_profile_rendered_gates(profile_file: str) -> list[str]:
    """Resolve the profile's render ceiling (t635_33).

    ``rendered_gates`` if the KEY is present — even ``[]``, an explicit
    render-nothing override — else ``default_gates``, else ``[]``.
    Key-presence, NOT truthiness: an ``or``-chain would make an explicit
    ``rendered_gates: []`` fall back to a nonempty ``default_gates`` and
    render machinery the profile disabled. Same semantics as the render
    context in skill_template.py and the bash compute path.
    """
    try:
        with open(profile_file, encoding="utf-8") as fh:
            ptext = fh.read()
    except OSError as exc:
        sys.stderr.write(f"Warning: could not read profile {profile_file!r}: {exc}\n")
        return []
    if _frontmatter_has_key(ptext, "rendered_gates"):
        return _read_frontmatter_list_from_text(ptext, "rendered_gates")
    return _read_frontmatter_list_from_text(ptext, "default_gates")


class ProfileReadError(RuntimeError):
    """A profile file required for an authoritative compute is missing,
    unreadable, or not plausibly a profile. Deliberately DISTINCT from the
    warn-and-degrade behavior of the introspection readers: computing an
    active set from a half-read profile would persist ``active_gates: []``
    and silently disable gates."""


# A gate name, optionally in a MATCHED quote pair (mismatched quoting like
# `'x"` is rejected — the regex readers would silently strip it).
_GATE_LIST_ITEM_RE = re.compile(r"(?:[A-Za-z0-9_]+|'[A-Za-z0-9_]+'|\"[A-Za-z0-9_]+\")")


def _validate_profile_gate_list_syntax(ptext: str, key: str, profile_file: str) -> None:
    """Reject a PRESENT gate-list key whose value is not a well-formed list.

    The regex list readers return ``[]`` (or silently normalize) anything they
    cannot parse — for an authoritative compute that would turn a typo like
    ``default_gates: [unclosed``, a scalar value, ``[a,,b]``, or a mis-dashed
    block into an empty/guessed render ceiling and persist ``active_gates:
    []``, silently disabling gates. Accepted shapes, matching the readers:
      * inline ``[...]`` on the key's own line, empty or with every
        comma-separated item a (possibly quoted) gate name;
      * a bare ``key:`` followed by ``- item`` block lines (each item a gate
        name); a bare key with no indented lines reads as empty.
    The value match is anchored to the key's OWN line (horizontal whitespace
    only) so block form is never mis-read as a scalar.
    """
    fm = _frontmatter_text(ptext)
    m = re.search(rf"(?m)^{re.escape(key)}:[ \t]*(.*?)[ \t]*$", fm)
    if not m:
        return  # key absent — nothing to validate

    def _bad(detail: str):
        raise ProfileReadError(
            f"profile {profile_file!r} has a malformed {key}: {detail} "
            f"(expected a YAML list like [a, b] or `- item` block lines)")

    val = m.group(1)
    if val:
        inline = re.fullmatch(r"\[(.*)\]", val)
        if not inline:
            _bad(f"scalar/unterminated value {val!r}")
        inner = inline.group(1).strip()
        if inner:
            for part in inner.split(","):
                if not _GATE_LIST_ITEM_RE.fullmatch(part.strip()):
                    _bad(f"invalid list item {part.strip()!r} in {val!r}")
        return
    # Bare `key:` — block form. YAML (and the readers) accept sequence items
    # at ANY indentation, including none, so a dash line is a list item
    # wherever it sits — it must carry a valid gate name (a bare `-` reads as
    # [] and would silently empty the ceiling). The block ends at the first
    # non-dash unindented line (the next top-level key); an indented non-dash
    # line inside the block is malformed. A dash item AFTER a blank line is
    # also rejected: both regex readers stop consuming at the blank, so the
    # trailing items would be silently DROPPED from the parsed set — the one
    # disagreement worse than a loud error. (Trailing blanks before the next
    # key are fine.)
    lines = fm.splitlines()
    start = fm[:m.start()].count("\n") + 1
    blank_pending = False
    item_seen = False
    for ln in lines[start:]:
        if not ln.strip():
            blank_pending = True
            continue
        if re.match(r"^[ \t]*-(?:[ \t]|$)", ln):
            # Only a blank INSIDE an already-started list is a split (the
            # reader stops there and would drop the rest); blanks between the
            # key line and the first item are consumed by the reader and fine.
            if blank_pending and item_seen:
                _bad("a blank line splits the block list — the reader stops "
                     "at blank lines and would drop the items after it; "
                     "keep items contiguous")
            blank_pending = False
            bm = re.match(r"^[ \t]*-[ \t]*(\S.*?)[ \t]*$", ln)
            if not bm or not _GATE_LIST_ITEM_RE.fullmatch(bm.group(1)):
                _bad(f"invalid block line {ln.strip()!r}")
            item_seen = True
            continue
        if re.match(r"^[ \t]+", ln):
            _bad(f"invalid block line {ln.strip()!r}")
        break  # dedented non-item line — next top-level key, block ended


def _read_profile_text_strict(profile_file: str) -> str:
    """Read a profile for compute_active_gates — fail loudly, never degrade.

    Requires a regular, readable file whose content carries a top-level
    ``name:`` key (every shipped profile does) and syntactically list-shaped
    ``default_gates`` / ``rendered_gates`` values when those keys are present
    — so a directory, a file that vanished after the caller's precheck, or
    garbage/malformed content raises instead of resolving to an empty render
    ceiling.
    """
    import os.path
    if not os.path.isfile(profile_file):
        raise ProfileReadError(f"profile is not a regular file: {profile_file!r}")
    try:
        with open(profile_file, encoding="utf-8") as fh:
            ptext = fh.read()
    except OSError as exc:
        raise ProfileReadError(f"cannot read profile {profile_file!r}: {exc}") from exc
    if not _frontmatter_has_key(ptext, "name"):
        raise ProfileReadError(
            f"profile {profile_file!r} has no top-level 'name:' key — not a profile?")
    _validate_profile_gate_list_syntax(ptext, "default_gates", profile_file)
    _validate_profile_gate_list_syntax(ptext, "rendered_gates", profile_file)
    return ptext


def compute_active_gates(text: str, profile_file: str,
                         mv_allowlist: tuple[str, ...] = ()) -> tuple[list[str], list[str], str]:
    """Compute (active, filtered, digest) for a task under a profile.

    ``active = resolve(task.gates, profile.default_gates) ∩ rendered_set``;
    ``filtered`` is what the ceiling removed. For ``issue_type:
    manual_verification`` the resolved set is first intersected with
    ``mv_allowlist`` (the t1156 reachable-gates allowlist, passed in by the
    bash caller from task_utils.sh's MANUAL_VERIFICATION_REACHABLE_GATES so
    there is a single source) — such tasks skip Steps 6-8, so an unreachable
    gate would block archival forever; stripped-as-unreachable gates land in
    neither ``active`` nor ``filtered``.

    Raises :class:`ProfileReadError` on a missing/invalid profile — this is
    the authoritative write path, so a read failure must propagate (the bash
    caller then clears any stale tuple and exits nonzero) rather than degrade
    to an empty ceiling that would persist ``active_gates: []``.
    """
    ptext = _read_profile_text_strict(profile_file)
    default_gates = _read_frontmatter_list_from_text(ptext, "default_gates")
    if _frontmatter_has_key(ptext, "rendered_gates"):
        rendered = _read_frontmatter_list_from_text(ptext, "rendered_gates")
    else:
        rendered = list(default_gates)
    if _frontmatter_has_key(text, "gates"):
        resolved = read_declared_gates_from_text(text)
    else:
        resolved = list(default_gates)
    if _read_frontmatter_scalar_from_text(text, "issue_type") == "manual_verification":
        resolved = [g for g in resolved if g in mv_allowlist]
    active = [g for g in resolved if g in rendered]
    filtered = [g for g in resolved if g not in rendered]
    digest = build_active_digest(text, default_gates, rendered, active, filtered)
    return active, filtered, digest


def active_tuple_status(text: str, profile_file: str, profile_name: str,
                        mv_allowlist: tuple[str, ...] = ()) -> str:
    """Freshness of the persisted tuple vs the CURRENTLY governing profile.

    Returns ``ABSENT`` (no tuple), ``FRESH`` (stamp, digest, and stored values
    all match a recomputation under ``profile_file``), or
    ``STALE:<stamped>-><current>``. Uses the same compute path as
    materialize-active so freshness comparison applies the identical rule
    (incl. the manual-verification allowlist).
    """
    if not _frontmatter_has_key(text, "active_gates"):
        return "ABSENT"
    stamped = _read_frontmatter_scalar_from_text(text, "active_gates_profile")
    stored_digest = _read_frontmatter_scalar_from_text(text, "active_gates_digest")
    stored_active = _read_frontmatter_list_from_text(text, "active_gates")
    stored_filtered = _read_frontmatter_list_from_text(text, "active_gates_filtered")
    active, filtered, digest = compute_active_gates(text, profile_file, mv_allowlist)
    if (stamped == profile_name and stored_digest == digest
            and stored_active == active and stored_filtered == filtered):
        return "FRESH"
    return f"STALE:{stamped or '(unknown)'}->{profile_name}"


def _truthy(value: str) -> bool:
    """YAML-ish boolean: true/yes/on/1 (case-insensitive) -> True, else False."""
    return value.strip().strip("'\"").lower() in ("true", "yes", "on", "1")


def _indent_width(ws: str) -> int:
    """Indent width counting a tab as one level-ish (files use spaces)."""
    return len(ws.replace("\t", "    "))


def _int_or(value: str, default):
    """Parse an int from a YAML scalar; return ``default`` when not an int."""
    try:
        return int(value.strip().strip("'\""))
    except (ValueError, AttributeError):
        return default


def _parse_inline_list(value: str):
    """Parse an inline YAML list ``[a, b]`` → list (``[]`` for ``[]``).

    Returns ``None`` when ``value`` is not bracketed (so the caller can fall
    back to block-list parsing).
    """
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    return None


def _default_gate_meta() -> dict:
    """Default per-gate registry record.

    ``unlocks`` defaults to ``None`` meaning the key is ABSENT — the
    orchestrator uses the linear default (next gate in the task's ``gates:``
    list) for that gate. An explicit ``unlocks: []`` parses to ``[]`` (terminal,
    unlocks nothing) and is deliberately distinct from ``None`` (t635_11,
    concern 1).
    """
    return {
        "type": "", "description": "", "blocks_dependents": False,
        "verifier": "", "max_retries": 0, "unlocks": None,
        "timeout_seconds": None, "signal": "", "signal_target": "",
        "kind": "",
    }


def read_registry(registry_file: str) -> dict[str, dict]:
    """Parse gates.yaml with ``re`` only (stdlib, no PyYAML).

    Returns ``name -> {type, kind, description, blocks_dependents, verifier,
    max_retries, unlocks, timeout_seconds, signal, signal_target}``.

    - ``blocks_dependents`` (t635_3) marks a gate required-to-pass before the
      owning task's dependents unblock; defaults to ``False``.
    - ``kind`` (t635_19) — ``"procedure"`` marks a procedure-backed (agent-skill)
      gate the headless engine defers (`needs-agent`); ``""``/absent or
      ``"command"`` = a normal command verifier.
    - ``verifier`` (t635_11) — command the orchestrator runs; ``""`` = no
      auto-run.
    - ``max_retries`` (t635_11) — int, default ``0`` (single shot).
    - ``unlocks`` (t635_11) — ``None`` when ABSENT (→ linear default) vs a
      ``list[str]`` when present (``[]`` = terminal). Inline ``[a, b]`` or block
      ``- a`` form.
    - ``timeout_seconds`` (t635_11) — int or ``None``.
    - ``signal`` / ``signal_target`` (t635_11) — human-gate signal kind + target.

    The parser is **indent-aware**: a gate header is a ``name:`` at the first
    gate's indent depth; deeper-indented ``name:`` lines (e.g. a block-form
    ``unlocks:``) are fields of the current gate, not new gates.
    """
    gates: dict[str, dict] = {}
    if not registry_file or not os.path.exists(registry_file):
        return gates
    with open(registry_file, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    in_gates = False
    gate_indent = None
    cur = None
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if re.match(r"^gates:\s*$", line):
            in_gates = True
            i += 1
            continue
        if not in_gates or not line.strip():
            i += 1
            continue
        # A non-indented, non-blank line ends the gates: mapping.
        if re.match(r"^\S", line):
            in_gates = False
            cur = None
            i += 1
            continue
        m = re.match(r"^([ \t]+)([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        indent, key, val = _indent_width(m.group(1)), m.group(2), m.group(3).strip()
        if gate_indent is None:
            gate_indent = indent
        if indent <= gate_indent:
            # New gate header (its fields are more-indented).
            cur = key
            gates[cur] = _default_gate_meta()
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        # A field of the current gate.
        if key == "type":
            gates[cur]["type"] = val.strip("'\"")
        elif key == "kind":
            # t635_19 — "procedure" marks a procedure-backed (agent-skill) gate
            # the headless engine defers; absent/"command" = normal command verifier.
            gates[cur]["kind"] = val.strip("'\"")
        elif key == "description":
            gates[cur]["description"] = val.strip("'\"")
        elif key == "blocks_dependents":
            gates[cur]["blocks_dependents"] = _truthy(val)
        elif key == "verifier":
            gates[cur]["verifier"] = val.strip("'\"")
        elif key == "max_retries":
            gates[cur]["max_retries"] = _int_or(val, 0)
        elif key == "timeout_seconds":
            gates[cur]["timeout_seconds"] = _int_or(val, None)
        elif key == "signal":
            gates[cur]["signal"] = val.strip("'\"")
        elif key == "signal_target":
            gates[cur]["signal_target"] = val.strip("'\"")
        elif key == "unlocks":
            inline = _parse_inline_list(val)
            if inline is not None:
                gates[cur]["unlocks"] = inline
            elif val:
                gates[cur]["unlocks"] = [val.strip("'\"")]
            else:
                # Block form: consume deeper-indented "- item" lines.
                items: list[str] = []
                j = i + 1
                while j < n:
                    bl = lines[j]
                    if not bl.strip():
                        j += 1
                        continue
                    bm = re.match(r"^([ \t]+)-[ \t]*(.+?)\s*$", bl)
                    if bm and _indent_width(bm.group(1)) > indent:
                        items.append(bm.group(2).strip().strip("'\""))
                        j += 1
                        continue
                    break
                gates[cur]["unlocks"] = items
                i = j
                continue
        i += 1
    return gates


def format_list(task_file: str, registry_file: str | None) -> str:
    # Deliberately the DECLARED set (t635_33): `list` is the declared-intent
    # introspection verb; the enforced active set is displayed by
    # `aitask_gate.sh active-gates-status` (full tuple + freshness).
    declared = read_declared_gates(task_file)
    if not declared:
        return "(no gates declared)"
    registry = read_registry(registry_file) if registry_file else {}
    lines = []
    for g in declared:
        meta = registry.get(g, {})
        gtype = meta.get("type", "")
        desc = meta.get("description", "")
        parts = [g]
        if gtype:
            parts.append(f"[{gtype}]")
        if desc:
            parts.append(f"- {desc}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


# --- Dependency-unblock decision (t635_3) ---------------------------------

def required_unblock_gates(declared: list[str], also: list[str],
                          registry: dict[str, dict]) -> list[str]:
    """Gates that must pass before the owning task's dependents unblock.

    The registry-default set (declared gates flagged ``blocks_dependents``) plus
    the per-task ``also_blocks_dependents`` additions, de-duplicated in order.
    """
    req = [g for g in declared if registry.get(g, {}).get("blocks_dependents")]
    for g in also:
        if g not in req:
            req.append(g)
    return req


def _dependents_status_from_state(declared: list[str], also: list[str],
                                  registry: dict[str, dict],
                                  state: dict[str, GateRun]) -> tuple[str, list[str]]:
    required = required_unblock_gates(declared, also, registry)
    if not required:
        return ("NO_GATES", [])
    pending = [g for g in required
               if (state.get(g).status if state.get(g) else None) not in SATISFIED_STATUSES]
    return ("BLOCKED", pending) if pending else ("SATISFIED", [])


def dependents_status(task_file: str, registry_file: str | None) -> tuple[str, list[str]]:
    """Decide whether ``task_file`` releases its dependents.

    Reads the ENFORCED active set (t635_33) — a profile-filtered gate must not
    hold dependents. ``also_blocks_dependents`` entries are filtered by the
    persisted ``active_gates_filtered`` list, dropping exactly the
    declared-but-filtered gates while keeping independent blockers (e.g. a
    checkpoint gate like ``merge_approved`` that is intentionally listed
    without being declared). Both reads come from the ONE validated tuple
    reader: an absent/stale/corrupt tuple yields ``filtered=[]``, so ``also``
    degrades to unfiltered in the same decision that falls ``active_gates``
    back to raw intent.

    Returns one of:
      - ``("NO_GATES", [])``   — no required-to-unblock gates (ungated, or a
        gated task that flags none as blocking). Caller falls back to today's
        file-existence behavior (block until archived).
      - ``("SATISFIED", [])``  — every required gate has derived status ``pass``;
        dependents may proceed even while non-required gates still pend.
      - ``("BLOCKED", pending)`` — one or more required gates are not ``pass``.
    """
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    active, filtered, _valid = read_active_tuple_from_text(text)
    also = _read_frontmatter_list_from_text(text, "also_blocks_dependents")
    also_effective = [g for g in also if g not in filtered]
    registry = read_registry(registry_file) if registry_file else {}
    return _dependents_status_from_state(active, also_effective, registry,
                                         derive_gate_runs(text))


# --- Gate-guarded archival decision (t635_4) ------------------------------

def _archive_status_from_state(declared: list[str],
                               state: dict[str, GateRun]) -> tuple[str, list[str]]:
    if not declared:
        return ("NO_GATES", [])
    nonpass = [g for g in declared
               if (state.get(g).status if state.get(g) else None) not in SATISFIED_STATUSES]
    return ("BLOCKED", nonpass) if nonpass else ("ALL_PASS", [])


def unmet_procedure_gates(task_file: str, registry_file: str | None) -> list[str]:
    """Declared gates that are ``kind: procedure`` AND not terminal-satisfied
    (t635_19). The attended dispatch seam (task-workflow Step 8 / aitask-resume)
    runs each such gate's skill. A gate already ``pass``/``skip`` is done and is
    excluded (it must NOT be re-dispatched)."""
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    active = read_active_gates_from_text(text)  # enforced set (t635_33)
    if not active:
        return []
    registry = read_registry(registry_file) if registry_file else {}
    state = derive_gate_runs(text)
    out = []
    for g in active:
        if registry.get(g, {}).get("kind") != "procedure":
            continue
        st = state.get(g).status if state.get(g) else None
        if st not in SATISFIED_STATUSES:
            out.append(g)
    return out


def archive_status(task_file: str) -> tuple[str, list[str]]:
    """Decide whether ``task_file`` may archive (D5: every declared gate pass).

    Unlike :func:`dependents_status` (which filters to ``blocks_dependents``
    gates), archival requires **every** declared gate to pass — so no registry
    lookup is needed. A declared gate with no recorded run counts as not-pass.

    Returns one of:
      - ``("NO_GATES", [])``   — no declared gates → archive as today (the
        dormant case until t635_14 populates ``gates:``).
      - ``("ALL_PASS", [])``   — every declared gate has derived status ``pass``.
      - ``("BLOCKED", nonpass)`` — one or more declared gates are not ``pass``.
    """
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    return archive_status_from_text(text)


def archive_status_from_text(text: str) -> tuple[str, list[str]]:
    """Content-level twin of :func:`archive_status` — no filesystem open.

    Lets callers that already hold the task body (e.g. the stats active-task
    scan, which iterates ``(filename, content)`` pairs) classify archival
    readiness deterministically, without re-reading a path that may not exist
    under a rebased project root. Composes the shared primitives — no parsing
    fork (D6). Reads the ENFORCED active set (t635_33): a profile-filtered
    gate can never block archival.
    """
    return _archive_status_from_state(
        read_active_gates_from_text(text), derive_gate_runs(text))


# --- Ledger-driven re-entry decision (t635_5) -----------------------------

def resume_point(task_file: str) -> str:
    """Derive the task-workflow resume stage from the *recorded checkpoint* ledger.

    Keys off the recorded ``## Gate Runs`` checkpoints (t635_2:
    ``plan_approved`` / ``review_approved``), NOT the declared ``gates:`` field —
    so it is independent of :func:`archive_status` / :func:`dependents_status`.
    State is derived back-to-front (last block per gate wins) via
    :func:`derive_status`, so a re-opened checkpoint (e.g. ``pass`` → ``fail``)
    correctly demotes the resume stage.

    Returns one of:
      - ``"PLAN"``      — ``plan_approved`` not ``pass`` (incl. an empty ledger):
        nothing durable recorded → plan from scratch (today's flow).
      - ``"IMPLEMENT"`` — ``plan_approved`` ``pass`` but ``review_approved`` not
        ``pass`` → resume at the Step 7 implementation body.
      - ``"POSTIMPL"``  — ``review_approved`` ``pass`` → resume at Step 9
        (merge / build / archive pending).
    """
    with open(task_file, encoding="utf-8") as fh:
        state = derive_gate_runs(fh.read())
    return _resume_point_from_state(state)


def _resume_point_from_state(state: dict[str, GateRun]) -> str:
    def passed(gate: str) -> bool:
        run = state.get(gate)
        return run is not None and run.status == "pass"

    if not passed("plan_approved"):
        return "PLAN"
    if not passed("review_approved"):
        return "IMPLEMENT"
    return "POSTIMPL"


def read_task_gate_state(task_file: str, registry_file: str | None = None) -> TaskGateState:
    """Read a task file once and derive all gate state needed by TUIs."""
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    runs = parse_gate_run_blocks(text)
    current: dict[str, GateRun] = {}
    for run in runs:
        current[run.name] = run
    declared = read_declared_gates_from_text(text)
    active, filtered, _valid = read_active_tuple_from_text(text)
    also = _read_frontmatter_list_from_text(text, "also_blocks_dependents")
    also_effective = [g for g in also if g not in filtered]
    registry = read_registry(registry_file) if registry_file else {}
    archive_decision, archive_pending = _archive_status_from_state(active, current)
    dep_decision, dep_pending = _dependents_status_from_state(active, also_effective,
                                                              registry, current)
    order: list[str] = []
    seen: set[str] = set()
    for run in runs:
        if run.name not in seen:
            seen.add(run.name)
            order.append(run.name)
    return TaskGateState(
        task_file=task_file,
        declared_gates=declared,
        runs=runs,
        current=current,
        status_text="\n".join(_format_gate_run_status_line(n, current[n]) for n in order),
        archive_decision=archive_decision,
        archive_pending=archive_pending,
        dependents_decision=dep_decision,
        dependents_pending=dep_pending,
        resume_point=_resume_point_from_state(current),
        active_gates=active,
        filtered_gates=filtered,
    )


# --- CLI ------------------------------------------------------------------

def _parse_kv(args: list[str]) -> dict:
    fields: dict = {}
    for a in args:
        if "=" not in a:
            sys.stderr.write(f"Warning: ignoring malformed key=value arg: {a}\n")
            continue
        k, v = a.split("=", 1)
        if k not in SUPPORTED_KEYS:
            sys.stderr.write(f"Warning: ignoring unsupported gate field: {k}\n")
            continue
        fields[k] = v
    return fields


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write(__doc__ or "")
        return 2
    cmd = argv[0]

    if cmd == "append":
        if len(argv) < 4:
            sys.stderr.write("Usage: gate_ledger.py append <file> <gate> <status> [k=v ...]\n")
            return 2
        path, gate, status = argv[1], argv[2], argv[3]
        if status not in VALID_STATUSES:
            sys.stderr.write(f"Error: invalid status '{status}' (one of: {', '.join(VALID_STATUSES)})\n")
            return 2
        fields = _parse_kv(argv[4:])
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new_text, block = append_block(text, gate, status, fields)
        _atomic_write(path, new_text)
        sys.stdout.write(block + "\n")
        return 0

    if cmd == "status":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py status <file>\n")
            return 2
        with open(argv[1], encoding="utf-8") as fh:
            text = fh.read()
        out = format_status(text)
        if out:
            sys.stdout.write(out + "\n")
        return 0

    if cmd == "list":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py list <file> [registry]\n")
            return 2
        registry = argv[2] if len(argv) > 2 else None
        sys.stdout.write(format_list(argv[1], registry) + "\n")
        return 0

    if cmd == "deps-unblock":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py deps-unblock <file> [registry]\n")
            return 2
        registry = argv[2] if len(argv) > 2 else None
        decision, pending = dependents_status(argv[1], registry)
        if decision == "BLOCKED":
            sys.stdout.write("BLOCKED:" + ",".join(pending) + "\n")
        else:
            sys.stdout.write(decision + "\n")
        return 0

    if cmd == "archive-ready":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py archive-ready <file>\n")
            return 2
        decision, nonpass = archive_status(argv[1])
        if decision == "BLOCKED":
            sys.stdout.write("BLOCKED:" + ",".join(nonpass) + "\n")
        else:
            sys.stdout.write(decision + "\n")
        return 0

    if cmd == "procedure-gates":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py procedure-gates <file> [registry]\n")
            return 2
        registry = argv[2] if len(argv) > 2 else None
        for g in unmet_procedure_gates(argv[1], registry):
            sys.stdout.write(g + "\n")
        return 0

    if cmd == "resume-point":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py resume-point <file>\n")
            return 2
        sys.stdout.write(resume_point(argv[1]) + "\n")
        return 0

    if cmd == "effective-gates":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py effective-gates <file> [profile_file]\n")
            return 2
        profile = argv[2] if len(argv) > 2 and argv[2] else None
        for g in effective_gates(argv[1], profile):
            sys.stdout.write(g + "\n")
        return 0

    if cmd == "has-gates-field":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py has-gates-field <file>\n")
            return 2
        with open(argv[1], encoding="utf-8") as fh:
            present = _frontmatter_has_key(fh.read(), "gates")
        return 0 if present else 1

    if cmd == "should-self-record":
        if len(argv) < 3:
            sys.stderr.write("Usage: gate_ledger.py should-self-record <file> <gate>\n")
            return 2
        return 0 if should_self_record(argv[1], argv[2]) else 1

    if cmd == "active":
        if len(argv) < 3:
            sys.stderr.write("Usage: gate_ledger.py active <file> <gate>\n")
            return 2
        with open(argv[1], encoding="utf-8") as fh:
            return 0 if argv[2] in read_active_gates_from_text(fh.read()) else 1

    if cmd == "compute-active":
        if len(argv) < 3:
            sys.stderr.write("Usage: gate_ledger.py compute-active <file> <profile> [mv_allowlist_csv]\n")
            return 2
        allowlist = tuple(g for g in (argv[3] if len(argv) > 3 else "").split(",") if g)
        with open(argv[1], encoding="utf-8") as fh:
            try:
                active, filtered, digest = compute_active_gates(fh.read(), argv[2], allowlist)
            except ProfileReadError as exc:
                sys.stderr.write(f"Error: {exc}\n")
                return 3
        sys.stdout.write("ACTIVE:" + ",".join(active) + "\n")
        sys.stdout.write("FILTERED:" + ",".join(filtered) + "\n")
        sys.stdout.write("DIGEST:" + digest + "\n")
        return 0

    if cmd == "active-status":
        if len(argv) < 4:
            sys.stderr.write("Usage: gate_ledger.py active-status <file> <profile> <profile_name> [mv_allowlist_csv]\n")
            return 2
        allowlist = tuple(g for g in (argv[4] if len(argv) > 4 else "").split(",") if g)
        with open(argv[1], encoding="utf-8") as fh:
            try:
                sys.stdout.write(active_tuple_status(fh.read(), argv[2], argv[3], allowlist) + "\n")
            except ProfileReadError as exc:
                sys.stderr.write(f"Error: {exc}\n")
                return 3
        return 0

    sys.stderr.write(f"Unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
