#!/usr/bin/env python3
"""model_stats_store.py - code-agent usage/verified counters on ``aitask-stats``.

The counters (``usagestats`` / ``verifiedstats``) used to live inside
``aitasks/metadata/models_<agent>.json`` on the task-data branch, and every
write fetched, rebased and pushed the shared ``.aitask-data`` worktree. This
store keeps them on a plumbing-only orphan branch instead (t1912). It is built
on ``orphan_ref_store``: trees go through a private ``GIT_INDEX_FILE``, so a
write never touches any worktree, index or HEAD.

Layout (schema 1)
-----------------
``<agent>.json``            ``{"schema": 1, "models": {"<model>": {"usagestats":
                            {...}, "verifiedstats": {...}}}}`` in the writers'
                            exact bucket shape (``all_time`` / ``prev_month`` /
                            ``month`` / ``week``, ``period`` stamps ``%Y-%m`` and
                            ISO ``%G-W%V``).
``migrations/<agent>.json``  the per-agent cutover marker (content: t1912_5).
                            Present => readers use the branch only; absent =>
                            legacy file counters + branch counters.

Refs
----
``refs/heads/aitask-stats`` is the one ref readers read, and only this module
moves it, always fast-forward. ``refs/remotes/origin/aitask-stats`` is never
consulted: it exists only when ``remote.origin.fetch`` maps it, and
single-branch clones or a negative ``^refs/heads/...`` refspec leave it missing
or stale. Fetches go through ``fetch_pinned`` (explicit refspec into a private
temp ref), so they do not depend on the configured refspecs either.

Layers
------
- pure: ``bump_usage``, ``record_verified`` (ports of the jq renderers in
  ``aitask_usage_update.sh`` / ``aitask_verified_update.sh``), ``merge_buckets``,
  ``merge_stats``, ``parse_blob`` / ``render_blob``;
- write: ``update`` (read-modify-write recomputed on the origin tip on every
  retry; leased push; fast-forward of the local ref);
- ``refresh`` (best-effort fast-forward of the local ref from origin);
- loader: ``load_agent_stats`` / ``load_all_stats`` (never fetch).

Standard library only.
"""
from __future__ import annotations

import copy
import json
import math
import os
import random
import re
import sys
import time
import uuid
from collections import OrderedDict
from datetime import date
from pathlib import Path

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import orphan_ref_store as ors  # noqa: E402
from model_stats_windows import current_periods  # noqa: E402

BRANCH = "aitask-stats"
L_REF = f"refs/heads/{BRANCH}"
TMP_PREFIX = "refs/aitask-stats/tmp/"
IDENT = {
    "GIT_AUTHOR_NAME": "ait stats",
    "GIT_AUTHOR_EMAIL": "ait-stats@localhost",
    "GIT_COMMITTER_NAME": "ait stats",
    "GIT_COMMITTER_EMAIL": "ait-stats@localhost",
}
SCHEMA = 1
MAX_ATTEMPTS = 8
DEFAULT_TIMEOUT = 10.0
STATS_KEYS = ("usagestats", "verifiedstats")
MIGRATIONS_DIR = "migrations"

AGENT_RE = re.compile(r"[a-z][a-z0-9]*")
_MONTH_RE = re.compile(r"(\d{4})-(\d{2})")


class StatsError(RuntimeError):
    """A store operation failed; ``reason`` is a single-line token."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason.replace("\n", " ").replace("|", "/")[:200]


class StatsDiverged(StatsError):
    """Local and origin ``aitask-stats`` have diverged; nothing was written."""

    def __init__(self, local: str, remote: str):
        super().__init__(f"diverged:{local}|{remote}")
        self.local = local
        self.remote = remote


def _test_hook(point: str, **ctx) -> None:
    """No-op seam: tests replace it to act at a named point."""


def default_timeout() -> float:
    try:
        return float(os.environ.get("AIT_STATS_FETCH_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        return DEFAULT_TIMEOUT


def check_agent(agent: str) -> str:
    if not isinstance(agent, str) or not AGENT_RE.fullmatch(agent):
        raise StatsError(f"invalid_agent:{agent!r}")
    return agent


def agent_path(agent: str) -> str:
    return f"{check_agent(agent)}.json"


def marker_path(agent: str) -> str:
    return f"{MIGRATIONS_DIR}/{check_agent(agent)}.json"


# ====================================================================== pure

def _field(obj, key):
    """jq ``.key``: null on null, the value on an object, an error otherwise."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    raise StatsError("malformed_bucket")


