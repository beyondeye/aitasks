#!/usr/bin/env python3
"""relations_worker.py - the relations analysis worker (t1981_3).

Design: aidocs/framework/task_relations.md D5 ("Spool and worker", "The headless
operation", "Usage is measured"), D7, and the "Worker API" section.

Subcommands (all invoked detached by ``aitask_relations_enqueue.sh`` /
``ait relations``; none prints to a caller's terminal)::

    relations_worker.py run <root>                       drain the spool (one worker)
    relations_worker.py enqueue <root> <op> <trigger> <id>
    relations_worker.py stamp-publish <root> <id>        flush, then enqueue plan_approved

Per job, in D5 order (``analyse``): fresh config/Store/TaskIndex and ONE store
snapshot; daily-cap pre-check; source lookup (manual_verification excluded);
the snapshot manifest and the candidate provider (contract:
``relation_candidates_contract``); input digests and snapshot agreement; the
``UP_TO_DATE`` skip; the zero-candidate shortcut; materialized inputs and the
prompt; the unresolved-invocation guard; ``admit()``; the headless op under a
process-group timeout; validation; the store write.

Crash safety: the running entry records ``spawning`` before the agent starts
and ``agent`` (pgid + leader identity) right after; ``recover_running`` (under
the worker lock) proves the previous invocation ended -- killing an orphaned
group if needed -- before any retry, and otherwise writes an unresolved guard
that blocks every new launch for that task.

Test seams (never set in production): ``AIT_RELATIONS_CANDIDATES_CMD``,
``AIT_RELATIONS_AGENT_CMD``, ``AIT_RELATIONS_AGENT_STRING``,
``AIT_RELATIONS_TEST_BARRIER=<point>[,<point>...]:<dir>``.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import socket
import subprocess
import sys
import time
import traceback
import uuid

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import bounded_run  # noqa: E402
import orphan_ref_store as ors  # noqa: E402
import relation_candidates_contract as cc  # noqa: E402
import relations_config as rcfg  # noqa: E402
import relations_schema as rs  # noqa: E402
import relations_spool as rsp  # noqa: E402
import relations_store as rst  # noqa: E402

SCRIPTS = os.path.dirname(_LIB)
CANDIDATES_SCRIPT = os.path.join(SCRIPTS, "aitask_relation_candidates.sh")
CODEAGENT = os.path.join(SCRIPTS, "aitask_codeagent.sh")
PID_ANCHOR = os.path.join(_LIB, "pid_anchor.sh")
PROMPT_TEMPLATE = os.path.join(SCRIPTS, "relations", "prompts", "relations_analysis.md")
OP = "relations"
OPS_IMPLEMENTED = ("relations",)
PROVIDER_TIMEOUT_S = 300
KILL_GRACE_S = 5.0
MAX_TIMEOUT_RETRIES = 1
MAX_INTERRUPTIONS = 2
MAX_FULL_READS = 8


class JobFailed(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class JobHeld(Exception):
    """Back to the queue with a hold (``capped`` / ``blocked_unresolved``)."""

    def __init__(self, state, outcome):
        super().__init__(outcome)
        self.state, self.outcome = state, outcome


class JobRetry(Exception):
    """A timeout: requeue once, then fail."""


class JobSkipped(Exception):
    """Analysis was switched off (project or host) after the job was queued."""

    def __init__(self, outcome):
        super().__init__(outcome)
        self.outcome = outcome


def switched_off(root):
    """``SKIPPED:disabled`` / ``SKIPPED:host_off`` when a paid run must not start, else None.

    Read fresh (never from the job's earlier config load): an opt-out made while
    work was queued -- or while this job was gathering candidates -- must stop it.
    """
    if not rcfg.load(root).enabled:
        return "SKIPPED:disabled"
    if os.environ.get("AIT_RELATIONS") == "0":
        return "SKIPPED:host_off"
    return None


class Refused(Exception):
    """A dry run that may not launch an agent (``CAP_REACHED`` / ``BLOCKED_UNRESOLVED``)."""


# ------------------------------------------------------------------- seams

def _test_hook(point: str, **ctx) -> None:
    """Barrier seam: with AIT_RELATIONS_TEST_BARRIER=<points>:<dir>, announce
    ``<dir>/<point>.reached`` and wait (bounded) for ``<dir>/<point>.release``."""
    spec = os.environ.get("AIT_RELATIONS_TEST_BARRIER")
    if not spec or ":" not in spec:
        return
    points, directory = spec.rsplit(":", 1)
    if point not in points.split(","):
        return
    with open(os.path.join(directory, f"{point}.reached"), "w") as fh:
        fh.write(json.dumps({"pid": os.getpid(), **{k: str(v) for k, v in ctx.items()}}))
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if os.path.exists(os.path.join(directory, f"{point}.release")):
            return
        time.sleep(0.05)


def _cmd_from_env(name):
    value = os.environ.get(name)
    return shlex.split(value) if value else None


# -------------------------------------------------------------------- git

def _git(repo, *args, check=True):
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise JobFailed(f"GIT_ERROR:{args[0]}:{proc.stderr.strip()[:120]}")
    return proc


def state_dir(root) -> str:
    return os.path.join(ors.git_common_dir(root), "aitask-relations")


def data_repo(root) -> str:
    """The git toplevel holding the task data (``.aitask-data`` in branch mode)."""
    task_dir = os.path.realpath(os.path.join(root, os.environ.get("TASK_DIR", "aitasks")))
    proc = subprocess.run(["git", "-C", task_dir, "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise JobFailed("DATA_REPO_UNRESOLVED")
    return proc.stdout.strip()


def _rel_dir(root, drepo, env, default):
    return os.path.relpath(os.path.realpath(os.path.join(root, os.environ.get(env, default))), drepo)


def _name_patterns(tid):
    if "_" in tid:
        parent, child = tid.split("_", 1)
        return parent, re.compile(rf"^t{parent}_{child}_.*\.md$"), re.compile(rf"^p{parent}_{child}_.*\.md$")
    return tid, re.compile(rf"^t{tid}_(?!\d+_).*\.md$"), re.compile(rf"^p{tid}_(?!\d+_).*\.md$")


def _find_at_commit(drepo, commit, base_rel, tid, kind):
    parent, task_re, plan_re = _name_patterns(tid)
    name_re = task_re if kind == "task" else plan_re
    sub = f"{'t' if kind == 'task' else 'p'}{parent}"
    where = f"{base_rel}/{sub}" if "_" in tid else base_rel
    proc = _git(drepo, "ls-tree", "--name-only", f"{commit}:{where}", check=False)
    if proc.returncode != 0:
        return None
    for name in proc.stdout.splitlines():
        if name_re.match(name):
            return f"{where}/{name}"
    return None


def file_at_commit(root, drepo, commit, tid, kind):
    """Text of the task (``kind='task'``) or plan file of ``tid`` at ``commit``; None if absent."""
    base = (_rel_dir(root, drepo, "TASK_DIR", "aitasks") if kind == "task"
            else _rel_dir(root, drepo, "PLAN_DIR", "aiplans"))
    path = _find_at_commit(drepo, commit, base, tid, kind)
    if path is None:
        return None
    proc = _git(drepo, "show", f"{commit}:{path}", check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


# ------------------------------------------------------------- the stamp

class StampError(Exception):
    pass


def write_stamp(root, tid):
    """The D2 approval stamp, written synchronously into the outbox.

    Returns the plan digest, or None when the project has analysis disabled.
    """
    if not rcfg.load(root).enabled:
        return None
    try:
        store = rst.Store(root)
    except rst.ProjectUnresolved as exc:
        raise StampError(f"project_unresolved:{exc}") from None
    tid = rs.norm_id(tid)
    entry = store.index.lookup(tid)
    if entry is None or not entry.created_at:
        raise StampError("task_not_found")
    try:
        drepo = data_repo(root)
    except JobFailed as exc:
        raise StampError(exc.reason.lower()) from None
    head = _git(drepo, "rev-parse", "HEAD", check=False).stdout.strip()
    if not head:
        raise StampError("no_data_head")
    body = file_at_commit(root, drepo, head, tid, "task")
    plan = file_at_commit(root, drepo, head, tid, "plan")
    if body is None:
        raise StampError("task_not_committed")
    if plan is None:
        raise StampError("plan_not_committed")
    dig = rs.digests(body, plan)
    rec = {"task": store.ref(tid), "task_created_at": entry.created_at,
           "approved_at": rsp.utc_iso(), "data_commit": head,
           "body_sha256": dig["body_sha256"], "plan_sha256": dig["plan_sha256"]}
    reports = store.write(rs.store_path("approvals", tid), rec, flush=False)
    if not reports or not reports[0].startswith("OUTBOX:"):
        raise StampError((reports[0] if reports else "no_report").lower())
    return dig["plan_sha256"]


def plan_digest(root, tid):
    """Digest of the plan as committed at the task-data HEAD, or None (no plan)."""
    drepo = data_repo(root)
    head = _git(drepo, "rev-parse", "HEAD").stdout.strip()
    plan = file_at_commit(root, drepo, head, rs.norm_id(tid), "plan")
    return None if plan is None else rs.digests("", plan)["plan_sha256"]


# ----------------------------------------------------------- inputs

class Inputs:
    __slots__ = ("ref", "tid", "created_at", "body", "plan", "digests", "stamped")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _issue_type(text):
    import task_yaml
    try:
        parsed = task_yaml.parse_frontmatter(text or "")
    except Exception:
        return None
    return parsed[0].get("issue_type") if parsed else None


def valid_stamps(store, snap) -> dict:
    """``{tid: stamp}`` for every visible stamp whose identity is the live task's."""
    out = {}
    for path, rec in snap.files.items():
        parsed = rs.parse_store_path(path)
        if not parsed or parsed[0] != "approvals":
            continue
        tid = parsed[1]
        live = store.index.live_created_at(tid)
        if live is not None and rec.get("task_created_at") == live:
            out[tid] = rec
    return out


def task_inputs(root, store, drepo, stamps, tid):
    """Analysed inputs of ``tid`` under the D5 rule; None when the task is unknown."""
    entry = store.index.lookup(tid)
    if entry is None or entry.text is None:
        return None
    stamp = stamps.get(tid)
    if stamp is not None:
        plan_raw = file_at_commit(root, drepo, stamp["data_commit"], tid, "plan")
        if plan_raw is None:
            raise JobFailed(f"STAMP_PLAN_UNREADABLE:{store.ref(tid)}")
    else:
        plan_raw = store.index._find_plan(tid)
        if plan_raw is rst.UNREADABLE:
            raise JobFailed(f"PLAN_UNREADABLE:{store.ref(tid)}")
    dig = rs.digests(entry.text, plan_raw)
    return Inputs(ref=store.ref(tid), tid=tid, created_at=entry.created_at,
                  body=rs.normalize_body(entry.text),
                  plan=rs.normalize_plan(plan_raw) if plan_raw is not None else None,
                  digests=dig, stamped=stamp is not None)


# --------------------------------------------------------- the provider

def run_provider(root, tid, cap, manifest_path):
    cmd = _cmd_from_env("AIT_RELATIONS_CANDIDATES_CMD")
    if cmd is None:
        if not os.path.exists(CANDIDATES_SCRIPT):
            raise JobFailed("CANDIDATES_UNAVAILABLE:no_provider")
        cmd = [CANDIDATES_SCRIPT]
    argv = cmd + [tid, "--json", "--cap", str(cap), "--snapshot", manifest_path]
    try:
        res = bounded_run.run_bounded(argv, PROVIDER_TIMEOUT_S, cwd=str(root))
    except subprocess.TimeoutExpired:
        raise JobFailed("PROVIDER_ERROR:timeout") from None
    except OSError as exc:
        raise JobFailed(f"CANDIDATES_UNAVAILABLE:{exc.__class__.__name__}") from None
    if res.returncode != 0:
        raise JobFailed(f"PROVIDER_ERROR:exit_{res.returncode}")
    try:
        obj = cc.validate(cc.parse_json_stdout(res.stdout))
    except cc.ContractError as exc:
        reason = str(exc)
        if reason.startswith("core_missing:"):
            raise JobFailed(f"CANDIDATES_UNAVAILABLE:{reason}") from None
        if reason.startswith("malformed:"):
            raise JobFailed(f"PROVIDER_ERROR:{reason}"[:200]) from None
        raise JobFailed(f"PROVIDER_ERROR:malformed:{reason}"[:200]) from None
    return obj, res.stderr


def gather(root, store, drepo, stamps, tid, cap, work, log):
    """Provider output + analysed inputs that provably agree (one re-run on mismatch)."""
    manifest = cc.snapshot_manifest(drepo, store.ref(tid),
                                    {store.ref(t): s["data_commit"] for t, s in stamps.items()})
    manifest_path = os.path.join(work, "snapshot.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    last = None
    for _attempt in range(2):
        obj, stderr = run_provider(root, tid, cap, manifest_path)
        if stderr.strip():
            log(f"provider stderr t{tid}: {stderr.strip()[:500]}")
        if obj["source"] != store.ref(tid):
            raise JobFailed(f"PROVIDER_ERROR:malformed:source {obj['source']} is not {store.ref(tid)}")
        source = task_inputs(root, store, drepo, stamps, tid)
        cands, mismatch, dropped = {}, None, []
        if cc.input_echo(obj, obj["source"]) != source.digests:
            mismatch = obj["source"]
        for ref in cc.all_refs(obj):
            ctid = store.local_id(ref)
            inp = task_inputs(root, store, drepo, stamps, ctid) if ctid else None
            if inp is None or not inp.created_at:
                dropped.append(ref)
                continue
            if mismatch is None and cc.input_echo(obj, ref) != inp.digests:
                mismatch = ref
            cands[ref] = inp
        if mismatch is None:
            if dropped:
                log(f"t{tid}: dropped candidates without a live local identity: {','.join(dropped)}")
            return obj, source, cands, dropped
        last = mismatch
        log(f"t{tid}: snapshot mismatch on {mismatch}; re-running the provider once")
    raise JobFailed(f"SNAPSHOT_MISMATCH:{last}")


def _without(obj, dropped):
    if not dropped:
        return obj
    gone = set(dropped)
    out = dict(obj)
    out["candidates"] = [c for c in obj["candidates"] if c["ref"] not in gone]
    by_class = {k: [r for r in v if r not in gone] for k, v in obj["truncated"]["by_class"].items()}
    by_class = {k: v for k, v in by_class.items() if v}
    out["truncated"] = {"count": sum(len(v) for v in by_class.values()), "by_class": by_class,
                        "inputs": {r: p for r, p in obj["truncated"]["inputs"].items() if r not in gone}}
    return out


# -------------------------------------------------------- record pieces

def candidate_entries(cands: dict) -> list:
    return sorted(({"ref": ref, "created_at": inp.created_at,
                    "body_sha256": inp.digests["body_sha256"],
                    "plan_sha256": inp.digests["plan_sha256"]} for ref, inp in cands.items()),
                  key=lambda c: c["ref"])


def up_to_date(store, snap, tid, stage, source, entries, coverage, screening) -> bool:
    rec = snap.files.get(rs.store_path("records", tid))
    if not isinstance(rec, dict) or not rec.get("analysed") or not store._record_identity_ok(rec):
        return False
    try:
        return (rec["run"]["stage"] >= stage
                and rec["inputs"]["source"] == source.digests
                and sorted(rec["inputs"]["candidates"], key=lambda c: c["ref"]) == entries
                and sorted(rec.get("coverage", {}).get("missing_sources", [])) == sorted(coverage)
                and rec["inputs"].get("screening_sha256") == screening and screening is not None)
    except (KeyError, TypeError):
        return False


def _code_base(root):
    proc = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def agent_string(root):
    if os.environ.get("AIT_RELATIONS_AGENT_CMD"):
        return os.environ.get("AIT_RELATIONS_AGENT_STRING", "test/stub")
    proc = subprocess.run([CODEAGENT, "resolve", OP], capture_output=True, text=True, cwd=str(root))
    for line in proc.stdout.splitlines():
        if line.startswith("AGENT_STRING:"):
            return line.split(":", 1)[1].strip()
    return ""


def build_record(store, tid, job, stage, source, entries, coverage, screening, provider,
                 considered, relations, usage, drepo, root, agent):
    rec = {
        "schema": rs.SCHEMA, "task": store.ref(tid), "task_created_at": source.created_at,
        "analysed": True,
        "run": {"id": uuid.uuid4().hex, "trigger": job.get("trigger", "manual"), "stage": stage,
                "at": rsp.utc_iso(), "host": socket.gethostname(), "agent_string": agent,
                "code_base": _code_base(root),
                "data_base": _git(drepo, "rev-parse", "HEAD", check=False).stdout.strip(),
                "candidate_provider": provider},
        "inputs": {"source": dict(source.digests), "candidates": entries,
                   "screening_sha256": screening},
        "considered": considered, "relations": relations,
        "usage": usage,
    }
    if coverage:
        rec["coverage"] = {"missing_sources": sorted(coverage)}
    rs.validate("records", rs.store_path("records", tid), rec)
    return rec


# ------------------------------------------------------- prompt + inputs

def materialize(work, source, cands):
    """Write the analysed (normalized) content the agent may read in full."""
    base = os.path.join(work, "inputs")

    def put(sub, inp):
        d = os.path.join(base, sub)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "body.md"), "w", encoding="utf-8") as fh:
            fh.write(inp.body)
        if inp.plan is not None:
            with open(os.path.join(d, "plan.md"), "w", encoding="utf-8") as fh:
                fh.write(inp.plan)
        return d

    paths = {source.ref: put("source", source)}
    for ref, inp in cands.items():
        paths[ref] = put(os.path.join("candidates", f"t{inp.tid}"), inp)
    return base, paths


