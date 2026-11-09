#!/usr/bin/env python3
"""obsolete_cli.py - ``ait obsolete``: the obsolescence layer's surfaces (t1981_6).

Design: aidocs/framework/task_relations.md D9 ("Surfaces and dispositions",
"Obsolescence API"). Verbs (``aitask_obsolete.sh`` runs ``review`` itself and
calls the rest here)::

    evidence <id> [--json] [--no-fetch]     the static evidence rows, live
    ls [--min-band low|medium|high] [--all] [--no-fetch]
    show <id> [--json] [--no-fetch]          one stored assessment
    dismiss <id> [--note <text>]             a human dismissal, keyed to the digest
    sweep [--budget N]                       enqueue a fairly rotated batch
    unblock <id> [--kill] [--force]          clear this op's unresolved-invocation guard
    _review-items [--no-fetch]               (review's list: "<id>|<fold_target or ->")

Every output starts with ``RELATIONS_STATE:`` and ``STORE:``. Free-text fields
are percent-encoded (``%0D``, ``%0A``, ``%7C``, ``%25``). Exit: 0 ok, 1 usage /
not found / refused, 3 retained for retry (``RETAINED:``).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import obsolescence_evidence as oe  # noqa: E402
import relations_config as rcfg  # noqa: E402
import relations_consume as rc  # noqa: E402
import relations_schema as rs  # noqa: E402
import relations_spool as rsp  # noqa: E402
import relations_store as rst  # noqa: E402
import relations_worker as rw  # noqa: E402

BAND_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
PICK_MIN_BAND = "medium"
PICK_MAX_REASONS = 3


def _root():
    return rst.ors.toplevel(os.getcwd())


def _open(root, no_fetch=False):
    """``(store, snap, state)`` or ``(None, None, lines)`` for an unresolvable project."""
    try:
        store = rst.Store(root)
    except rst.ProjectUnresolved:
        return None, None, ["RELATIONS_STATE:disabled", "STORE:unreachable:project_unresolved"]
    state = store.relations_state()
    snap = store.read(no_fetch=no_fetch or state == "disabled")
    return store, snap, state


def _head(snap, state):
    return [f"RELATIONS_STATE:{state}", f"STORE:{snap.state}"]


# ============================================================ shared views

def assessment(store, snap, tid):
    """``(record, dismissal_state, dismissal)`` for an identity-valid record, else Nones.

    ``dismissal_state``: None (no dismissal), ``current`` (keyed to this record's
    evidence digest, so it hides the task) or ``stale`` (an older digest).
    """
    tid = rs.norm_id(tid)
    rec = snap.files.get(rs.store_path("obsolescence", tid))
    if not isinstance(rec, dict) or not store._record_identity_ok(rec):
        return None, None, None
    dis = snap.files.get(rs.store_path("dismissals", tid))
    if not isinstance(dis, dict) or not store._record_identity_ok(dis):
        return rec, None, None
    state = "current" if dis.get("evidence_digest") == rec["inputs"]["evidence_digest"] else "stale"
    return rec, state, dis


def inputs_freshness(root, store, snap, tid, rec, stamps=None, drepo=None) -> str:
    """``fresh`` / ``stale`` (body or plan changed since the assessment) / ``unverified``."""
    try:
        drepo = drepo or rw.data_repo(root)
        stamps = stamps if stamps is not None else rw.valid_stamps(store, snap)
        src = rw.task_inputs(root, store, drepo, stamps, rs.norm_id(tid))
    except (rw.JobFailed, OSError):
        return "unverified"
    if src is None:
        return "unverified"
    same = (src.digests["body_sha256"] == rec["inputs"]["body_sha256"]
            and src.digests["plan_sha256"] == rec["inputs"]["plan_sha256"])
    return "fresh" if same else "stale"


def _disp(rec) -> str:
    target = rec.get("fold_target")
    return f"{rec['disposition']}:{target}" if target else rec["disposition"]


def pick_view(root, store, snap, tid):
    """The pick-time display (D9 / related-work ``--point pick``), or None.

    Shown only for an identity-valid assessment with band >= medium that is not
    dismissed at its current digest.
    """
    rec, dstate, _dis = assessment(store, snap, tid)
    if rec is None or dstate == "current" or BAND_RANK[rec["band"]] < BAND_RANK[PICK_MIN_BAND]:
        return None
    return {"band": rec["band"], "disposition": rec["disposition"],
            "fold_target": rec.get("fold_target"),
            "inputs": inputs_freshness(root, store, snap, tid, rec),
            "reasons": [r["text"] for r in rec["reasons"][:PICK_MAX_REASONS]],
            "assessed_at": rec["run"]["at"]}


def pick_lines(view) -> list:
    if view is None:
        return []
    disp = view["disposition"] + (f":{view['fold_target']}" if view["fold_target"] else "")
    lines = [f"OBSOLESCENCE:{view['band']}|{disp}|{view['inputs']}"]
    lines += [f"OBSOLESCENCE_REASON:{rc.enc(t)}" for t in view["reasons"]]
    return lines


def _active_eligible(store):
    store.index.load_active()
    out = []
    for tid, entry in list(store.index._entries.items()):
        if rw.obs_eligible(entry):
            out.append(tid)
    return sorted(out, key=_id_key)


def _id_key(tid):
    return tuple(int(p) for p in rs.norm_id(tid).split("_"))


# ================================================================== verbs

def cmd_evidence(root, args):
    store, snap, state = _open(root, args.no_fetch)
    if store is None:
        print("\n".join(state + ["EVIDENCE_UNAVAILABLE:project_unresolved"]))
        return 1
    tid = rs.norm_id(args.id)
    entry = store.index.lookup(tid)
    if entry is None or entry.text is None:
        print("\n".join(_head(snap, state) + [f"TASK_NOT_FOUND:t{tid}"]))
        return 1
    incomplete = []
    plan = None
    try:
        src = rw.task_inputs(root, store, rw.data_repo(root), rw.valid_stamps(store, snap), tid)
        plan = src.plan if src is not None else None
    except rw.JobFailed as exc:
        incomplete.append(f"inputs:{exc.reason}")
    ev = oe.collect(root, store, snap, tid, entry.text, plan)
    incomplete = incomplete + ev.incomplete
    if args.json:
        print(json.dumps({"relations_state": state, "store": snap.state, "task": store.ref(tid),
                          "rows": [dict(r.as_dict(), signal=r.signal) for r in ev.rows],
                          "incomplete": incomplete, "signal_rows": ev.signal_count,
                          "evidence_digest": ev.digest}, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    lines = _head(snap, state)
    for r in ev.rows:
        lines.append(f"EVIDENCE:{r.id}|{r.kind}|{'signal' if r.signal else 'context'}|"
                     f"{rc.enc(r.source)}|{rc.enc(r.detail)}")
    lines += [f"INCOMPLETE:{rc.enc(x)}" for x in incomplete]
    lines += [f"SIGNAL_ROWS:{ev.signal_count}", f"EVIDENCE_DIGEST:{ev.digest}"]
    print("\n".join(lines))
    return 0


def list_rows(root, store, snap, min_band="low", include_dismissed=False):
    drepo = rw.data_repo(root)
    stamps = rw.valid_stamps(store, snap)
    rows = []
    for path in sorted(snap.files):
        parsed = rs.parse_store_path(path)
        if not parsed or parsed[0] != "obsolescence":
            continue
        tid = parsed[1]
        if not rw.obs_eligible(store.index.lookup(tid)):
            continue
        rec, dstate, _ = assessment(store, snap, tid)
        if rec is None or BAND_RANK[rec["band"]] < BAND_RANK[min_band]:
            continue
        if dstate == "current" and not include_dismissed:
            continue
        rows.append((tid, rec, dstate, inputs_freshness(root, store, snap, tid, rec, stamps, drepo)))
    rows.sort(key=lambda r: (-BAND_RANK[r[1]["band"]], _id_key(r[0])))
    return rows


def cmd_ls(root, args):
    store, snap, state = _open(root, args.no_fetch)
    if store is None:
        print("\n".join(state + ["OBSOLETE:0"]))
        return 0
    lines = _head(snap, state)
    rows = list_rows(root, store, snap, args.min_band, args.all)
    for tid, rec, dstate, fresh in rows:
        line = f"OBSOLETE:t{tid}|{rec['band']}|{_disp(rec)}|{fresh}|reasons={len(rec['reasons'])}"
        if dstate == "current":
            line += "|dismissed"
        lines.append(line)
    if not rows:
        lines.append("OBSOLETE:0")
    print("\n".join(lines))
    return 0


def cmd_review_items(root, args):
    store, snap, state = _open(root, args.no_fetch)
    if store is None:
        return 0
    for tid, rec, _dstate, _fresh in list_rows(root, store, snap):
        print(f"{tid}|{rec.get('fold_target') or '-'}")
    return 0


def cmd_show(root, args):
    store, snap, state = _open(root, args.no_fetch)
    if store is None:
        print("\n".join(state + [f"NO_ASSESSMENT:t{rs.norm_id(args.id)}"]))
        return 1
    tid = rs.norm_id(args.id)
    rec, dstate, dis = assessment(store, snap, tid)
    if rec is None:
        print("\n".join(_head(snap, state) + [f"NO_ASSESSMENT:t{tid}"]))
        return 1
    fresh = inputs_freshness(root, store, snap, tid, rec)
    if args.json:
        print(json.dumps({"relations_state": state, "store": snap.state, "record": rec,
                          "inputs": fresh, "dismissal": dis, "dismissal_state": dstate},
                         indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    run = rec["run"]
    lines = _head(snap, state) + [
        f"OBSOLESCENCE:t{tid}|{rec['band']}|{_disp(rec)}|{fresh}",
        f"RUN:{run['trigger']}|stage={run['stage']}|{run['at']}|{rc.enc(run.get('agent_string', ''))}"]
    for reason in rec["reasons"]:
        lines.append(f"REASON:{','.join(reason['evidence_ids'])}|{rc.enc(reason['text'])}")
    for ev in rec["evidence"]:
        lines.append(f"EVIDENCE:{ev['id']}|{ev['kind']}|{rc.enc(ev['source'])}|{rc.enc(ev['detail'])}")
    usage = rec.get("usage") or {}
    lines.append("USAGE:" + "|".join(f"{k}={usage.get(k)}" for k in
                                     ("input_tokens", "output_tokens", "cost_usd", "wall_s")))
    if dis is None:
        lines.append("DISMISSED:no")
    else:
        lines.append(f"DISMISSED:{dstate}|{dis['at']}|{rc.enc(dis['by'])}|{rc.enc(dis.get('note', ''))}")
    lines.append(f"CONTEXT:see ait obsolete evidence {tid}")
    print("\n".join(lines))
    return 0


def _dismissed_by(root) -> str:
    cfg = os.path.join(root, os.environ.get("TASK_DIR", "aitasks"), "metadata", "userconfig.yaml")
    try:
        with open(cfg, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("email:"):
                    value = line.split(":", 1)[1].strip().strip("'\"")
                    if value:
                        return value
    except OSError:
        pass
    proc = subprocess.run(["git", "-C", str(root), "config", "user.email"],
                          capture_output=True, text=True)
    return proc.stdout.strip() or socket.gethostname()


def cmd_dismiss(root, args):
    store, snap, state = _open(root)
    tid = rs.norm_id(args.id)
    if store is None:
        print("\n".join(state + [f"NO_ASSESSMENT:t{tid}"]))
        return 1
    rec, _dstate, _dis = assessment(store, snap, tid)
    if rec is None:
        print("\n".join(_head(snap, state) + [f"NO_ASSESSMENT:t{tid}"]))
        return 1
    dismissal = {"task": store.ref(tid), "task_created_at": rec["task_created_at"],
                 "at": rsp.utc_iso(), "by": _dismissed_by(root),
                 "evidence_digest": rec["inputs"]["evidence_digest"]}
    if args.note:
        dismissal["note"] = args.note
    try:
        reports = store.write(rs.store_path("dismissals", tid), dismissal)
    except rs.SchemaError as exc:
        print("\n".join(_head(snap, state) + [f"DISMISS_ERROR:{rc.enc(str(exc))}"]))
        return 1
    head = reports[0] if reports else ""
    lines = _head(snap, state)
    if head.startswith(("IDENTITY_MISMATCH", "PROJECT_MISMATCH", "STALE_RUN")):
        print("\n".join(lines + [f"DISMISS_REFUSED:{head}"]))
        return 1
    lines.append(f"DISMISSED:t{tid}|{rec['inputs']['evidence_digest'][:12]}")
    lines += reports
    print("\n".join(lines))
    return 3 if any(r.startswith("RETAINED:") for r in reports) else 0


def _last_attempts(sp) -> dict:
    """``{tid: (position, outcome)}`` of each task's newest obsolescence job row.

    The position is the row's index in this host's append-only ledger: rows are
    appended under ``usage.lock`` in the order the jobs ended, so it orders
    attempts exactly (the ``at`` field has one-second resolution and would tie).
    """
    rows, _corrupt = sp.read_ledger()
    last = {}
    for pos, row in enumerate(rows):
        if row.get("kind") == "job" and row.get("op") == rw.OBS_OP and not row.get("dry_run"):
            last[str(row.get("task", ""))] = (pos, str(row.get("outcome", "")))
    return last


def sweep_order(root, store, snap, sp) -> list:
    """Every eligible task, fairly rotated: ``(not boosted, last attempt, id)``.

    A task with no assessment, or whose body / plan changed since it, is
    BOOSTED until an attempt fails on it: with no assessment, any attempt spends
    the boost; with a changed one, the boost holds only while the newest attempt
    is the successful one the stored record came from (the change happened
    after it). After that every task rotates by its last attempt, so a
    persistent failure can never monopolise a bounded sweep.
    """
    last = _last_attempts(sp)
    drepo = rw.data_repo(root)
    stamps = rw.valid_stamps(store, snap)
    order = []
    for tid in _active_eligible(store):
        state = sp.job_state(tid, rw.OBS_OP)
        if state and state.startswith("pending"):
            continue
        rec, _d, _dis = assessment(store, snap, tid)
        pos, outcome = last.get(tid, (-1, ""))
        if rec is None:
            boosted = pos < 0
        else:
            changed = inputs_freshness(root, store, snap, tid, rec, stamps, drepo) != "fresh"
            boosted = changed and (pos < 0 or outcome.startswith(("ASSESSED", "UP_TO_DATE")))
        order.append((0 if boosted else 1, pos, _id_key(tid), tid))
    order.sort()
    return [entry[-1] for entry in order]


def cmd_sweep(root, args):
    cfg = rcfg.load(root)
    if not cfg.enabled:
        print("DISABLED:relations analysis is disabled in this project (ait relations enable)")
        return 1
    if os.environ.get("AIT_RELATIONS") == "0":
        print("HOST_OFF:AIT_RELATIONS=0 switches analysis off on this host")
        return 1
    store, snap, state = _open(root)
    if store is None:
        print("\n".join(state + ["SWEEP:0|budget=0|candidates=0"]))
        return 1
    sp = rsp.Spool(rw.state_dir(root))
    budget = args.budget
    if budget is None:
        budget = max(0, cfg.max_jobs_per_day - sp.calls_today(rw.OBS_OP))
    order = sweep_order(root, store, snap, sp)
    lines = _head(snap, state)
    picked = order[:max(0, budget)]
    for tid in picked:
        rw.enqueue_job(root, rw.OBS_OP, "sweep", tid)
        lines.append(f"ENQUEUED:t{tid}")
    lines.append(f"SWEEP:{len(picked)}|budget={budget}|candidates={len(order)}")
    print("\n".join(lines))
    return 0


def cmd_unblock(root, args):
    """``ait obsolete unblock``: the obsolescence op's guards only (``ait relations
    unblock --op obsolescence``), same protocol and exit codes."""
    import relations_cli
    args.op = rw.OBS_OP
    return relations_cli.cmd_unblock(root, args)


def build_parser():
    ap = argparse.ArgumentParser(prog="ait obsolete", allow_abbrev=False)
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("evidence", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-fetch", action="store_true")
    p = sub.add_parser("ls", allow_abbrev=False)
    p.add_argument("--min-band", choices=("low", "medium", "high"), default="low")
    p.add_argument("--all", action="store_true")
    p.add_argument("--no-fetch", action="store_true")
    p = sub.add_parser("show", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-fetch", action="store_true")
    p = sub.add_parser("dismiss", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--note", default=None)
    p = sub.add_parser("sweep", allow_abbrev=False)
    p.add_argument("--budget", type=int, default=None)
    p = sub.add_parser("unblock", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--kill", action="store_true")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("_review-items", allow_abbrev=False)
    p.add_argument("--no-fetch", action="store_true")
    return ap


VERBS = {"evidence": cmd_evidence, "ls": cmd_ls, "show": cmd_show, "dismiss": cmd_dismiss,
         "sweep": cmd_sweep, "unblock": cmd_unblock, "_review-items": cmd_review_items}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.id = rs.norm_id(args.id) if getattr(args, "id", None) is not None else None
    except rs.SchemaError as exc:
        sys.stderr.write(f"ait obsolete: {exc}\n")
        return 1
    return VERBS[args.verb](_root(), args)


if __name__ == "__main__":
    sys.exit(main())