def _add(a, b):
    """jq ``a + b`` for numbers, where null is the identity."""
    if a is None:
        return b
    if b is None:
        return a
    if isinstance(a, bool) or isinstance(b, bool) or \
            not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise StatsError("malformed_count")
    return a + b


def _jq_round(x) -> int:
    """jq ``round``: half away from zero (Python's ``round`` is half-even)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def empty_blob() -> dict:
    return {"schema": SCHEMA, "models": {}}


def parse_blob(data) -> dict:
    """The blob at ``<agent>.json`` (bytes or None) as a dict."""
    if data is None:
        return empty_blob()
    try:
        obj = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise StatsError(f"malformed_blob:{exc}") from None
    if not isinstance(obj, dict):
        raise StatsError("malformed_blob:not an object")
    if obj.get("schema") != SCHEMA:
        raise StatsError(f"unsupported_schema:{obj.get('schema')!r}")
    if not isinstance(obj.get("models"), dict):
        raise StatsError("malformed_blob:models")
    return obj


def render_blob(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _stats_map(blob: dict, model: str, key: str) -> dict:
    """``blob.models[model][key]`` (created when absent), jq ``// {}`` style."""
    models = blob.setdefault("models", {})
    entry = models.get(model)
    if entry is None:
        entry = models[model] = {}
    if not isinstance(entry, dict):
        raise StatsError("malformed_model_entry")
    stats = entry.get(key)
    if stats is None or stats is False:
        stats = entry[key] = {}
    if not isinstance(stats, dict):
        raise StatsError(f"malformed_{key}")
    return stats


def bump_usage(blob: dict, model: str, skill: str, today: date):
    """One usage run; returns ``(new_blob, month_runs)``.

    Port of ``render_usage_bump`` (``aitask_usage_update.sh``). The input is not
    mutated.
    """
    p = current_periods(today)
    blob = copy.deepcopy(blob)
    stats = _stats_map(blob, model, "usagestats")
    existing = stats.get(skill)
    if isinstance(existing, dict) and "all_time" in existing:
        base = dict(existing)
        if base.get("prev_month") is None or base.get("prev_month") is False:
            base["prev_month"] = {"period": "", "runs": 0}
    else:
        base = {
            "all_time": {"runs": 0},
            "prev_month": {"period": "", "runs": 0},
            "month": {"period": p.month, "runs": 0},
            "week": {"period": p.week, "runs": 0},
        }
    at_runs = _add(_field(base.get("all_time"), "runs"), 1)
    month_period = _field(base.get("month"), "period")
    if month_period == p.month:
        pm = base.get("prev_month")
    elif month_period == p.prev_month:
        pm = base.get("month")
    else:
        pm = {"period": "", "runs": 0}
    m_runs = _add(_field(base.get("month"), "runs"), 1) if month_period == p.month else 1
    w_runs = (_add(_field(base.get("week"), "runs"), 1)
              if _field(base.get("week"), "period") == p.week else 1)
    stats[skill] = {
        "all_time": {"runs": at_runs},
        "prev_month": copy.deepcopy(pm),
        "month": {"period": p.month, "runs": m_runs},
        "week": {"period": p.week, "runs": w_runs},
    }
    return blob, m_runs