def compose_prompt(work, obj, source, cands, paths):
    with open(PROMPT_TEMPLATE, encoding="utf-8") as fh:
        template = fh.read()

    def files(ref):
        d = paths[ref]
        plan = os.path.join(d, "plan.md")
        return f"{os.path.join(d, 'body.md')}" + (f", {plan}" if os.path.exists(plan) else " (no plan)")

    lines = ["", "---", "", "## This job", "",
             f"- Source task: `{source.ref}` ({'approved plan' if source.stamped else 'working-tree plan'})",
             f"- Source files: {files(source.ref)}",
             f"- Input directory (the ONLY place for full reads): `{os.path.join(work, 'inputs')}`",
             f"- Full reads allowed: at most {MAX_FULL_READS}",
             f"- Candidate provider: `{obj['provider']['path']}`",
             f"- Sources not answered (partial coverage): {', '.join(obj['coverage']['missing_sources']) or 'none'}",
             "", "### Candidates (cards and evidence)", ""]
    full = [c for c in obj["candidates"] if c["ref"] in cands]
    if not full:
        lines.append("(none)")
    for cand in full:
        lines.append(f"#### `{cand['ref']}` -- sources: {', '.join(cand['sources'])}")
        lines.append(f"Files: {files(cand['ref'])}")
        lines.append("")
        lines.append(cand["card"].strip() or "(no card)")
        lines.append("")
        for ev in cand["evidence"]:
            where = "/".join(str(x) for x in (ev.get("section"), ev.get("line")) if x is not None)
            lines.append(f"- evidence `{ev['source']}`{' (' + where + ')' if where else ''}: {ev['detail']}")
        lines.append("")
    trunc = {k: [r for r in v if r in cands] for k, v in obj["truncated"]["by_class"].items()}
    trunc = {k: v for k, v in trunc.items() if v}
    lines.append(f"### TRUNCATED: {sum(len(v) for v in trunc.values())}")
    lines.append("")
    for cls in sorted(trunc):
        lines.append(f"- {cls}: " + ", ".join(f"`{r}` ({files(r)})" for r in trunc[cls]))
    lines.append("")
    lines.append("Every candidate ref above (full or truncated) is a valid relation end; no other is.")
    text = template.rstrip("\n") + "\n" + "\n".join(lines) + "\n"
    path = os.path.join(work, "prompt.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


# ------------------------------------------------------- agent output

def _usage(outer, wall):
    u = outer.get("usage") if isinstance(outer, dict) else None
    u = u if isinstance(u, dict) else {}
    parts = [u.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")]
    ints = [p for p in parts if isinstance(p, int) and not isinstance(p, bool)]
    out_tok = u.get("output_tokens")
    cost = outer.get("total_cost_usd") if isinstance(outer, dict) else None
    return {"input_tokens": sum(ints) if ints else None,
            "output_tokens": out_tok if isinstance(out_tok, int) and not isinstance(out_tok, bool) else None,
            "cost_usd": cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None,
            "wall_s": round(wall, 3)}


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*)\n```\s*$", re.S)


def parse_agent_output(stdout, wall):
    """``(payload, usage)``; raises JobFailed. The payload is exactly one JSON object."""
    try:
        outer = json.loads(stdout)
    except (ValueError, TypeError):
        raise JobFailed("AGENT_ERROR:unparseable_output") from None
    usage = _usage(outer, wall)
    if not isinstance(outer, dict):
        raise JobFailed("AGENT_ERROR:unparseable_output")
    if outer.get("is_error") is True or outer.get("subtype", "success") != "success":
        detail = str(outer.get("subtype") or outer.get("stop_reason") or "is_error")[:80]
        raise _WithUsage(JobFailed(f"AGENT_ERROR:{detail}"), usage)
    text = outer.get("result")
    if not isinstance(text, str):
        raise _WithUsage(JobFailed("INVALID_OUTPUT:no result text"), usage)
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    try:
        payload = cc.parse_json_stdout(text)
    except cc.ContractError as exc:
        raise _WithUsage(JobFailed(f"INVALID_OUTPUT:{str(exc).replace('malformed:', '')}"), usage) from None
    return payload, usage


class _WithUsage(Exception):
    def __init__(self, failure, usage):
        super().__init__(failure.reason)
        self.failure, self.usage = failure, usage


def canonical_payload(store, payload, cand_refs: set):
    """Canonicalize refs; fail closed on any shape the record cannot carry."""
    if not isinstance(payload, dict) or set(payload) - {"considered", "relations"} \
            or "relations" not in payload:
        raise JobFailed("INVALID_OUTPUT:expected {considered, relations}")
    considered = payload.get("considered", [])
    relations = payload["relations"]
    if not isinstance(considered, list) or not isinstance(relations, list):
        raise JobFailed("INVALID_OUTPUT:considered/relations must be lists")
    try:
        out_c = []
        for item in considered:
            if not isinstance(item, dict):
                raise JobFailed("INVALID_OUTPUT:considered item is not an object")
            item = dict(item)
            item["ref"] = store.canonical_ref(item.get("ref", ""))
            if item["ref"] not in cand_refs:
                raise JobFailed(f"INVALID_OUTPUT:considered ref {item['ref']} is not a candidate")
            out_c.append(item)
        out_r = []
        for rel in relations:
            if not isinstance(rel, dict):
                raise JobFailed("INVALID_OUTPUT:relation is not an object")
            rel = dict(rel)
            rel["from"] = store.canonical_ref(rel.get("from", ""))
            rel["to"] = store.canonical_ref(rel.get("to", ""))
            out_r.append(rel)
    except rs.SchemaError as exc:
        raise JobFailed(f"INVALID_OUTPUT:{exc}"[:200]) from None
    return out_c, out_r


# -------------------------------------------------------- liveness

def _pid_anchor(fn, *args):
    proc = subprocess.run(["bash", "-c", 'source "$1"; shift; "$@"', "_", PID_ANCHOR, fn, *args],
                          capture_output=True, text=True, timeout=30)
    return proc.stdout.strip()


def leader_identity(pid):
    out = _pid_anchor("get_pid_identity", str(pid)) or "none -"
    kind, _, tok = out.partition(" ")
    return kind, tok or "-"


def agent_ended(agent):
    """``(verdict, why)``: ``ended`` | ``alive`` | ``unknown``."""
    if not isinstance(agent, dict) or not agent.get("pgid"):
        return "unknown", "no_pgid"
    pgid, pid = int(agent["pgid"]), int(agent.get("leader_pid") or agent["pgid"])
    try:
        os.kill(pid, 0)
        exists = True
    except ProcessLookupError:
        exists = False
    except PermissionError:
        exists = True
    if not exists:
        # A pid is never reused while a process group of that id exists, so with
        # the leader gone the group probe is definitive for OUR group.
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return "ended", "group_gone"
        except PermissionError:
            return "unknown", "eperm"
        return "alive", "orphaned_members"
    verdict = _pid_anchor("lock_holder_liveness", str(pid), str(agent.get("identity", "-")),
                          str(agent.get("identity_kind", "proc")))
    if verdict == "dead":
        return "ended", "pid_reused"
    if verdict == "alive":
        return "alive", "leader_alive"
    return "unknown", "weak_identity"


def end_or_kill(agent):
    verdict, why = agent_ended(agent)
    if verdict == "alive":
        if bounded_run.kill_process_group_by_id(int(agent["pgid"]), KILL_GRACE_S):
            return "ended", "killed"
        return "unknown", "kill_unconfirmed"
    return verdict, why


# --------------------------------------------------------------- analyse

def analyse(root, sp, job, *, dry_run=False, log=None):
    """One job, D5 order. Returns ``(outcome, record_or_None)``."""
    log = log or sp.log
    tid = rs.norm_id(job["task"])
    cfg = rcfg.load(root)
    if not dry_run:
        off = switched_off(root)
        if off:
            raise JobSkipped(off)
    try:
        store = rst.Store(root)
    except rst.ProjectUnresolved as exc:
        raise JobFailed(f"PROJECT_UNRESOLVED:{exc}"[:200]) from None
    if not dry_run and not job.get("over_cap") and sp.cap_reached(OP, cfg.max_jobs_per_day):
        raise JobHeld(rsp.HOLD_CAPPED, "CAP_REACHED")
    entry = store.index.lookup(tid)
    if entry is None:
        raise JobFailed("TASK_NOT_FOUND")
    if not entry.created_at:
        raise JobFailed("IDENTITY_UNKNOWN")
    if _issue_type(entry.text) == "manual_verification":
        return "EXCLUDED", None
    snap = store.read()
    _test_hook("after_snapshot", task=tid)
    drepo = data_repo(root)
    stamps = valid_stamps(store, snap)
    run_id = uuid.uuid4().hex
    work = sp.new_work_dir(run_id)
    obj, source, cands, dropped = gather(root, store, drepo, stamps, tid, cfg.candidate_cap, work, log)
    obj = _without(obj, dropped)
    stage = 2 if source.stamped else 1
    screening = cc.screening_digest(obj)
    entries = candidate_entries(cands)
    coverage = list(obj["coverage"]["missing_sources"])
    provider = obj["provider"]["path"]
    if not dry_run and up_to_date(store, snap, tid, stage, source, entries, coverage, screening):
        return "UP_TO_DATE", None
    agent = agent_string(root)
    if not cands:
        rec = build_record(store, tid, job, stage, source, entries, coverage, screening, provider,
                           [], [], {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0, "wall_s": 0},
                           drepo, root, agent)
        if dry_run:
            return "ANALYSED_EMPTY", rec
        return _write(store, tid, rec), rec
    _base, paths = materialize(work, source, cands)
    prompt = compose_prompt(work, obj, source, cands, paths)
    # The shared pre-admission boundary. First reconcile this task's previews:
    # one that was alive at startup may have lost its CLI since (its agent
    # ended now, or turned into a guard). Then the unresolved-invocation guard.
    recover_previews(sp, log=log, task=tid)
    outstanding = []
    for entry in sp.guard(OP, tid):
        verdict, why = agent_ended(entry.get("agent")) if entry.get("agent") else ("unknown", "no_pgid")
        if verdict == "ended":
            sp.clear_guard(OP, tid, entry["_inv"])
            log(f"UNRESOLVED_CLEARED:t{tid}|{entry['_inv']}|ended({why})")
        else:
            outstanding.append(entry)
    if outstanding:  # every invocation must be resolved before a new launch
        if dry_run:
            raise Refused("BLOCKED_UNRESOLVED")
        raise JobHeld(rsp.HOLD_BLOCKED, "BLOCKED_UNRESOLVED")
    # The opt-out switches, re-read immediately before paid admission. A dry run
    # is the deliberate exception (an explicit, cap-admitted preview).
    if not dry_run:
        off = switched_off(root)
        if off:
            raise JobSkipped(off)
    _test_hook("before_admit", task=tid)
    try:
        # The final guard check and the paid reservation are one critical
        # section relative to guard writers (spool.lock); the liveness cleanup
        # above stays outside it.
        call_id = sp.admit_unguarded(OP, tid, job.get("trigger", "manual"), cap=cfg.max_jobs_per_day,
                                     dry_run=dry_run, over_cap=bool(job.get("over_cap")))
    except rsp.Blocked:
        if dry_run:
            raise Refused("BLOCKED_UNRESOLVED") from None
        raise JobHeld(rsp.HOLD_BLOCKED, "BLOCKED_UNRESOLVED") from None
    except rsp.CapReached as exc:
        if dry_run:
            raise Refused(str(exc)) from None
        raise JobHeld(rsp.HOLD_CAPPED, "CAP_REACHED") from None
    # Ownership phases recorded for recovery, for EVERY paid invocation: a
    # worker job in its running entry, a dry run in a preview entry owned by
    # this process. `call_id` alone = admitted, no process can exist yet (safe
    # retry); `spawning` = Popen may be in progress; `agent` = the process
    # group this invocation owns.
    if dry_run:
        kind, tok = leader_identity(os.getpid())
        sp.write_preview(call_id, {"op": OP, "task": tid, "call_id": call_id, "at": rsp.utc_iso(),
                                   "owner": {"pid": os.getpid(), "identity": tok,
                                             "identity_kind": kind}})

        def own(**fields):
            sp.update_preview(call_id, **fields)
    else:
        def own(**fields):
            sp.update_running(job, **fields)
        own(call_id=call_id)
    _test_hook("after_admit", task=tid, call_id=call_id)
    argv = _cmd_from_env("AIT_RELATIONS_AGENT_CMD")
    argv = (argv if argv is not None else [CODEAGENT, "--headless", "invoke", OP]) + \
        [prompt, os.path.join(work, "inputs")]
    own(spawning=call_id)

    def on_start(proc):
        kind, tok = leader_identity(proc.pid)
        own(agent={"pgid": proc.pid, "leader_pid": proc.pid, "identity": tok,
                   "identity_kind": kind, "deadline": time.time() + cfg.job_timeout_s})
        _test_hook("after_spawn", task=tid, pgid=proc.pid)

    settled = {"done": False}

    def settle(outcome, usage=None):
        if not settled["done"]:
            settled["done"] = True
            sp.settle_call(call_id, outcome, usage)

    started = time.monotonic()
    try:
        try:
            res = bounded_run.run_bounded(argv, cfg.job_timeout_s, cwd=str(root), on_start=on_start)
        except subprocess.TimeoutExpired:
            settle("timeout", {"wall_s": round(time.monotonic() - started, 3)})
            raise JobRetry() from None
        finally:
            # The agent's group has ended here (run_bounded reaps it on every
            # path), so the ownership record is released.
            if dry_run:
                sp.remove_preview(call_id)
            else:
                own(spawning=None, agent=None)
        wall = time.monotonic() - started
        with open(os.path.join(work, "agent_stdout.json"), "w", encoding="utf-8") as fh:
            fh.write(res.stdout)
        if res.stderr.strip():
            log(f"agent stderr t{tid}: {res.stderr.strip()[:500]}")
        if res.returncode != 0:
            usage = None
            try:
                usage = _usage(json.loads(res.stdout), wall)
            except (ValueError, TypeError):
                pass
            settle("agent_error", usage)
            raise JobFailed(f"AGENT_ERROR:exit_{res.returncode}")
        try:
            payload, usage = parse_agent_output(res.stdout, wall)
        except _WithUsage as wu:
            settle("agent_error" if wu.failure.reason.startswith("AGENT_ERROR") else "invalid_output",
                   wu.usage)
            raise wu.failure from None
        except JobFailed:
            settle("agent_error")
            raise
        try:
            considered, relations = canonical_payload(store, payload, set(cands))
            rec = build_record(store, tid, job, stage, source, entries, coverage, screening, provider,
                               considered, relations, usage, drepo, root, agent)
        except JobFailed:
            settle("invalid_output", usage)
            raise
        except rs.SchemaError as exc:
            settle("invalid_output", usage)
            raise JobFailed(f"INVALID_OUTPUT:{exc}"[:200]) from None
        settle("ok", usage)
    finally:
        settle("error")
    if dry_run:
        return "ANALYSED", rec
    return _write(store, tid, rec), rec


def _write(store, tid, rec):
    reports = store.write(rs.store_path("records", tid), rec)
    head = reports[0] if reports else "NO_REPORT"
    if head.startswith(("IDENTITY_MISMATCH", "PROJECT_MISMATCH")):
        raise JobFailed(head.split("|", 1)[0])
    if head.startswith("STALE_RUN"):
        return "STALE_RUN"
    retained = [r for r in reports if r.startswith("RETAINED:")]
    return f"ANALYSED({'retained' if retained else 'published'})"


# --------------------------------------------------------------- worker

def recover_previews(sp, log=None, task=None):
    """Settle dry-run invocations whose owning process died (any caller may run it).

    A preview whose owner is provably alive is still in progress and is left
    alone. Otherwise its agent must provably have ended -- killing an orphaned
    group if needed -- before the entry is released; when that cannot be
    established, an unresolved guard blocks every new launch for the task.

    Called at every worker start, at every dry-run start, and at the shared
    PRE-ADMISSION boundary of every paid launch (``task`` = the task about to
    launch), so a preview whose CLI died after those startup scans is still
    accounted for before a replacement agent can start.

    Recovery is SERIALIZED: the whole transition of one entry (re-read, decide,
    kill, settle, account, release) runs under ``recovery.lock``, and the entry
    is re-read under the lock, so concurrent recoverers act on it at most once.
    Settlement and the terminal job row are also idempotent per invocation.
    """
    log = log or sp.log
    for listed in sp.previews():
        name = listed["_name"]
        if task is not None and not listed.get("_corrupt") and listed.get("task") != task:
            continue
        _test_hook("preview_listed", name=name)
        with sp.recovery_lock():
            prev = sp._read(sp.path("previews", name))
            if prev is None:
                continue  # another recoverer (or its owner) already released it
            if prev.get("_corrupt"):
                sp.remove_preview(name)
                log(f"PREVIEW_CORRUPT:{name}")
                continue
            owner = prev.get("owner") or {}
            liveness = _pid_anchor("lock_holder_liveness", str(owner.get("pid", "-")),
                                   str(owner.get("identity", "-")), str(owner.get("identity_kind", "proc")))
            if liveness == "alive":
                continue  # its owner is still running it
            call_id, agent, tid = prev.get("call_id"), prev.get("agent"), prev.get("task")
            op = prev.get("op", OP)
            if prev.get("spawning") or agent:
                verdict, why = end_or_kill(agent) if agent else ("unknown", "spawn_gap")
                if liveness == "unknown" and verdict != "ended":
                    why = f"owner_unknown:{why}"
                if verdict != "ended":
                    pgid = (agent or {}).get("pgid", "-")
                    sp.write_guard(op, tid, {"call_id": call_id, "agent": agent,
                                             "why": f"preview:{why}", "at": rsp.utc_iso()})
                    if call_id:
                        sp.settle_call(call_id, "unresolved")
                    sp.log_job(op, tid, "manual", f"FAILED:INTERRUPTED_UNRESOLVED:preview:{why}",
                               dry_run=True, invocation=call_id or name)
                    sp.remove_preview(name)
                    log(f"INTERRUPTED_UNRESOLVED:preview:{name}|{why}|pgid={pgid}")
                    continue
            if call_id:
                sp.settle_call(call_id, "interrupted")
            sp.log_job(op, tid, "manual", "FAILED:INTERRUPTED", dry_run=True,
                       invocation=call_id or name)
            sp.remove_preview(name)
            log(f"PREVIEW_RECOVERED:{name}")


def recover_running(root, sp):
    """Under the worker lock: prove each orphaned invocation ended before a retry."""
    recover_previews(sp)
    for guard in sp.guards():  # each outstanding invocation on its own
        if guard.get("agent"):
            verdict, why = agent_ended(guard["agent"])
            if verdict == "ended":
                sp.clear_guard(guard["_op"], guard["_task"], guard["_inv"])
                sp.log(f"UNRESOLVED_CLEARED:{guard['_key']}|{guard['_inv']}|ended({why})")
    for job in sp.list_jobs("running"):
        name = job.pop("_name")
        if job.get("_corrupt"):
            op, _, tpart = name.partition("__t")
            sp.write_guard(op, tpart, {"call_id": None, "agent": None, "why": "corrupt_running_entry",
                                       "at": rsp.utc_iso()})
            stub = {"op": op, "task": tpart, "request_ids": []}
            sp.fail(stub, "INTERRUPTED_UNRESOLVED:corrupt_running_entry|pgid=-")
            sp.log_job(op, tpart, None, "FAILED:INTERRUPTED_UNRESOLVED:corrupt_running_entry")
            continue
        call_id, agent = job.get("call_id"), job.get("agent")
        if job.get("spawning") or agent:
            verdict, why = end_or_kill(agent) if agent else ("unknown", "spawn_gap")
            if verdict != "ended":
                pgid = (agent or {}).get("pgid", "-")
                sp.write_guard(job["op"], job["task"], {"call_id": call_id, "agent": agent,
                                                        "why": why, "at": rsp.utc_iso()})
                if call_id and not sp.settled(call_id):
                    sp.settle_call(call_id, "unresolved")
                sp.fail(job, f"INTERRUPTED_UNRESOLVED:{why}|pgid={pgid}")
                sp.log_job(job["op"], job["task"], job.get("trigger"),
                           f"FAILED:INTERRUPTED_UNRESOLVED:{why}")
                sp.log(f"INTERRUPTED_UNRESOLVED:{name}|{why}|pgid={pgid}")
                continue
            if call_id and not sp.settled(call_id):
                sp.settle_call(call_id, "interrupted")
        elif call_id and not sp.settled(call_id):
            sp.settle_call(call_id, "interrupted")  # admitted, never spawned
        interrupted = int(job.get("interrupted", 0)) + 1
        if interrupted >= MAX_INTERRUPTIONS:
            job["interrupted"] = interrupted
            sp.fail(job, "INTERRUPTED")
            sp.log_job(job["op"], job["task"], job.get("trigger"), "FAILED:INTERRUPTED")
            continue
        sp.requeue(job, not_before=time.time(), interrupted=interrupted)
        sp.log(f"RECOVERED:{name}|interrupted={interrupted}")


def process_job(root, sp, job):
    """Run one job; every TERMINAL outcome writes exactly one ``kind:"job"`` row.

    Held and requeued jobs (cap, guard, timeout retry, interruption) write none:
    a retried job is still one job, while each of its attempts is one call.
    """
    tid = job["task"]
    try:
        outcome, _rec = analyse(root, sp, job)
        sp.done(job, outcome)
        sp.log_job(OP, tid, job.get("trigger"), outcome)
        sp.log(f"DONE:t{tid}|{outcome}")
    except JobSkipped as skipped:
        sp.done(job, skipped.outcome)
        sp.log_job(OP, tid, job.get("trigger"), skipped.outcome)
        sp.log(f"{skipped.outcome}:t{tid} (switched off after it was queued)")
    except JobHeld as held:
        sp.resolve_requests(job, held.outcome)
        sp.requeue(job, state=held.state)
        sp.log(f"HELD:t{tid}|{held.state}")
    except JobRetry:
        attempts = int(job.get("attempts", 0)) + 1
        if attempts > MAX_TIMEOUT_RETRIES:
            job["attempts"] = attempts
            sp.fail(job, "TIMEOUT")
            sp.log_job(OP, tid, job.get("trigger"), "FAILED:TIMEOUT")
        else:
            sp.requeue(job, not_before=time.time(), attempts=attempts)
            sp.log(f"RETRY:t{tid}|timeout attempt={attempts}")
    except JobFailed as failed:
        sp.fail(job, failed.reason)
        sp.log_job(OP, tid, job.get("trigger"), f"FAILED:{failed.reason}"[:200])
        sp.log(f"FAILED:t{tid}|{failed.reason}")
    except Exception as exc:  # never let one job take the worker down
        sp.fail(job, f"INTERNAL:{exc.__class__.__name__}")
        sp.log_job(OP, tid, job.get("trigger"), f"FAILED:INTERNAL:{exc.__class__.__name__}")
        sp.log(f"INTERNAL:t{tid}|{traceback.format_exc()[-1500:]}")


def _flush_outbox(root, sp):
    try:
        store = rst.Store(root)
        if store._outbox_paths():
            for line in store.flush():
                sp.log(f"FLUSH:{line}")
    except Exception as exc:
        sp.log(f"FLUSH_ERROR:{exc.__class__.__name__}:{exc}"[:300])


def drain(root, sp):
    while True:
        job = sp.claim()
        if job is not None:
            _test_hook("after_claim", task=job["task"])
            process_job(root, sp, job)
            _test_hook("between_jobs", task=job["task"])
            continue
        pending = sp.pending_unheld()
        if not pending:
            return
        _test_hook("settle_wait")
        now = time.time()
        wake = min(j.get("not_before", now) for j in pending)
        time.sleep(min(max(0.05, wake - now), 30.0))


def run_worker(root) -> int:
    root = ors.toplevel(root)
    sp = rsp.Spool(state_dir(root))
    fd = sp.try_worker_lock()
    if fd is None:
        return 0
    try:
        while True:
            recover_running(root, sp)
            sp.reset_holds()
            _flush_outbox(root, sp)
            drain(root, sp)
            sp.prune_work_dirs()
            _test_hook("before_release")
            sp.release_worker_lock(fd)
            fd = None
            # Shutdown handoff: any non-held job -- ready OR still settling --
            # keeps the work alive. A failed re-acquire means another worker now
            # holds the lock, and its own first scan owns the job.
            _test_hook("after_release")
            if not sp.pending_unheld():
                return 0
            fd = sp.try_worker_lock()
            if fd is None:
                return 0
    finally:
        sp.release_worker_lock(fd)


def start_worker_detached(root, sp=None):
    sp = sp or rsp.Spool(state_dir(root))
    if not sp.worker_lock_free():
        return False
    log = open(sp.log_path, "a")
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "run", str(root)],
                         cwd=str(root), stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, close_fds=True)
    except OSError as exc:
        sp.log(f"WORKER_START_FAILED:{exc}")
        return False
    finally:
        log.close()
    return True


def enqueue_job(root, op, trigger, tid, *, now=False, over_cap=False, request_id=None,
                respect_switches=True):
    """Coalesce a job and start the worker. Returns the job, or a skip reason string."""
    cfg = rcfg.load(root)
    sp = rsp.Spool(state_dir(root))
    if respect_switches:
        if not cfg.enabled:
            return "SKIPPED:disabled"
        if os.environ.get("AIT_RELATIONS") == "0":
            return "SKIPPED:host_off"
        if trigger in rcfg.TRIGGERS and not cfg.trigger_enabled(trigger):
            return f"SKIPPED:trigger_off:{trigger}"
    if op not in OPS_IMPLEMENTED:
        return "SKIPPED:op_unimplemented"
    job = sp.enqueue(op, trigger, rs.norm_id(tid), settle_s=cfg.settle_s, now=now,
                     over_cap=over_cap, request_id=request_id)
    start_worker_detached(root, sp)
    return job


def cmd_enqueue(root, op, trigger, tid) -> int:
    """The detached part of ``aitask_relations_enqueue.sh``. Never raises."""
    sp = None
    try:
        sp = rsp.Spool(state_dir(root))
        if op == OP and trigger == "plan_approved":
            try:
                sha = write_stamp(root, tid)
                sp.log(f"STAMP:t{rs.norm_id(tid)}|{sha or 'disabled'}")
                if sha:
                    _flush_outbox(root, sp)
            except StampError as exc:
                sp.log(f"STAMP_ERROR:t{tid}|{exc}")
        result = enqueue_job(root, op, trigger, tid)
        sp.log(f"ENQUEUE:{op}|{trigger}|t{tid}|{result if isinstance(result, str) else 'queued'}")
    except Exception as exc:
        if sp is not None:
            sp.log(f"ENQUEUE_ERROR:{op}|{trigger}|t{tid}|{exc.__class__.__name__}:{exc}"[:300])
    return 0


def cmd_stamp_publish(root, tid) -> int:
    sp = None
    try:
        sp = rsp.Spool(state_dir(root))
        _flush_outbox(root, sp)
        result = enqueue_job(root, OP, "plan_approved", tid)
        sp.log(f"ENQUEUE:{OP}|plan_approved|t{tid}|{result if isinstance(result, str) else 'queued'}")
    except Exception as exc:
        if sp is not None:
            sp.log(f"STAMP_PUBLISH_ERROR:t{tid}|{exc.__class__.__name__}:{exc}"[:300])
    return 0


def detach(argv, root):
    """Run ``relations_worker.py <argv>`` detached (own session, output to the log)."""
    sp = rsp.Spool(state_dir(root))
    log = open(sp.log_path, "a")
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), *argv], cwd=str(root),
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, close_fds=True)
    finally:
        log.close()


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 2 and argv[0] == "run":
        return run_worker(argv[1])
    if len(argv) == 5 and argv[0] == "enqueue":
        try:
            os.setsid()
        except OSError:
            pass
        return cmd_enqueue(argv[1], argv[2], argv[3], argv[4])
    if len(argv) == 3 and argv[0] == "stamp-publish":
        return cmd_stamp_publish(argv[1], argv[2])
    sys.stderr.write("usage: relations_worker.py run <root> | enqueue <root> <op> <trigger> <id>"
                     " | stamp-publish <root> <id>\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
