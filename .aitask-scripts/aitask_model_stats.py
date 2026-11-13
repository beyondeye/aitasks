#!/usr/bin/env python3
"""aitask_model_stats.py - CLI over lib/model_stats_store.py (the aitask-stats branch).

Verbs (single-line structured stdout, diagnostics on stderr):

  bump-usage      --agent A --model M --skill S [--date YYYY-MM-DD]
                  -> UPDATED:<A>/<M>:<S>:<month runs>
  record-verified --agent A --model M --skill S --score 1-5 [--date YYYY-MM-DD]
                  -> UPDATED:<A>/<M>:<S>:<all-time average, 0-100>
  refresh         [--timeout SECONDS]
                  -> REFRESHED:<sha> | REFRESH_SKIPPED:<reason> |
                     STATS_DIVERGED:<local>|<remote>      (always exit 0)
  export          --agent A      -> effective {"schema":1,"models":{...}} JSON
  show                           -> BRANCH:/MARKER: header, then one line per
                                    agent/model/stats key/skill

Failures: STATS_ERROR:usage:<msg> (exit 2), STATS_ERROR:<reason> (exit 1),
STATS_DIVERGED:<local>|<remote> (exit 1). Every verb takes --root (default: the
current directory); nothing here touches the task-data worktree.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "lib"))

import model_stats_store as mss  # noqa: E402

MODEL_RE = re.compile(r"[a-z0-9_]+")
SKILL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
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


def cmd_bump_usage(args) -> int:
    _target(args)
    today = _today(args.date)
    value = mss.update(
        args.root, args.agent,
        lambda blob: mss.bump_usage(blob, args.model, args.skill, today),
        message=f"ait: Update usage count {args.agent}/{args.model} {args.skill}")
    _line(f"UPDATED:{args.agent}/{args.model}:{args.skill}:{value}")
    return 0


def cmd_record_verified(args) -> int:
    _target(args)
    if not re.fullmatch(r"[1-5]", args.score or ""):
        raise UsageError("--score must be an integer from 1 to 5")
    today = _today(args.date)
    mapped = int(args.score) * 20
    value = mss.update(
        args.root, args.agent,
        lambda blob: mss.record_verified(blob, args.model, args.skill, mapped, today),
        message=f"ait: Update verified score {args.agent}/{args.model} {args.skill}")
    _line(f"UPDATED:{args.agent}/{args.model}:{args.skill}:{value}")
    return 0


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
    add("show", cmd_show)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if not getattr(args, "func", None):
            raise UsageError("a verb is required: bump-usage, record-verified, "
                             "refresh, export, show")
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