def record_verified(blob: dict, model: str, skill: str, score_100, today: date):
    """One verified score (already mapped: raw 1-5 x 20); returns
    ``(new_blob, all_time_average)``.

    Port of ``render_verified_update`` (``aitask_verified_update.sh``) without
    its ``verified[skill]`` write: ``verified`` stays a registry prior on the
    task-data branch (t1912 decision 4). The input is not mutated.
    """
    if isinstance(score_100, bool) or not isinstance(score_100, (int, float)):
        raise StatsError("malformed_score")
    p = current_periods(today)
    blob = copy.deepcopy(blob)
    stats = _stats_map(blob, model, "verifiedstats")
    existing = stats.get(skill)
    if isinstance(existing, dict) and "runs" in existing and "all_time" not in existing:
        # The old flat format, migrated to buckets.
        base = {
            "all_time": {"runs": existing.get("runs"), "score_sum": existing.get("score_sum")},
            "prev_month": {"period": "", "runs": 0, "score_sum": 0},
            "month": {"period": p.month, "runs": 0, "score_sum": 0},
            "week": {"period": p.week, "runs": 0, "score_sum": 0},
        }
    elif isinstance(existing, dict) and "all_time" in existing:
        base = dict(existing)
        if base.get("prev_month") is None or base.get("prev_month") is False:
            base["prev_month"] = {"period": "", "runs": 0, "score_sum": 0}
    else:
        base = {
            "all_time": {"runs": 0, "score_sum": 0},
            "prev_month": {"period": "", "runs": 0, "score_sum": 0},
            "month": {"period": p.month, "runs": 0, "score_sum": 0},
            "week": {"period": p.week, "runs": 0, "score_sum": 0},
        }
    at = base.get("all_time")
    at_runs = _add(_field(at, "runs"), 1)
    at_sum = _add(_field(at, "score_sum"), score_100)
    month = base.get("month")
    week = base.get("week")
    month_period = _field(month, "period")
    if month_period == p.month:
        pm = base.get("prev_month")
    elif month_period == p.prev_month:
        pm = month
    else:
        pm = {"period": "", "runs": 0, "score_sum": 0}
    same_month = month_period == p.month
    same_week = _field(week, "period") == p.week
    m_runs = _add(_field(month, "runs"), 1) if same_month else 1
    m_sum = _add(_field(month, "score_sum"), score_100) if same_month else score_100
    w_runs = _add(_field(week, "runs"), 1) if same_week else 1
    w_sum = _add(_field(week, "score_sum"), score_100) if same_week else score_100
    stats[skill] = {
        "all_time": {"runs": at_runs, "score_sum": at_sum},
        "prev_month": copy.deepcopy(pm),
        "month": {"period": p.month, "runs": m_runs, "score_sum": m_sum},
        "week": {"period": p.week, "runs": w_runs, "score_sum": w_sum},
    }
    if not at_runs:
        raise StatsError("malformed_count")
    return blob, _jq_round(at_sum / at_runs)


# ----------------------------------------------------------------- merging

def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return value


def _normalize(entry):
    """A skill entry as buckets; the flat ``{runs, score_sum}`` -> all_time only."""
    if not isinstance(entry, dict):
        return {}
    if "all_time" not in entry and "runs" in entry:
        at = {"runs": entry.get("runs")}
        if "score_sum" in entry:
            at["score_sum"] = entry.get("score_sum")
        return {"all_time": at}
    return entry


def _is_scored(*entries) -> bool:
    for entry in entries:
        for bucket in entry.values():
            if isinstance(bucket, dict) and "score_sum" in bucket:
                return True
    return False


def _bucket(period, runs, score_sum, scored):
    out = {"period": period, "runs": runs}
    if scored:
        out["score_sum"] = score_sum
    return out


def _previous_month(period: str):
    m = _MONTH_RE.fullmatch(period or "")
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def merge_buckets(a, b) -> dict:
    """The sum of two skill entries (legacy overlay / migration absorb).

    - ``all_time`` adds;
    - ``month`` + ``prev_month`` of both sides are summed per period, then
      re-slotted around the newest period: ``month`` is the newest,
      ``prev_month`` the calendar month before it (empty when neither side has
      it);
    - ``week``: equal periods sum, otherwise the newer period wins.
    A flat ``{runs, score_sum}`` side contributes to ``all_time`` only.
    """
    a, b = _normalize(a), _normalize(b)
    scored = _is_scored(a, b)
    at_a, at_b = a.get("all_time") or {}, b.get("all_time") or {}
    if not isinstance(at_a, dict):
        at_a = {}
    if not isinstance(at_b, dict):
        at_b = {}
    all_time = {"runs": _num(at_a.get("runs")) + _num(at_b.get("runs"))}
    if scored:
        all_time["score_sum"] = _num(at_a.get("score_sum")) + _num(at_b.get("score_sum"))

    months: dict = {}
    for side in (a, b):
        for slot in ("month", "prev_month"):
            bucket = side.get(slot)
            if not isinstance(bucket, dict):
                continue
            period = bucket.get("period")
            if not isinstance(period, str) or not period:
                continue
            acc = months.setdefault(period, [0, 0])
            acc[0] += _num(bucket.get("runs"))
            acc[1] += _num(bucket.get("score_sum"))
    if months:
        newest = max(months)
        month = _bucket(newest, months[newest][0], months[newest][1], scored)
        prev = _previous_month(newest)
        if prev is not None and prev in months:
            prev_month = _bucket(prev, months[prev][0], months[prev][1], scored)
        else:
            prev_month = _bucket("", 0, 0, scored)
    else:
        month = _bucket("", 0, 0, scored)
        prev_month = _bucket("", 0, 0, scored)

    weeks = []
    for side in (a, b):
        bucket = side.get("week")
        if isinstance(bucket, dict) and isinstance(bucket.get("period"), str) \
                and bucket.get("period"):
            weeks.append(bucket)
    if not weeks:
        week = _bucket("", 0, 0, scored)
    else:
        newest = max(w["period"] for w in weeks)
        same = [w for w in weeks if w["period"] == newest]
        week = _bucket(newest, sum(_num(w.get("runs")) for w in same),
                       sum(_num(w.get("score_sum")) for w in same), scored)
    return {"all_time": all_time, "prev_month": prev_month, "month": month,
            "week": week}


