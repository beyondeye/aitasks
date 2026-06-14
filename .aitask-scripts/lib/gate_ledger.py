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
    gate_ledger.py append <task-file> <gate> <status> [key=value ...]
    gate_ledger.py status <task-file>
    gate_ledger.py list   <task-file> [registry.yaml]

Supported append keys (anything else is ignored with a warning):
    marker line : run, status, attempt, duration, type
    body lines  : verifier, result, log, note
"""
from __future__ import annotations

import datetime
import os
import re
import sys

SECTION_HEADER = "## Gate Runs"
SECTION_COMMENT = (
    "<!-- Appended by the gate framework. Do not edit by hand; "
    "use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->"
)

VALID_STATUSES = ("pass", "fail", "pending", "running", "skip", "error")
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
KV_RE = re.compile(r"(\w+)=(\S+)")

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


def iso_now() -> str:
    """Current UTC timestamp as ISO-8601-Z (second precision)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Parsing / derivation -------------------------------------------------

def parse_gate_runs(text: str) -> list[dict]:
    """Return every gate-run marker in file order as a list of dicts.

    Each dict has at least ``name`` and ``icon`` plus any ``key=value`` pairs
    found on the marker line (notably ``status``, ``attempt``, ``run``).
    Markers are matched anywhere in the file — the pattern is unambiguous and
    does not appear in ordinary task prose — so a missing/renamed section header
    never loses runs.
    """
    runs: list[dict] = []
    for line in text.splitlines():
        m = MARKER_RE.match(line)
        if not m:
            continue
        run = {"name": m.group(2), "icon": m.group(1)}
        run.update(dict(KV_RE.findall(m.group(3))))
        runs.append(run)
    return runs


def derive_status(text: str) -> dict[str, dict]:
    """Map gate name -> its current run (the last marker in file order wins)."""
    current: dict[str, dict] = {}
    for run in parse_gate_runs(text):
        current[run["name"]] = run
    return current


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


def format_status(text: str) -> str:
    """Render derived state, one gate per line, in first-seen order."""
    order: list[str] = []
    seen: set[str] = set()
    for run in parse_gate_runs(text):
        if run["name"] not in seen:
            seen.add(run["name"])
            order.append(run["name"])
    current = derive_status(text)
    return "\n".join(_format_status_line(n, current[n]) for n in order)


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

def read_declared_gates(task_file: str) -> list[str]:
    """Read the task's ``gates:`` frontmatter list (inline or block style)."""
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"(?s)\A---\n(.*?)\n---\n", text)
    fm = m.group(1) if m else text
    # Inline: gates: [a, b]
    inline = re.search(r"(?m)^gates:\s*\[(.*?)\]\s*$", fm)
    if inline:
        return [g.strip().strip("'\"") for g in inline.group(1).split(",") if g.strip()]
    # Block: gates:\n  - a\n  - b
    block = re.search(r"(?m)^gates:\s*$\n((?:[ \t]*-[ \t]*.+\n?)*)", fm)
    if block:
        return [re.sub(r"^[ \t]*-[ \t]*", "", ln).strip().strip("'\"")
                for ln in block.group(1).splitlines() if ln.strip()]
    return []


def read_registry(registry_file: str) -> dict[str, dict]:
    """Parse the minimal gates.yaml (name -> {type, description}) with re only."""
    gates: dict[str, dict] = {}
    if not registry_file or not os.path.exists(registry_file):
        return gates
    cur = None
    in_gates = False
    with open(registry_file, encoding="utf-8") as fh:
        for line in fh:
            if re.match(r"^gates:\s*$", line):
                in_gates = True
                continue
            if not in_gates:
                continue
            # A gate header is an indented "name:" with no inline value.
            hdr = re.match(r"^[ \t]+([A-Za-z0-9_]+):\s*$", line)
            if hdr:
                cur = hdr.group(1)
                gates[cur] = {"type": "", "description": ""}
                continue
            if cur is None:
                # A non-indented line ends the gates: mapping.
                if re.match(r"^\S", line):
                    in_gates = False
                continue
            mt = re.match(r"^[ \t]+type:\s*(.+?)\s*$", line)
            if mt:
                gates[cur]["type"] = mt.group(1).strip().strip("'\"")
                continue
            md = re.match(r"^[ \t]+description:\s*(.+?)\s*$", line)
            if md:
                gates[cur]["description"] = md.group(1).strip().strip("'\"")
                continue
            if re.match(r"^\S", line):
                in_gates = False
                cur = None
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

    sys.stderr.write(f"Unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
