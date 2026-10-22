"""Shared utilities for AgentCrew: YAML helpers, status validation, DAG ops, heartbeat."""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
from collections import deque
from datetime import date, datetime, timezone

import yaml

# lib/ holds bounded_run.py. Importers put different directories on sys.path
# (the scripts dir, agentcrew/ itself), so make lib/ reachable from here;
# appended, so it never shadows a module the importer already resolves.
_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.append(_LIB_DIR)

from bounded_run import noninteractive_env, run_bounded  # noqa: E402

# ---------------------------------------------------------------------------
# Status constants (must match .aitask-scripts/lib/agentcrew_utils.sh)
# ---------------------------------------------------------------------------

AGENT_STATUSES = [
    "Waiting", "Ready", "Running",
    "Completed", "Aborted", "Error", "Paused",
]
CREW_STATUSES = ["Initializing", "Running", "Killing", "Paused", "Completed", "Error", "Aborted"]

# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

AGENT_TRANSITIONS: dict[str, list[str]] = {
    "Waiting": ["Ready"],
    "Ready": ["Running"],
    "Running": ["Completed", "Error", "Aborted", "Paused"],
    "Paused": ["Running"],
    # Status is agent-self-reported. Heartbeat freshness is a separate signal
    # exposed via <agent>_alive.yaml; the runner does NOT mutate status on
    # stale heartbeat. Error remains recoverable so a Running -> Error -> Running
    # path is still valid for the agent's own self-correction.
    "Completed": [],
    "Aborted": [],
    "Error": ["Waiting", "Running", "Completed"],
}

CREW_TRANSITIONS: dict[str, list[str]] = {
    "Initializing": ["Running"],
    "Running": ["Killing", "Paused", "Completed", "Error", "Aborted"],
    "Killing": ["Completed", "Error", "Aborted"],
    "Paused": ["Running", "Killing", "Aborted"],
    # Terminal states
    "Completed": [],
    "Error": [],
    "Aborted": [],
}

# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

AGENTCREW_DIR = ".aitask-crews"