def merge_stats(legacy: dict, branch: dict) -> dict:
    """Effective ``{model: {stats_key: {skill: entry}}}`` from both sources.

    A skill present on one side only is that side's entry unchanged (a deep
    copy), so the effective values equal today's file values while the branch
    holds nothing for it. Both sides => ``merge_buckets``.
    """
    out: dict = {}
    for model in sorted(set(legacy) | set(branch)):
        lrow = legacy.get(model) if isinstance(legacy.get(model), dict) else {}
        brow = branch.get(model) if isinstance(branch.get(model), dict) else {}
        row = {}
        for key in STATS_KEYS:
            if key not in lrow and key not in brow:
                continue
            lstats = lrow.get(key) if isinstance(lrow.get(key), dict) else {}
            bstats = brow.get(key) if isinstance(brow.get(key), dict) else {}
            merged = {}
            for skill in sorted(set(lstats) | set(bstats)):
                if skill in lstats and skill in bstats:
                    merged[skill] = merge_buckets(lstats[skill], bstats[skill])
                else:
                    merged[skill] = copy.deepcopy(
                        lstats[skill] if skill in lstats else bstats[skill])
            row[key] = merged
        out[model] = row
    return out


# =============================================================== git: write

def _jitter(attempt: int) -> None:
    if attempt:
        time.sleep(random.uniform(0.05, 0.4) * attempt)


def update(project_root, agent, fn, *, timeout=None, message=None, remote="origin"):
    """Read-modify-write ``<agent>.json``; return ``fn``'s value.

    ``fn(blob) -> (new_blob, value)`` runs on the blob read from the base it
    will be committed on, and again from the re-read tip after every lost race.
    Raises ``StatsError`` (``StatsDiverged`` when local and origin diverged).
    """
    path = agent_path(agent)
    root = ors.toplevel(project_root)
    timeout = default_timeout() if timeout is None else float(timeout)
    message = message or f"ait: Update {agent} stats"
    has_remote = ors.remote_url(root, remote) is not None
    last = "contended"
    for attempt in range(MAX_ATTEMPTS):
        _jitter(attempt)
        local = ors.resolve(root, L_REF)
        if not has_remote:
            value, commit = _render(root, local, path, fn, message)
            _test_hook("after_render", attempt=attempt, base=local, commit=commit)
            if ors.cas_local(root, L_REF, commit, local) == "OK":
                return value
            last = "local_conflict"
            continue

        probe = ors.probe_remote_branch(root, BRANCH, timeout, remote)
        if probe.startswith("ERROR:"):
            raise StatsError(f"unreachable:{probe[len('ERROR:'):]}")
        remote_tip = None
        if probe == "ABSENT":
            # Local-only history (or nothing) becomes the base: one push both
            # publishes it and lands this write.
            base = local
        else:
            remote_tip, err = ors.fetch_pinned(root, BRANCH, timeout, remote,
                                               tmp_prefix=TMP_PREFIX)
            if err:
                raise StatsError(f"unreachable:{err}")
            if local is None or ors.is_ancestor(root, local, remote_tip):
                base = remote_tip
            elif ors.is_ancestor(root, remote_tip, local):
                base = local  # local strictly ahead: a fast-forward loses nothing
            else:
                raise StatsDiverged(local, remote_tip)
        _test_hook("after_pin", attempt=attempt, base=base, remote=remote_tip)
        value, commit = _render(root, base, path, fn, message)
        status = ors.cas_push(root, commit, BRANCH, remote_tip, timeout, remote)
        _test_hook("after_push", attempt=attempt, status=status, commit=commit)
        if status == "CONFLICT":
            last = "contended"
            continue
        if status != "OK":
            raise StatsError(status[len("ERROR:"):] if status.startswith("ERROR:") else status)
        outcome = ors.advance_ref(root, L_REF, commit)
        if outcome == "DIVERGED":
            sys.stderr.write(f"model_stats_store: pushed {commit[:12]} but {L_REF} "
                             "could not be fast-forwarded to it\n")
        return value
    raise StatsError(last)


