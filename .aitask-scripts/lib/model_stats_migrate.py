#!/usr/bin/env python3
"""model_stats_migrate.py - one-time move of legacy counters into aitask-stats (t1912_5).

Until an agent is migrated, ``models_<agent>.json`` on the task-data branch still
holds frozen ``usagestats`` / ``verifiedstats`` counters, and readers add them to
the branch counters. ``migrate`` moves them into the ``aitask-stats`` branch
exactly once per agent and strips them from the registry. After that, the
per-agent marker ``migrations/<agent>.json`` makes readers use the branch only.

The cutover point
-----------------
For every agent, the cutover is ONE **baseline** commit on the task-data branch,
pushed with a lease on the pinned source tip O. It carries these trailers:

    Stats-Migration-Agent: <agent>
    Stats-Migration-Kind:  baseline
    Stats-Migration-Id:    <uuid4 hex>

When the source holds counters, the baseline strips them. When it holds none,
the baseline is an empty commit (same tree as O). Either way the empty-source
case and the counters case go through the same leased push, so there is at
most one baseline per agent: a baseline is only pushed against a tip with no
baseline in its history, and the lease rejects any tip that moved.

The absorb reads ``S1^`` (immutable: the same for every retry and every
migrator). It writes the merged counters and the marker naming S1 in one
leased ``aitask-stats`` commit. Counters that an older framework writes after
S1 are **residue**: they are stripped with ``Kind: residue`` and never
absorbed (the hard cutover the user accepted).

Recovery never samples a mutable ref. S1 is found by its trailers, scanning
the whole history with no pathspec, because an empty baseline is TREESAME to
its parent and any path-limited log omits it.

Publication
-----------
A marker is published only after it is validated against the task-data history
it claims to cut. ``MarkerGate`` checks every local-only marker, of every
agent, against a validation tip: the pinned O, or our own just-pushed strip.
``model_stats_store.write`` holds unvalidated markers locally for every
ordinary writer, and only this route passes a gate.

Never touches the ``.aitask-data`` worktree, index or local branch ref in remote
mode. The no-remote strip goes through ``aitask_model_stats_strip.sh``
(``ait_cas_rewrite`` plus a path-scoped commit).

Result lines (one status line per agent, plus an optional residue line):

    MIGRATED:<agent>|<S1>|<runs absorbed>
    MIGRATE_NOOP:<agent>|marked
    MIGRATE_SKIPPED:<agent>|no_registry
    MIGRATE_DEFERRED:<agent>|<reason>
    MIGRATE_ERROR:<agent>|<reason>
    MIGRATE_PLAN:<agent>|marker=..|baseline=..|absorb_runs=..|residue_runs=..   (dry run)
    STRIPPED_RESIDUE:<agent>|<runs discarded>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import model_stats_store as mss  # noqa: E402
import orphan_ref_store as ors  # noqa: E402

STRIP_JQ = os.path.join(_LIB, "model_stats_strip.jq")
STRIP_HELPER = os.path.join(os.path.dirname(_LIB), "aitask_model_stats_strip.sh")
TMP_PREFIX = "refs/aitask-stats/migrate-tmp/"
MAX_ATTEMPTS = 8
TRAILER_AGENT = "Stats-Migration-Agent"
TRAILER_KIND = "Stats-Migration-Kind"
TRAILER_ID = "Stats-Migration-Id"
_ID_RE = re.compile(r"[0-9a-f]{32}")
_FMT = ("%H%x00"
        f"%(trailers:key={TRAILER_AGENT},valueonly,separator=%x2C)%x00"
        f"%(trailers:key={TRAILER_KIND},valueonly,separator=%x2C)%x00"
        f"%(trailers:key={TRAILER_ID},valueonly,separator=%x2C)%x1e")


class Deferred(Exception):
    """Nothing was decided for this agent; the next setup/upgrade retries."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = _token(reason)