def read_yaml(path: str) -> dict:
    """Read a YAML file and return its contents as a dict."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def write_yaml(path: str, data: dict) -> None:
    """Write a dict to a YAML file."""
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def update_yaml_field(path: str, field: str, value) -> None:
    """Update a single field in a YAML file, preserving other fields."""
    data = read_yaml(path)
    data[field] = value
    write_yaml(path, data)

# ---------------------------------------------------------------------------
# Status validation
# ---------------------------------------------------------------------------


def validate_agent_transition(current: str, target: str) -> bool:
    """Return True if the agent status transition is valid."""
    if current not in AGENT_TRANSITIONS:
        return False
    return target in AGENT_TRANSITIONS[current]


def validate_crew_transition(current: str, target: str) -> bool:
    """Return True if the crew status transition is valid."""
    if current not in CREW_TRANSITIONS:
        return False
    return target in CREW_TRANSITIONS[current]


def compute_crew_status(agent_statuses: list[str]) -> str:
    """Derive the overall crew status from a list of agent statuses.

    Rules:
    - All Completed -> Completed
    - Any Error (no Running) -> Error
    - Any Running -> Running
    - All Waiting -> Initializing
    - Any Paused (no Running) -> Paused
    - Otherwise -> Running (mixed active states)
    """
    if not agent_statuses:
        return "Initializing"

    status_set = set(agent_statuses)
    active = {"Running"}

    if status_set == {"Completed"}:
        return "Completed"

    if "Error" in status_set and not (status_set & active):
        return "Error"

    if status_set & active:
        return "Running"

    # All members terminal, no active work. Error already returned above, so the
    # remaining set is a subset of {Completed, Aborted}. A run where every agent
    # was user-aborted is reported "Aborted" (honest); any real Completed output
    # makes it "Completed". Both are terminal and cleanup-eligible, and existing
    # consumers already treat crew-level "Aborted" as terminal (dashboard
    # STATUS_COLORS / cleanup gate, cleanup's is_terminal_state).
    if status_set <= {"Completed", "Aborted", "Error"}:
        return "Completed" if "Completed" in status_set else "Aborted"

    if status_set == {"Waiting"}:
        return "Initializing"

    if "Paused" in status_set and not (status_set & active):
        return "Paused"

    # Mixed states (e.g. some Ready, some Waiting, some Completed) -> Running
    return "Running"


def compute_crew_progress(agent_statuses: list[str]) -> int:
    """Percent of member agents that have reached Completed (0 if none)."""
    total = len(agent_statuses)
    if total == 0:
        return 0
    completed = sum(1 for s in agent_statuses if s == "Completed")
    return int(completed * 100 / total)


def read_member_statuses(crew_dir: str) -> list[str]:
    """Status string of every member agent (skips members with no status)."""
    statuses = []
    for sf in list_agent_files(crew_dir, "_status.yaml"):
        s = read_yaml(sf).get("status")
        if s:
            statuses.append(s)
    return statuses


# Seconds since the last runner heartbeat within which the runner is considered
# alive (a few runner iterations). Used to decide whether a persisted "Killing"
# crew status is still authoritative or should be derived from members instead.
RUNNER_LIVE_STALE_SECONDS = 180


def runner_is_live(crew_dir: str) -> bool:
    """True iff a runner is actively heartbeating for this crew."""
    p = os.path.join(crew_dir, "_runner_alive.yaml")
    if not os.path.isfile(p):
        return False
    d = read_yaml(p)
    if d.get("status") != "running":
        return False
    hb = _parse_timestamp(str(d.get("last_heartbeat", "")))
    if hb is None:
        return False
    return (datetime.now(timezone.utc) - hb).total_seconds() <= RUNNER_LIVE_STALE_SECONDS


def effective_crew_rollup(
    crew_dir: str, persisted_status: str = "", persisted_progress: int = 0
) -> tuple[str, int]:
    """Live (status, progress) for a crew, derived from member status files.

    Fixes a stale persisted ``_crew_status.yaml``: with no live runner to
    recompute it, the persisted aggregate lags member state. Readers call this
    instead of trusting the persisted fields, so the aggregate can never go
    stale at display/query/cleanup time regardless of runner lifecycle.

    "Killing" has no member-derivable equivalent (members stay Running during a
    graceful shutdown), so it is preserved ONLY while a runner is actively
    heartbeating; once the runner is gone it is derived from members so it never
    sticks permanently. A crew with no member status files keeps whatever was
    persisted (e.g. a freshly-initialized Initializing crew).
    """
    if persisted_status == "Killing" and runner_is_live(crew_dir):
        return persisted_status, persisted_progress
    statuses = read_member_statuses(crew_dir)
    if not statuses:
        return persisted_status or "Initializing", persisted_progress
    return compute_crew_status(statuses), compute_crew_progress(statuses)

# ---------------------------------------------------------------------------
# DAG operations
# ---------------------------------------------------------------------------


def topo_sort(agents: dict[str, list[str]]) -> list[str]:
    """Topological sort via Kahn's BFS. Returns ordered list of agent names.

    agents: {name: [dependency_names]}
    Raises ValueError if a cycle is detected.
    """
    # Build in-degree and adjacency (dep -> dependents)
    in_degree: dict[str, int] = {name: 0 for name in agents}
    dependents: dict[str, list[str]] = {name: [] for name in agents}

    for name, deps in agents.items():
        for dep in deps:
            if dep in agents:
                in_degree[name] += 1
                dependents[dep].append(name)

    queue = deque(name for name, deg in in_degree.items() if deg == 0)
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for dependent in dependents[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(agents):
        missing = set(agents) - set(result)
        raise ValueError(f"Circular dependency detected involving: {', '.join(sorted(missing))}")

    return result


def detect_cycles(agents: dict[str, list[str]]) -> list[str] | None:
    """Detect cycles in the agent dependency graph.

    Returns None if no cycle, or a list of agent names involved in a cycle.
    """
    try:
        topo_sort(agents)
        return None
    except ValueError:
        # Find the agents that couldn't be sorted
        in_degree: dict[str, int] = {name: 0 for name in agents}
        for name, deps in agents.items():
            for dep in deps:
                if dep in agents:
                    in_degree[name] += 1

        queue = deque(name for name, deg in in_degree.items() if deg == 0)
        visited: set[str] = set()
        while queue:
            node = queue.popleft()
            visited.add(node)
            for name, deps in agents.items():
                if node in deps and name not in visited:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        return sorted(set(agents) - visited)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def crew_worktree_path(crew_id: str) -> str:
    """Return the filesystem path for a crew's worktree."""
    return os.path.join(AGENTCREW_DIR, f"crew-{crew_id}")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


# Crew git network operations (t2024): each fetch/push to origin is bounded by
# AIT_CREW_GIT_TIMEOUT seconds. Mirrors crew_git_timeout in lib/agentcrew_utils.sh.
CREW_GIT_TIMEOUT_DEFAULT = 10
GIT_TIMED_OUT = 124
_CREW_GIT_TIMEOUT = re.compile(r"[0-9]{1,6}")


def crew_git_timeout() -> int:
    """Seconds one crew git network operation may take.

    Unset, empty, zero, negative, non-numeric or absurdly long values fall back
    to the default.
    """
    raw = os.environ.get("AIT_CREW_GIT_TIMEOUT", "")
    if _CREW_GIT_TIMEOUT.fullmatch(raw) and int(raw) > 0:
        return int(raw)
    return CREW_GIT_TIMEOUT_DEFAULT


