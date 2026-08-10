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
    gate_ledger.py deps-unblock-batch [registry.yaml] < task-file paths
                                 -> one `<decision>\t<path>` line per NON-EMPTY
                                    input line, in input order. Blank lines are
                                    skipped and produce no row, so map results by
                                    the echoed path, not by line position. The
                                    batched twin of the verb above, for `ait ls`
                                    (t1472): one process, one registry parse, at
                                    most one code_digest(). Exit 1 (with all rows
                                    NO_GATES) iff registry setup failed; else 0.
    gate_ledger.py archive-ready <task-file> [registry.yaml]
                                 -> ALL_PASS | BLOCKED:<csv> | NO_GATES (t635_4).
                                    With a registry, a ledger-satisfied human gate
                                    whose signal witness is code-STALE also blocks
                                    (t1409).
    gate_ledger.py resume-point  <task-file>
                                 -> PLAN | IMPLEMENT | POSTIMPL (t635_5)
    gate_ledger.py run-state     <task-file> <gate>
                                 -> OPEN:<run-id>|<attempt> / TERMINAL:<n>, the
                                    python twin of aitask_gate.sh's
                                    _gate_run_state (t1262)
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
import hashlib
import os
import re
import subprocess
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

# Statuses that mean a run reached a VERDICT — the ones that CLOSE an attempt.
# Deliberately distinct from SATISFIED_STATUSES ({pass, skip}), which asks
# whether a gate is *done*; this asks whether an attempt *ended*. `running` and
# `pending` are in-progress bookkeeping and never advance the attempt counter
# (t1262). Mirrors TERMINAL_STATUSES in aitask_gate.sh.
TERMINAL_STATUSES = frozenset({"pass", "fail", "skip", "error"})