def _render(root, base, path, fn, message):
    blob = parse_blob(ors.read_file(root, base, path) if base else None)
    new_blob, value = fn(blob)
    # The write id makes every commit unique. Without it, two writers that
    # pinned the same tip and computed the same increment (same identity, same
    # second) build byte-identical commits; the second leased push then reports
    # "up to date" as success and one increment is silently lost.
    message = f"{message}\n\nStats-Write-Id: {uuid.uuid4().hex}\n"
    commit = ors.build_commit(root, base, {path: render_blob(new_blob)}, message,
                              ident=IDENT)
    return value, commit


# ============================================================= git: refresh

def refresh(project_root, timeout=None, remote="origin"):
    """Fast-forward ``refs/heads/aitask-stats`` from origin; never raises.

    Returns ``(kind, detail)``: ``("refreshed", <sha>)``, ``("skipped",
    <reason>)`` or ``("diverged", "<local>|<remote>")`` (the ref is not moved).
    """
    try:
        root = ors.toplevel(project_root)
        timeout = default_timeout() if timeout is None else float(timeout)
        if ors.remote_url(root, remote) is None:
            return ("skipped", "no_remote")
        probe = ors.probe_remote_branch(root, BRANCH, timeout, remote)
        if probe.startswith("ERROR:"):
            return ("skipped", f"unreachable:{probe[len('ERROR:'):]}")
        if probe == "ABSENT":
            return ("skipped", "absent")
        remote_tip, err = ors.fetch_pinned(root, BRANCH, timeout, remote,
                                           tmp_prefix=TMP_PREFIX)
        if err:
            return ("skipped", f"unreachable:{err}")
        local = ors.resolve(root, L_REF)
        if local is None or ors.is_ancestor(root, local, remote_tip):
            outcome = ors.advance_ref(root, L_REF, remote_tip)
            if outcome == "DIVERGED":
                now = ors.resolve(root, L_REF) or ""
                return ("diverged", f"{now}|{remote_tip}")
            return ("refreshed", ors.resolve(root, L_REF) or remote_tip)
        if ors.is_ancestor(root, remote_tip, local):
            return ("refreshed", local)
        return ("diverged", f"{local}|{remote_tip}")
    except Exception as exc:  # noqa: BLE001 - best-effort by contract
        reason = str(exc).replace("\n", " ").replace("|", "/")[:200]
        return ("skipped", f"error:{reason}")


# ================================================================== loader

_CACHE_MAX = 16
_branch_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_layout_cache: dict = {}
_reported: set = set()


def _layout(project_root):
    """``(toplevel, realpath(common dir))`` of a project.

    Cached per realpath(project_root): it describes the repository's structure,
    not its content; the content key is the commit sha below.
    """
    key = os.path.realpath(str(project_root))
    hit = _layout_cache.get(key)
    if hit is None:
        top = ors.toplevel(project_root)
        hit = (top, ors.git_common_dir(top))
        _layout_cache[key] = hit
    return hit


def _parse_branch(files: dict) -> dict:
    agents: dict = {}
    markers: set = set()
    for path, data in files.items():
        if path.startswith(MIGRATIONS_DIR + "/") and path.endswith(".json"):
            name = path[len(MIGRATIONS_DIR) + 1:-len(".json")]
            if AGENT_RE.fullmatch(name):
                markers.add(name)
            continue
        if "/" in path or not path.endswith(".json"):
            continue
        name = path[:-len(".json")]
        if not AGENT_RE.fullmatch(name):
            continue
        try:
            agents[name] = parse_blob(data)["models"]
        except StatsError as exc:
            sys.stderr.write(f"model_stats_store: ignoring {path}: {exc.reason}\n")
    return {"agents": agents, "markers": frozenset(markers)}


