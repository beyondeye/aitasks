#!/usr/bin/env python3
"""relations_cli.py - ``ait relations`` (t1981_1 store verbs, t1981_3 analysis verbs).

Store verbs: ``show <id> [--json] [--no-fetch]``, ``why <a> <b> [--no-fetch]``,
``status``, ``flush``, ``gc [--dry-run]``.
Analysis verbs (t1981_3): ``analyze <id> [--dry-run] [--now [--wait <s>]]
[--over-cap]``, ``stamp <id>``, ``plan-digest <id>``, ``analysis-state <id>
[--expect-plan <sha>]``, ``usage [--days N]``, ``ledgers --export``,
``unblock <id> [--kill] [--force] [--op <op>]``, ``enable``, ``disable``. Line protocols:
aidocs/framework/task_relations.md "Worker API".

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
import socket
import subprocess
import sys
import time
import uuid

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import relations_config as rcfg  # noqa: E402
import relations_consume as rc  # noqa: E402
import relations_schema as rs  # noqa: E402
import relations_spool as rsp  # noqa: E402
import relations_store as rst  # noqa: E402
import relations_worker as rw  # noqa: E402

VERBS = ("show", "why", "status", "flush", "gc", "analyze", "stamp", "plan-digest",
         "analysis-state", "usage", "ledgers", "unblock", "enable", "disable",
         "related-work", "notify-candidates", "notify-outcome")
# Verbs that construct their own Store (or none): a disabled project without
# project.name must still answer STAMP:disabled / disabled, never PROJECT_UNRESOLVED.
NO_STORE_VERBS = ("analyze", "stamp", "plan-digest", "analysis-state", "usage", "ledgers",
                  "unblock", "enable", "disable", "related-work", "notify-candidates",
                  "notify-outcome")
USAGE = """usage: ait relations <verb> [args]

  show <id> [--json] [--no-fetch]   relations of a task (forward + reverse)
  why <a> <b> [--no-fetch]          the relations between two tasks
  status                            store state, the outbox, and the analysis spool
  flush                             publish the outbox
  gc [--dry-run]                    remove files of tasks that exist nowhere
  analyze <id> [--dry-run] [--now [--wait <s>]] [--over-cap]
                                    queue (or, with --dry-run, run and print) an analysis
  stamp <id>                        record the plan-approval stamp (prints STAMP:<sha>)
  plan-digest <id>                  digest of the plan committed at the task-data HEAD
  analysis-state <id> [--expect-plan <sha>]
                                    Step 8e completeness verdict (ANALYSIS_STATE:)
  usage [--days N]                  jobs, calls, tokens, cost, wall time
  ledgers --export                  this host's ledgers as host-tagged JSON lines
  unblock <id> [--kill] [--force] [--op relations|obsolescence]
                                    clear an unresolved-invocation guard (per op)
  enable | disable                  switch background analysis on/off (commits)
  related-work <id> --point pick|review|note [--since <ts>] [--log] [--json]
                                    the display-only related-work check (D8 pull);
                                    at --point pick it also shows the task's own
                                    obsolescence band when medium+ (OBSOLESCENCE:)
  notify-candidates <id> [--rev <rev> | --diff <range>] [--expect-plan <sha>]
      [--option <opt>] [--log] [--json]
                                    Step 8e PUSH/PULL rows against the task's own change
  notify-outcome <id> --run <id> --to <ref> --type <type> --outcome sent|declined|not_offered
      [--note-id <id>]              record one Step 8e offer outcome (notify.jsonl)
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
    sp = rsp.Spool(rw.state_dir(store.root))
    for sub, tag in (("running", "RUNNING"), ("jobs", "JOB")):
        for job in sp.list_jobs(sub):
            print(f"{tag}:{job.get('op')}|t{job.get('task')}|trigger={job.get('trigger')}"
                  f"|state={job.get('state') or ('now' if job.get('now') else 'queued')}")
    for job in sp.list_jobs("failed"):
        print(f"FAILED:{job.get('op')}|t{job.get('task')}|{job.get('reason')}")
    for guard in sp.guards():
        agent = guard.get("agent") or {}
        print(f"UNRESOLVED:{guard['_key']}|{guard['_inv']}|{guard.get('why')}|pgid={agent.get('pgid', '-')}")
    return 0


