#!/usr/bin/env python3
"""Gate orchestrator engine for the aitasks gate framework (t635_11, Phase 4).

The headless, stateless, re-entrant engine that *runs* a task's declared gates.
It reads the task file + ``aitasks/metadata/gates.yaml`` registry, derives the
current per-gate state from the ledger, computes which gates are unlocked, runs
the unlocked machine-gate verifiers (in parallel, within their retry budgets),
observes human gates without ever self-signalling, and stops — all derived from
the ledger, with no frontmatter writes.

This module is **Layer 1**: a pure, unit-testable engine wrapped by
``aitask_run_gates.sh`` (which ``ait gates run`` / ``ait gates unlocked`` and the
autonomous lane call). The ``aitask-run-gates`` skill is the conversational
**Layer 2** front; both call this same engine — neither forks the decision logic.

Design notes:
  * **Verifiers are resolvable COMMANDS** invoked as
    ``<verifier> <task-id> <attempt> <run-id>`` with exit codes
    ``0=pass 1=fail 2=skip 3=error`` (and ``4=pending`` for HUMAN gates only).
  * **Exit code is authoritative.** A verifier may append its own terminal
    block (rich body fields), but its status MUST match its exit code; on
    mismatch the engine appends an ``error`` malformed-correction (last-wins).
  * **Appends go through ``aitask_gate.sh``** so the per-task lock + atomic
    write are reused; the engine never writes the task file directly.
  * **Human-gate signatures are re-validated on every observation** (t1409),
    including after a ``pass`` is already recorded: a witness signed against a
    different code state is demoted in ``_read_state`` and re-pends. Otherwise a
    recorded pass would freeze the code-binding and code changed after sign-off
    could archive unreviewed.
  * **Stopping heuristic** keys off the *code* change surface (HEAD + staged +
    unstaged + untracked, excluding the task/plan data dirs), recorded as
    ``note=stuckhash:`` on the engine-authored ``running`` block — NOT the task
    file (whose gate-run appends would always change its hash).

Stdlib only (mirrors ``gate_ledger.py``).

CLI:
    gate_orchestrator.py run      <task-file> [--task-id ID] [--gate NAME]
                                  [--dry-run] [--max-parallel N] [--registry F]
    gate_orchestrator.py unlocked <task-file> [--registry F]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_ledger as gl  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE_SH = os.path.join(SCRIPTS_DIR, "aitask_gate.sh")
DEFAULT_REGISTRY = os.path.join("aitasks", "metadata", "gates.yaml")

SATISFIED = gl.SATISFIED_STATUSES  # {"pass", "skip"}
_STUCKHASH_RE = re.compile(r"stuckhash:(\S+)")

# --- code change surface + signal witness (re-exported from gate_ledger) ---
#
# These moved into ``gate_ledger`` (t1409) so the read-side archival guard can
# run the SAME freshness classification the engine does, instead of a second
# copy free to drift. They are re-exported under their original names because
# both this module's ``code-digest`` CLI verb and its importers/tests use them.
code_digest = gl.code_digest
_read_witness_digest = gl.read_witness_digest
_task_id_from_file = gl.task_id_from_file


# --- pure decision logic (unit-testable, no subprocess) -------------------

def _runs_by_gate(runs: list) -> dict[str, list]:
    out: dict[str, list] = {}
    for r in runs:
        out.setdefault(r.name, []).append(r)
    return out


def _attempts_used(runs_for_gate: list) -> int:
    """Attempts consumed = terminal fail/error runs (pass/skip satisfy; running/pending don't count).

    BUDGET consumption only. The ledger's attempt ORDINAL is
    ``gate_ledger.next_attempt`` — a different question, which counts every
    terminal run. They coincide on every path that re-dispatches a gate; see that
    function's docstring for where and why they are allowed to diverge (t1262).
    """
    return sum(1 for r in runs_for_gate if r.status in ("fail", "error"))


def _dag_mode(declared: list[str], registry: dict) -> bool:
    """True once ANY declared gate carries an explicit ``unlocks`` (incl. ``[]``).

    The unlock DAG is GLOBAL (framework §Data model): with no explicit ``unlocks``
    anywhere, the order is purely LINEAR (each gate unlocks the next). The moment
    one gate declares ``unlocks``, the registry drives the DAG — gates *without*
    an explicit ``unlocks`` become TERMINAL (they unlock nothing), so a declared
    parallel fan-out is real and not re-chained by an implicit linear edge.
    """
    return any(registry.get(g, {}).get("unlocks") is not None for g in declared)


def successors(gate: str, declared: list[str], registry: dict,
               dag_mode: bool | None = None) -> list[str]:
    """Gates ``gate`` unlocks. An explicit ``unlocks`` (incl. ``[]``) is used
    verbatim. ABSENT (None): the LINEAR next gate when no gate declares unlocks,
    else TERMINAL (the global DAG-mode rule — t635_11, concern 1)."""
    if dag_mode is None:
        dag_mode = _dag_mode(declared, registry)
    u = registry.get(gate, {}).get("unlocks")
    if u is not None:
        return list(u)
    if dag_mode:
        return []
    idx = declared.index(gate) if gate in declared else -1
    return [declared[idx + 1]] if 0 <= idx < len(declared) - 1 else []


def predecessors_map(declared: list[str], registry: dict) -> dict[str, list[str]]:
    dag_mode = _dag_mode(declared, registry)
    preds: dict[str, list[str]] = {g: [] for g in declared}
    for p in declared:
        for s in successors(p, declared, registry, dag_mode):
            if s in preds:
                preds[s].append(p)
    return preds


def _status_of(state: dict, gate: str):
    run = state.get(gate)
    return run.status if run else None


def _satisfied(state: dict, gate: str) -> bool:
    return _status_of(state, gate) in SATISFIED


def is_stuck(runs_for_gate: list, current_digest: str | None) -> bool:
    """Stopping heuristic: ≥2 trailing FAILED runs ran on the CURRENT code.

    Reads the engine-authored ``running`` block's ``note=stuckhash:`` (the code
    digest at dispatch time) for each run id that ended in ``fail``. The gate is
    stuck iff the most recent contiguous run of fails — counting back from the
    latest — has ≥2 whose dispatch digest equals ``current_digest`` (no code
    change since ⇒ deterministic failure ⇒ don't burn the rest of the budget). A
    real code fix flips ``current_digest``, so the old fails no longer match and
    the gate is eligible again. Returns False when the digest is unavailable
    (git absent) — the plain retry budget then governs."""
    if not current_digest:
        return False
    order: list[str] = []
    by_run: dict[str, dict] = {}
    for r in runs_for_gate:
        rid = r.run_id
        if rid not in by_run:
            by_run[rid] = {"terminal": None, "digest": None}
            order.append(rid)
        if r.status == "running":
            m = _STUCKHASH_RE.search(r.body_fields.get("note", ""))
            if m:
                by_run[rid]["digest"] = m.group(1)
        else:
            by_run[rid]["terminal"] = r.status
    count = 0
    for rid in reversed(order):
        term = by_run[rid]["terminal"]
        if term is None:
            continue  # still 'running' (pre-reconcile) — skip
        if term != "fail":
            break
        if by_run[rid]["digest"] == current_digest:
            count += 1
        else:
            break  # a fail on different code — chain of same-code fails ends
    return count >= 2


def compute_unlocked(declared: list[str], registry: dict, state: dict,
                     runs_by_gate: dict) -> list[str]:
    """The DAG rule, per-gate: g is unlocked iff every predecessor is satisfied
    (pass/skip), g itself is not satisfied, and its retry budget is not spent."""
    preds = predecessors_map(declared, registry)
    unlocked: list[str] = []
    for g in declared:
        if _satisfied(state, g):
            continue
        if not all(_satisfied(state, p) for p in preds[g]):
            continue
        mr = registry.get(g, {}).get("max_retries", 0) or 0
        if _attempts_used(runs_by_gate.get(g, [])) >= mr + 1:
            continue
        unlocked.append(g)
    return unlocked


def blocked_reason(g: str, declared: list[str], registry: dict, state: dict,
                   runs_by_gate: dict, digest: str | None = None) -> str:
    preds = predecessors_map(declared, registry)
    unmet = [p for p in preds[g] if not _satisfied(state, p)]
    if unmet:
        return "blocked: upstream " + ", ".join(unmet) + " not satisfied"
    if is_stuck(runs_by_gate.get(g, []), digest):
        return "blocked: exhausted (stopping heuristic — no code change since last failure)"
    mr = registry.get(g, {}).get("max_retries", 0) or 0
    if _attempts_used(runs_by_gate.get(g, [])) >= mr + 1:
        return "blocked: exhausted (retry budget spent)"
    if registry.get(g, {}).get("type") == "human":
        return "blocked: pending human signal"
    if registry.get(g, {}).get("kind") == "procedure":
        return ("needs agent (procedure-backed gate — run via task-workflow / "
                "aitask-resume)")
    # Shared with the pick-time warning in `aitask_gate.sh materialize-active`
    # (t635_34) so the two can never drift. Behaviour-identical to the former
    # inline `not registry.get(g, {}).get("verifier")`: the human and procedure
    # arms above have already returned, so for a machine command gate the
    # predicate reduces to exactly "no registry entry, or no verifier".
    if gl.unverifiable_reason(g, registry):
        return "blocked: no verifier configured (deferred)"
    return "blocked"


def map_exit(code: int, gate_type: str) -> str:
    """Map a verifier exit code to a status. Exit 4 (pending) is HUMAN-only —
    a machine verifier returning 4 is malfunctioning → error (concern 4)."""
    if code == 0:
        return "pass"
    if code == 1:
        return "fail"
    if code == 2:
        return "skip"
    if code == 4:
        return "pending" if gate_type == "human" else "error"
    return "error"


# --- verifier resolution + execution --------------------------------------

def resolve_verifier(verifier: str) -> list[str] | None:
    """Resolve a registry ``verifier:`` value to a runnable command (concern: one
    place owns resolution). A path / existing file runs directly; a bare
    ``aitask-gate-<x>`` → ``.aitask-scripts/aitask_gate_<x>.sh``; anything else is
    treated as a PATH command. Empty → ``None`` (no auto-run)."""
    if not verifier:
        return None
    if "/" in verifier or os.path.isfile(verifier):
        return [verifier]
    m = re.match(r"^aitask-gate-(.+)$", verifier)
    if m:
        return [os.path.join(SCRIPTS_DIR, "aitask_gate_" + m.group(1).replace("-", "_") + ".sh")]
    return [verifier]


def _gate_append(task_id: str, gate: str, status: str, *, only_if_running: str | None = None,
                 **fields) -> None:
    """Append a gate-run block via aitask_gate.sh (reuses its per-task lock)."""
    cmd = [GATE_SH, "append"]
    if only_if_running:
        cmd += ["--only-if-running", only_if_running]
    cmd += [task_id, gate, status]
    for k, v in fields.items():
        if v is not None and v != "":
            cmd.append(f"{k}={v}")
    subprocess.run(cmd, capture_output=True, text=True)


def _spawn_verifier(vcmd: list[str], task_id: str, attempt: int, run_id: str,
                    timeout) -> int:
    """Run the verifier subprocess; return an exit code (3=error on failure to
    launch, error-mapped on timeout — the subprocess is killed before reconcile)."""
    try:
        r = subprocess.run([*vcmd, task_id, str(attempt), run_id],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode
    except subprocess.TimeoutExpired:
        return 3  # killed; treated as error
    except (OSError, subprocess.SubprocessError):
        return 3


def _current_run_status(file: str, run_id: str):
    """Derive the latest status recorded for ``run_id`` (or None)."""
    last = None
    with open(file, encoding="utf-8") as fh:
        for r in gl.parse_gate_run_blocks(fh.read()):
            if r.run_id == run_id:
                last = r.status
    return last


def reconcile_terminal(task_id: str, file: str, gate: str, run_id: str,
                       exit_status: str, attempt: int, reports: list) -> None:
    """Make the ledger's terminal status agree with the exit code (concerns 4,6,B).

    The exit code is authoritative. Three cases:
      * run still ``running`` (verifier appended nothing) → append the engine's
        terminal block (atomic, only-if-running).
      * a terminal block exists AND matches ``exit_status`` → no-op.
      * a terminal block exists but DISAGREES → the verifier self-reported a
        status contradicting its exit code: append a fresh-run_id ``error``
        malformed-correction (last-marker-wins overrides) and report it.
    """
    cur = _current_run_status(file, run_id)
    if cur is None or cur == "running":
        _gate_append(task_id, gate, exit_status, only_if_running=run_id,
                     run=run_id, attempt=str(attempt), type="machine")
        return
    if cur == exit_status:
        return
    note = (f"malformed: verifier reported {cur} but exit code mapped to "
            f"{exit_status}; treated as error")
    _gate_append(task_id, gate, "error", attempt=str(attempt), type="machine", note=note)
    reports.append(f"  ⚠ {gate}: {note}")


# --- the engine -----------------------------------------------------------

class Engine:
    def __init__(self, task_file: str, task_id: str, registry_file: str,
                 max_parallel: int, reports: list):
        self.file = task_file
        self.task_id = task_id
        self.registry = gl.read_registry(registry_file)
        self.max_parallel = max(1, min(max_parallel, os.cpu_count() or 1))
        self.reports = reports
        self.digest = code_digest()

    def _read_state(self):
        with open(self.file, encoding="utf-8") as fh:
            text = fh.read()
        # Enforced active set (t635_33): a profile-filtered gate is never
        # scheduled/recorded; falls back to raw `gates:` when no valid tuple.
        active = gl.read_active_gates_from_text(text)
        runs = gl.parse_gate_run_blocks(text)
        state = {}
        for r in runs:
            state[r.name] = r
        # A recorded pass must NOT freeze the code-binding (t1409). A human gate
        # whose signal witness was signed against a DIFFERENT code state is
        # dropped from the derived view here, at the ONE place state is read, so
        # every consumer — the all-satisfied short-circuit in `run()`,
        # `compute_unlocked`, `blocked_reason`, `_handle_human` and `_force_one`
        # — sees it as unsatisfied without any of them special-casing it. The
        # re-pend itself is then done by `_handle_human`'s existing `stale`
        # branch, so there is no second append site. `runs_by_gate` is left
        # intact: retry budgets and the stopping heuristic are unaffected.
        # The demotion is `gl.demote_stale_signed` (t1416) rather than an inline
        # loop, so this enforcing path and the read-side surfaces share ONE
        # implementation instead of agreeing copies.
        state, _stale = gl.demote_stale_signed(active, self.registry, state,
                                               self.task_id, self.digest)
        return active, state, _runs_by_gate(runs)

    def _run_machine_gate(self, gate: str, runs_by_gate: dict) -> None:
        meta = self.registry.get(gate, {})
        # Budget slot k of max_retries+1, deliberately NOT gl.next_attempt (the
        # ledger ordinal) — line 359 reports this number alongside the budget, so
        # it must stay the budget's own count. See gl.next_attempt (t1262).
        attempt = _attempts_used(runs_by_gate.get(gate, [])) + 1
        run_id = f"{gl.iso_now()}-{gate}-a{attempt}"
        note = f"stuckhash:{self.digest}" if self.digest else None
        _gate_append(self.task_id, gate, "running", run=run_id, attempt=str(attempt),
                     type="machine", verifier=meta.get("verifier", ""), note=note)
        vcmd = resolve_verifier(meta.get("verifier", ""))
        if vcmd is None:
            return
        code = _spawn_verifier(vcmd, self.task_id, attempt, run_id,
                               meta.get("timeout_seconds"))
        status = map_exit(code, meta.get("type", "machine"))
        reconcile_terminal(self.task_id, self.file, gate, run_id, status, attempt, self.reports)
        self.reports.append(f"  {gate}: {status} (attempt {attempt})")

    def _signal_state(self, gate: str) -> tuple[str, str | None]:
        """Classify this gate's signal witness — see :func:`gate_ledger.witness_state`,
        which owns the ``absent`` / ``fresh`` / ``stale`` / ``unstamped`` rule for
        both this engine and the read-side archival guard."""
        return gl.witness_state(gate, self.registry, self.task_id, self.digest)

    def _handle_human(self, gate: str, state: dict) -> bool:
        """Read-side only: pass if a CURRENT signal is present, else pending.
        NEVER self-signals. A witness code-bound to a different state (``stale``)
        is not honored — it re-pends with a note so the human re-signs (t635_15)."""
        kind, recorded = self._signal_state(gate)
        if kind in ("fresh", "unstamped"):
            note = f"signed_digest:{recorded}" if recorded else None
            _gate_append(self.task_id, gate, "pass", type="human", note=note)
            self.reports.append(f"  {gate}: pass (human signal observed)")
            return True
        cur = state.get(gate)
        if kind == "stale":
            note = (f"stale signature: signed against {recorded}, code now "
                    f"{self.digest} — re-sign with 'ait gate pass'")
            if cur is None or cur.status != "pending":
                _gate_append(self.task_id, gate, "pending", type="human", note=note)
                self.reports.append(f"  {gate}: pending — {note}")
                return True
            self.reports.append(f"  {gate}: pending — {note}")
            return False
        # absent
        if cur is None or cur.status != "pending":
            _gate_append(self.task_id, gate, "pending", type="human")
            self.reports.append(f"  {gate}: pending — awaiting human signal")
            return True
        return False

    def run(self, gate=None, dry_run=False) -> int:
        # `active` is the enforced set (t635_33). An empty set — no gates, an
        # opt-out, or a fully profile-filtered task — prints the same sentinel
        # line SKILL.md Step 9 branches on for the legacy inline fallback.
        active, state, runs_by_gate = self._read_state()
        if not active:
            self.reports.append("No gates declared; nothing to do.")
            return 0
        if gate is not None:
            return self._force_one(gate)
        # Safety backstop only — the real terminators are the empty-unlocked
        # return and the no-progress break. Sized for the worst case: every
        # gate's full retry budget plus the unlock-chain depth.
        total_budget = sum((self.registry.get(g, {}).get("max_retries", 0) or 0) + 1
                           for g in active)
        for _ in range(total_budget + len(active) + 2):
            active, state, runs_by_gate = self._read_state()
            if all(_satisfied(state, g) for g in active):
                self.reports.append("All gates satisfied. Task ready for archive "
                                    "(suggest status: Done — not auto-applied).")
                return 0
            unlocked = compute_unlocked(active, self.registry, state, runs_by_gate)
            if not unlocked:
                for g in active:
                    if not _satisfied(state, g):
                        self.reports.append(
                            f"  {g}: " + blocked_reason(g, active, self.registry,
                                                        state, runs_by_gate, self.digest))
                return 0
            machine = [g for g in unlocked
                       if self.registry.get(g, {}).get("type") == "machine"
                       and self.registry.get(g, {}).get("kind") != "procedure"
                       and self.registry.get(g, {}).get("verifier")
                       and not is_stuck(runs_by_gate.get(g, []), self.digest)]
            human = [g for g in unlocked if self.registry.get(g, {}).get("type") == "human"]
            if dry_run:
                self.reports.append("Dry run — would dispatch:")
                self.reports.append("  unlocked: " + ", ".join(unlocked))
                self.reports.append("  machine:  " + (", ".join(machine) or "(none)"))
                self.reports.append("  human:    " + (", ".join(human) or "(none)"))
                return 0
            if not machine and not human:
                # Unlocked gates exist but none are runnable now (empty verifier /
                # stuck). Report why and stop instead of breaking silently.
                for g in unlocked:
                    self.reports.append(
                        f"  {g}: " + blocked_reason(g, active, self.registry,
                                                    state, runs_by_gate, self.digest))
                return 0
            changed = False
            if machine:
                workers = min(self.max_parallel, len(machine))
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    list(ex.map(lambda g: self._run_machine_gate(g, runs_by_gate), machine))
                changed = True
            for g in human:
                if self._handle_human(g, state):
                    changed = True
            if not changed:
                break
        return 0

    def _force_one(self, gate: str) -> int:
        """`--gate`: force-run one gate, overriding skip-already-passed + budget,
        but only when its predecessors are satisfied (concern 7)."""
        active, state, runs_by_gate = self._read_state()
        if gate not in active:
            self.reports.append(f"{gate}: not in this task's active gate set")
            return 0
        preds = predecessors_map(active, self.registry).get(gate, [])
        unmet = [p for p in preds if not _satisfied(state, p)]
        if unmet:
            self.reports.append(f"{gate}: predecessors not satisfied ({', '.join(unmet)}) — not forced")
            return 0
        meta = self.registry.get(gate, {})
        if meta.get("type") == "human":
            self._handle_human(gate, state)
        elif meta.get("verifier"):
            self._run_machine_gate(gate, runs_by_gate)
        else:
            self.reports.append(f"{gate}: no verifier configured — nothing to run")
        return 0


def run(task_file: str, task_id: str, *, gate=None, dry_run=False,
        max_parallel=2, registry_file=DEFAULT_REGISTRY) -> tuple[int, list]:
    reports: list = []
    rc = Engine(task_file, task_id, registry_file, max_parallel, reports).run(gate, dry_run)
    return rc, reports


def unlocked(task_file: str, registry_file=DEFAULT_REGISTRY,
             current_digest=gl._COMPUTE_DIGEST) -> list[str]:
    """The unlocked set for ``ait gates unlocked``.

    Re-validates code-bound signatures exactly as :meth:`Engine._read_state`
    does (t1416), through the same ``gl.demote_stale_signed`` seam — so this
    introspection verb cannot disagree with the enforcing ``Engine.run`` about
    which gates are outstanding. It was left ledger-only by t1409 on an
    affordability argument borrowed from the per-task TUI surfaces, but that
    argument never applied here: this is a one-shot, single-task, human-invoked
    verb, so re-validation costs at most one ``code_digest()`` — and nothing at
    all unless the task carries a stamped witness.

    Read-only, like every other introspection verb: a stale signature makes the
    gate appear unlocked (work to do), and recording the resulting ``pending``
    remains ``ait gates run``'s job alone.
    """
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    active = gl.read_active_gates_from_text(text)  # enforced set (t635_33)
    registry = gl.read_registry(registry_file)
    runs = gl.parse_gate_run_blocks(text)          # parse ONCE, feed both views
    state = {r.name: r for r in runs}
    state, _stale = gl.demote_stale_signed(
        active, registry, state, gl.task_id_from_file(task_file), current_digest)
    return compute_unlocked(active, registry, state, _runs_by_gate(runs))


# --- CLI ------------------------------------------------------------------

def _pop_opt(argv: list[str], name: str, default=None):
    if name in argv:
        i = argv.index(name)
        val = argv[i + 1] if i + 1 < len(argv) else default
        del argv[i:i + 2]
        return val
    return default


def _pop_flag(argv: list[str], name: str) -> bool:
    if name in argv:
        argv.remove(name)
        return True
    return False


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write(__doc__ or "")
        return 2
    cmd, rest = argv[0], list(argv[1:])

    if cmd == "run":
        registry = _pop_opt(rest, "--registry", DEFAULT_REGISTRY)
        gate = _pop_opt(rest, "--gate")
        task_id_opt = _pop_opt(rest, "--task-id")
        max_parallel = int(_pop_opt(rest, "--max-parallel", "2") or "2")
        dry_run = _pop_flag(rest, "--dry-run")
        if not rest:
            sys.stderr.write("Usage: gate_orchestrator.py run <task-file> [...]\n")
            return 2
        task_file = rest[0]
        task_id = task_id_opt or _task_id_from_file(task_file)
        rc, reports = run(task_file, task_id, gate=gate, dry_run=dry_run,
                          max_parallel=max_parallel, registry_file=registry)
        for line in reports:
            sys.stdout.write(line + "\n")
        return rc

    if cmd == "code-digest":
        # Emit the current code-state digest (t635_15) — used by `ait gate pass`
        # to code-bind a human-gate signal witness. Exit 1 when unavailable.
        d = code_digest()
        if d is None:
            return 1
        sys.stdout.write(d + "\n")
        return 0

    if cmd == "unlocked":
        registry = _pop_opt(rest, "--registry", DEFAULT_REGISTRY)
        if not rest:
            sys.stderr.write("Usage: gate_orchestrator.py unlocked <task-file> [--registry F]\n")
            return 2
        for g in unlocked(rest[0], registry):
            sys.stdout.write(g + "\n")
        return 0

    sys.stderr.write(f"Unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