def git_cmd(worktree: str, *args: str, check: bool = True,
            timeout: float | None = None, input: str | bytes | None = None,
            text: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the given worktree directory.

    ``timeout`` is for network operations only: the command then runs through
    bounded_run.run_bounded under noninteractive_env() — its own process group
    with no controlling terminal, no askpass program and no display, so nothing can
    prompt — and its whole process tree is killed after ``timeout`` seconds. A
    timed-out command reports exit status 124 with a message on stderr, like
    any other failure. Never pass it for a step that writes the worktree.

    ``input`` is fed to stdin, for local plumbing (``hash-object --stdin``,
    ``mktree``). ``text=False`` exchanges raw bytes — for file names and blob
    contents, which text mode would decode and newline-translate. Neither can
    be combined with ``timeout``.
    """
    cmd = ["git", "-C", worktree] + list(args)
    if timeout is None:
        return subprocess.run(cmd, capture_output=True, text=text, check=check,
                              input=input)
    if input is not None or not text:
        raise ValueError("git_cmd: input= and text=False are for local commands; "
                         "they cannot be bounded")
    try:
        result = run_bounded(cmd, timeout, env=noninteractive_env())
    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess(
            cmd, GIT_TIMED_OUT, "",
            f"timed out after {timeout:g}s (the remote did not answer in time; "
            "AIT_CREW_GIT_TIMEOUT sets the bound)")
    if check:
        result.check_returncode()
    return result


# git_pull outcomes (t2018).
PULL_OK = "ok"              # up to date, fast-forwarded, or merged
PULL_DEFERRED = "deferred"  # nothing merged and no merge state left; retried next time
PULL_UNSAFE = "unsafe"      # an unfinished merge or rebase sits in the worktree

_OBJECT_ID = re.compile(r"[0-9a-f]{40,64}")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def crew_merge_state(worktree: str) -> str | None:
    """Name the unfinished merge or rebase in the worktree, or None.

    ``merge_in_progress``, ``rebase_in_progress``, ``unmerged_paths``, or
    ``probe_failed`` when git could not answer: an unknown state is not a
    clean one.
    """
    merge_head = git_cmd(worktree, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False)
    if merge_head.returncode == 0:
        return "merge_in_progress"
    if merge_head.returncode != 1:
        return "probe_failed"
    for name in ("rebase-merge", "rebase-apply"):
        found = git_cmd(worktree, "rev-parse", "--git-path", name, check=False)
        if found.returncode != 0:
            return "probe_failed"
        path = found.stdout.strip()
        if os.path.exists(path if os.path.isabs(path) else os.path.join(worktree, path)):
            return "rebase_in_progress"
    unmerged = git_cmd(worktree, "ls-files", "-u", check=False)
    if unmerged.returncode != 0:
        return "probe_failed"
    return "unmerged_paths" if unmerged.stdout.strip() else None


def _commit_id(worktree: str, rev: str) -> str:
    found = git_cmd(worktree, "rev-parse", "-q", "--verify", f"{rev}^{{commit}}", check=False)
    oid = found.stdout.strip()
    return oid if found.returncode == 0 and _OBJECT_ID.fullmatch(oid) else ""


def _is_ancestor(worktree: str, ancestor: str, descendant: str) -> bool | None:
    """True / False, or None when git could not tell."""
    rc = git_cmd(worktree, "merge-base", "--is-ancestor", ancestor, descendant,
                 check=False).returncode
    return {0: True, 1: False}.get(rc)


def _upstream_source(worktree: str) -> tuple[str, str] | None:
    """The (remote, branch ref) the current branch tracks, or None."""
    branch = git_cmd(worktree, "symbolic-ref", "-q", "HEAD", check=False)
    ref = branch.stdout.strip()
    if branch.returncode != 0 or not ref:
        return None
    found = git_cmd(worktree, "for-each-ref",
                    "--format=%(upstream:remotename)%00%(upstream:remoteref)", ref, check=False)
    remote, _, merge_ref = found.stdout.strip().partition("\0")
    if found.returncode != 0 or not remote or not merge_ref:
        return None
    return remote, merge_ref


def _advance(worktree: str, target: str, outcome: str) -> tuple[str, str]:
    """Fast-forward the worktree to ``target``: the one step that writes it.

    ``merge --ff-only`` checks before writing and refuses, writing nothing, when
    a dirty, untracked or ignored path would be overwritten (git overwrites
    ignored files unless told not to) or when HEAD is no longer an ancestor of
    ``target``. It never leaves a MERGE_HEAD, so a refusal is a deferral and
    nothing is ever aborted.
    """
    advance = git_cmd(worktree, "merge", "--ff-only", "--no-autostash", "--no-overwrite-ignore",
                      "--quiet", target, check=False)
    if advance.returncode != 0:
        return PULL_DEFERRED, f"merge_refused: {_one_line(advance.stderr)}"
    return PULL_OK, outcome


def _sign_args(worktree: str) -> list[str] | None:
    """``-S`` when commit.gpgSign is set, as ``git merge`` would sign; None if unreadable."""
    found = git_cmd(worktree, "config", "--type=bool", "commit.gpgSign", check=False)
    if found.returncode == 1:
        return []
    if found.returncode != 0:
        return None
    return ["-S"] if found.stdout.strip() == "true" else []


# Runner-file convergence (t2029): the runner owns _runner_alive.yaml, so a
# merge conflict confined to it is resolved field by field, in memory.
RUNNER_ALIVE_FILE = "_runner_alive.yaml"
# The live runner's identity and heartbeat, which it rewrites after every pull.
_RUNNER_OWNED_FIELDS = frozenset({"status", "pid", "hostname", "started_at",
                                  "last_heartbeat", "next_check_at", "interval"})
_ABSENT = object()    # a key missing from one side
_CONFLICT = object()  # both sides changed a value differently


def _three_way(base, ours, theirs):
    """git's rule for one value: the side that changed it, else ``_CONFLICT``."""
    if ours == theirs or theirs == base:
        return ours
    if ours == base:
        return theirs
    return _CONFLICT


def _merge_runner_alive_fields(base: dict, ours: dict, theirs: dict) -> dict | None:
    """Merge the runner file's fields; None when a key cannot be resolved.

    Policies, in order — the field policies run before git's three-way rule:

    1. A runner-owned field takes ours, unconditionally (absence included): it
       describes the live runner doing this merge, which rewrites it right
       after the pull. A peer naming another runner is refused beforehand
       (``_competing_runner_identity``).
    2. ``requested_action``: a stop either side introduced since the merge
       base wins. Otherwise git's three-way rule, and theirs when both sides
       changed it. So a stop already in the base, cleared by a restarted
       runner and untouched on theirs, stays cleared, as a clean merge leaves
       it. A repeat stop written over that identical stop before the
       controller saw the clearing cannot be told from it and is lost — the
       merge contains the peer's commit, so no later pull brings it back — and
       must be reissued once the controller has synced.
    3. Any other key: git's three-way rule; None when both sides changed it.

    Keys keep ours' order, then theirs-only keys follow. The three sides must
    be flat mappings of scalars, as ``_runner_alive_at`` returns them: values
    are compared with ``==``, which a self-referencing value would recurse on.
    """
    merged = {}
    for key in list(ours) + [k for k in theirs if k not in ours]:
        b, o, t = (side.get(key, _ABSENT) for side in (base, ours, theirs))
        if key in _RUNNER_OWNED_FIELDS:
            value = o
        elif key == "requested_action":
            if b != "stop" and "stop" in (o, t):
                value = "stop"
            else:
                value = _three_way(b, o, t)
                if value is _CONFLICT:
                    value = t
        else:
            value = _three_way(b, o, t)
            if value is _CONFLICT:
                return None
        if value is not _ABSENT:
            merged[key] = value
    return merged


def _runner_identity(fields: dict) -> tuple:
    return fields.get("hostname", _ABSENT), fields.get("pid", _ABSENT)


def _competing_runner_identity(base: dict, ours: dict, theirs: dict) -> bool:
    """True when theirs names a runner other than this one.

    Theirs' (hostname, pid) changed since the merge base and is not ours: a
    takeover or a second runner rewrote the file. The field merge would
    overwrite that claim with ours, so the pull defers instead.
    """
    peer = _runner_identity(theirs)
    return peer != _runner_identity(base) and peer != _runner_identity(ours)


def _identity_label(fields: dict) -> str:
    return _one_line(f"{fields.get('hostname', '?')}/{fields.get('pid', '?')}")


# What a runner file field may hold (date covers datetime). Anything else — a
# list, a nested or self-referencing mapping — the runner never writes, and
# comparing it could recurse without end, so it makes the side unreadable.
_RUNNER_SCALARS = (str, int, float, bool, date, type(None))


def _runner_alive_at(worktree: str, rev: str) -> dict | None:
    """The runner file's fields at ``rev``; None unless it is a flat mapping of scalars.

    The blob is a peer's bytes: read raw and decoded here, so invalid UTF-8,
    a value YAML cannot construct (``2026-99-99 10:00:00`` is a timestamp
    with no date), runaway nesting or a non-scalar value (``note: &n {self:
    *n}``) is an unreadable side, never an exception that would end the runner.
    """
    found = git_cmd(worktree, "cat-file", "blob", f"{rev}:{RUNNER_ALIVE_FILE}",
                    check=False, text=False)
    if found.returncode != 0:
        return None
    try:
        data = yaml.safe_load(found.stdout.decode("utf-8"))
    except (yaml.YAMLError, ValueError, RecursionError):  # UnicodeDecodeError is a ValueError
        return None
    if not isinstance(data, dict) or not all(
            isinstance(k, str) and isinstance(v, _RUNNER_SCALARS) for k, v in data.items()):
        return None
    return data


def _resolve_runner_alive(worktree: str, head: str, upstream: str, tree: str,
                          conflicted: list[str]) -> tuple[str, str]:
    """Resolve a merge conflict confined to the runner file, in memory (t2029).

    Returns ``(tree, "")`` — merge-tree's ``tree`` with the conflicted runner
    file replaced by its field-wise merge — or ``("", reason)`` to defer; a
    conflict on any other path defers with no reason, as before. Only objects
    are written (hash-object, mktree); the worktree is never touched.
    """
    if conflicted != [RUNNER_ALIVE_FILE]:
        return "", ""
    if not _OBJECT_ID.fullmatch(tree):
        return "", "merge-tree reported no tree id"
    ours = _runner_alive_at(worktree, head)
    theirs = _runner_alive_at(worktree, upstream)
    base: dict | None = {}
    found = git_cmd(worktree, "merge-base", head, upstream, check=False)
    base_rev = found.stdout.strip()
    if (found.returncode == 0 and _OBJECT_ID.fullmatch(base_rev)
            and git_cmd(worktree, "cat-file", "-e", f"{base_rev}:{RUNNER_ALIVE_FILE}",
                        check=False).returncode == 0):
        base = _runner_alive_at(worktree, base_rev)
    if ours is None or theirs is None or base is None:
        return "", "runner file unreadable on one side"
    if _competing_runner_identity(base, ours, theirs):
        return "", ("competing runner identities: "
                    f"{_identity_label(theirs)} vs {_identity_label(ours)}")
    fields = _merge_runner_alive_fields(base, ours, theirs)
    if fields is None:
        return "", "runner file fields conflict"
    blob = git_cmd(worktree, "hash-object", "-w", "--stdin", check=False,
                   input=yaml.safe_dump(fields, default_flow_style=False, sort_keys=False))
    blob_id = blob.stdout.strip()
    if blob.returncode != 0 or not _OBJECT_ID.fullmatch(blob_id):
        return "", f"runner file blob not written: {_one_line(blob.stderr)}"
    # Raw bytes end to end: the other entries' names reach mktree exactly as
    # ls-tree printed them (text mode would turn a CR into a LF, or fail).
    listing = git_cmd(worktree, "ls-tree", "-z", tree, check=False, text=False)
    if listing.returncode != 0:
        return "", f"merge tree unreadable: {_one_line(listing.stderr.decode(errors='replace'))}"
    runner_name = RUNNER_ALIVE_FILE.encode()
    entries = [e for e in listing.stdout.split(b"\0") if e]
    hits = [i for i, e in enumerate(entries) if e.partition(b"\t")[2] == runner_name]
    if len(hits) != 1:
        return "", "runner file entry not found once in the merge tree"
    meta = entries[hits[0]].partition(b"\t")[0].split()
    if len(meta) != 3 or meta[1] != b"blob" or meta[0] not in (b"100644", b"100755"):
        return "", "runner file is not a regular file in the merge tree"
    entries[hits[0]] = meta[0] + b" blob " + blob_id.encode() + b"\t" + runner_name
    built = git_cmd(worktree, "mktree", "-z", check=False, text=False,
                    input=b"".join(e + b"\0" for e in entries))
    resolved = built.stdout.decode("ascii", errors="replace").strip()
    if built.returncode != 0 or not _OBJECT_ID.fullmatch(resolved):
        return "", f"merged tree not built: {_one_line(built.stderr.decode(errors='replace'))}"
    return resolved, ""


def _merge_diverged(worktree: str, head: str, upstream: str) -> tuple[str, str]:
    """Merge the pinned commits without ever opening a merge in the worktree.

    aitask_sync.sh's guarded merge (t1731), minus its disjoint-paths policy:
    the runner must merge same-file edits on different lines (its heartbeat vs
    a peer's requested_action). merge-tree proves the merge clean in memory,
    commit-tree builds it, and ``_advance`` fast-forwards to it. A conflict
    confined to the runner's own file is resolved field by field in memory
    instead (``_resolve_runner_alive``, t2029); any other conflict defers.
    commit-tree does not read commit.gpgSign, so the setting is passed on
    explicitly; a signing failure defers. As in t1731, no commit hooks run for
    this commit.
    """
    proof = git_cmd(worktree, "merge-tree", "--write-tree", "--no-messages", "--name-only",
                    head, upstream, check=False)
    lines = proof.stdout.splitlines()
    resolved = ""
    if proof.returncode == 1:
        conflicted = [p for p in lines[1:] if p]
        tree, why = _resolve_runner_alive(worktree, head, upstream,
                                          lines[0].strip() if lines else "", conflicted)
        if not tree:
            return PULL_DEFERRED, ("merge_conflict: " + ", ".join(conflicted)
                                   + (f" ({why})" if why else ""))
        resolved = f" (resolved {RUNNER_ALIVE_FILE})"
    elif proof.returncode == 129:
        # No live-worktree fallback: a plain merge would write conflict markers
        # into files the agents read and stage.
        return PULL_DEFERRED, ("merge_proof_unsupported: divergent histories need "
                               "git >= 2.38 (merge-tree --write-tree)")
    else:
        tree = lines[0].strip() if lines else ""
        if proof.returncode != 0 or not _OBJECT_ID.fullmatch(tree):
            return PULL_DEFERRED, f"merge_proof_failed: {_one_line(proof.stderr) or 'no tree id'}"
    sign = _sign_args(worktree)
    if sign is None:
        return PULL_DEFERRED, "merge_commit_failed: commit.gpgSign could not be read"
    commit = git_cmd(worktree, "commit-tree", *sign, tree, "-p", head, "-p", upstream,
                     "-m", f"crew: merge {upstream[:12]} into {head[:12]}{resolved}",
                     check=False)
    merged = commit.stdout.strip()
    if commit.returncode != 0 or not _OBJECT_ID.fullmatch(merged):
        return PULL_DEFERRED, f"merge_commit_failed: {_one_line(commit.stderr)}"
    return _advance(worktree, merged, f"merged {upstream[:12]}{resolved}")


def _sync_with_upstream(worktree: str) -> tuple[str, str]:
    source = _upstream_source(worktree)
    if source is None:
        return PULL_DEFERRED, "no_upstream: the crew branch tracks no upstream"
    remote, merge_ref = source
    # The fetch `git pull` would run, on its own: a transport failure is
    # reported instead of being read past via stale tracking refs. The one
    # network step, so the only bounded one (t2024); a timeout is a failure.
    fetch = git_cmd(worktree, "fetch", "--quiet", "--", remote, merge_ref, check=False,
                    timeout=crew_git_timeout())
    if fetch.returncode != 0:
        return PULL_DEFERRED, f"fetch_failed: {_one_line(fetch.stderr) or f'exit {fetch.returncode}'}"
    head = _commit_id(worktree, "HEAD")
    upstream = _commit_id(worktree, "@{u}")
    if not head or not upstream:
        return PULL_DEFERRED, "rev_unresolved: HEAD or @{u} is not a commit"
    if head == upstream:
        return PULL_OK, "up to date"
    upstream_merged = _is_ancestor(worktree, upstream, head)
    if upstream_merged:
        return PULL_OK, "ahead of upstream"
    behind_only = _is_ancestor(worktree, head, upstream)
    if upstream_merged is None or behind_only is None:
        return PULL_DEFERRED, "ancestry_unknown"
    if behind_only:
        return _advance(worktree, upstream, "fast-forwarded")
    return _merge_diverged(worktree, head, upstream)


def git_pull(worktree: str, batch: bool = False) -> tuple[str, str]:
    """Bring the crew branch up to date with its upstream (best-effort).

    --no-autostash (t2008): agents' uncommitted heartbeat/status/command files
    live in this worktree, and a user's merge.autoStash would stash and
    re-apply them around the merge.

    Never opens a merge in the worktree (t2018): after fetching the upstream it
    fast-forwards, or for a diverged branch fast-forwards to the merge proven
    clean in memory (``_merge_diverged``); a conflict confined to
    _runner_alive.yaml is resolved there field by field (t2029). A failed
    fetch, any other conflict, a runner file that cannot be resolved, a
    missing proof (git < 2.38) or a path that is dirty, untracked or ignored
    is a deferral that leaves the worktree as it was. Returns
    ``(status, detail)``:

    - ``PULL_OK`` / ``PULL_DEFERRED`` — no merge state in the worktree; the
      caller carries on.
    - ``PULL_UNSAFE`` — an unfinished merge or rebase (detail names it), left
      by another process before or during this pull. Callers must not read,
      rewrite or stage crew files until it is resolved; this function never
      aborts or resets it.
    """
    state = crew_merge_state(worktree)
    if state:
        return PULL_UNSAFE, state
    status, detail = _sync_with_upstream(worktree)
    state = crew_merge_state(worktree)
    if state:
        return PULL_UNSAFE, state
    if status == PULL_DEFERRED and not batch:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] git pull warning: {detail}", file=sys.stderr)
    return status, detail