_EMPTY_BRANCH = {"agents": {}, "markers": frozenset()}


def _branch_content(project_root) -> dict:
    """Parsed branch content at the current local ref (never fetches).

    Only this immutable parse is cached, keyed by (common dir, commit sha). A
    git failure reads as no branch content and is reported once per project.
    """
    try:
        top, common = _layout(project_root)
        sha = ors.resolve(top, L_REF)
        if sha is None:
            return _EMPTY_BRANCH
        key = (common, sha)
        hit = _branch_cache.get(key)
        if hit is not None:
            _branch_cache.move_to_end(key)
            return hit
        parsed = _parse_branch(ors.read_files(top, sha))
        _branch_cache[key] = parsed
        while len(_branch_cache) > _CACHE_MAX:
            _branch_cache.popitem(last=False)
        return parsed
    except (ors.GitError, OSError) as exc:
        where = os.path.realpath(str(project_root))
        if where not in _reported:
            _reported.add(where)
            sys.stderr.write(f"model_stats_store: stats branch unreadable in {where}: {exc}\n")
        return _EMPTY_BRANCH


def metadata_dir(project_root, metadata_path=None) -> Path:
    """Where ``models_<agent>.json`` lives for ``project_root``.

    Same rule as ``config_utils.load_all_models`` (which imports yaml, so it is
    restated here): ``metadata_path`` is used verbatim (cross-repo callers); else
    ``<root>/<TASK_DIR>/metadata``, where an ABSOLUTE ``TASK_DIR`` falls back to
    ``aitasks`` — ``root / abs`` would silently discard the root and read
    another project's counters.
    """
    if metadata_path is not None:
        return Path(metadata_path)
    rel = Path(os.environ.get("TASK_DIR", "aitasks"))
    if rel.is_absolute():
        rel = Path("aitasks")
    return Path(project_root) / rel / "metadata"


def legacy_models(project_root, agent, metadata_path=None) -> dict:
    """``{model: {stats_key: ...}}`` from ``models_<agent>.json`` (read now)."""
    path = metadata_dir(project_root, metadata_path) / f"models_{check_agent(agent)}.json"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    rows = data.get("models") if isinstance(data, dict) else None
    out: dict = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            continue
        stats = {k: row[k] for k in STATS_KEYS if isinstance(row.get(k), dict)}
        if stats:
            out[row["name"]] = copy.deepcopy(stats)
    return out


def load_agent_stats(project_root, agent, *, metadata_path=None) -> dict:
    """Effective ``{model: {"usagestats": ..., "verifiedstats": ...}}``.

    Marker present => the branch only; absent => legacy file + branch. The
    legacy file and the merge are recomputed on every call; the result is a new
    object every time.
    """
    check_agent(agent)
    content = _branch_content(project_root)
    branch = content["agents"].get(agent, {})
    if agent in content["markers"]:
        return merge_stats({}, branch)
    return merge_stats(legacy_models(project_root, agent, metadata_path), branch)


def load_all_stats(project_root, *, metadata_path=None) -> dict:
    """``{agent: load_agent_stats(...)}`` over branch agents and models_*.json."""
    content = _branch_content(project_root)
    agents = set(content["agents"]) | set(content["markers"])
    meta = metadata_dir(project_root, metadata_path)
    try:
        for entry in os.listdir(meta):
            if entry.startswith("models_") and entry.endswith(".json"):
                name = entry[len("models_"):-len(".json")]
                if AGENT_RE.fullmatch(name):
                    agents.add(name)
    except OSError:
        pass
    return {agent: load_agent_stats(project_root, agent, metadata_path=metadata_path)
            for agent in sorted(agents)}


def branch_state(project_root) -> dict:
    """``{"sha": <sha|None>, "markers": [...]}`` of the local stats ref."""
    try:
        top, _ = _layout(project_root)
        sha = ors.resolve(top, L_REF)
    except (ors.GitError, OSError):
        sha = None
    content = _branch_content(project_root)
    return {"sha": sha, "markers": sorted(content["markers"])}
