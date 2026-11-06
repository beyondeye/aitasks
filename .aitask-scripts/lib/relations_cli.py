#!/usr/bin/env python3
"""relations_cli.py - ``ait relations`` store verbs (t1981_1).

Verbs: ``show <id> [--json] [--no-fetch]``, ``why <a> <b> [--no-fetch]``,
``status``, ``flush``, ``gc [--dry-run]``. The worker child (t1981_3) adds the
analysis verbs here.

Every reader output starts with the state lines of
aidocs/framework/task_relations.md D1 -- ``RELATIONS_STATE:``, ``STORE:`` and,
per task, ``ANALYSIS:`` -- so an empty, disabled or unreachable store is never
presented as "no related tasks".

Exit codes: 0 ok; 1 usage or validation error; 2 unknown verb; 3 the work was
kept for retry (``RETAINED:``) or refused (``GC_REFUSED:``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import relations_schema as rs  # noqa: E402
import relations_store as rst  # noqa: E402

VERBS = ("show", "why", "status", "flush", "gc")
USAGE = """usage: ait relations <verb> [args]

  show <id> [--json] [--no-fetch]   relations of a task (forward + reverse)
  why <a> <b> [--no-fetch]          the relations between two tasks
  status                            store state and the outbox (age, last error)
  flush                             publish the outbox
  gc [--dry-run]                    remove files of tasks that exist nowhere
"""


def _state_lines(store, snap, task_ids, relations_state):
    lines = [f"RELATIONS_STATE:{relations_state}", f"STORE:{snap.state}"]
    for ref in task_ids:
        lines.append(f"ANALYSIS:{store.label(ref)}|{store.analysis_line(ref, snap, relations_state)}")
    for entry in snap.corrupt:
        lines.append(f"CORRUPT:{entry}")
    return lines


def _rel_lines(rel):
    flag = "|pending_push" if rel.pending_push else ""
    lines = [f"REL:{rel.direction}|{rel.type}|{rel.other}|{rel.freshness}{flag}",
             f"  {rel.description}"]
    for basis in rel.basis:
        lines.append(f"  basis:{basis['kind']}:{basis['value']}")
    return lines


def cmd_show(store, args):
    tid = store.ref(args.id)  # a bare id is local; a <project>#<id> keeps its project
    snap = store.read(no_fetch=args.no_fetch)
    state = store.relations_state()
    rels = store.relations(tid, snap)
    if args.json:
        print(json.dumps({
            "relations_state": state, "store": snap.state,
            "analysis": store.analysis_line(tid, snap, state),
            "task": store.canonical_ref(tid), "project": store.project,
            "corrupt": snap.corrupt,
            "relations": [r.as_dict() for r in rels]}, indent=2, sort_keys=True))
        return 0
    print("\n".join(_state_lines(store, snap, [tid], state)))
    if state == "disabled" and not rels:
        print("NOTE:relations analysis is disabled in this project -- no relation data")
    for rel in rels:
        print("\n".join(_rel_lines(rel)))
    if not rels:
        print("RELATIONS:0")
    return 0


def cmd_why(store, args):
    a, b = store.ref(args.a), store.ref(args.b)
    snap = store.read(no_fetch=args.no_fetch)
    state = store.relations_state()
    print("\n".join(_state_lines(store, snap, [a, b], state)))
    cb = store.canonical_ref(b)
    found = 0
    for rel in store.relations(a, snap):
        if cb in (rel.from_, rel.to):
            found += 1
            print("\n".join(_rel_lines(rel)))
            print(f"  recorded_by:{rel.record_task}")
            for ev in rel.evidence:
                print(f"  evidence:{ev.get('source')}:{ev.get('detail')}")
    if not found:
        print("RELATIONS:0")
    return 0


def cmd_status(store, _args):
    snap = store.read()
    print(f"RELATIONS_STATE:{store.relations_state()}")
    print(f"STORE:{snap.state}")
    print(f"MODE:{store.mode()}")
    print("\n".join(store.status()))
    return 0


def _emit(lines):
    print("\n".join(lines))
    return 3 if any(ln.startswith(("RETAINED:", "GC_REFUSED:")) for ln in lines) else 0


def cmd_flush(store, _args):
    return _emit(store.flush())


def cmd_gc(store, args):
    return _emit(store.gc(dry_run=args.dry_run))


def build_parser():
    parser = argparse.ArgumentParser(prog="ait relations", add_help=True, allow_abbrev=False)
    sub = parser.add_subparsers(dest="verb")
    p = sub.add_parser("show", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-fetch", action="store_true")
    p = sub.add_parser("why", allow_abbrev=False)
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--no-fetch", action="store_true")
    sub.add_parser("status", allow_abbrev=False)
    sub.add_parser("flush", allow_abbrev=False)
    p = sub.add_parser("gc", allow_abbrev=False)
    p.add_argument("--dry-run", action="store_true")
    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        sys.stdout.write(USAGE)
        return 0 if argv else 1
    if argv[0] not in VERBS:
        sys.stderr.write(f"ait relations: unknown verb '{argv[0]}'\n{USAGE}")
        return 2
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 1 if exc.code else 0
    try:
        store = rst.Store(os.getcwd())
        return {"show": cmd_show, "why": cmd_why, "status": cmd_status,
                "flush": cmd_flush, "gc": cmd_gc}[args.verb](store, args)
    except rst.ProjectUnresolved as exc:
        sys.stderr.write(f"ait relations: PROJECT_UNRESOLVED: {exc} -- run 'ait setup' to seed project.name\n")
        return 1
    except rs.SchemaError as exc:
        sys.stderr.write(f"ait relations: {exc}\n")
        return 1
    except rst.ors.GitError as exc:
        sys.stderr.write(f"ait relations: git: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
