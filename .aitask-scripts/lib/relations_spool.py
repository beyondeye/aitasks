#!/usr/bin/env python3
"""relations_spool.py - the relations job spool, cap admission and ledgers (t1981_3).

Design: aidocs/framework/task_relations.md D5 ("Spool and worker", "Usage is
measured") and the "Worker API" section. All state is per clone, under
``<git-common-dir>/aitask-relations/spool/``::

    jobs/<op>__t<id>.json       queued job (one per (op, task): coalescing)
    running/<op>__t<id>.json    the job the worker holds (only the lock holder)
    failed/<op>__t<id>.json     a failed job and its reason
    unresolved/<op>__t<id>/<invocation>.json
                                one per interrupted invocation whose end could not
                                be established; the key is blocked while ANY remains
    previews/<call_id>.json     the ownership record of a running dry run (its
                                owner process, `spawning`, `agent`), so a killed
                                preview is recovered like a running job
    results/<request_id>.json   the outcome of a request (``--now --wait``)
    work/<run_id>/              a job's materialized inputs, prompt and output
    spool.lock                  flock: every spool mutation
    worker.lock                 flock: the single worker
    usage.lock                  flock: ledger appends and cap admission
    recovery.lock               flock: one interrupted-invocation recovery at a time
    enqueue.log                 diagnostics of the detached parts

and, directly under ``<git-common-dir>/aitask-relations/`` (D13's per-host
ledgers), ``usage.jsonl``: calls (reservations), their outcomes, and the jobs
that made no call.

**Admission.** Every real agent call reserves its slot with ``admit()`` BEFORE
it is made; the reservation is appended under ``usage.lock`` together with the
count check, so two callers can never both take the last slot, and it consumes
allowance whatever happens next. ``settle_call()`` appends the outcome (token
and cost fields ``None`` = unknown, never 0).
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import fcntl
import json
import os
import shutil
import socket
import time
import uuid

TRIGGER_PRIORITY = {"plan_approved": 2}  # every other trigger: 1
HOLD_CAPPED = "capped"
HOLD_BLOCKED = "blocked_unresolved"
KEEP_WORK_DIRS = 20


class Blocked(RuntimeError):
    """An unresolved invocation guards the task; no new launch may be admitted."""


class CapReached(RuntimeError):
    def __init__(self, used, cap):
        super().__init__(f"CAP_REACHED:{used}/{cap}")
        self.used, self.cap = used, cap


def utc_iso(ts=None) -> str:
    dt = _dt.datetime.fromtimestamp(time.time() if ts is None else ts, _dt.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def key(op: str, tid: str) -> str:
    return f"{op}__t{tid}"


def _priority(trigger) -> int:
    return TRIGGER_PRIORITY.get(trigger, 1)


class Spool:
    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self.root = os.path.join(state_dir, "spool")
        for sub in ("jobs", "running", "failed", "unresolved", "results", "work", "previews"):
            os.makedirs(os.path.join(self.root, sub), exist_ok=True)
        # Ledgers sit next to the spool, directly under aitask-relations/ (D13):
        # usage.jsonl here; pull.jsonl / notify.jsonl are t1981_5's.
        self.usage_path = os.path.join(state_dir, "usage.jsonl")
        self.log_path = os.path.join(self.root, "enqueue.log")

    # ----------------------------------------------------------- primitives
    def path(self, sub, name):
        return os.path.join(self.root, sub, name + ".json") if name else os.path.join(self.root, sub)

    @contextlib.contextmanager
    def _flock(self, name):
        fd = os.open(os.path.join(self.root, name), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def recovery_lock(self):
        """flock serializing every interrupted-invocation recovery transition."""
        return self._flock("recovery.lock")

    def try_worker_lock(self):
        """The worker lock's fd, or None when another worker holds it."""
        fd = os.open(os.path.join(self.root, "worker.lock"), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return None
        return fd

    @staticmethod
    def release_worker_lock(fd):
        if fd is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def worker_lock_free(self) -> bool:
        fd = self.try_worker_lock()
        if fd is None:
            return False
        self.release_worker_lock(fd)
        return True

    @staticmethod
    def _read(path):
        try:
            with open(path, "rb") as fh:
                obj = json.loads(fh.read().decode("utf-8"))
        except FileNotFoundError:
            return None
        except (ValueError, UnicodeDecodeError):
            return {"_corrupt": True}
        return obj if isinstance(obj, dict) else {"_corrupt": True}

    @staticmethod
    def _write(path, obj):
        tmp = f"{path}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
        data = (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)

    def log(self, line: str):
        with contextlib.suppress(OSError):
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(f"{utc_iso()} [{os.getpid()}] {line}\n")

    # ------------------------------------------------------------- enqueue
    def enqueue(self, op, trigger, tid, *, settle_s, now=False, over_cap=False,
                request_id=None, ts=None) -> dict:
        """Coalesce a request into the ``(op, task)`` job (D4 "Coalescing")."""
        ts = time.time() if ts is None else ts
        name = key(op, tid)
        with self._flock("spool.lock"):
            job = self._read(self.path("jobs", name))
            if job is None or job.get("_corrupt"):
                job = {"op": op, "task": tid, "trigger": trigger, "enqueued_at": ts,
                       "now": False, "over_cap": False, "attempts": 0, "interrupted": 0,
                       "request_ids": [], "state": None}
            if _priority(trigger) >= _priority(job.get("trigger")):
                job["trigger"] = trigger
            job["not_before"] = ts + max(0, settle_s)
            job["now"] = bool(job.get("now")) or now
            job["over_cap"] = bool(job.get("over_cap")) or over_cap
            if request_id and request_id not in job["request_ids"]:
                job["request_ids"].append(request_id)
            # A new request re-opens a capped job for re-evaluation (the cap is
            # checked again at claim time). A blocked hold is NOT cleared: it
            # follows its unresolved guard (reset_holds / the launch check).
            if job.get("state") == HOLD_CAPPED:
                job["state"] = None
            self._write(self.path("jobs", name), job)
            # A new request supersedes an old failure; an UNRESOLVED guard is
            # deliberately never removed here (only `ended` or a human unblock).
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.path("failed", name))
        return job

    # ----------------------------------------------------------- selection
    def list_jobs(self, sub="jobs") -> list:
        out = []
        for entry in sorted(os.listdir(self.path(sub, None))):
            if entry.endswith(".json"):
                job = self._read(os.path.join(self.path(sub, None), entry))
                if job is not None:
                    job["_name"] = entry[:-5]
                    out.append(job)
        return out

    @staticmethod
    def is_ready(job, ts) -> bool:
        if job.get("_corrupt") or job.get("state") in (HOLD_CAPPED, HOLD_BLOCKED):
            return False
        return bool(job.get("now")) or job.get("not_before", 0) <= ts

    def pending_unheld(self) -> list:
        """Queued jobs that are not held (capped / blocked): ready or settling."""
        return [j for j in self.list_jobs() if not j.get("_corrupt")
                and j.get("state") not in (HOLD_CAPPED, HOLD_BLOCKED)]

    def claim(self, ts=None):
        """Move the next ready job into ``running/``; None when nothing is ready."""
        ts = time.time() if ts is None else ts
        with self._flock("spool.lock"):
            ready = [j for j in self.list_jobs() if self.is_ready(j, ts)]
            if not ready:
                return None
            ready.sort(key=lambda j: (not j.get("now"), j.get("not_before", 0), j["_name"]))
            job = ready[0]
            name = job.pop("_name")
            os.replace(self.path("jobs", name), self.path("running", name))
            job["claimed_at"] = ts
            self._write(self.path("running", name), job)
            return job

    def update_running(self, job, **fields):
        job.update(fields)
        with self._flock("spool.lock"):
            self._write(self.path("running", key(job["op"], job["task"])), job)

    def reset_holds(self):
        """At worker start: re-evaluate capped jobs; unblock jobs with no guard."""
        with self._flock("spool.lock"):
            for job in self.list_jobs():
                name = job.pop("_name")
                state = job.get("state")
                op, _, tpart = name.partition("__t")
                if state == HOLD_CAPPED or (state == HOLD_BLOCKED and not self.has_guard(op, tpart)):
                    job["state"] = None
                    self._write(self.path("jobs", name), job)

    # ------------------------------------------------------------- outcomes
    def _merge_into_queued(self, running, queued):
        if _priority(running.get("trigger")) > _priority(queued.get("trigger")):
            queued["trigger"] = running["trigger"]
        queued["now"] = bool(queued.get("now")) or bool(running.get("now"))
        queued["over_cap"] = bool(queued.get("over_cap")) or bool(running.get("over_cap"))
        for rid in running.get("request_ids", []):
            if rid not in queued.setdefault("request_ids", []):
                queued["request_ids"].append(rid)
        queued["attempts"] = max(queued.get("attempts", 0), running.get("attempts", 0))
        queued["interrupted"] = max(queued.get("interrupted", 0), running.get("interrupted", 0))
        return queued

    def requeue(self, job, *, state=None, not_before=None, **fields):
        """Put a running job back in ``jobs/`` (merging a newer queued request)."""
        name = key(job["op"], job["task"])
        clean = {k: v for k, v in job.items()
                 if k not in ("spawning", "agent", "call_id", "claimed_at", "_name")}
        clean.update(fields)
        clean["state"] = state
        if not_before is not None:
            clean["not_before"] = not_before
        with self._flock("spool.lock"):
            queued = self._read(self.path("jobs", name))
            if queued is not None and not queued.get("_corrupt"):
                merged = self._merge_into_queued(clean, queued)
                if state is not None:
                    merged["state"] = state
                self._write(self.path("jobs", name), merged)
            else:
                self._write(self.path("jobs", name), clean)
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.path("running", name))

    def _results(self, request_ids, task, outcome):
        for rid in request_ids or []:
            self._write(self.path("results", rid),
                        {"request_id": rid, "task": task, "outcome": outcome, "at": utc_iso()})

    def resolve_requests(self, job, outcome):
        self._results(job.get("request_ids"), job["task"], outcome)

    def done(self, job, outcome):
        name = key(job["op"], job["task"])
        with self._flock("spool.lock"):
            self._results(job.get("request_ids"), job["task"], outcome)
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.path("running", name))

    def fail(self, job, reason):
        name = key(job["op"], job["task"])
        with self._flock("spool.lock"):
            rec = {k: v for k, v in job.items() if k != "_name"}
            rec.update({"reason": reason, "failed_at": utc_iso()})
            self._write(self.path("failed", name), rec)
            self._results(job.get("request_ids"), job["task"], f"FAILED:{reason}")
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.path("running", name))

    def result(self, request_id):
        return self._read(self.path("results", request_id))

    # -------------------------------------------------------------- guards
    # One entry PER UNRESOLVED INVOCATION: unresolved/<op>__t<id>/<invocation>.json.
    # A task is blocked while ANY of its entries remains, so a second
    # interrupted invocation can never overwrite the first one's protection,
    # and clearing one entry (its agent provably ended) leaves the others.
    def _guard_dir(self, op, tid):
        return os.path.join(self.root, "unresolved", key(op, tid))

    def write_guard(self, op, tid, guard: dict) -> str:
        inv = str(guard.get("call_id") or f"x{uuid.uuid4().hex}")
        with self._flock("spool.lock"):
            os.makedirs(self._guard_dir(op, tid), exist_ok=True)
            self._write(os.path.join(self._guard_dir(op, tid), f"{inv}.json"),
                        dict(guard, invocation=inv))
        return inv

    def guard(self, op, tid) -> list:
        """Every outstanding unresolved invocation of ``(op, task)`` (``[]`` = none)."""
        d = self._guard_dir(op, tid)
        out = []
        try:
            names = sorted(os.listdir(d))
        except FileNotFoundError:
            return out
        for name in names:
            if name.endswith(".json"):
                rec = self._read(os.path.join(d, name)) or {"_corrupt": True}
                rec["_inv"] = name[:-5]
                out.append(rec)
        return out

    def has_guard(self, op, tid) -> bool:
        return bool(self.guard(op, tid))

    def clear_guard(self, op, tid, inv):
        with self._flock("spool.lock"):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(os.path.join(self._guard_dir(op, tid), f"{inv}.json"))
            with contextlib.suppress(OSError):
                os.rmdir(self._guard_dir(op, tid))  # only when no invocation remains

    def guards(self) -> list:
        """Every outstanding invocation of every key, each with ``_key`` and ``_inv``."""
        base = os.path.join(self.root, "unresolved")
        out = []
        for entry in sorted(os.listdir(base)):
            if os.path.isdir(os.path.join(base, entry)):
                op, _, tpart = entry.partition("__t")
                for rec in self.guard(op, tpart):
                    rec["_key"] = entry
                    rec["_op"], rec["_task"] = op, tpart
                    out.append(rec)
        return out

    # ------------------------------------------------------------ previews
    def write_preview(self, call_id, rec: dict):
        with self._flock("spool.lock"):
            self._write(self.path("previews", call_id), rec)

    def update_preview(self, call_id, **fields):
        with self._flock("spool.lock"):
            rec = self._read(self.path("previews", call_id)) or {}
            rec.update(fields)
            self._write(self.path("previews", call_id), rec)

    def remove_preview(self, call_id):
        with self._flock("spool.lock"):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.path("previews", call_id))

    def previews(self) -> list:
        return self.list_jobs("previews")

    # ------------------------------------------------------------ job state
    def job_state(self, tid, op="relations", ts=None):
        """``pending(..)`` / ``failed(..)`` for D1's ``ANALYSIS:``, or None."""
        ts = time.time() if ts is None else ts
        name = key(op, tid)
        if self.has_guard(op, tid):
            return "failed(interrupted_unresolved)"
        if os.path.exists(self.path("running", name)):
            return "pending(running)"
        job = self._read(self.path("jobs", name))
        if job is not None and not job.get("_corrupt"):
            if job.get("state") == HOLD_CAPPED:
                return "pending(capped)"
            if job.get("state") == HOLD_BLOCKED:
                return "failed(interrupted_unresolved)"
            if not job.get("now") and job.get("not_before", 0) > ts:
                return "pending(settling)"
            return "pending(queued)"
        failed = self._read(self.path("failed", name))
        if failed is not None:
            reason = str(failed.get("reason", "unknown")).split("|", 1)[0]
            return f"failed({reason.lower()})"
        return None

    # ------------------------------------------------------------ work dirs
    def new_work_dir(self, run_id) -> str:
        path = os.path.join(self.root, "work", run_id)
        os.makedirs(os.path.join(path, "inputs"), exist_ok=True)
        return path

    def prune_work_dirs(self, keep=KEEP_WORK_DIRS):
        base = os.path.join(self.root, "work")
        entries = sorted((os.path.getmtime(os.path.join(base, e)), e) for e in os.listdir(base))
        for _mt, entry in entries[:-keep] if keep else entries:
            shutil.rmtree(os.path.join(base, entry), ignore_errors=True)

    # ------------------------------------------------------- usage ledger
    def _append(self, row: dict):
        data = (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(self.usage_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

    def read_ledger(self, path=None):
        """``(rows, corrupt_line_numbers)`` -- a corrupt line is reported, never skipped silently."""
        rows, corrupt = [], []
        try:
            with open(path or self.usage_path, "rb") as fh:
                for n, raw in enumerate(fh, 1):
                    if not raw.strip():
                        continue
                    try:
                        obj = json.loads(raw.decode("utf-8"))
                        if not isinstance(obj, dict):
                            raise ValueError
                        rows.append(obj)
                    except (ValueError, UnicodeDecodeError):
                        corrupt.append(n)
        except FileNotFoundError:
            pass
        return rows, corrupt

    @staticmethod
    def _today(ts=None) -> str:
        return utc_iso(ts)[:10]

    def calls_today(self, op, ts=None) -> int:
        day = self._today(ts)
        rows, _ = self.read_ledger()
        return sum(1 for r in rows if r.get("kind") == "call" and r.get("op") == op
                   and str(r.get("at", "")).startswith(day))

    def cap_reached(self, op, cap, ts=None) -> bool:
        return self.calls_today(op, ts) >= cap

    def admit(self, op, tid, trigger, *, cap, dry_run=False, over_cap=False, ts=None) -> str:
        """Reserve one agent call (atomic check + append); raise ``CapReached``."""
        with self._flock("usage.lock"):
            used = self.calls_today(op, ts)
            if used >= cap and not over_cap:
                raise CapReached(used, cap)
            call_id = uuid.uuid4().hex
            self._append({"kind": "call", "call_id": call_id, "at": utc_iso(ts),
                          "host": socket.gethostname(), "op": op, "task": tid,
                          "trigger": trigger, "dry_run": bool(dry_run),
                          "over_cap": bool(over_cap) and used >= cap})
            return call_id

    def admit_unguarded(self, op, tid, trigger, *, cap, dry_run=False, over_cap=False, ts=None) -> str:
        """``admit()`` made atomic with the final unresolved-guard check.

        Runs under ``spool.lock``, the lock every ``write_guard`` takes, so a
        guard written after the caller's earlier (liveness-checking) scan is
        either visible here -- ``Blocked`` -- or written after this reservation.
        Lock order is spool.lock -> usage.lock; nothing takes them the other way.
        """
        with self._flock("spool.lock"):
            if self.has_guard(op, tid):
                raise Blocked(f"BLOCKED_UNRESOLVED:{op}|t{tid}")
            return self.admit(op, tid, trigger, cap=cap, dry_run=dry_run, over_cap=over_cap, ts=ts)

    def settle_call(self, call_id, outcome, usage=None):
        """Append the call's outcome -- at most once per call_id (idempotent)."""
        usage = usage or {}
        with self._flock("usage.lock"):
            rows, _ = self.read_ledger()
            if any(r.get("kind") == "outcome" and r.get("call_id") == call_id for r in rows):
                return False
            self._append({"kind": "outcome", "call_id": call_id, "at": utc_iso(),
                          "outcome": outcome,
                          "input_tokens": usage.get("input_tokens"),
                          "output_tokens": usage.get("output_tokens"),
                          "cost_usd": usage.get("cost_usd"),
                          "wall_s": usage.get("wall_s")})
            return True

    def settled(self, call_id) -> bool:
        rows, _ = self.read_ledger()
        return any(r.get("kind") == "outcome" and r.get("call_id") == call_id for r in rows)

    def log_job(self, op, tid, trigger, outcome, invocation=None, **extra):
        """One terminal ``kind:"job"`` row; with ``invocation``, at most one per invocation."""
        row = {"kind": "job", "at": utc_iso(), "host": socket.gethostname(), "op": op,
               "task": tid, "trigger": trigger, "outcome": outcome}
        if invocation is not None:
            row["invocation"] = invocation
        row.update(extra)
        with self._flock("usage.lock"):
            if invocation is not None:
                rows, _ = self.read_ledger()
                if any(r.get("kind") == "job" and r.get("invocation") == invocation for r in rows):
                    return False
            self._append(row)
            return True

    def log_unblock(self, op, tid, how):
        with self._flock("usage.lock"):
            self._append({"kind": "unblock", "at": utc_iso(), "host": socket.gethostname(),
                          "op": op, "task": tid, "how": how})


def job_state(state_dir, tid, op="relations"):
    """Module-level hook used by ``relations_store.analysis_line``."""
    if not state_dir or not os.path.isdir(os.path.join(state_dir, "spool")):
        return None
    return Spool(state_dir).job_state(tid, op)