def git_push(worktree: str, batch: bool = False) -> None:
    """Publish the crew branch to origin (best-effort).

    Always ``push -u origin HEAD`` (t2016): crew init creates the branch with
    no upstream, so a bare ``git push`` dies with "has no upstream branch"
    unless the user sets push.autoSetupRemote; -u gives it one on the first
    push that succeeds, so an offline init heals later. Naming the destination
    also keeps a push.default=matching from publishing the repository's other
    branches. No origin remote means nothing to publish to: skip silently.
    Bounded by crew_git_timeout() (t2024); a timeout is warned like any other
    failure and leaves the branch as a failed push does. Mirrors ``crew_push``
    in lib/agentcrew_utils.sh.
    """
    if git_cmd(worktree, "remote", "get-url", "origin", check=False).returncode != 0:
        return
    result = git_cmd(worktree, "push", "--quiet", "-u", "origin", "HEAD", check=False,
                     timeout=crew_git_timeout())
    if result.returncode != 0 and not batch:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] git push warning: {result.stderr.strip()}", file=sys.stderr)


def _commit_index(worktree: str, message: str) -> tuple[str, str]:
    """Commit the staged index to the checked-out crew branch (t2028).

    Never ``git commit``: it concludes a merge (it reads MERGE_HEAD) and commits
    onto a rebase's detached HEAD, so no check placed before it can be trusted
    and none placed after it can tell our commit from a concurrent writer's.
    The tree is written, the state re-checked, the commit built with commit-tree
    (which never reads MERGE_HEAD), and the branch ref advanced with a
    compare-and-swap update-ref: it lands only if the branch is still where it
    was, so the commit is exactly ours and a plain child of it. As for the
    synthetic merge commit (``_merge_diverged``), no commit hooks run. Mirrors
    ``crew_commit_paths`` in lib/agentcrew_utils.sh.

    Returns ``(outcome, detail)``: ``committed`` (detail: the commit),
    ``nothing`` (the tree is HEAD's: another writer committed it), ``unsafe``
    (detail: the crew_merge_state that appeared), ``moved`` (the branch moved
    under the swap; retry), or ``failed`` (detail: why).
    """
    ref = git_cmd(worktree, "symbolic-ref", "-q", "HEAD", check=False)
    branch = ref.stdout.strip()
    if ref.returncode != 0 or not branch:
        state = crew_merge_state(worktree)
        return ("unsafe", state) if state else ("failed", "HEAD is detached")
    pre = _commit_id(worktree, "HEAD")
    if not pre:
        return "failed", "HEAD is not a commit"
    written = git_cmd(worktree, "write-tree", check=False)
    tree = written.stdout.strip()
    state = crew_merge_state(worktree)
    if state:
        return "unsafe", state
    if written.returncode != 0 or not _OBJECT_ID.fullmatch(tree):
        return "failed", f"write-tree: {_one_line(written.stderr) or 'no tree id'}"
    head_tree = git_cmd(worktree, "rev-parse", "-q", "--verify", f"{pre}^{{tree}}", check=False)
    if head_tree.returncode == 0 and head_tree.stdout.strip() == tree:
        return "nothing", ""
    sign = _sign_args(worktree)
    if sign is None:
        return "failed", "commit.gpgSign could not be read"
    commit = git_cmd(worktree, "commit-tree", *sign, tree, "-p", pre, "-m", message, check=False)
    new = commit.stdout.strip()
    if commit.returncode != 0 or not _OBJECT_ID.fullmatch(new):
        return "failed", f"commit-tree: {_one_line(commit.stderr)}"
    swap = git_cmd(worktree, "update-ref", "-m", f"commit: {message}", branch, new, pre,
                   check=False)
    if swap.returncode != 0:
        return "moved", ""
    return "committed", new


