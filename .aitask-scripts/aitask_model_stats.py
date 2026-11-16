#!/usr/bin/env python3
"""aitask_model_stats.py - CLI over lib/model_stats_store.py (the aitask-stats branch).

Verbs (single-line structured stdout, diagnostics on stderr):

  bump-usage      --agent A --model M --skill S [--date YYYY-MM-DD]
                  -> UPDATED:<A>/<M>:<S>:<month runs>
  record-verified --agent A --model M --skill S --score 1-5 [--date YYYY-MM-DD]
                  -> UPDATED:<A>/<M>:<S>:<all-time average, 0-100>

                  UPDATED: always means the write is recorded. The value is the
                  total every reader now shows (legacy file counters + branch,
                  or the branch alone once the agent is migrated), computed from
                  the commit just written. It is the literal `unknown` when that
                  total cannot be stated (stderr says why); the write still
                  stands and the exit status is 0. A local aitask-stats ref that
                  could not be advanced after a successful push is likewise a
                  stderr report, not a failure.
  refresh         [--timeout SECONDS]
                  -> REFRESHED:<sha> | REFRESH_SKIPPED:<reason> |
                     STATS_DIVERGED:<local>|<remote>      (always exit 0)
  export          --agent A      -> effective {"schema":1,"models":{...}} JSON
  overlay         --agent A --file F [--root R]
                                 -> F (a models_<A>.json) as JSON with its
                                    usagestats / verifiedstats made effective;
                                    --root defaults to F's directory
  show                           -> BRANCH:/MARKER: header, then one line per
                                    agent/model/stats key/skill

Failures: STATS_ERROR:usage:<msg> (exit 2), STATS_ERROR:<reason> (exit 1),
STATS_DIVERGED:<local>|<remote> (exit 1). Every verb takes --root (default: the
current directory); nothing here touches the task-data worktree.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "lib"))

import model_stats_store as mss  # noqa: E402

MODEL_RE = re.compile(r"[a-z0-9_]+")
# Any non-empty skill the counter writers have always accepted (it is only ever
# a JSON key), so routing them through this CLI narrows nothing (t1912_4). The
# one refusal is a control character: it would split the single-line
# `UPDATED:<agent>/<model>:<skill>:<value>` result every caller parses.
SKILL_RE = re.compile(r"[^\x00-\x1f\x7f]+")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def _line(text: str) -> None:
    sys.stdout.write(text + "\n")


def _today(value):
    if value is None:
        return date.today()
    if not DATE_RE.fullmatch(value):
        raise UsageError("--date must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise UsageError(f"--date is not a valid date: {value}") from None


def _target(args):
    if not mss.AGENT_RE.fullmatch(args.agent or ""):
        raise UsageError(f"invalid --agent: {args.agent!r}")
    if not MODEL_RE.fullmatch(args.model or ""):
        raise UsageError(f"invalid --model: {args.model!r}")
    if not SKILL_RE.fullmatch(args.skill or ""):
        raise UsageError(f"invalid --skill: {args.skill!r}")


def _warn(text: str) -> None:
    try:
        sys.stderr.write(f"model-stats: {text}\n")
    except Exception:  # noqa: BLE001 - reporting must never undo a recorded write
        pass


def _write(args, key, render, message) -> int:
    """Run one counter write and print its UPDATED: line.

    Everything after ``mss.update`` returns runs on a write that is already
    durable, so no failure there may become a failure exit or read as "not
    recorded": local-ref trouble and an unavailable total are stderr reports.
    """
    today = _today(args.date)
    committed = {}

    def fn(blob):
        new_blob, value = render(blob, today)
        # The last call is the committed attempt: update() returns right after
        # that attempt's push (or local CAS) succeeds.
        committed["models"] = copy.deepcopy(new_blob.get("models") or {})
        return new_blob, value

    res = mss.update(args.root, args.agent, fn, message=message, return_commit=True)
    head = f"UPDATED:{args.agent}/{args.model}:{args.skill}:"
    try:
        if res.local_ref == "DIVERGED" or res.local_ref.startswith("ERROR:"):
            _warn(f"recorded on origin, but the local {mss.L_REF} was not advanced "
                  f"({res.local_ref}); run 'aitask_model_stats.py refresh' or './ait sync'")
        total = mss.effective_total(args.root, args.agent, args.model, key, args.skill,
                                    today, committed.get("models"), res.commit)
        text = f"{head}{total}"
    except Exception as exc:  # noqa: BLE001 - see the docstring
        reason = exc.reason if isinstance(exc, mss.StatsError) else type(exc).__name__
        _warn(f"recorded, but the effective total is unavailable ({reason})")
        text = f"{head}unknown"
    _line(text)
    return 0


def cmd_bump_usage(args) -> int:
    _target(args)
    return _write(
        args, "usagestats",
        lambda blob, today: mss.bump_usage(blob, args.model, args.skill, today),
        f"ait: Update usage count {args.agent}/{args.model} {args.skill}")


def cmd_record_verified(args) -> int:
    _target(args)
    if not re.fullmatch(r"[1-5]", args.score or ""):
        raise UsageError("--score must be an integer from 1 to 5")
    mapped = int(args.score) * 20
    return _write(
        args, "verifiedstats",
        lambda blob, today: mss.record_verified(blob, args.model, args.skill, mapped, today),
        f"ait: Update verified score {args.agent}/{args.model} {args.skill}")


def cmd_refresh(args) -> int:
    kind, detail = mss.refresh(args.root, timeout=args.timeout)
    if kind == "refreshed":
        _line(f"REFRESHED:{detail}")
    elif kind == "diverged":
        _line(f"STATS_DIVERGED:{detail}")
    else:
        _line(f"REFRESH_SKIPPED:{detail}")
    return 0


def cmd_export(args) -> int:
    if not mss.AGENT_RE.fullmatch(args.agent or ""):
        raise UsageError(f"invalid --agent: {args.agent!r}")
    models = mss.load_agent_stats(args.root, args.agent)
    sys.stdout.write(json.dumps({"schema": mss.SCHEMA, "models": models},
                                sort_keys=True, indent=2) + "\n")
    return 0


def cmd_overlay(args) -> int:
    if not mss.AGENT_RE.fullmatch(args.agent or ""):
        raise UsageError(f"invalid --agent: {args.agent!r}")
    path = args.file
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise UsageError(f"unreadable --file {path!r}: {exc}") from None
    root = args.root if args.root is not None else os.path.dirname(os.path.abspath(path))
    out = mss.overlay_data(root, args.agent, data)
    sys.stdout.write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return 0


def cmd_show(args) -> int:
    state = mss.branch_state(args.root)
    _line(f"BRANCH:{state['sha'] or 'none'}")
    everything = mss.load_all_stats(args.root)
    for agent in sorted(everything):
        _line(f"MARKER:{agent}:{'yes' if agent in state['markers'] else 'no'}")
    for agent, models in sorted(everything.items()):
        for model, row in sorted(models.items()):
            for key in mss.STATS_KEYS:
                for skill, entry in sorted((row.get(key) or {}).items()):
                    at = mss._normalize(entry).get("all_time") or {}
                    runs = mss._num(at.get("runs"))
                    text = f"{agent}/{model} {key} {skill} all_time={runs}"
                    if key == "verifiedstats" and runs:
                        text += f" avg={mss._jq_round(mss._num(at.get('score_sum')) / runs)}"
                    _line(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="aitask_model_stats.py", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="verb", parser_class=_Parser)

    def add(name, func):
        p = sub.add_parser(name)
        p.add_argument("--root", default=os.getcwd())
        p.set_defaults(func=func)
        return p

    for name, func in (("bump-usage", cmd_bump_usage),
                       ("record-verified", cmd_record_verified)):
        p = add(name, func)
        p.add_argument("--agent", required=True)
        p.add_argument("--model", required=True)
        p.add_argument("--skill", required=True)
        p.add_argument("--date")
        if name == "record-verified":
            p.add_argument("--score", required=True)
    p = add("refresh", cmd_refresh)
    p.add_argument("--timeout", type=float)
    p = add("export", cmd_export)
    p.add_argument("--agent", required=True)
    p = add("overlay", cmd_overlay)
    p.add_argument("--agent", required=True)
    p.add_argument("--file", required=True)
    p.set_defaults(root=None)
    add("show", cmd_show)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if not getattr(args, "func", None):
            raise UsageError("a verb is required: bump-usage, record-verified, "
                             "refresh, export, overlay, show")
        return args.func(args)
    except UsageError as exc:
        _line(f"STATS_ERROR:usage:{str(exc).replace(chr(10), ' ')}")
        return 2
    except mss.StatsDiverged as exc:
        _line(f"STATS_DIVERGED:{exc.local}|{exc.remote}")
        return 1
    except mss.StatsError as exc:
        _line(f"STATS_ERROR:{exc.reason}")
        return 1
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        _line(f"STATS_ERROR:{type(exc).__name__}:{str(exc).replace(chr(10), ' ')[:200]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
