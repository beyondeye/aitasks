"""Gateway-side task creation from a validated payload (t1120_6).

Pinned contract 7: **the gateway creates + commits the aitask; the agent
has no git access.** The description travels via stdin (``--desc-file -``)
as an argv-list subprocess — never shell interpolation, never
user-controlled frontmatter keys. ``--commit`` routes through the script's
own ``task_git`` gateway, so aitask-data-branch semantics are respected.

Blocking module (subprocess + parsing) — the flow runs it via
``asyncio.to_thread``. Script path and push argv are injectable test seams.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .relay import TaskPayload

#: Success is either a ``Finalized: <path> (ID: <id>)`` line (remote-ID
#: claim flow) or a plain ``Created: <path>`` line (local/no-remote claim
#: flow — the ``--commit`` commit still lands; observed in fixture repos).
#: Output may carry ANSI color codes (terminal_compat.sh colors
#: unconditionally).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_FINALIZED_RE = re.compile(
    r"^Finalized(?: child task)?: (?P<path>\S+) \(ID: (?P<id>[A-Za-z0-9_]+)\)",
    re.MULTILINE,
)
_CREATED_RE = re.compile(r"^Created: (?P<path>\S+)", re.MULTILINE)

_CREATE_TIMEOUT_S = 120
_PUSH_TIMEOUT_S = 60


class TaskCreateError(Exception):
    """Creation failed; ``reason`` is machine-readable for thread + audit."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CreatedTask:
    task_id: str
    path: str


def build_description(payload: TaskPayload, *, initiator_tag: str) -> str:
    """The stdin description document: title heading + body + provenance."""
    return (
        f"## {payload.title}\n\n"
        f"{payload.description}\n\n"
        f"---\n"
        f"*Reported via chatlink session `{payload.session_id}` "
        f"by {initiator_tag}.*\n"
    )


def create_task_from_payload(
    payload: TaskPayload,
    *,
    repo_root: str | Path,
    initiator_tag: str,
    audit,
    create_script: str | Path | None = None,
    push_argv: tuple | None = None,
) -> CreatedTask:
    """Create + commit an aitask from a validated payload; then push
    best-effort. Raises :class:`TaskCreateError` on failure (the flow maps
    it to a fail-closed session failure)."""
    repo_root = Path(repo_root)
    script = Path(create_script) if create_script is not None else (
        repo_root / ".aitask-scripts" / "aitask_create.sh")
    argv = [
        str(script), "--batch", "--commit",
        "--name", payload.name,
        "--priority", payload.priority,
        "--effort", payload.effort,
        "--type", payload.issue_type,
        "--desc-file", "-",
    ]
    if payload.labels:
        argv += ["--labels", ",".join(payload.labels)]
    desc = build_description(payload, initiator_tag=initiator_tag)
    try:
        proc = subprocess.run(
            argv, input=desc, capture_output=True, text=True,
            cwd=str(repo_root), timeout=_CREATE_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TaskCreateError(f"create script failed to run: {exc}") from exc
    out = _ANSI_RE.sub("", proc.stdout or "")
    if proc.returncode != 0:
        err = _ANSI_RE.sub("", (proc.stderr or "")).strip()
        audit.error("task create exited %s: %s", proc.returncode,
                    err[-500:])
        raise TaskCreateError(f"create script exited {proc.returncode}")
    match = _FINALIZED_RE.search(out)
    if match is not None:
        created = CreatedTask(task_id=match.group("id"),
                              path=match.group("path"))
    else:
        match = _CREATED_RE.search(out)
        if match is None:
            audit.error("task create output unparseable: %r", out[-500:])
            raise TaskCreateError(
                "create output missing Finalized/Created line")
        path = match.group("path")
        # ``aitasks/t42_some_name.md`` → id ``t42``
        created = CreatedTask(task_id=Path(path).stem.split("_", 1)[0],
                              path=path)
    audit.info("task created id=%s path=%s session=%s",
               created.task_id, created.path, payload.session_id)

    # Best-effort push (audited, never fatal — the commit is durable).
    argv_push = list(push_argv) if push_argv is not None else [
        str(repo_root / "ait"), "git", "push"]
    try:
        push = subprocess.run(
            argv_push, capture_output=True, text=True,
            cwd=str(repo_root), timeout=_PUSH_TIMEOUT_S,
        )
        if push.returncode != 0:
            audit.warning("task push failed (rc=%s) — commit is local only",
                          push.returncode)
    except (OSError, subprocess.TimeoutExpired) as exc:
        audit.warning("task push failed: %s — commit is local only", exc)
    return created
