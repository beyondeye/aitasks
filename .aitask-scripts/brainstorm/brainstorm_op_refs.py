"""Typed references to operation data on disk.

Lets dashboard and detail screens point at user inputs / agent outputs /
agent logs in their canonical session-directory locations rather than
duplicating values into ``br_groups.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .brainstorm_dag import NODES_DIR, PLANS_DIR, PROPOSALS_DIR

_OP_INPUT_SECTION = {
    "explore":   "Exploration Mandate",
    "compare":   "Comparison Request",
    "hybridize": "Merge Rules",
    "detail":    None,
    "patch":     "Patch Request",
    "bootstrap": "Mandate",
}

_VALID_KINDS = {
    "agent_input", "agent_output", "agent_log",
    "node_proposal", "node_plan", "node_metadata",
    "session_spec",
}


@dataclass(frozen=True)
class OpDataRef:
    kind: str
    target: str
    section: str | None = None

    def __post_init__(self):
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"OpDataRef: bad kind {self.kind!r}")


def file_for_ref(session_path: Path, ref: OpDataRef) -> Path:
    if ref.kind == "agent_input":
        return session_path / f"{ref.target}_input.md"
    if ref.kind == "agent_output":
        return session_path / f"{ref.target}_output.md"
    if ref.kind == "agent_log":
        return session_path / f"{ref.target}_log.txt"
    if ref.kind == "node_proposal":
        return session_path / PROPOSALS_DIR / f"{ref.target}.md"
    if ref.kind == "node_plan":
        return session_path / PLANS_DIR / f"{ref.target}_plan.md"
    if ref.kind == "node_metadata":
        return session_path / NODES_DIR / f"{ref.target}.yaml"
    if ref.kind == "session_spec":
        return session_path / "br_session.yaml"
    raise ValueError(f"unhandled kind {ref.kind!r}")


def resolve_ref(session_path: Path, ref: OpDataRef) -> str:
    p = file_for_ref(session_path, ref)
    if not p.is_file():
        return ""
    text = p.read_text(encoding="utf-8")
    if ref.section is None:
        return text
    return _extract_md_section(text, ref.section)


def _extract_md_section(text: str, header: str) -> str:
    """Extract content under ``## <header>`` until the next ``## `` or EOF.

    Returns empty string if the header is not found.
    """
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("## ") and ln[3:].strip() == header:
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end]).strip("\n")


def list_op_inputs(group_info: dict) -> list[OpDataRef]:
    agents = group_info.get("agents") or []
    op = group_info.get("operation", "")
    if not agents:
        return []
    section = _OP_INPUT_SECTION.get(op)
    return [OpDataRef("agent_input", agents[0], section=section)]


def list_op_outputs(group_info: dict) -> list[OpDataRef]:
    return [OpDataRef("agent_output", a)
            for a in group_info.get("agents") or []]


def list_op_logs(group_info: dict) -> list[OpDataRef]:
    return [OpDataRef("agent_log", a)
            for a in group_info.get("agents") or []]


def list_op_definition(group_info: dict) -> list[OpDataRef]:
    refs: list[OpDataRef] = []
    head = group_info.get("head_at_creation")
    if head:
        refs.append(OpDataRef("node_metadata", head))
    for nid in group_info.get("nodes_created") or []:
        refs.append(OpDataRef("node_metadata", nid))
    return refs