def _emit(lines):
    print("\n".join(lines))
    return 3 if any(ln.startswith(("RETAINED:", "GC_REFUSED:")) for ln in lines) else 0


def cmd_flush(store, _args):
    return _emit(store.flush())


def cmd_gc(store, args):
    return _emit(store.gc(dry_run=args.dry_run))


# ================================================================ t1981_3

def _root():
    return rst.ors.toplevel(os.getcwd())


def _tid(value):
    return rs.norm_id(value)


def cmd_analyze(root, args):
    cfg = rcfg.load(root)
    sp = rsp.Spool(rw.state_dir(root))
    tid = _tid(args.id)
    if args.wait is not None and not args.now:
        sys.stderr.write("ait relations analyze: --wait requires --now\n")
        return 1
    if args.dry_run:
        if not args.over_cap and sp.cap_reached(rw.OP, cfg.max_jobs_per_day):
            print(f"CAP_REACHED:{sp.calls_today(rw.OP)}/{cfg.max_jobs_per_day}")
            return 3
        job = {"op": rw.OP, "task": tid, "trigger": "manual", "over_cap": bool(args.over_cap)}

        def log(msg):
            sys.stderr.write(msg + "\n")
        # A preview killed earlier may have left its agent running: account for
        # it (end it, or guard the task) before this run can start a new one.
        rw.recover_previews(sp, log=log)

        def job_row(outcome):
            sp.log_job(rw.OP, tid, "manual", outcome, dry_run=True)
        try:
            outcome, rec = rw.analyse(root, sp, job, dry_run=True, log=log)
        except rw.Refused as exc:
            print(str(exc))
            return 3
        except rw.JobFailed as exc:
            job_row(f"FAILED:{exc.reason}"[:200])
            print(f"FAILED:{exc.reason}")
            return 1
        except rw.JobRetry:
            job_row("FAILED:TIMEOUT")
            print("FAILED:TIMEOUT")
            return 1
        job_row(outcome)
        if rec is None:
            print(f"ANALYSIS_SKIPPED:{outcome}")
            return 0
        print(json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    state = rcfg.load(root)
    if not state.enabled:
        print("DISABLED:relations analysis is disabled in this project (ait relations enable)")
        return 1
    if os.environ.get("AIT_RELATIONS") == "0":
        print("HOST_OFF:AIT_RELATIONS=0 switches analysis off on this host")
        return 1
    if args.now and not args.over_cap and sp.cap_reached(rw.OP, cfg.max_jobs_per_day):
        print(f"CAP_REACHED:{sp.calls_today(rw.OP)}/{cfg.max_jobs_per_day}")
        return 3
    rid = uuid.uuid4().hex if args.wait is not None else None
    rw.enqueue_job(root, rw.OP, "manual", tid, now=bool(args.now), over_cap=bool(args.over_cap),
                   request_id=rid, respect_switches=False)
    if rid is None:
        print(f"ENQUEUED:t{tid}")
        return 0
    deadline = time.monotonic() + max(0.0, args.wait)
    while True:
        res = sp.result(rid)
        if res is not None:
            outcome = res.get("outcome", "")
            print(f"ANALYZED:t{tid}|{outcome}")
            return 3 if outcome.startswith(("FAILED", "CAP_REACHED", "BLOCKED")) else 0
        if time.monotonic() >= deadline:
            print(f"WAIT_TIMEOUT:t{tid}|{sp.job_state(tid) or 'none'}")
            return 3
        time.sleep(0.2)


def cmd_stamp(root, args):
    tid = _tid(args.id)
    try:
        sha = rw.write_stamp(root, tid)
    except rw.StampError as exc:
        print(f"STAMP_ERROR:{exc}")
        return 1
    if sha is None:
        print("STAMP:disabled")
        return 0
    print(f"STAMP:{sha}")
    sys.stdout.flush()
    try:  # the network publish and the plan_approved enqueue never block the caller
        rw.detach(["stamp-publish", root, tid], root)
    except OSError as exc:
        sys.stderr.write(f"ait relations stamp: could not detach the publish: {exc}\n")
    return 0


def cmd_plan_digest(root, args):
    try:
        sha = rw.plan_digest(root, _tid(args.id))
    except rw.JobFailed as exc:
        print(f"PLAN_DIGEST_ERROR:{exc.reason.lower()}")
        return 1
    if sha is None:
        print("PLAN_DIGEST_ERROR:no_plan")
        return 1
    print(f"PLAN_DIGEST:{sha}")
    return 0


def analysis_state(store, tid, expect):
    """The D8 Step-8e verdict; evaluation order in the design doc's "Worker API"."""
    if store.relations_state() == "disabled":
        return "disabled", None
    if not expect:
        return "incomplete:unverifiable(no_expected_identity)", None
    snap = store.read()
    if snap.state.startswith("stale"):
        return "incomplete:unverifiable(store_stale)", snap
    if snap.state.startswith("unreachable"):
        return "incomplete:unverifiable(store_unreachable)", snap
    spath = rs.store_path("approvals", tid)
    if any(c.split("|", 1)[0] in (spath, f"outbox/{spath}") for c in snap.corrupt):
        return "incomplete:unverifiable(stamp_unreadable)", snap
    stamp = snap.files.get(spath)
    live = store.index.live_created_at(tid)
    if stamp is None or live is None or stamp.get("task_created_at") != live:
        return "incomplete:unverifiable(no_stamp)", snap
    if stamp.get("plan_sha256") != expect:
        return "incomplete:unverifiable(stamp_mismatch)", snap
    rec = snap.files.get(rs.store_path("records", tid))
    rec_ok = isinstance(rec, dict) and rec.get("analysed") and store._record_identity_ok(rec)
    if rec_ok:
        try:
            src = rec["inputs"]["source"]
            if (rec["run"]["stage"] == 2 and src.get("plan_sha256") == expect
                    and src.get("body_sha256") == store.index.body_digest(tid)):
                return "complete", snap
        except (KeyError, TypeError):
            rec_ok = False
    job = rst.job_state(tid, store.state_dir)
    if job:
        return f"incomplete:{job}", snap
    if rec_ok:
        return "incomplete:inputs_mismatch", snap
    return "incomplete:missing", snap


def cmd_analysis_state(root, args):
    tid = _tid(args.id)
    try:
        store = rst.Store(root)
    except rst.ProjectUnresolved as exc:
        if not rcfg.load(root).enabled:
            print("RELATIONS_STATE:disabled")
            print("ANALYSIS_STATE:disabled")
            return 0
        raise exc
    state, snap = analysis_state(store, tid, args.expect_plan)
    print(f"RELATIONS_STATE:{store.relations_state()}")
    if snap is not None:
        print(f"STORE:{snap.state}")
    print(f"ANALYSIS_STATE:{state}")
    if os.environ.get("AIT_RELATIONS") == "0" and state != "disabled":
        print("NOTE:analysis is switched off on this host (AIT_RELATIONS=0)")
    return 0


def _fmt(total, unknown, digits=None):
    val = round(total, digits) if digits is not None else total
    return f"{val}+unknown({unknown})" if unknown else f"{val}"


def _agg(rows_by_call, outcomes, jobs, key_of):
    groups = {}

    def group(k):
        return groups.setdefault(k, {"jobs": 0, "calls": 0, "failed_calls": 0, "unsettled": 0,
                                     "in": [0, 0], "out": [0, 0], "cost": [0.0, 0], "wall": [0.0, 0]})
    for row in jobs:
        group(key_of(row))["jobs"] += 1
    for cid, call in rows_by_call.items():
        g = group(key_of(call))
        g["calls"] += 1
        out = outcomes.get(cid)
        if out is None:
            g["unsettled"] += 1
            for f in ("in", "out", "cost", "wall"):
                g[f][1] += 1
            continue
        if out.get("outcome") != "ok":
            g["failed_calls"] += 1
        for f, src in (("in", "input_tokens"), ("out", "output_tokens"),
                       ("cost", "cost_usd"), ("wall", "wall_s")):
            v = out.get(src)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                g[f][0] += v
            else:
                g[f][1] += 1
    return groups


def cmd_usage(root, args):
    sp = rsp.Spool(rw.state_dir(root))
    cutoff = rsp.utc_iso(time.time() - args.days * 86400)
    rows, corrupt = sp.read_ledger()
    calls = {r["call_id"]: r for r in rows if r.get("kind") == "call" and r.get("call_id")
             and str(r.get("at", "")) >= cutoff}
    outcomes = {r["call_id"]: r for r in rows if r.get("kind") == "outcome" and r.get("call_id")}
    jobs = [r for r in rows if r.get("kind") == "job" and str(r.get("at", "")) >= cutoff]
    groups = _agg(calls, outcomes, jobs, lambda r: (r.get("op", "-"), r.get("trigger", "-")))
    print(f"USAGE_WINDOW:days={args.days}|since={cutoff}")
    for (op, trig), g in sorted(groups.items()):
        print(f"USAGE:local|{op}|{trig}|jobs={g['jobs']}|calls={g['calls']}"
              f"|failed_calls={g['failed_calls']}|unsettled={g['unsettled']}"
              f"|in={_fmt(*g['in'])}|out={_fmt(*g['out'])}|cost={_fmt(*g['cost'], 6)}"
              f"|wall={_fmt(*g['wall'], 3)}")
    if corrupt:
        print(f"LEDGER_CORRUPT:usage.jsonl|{len(corrupt)}")
    try:
        store = rst.Store(root)
        snap = store.read()
    except rst.ProjectUnresolved:
        print("USAGE:store|unavailable|project_unresolved")
        return 0
    per = {}
    for path, rec in snap.files.items():
        parsed = rs.parse_store_path(path)
        if not parsed or parsed[0] not in ("records", "obsolescence"):
            continue
        run = rec.get("run", {})
        if str(run.get("at", "")) < cutoff:
            continue
        op = "relations" if parsed[0] == "records" else "obsolescence"
        g = per.setdefault((op, run.get("trigger", "-")),
                           {"records": 0, "in": [0, 0], "out": [0, 0], "cost": [0.0, 0], "wall": [0.0, 0]})
        g["records"] += 1
        usage = rec.get("usage") or {}
        for f, src in (("in", "input_tokens"), ("out", "output_tokens"),
                       ("cost", "cost_usd"), ("wall", "wall_s")):
            v = usage.get(src)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                g[f][0] += v
            else:
                g[f][1] += 1
    print(f"STORE:{snap.state}")
    for (op, trig), g in sorted(per.items()):
        print(f"USAGE:store|{op}|{trig}|records={g['records']}|in={_fmt(*g['in'])}"
              f"|out={_fmt(*g['out'])}|cost={_fmt(*g['cost'], 6)}|wall={_fmt(*g['wall'], 3)}")
    return 0


def cmd_ledgers(root, args):
    if not args.export:
        sys.stderr.write("ait relations ledgers: only --export is supported\n")
        return 1
    sd = rw.state_dir(root)
    sp = rsp.Spool(sd)
    host = socket.gethostname()
    for name in ("usage", "pull", "notify"):
        path = os.path.join(sd, f"{name}.jsonl")
        if not os.path.exists(path):
            continue
        rows, corrupt = sp.read_ledger(path)
        for row in rows:
            out = {"host": host, "ledger": name}
            out.update(row)
            print(json.dumps(out, sort_keys=True))
        for n in corrupt:
            print(json.dumps({"host": host, "ledger": name, "corrupt_line": n}, sort_keys=True))
    return 0


def cmd_unblock(root, args):
    """Resolve a task's unresolved invocations of ONE operation; it unblocks only
    when none of that operation's remains. Guards are per ``(op, task)``: clearing
    the ``relations`` guards never touches an ``obsolescence`` guard, and vice versa.
    """
    sp = rsp.Spool(rw.state_dir(root))
    tid = _tid(args.id)
    op = getattr(args, "op", None) or rw.OP
    if op not in rw.OPS_IMPLEMENTED:
        sys.stderr.write(f"ait relations unblock: unknown --op {op!r}\n")
        return 1
    entries = sp.guard(op, tid)
    if not entries:
        print(f"NO_GUARD:t{tid}")
        return 0
    if args.force:
        for entry in entries:
            sp.clear_guard(op, tid, entry["_inv"])
            sp.log_unblock(op, tid, f"forced:{entry['_inv']}")
        sp.log(f"UNBLOCKED:t{tid}|forced (human assertion) {len(entries)} invocation(s)")
        print(f"UNBLOCKED:t{tid}|forced")
        rw.start_worker_detached(root, sp)
        return 0
    remaining = []
    for entry in entries:
        agent = entry.get("agent")
        if not agent:
            remaining.append((entry, "no_pgid (use --force once you know it ended)"))
            continue
        verdict, why = (rw.end_or_kill(agent) if args.kill else rw.agent_ended(agent))
        if verdict == "ended":
            sp.clear_guard(op, tid, entry["_inv"])
            sp.log_unblock(op, tid, f"ended:{why}:{entry['_inv']}")
        else:
            remaining.append((entry, f"{why}|pgid={agent.get('pgid')}"))
    if not remaining:
        sp.log(f"UNBLOCKED:t{tid}|ended")
        print(f"UNBLOCKED:t{tid}|ended")
        rw.start_worker_detached(root, sp)
        return 0
    print(f"STILL_UNRESOLVED:t{tid}|{remaining[0][1]}|remaining={len(remaining)}")
    return 3


def _commit_config(root):
    rel = os.path.join(os.environ.get("TASK_DIR", "aitasks"), "metadata", "project_config.yaml")
    script = os.path.join(rw.SCRIPTS, "aitask_metadata_commit.sh")
    proc = subprocess.run([script, rel], cwd=root, capture_output=True, text=True)
    line = (proc.stdout.strip().splitlines() or [""])[-1]
    return proc.returncode, line


def _state_line(root):
    cfg = rcfg.load(root)
    if not cfg.enabled:
        return "RELATIONS:disabled"
    return f"RELATIONS:enabled({rw.agent_string(root) or 'unresolved'}, cap {cfg.max_jobs_per_day}/day)"


def cmd_enable(root, args, value):
    try:
        lines = rcfg.enable(root) if value else (rcfg.set_enabled(root, False) or ["ENABLED_SET:false"])
    except rcfg.ProjectUnresolved as exc:
        print(f"PROJECT_UNRESOLVED:{exc}")
        return 1
    except rcfg.ConfigWriteError as exc:
        print(f"WRITE_FAILED:{exc}")
        return 1
    print("\n".join(lines))
    rc, line = _commit_config(root)
    print(f"COMMIT:{line or 'none'}")
    print(_state_line(root))
    if value:
        print("NOTE:background analysis runs headless Claude print mode, which bills at a higher "
              "per-token rate; it is capped per host per day (relations.max_jobs_per_day)")
    return 0 if rc in (0, 2) and not line.startswith(("FAILED", "REFUSED")) else 1

# ================================================================ t1981_5

def _consumer_store(root):
    """``(store, None)``, or ``(None, lines)`` for a disabled project with no project.name."""
    try:
        return rst.Store(root), None
    except rst.ProjectUnresolved:
        if not rcfg.load(root).enabled:
            return None, ["RELATIONS_STATE:disabled", "STORE:unreachable:project_unresolved",
                          f"SUMMARY:{rc.DISABLED_TEXT}"]
        raise


def _snap(store, relations_state):
    # A disabled project never pays a network fetch: local data only.
    return store.read(no_fetch=(relations_state == "disabled"))


def cmd_related_work(root, args):
    store, early = _consumer_store(root)
    if store is None:
        print("\n".join(early + ["RELATED_WORK:0"]))
        return 0
    since = None
    if args.since is not None:
        since = rc.parse_time(args.since)
        if since is None:
            sys.stderr.write(f"ait relations related-work: unparseable --since {args.since!r}\n")
            return 1
    tid = store.ref(args.id)
    state = store.relations_state()
    snap = _snap(store, state)
    local = store.local_id(store.canonical_ref(tid))
    checked = rc.now_utc()
    ref_ts, ref_src = (since, "since") if since is not None else (None, "n/a")
    if args.point != "note" and local is not None:
        ref_ts, ref_src = rc.reference_time(
            store, snap, local, args.point, since,
            lock_reader=lambda t: rc.read_lock_time(root, t))
    changes = rc.Changes(root)
    items, more, before = rc.related_work(store, snap, tid, args.point, ref_ts, changes,
                                          extract_dir=os.path.join(store.state_dir, "archived-plans"))
    analysis = store.analysis_line(tid, snap, state)
    summary = rc.plain_summary(state, snap.state, analysis)
    # D9 pick-time display: the task's OWN obsolescence band, when medium or
    # higher and not dismissed at its current evidence digest. Advisory only.
    obsolescence = None
    if args.point == "pick" and local is not None:
        import obsolete_cli
        obsolescence = obsolete_cli.pick_view(root, store, snap, local)
    if args.log and (state != "disabled" or items):
        base = rc.ledger_base(store, tid)
        for it in items:
            row = dict(base, point=args.point, group=it.group, relation=rc._rel_key(it.rel),
                       freshness=it.rel.freshness, confirmation=it.confirmation,
                       end=it.end.label(), outcome="shown")
            if it.covered_by_note:
                row["covered_by_note"] = it.covered_by_note
            rc.append_ledger(store.state_dir, "pull", row)
        rc.append_ledger(store.state_dir, "pull", dict(
            base, kind="summary", point=args.point, relations_state=state, store=snap.state,
            analysis=analysis, shown=len(items), more=more, reference=rc.iso(ref_ts)))
    if args.json:
        print(json.dumps({
            "relations_state": state, "store": snap.state, "analysis": analysis,
            "summary": summary, "checked_at": rc.iso(checked),
            "reference": {"at": rc.iso(ref_ts) if ref_ts else None, "source": ref_src},
            "task": store.canonical_ref(tid), "corrupt": snap.corrupt,
            "items": [rc.item_dict(it, store) for it in items], "more": more,
            "before_reference": before, "obsolescence": obsolescence},
            indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    lines = _state_lines(store, snap, [tid], state)
    lines += [f"SUMMARY:{summary}", f"CHECKED_AT:{rc.iso(checked)}",
              f"REFERENCE:{rc.iso(ref_ts) if ref_ts else 'unknown'}|{ref_src}"]
    if obsolescence is not None:
        import obsolete_cli
        lines += obsolete_cli.pick_lines(obsolescence)
    for it in items:
        lines += rc.item_lines(it, store)
    if more:
        lines.append(f"MORE:{more}")
    if before:
        lines.append(f"BEFORE_REFERENCE:{before}")
    if not items:
        lines.append("RELATED_WORK:0")
    print("\n".join(lines))
    return 0


def cmd_notify_candidates(root, args):
    store, early = _consumer_store(root)
    run_id = uuid.uuid4().hex
    if store is None:
        print("\n".join(early + ["ANALYSIS_STATE:disabled", f"RUN_ID:{run_id}",
                                 "PUSH_NONE:disabled"]))
        return 0
    tid = store.ref(args.id)
    local = store.local_id(store.canonical_ref(tid))
    if local is None:
        sys.stderr.write("ait relations notify-candidates: the source must be a task of this project\n")
        return 1
    state, snap = analysis_state(store, local, args.expect_plan)
    rstate = store.relations_state()
    if snap is None:
        snap = _snap(store, rstate)
    rec = snap.files.get(rs.store_path("records", local))
    if isinstance(rec, dict) and rec.get("analysed") and store._record_identity_ok(rec):
        try:
            fresh = store._end_freshness(local, rec["inputs"]["source"], snap)
            record_line = f"RECORD:stage={rec['run']['stage']}|source={fresh}"
            record_stage = rec["run"]["stage"]
        except (KeyError, TypeError):
            record_line, record_stage = "RECORD:none", None
    else:
        record_line, record_stage = "RECORD:none", None
    warn = []
    try:
        if args.diff is not None:
            cs = rc.changeset_for_range(root, args.diff)
        else:
            commits = rc.commits_for(root, local, args.rev)
            cs = rc.changeset_for_commits(root, commits, f"commits:{args.rev}")
    except (ValueError, rst.ors.GitError) as exc:
        cs = rc.ChangeSet(f"diff:{args.diff}" if args.diff is not None else f"commits:{args.rev}",
                          [], {}, [], error=str(exc).splitlines()[0][:200])
        warn.append(f"WARN:the change set could not be read ({cs.error}) -- no relation can be confirmed")
    if cs.error is None and cs.empty:
        warn.append(f"WARN:no change found ({cs.origin}) -- no relation can be confirmed; "
                    f"check that the code commits carry (t{local})")
    rows = rc.notify_candidates(store, snap, tid, cs, rstate)
    pushes = [r for r in rows if r.kind == "PUSH"]
    # The all-clear needs BOTH a complete analysis AND a readable, non-empty
    # change set: with no change to confirm against, an empty list is unknown.
    if rstate == "disabled":
        none_line = "PUSH_NONE:disabled"
    elif cs.error:
        none_line = "PUSH_NONE:changeset_unreadable"
    elif cs.empty:
        none_line = "PUSH_NONE:changeset_empty"
    elif state == "complete":
        none_line = "PUSH_NONE:complete"
    else:
        none_line = f"PUSH_NONE:{state}"
    summary = (rc.DISABLED_TEXT if rstate == "disabled"
               else f"{rc.plain_summary(rstate, snap.state, store.analysis_line(tid, snap, rstate))}"
                    f"; {rc.plain_analysis_state(state)}")
    if rstate != "disabled" and cs.error:
        summary += "; the change set could not be read — whether any task is affected is unknown"
    elif rstate != "disabled" and cs.empty:
        summary += "; no change found to confirm against — whether any task is affected is unknown"
    elif state == "complete" and not pushes and rstate != "disabled":
        summary += "; no affected targets"
    if args.log:
        base = rc.ledger_base(store, tid)
        for r in rows:
            rc.append_ledger(store.state_dir, "notify", dict(
                base, run_id=run_id, kind=r.kind.lower(), relation=rc._rel_key(r.rel),
                recipient=r.recipient, reason=r.reason or None, freshness=r.rel.freshness,
                confirmation=r.confirmation, analysis_state=state,
                outcome="offered" if r.kind == "PUSH" else "shown"))
        rc.append_ledger(store.state_dir, "notify", dict(
            base, run_id=run_id, kind="summary", analysis_state=state,
            relations_state=rstate, option=args.option, record_stage=record_stage,
            changeset=cs.origin, changeset_error=cs.error, commits=len(cs.commits),
            push=len(pushes),
            pull=len(rows) - len(pushes)))
    if args.json:
        print(json.dumps({
            "relations_state": rstate, "store": snap.state, "analysis_state": state,
            "record": record_line[len("RECORD:"):], "summary": summary, "run_id": run_id,
            "changeset": {"origin": cs.origin, "commits": cs.commits, "error": cs.error,
                          "files": sorted(cs.paths)},
            "warnings": [w[len("WARN:"):] for w in warn],
            "rows": [rc.row_dict(r, store) for r in rows],
            "push_none": None if pushes else none_line[len("PUSH_NONE:"):]},
            indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    lines = _state_lines(store, snap, [tid], rstate)
    lines += [f"ANALYSIS_STATE:{state}", record_line, f"SUMMARY:{summary}",
              f"CHANGESET:{len(cs.commits)}|{rc.enc(cs.origin)}"]
    lines += warn
    lines += [f"CHANGED_FILE:{rc.enc(p)}" for p in sorted(cs.paths)]
    lines.append(f"RUN_ID:{run_id}")
    for r in rows:
        lines += rc.row_lines(r, store)
    if not pushes:
        lines.append(none_line)
    print("\n".join(lines))
    return 0


def cmd_notify_outcome(root, args):
    store, early = _consumer_store(root)
    if store is None:
        sdir = rw.state_dir(root)
        task = f"t{_tid(args.id)}"
    else:
        sdir, task = store.state_dir, store.canonical_ref(args.id)
    row = {"at": rc.iso(rc.now_utc()), "host": socket.gethostname(), "task": task,
           "run_id": args.run, "kind": "outcome", "recipient": args.to, "type": args.type,
           "outcome": args.outcome}
    if args.note_id:
        row["note_id"] = args.note_id
    rc.append_ledger(sdir, "notify", row)
    print(f"RECORDED:{args.outcome}|{args.to}")
    return 0


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
    p = sub.add_parser("analyze", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--now", action="store_true")
    p.add_argument("--wait", type=float, default=None)
    p.add_argument("--over-cap", action="store_true")
    for verb in ("stamp", "plan-digest"):
        p = sub.add_parser(verb, allow_abbrev=False)
        p.add_argument("id")
    p = sub.add_parser("analysis-state", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--expect-plan", default=None)
    p = sub.add_parser("usage", allow_abbrev=False)
    p.add_argument("--days", type=int, default=7)
    p = sub.add_parser("ledgers", allow_abbrev=False)
    p.add_argument("--export", action="store_true")
    p = sub.add_parser("unblock", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--kill", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--op", choices=rw.OPS_IMPLEMENTED, default=rw.OP)
    sub.add_parser("enable", allow_abbrev=False)
    sub.add_parser("disable", allow_abbrev=False)
    p = sub.add_parser("related-work", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--point", required=True, choices=rc.POINTS)
    p.add_argument("--since", default=None)
    p.add_argument("--log", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("notify-candidates", allow_abbrev=False)
    p.add_argument("id")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--rev", default="HEAD")
    g.add_argument("--diff", default=None)
    p.add_argument("--expect-plan", default=None)
    p.add_argument("--option", default=None, choices=rc.OPTIONS)
    p.add_argument("--log", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("notify-outcome", allow_abbrev=False)
    p.add_argument("id")
    p.add_argument("--run", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--type", required=True, choices=tuple(rs.TYPES) + ("unconfirmed",))
    p.add_argument("--outcome", required=True, choices=rc.OUTCOMES)
    p.add_argument("--note-id", default=None)
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
        if args.verb in NO_STORE_VERBS:
            root = _root()
            if args.verb in ("enable", "disable"):
                return cmd_enable(root, args, args.verb == "enable")
            return {"analyze": cmd_analyze, "stamp": cmd_stamp, "plan-digest": cmd_plan_digest,
                    "analysis-state": cmd_analysis_state, "usage": cmd_usage,
                    "ledgers": cmd_ledgers, "unblock": cmd_unblock,
                    "related-work": cmd_related_work,
                    "notify-candidates": cmd_notify_candidates,
                    "notify-outcome": cmd_notify_outcome}[args.verb](root, args)
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