_COMMIT_ATTEMPTS = 3


def git_commit_push_if_changes(worktree: str, message: str, batch: bool = False) -> None:
    """Stage all changes in worktree, commit and push if there are changes.

    Never stages, commits or pushes while a merge or rebase is unfinished in the
    worktree (t2028): ``git add -A`` would mark conflicted paths resolved with
    their markers. The commit goes through ``_commit_index``, so it can never
    conclude or join another process's operation; a branch that moved under it
    is retried. A call that staged work publishes the branch once that work is
    on it, whoever committed it — ``ait crew status set`` relies on its terminal
    transition reaching origin. The skip warnings go to stderr in batch mode too:
    they are the only sign that a change stayed uncommitted.
    """
    had_work = False
    for _ in range(_COMMIT_ATTEMPTS):
        state = crew_merge_state(worktree)
        if state:
            _warn_commit_skipped(worktree, message, f"unfinished {state}",
                                 "staged but not committed" if had_work else "nothing staged")
            return
        staged = git_cmd(worktree, "add", "-A", check=False)
        if staged.returncode != 0:
            # An unstaged change is not "no work": a held index.lock would
            # otherwise leave e.g. a terminal status uncommitted without a word.
            _warn_commit_skipped(worktree, message,
                                 f"git add failed: {_one_line(staged.stderr) or f'exit {staged.returncode}'}",
                                 "staged but not committed" if had_work else "not staged")
            return
        if git_cmd(worktree, "diff", "--cached", "--quiet", check=False).returncode == 0:
            if had_work:
                git_push(worktree, batch)  # another writer committed our work
            return
        had_work = True
        outcome, detail = _commit_index(worktree, message)
        if outcome in ("committed", "nothing"):
            git_push(worktree, batch)
            return
        if outcome == "unsafe":
            _warn_commit_skipped(worktree, message, f"unfinished {detail}",
                                 "staged but not committed")
            return
        if outcome == "failed":
            _warn_commit_skipped(worktree, message, detail, "staged but not committed")
            return
    _warn_commit_skipped(worktree, message, "the crew branch kept moving",
                         "staged but not committed")


