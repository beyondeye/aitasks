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
    """Structured gate state for TUI consumers."""

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
    a declared-based count would read ``0/0`` for every task. Returns ``""``
    when no gate runs are recorded, so callers can show no column for ungated
    tasks. Example output: ``"3/4 pass, 1 pending"``, ``"2/2 pass"``, or
    ``"1/3 pass, 1 pending, 1 failed"``.
    """
    runs = list(state.current.values())
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
    }


def read_registry(registry_file: str) -> dict[str, dict]:
    """Parse gates.yaml with ``re`` only (stdlib, no PyYAML).

    Returns ``name -> {type, description, blocks_dependents, verifier,
    max_retries, unlocks, timeout_seconds, signal, signal_target}``.

    - ``blocks_dependents`` (t635_3) marks a gate required-to-pass before the
      owning task's dependents unblock; defaults to ``False``.
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
    declared = read_declared_gates_from_text(text)
    also = _read_frontmatter_list_from_text(text, "also_blocks_dependents")
    registry = read_registry(registry_file) if registry_file else {}
    return _dependents_status_from_state(declared, also, registry, derive_gate_runs(text))


# --- Gate-guarded archival decision (t635_4) ------------------------------

def _archive_status_from_state(declared: list[str],
                               state: dict[str, GateRun]) -> tuple[str, list[str]]:
    if not declared:
        return ("NO_GATES", [])
    nonpass = [g for g in declared
               if (state.get(g).status if state.get(g) else None) not in SATISFIED_STATUSES]
    return ("BLOCKED", nonpass) if nonpass else ("ALL_PASS", [])


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
    return _archive_status_from_state(read_declared_gates_from_text(text), derive_gate_runs(text))


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
    also = _read_frontmatter_list_from_text(text, "also_blocks_dependents")
    registry = read_registry(registry_file) if registry_file else {}
    archive_decision, archive_pending = _archive_status_from_state(declared, current)
    dep_decision, dep_pending = _dependents_status_from_state(declared, also, registry, current)
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

    if cmd == "resume-point":
        if len(argv) < 2:
            sys.stderr.write("Usage: gate_ledger.py resume-point <file>\n")
            return 2
        sys.stdout.write(resume_point(argv[1]) + "\n")
        return 0

    sys.stderr.write(f"Unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
