"""Cross-repo dependency (``xdeprepo`` + ``xdeps``) status helpers.

Shared by the board's ``TaskManager`` (the Kanban card and detail screen) and
the By-Trail view / stand-alone trails app (t1957_1). It lives in ``lib/``
rather than in a board module because the trail modules' import contract (C1)
allows them no board import beyond ``board_widgets`` / ``board_trail_view``.

``xdep_ref_pairs`` and ``classify_xdep_status`` are pure. ``probe_xdep_status``
runs a blocking subprocess and caches nothing: the board wraps it in a
per-refresh cache, and the trail view only ever calls it from a worker thread.
"""

import subprocess


def xdep_ref_pairs(xdeprepo, xdeps) -> list:
    """``(repo, id)`` pairs of a task's cross-repo deps.

    Empty unless BOTH fields are present (the both-or-neither invariant from
    t832_3). ``xdeps`` values are not normalized by task_yaml, so they are
    coerced and stripped of a leading ``t`` here — the one normalization every
    consumer keys its status lookups on."""
    if not xdeprepo or not xdeps:
        return []
    return [(str(xdeprepo), str(xd).lstrip('t')) for xd in xdeps]


def classify_xdep_status(ref: str, status: str) -> tuple:
    """``(display, blocked)`` for ONE completed status probe of ``ref``.

    Fails closed: only ``Done`` unblocks. An empty status or ``NOT_FOUND`` is
    an unreachable project / missing task (``ref (UNREACHABLE)``); any other
    status is shown in brackets (``ref [Implementing]``)."""
    if status == 'Done':
        return ref, False
    if not status or status == 'NOT_FOUND':
        return f"{ref} (UNREACHABLE)", True
    return f"{ref} [{status}]", True


def probe_xdep_status(repo: str, task_id: str) -> str:
    """Live status of one cross-repo task — a blocking subprocess, no cache.

    Shells out to ``aitask_query_files.sh --project <repo> task-status <id>``
    (cross-repo re-exec resolves <repo> via the registry; the script path is
    cwd-relative, like every TUI launcher path). Returns the status (e.g.
    ``Implementing``, ``Done``), ``NOT_FOUND`` when the project resolves but
    the task is missing, or ``""`` when the project is unreachable or the
    probe fails."""
    try:
        result = subprocess.run(
            ["./.aitask-scripts/aitask_query_files.sh",
             "--project", repo, "task-status", task_id],
            capture_output=True, text=True, timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("STATUS:"):
            return line[len("STATUS:"):].strip()
    return ""