def _warn_commit_skipped(worktree: str, message: str, reason: str, left: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] git commit skipped ({message}): {reason} in {worktree}; changes "
          f"{left}. The crew runner holds while a merge or rebase is unfinished: "
          f"`git -C {worktree} status` shows it.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Agent file enumeration
# ---------------------------------------------------------------------------


def list_agent_files(worktree_path: str, suffix: str) -> list[str]:
    """List all agent files with the given suffix in the worktree.

    Excludes crew-level files (prefixed with _).
    """
    pattern = os.path.join(worktree_path, f"*{suffix}")
    return [
        f for f in sorted(glob.glob(pattern))
        if not os.path.basename(f).startswith("_")
    ]


def get_agent_names(worktree_path: str) -> list[str]:
    """Get all agent names from _status.yaml files in the worktree."""
    names = []
    for status_file in list_agent_files(worktree_path, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        if name:
            names.append(name)
    return names

# ---------------------------------------------------------------------------
# Ready-agent detection
# ---------------------------------------------------------------------------


def get_ready_agents(worktree_path: str) -> list[str]:
    """Return agents with Waiting status whose all dependencies are Completed.

    These agents are eligible to transition to Ready.
    """
    # Load all agent statuses and dependencies
    agent_data: dict[str, dict] = {}
    for status_file in list_agent_files(worktree_path, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        if name:
            agent_data[name] = data

    ready = []
    for name, data in agent_data.items():
        if data.get("status") != "Waiting":
            continue
        deps = data.get("depends_on", [])
        if not deps:
            ready.append(name)
            continue
        # Check all deps are Completed
        all_done = all(
            agent_data.get(dep, {}).get("status") == "Completed"
            for dep in deps
        )
        if all_done:
            ready.append(name)

    return sorted(ready)

# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


def _parse_timestamp(ts_str: str) -> datetime | None:
    """Parse a UTC timestamp string. Returns None if empty or invalid."""
    if not ts_str:
        return None
    ts_str = str(ts_str).strip()
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def check_agent_alive(alive_path: str, timeout_seconds: int = 300) -> bool:
    """Check if an agent's heartbeat is within the timeout.

    Returns True if alive (heartbeat within timeout), False if stale or no heartbeat.
    """
    data = read_yaml(alive_path)
    last_hb = data.get("last_heartbeat")
    if not last_hb:
        return False
    ts = _parse_timestamp(str(last_hb))
    if ts is None:
        return False
    now = datetime.now(timezone.utc)
    return (now - ts).total_seconds() <= timeout_seconds


def get_stale_agents(worktree_path: str, timeout_seconds: int = 300) -> list[str]:
    """Return names of Running agents whose heartbeat exceeds the timeout."""
    stale = []
    for status_file in list_agent_files(worktree_path, "_status.yaml"):
        data = read_yaml(status_file)
        name = data.get("agent_name", "")
        status = data.get("status", "")
        if not name or status != "Running":
            continue
        alive_path = os.path.join(worktree_path, f"{name}_alive.yaml")
        if not os.path.isfile(alive_path):
            stale.append(name)
            continue
        if not check_agent_alive(alive_path, timeout_seconds):
            stale.append(name)
    return sorted(stale)


# ---------------------------------------------------------------------------
# Crew listing
# ---------------------------------------------------------------------------


def list_crews() -> list[dict]:
    """List all agentcrews by scanning .aitask-crews/ directories.

    Returns a list of dicts, each with keys:
      id, name, status, progress, created_at, started_at, updated_at,
      agent_count, runner_status, runner_heartbeat
    """
    crews_dir = AGENTCREW_DIR
    if not os.path.isdir(crews_dir):
        return []

    results = []
    prefix = "crew-"
    for entry in sorted(os.listdir(crews_dir)):
        entry_path = os.path.join(crews_dir, entry)
        if not os.path.isdir(entry_path) or not entry.startswith(prefix):
            continue

        crew_id = entry[len(prefix):]
        meta_path = os.path.join(entry_path, "_crew_meta.yaml")
        status_path = os.path.join(entry_path, "_crew_status.yaml")
        runner_path = os.path.join(entry_path, "_runner_alive.yaml")

        meta = read_yaml(meta_path) if os.path.isfile(meta_path) else {}
        status_data = read_yaml(status_path) if os.path.isfile(status_path) else {}
        runner_data = read_yaml(runner_path) if os.path.isfile(runner_path) else {}

        agent_names = get_agent_names(entry_path)

        eff_status, eff_progress = effective_crew_rollup(
            entry_path,
            status_data.get("status", "Unknown"),
            status_data.get("progress", 0),
        )

        results.append({
            "id": crew_id,
            "name": meta.get("name", crew_id),
            "status": eff_status,
            "progress": eff_progress,
            "created_at": meta.get("created_at", ""),
            "started_at": status_data.get("started_at", ""),
            "updated_at": status_data.get("updated_at", ""),
            "agent_count": len(agent_names),
            "runner_status": runner_data.get("status", ""),
            "runner_heartbeat": runner_data.get("last_heartbeat", ""),
        })

    return results


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def load_groups(crew_dir: str) -> list[dict]:
    """Load _groups.yaml, return list of group dicts sorted by sequence."""
    groups_file = os.path.join(crew_dir, "_groups.yaml")
    if not os.path.exists(groups_file):
        return []
    data = read_yaml(groups_file)
    groups = data.get("groups", [])
    return sorted(groups, key=lambda g: g.get("sequence", 999))


def get_group_agents(crew_dir: str, group_name: str) -> list[str]:
    """Return agent names belonging to the specified group."""
    agents = []
    for f in list_agent_files(crew_dir, "_status.yaml"):
        data = read_yaml(f)
        if data.get("group", "") == group_name:
            name = data.get("agent_name", "")
            if name:
                agents.append(name)
    return agents


def get_group_status(crew_dir: str, group_name: str) -> str:
    """Return derived status for a group: Completed/Running/Error/Waiting."""
    agents = get_group_agents(crew_dir, group_name)
    if not agents:
        return "Waiting"
    statuses = []
    for name in agents:
        sf = os.path.join(crew_dir, f"{name}_status.yaml")
        if os.path.exists(sf):
            data = read_yaml(sf)
            statuses.append(data.get("status", "Waiting"))
    if all(s == "Completed" for s in statuses):
        return "Completed"
    active = {"Running"}
    status_set = set(statuses)
    if "Error" in status_set and not (status_set & active):
        return "Error"
    if status_set & active:
        return "Running"
    return "Waiting"


def group_sort_key(agent_status: dict, groups: list[dict]) -> tuple:
    """Return sort key for group-priority scheduling.

    Lower sequence = higher priority. No-group agents sort last.
    """
    group_name = agent_status.get("group", "")
    if not group_name:
        return (999, agent_status.get("agent_name", ""))
    for g in groups:
        if g.get("name") == group_name:
            return (g.get("sequence", 999), agent_status.get("agent_name", ""))
    return (999, agent_status.get("agent_name", ""))


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_elapsed(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    if seconds < 0:
        return "0s"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        secs = seconds % 60
        return f"{minutes}m" if secs == 0 else f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h" if mins == 0 else f"{hours}h {mins}m"