class Failed(Exception):
    """Fail closed: a state the migration refuses to act on."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = _token(reason)


class MarkerMismatch(Exception):
    """aitask-stats already holds a marker naming another strip commit."""


def _token(text) -> str:
    return " ".join(str(text).split()).replace("|", "/")[:200] or "unknown"


def _hook(point: str, **ctx) -> None:
    """No-op seam: tests replace it in-process to act at a named point
    (``after_pin``, ``before_strip_push``, ``after_strip``, ``before_absorb``)."""


# ================================================================ context

Context = namedtuple("Context", "top data_wt data_branch mode has_remote remote timeout")


def resolve_context(project_root, remote="origin", timeout=None) -> Context:
    """Where task data lives, restating ``_ait_detect_data_worktree``.

    A ``.aitask-data`` worktree at the toplevel ⇒ branch mode (its checked-out
    branch); otherwise legacy mode (the root's checked-out branch). A linked
    worktree without its own ``.aitask-data`` is refused: treating it as legacy
    would cut the strip on that worktree's branch.
    """
    top = ors.toplevel(project_root)
    timeout = mss.default_timeout() if timeout is None else float(timeout)
    wt = Path(top) / ".aitask-data"
    if (wt / ".git").exists():
        if ors.git_common_dir(str(wt)) != ors.git_common_dir(top):
            raise Deferred("unsupported_layout:data_worktree_not_shared")
        data_wt, mode = str(wt), "branch"
    else:
        own = os.path.realpath(ors._out(top, "rev-parse", "--absolute-git-dir"))
        if own != ors.git_common_dir(top):
            raise Deferred("linked_worktree")
        data_wt, mode = top, "legacy"
    proc = ors.git(data_wt, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    branch = proc.stdout.decode().strip()
    if proc.returncode != 0 or not branch:
        raise Deferred("detached_head")
    return Context(top, data_wt, branch, mode,
                   ors.remote_url(top, remote) is not None, remote, timeout)


def registry_path(agent: str) -> str:
    rel = Path(os.environ.get("TASK_DIR", "aitasks"))
    if rel.is_absolute():
        rel = Path("aitasks")
    return f"{rel.as_posix()}/metadata/models_{mss.check_agent(agent)}.json"


def registry_agents(ctx: Context, tip) -> list:
    """Agents with a ``models_<agent>.json`` at ``tip``."""
    prefix = registry_path("x").rsplit("/", 1)[0] + "/"
    out = []
    for path in ors.read_tree(ctx.top, tip):
        if path.startswith(prefix):
            name = path[len(prefix):]
            if name.startswith("models_") and name.endswith(".json"):
                agent = name[len("models_"):-len(".json")]
                if mss.AGENT_RE.fullmatch(agent):
                    out.append(agent)
    return sorted(out)


def discover_agents(ctx: Context, tip) -> list:
    """Every agent with a registry at ``tip``, plus every agent with a baseline
    in ``tip``'s history: a registry deleted after its strip must not orphan the
    strip's counters (the absorb reads them from ``S1^``)."""
    agents = set(registry_agents(ctx, tip))
    agents.update(s.agent for s in scan(ctx.top, tip) if s.kind == "baseline")
    return sorted(agents)


# ================================================================== pure

def _parse_registry(blob):
    try:
        return json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise Failed("malformed_registry") from None


def has_stats(blob) -> bool:
    """Any registry row carries ``usagestats`` / ``verifiedstats`` (any value)."""
    if blob is None:
        return False
    data = _parse_registry(blob)
    rows = data.get("models") if isinstance(data, dict) else None
    return any(isinstance(row, dict) and any(k in row for k in mss.STATS_KEYS)
               for row in (rows if isinstance(rows, list) else []))


def legacy_counters(blob) -> dict:
    return {} if blob is None else mss.registry_counters(_parse_registry(blob))


def count_runs(counters: dict) -> int:
    total = 0
    for row in counters.values():
        for key in mss.STATS_KEYS:
            for entry in (row.get(key) or {}).values():
                at = mss._normalize(entry).get("all_time")
                if isinstance(at, dict):
                    total += mss._num(at.get("runs"))
    return total


def strip_blob(blob: bytes) -> bytes:
    """The registry without its counters, through the shared jq filter."""
    try:
        proc = subprocess.run(["jq", "-f", STRIP_JQ], input=blob,
                              capture_output=True, check=False)
    except FileNotFoundError:
        raise Failed("jq_missing") from None
    if proc.returncode != 0 or not proc.stdout:
        raise Failed("strip_failed:" + proc.stderr.decode("utf-8", "replace"))
    return proc.stdout


def strip_message(agent, kind, mid) -> str:
    return (f"ait: Strip {agent} stats keys from the model registry ({kind})\n\n"
            f"{TRAILER_AGENT}: {agent}\n{TRAILER_KIND}: {kind}\n{TRAILER_ID}: {mid}\n")


# ========================================================== trailer scan

Strip = namedtuple("Strip", "sha agent kind mid")


def _parse_scan(raw: str) -> list:
    out = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x00")
        if len(parts) != 4:
            continue
        sha, agent, kind, mid = (p.strip() for p in parts)
        if (mss.AGENT_RE.fullmatch(agent) and kind in ("baseline", "residue")
                and _ID_RE.fullmatch(mid)):
            out.append(Strip(sha, agent, kind, mid))
    return out


def scan(root, tip) -> list:
    """Every migration strip reachable from ``tip``, oldest first.

    No pathspec: an empty baseline is TREESAME to its parent, so any path
    limit (``--full-history`` included) drops it. ``--grep`` only narrows the
    walk; the parsed trailers decide.
    """
    if tip is None:
        return []
    raw = ors.git(root, "log", "--reverse", "--fixed-strings",
                  f"--grep={TRAILER_AGENT}:", f"--format={_FMT}", tip).stdout
    return _parse_scan(raw.decode("utf-8", "replace"))


def strip_of(root, sha):
    """The ``Strip`` record of one commit, or None (missing object, no trailers)."""
    proc = ors.git(root, "log", "-1", f"--format={_FMT}", sha, check=False)
    if proc.returncode != 0:
        return None
    found = _parse_scan(proc.stdout.decode("utf-8", "replace"))
    return found[0] if found else None


def find_baseline(root, tip, agent):
    for strip in scan(root, tip):
        if strip.agent == agent and strip.kind == "baseline":
            return strip
    return None


def find_by_id(root, tip, agent, mid):
    for strip in scan(root, tip):
        if strip.agent == agent and strip.mid == mid:
            return strip
    return None


def parents(root, sha) -> list:
    return ors._out(root, "rev-list", "--parents", "-n1", sha).split()[1:]


def _reaches(root, a, b) -> bool:
    """``a`` is an ancestor of (or equal to) ``b``; False when unprovable."""
    if not a or not b:
        return False
    try:
        return ors.is_ancestor(root, a, b)
    except ors.GitError:
        return False


# ================================================================ gate

class MarkerGate:
    """Validates every local-only marker before it may be published.

    ``tip`` is the validation tip V: the newest task-data commit known to be on
    origin. That is the pinned O, or our own strip right after its leased push
    succeeded (a fresh S1 is O's child, so validating against the pre-push O
    would reject every first-run absorb). It is kept separate from the absorb
    source ``S1^``, which never changes. Validation is by sha, never by
    migration id: a rebased copy of an offline strip has another parent, so it
    absorbed a different source.
    """

    def __init__(self, ctx: Context, tip):
        self.ctx = ctx
        self.tip = tip

    def check(self, agent, data) -> dict:
        try:
            marker = mss.parse_marker(data)
        except mss.StatsError:
            raise mss.MarkerUnpublishable(agent, "malformed_marker") from None
        if marker["agent"] != agent:
            raise mss.MarkerUnpublishable(agent, "agent_mismatch")
        s1 = marker["strip_commit"]
        strip = strip_of(self.ctx.top, s1)
        valid = (strip is not None and strip.agent == agent and strip.kind == "baseline"
                 and parents(self.ctx.top, s1) == [marker["source_commit"]])
        if valid and _reaches(self.ctx.top, s1, self.tip):
            return marker
        # "Unpublished" only when publishing the local task-data branch would
        # bring the strip to origin: origin's tip is an ancestor of it. An
        # unrelated or diverged origin history means the offline migration
        # absorbed a source origin does not have.
        local_data = ors.resolve(self.ctx.top, f"refs/heads/{self.ctx.data_branch}")
        if (valid and self.ctx.has_remote and _reaches(self.ctx.top, s1, local_data)
                and _reaches(self.ctx.top, self.tip, local_data)):
            raise mss.MarkerUnpublishable(agent, "strip_unpublished")
        raise mss.MarkerUnpublishable(agent, "marker_not_in_source")

    def __call__(self, pending: dict) -> None:
        for agent, data in sorted(pending.items()):
            self.check(agent, data)


def _raise_for(exc: mss.MarkerUnpublishable, blocked_by=None):
    reason = exc.why if blocked_by is None else f"blocked:{blocked_by}:{exc.why}"
    if exc.why == "strip_unpublished":
        raise Deferred(reason)
    raise Failed(reason)


# ============================================================ git: source

def pin_source(ctx: Context):
    """The task-data tip O: origin's (pinned) or, without a remote, local HEAD."""
    if not ctx.has_remote:
        tip = ors.resolve(ctx.data_wt, "HEAD")
        if tip is None:
            raise Deferred("data_branch_unborn")
        return tip
    probe = ors.probe_remote_branch(ctx.top, ctx.data_branch, ctx.timeout, ctx.remote)
    if probe.startswith("ERROR:"):
        raise Deferred("unreachable:" + probe[len("ERROR:"):])
    if probe == "ABSENT":
        raise Deferred("data_branch_absent")
    tip, err = ors.fetch_pinned(ctx.top, ctx.data_branch, ctx.timeout, ctx.remote,
                                tmp_prefix=TMP_PREFIX)
    if err:
        raise Deferred(f"unreachable:{err}")
    return tip


def stats_candidate(ctx: Context):
    """``(T, R)``: the stats tip to trust and origin's tip (read-only).

    T is origin's tip when local is absent or behind it, and local when origin
    is ABSENT or strictly behind. Diverged ⇒ ``Failed``.
    """
    local = ors.resolve(ctx.top, mss.L_REF)
    if not ctx.has_remote:
        return local, None
    probe = ors.probe_remote_branch(ctx.top, mss.BRANCH, ctx.timeout, ctx.remote)
    if probe.startswith("ERROR:"):
        raise Deferred("unreachable:" + probe[len("ERROR:"):])
    if probe == "ABSENT":
        return local, None
    remote_tip, err = ors.fetch_pinned(ctx.top, mss.BRANCH, ctx.timeout, ctx.remote,
                                       tmp_prefix=mss.TMP_PREFIX)
    if err:
        raise Deferred(f"unreachable:{err}")
    if local is None or ors.is_ancestor(ctx.top, local, remote_tip):
        return remote_tip, remote_tip
    if ors.is_ancestor(ctx.top, remote_tip, local):
        return local, remote_tip
    raise Failed("stats_diverged")


def _blob_id(ctx, data: bytes) -> str:
    return ors._out(ctx.top, "hash-object", "--stdin", input=data)


# ============================================================= git: strips

def _push_strip(ctx: Context, base, agent, kind, changes):
    """Leased strip on origin's task-data branch: the commit, or None (CONFLICT)."""
    mid = uuid.uuid4().hex
    commit = ors.build_commit(ctx.top, base, changes, strip_message(agent, kind, mid),
                              ident=mss.IDENT)
    _hook("before_strip_push", agent=agent, kind=kind, base=base, commit=commit)
    status = ors.cas_push(ctx.top, commit, ctx.data_branch, base, ctx.timeout, ctx.remote)
    if status == "CONFLICT":
        return None
    if status != "OK":
        raise Deferred("push:" + (status[len("ERROR:"):] if status.startswith("ERROR:")
                                  else status))
    found = find_by_id(ctx.top, commit, agent, mid)
    if found is None or found.sha != commit:
        raise Failed("strip_not_found")
    return commit


def _check_worktree(ctx: Context, path, blob):
    """No-remote: the worktree file must be the committed blob, or its strip.

    The second form is this migration's own interrupted state: the strip
    rewrote the file, then the process died before its commit. The retry
    resumes it. Anything else is someone's edit ⇒ deferred, never touched.
    """
    try:
        current = (Path(ctx.data_wt) / path).read_bytes()
    except FileNotFoundError:
        current = None
    if current == blob:
        return
    if blob is not None and has_stats(blob) and current == strip_blob(blob):
        return
    raise Deferred("dirty")


def _local_strip(ctx: Context, agent, kind, path, blob):
    """No-remote strip with counters, through the CAS-rewrite + scoped-commit helper.

    The helper prints no sha. The commit is resolved by its unique migration
    id from the new HEAD, so an unrelated commit landing right after the strip
    is never taken for it.
    """
    mid = uuid.uuid4().hex
    with tempfile.NamedTemporaryFile("w", prefix="ait-stats-strip-", suffix=".msg",
                                     delete=False, encoding="utf-8") as fh:
        fh.write(strip_message(agent, kind, mid))
        msg = fh.name
    try:
        proc = subprocess.run(
            ["bash", STRIP_HELPER, "--path", path,
             "--expect-blob", _blob_id(ctx, blob),
             "--expect-stripped-blob", _blob_id(ctx, strip_blob(blob)),
             "--message-file", msg],
            cwd=ctx.top, capture_output=True, text=True, check=False)
    finally:
        os.unlink(msg)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if proc.returncode == 0 and last == "STRIPPED":
        head = ors.resolve(ctx.data_wt, "HEAD")
        found = find_by_id(ctx.top, head, agent, mid)
        if found is None:
            raise Failed("strip_not_found")
        return found.sha
    if last.startswith("STRIP_DEFERRED:"):
        raise Deferred(last[len("STRIP_DEFERRED:"):])
    if proc.returncode < 0:
        raise Deferred(f"strip_interrupted:signal{-proc.returncode}")
    detail = last or proc.stderr.strip().splitlines()[-1:] or [f"exit {proc.returncode}"]
    raise Failed(f"strip_helper:{detail if isinstance(detail, str) else detail[0]}")


def _local_empty_baseline(ctx: Context, base, agent):
    """No-remote empty baseline: commit-tree on HEAD's tree + CAS the branch.

    The tree is identical, so the checked-out worktree and index stay
    consistent with the new HEAD by construction. Returns the commit or None.
    """
    mid = uuid.uuid4().hex
    env = ors._commit_env(ctx.top, ident=mss.IDENT)
    commit = ors.git(ctx.top, "commit-tree", ors.tree_of(ctx.top, base), "-p", base,
                     input=strip_message(agent, "baseline", mid).encode(),
                     env=env).stdout.decode().strip()
    if ors.cas_local(ctx.top, f"refs/heads/{ctx.data_branch}", commit, base) != "OK":
        return None
    return commit


# ============================================================ the protocol

def _absorb(ctx: Context, agent, s1, gate):
    """Absorb ``S1^`` + write the marker in one leased stats commit.

    Returns ``("migrated", runs)`` or ``("noop", 0)``.
    """
    path = registry_path(agent)
    (source,) = parents(ctx.top, s1)
    blob = ors.read_file(ctx.top, source, path)
    legacy = legacy_counters(blob)
    runs = count_runs(legacy)
    marker = mss.marker_blob(
        agent=agent, migration_id=strip_of(ctx.top, s1).mid, strip_commit=s1,
        source_commit=source,
        source_blob=None if blob is None else _blob_id(ctx, blob),
        absorbed_runs=runs,
        absorbed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def render(read):
        existing = read(mss.marker_path(agent))
        if existing is not None:
            try:
                named = mss.parse_marker(existing)["strip_commit"]
            except mss.StatsError:
                raise MarkerMismatch() from None
            if named == s1:
                return None, ("noop", 0)
            raise MarkerMismatch()
        models = mss.parse_blob(read(mss.agent_path(agent)))["models"]
        merged = mss.absorb_models(legacy, models)
        return ({mss.agent_path(agent): mss.render_blob({"schema": mss.SCHEMA,
                                                         "models": merged}),
                 mss.marker_path(agent): marker},
                ("migrated", runs))

    res = mss.write(ctx.top, render, timeout=ctx.timeout, remote=ctx.remote,
                    message=f"ait: Absorb {agent} legacy stats (migration {s1[:12]})",
                    marker_gate=gate)
    return res.value


def _residue(ctx: Context, agent, gate) -> int:
    """Strip counters an older framework wrote after the baseline; never absorb."""
    path = registry_path(agent)
    for attempt in range(MAX_ATTEMPTS):
        mss._jitter(attempt)
        tip = pin_source(ctx)
        gate.tip = tip
        blob = ors.read_file(ctx.top, tip, path)
        if not has_stats(blob):
            return 0
        runs = count_runs(legacy_counters(blob))
        if ctx.has_remote:
            commit = _push_strip(ctx, tip, agent, "residue", {path: strip_blob(blob)})
            if commit is None:
                continue
            gate.tip = commit
        else:
            _check_worktree(ctx, path, blob)
            gate.tip = _local_strip(ctx, agent, "residue", path, blob)
        return runs
    raise Deferred("contended")


def _plan_line(agent, marker, baseline, absorb_runs, residue_runs) -> str:
    return (f"MIGRATE_PLAN:{agent}|marker={'yes' if marker else 'no'}"
            f"|baseline={baseline or 'none'}|absorb_runs={absorb_runs}"
            f"|residue_runs={residue_runs}")


def migrate_agent(ctx: Context, agent, dry_run=False) -> list:
    """Run the per-agent protocol; return its result lines."""
    path = registry_path(agent)
    gate = MarkerGate(ctx, None)
    for attempt in range(MAX_ATTEMPTS):
        mss._jitter(attempt)
        # 1. Pin the source.
        tip = pin_source(ctx)
        gate.tip = tip
        blob = ors.read_file(ctx.top, tip, path)
        _hook("after_pin", agent=agent, tip=tip, attempt=attempt)

        # 2. Reconcile the stats ref before trusting a marker.
        stats_tip, _remote_stats = stats_candidate(ctx)
        marker = ors.read_file(ctx.top, stats_tip, mss.marker_path(agent)) if stats_tip else None
        if marker is not None:
            # A published marker's strip reached the task-data branch before
            # the marker reached aitask-stats, so a source pinned AFTER reading
            # the marker contains it; the pin above may predate a concurrent
            # migrator's strip. Re-pin, then validate against the fresh tip.
            tip = pin_source(ctx)
            gate.tip = tip
            blob = ors.read_file(ctx.top, tip, path)
            try:
                gate.check(agent, marker)
            except mss.MarkerUnpublishable as exc:
                _raise_for(exc)
            residue_runs = count_runs(legacy_counters(blob)) if has_stats(blob) else 0
            if dry_run:
                return [_plan_line(agent, True, mss.parse_marker(marker)["strip_commit"],
                                   0, residue_runs)]
            if ctx.has_remote:
                try:
                    shared = mss.publish(ctx.top, marker_gate=gate, timeout=ctx.timeout,
                                         remote=ctx.remote)
                except mss.MarkerUnpublishable as exc:
                    _raise_for(exc)
                if shared != stats_tip:
                    again = ors.read_file(ctx.top, shared, mss.marker_path(agent))
                    if again != marker:
                        try:
                            gate.check(agent, again)
                        except mss.MarkerUnpublishable:
                            continue  # a concurrent migrator's newer state: re-pin
            lines = [f"MIGRATE_NOOP:{agent}|marked"]
            runs = _residue(ctx, agent, gate)
            if runs:
                lines.append(f"STRIPPED_RESIDUE:{agent}|{runs}")
            return lines

        # 3. Find or cut the baseline: the trailer scan runs before B's keys
        #    are looked at (or even B's existence), so neither reappeared
        #    counters nor a registry deleted after the strip ever hide a
        #    pending baseline: its counters are recovered from S1^.
        found = find_baseline(ctx.top, tip, agent)
        if found is None and blob is None:
            return [f"MIGRATE_SKIPPED:{agent}|no_registry"]
        if found is not None:
            s1 = found.sha
        else:
            if dry_run:
                return [_plan_line(agent, False, None, count_runs(legacy_counters(blob)), 0)]
            counters = has_stats(blob)
            if ctx.has_remote:
                changes = {path: strip_blob(blob)} if counters else {}
                s1 = _push_strip(ctx, tip, agent, "baseline", changes)
                if s1 is None:
                    continue  # the lease lost: origin moved; re-pin and re-scan
            else:
                _check_worktree(ctx, path, blob)
                if counters:
                    s1 = _local_strip(ctx, agent, "baseline", path, blob)
                else:
                    s1 = _local_empty_baseline(ctx, tip, agent)
                    if s1 is None:
                        continue
                # The oldest baseline wins, whoever cut it.
                head = ors.resolve(ctx.data_wt, "HEAD")
                oldest = find_baseline(ctx.top, head, agent)
                s1 = oldest.sha if oldest is not None else s1
            gate.tip = s1
            _hook("after_strip", agent=agent, strip=s1)
        if len(parents(ctx.top, s1)) != 1:
            raise Failed("bad_baseline")
        if dry_run:
            (source,) = parents(ctx.top, s1)
            absorb = count_runs(legacy_counters(ors.read_file(ctx.top, source, path)))
            residue_runs = count_runs(legacy_counters(blob)) if has_stats(blob) else 0
            return [_plan_line(agent, False, s1, absorb, residue_runs)]

        # 4. Absorb S1^ + marker, one leased stats commit.
        _hook("before_absorb", agent=agent, strip=s1)
        try:
            outcome, runs = _absorb(ctx, agent, s1, gate)
        except MarkerMismatch:
            raise Failed("marker_mismatch") from None
        except mss.MarkerUnpublishable as exc:
            _raise_for(exc)
        except mss.StatsDiverged:
            raise Failed("stats_diverged") from None
        except mss.StatsError as exc:
            raise Deferred(f"stats:{exc.reason}") from None
        lines = ([f"MIGRATED:{agent}|{s1}|{runs}"] if outcome == "migrated"
                 else [f"MIGRATE_NOOP:{agent}|marked"])

        # 5. Residue.
        residue = _residue(ctx, agent, gate)
        if residue:
            lines.append(f"STRIPPED_RESIDUE:{agent}|{residue}")
        return lines
    raise Deferred("contended")


def migrate(project_root, agent=None, *, dry_run=False, remote="origin", timeout=None) -> list:
    """Migrate one agent or every agent with a registry; return the result lines."""
    label = agent or "all"
    try:
        ctx = resolve_context(project_root, remote=remote, timeout=timeout)
        # Global pre-check: every local-only marker, of every agent, must be
        # publishable before any agent cuts a baseline. Otherwise a later
        # absorb would push another agent's unpublishable marker, after its
        # own baseline already left the registry stripped on origin. The stats
        # side is read first and the source pinned after it, so any strip a
        # read marker names is already in the pinned source.
        stats_tip, remote_stats = stats_candidate(ctx)
        tip = pin_source(ctx)
        agents = [mss.check_agent(agent)] if agent else discover_agents(ctx, tip)
        pending = (mss.unpublished_markers(ctx.top, stats_tip, remote_stats)
                   if stats_tip and stats_tip != remote_stats else {})
        gate = MarkerGate(ctx, tip)
        for bad, data in sorted(pending.items()):
            try:
                gate.check(bad, data)
            except mss.MarkerUnpublishable as exc:
                kind = "DEFERRED" if exc.why == "strip_unpublished" else "ERROR"
                _diagnose(bad, exc.why)
                return [f"MIGRATE_{kind}:{a}|blocked:{bad}:{exc.why}" for a in agents or [label]]
    except Deferred as exc:
        return [f"MIGRATE_DEFERRED:{label}|{exc.reason}"]
    except Failed as exc:
        return [f"MIGRATE_ERROR:{label}|{exc.reason}"]
    except (mss.StatsError, ors.GitError, OSError) as exc:
        return [f"MIGRATE_ERROR:{label}|{_token(getattr(exc, 'reason', exc))}"]

    lines = []
    for name in agents:
        try:
            lines += migrate_agent(ctx, name, dry_run=dry_run)
        except Deferred as exc:
            lines.append(f"MIGRATE_DEFERRED:{name}|{exc.reason}")
        except Failed as exc:
            if exc.reason.startswith("marker_not_in_source"):
                _diagnose(name, "marker_not_in_source")
            lines.append(f"MIGRATE_ERROR:{name}|{exc.reason}")
        except (mss.StatsError, ors.GitError, OSError) as exc:
            lines.append(f"MIGRATE_ERROR:{name}|{_token(getattr(exc, 'reason', exc))}")
    return lines


def _diagnose(agent, why) -> None:
    text = {
        "marker_not_in_source": (
            f"the local {mss.L_REF} holds a migration marker for {agent} whose strip "
            "commit is not in origin's task-data history: an offline migration "
            "absorbed a registry that origin does not contain. Nothing was "
            "published, and nothing is repaired automatically. KEEP the local "
            f"{mss.L_REF} history: besides the offline migration it can hold "
            "counter writes recorded locally since then (held, not published), "
            "which exist nowhere else - discarding or resetting it loses them. "
            "A manual repair has to preserve the local history (e.g. back it up "
            "under another ref), account for every counter written after the "
            "offline marker, and only then redo the migration against origin's "
            "registry history; a plain reset followed by a re-run is NOT "
            "lossless."),
        "strip_unpublished": (
            f"the local {mss.L_REF} holds a migration marker for {agent} whose strip "
            "is only on the local task-data branch. Publish the task data first "
            "('./ait sync'), then re-run the migration."),
    }.get(why)
    if text:
        try:
            sys.stderr.write(f"model-stats migrate: {text}\n")
        except Exception:  # noqa: BLE001 - reporting only
            pass