# Sentinel distinguishing "no digest supplied — compute one lazily" from an
# explicitly supplied ``None`` (which means "unverifiable", a real answer).
# Lives up here with the other module constants rather than beside the digest
# helpers below because several functions take it as a DEFAULT ARGUMENT, and
# defaults are evaluated at def time — a definition further down the module is a
# NameError at import (t1416).
_COMPUTE_DIGEST = object()

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

    ``stale_signed`` (t1416) is the separate fact that a ledger-``pass`` human
    gate's code-bound witness no longer binds the current code. ``current``
    deliberately keeps the RAW ledger run for such a gate — the ledger really
    does say ``pass``, and rewriting it here would make the count silently drop
    with nothing to explain the drop — while ``archive_decision`` and
    ``dependents_decision`` ARE derived with the stale gates demoted. A surface
    rendering gate state should show the two facts together ("pass, signature
    stale"), never one without the other.
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
    stale_signed: list[str] = field(default_factory=list)


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


def next_attempt(text: str, gate: str) -> int:
    """Attempt ORDINAL for a new run of ``gate`` = terminal runs so far + 1.

    A completed attempt is ONE terminal marker (:data:`TERMINAL_STATUSES`), so the
    ``running`` block a run opens and the terminal block that closes it carry the
    SAME number. Counting every marker instead made the counter advance by 2 per
    attempt (t1262).

    Deliberately NOT ``gate_orchestrator._attempts_used() + 1``: that counts only
    ``fail``/``error`` because it answers a different question — how much RETRY
    BUDGET is spent. The two coincide on every path that re-dispatches a gate (a
    ``pass``/``skip`` gate is never re-run: the orchestrator skips it and
    :func:`unmet_procedure_gates` filters it out) and are allowed to diverge
    elsewhere, e.g. a re-recorded human gate advances the ordinal without
    spending budget. A malformed-verifier correction
    (``gate_orchestrator.reconcile_terminal``) writes a second terminal marker
    for one dispatch and counts here as its own run — the budget charges it the
    same way, so the two stay in lockstep there.

    Mirrored in bash by ``aitask_gate.sh``'s ``_gate_run_state``.
    """
    return 1 + sum(1 for r in parse_gate_run_blocks(text)
                   if r.name == gate and r.status in TERMINAL_STATUSES)


def live_run(text: str, gate: str) -> tuple[str, str] | None:
    """``(run_id, attempt)`` of ``gate``'s open run, or ``None`` if none is live.

    A run is LIVE when its latest marker is ``running``; any terminal marker
    carrying the same run id closes it. A gate has at most one live run, which is
    what ``begin-procedure`` adopts instead of opening a second (t1262).
    """
    latest: dict[str, str] = {}
    attempts: dict[str, str] = {}
    order: list[str] = []
    for r in parse_gate_run_blocks(text):
        if r.name != gate or not r.run_id:
            continue
        if r.run_id not in latest:
            order.append(r.run_id)
        latest[r.run_id] = r.status
        if r.status == "running":
            attempts[r.run_id] = r.attempt
    for run_id in reversed(order):
        if latest[run_id] == "running":
            return run_id, attempts.get(run_id, "")
    return None


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

    A gate on ``state.stale_signed`` (t1416) is counted as ``stale``, not
    ``pass``: its ledger says ``pass`` but its code-bound signature no longer
    binds, and the archival guard blocks on it — so counting it as passing would
    reproduce the exact disagreement this column exists to avoid. Renders e.g.
    ``"3/4 pass, 1 stale"``. Inert for callers that pass no registry (they never
    populate ``stale_signed``).
    """
    runs = [r for r in state.current.values() if r.name not in state.filtered_gates]
    if not runs:
        return ""
    stale = set(state.stale_signed)
    total = len(runs)
    n_stale = sum(1 for r in runs if r.name in stale)
    n_pass = sum(1 for r in runs if r.status == "pass" and r.name not in stale)
    n_fail = sum(1 for r in runs if r.status in ("fail", "error")
                 and r.name not in stale)
    n_pending = total - n_pass - n_fail - n_stale
    parts = [f"{n_pass}/{total} pass"]
    if n_pending:
        parts.append(f"{n_pending} pending")
    if n_fail:
        parts.append(f"{n_fail} failed")
    if n_stale:
        parts.append(f"{n_stale} stale")
    return ", ".join(parts)


# --- Append ---------------------------------------------------------------

def build_block(text: str, gate: str, status: str, fields: dict) -> str:
    """Build the marker-first blockquote for one gate run (no trailing newline).

    ``attempt`` is taken from ``fields`` if present, else auto-computed for any
    TERMINAL status as (terminal runs for this gate) + 1 — see
    :func:`next_attempt` — else omitted. ``run`` is taken from ``fields`` if
    present, else generated as an ISO-8601-Z stamp.
    """
    fields = dict(fields)
    run_id = fields.pop("run", None) or iso_now()

    attempt = fields.pop("attempt", None)
    if attempt is None and status in TERMINAL_STATUSES:
        attempt = str(next_attempt(text, gate))

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


# Keys the registry parser understands. Single source for the field dispatch
# below, the sync-registry fill allowlist, and the coverage drift guard — a key
# the parser cannot round-trip must never be written by the sync writer, or the
# writer would emit text `read_registry` silently drops (t635_34).
_SCALAR_GATE_KEYS = ("type", "kind", "description", "verifier",
                     "signal", "signal_target")
_GATE_FIELD_KEYS = _SCALAR_GATE_KEYS + ("blocks_dependents", "max_retries",
                                        "timeout_seconds", "unlocks")


@dataclass(frozen=True)
class _RegRec:
    """One typed record from the single registry line-walk (t635_34).

    ``kind``  ``"open"`` a ``gates:`` line activated the mapping ·
              ``"close"`` a column-0 line terminated it · ``"gate"`` a gate
              header at ``gate_indent`` · ``"field"`` a field of the current gate.
    ``ws``    the LITERAL leading-whitespace string. Tabs are preserved: the
              writer needs to reproduce a file's own indentation, and
              ``_indent_width`` collapses a tab to four spaces and cannot be
              inverted.
    ``value`` raw text after ``key:``, ``.strip()``ed — exactly what the old
              inline parser saw as ``val``. NOT quote-stripped.
    ``end``   last line index belonging to this record. Equals ``line`` except
              for a block-form ``unlocks``, where it is the last ``- item``
              line (blank lines trailing the block are excluded, so an inserter
              anchored on ``end`` never lands after a blank).
    """
    kind: str
    gate: str
    key: str
    value: str
    ws: str
    line: int
    end: int
    items: list[str] | None


def _walk_registry(lines: "list[str]"):
    """Single line-walk over a gates.yaml. Yields :class:`_RegRec` records.

    This IS the registry parser's control flow — :func:`read_registry_text` and
    :func:`registry_layout` are both thin consumers of it. Do not fork it.

    Behaviour pinned by ``tests/test_gate_registry_parser_quirks.py``; the
    quirks are deliberate and load-bearing:
      * ``gate_indent`` is sticky — never reset when the mapping deactivates;
      * ``cur`` IS reset on dedent, so orphan fields are dropped;
      * blank lines inside a block-form ``unlocks`` do not terminate it;
      * ``gates: {}`` never activates (the regex demands an empty value);
      * ANY column-0 line ends the mapping, ``#`` comments included.
    """
    in_gates = False
    gate_indent = None
    cur = None
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if re.match(r"^gates:\s*$", line):
            in_gates = True
            yield _RegRec("open", "", "", "", "", i, i, None)
            i += 1
            continue
        if not in_gates or not line.strip():
            i += 1
            continue
        # A non-indented, non-blank line ends the gates: mapping.
        if re.match(r"^\S", line):
            in_gates = False
            cur = None
            yield _RegRec("close", "", "", "", "", i, i, None)
            i += 1
            continue
        m = re.match(r"^([ \t]+)([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        ws, key, val = m.group(1), m.group(2), m.group(3).strip()
        indent = _indent_width(ws)
        if gate_indent is None:
            gate_indent = indent
        if indent <= gate_indent:
            # New gate header (its fields are more-indented).
            cur = key
            yield _RegRec("gate", cur, "", val, ws, i, i, None)
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        # A field of the current gate.
        if key == "unlocks" and not val:
            # Block form: consume deeper-indented "- item" lines. Entered iff
            # the value is empty — `_parse_inline_list("")` returns None and a
            # non-empty unbracketed value is the scalar case, both handled by
            # the consumer.
            items: "list[str]" = []
            j, last = i + 1, i
            while j < n:
                bl = lines[j]
                if not bl.strip():
                    j += 1
                    continue
                bm = re.match(r"^([ \t]+)-[ \t]*(.+?)\s*$", bl)
                if bm and _indent_width(bm.group(1)) > indent:
                    items.append(bm.group(2).strip().strip("'\""))
                    last = j
                    j += 1
                    continue
                break
            yield _RegRec("field", cur, key, val, ws, i, last, items)
            i = j
            continue
        yield _RegRec("field", cur, key, val, ws, i, i, None)
        i += 1


def read_registry_text(text: str) -> dict[str, dict]:
    """Text-level twin of :func:`read_registry` (testable without a tempfile)."""
    gates: dict[str, dict] = {}
    for rec in _walk_registry(text.splitlines()):
        if rec.kind == "gate":
            # Duplicate header re-defaults: last block wins WHOLESALE.
            gates[rec.gate] = _default_gate_meta()
            continue
        if rec.kind != "field":
            continue
        meta = gates.get(rec.gate)
        if meta is None:
            continue
        key, val = rec.key, rec.value
        if key in _SCALAR_GATE_KEYS:
            meta[key] = val.strip("'\"")
        elif key == "blocks_dependents":
            meta[key] = _truthy(val)
        elif key == "max_retries":
            meta[key] = _int_or(val, 0)
        elif key == "timeout_seconds":
            meta[key] = _int_or(val, None)
        elif key == "unlocks":
            if rec.items is not None:
                meta[key] = rec.items
            else:
                inline = _parse_inline_list(val)
                meta[key] = inline if inline is not None else [val.strip("'\"")]
        # Unknown keys are ignored, exactly as before.
    return gates


@dataclass(frozen=True)
class GateBlock:
    """Textual layout of one gate block (t635_34).

    ``field_ws`` is ``None`` for a header-only gate — callers must resolve the
    indent through :func:`resolve_field_indent` rather than assuming it exists.

    ``last_field_end`` is the INSERTION anchor (after the last field line, so a
    new key lands before any trailing comment that introduces the next thing).
    ``block_end`` is the LEXICAL extent (every indented line belonging to the
    gate, including comments, unknown keys and their block lists) and is what a
    whole-block copy must use — ``last_field_end`` would truncate an unknown
    key's ``- item`` lines, since the walk only recognises ``key:`` lines.
    """
    name: str
    header_line: int
    header_ws: str
    field_ws: str | None
    fields: dict          # key -> line index (last occurrence, matching the parser)
    raw_values: dict      # key -> raw value text (pre quote-strip)
    last_field_end: int
    block_end: int


@dataclass(frozen=True)
class RegistryLayout:
    """Where everything physically sits in a gates.yaml (t635_34).

    Shares :func:`_walk_registry` with :func:`read_registry_text`, so the
    presence oracle and the value parser can never disagree about a file.
    """
    lines: list[str]              # splitlines()
    raw: list[str]                # splitlines(keepends=True) — index-aligned
    open_line: int | None         # first activating `gates:` line
    close_line: int | None        # line that terminated it; None => ran to EOF
    close_starts_with_hash: bool  # a column-0 `#` truncated the mapping
    gate_indent: int | None
    order: list[str]              # gate names in file order (first occurrence)
    blocks: dict                  # name -> GateBlock (LAST block for duplicates)
    duplicates: list[str]
    orphan_field_names: list[str]  # parsed "gates" whose name is a field key


def registry_layout(text: str) -> RegistryLayout:
    """Second consumer of the shared walk: physical layout + key presence.

    Presence cannot be recovered from :func:`read_registry_text`'s output —
    ``verifier: ""`` and an absent ``verifier:`` both parse to ``""`` — so any
    fill-vs-conflict decision needs this.
    """
    lines = text.splitlines()
    raw = text.splitlines(keepends=True)
    open_line = close_line = None
    gate_indent = None
    order: list[str] = []
    blocks: dict = {}
    duplicates: list[str] = []
    orphans: list[str] = []
    header_lines: list[int] = []
    cur = None

    for rec in _walk_registry(lines):
        if rec.kind == "open":
            if open_line is None:
                open_line = rec.line
            continue
        if rec.kind == "close":
            if close_line is None:
                close_line = rec.line
            continue
        if rec.kind == "gate":
            if gate_indent is None:
                gate_indent = _indent_width(rec.ws)
            if rec.gate in blocks and rec.gate not in duplicates:
                duplicates.append(rec.gate)
            if rec.gate in _GATE_FIELD_KEYS and rec.gate not in orphans:
                # A gate named `type`/`verifier`/... means the file's fields are
                # indented at or below gate_indent and have ALREADY been read as
                # sibling gates — the mis-indent tell.
                orphans.append(rec.gate)
            if rec.gate not in order:
                order.append(rec.gate)
            header_lines.append(rec.line)
            cur = rec.gate
            blocks[cur] = GateBlock(
                name=cur, header_line=rec.line, header_ws=rec.ws,
                field_ws=None, fields={}, raw_values={},
                last_field_end=rec.line, block_end=rec.line,
            )
            continue
        # field
        blk = blocks.get(rec.gate)
        if blk is None or cur != rec.gate:
            continue
        fields = dict(blk.fields)
        fields[rec.key] = rec.line
        raw_values = dict(blk.raw_values)
        raw_values[rec.key] = rec.value
        blocks[rec.gate] = GateBlock(
            name=blk.name, header_line=blk.header_line, header_ws=blk.header_ws,
            field_ws=blk.field_ws if blk.field_ws is not None else rec.ws,
            fields=fields, raw_values=raw_values,
            last_field_end=max(blk.last_field_end, rec.end),
            block_end=blk.block_end,
        )

    # Lexical block extent: everything up to the next gate header / the line
    # that closed the mapping / EOF, minus trailing blanks. Computed after the
    # walk because it must include lines the walk does not yield records for
    # (comments, unknown keys' block-list items, nested mappings).
    stop = close_line if close_line is not None else len(lines)
    for idx, start in enumerate(header_lines):
        nxt = header_lines[idx + 1] if idx + 1 < len(header_lines) else stop
        boundary = min(nxt, stop) if nxt > start else stop
        end = boundary - 1
        while end > start and not lines[end].strip():
            end -= 1
        name = lines[start].strip().rstrip(":").strip()
        blk = blocks.get(name)
        # Only the LAST block of a duplicated name is retained, matching the
        # parser; earlier header lines for that name must not shrink its extent.
        if blk is not None and blk.header_line == start:
            blocks[name] = GateBlock(
                name=blk.name, header_line=blk.header_line,
                header_ws=blk.header_ws, field_ws=blk.field_ws,
                fields=blk.fields, raw_values=blk.raw_values,
                last_field_end=blk.last_field_end, block_end=max(end, start),
            )

    return RegistryLayout(
        lines=lines, raw=raw, open_line=open_line, close_line=close_line,
        close_starts_with_hash=(close_line is not None
                                and lines[close_line].lstrip().startswith("#")),
        gate_indent=gate_indent, order=order, blocks=blocks,
        duplicates=duplicates, orphan_field_names=orphans,
    )


def unverifiable_reason(gate: str, registry: dict[str, dict]) -> str | None:
    """Why an ENFORCED gate can never be satisfied — ``None`` when it can.

    Mirrors the last arms of ``gate_orchestrator.blocked_reason``: a human gate
    legitimately carries no verifier (it pends on a signal) and a procedure gate
    is run by the attended agent, so neither is a defect. Only a machine
    command gate with no verifier — or a gate with no registry entry at all —
    is genuinely unsatisfiable.

    ``blocked_reason`` calls this, so the pick-time warning and the run-time
    block can never drift apart (t635_34).
    """
    if gate not in registry:
        return "no registry entry"
    meta = registry[gate]
    if meta.get("type") == "human":
        return None
    if meta.get("kind") == "procedure":
        return None
    if not meta.get("verifier"):
        return "no verifier configured"
    return None


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

    The line-walk itself lives in :func:`_walk_registry` and is shared with
    :func:`registry_layout` (t635_34) so the presence oracle and the parser can
    never disagree about what a file says.
    """
    if not registry_file or not os.path.exists(registry_file):
        return {}
    with open(registry_file, encoding="utf-8") as fh:
        return read_registry_text(fh.read())


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


def _gate_satisfied(state: dict[str, GateRun], gate: str) -> bool:
    """Shared satisfied-predicate over a derived ``gate -> GateRun`` map: is the
    gate's current run terminal-satisfied (``pass``/``skip``)? An absent run is
    not satisfied."""
    run = state.get(gate)
    return (run.status if run else None) in SATISFIED_STATUSES


def _dependents_status_from_state(declared: list[str], also: list[str],
                                  registry: dict[str, dict],
                                  state: dict[str, GateRun]) -> tuple[str, list[str]]:
    required = required_unblock_gates(declared, also, registry)
    if not required:
        return ("NO_GATES", [])
    pending = [g for g in required if not _gate_satisfied(state, g)]
    return ("BLOCKED", pending) if pending else ("SATISFIED", [])


def dependents_status(task_file: str, registry_file: str | None,
                      current_digest=_COMPUTE_DIGEST) -> tuple[str, list[str]]:
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

    **Witness re-validation (t1416).** A required gate whose ledger says ``pass``
    but whose code-bound signature is stale counts as NOT satisfied. This is a
    semantics decision, not just a cost one: ``review_approved`` / ``merge_approved``
    are exactly the two gates flagged ``blocks_dependents: true`` AND the two that
    carry a code-bound witness, so a signature against different code is not an
    approval of the code a dependent would build on. The demotion runs over the
    **required** set (registry-flagged declared gates ∪ ``also_blocks_dependents``),
    so an ``also_blocks_dependents`` entry is re-validated too.

    **Cost.** The no-git pre-filter means a task without a stamped witness costs
    nothing (~2 µs). Measured on the framework repo (t1416): each witness-carrying
    task adds one ~5 ms ``code_digest()``, and this single-task entry point cannot
    amortize it — the cost stays linear in W (tasks carrying a signature) for
    every caller that loops over this function.

    ``ait ls`` no longer does (t1472). It goes through
    :func:`dependents_status_batch`, which decides the whole candidate list in ONE
    process with one registry parse and at most one ``code_digest()``, replacing a
    fan-out of one subprocess per gated task (190 processes / 9.7 s on the
    framework repo). This per-task verb remains for single-task callers and tests;
    a caller with its own once-per-refresh memo threads it via ``current_digest``.
    """
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    return _dependents_status_for_text(
        text, read_registry(registry_file) if registry_file else {},
        task_id_from_file(task_file), current_digest)


def _dependents_status_for_text(text: str, registry: dict[str, dict],
                                task_id: str,
                                current_digest) -> tuple[str, list[str]]:
    """Shared decision core of the per-task and batched deps-unblock verbs.

    Both :func:`dependents_status` and :func:`dependents_status_batch` route
    through here, so the two CLI surfaces cannot drift into two implementations
    of the unblock decision (pinned by ``tests/test_deps_unblock_batch.sh``).
    Takes an already-parsed ``registry`` and an explicit ``task_id`` so the batch
    can hoist the registry read out of its loop.
    """
    active, filtered, _valid = read_active_tuple_from_text(text)
    also = _read_frontmatter_list_from_text(text, "also_blocks_dependents")
    also_effective = [g for g in also if g not in filtered]
    state = derive_gate_runs(text)
    effective, _stale = demote_stale_signed(
        required_unblock_gates(active, also_effective, registry), registry,
        state, task_id, current_digest)
    return _dependents_status_from_state(active, also_effective, registry,
                                         effective)


def dependents_status_batch(task_files: list[str], registry_file: str | None,
                            current_digest=_COMPUTE_DIGEST
                            ) -> tuple[list[tuple[str, str, list[str]]],
                                       Exception | None]:
    """``(rows, setup_error)`` — one ``(path, decision, pending)`` row per input
    path, in input order, plus the setup failure that forced them all (t1472).

    A plain function, not a generator: the caller needs BOTH the rows and the
    setup verdict, and a generator would force either a second registry parse in
    the CLI or a ``StopIteration.value`` dance. 190 rows is nothing to hold.

    One process, ONE registry parse, and AT MOST one ``code_digest()`` for the
    whole batch — replacing ``ait ls``'s former one-subprocess-per-gated-task
    fan-out (190 processes / 9.7 s on the framework repo).

    **Totality is the contract: every element of ``task_files`` yields exactly one
    row, in input order.** Two distinct degradation boundaries keep it true. (The
    ``deps-unblock-batch`` CLI wrapping this function drops BLANK stdin lines
    before building ``task_files``, so its one-to-one guarantee is per *non-empty*
    input line — a caller mapping stdin lines to output rows positionally must
    account for that, or key off the echoed path instead.)

    *Per-file* — a file that cannot be read or decided yields ``("NO_GATES", [])``
    plus a stderr diagnostic naming it, rather than aborting the batch. This
    reproduces the boundary the old shape got for free from the per-task
    ``delegate_python ... || echo "NO_GATES"`` fallback: collapsing N processes
    into 1 must not let one bad task file cost ``ait ls`` every other decision.

    *Setup* — :func:`read_registry` runs ONCE, before the loop, and is therefore
    outside every per-file guard. It already returns ``{}`` for a MISSING
    registry, but still raises on a directory path, unreadable permissions,
    non-UTF-8 bytes, or a TOCTOU delete. Left unguarded that would abort before a
    single row, so the promised rows and diagnostic would never exist. Guarded, a
    setup failure degrades to the same shape: ``NO_GATES`` for every input row,
    ONE diagnostic (not N copies of one cause), and a non-``None``
    ``setup_error`` the CLI turns into a NONZERO exit — so a caller reading exit
    status can tell "everything fell back" from "nothing was gated", a
    distinction invisible in the rows themselves.

    Falling back to a partial ``registry={}`` decision is deliberately NOT done:
    with no registry no gate carries ``blocks_dependents``, so
    ``also_blocks_dependents`` entries would still be honored while
    registry-flagged ones silently would not — an inconsistent half-decision.
    All-``NO_GATES`` is the conservative whole answer (the caller falls back to
    file-existence, so a dependent stays blocked until archival); not fail-open.
    """
    try:
        registry = read_registry(registry_file) if registry_file else {}
    except Exception as exc:            # noqa: BLE001 — totality boundary, see above
        sys.stderr.write(
            f"deps-unblock-batch: registry unavailable ({registry_file}): {exc}"
            f" — every task falls back to NO_GATES\n")
        return [(p, "NO_GATES", []) for p in task_files], exc

    memo = _DigestMemo(current_digest)
    rows: list[tuple[str, str, list[str]]] = []
    for path in task_files:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            decision, pending = _dependents_status_for_text(
                text, registry, task_id_from_file(path), memo)
        except Exception as exc:        # noqa: BLE001 — totality boundary, see above
            sys.stderr.write(f"deps-unblock-batch: {path}: {exc}\n")
            decision, pending = "NO_GATES", []
        rows.append((path, decision, pending))
    return rows, None


# --- Code-state digest + human-gate signal witness (t635_15, t1409) -------
#
# These live here, not in ``gate_orchestrator.py``, because BOTH the write-side
# engine (``ait gates run``) and the read-side archival guard
# (``aitask_gate.sh archive-ready``) must classify a signature's freshness, and
# two agreeing copies would be free to drift. ``gate_orchestrator`` re-exports
# the public names so its own CLI / importers are unaffected.

# Paths whose churn must NOT flip the code digest (the ledger lives here).
_DIGEST_EXCLUDES = [":(exclude)aitasks/**", ":(exclude)aiplans/**",
                    ":(exclude).aitask-data/**"]

_TASK_ID_RE = re.compile(r"^t(\d+(?:_\d+)?)_")

def _resolve_digest(current_digest):
    """Resolve the four-state digest channel to ``str | None`` (t1416).

    The channel carries four DISTINCT things, and the branch order below is
    load-bearing:

    1. ``_COMPUTE_DIGEST`` (the default) — nothing supplied; compute one now.
    2. a **callable** — a caller's once-per-refresh memo. Invoked here, which is
       only ever reached AFTER the no-git pre-filter found a candidate, so a
       board that renders 300 ungated tasks never triggers a git subprocess.
    3. a ``str`` — an already-computed digest, used as-is.
    4. ``None`` — freshness is **unverifiable** (no git / no commits). This is a
       real answer, not a missing one: :func:`witness_state` resolves it to
       ``unstamped`` (accept). It must be tested BEFORE any truthiness check —
       ``callable(None)`` is ``False``, so the ordering here is what keeps
       "cannot check" from being silently re-read as "compute it".

    Deliberately does NOT catch exceptions from a provider. Making a provider
    total is the provider's job (see ``aitask_board.TaskManager
    .code_digest_for_refresh``); swallowing here would reinterpret a caller bug
    as "unverifiable" and quietly accept a signature nobody validated.
    """
    if current_digest is _COMPUTE_DIGEST:
        return code_digest()
    if callable(current_digest):
        return current_digest()
    return current_digest


class _DigestMemo:
    """One-shot memo over the four-state digest channel (t1472).

    Batch analogue of the board's ``TaskManager.code_digest_for_refresh``. Passed
    to the decision core as a *callable*, so :func:`_resolve_digest` invokes it
    only after some task's no-git pre-filter finds a stamped witness: a batch of
    300 unsigned tasks never shells out to git, and any number of signed ones
    shells out exactly once. Delegating to :func:`_resolve_digest` is what keeps
    all four incoming states (sentinel / callable / str / None) handled in one
    place instead of re-deciding them here.

    **A failed provider is memoized as the FAILURE, and re-raised.** It must not
    decay into a cached ``None``: :func:`witness_state` resolves
    ``current_digest is None`` to ``unstamped`` = *accept*, so a cached ``None``
    would let every signed task after the first release its dependents on a
    code-bound witness that was never re-validated — the exact fail-open t1416
    closed. It is also precisely what :func:`_resolve_digest` refuses to do one
    layer down ("swallowing here would reinterpret a caller bug as
    'unverifiable' and quietly accept a signature nobody validated").

    So: resolve at most ONCE (a failed provider is never retried, so a batch
    cannot pay N failing subprocesses), and every later caller re-raises the
    stored exception. Each signed row then hits the batch's per-file guard and
    falls back to ``NO_GATES`` — conservative, since a task whose staleness
    cannot be determined must not release its dependents. Unsigned rows never
    call the memo at all and are unaffected.

    ``Exception``, not ``BaseException``: a ``KeyboardInterrupt`` must still kill
    the batch rather than be replayed once per row.
    """

    __slots__ = ("_source", "_value", "_error", "_done")

    def __init__(self, source):
        self._source = source
        self._value = None
        self._error = None
        self._done = False

    def __call__(self):
        if not self._done:
            self._done = True               # set FIRST: a failure is never retried
            try:
                self._value = _resolve_digest(self._source)
            except Exception as exc:        # noqa: BLE001 — stored, then re-raised
                self._error = exc
                raise
        if self._error is not None:
            raise self._error
        return self._value


def _git(args: list[str], cwd: str) -> str | None:
    """Run a git command, returning stdout or ``None`` on any failure."""
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                           text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def code_digest(cwd: str | None = None) -> str | None:
    """Digest of the repo's CODE state — HEAD + staged/unstaged + untracked.

    Returns a short hex digest, or ``None`` when git is unavailable / the repo
    has no commits (in which case the stopping heuristic stays inert and the
    plain retry budget governs). ``git diff HEAD`` captures BOTH staged and
    unstaged tracked changes; ``ls-files --others`` adds untracked content. The
    task/plan data paths are excluded so ledger appends do not flip the digest.
    """
    cwd = cwd or os.getcwd()
    head = _git(["rev-parse", "HEAD"], cwd)
    if head is None:
        return None
    h = hashlib.sha256()
    h.update(head.encode())
    diff = _git(["diff", "HEAD", "--", ".", *_DIGEST_EXCLUDES], cwd) or ""
    h.update(diff.encode())
    others = _git(["ls-files", "--others", "--exclude-standard", "--", ".",
                   *_DIGEST_EXCLUDES], cwd) or ""
    for rel in sorted(others.splitlines()):
        rel = rel.strip()
        if not rel:
            continue
        h.update(rel.encode())
        try:
            with open(os.path.join(cwd, rel), "rb") as fh:
                h.update(fh.read())
        except OSError:
            pass
    return h.hexdigest()[:16]


def task_id_from_file(path: str) -> str:
    """Best-effort task id from a task filename (fallback when none is given)."""
    m = _TASK_ID_RE.match(os.path.basename(path))
    return m.group(1) if m else os.path.basename(path)


def read_witness_digest(path: str) -> str | None:
    """Read the ``code_digest=`` field from a human-gate signal witness file
    (t635_15), or ``None`` if absent/unreadable. The witness is a small
    ``key=value`` text file written by ``ait gate pass``."""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("code_digest="):
                    return line.split("=", 1)[1].strip() or None
    except OSError:
        return None
    return None


def resolve_signal_target(template: str, task_id: str, gate: str) -> str:
    """Expand a registry ``signal_target`` template (``<task-id>`` → ``t<id>``,
    ``<gate>`` → the gate name). Empty template → empty string."""
    if not template:
        return ""
    return template.replace("<task-id>", f"t{task_id}").replace("<gate>", gate)


def witness_state(gate: str, registry: dict[str, dict], task_id: str,
                  current_digest: str | None) -> tuple[str, str | None]:
    """Classify a human-gate signal witness (t635_15). Returns ``(kind,
    recorded_digest)`` where ``kind`` is one of:

      * ``absent``    — no ``signal_target`` configured, or the file is missing.
      * ``fresh``     — witness present and its ``code_digest`` matches the
                        current code state (the human signed THIS code).
      * ``stale``     — witness present but its ``code_digest`` differs from
                        the current code (signed against a different state).
      * ``unstamped`` — witness present with no ``code_digest`` (hand-created,
                        or the current digest is unavailable → cannot validate);
                        accepted as a pass for backward compatibility.

    ``current_digest is None`` means the freshness is **unverifiable**, which is
    a decision this function makes explicitly rather than leaving to callers: it
    resolves to ``unstamped`` (accept), the same way a witness with no recorded
    digest does. Nothing here is ever classified ``stale`` on a guess.
    """
    meta = registry.get(gate, {})
    target = resolve_signal_target(meta.get("signal_target", ""), task_id, gate)
    if not target or not os.path.exists(target):
        return ("absent", None)
    recorded = read_witness_digest(target)
    if recorded is None:
        return ("unstamped", None)          # hand-created / no digest → accept
    if current_digest is None:
        return ("unstamped", recorded)      # cannot validate → accept
    if recorded == current_digest:
        return ("fresh", recorded)
    return ("stale", recorded)


def _has_stamped_witness(gate: str, registry: dict[str, dict], task_id: str) -> bool:
    """Cheap (no-git) pre-filter: does this gate have a witness file carrying a
    ``code_digest``? Only such a gate can ever be classified ``stale``."""
    target = resolve_signal_target(
        registry.get(gate, {}).get("signal_target", ""), task_id, gate)
    if not target or not os.path.exists(target):
        return False
    return read_witness_digest(target) is not None


def stale_signed_gates(active: list[str], registry: dict[str, dict],
                       state: dict[str, GateRun], task_id: str,
                       current_digest=_COMPUTE_DIGEST) -> list[str]:
    """Ledger-SATISFIED human gates whose signature is code-stale (t1409).

    The code-binding contract ("a signature against a different code state
    re-pends") used to hold only while a gate's ledger status was non-terminal:
    once a ``pass`` was recorded, both the orchestrator's satisfied-gate
    short-circuit and the archival guard stopped consulting the witness, so code
    changed after sign-off could archive unreviewed. This is the shared
    re-validation both paths run instead.

    Only ``stale`` counts. ``absent`` must stay accepted — an **attended**
    session records ``review_approved`` directly from the interactive approval
    and never writes a witness — and ``unstamped`` stays accepted for backward
    compatibility. Returns the offending gates in ``active`` order.

    ``current_digest`` is the four-state channel documented on
    :func:`_resolve_digest`: the ``_COMPUTE_DIGEST`` default computes
    :func:`code_digest` **lazily**, a callable is a caller's once-per-refresh
    memo invoked just as lazily, a ``str`` is used as-is, and ``None`` means
    unverifiable (accept). Resolution happens only after the no-git pre-filter
    finds at least one stamped witness: this function runs on every archival
    readiness check and on every per-task TUI/`ait ls` decision, and the
    overwhelmingly common case (no witness files at all) must cost no
    subprocesses. Measured (t1416): 2 µs/task with no witness, versus one
    ~5 ms `code_digest()` when a witness is present.
    """
    candidates = [g for g in active
                  if _gate_satisfied(state, g)
                  and registry.get(g, {}).get("type") == "human"
                  and _has_stamped_witness(g, registry, task_id)]
    if not candidates:
        return []
    current_digest = _resolve_digest(current_digest)
    return [g for g in candidates
            if witness_state(g, registry, task_id, current_digest)[0] == "stale"]


def demote_stale_signed(gates: list[str], registry: dict[str, dict],
                        state: dict[str, GateRun], task_id: str,
                        current_digest=_COMPUTE_DIGEST
                        ) -> tuple[dict[str, GateRun], list[str]]:
    """``(state_without_stale, stale)`` — the derived view with code-stale
    human-gate signatures removed (t1409/t1416).

    The ONE seam every consuming surface goes through, so a surface added later
    cannot accidentally end up with a ledger-only view: the orchestrator's
    ``Engine._read_state`` and ``unlocked()``, plus ``read_task_gate_state`` and
    ``dependents_status``, all demote through here. (``archive_status`` composes
    :func:`stale_signed_gates` directly because it needs the stale list merged
    into a *declared-order* blocked list, not a filtered state map.)

    Returns the ORIGINAL mapping object — not a copy — when nothing is stale, so
    the overwhelmingly common case allocates nothing. Callers must therefore
    treat the returned map as read-only.
    """
    stale = stale_signed_gates(gates, registry, state, task_id, current_digest)
    if not stale:
        return state, []
    return {k: v for k, v in state.items() if k not in stale}, stale


# --- Gate-guarded archival decision (t635_4) ------------------------------

def _archive_status_from_state(declared: list[str],
                               state: dict[str, GateRun]) -> tuple[str, list[str]]:
    if not declared:
        return ("NO_GATES", [])
    nonpass = [g for g in declared if not _gate_satisfied(state, g)]
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
        if not _gate_satisfied(state, g):
            out.append(g)
    return out


def archive_status(task_file: str,
                   registry_file: str | None = None) -> tuple[str, list[str]]:
    """Decide whether ``task_file`` may archive (D5: every declared gate pass).

    Unlike :func:`dependents_status` (which filters to ``blocks_dependents``
    gates), archival requires **every** declared gate to pass. A declared gate
    with no recorded run counts as not-pass.

    Returns one of:
      - ``("NO_GATES", [])``   — no declared gates → archive as today (the
        dormant case until t635_14 populates ``gates:``).
      - ``("ALL_PASS", [])``   — every declared gate has derived status ``pass``.
      - ``("BLOCKED", nonpass)`` — one or more declared gates are not ``pass``.

    **Witness re-validation (t1409).** When ``registry_file`` is given, a gate
    whose *ledger* says ``pass`` can still block: a human gate signed via
    ``ait gate pass`` carries a code-bound witness, and a signature against a
    different code state is not an approval of the current code. Such gates are
    added to the blocked list (in declared order) via :func:`stale_signed_gates`.
    This guard **reports, it does not write** — it is a read-only decision verb,
    and ``ait gates run`` (the single writer of observed human-gate blocks) is
    what records the resulting ``pending``. So between a code change and the next
    ``gates run``, ``ait gate status`` reads ``pass`` while this reads
    ``BLOCKED``; that window is the contract, not a bug.

    ``registry_file`` defaults to ``None`` (ledger-only), so pre-t1409 callers
    keep their exact behavior; the shipped path passes it from
    ``aitask_gate.sh``.
    """
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    decision, nonpass = archive_status_from_text(text)
    if decision == "NO_GATES" or not registry_file:
        return decision, nonpass
    active = read_active_gates_from_text(text)
    stale = stale_signed_gates(active, read_registry(registry_file),
                               derive_gate_runs(text),
                               task_id_from_file(task_file))
    if not stale:
        return decision, nonpass
    return ("BLOCKED", [g for g in active if g in nonpass or g in stale])


def archive_status_from_text(text: str) -> tuple[str, list[str]]:
    """Content-level, LEDGER-ONLY twin of :func:`archive_status` — no filesystem
    open, no registry, and therefore **no witness re-validation**.

    Lets callers that already hold the task body (e.g. the stats active-task
    scan, which iterates ``(filename, content)`` pairs) classify archival
    readiness deterministically, without re-reading a path that may not exist
    under a rebased project root. Composes the shared primitives — no parsing
    fork (D6). Reads the ENFORCED active set (t635_33): a profile-filtered
    gate can never block archival.

    **The ledger-only scope is RATIFIED (t1416), and the reasons are contractual,
    not merely cost.** t1416 re-validated the signature on the other three
    ledger-only surfaces (``read_task_gate_state``, ``deps-unblock``,
    ``gate_orchestrator.unlocked``); this one stays ledger-only because:

    1. **It is a pure-text contract.** No filesystem, no registry, no task id —
       that is the whole reason it exists next to :func:`archive_status`.
       Re-validation needs all three, so threading a digest here would not extend
       this function, it would replace it with a different one.
    2. **Its verdict is hashed into a staleness digest.**
       ``trail_gather.task_record()`` puts ``gates_pending`` (derived from this
       call) into the trail's ``input_digest``. A code-state-dependent verdict
       would flip every trail's staleness result on unrelated commits — turning a
       correctness fix into a correctness regression.

    The ENFORCING decision is :func:`archive_status` with a registry, which every
    archival path goes through. A task whose only unmet gate is a stale signature
    therefore reads as archivable *here* and blocked *there* — a stated contract,
    not an oversight. The registered consumers and the guard that stops the split
    from silently growing live in ``tests/test_gate_ledger_only_surfaces.py``; the
    decision table is in ``aidocs/gates/gate-guarded-archival.md``.

    **Call this function directly — never through an alias or indirection.** That
    guard is syntactic, and an indirection defeats it.
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
        return resume_point_from_text(fh.read())


def resume_point_from_text(text: str) -> str:
    """Content-level twin of :func:`resume_point` — no filesystem open.

    **Supported cross-module API** (t1420): consumed by
    ``lib/workflow_phase.py``, which must not reach into the private
    ``_resume_point_from_state``. Same three-state contract as
    :func:`resume_point`; see its docstring. Keep this name and return values
    stable — ``tests/test_gate_ledger_public_api.py`` pins them.
    """
    return _resume_point_from_state(derive_gate_runs(text))


def read_active_gates_profile_from_text(text: str) -> str:
    """The profile name stamped into ``active_gates_profile`` at claim time
    (``materialize-active``), or ``""`` when the task was never materialized.

    **Supported cross-module API** (t1420): ``lib/workflow_phase.py`` uses it to
    say *why* a phase is ``UNKNOWN`` — a profile without ``record_gates`` never
    writes a ledger, so "no checkpoints yet" and "recording is off" are different
    states. Deliberately a *named* reader for this one field rather than an
    exported general scalar reader: a general escape hatch would re-create the
    private-helper coupling this exists to remove.
    """
    return _read_frontmatter_scalar_from_text(text, "active_gates_profile")


def _resume_point_from_state(state: dict[str, GateRun]) -> str:
    def passed(gate: str) -> bool:
        run = state.get(gate)
        return run is not None and run.status == "pass"

    if not passed("plan_approved"):
        return "PLAN"
    if not passed("review_approved"):
        return "IMPLEMENT"
    return "POSTIMPL"


def recorded_pass(task_file: str, gate: str) -> bool:
    """True iff ``gate``'s CURRENT recorded run has status ``pass`` (t1380).

    Reads the *recorded* ``## Gate Runs`` ledger with the same last-marker-wins
    rule as :func:`resume_point`, and applies the same **strict** ``== "pass"``
    predicate — deliberately NOT :data:`SATISFIED_STATUSES` (``{pass, skip}``),
    which :func:`archive_status` / :func:`dependents_status` use. A ``skip``
    means "not applicable", which is not an approval.

    Independent of the declared ``gates:`` / ``active_gates`` fields: the
    question is what the workflow *recorded*, not what the task enforces.
    """
    with open(task_file, encoding="utf-8") as fh:
        state = derive_gate_runs(fh.read())
    run = state.get(gate)
    return run is not None and run.status == "pass"


def read_task_gate_state(task_file: str, registry_file: str | None = None,
                         current_digest=_COMPUTE_DIGEST) -> TaskGateState:
    """Read a task file once and derive all gate state needed by TUIs.

    **Witness re-validation (t1416).** ``archive_decision`` and
    ``dependents_decision`` are derived with code-stale human-gate signatures
    demoted, so a TUI cannot report "ready to archive" for a task the enforcing
    guard (``aitask_gate.sh archive-ready``) would block. The offending gates are
    reported separately on ``stale_signed``; ``current`` keeps the raw ledger.

    Re-validation needs BOTH a ``registry_file`` (to know which gates are human
    and where their witnesses live) and a resolvable digest. A caller that passes
    **no registry is ledger-only by construction** — the monitor's
    ``GateSummaryCache`` is deliberately such a caller, because its cache is keyed
    on the *task file*'s ``(st_mtime_ns, st_size)`` and a code change does not
    touch that file. That split is ratified and registered in
    ``tests/test_gate_ledger_only_surfaces.py``; see
    ``aidocs/gates/gate-guarded-archival.md``.

    ``current_digest`` is the four-state channel of :func:`_resolve_digest`. A
    per-task caller in a refresh loop should pass its **once-per-refresh memo**
    (a callable) rather than the lazy default, which would compute one digest per
    task; the no-git pre-filter means neither costs anything for a task without a
    stamped witness.

    **Call this function directly — never through an alias or indirection.** The
    ledger-only/re-validated split is enforced by a syntactic guard, which an
    indirection defeats.
    """
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
    # Demote code-stale signatures once, then derive BOTH decisions from the same
    # effective view (t1416). Without a registry there are no human gates to
    # classify, so this is a no-op and costs nothing.
    effective, stale_signed = demote_stale_signed(
        active, registry, current, task_id_from_file(task_file), current_digest)
    archive_decision, archive_pending = _archive_status_from_state(active, effective)
    dep_decision, dep_pending = _dependents_status_from_state(active, also_effective,
                                                              registry, effective)
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
        stale_signed=stale_signed,
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

    if cmd == "deps-unblock-batch":
        # Task FILE PATHS on stdin, one per line; `<decision>\t<path>` per
        # NON-EMPTY input line, in input order. Blank lines are dropped below and
        # produce NO row, so the one-to-one guarantee is against non-empty lines,
        # not against raw line positions — map results by the echoed path. (A
        # blank line has no task file to decide; emitting `NO_GATES\t` for it
        # would hand `aitask_ls.sh` an empty basename to normalize.)
        # Exit 0 = every row decided (per-file fallbacks included — those are
        # isolated and the other rows are valid); exit 1 = registry setup failed
        # and every row is a conservative NO_GATES. Rows are always written
        # BEFORE the nonzero return, so a caller that ignores the status still
        # degrades safely.
        registry_file = argv[1] if len(argv) > 1 else None
        paths = [p for p in (ln.rstrip("\n") for ln in sys.stdin) if p]
        rows, setup_error = dependents_status_batch(paths, registry_file)
        for path, decision, pending in rows:
            label = ("BLOCKED:" + ",".join(pending)
                     if decision == "BLOCKED" else decision)
            sys.stdout.write(f"{label}\t{path}\n")
        return 1 if setup_error is not None else 0

    if cmd == "archive-ready":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py archive-ready <file> [registry]\n")
            return 2
        # The registry is what enables the t1409 stale-signature re-validation;
        # without it the decision stays ledger-only (pre-t1409 behavior).
        decision, nonpass = archive_status(argv[1],
                                           argv[2] if len(argv) > 2 else None)
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

    if cmd == "recorded-pass":
        if len(argv) < 3:
            sys.stderr.write("Usage: gate_ledger.py recorded-pass <file> <gate>\n")
            return 2
        return 0 if recorded_pass(argv[1], argv[2]) else 1

    if cmd == "run-state":
        if len(argv) < 3:
            sys.stderr.write("Usage: gate_ledger.py run-state <file> <gate>\n")
            return 2
        with open(argv[1], encoding="utf-8") as fh:
            text = fh.read()
        open_run = live_run(text, argv[2])
        run_id, attempt = open_run if open_run else ("", "")
        sys.stdout.write(f"OPEN:{run_id}|{attempt}\n")
        sys.stdout.write(f"TERMINAL:{next_attempt(text, argv[2]) - 1}\n")
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

    if cmd == "unverifiable-gates":
        # Pick-time check behind the `materialize-active` warning (t635_34).
        # A SEPARATE arm rather than an extra line on compute-active's output,
        # so the load-bearing digest/tuple path stays untouched.
        if len(argv) < 3:
            sys.stderr.write(
                "Usage: gate_ledger.py unverifiable-gates <registry> <gates_csv>\n")
            return 2
        registry = read_registry(argv[1])
        for gate in (g.strip() for g in argv[2].split(",") if g.strip()):
            reason = unverifiable_reason(gate, registry)
            if reason:
                sys.stdout.write(f"UNVERIFIABLE:{gate}:{reason}\n")
        return 0

    if cmd == "sync-registry":
        # Additive reconcile against the canonical reference (t635_34).
        if len(argv) < 4:
            sys.stderr.write(
                "Usage: gate_ledger.py sync-registry <registry> <reference> "
                "<dry_run:0|1> [scripts_dir] [profile_file ...]\n")
            return 2
        import gate_registry_sync as grs
        try:
            report = grs.sync_registry(
                argv[1], argv[2], dry_run=(argv[3] == "1"),
                scripts_dir=(argv[4] if len(argv) > 4 and argv[4] else None),
                profile_files=list(argv[5:]))
        except grs.SyncError as exc:
            sys.stderr.write(f"Error: {exc}\n")
            return exc.code
        for line in report:
            sys.stdout.write(line + "\n")
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
